"""Settings and API keys from the web app: raw config edits, backups, .env secrets."""

import http.client
import json
import os
import shutil
import stat
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from dotenv import dotenv_values

from src.archive import ItemArchive
from src.processing import ProfileRegistry
from src.settings_api import SettingsService
from src.web_api import build_context, make_handler, resolve

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ProfileRegistry.load(ROOT / "profiles", "tech-news")
SECRET = "sk-test-'quoted' \"double\" #hash $DOLLAR \\back"


@pytest.fixture
def service(tmp_path, monkeypatch) -> SettingsService:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = json.loads((ROOT / "data" / "config.example.json").read_text())
    config["ai"]["model"] = "${LUCIDNEWS_TEST_MODEL}"  # a placeholder must survive every write
    config["ai"]["base_url"] = "${LUCIDNEWS_TEST_BASE_URL}"
    monkeypatch.setenv("LUCIDNEWS_TEST_MODEL", "gemini-2.5-flash")
    (tmp_path / "config.json").write_text(json.dumps(config, indent=2))
    changes = []
    service = SettingsService(
        config_path=tmp_path / "config.json",
        backup_dir=tmp_path / "backups",
        profiles=PROFILES,
        env_path=tmp_path / ".env",
        on_change=lambda: changes.append(1),
    )
    service.changes = changes  # type: ignore[attr-defined]
    return service


def raw(service: SettingsService) -> dict:
    return json.loads(service.config_path.read_text())


# Configuration ---------------------------------------------------------------------


def test_get_reports_values_options_and_locked_fields(service) -> None:
    status, body = service.get()

    assert status == 200
    assert body["values"]["ai"]["model"] == "gemini-2.5-flash"  # expanded for display
    assert body["values"]["ai"]["languages"] == ["en", "fr"]
    assert body["values"]["profiles"]["tech-news"]["topic_dedup"] in (True, False)
    assert "ai.model" in body["locked"]
    assert {"id": "gemini", "model": "gemini-1.5-flash", "api_key_env": "GOOGLE_API_KEY"} in body["options"]["providers"]
    assert {label for label in body["options"]["labels"]} == {"confirmed", "reliable", "unverified", "rumor"}


def test_update_writes_normalized_values_and_keeps_placeholders(service) -> None:
    _, current = service.get()

    status, body = service.update(
        {
            "version": current["version"],
            "values": {
                "ai": {"max_tokens_per_run": "200000", "languages": ["fr"]},
                "collection": {"time_window_hours": 48},
                "profiles": {"tech-news": {"threshold": 6.5, "topic_dedup": False}},
                "reliability": {"exclude_labels": ["rumor"]},
            },
        }
    )

    assert status == 200, body
    stored = raw(service)
    assert stored["ai"]["max_tokens_per_run"] == 200000  # "200000" stored as a number
    assert stored["ai"]["languages"] == ["fr"]
    assert stored["ai"]["model"] == "${LUCIDNEWS_TEST_MODEL}"
    assert stored["ai"]["base_url"] == "${LUCIDNEWS_TEST_BASE_URL}"
    assert stored["collection"]["time_window_hours"] == 48
    assert stored["processing"]["profile_settings"]["tech-news"] == {"threshold": 6.5, "topic_dedup": False}
    assert stored["reliability"]["exclude_labels"] == ["rumor"]
    assert body["version"] != current["version"]
    assert service.changes == [1]
    assert len(list((service.backup_dir).iterdir())) == 1


def test_stale_version_is_refused(service) -> None:
    before = service.config_path.read_text()

    status, _ = service.update({"version": "outdated", "values": {"collection": {"time_window_hours": 12}}})

    assert status == 409
    assert service.config_path.read_text() == before


@pytest.mark.parametrize(
    "values, field",
    [
        ({"ai": {"max_tokens_per_run": 0}}, "ai.max_tokens_per_run"),
        ({"ai": {"provider": "skynet"}}, "ai.provider"),
        ({"digest": {"unanalyzed_max_items": -1}}, "digest.unanalyzed_max_items"),
        ({"profiles": {"tech-news": {"threshold": 11}}}, "profiles.tech-news.threshold"),
        ({"profiles": {"nope": {"threshold": 5}}}, "profiles.nope"),
        ({"ai": {"model": "other"}}, "ai.model"),  # locked by a ${VARIABLE}
        ({"email": {"password_env": "X"}}, "email.password_env"),  # not editable here
    ],
)
def test_invalid_settings_are_refused_without_touching_the_file(service, values, field) -> None:
    before = service.config_path.read_text()
    _, current = service.get()

    status, body = service.update({"version": current["version"], "values": values})

    assert status == 422
    assert field in body["fields"]
    assert service.config_path.read_text() == before
    assert service.changes == []


def test_a_key_pasted_as_variable_name_is_refused_and_not_echoed(service) -> None:
    _, current = service.get()

    status, body = service.update(
        {"version": current["version"], "values": {"ai": {"api_key_env": "AIzaSyFAKEKEYVALUE123"}}}
    )

    assert status == 422
    assert "AIzaSyFAKEKEYVALUE123" not in json.dumps(body)


def test_backups_can_be_listed_and_restored(service) -> None:
    original = raw(service)
    _, current = service.get()
    service.update({"version": current["version"], "values": {"collection": {"time_window_hours": 6}}})

    _, listing = service.backups()
    assert len(listing["backups"]) == 1
    name = listing["backups"][0]["name"]
    assert datetime.fromisoformat(listing["backups"][0]["saved_at"]).tzinfo == timezone.utc

    status, _ = service.restore({"name": name})
    assert status == 200
    assert raw(service) == original
    assert service.restore({"name": "../config.json"})[0] == 400
    assert service.restore({"name": "config-20000101T000000Z.json"})[0] == 404


def test_only_ten_backups_are_kept(service) -> None:
    for hours in range(1, 13):
        _, current = service.get()
        service.update({"version": current["version"], "values": {"collection": {"time_window_hours": hours}}})

    assert len(service.backups()[1]["backups"]) == 10


# API keys ---------------------------------------------------------------------------


def test_secrets_lists_declared_variables_without_values(service, monkeypatch) -> None:
    monkeypatch.setenv("LUCIDNEWS_TEST_BASE_URL", "https://example.com")

    status, body = service.secrets()

    assert status == 200
    by_name = {entry["name"]: entry for entry in body["secrets"]}
    assert by_name["GOOGLE_API_KEY"] == {
        "name": "GOOGLE_API_KEY", "used_by": ["ai:gemini"], "in_file": False, "in_environment": False,
    }
    assert by_name["LUCIDNEWS_TEST_BASE_URL"]["in_environment"] is True
    assert "https://example.com" not in json.dumps(body)


def test_a_secret_is_written_to_env_privately_and_never_returned(service) -> None:
    (service.env_path).write_text("# my notes\nOTHER=keep\nGOOGLE_API_KEY=old\n")

    status, body = service.set_secret("GOOGLE_API_KEY", {"value": f"  {SECRET}  "})

    assert status == 200 and body == {"name": "GOOGLE_API_KEY", "in_file": True}
    assert dotenv_values(service.env_path) == {"OTHER": "keep", "GOOGLE_API_KEY": SECRET}
    assert service.env_path.read_text().startswith("# my notes\n")
    assert stat.S_IMODE(os.stat(service.env_path).st_mode) == 0o600
    listing = json.dumps(service.secrets()[1])
    assert SECRET not in listing and "in_file\": true" in listing

    assert service.delete_secret("GOOGLE_API_KEY")[0] == 200
    assert dotenv_values(service.env_path) == {"OTHER": "keep"}
    assert service.delete_secret("GOOGLE_API_KEY")[0] == 404


@pytest.mark.parametrize("value", ["", "   ", "line1\nline2", "x" * 5000])
def test_invalid_secret_values_are_refused(service, value) -> None:
    status, body = service.set_secret("GOOGLE_API_KEY", {"value": value})

    assert status == 422
    assert not service.env_path.exists()
    assert value.strip() == "" or value not in json.dumps(body)


def test_undeclared_variables_cannot_be_written(service) -> None:
    assert service.set_secret("PATH", {"value": "/tmp"})[0] == 404
    assert not service.env_path.exists()


# HTTP ---------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)  # profiles_dir is relative to the project
    ctx = build_context(str(tmp_path), None, local_features=True)
    ctx.settings.env_path = tmp_path / ".env"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield ctx, server.server_address[1]
    server.shutdown()
    server.server_close()


def _request(port, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
    conn = http.client.HTTPConnection("127.0.0.1", port)
    data = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=data, headers={"Content-Type": "application/json", **(headers or {})})
    response = conn.getresponse()
    payload = json.loads(response.read() or b"{}")
    conn.close()
    return response.status, payload


def test_http_settings_are_local_only_and_reload_the_api(api, capfd) -> None:
    ctx, port = api
    local = {"Origin": "http://localhost:5173"}

    status, current = _request(port, "GET", "/api/settings")
    assert status == 200
    assert _request(port, "GET", "/api/settings", headers={"Host": "evil.example"})[0] == 403
    assert _request(port, "PUT", "/api/secrets/GOOGLE_API_KEY", {"value": SECRET},
                    {"Origin": "https://evil.example"})[0] == 403

    status, _ = _request(port, "PUT", "/api/secrets/GOOGLE_API_KEY", {"value": SECRET}, local)
    assert status == 200
    status, body = _request(port, "PUT", "/api/settings",
                            {"version": current["version"], "values": {"ai": {"languages": ["fr"]}}}, local)
    assert status == 200 and body["values"]["ai"]["languages"] == ["fr"]
    assert ctx.default_language == "fr"  # the API now serves the new configuration
    assert ctx.settings.config_path == ctx.settings.config_path.parent / "config.json"

    logs = capfd.readouterr()
    assert SECRET not in logs.out + logs.err


def test_settings_routes_are_absent_without_local_features(tmp_path, monkeypatch) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)
    ctx = build_context(str(tmp_path), None, local_features=False)

    assert resolve(ctx, "/api/settings", {})[0] == 403
    assert resolve(ctx, "/api/secrets", {})[0] == 403


def test_unchanged_values_leave_the_file_alone(service) -> None:
    _, current = service.get()
    before = service.config_path.read_text()

    status, body = service.update({"version": current["version"], "values": current["values"]})

    assert status == 200
    assert service.config_path.read_text() == before  # no default written, no backup
    assert not service.backup_dir.exists()
    assert service.changes == []


def test_only_changed_fields_are_written(service) -> None:
    _, current = service.get()
    values = json.loads(json.dumps(current["values"]))
    values["collection"]["time_window_hours"] = 36
    before = raw(service)

    service.update({"version": current["version"], "values": values})

    after = raw(service)
    assert after["collection"]["time_window_hours"] == 36
    assert {key for key in after if after[key] != before.get(key)} == {"collection"}
