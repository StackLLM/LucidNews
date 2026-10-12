"""Start the pipeline from the web app, follow it, schedule it (lot 20).

The pipeline itself is replaced by a short script and launchctl by a recorder:
these tests never call the AI and never load anything into launchd.
"""

import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lucidnews.archive import ItemArchive
from lucidnews.run_lock import LOCK_NAME, current_holder, run_lock
from lucidnews.runs_api import ALREADY_RUNNING, RunService, ScheduleService, clean_log, detect_step, next_run
from lucidnews.web_api import build_context, resolve, resolve_write

ROOT = Path(__file__).resolve().parents[1]
SECRET = "AIzaSy-test-secret-value"


# Lock --------------------------------------------------------------------------------


def test_only_one_run_holds_the_lock(tmp_path) -> None:
    with run_lock(tmp_path, origin="terminal") as first:
        assert first is True
        holder = current_holder(tmp_path)
        assert holder["pid"] == os.getpid() and holder["origin"] == "terminal"
        with run_lock(tmp_path) as second:
            assert second is False
    assert current_holder(tmp_path) is None


def test_a_crashed_run_does_not_block_the_next_one(tmp_path) -> None:
    dead = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    (tmp_path / LOCK_NAME).write_text(json.dumps({"pid": int(dead.stdout), "origin": "web"}))

    assert current_holder(tmp_path) is None
    with run_lock(tmp_path) as acquired:
        assert acquired is True


def test_the_pipeline_refuses_to_start_while_another_run_holds_the_lock(tmp_path) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    with run_lock(tmp_path, origin="schedule"):
        result = subprocess.run(
            [sys.executable, "-m", "lucidnews.main", "--data-dir", str(tmp_path)],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
            env={**os.environ, "COLUMNS": "200"},
        )
    assert result.returncode == ALREADY_RUNNING
    assert "Another LucidNews run is in progress" in result.stderr + result.stdout


# Runs --------------------------------------------------------------------------------


def fake_pipeline(tmp_path: Path, *, code: int = 0, pause: float = 0.6, lock: bool = True) -> list[str]:
    """A stand-in for ``python -m lucidnews.main``: same banner and step lines, same lock."""
    script = f"""
import sys, time
from pathlib import Path
from lucidnews.run_lock import run_lock
print("  LucidNews", flush=True)
with run_lock(Path({str(tmp_path)!r})) if {lock} else open("/dev/null") as held:
    print("Fetching content since: 2026-10-10", flush=True)
    print("\\x1b[32mFetched 12 items from all sources\\x1b[0m", flush=True)
    print("key in a traceback: {SECRET}", flush=True)
    time.sleep({pause})
    if {code} == 1:
        print("Fatal error: boom", flush=True)
    else:
        print("Saved EN summary to: data/summaries/x.md", flush=True)
        print("LucidNews completed successfully!", flush=True)
sys.exit({code})
"""
    return [sys.executable, "-c", script]


def wait_until_finished(service: RunService, timeout: float = 20) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, body = service.current()
        if not body["running"]:
            return body
        time.sleep(0.1)
    raise AssertionError("the run did not finish")


def service(tmp_path: Path, command: list[str]) -> RunService:
    return RunService(tmp_path, project_root=ROOT, secret_values=lambda: [SECRET], command=command)


def test_a_run_is_started_followed_and_reported(tmp_path) -> None:
    runs = service(tmp_path, fake_pipeline(tmp_path))

    status, body = runs.start()
    assert status == 202 and body["running"] is True and body["origin"] == "web"
    assert runs.start()[0] == 409  # one at a time

    body = wait_until_finished(runs)
    assert body["exit_code"] == 0 and body["step"] == "done"
    assert "Fetched 12 items from all sources" in body["log"]
    assert "\x1b[" not in body["log"]  # no colour codes
    assert SECRET not in body["log"] and "•••" in body["log"]
    assert list((tmp_path / "runs").glob("web-*.log"))


def test_a_failed_run_is_reported_as_failed(tmp_path) -> None:
    runs = service(tmp_path, fake_pipeline(tmp_path, code=1, pause=0))
    runs.start()

    body = wait_until_finished(runs)
    assert body["exit_code"] == 1 and body["step"] == "analyze"
    assert "Fatal error: boom" in body["log"]


def test_a_run_from_the_terminal_or_the_schedule_blocks_the_button(tmp_path) -> None:
    runs = service(tmp_path, fake_pipeline(tmp_path))
    with run_lock(tmp_path, origin="schedule", log=str(tmp_path / "scheduled.log")):
        status, body = runs.start()
        assert status == 409
        assert body["running"] is True and body["origin"] == "schedule"
    assert not (tmp_path / "runs").exists()  # nothing was started


def test_losing_the_race_for_the_lock_is_reported(tmp_path) -> None:
    script = f"import sys; sys.exit({ALREADY_RUNNING})"
    runs = service(tmp_path, [sys.executable, "-c", script])
    runs.start()

    assert wait_until_finished(runs)["already_running"] is True


def test_steps_and_log_cleaning() -> None:
    assert detect_step("Fetching content since: 2026-10-10\nAnalyzed 3 items with AI") == "select"
    assert detect_step("nothing yet") is None
    assert detect_step("No new content found. Exiting.") == "done"
    traceback = 'Fetched 31 items from all sources\n│ 341 │ f"{icons} Analyzed {len(analyzed_items)} items with AI"'
    assert detect_step(traceback) == "analyze"  # quoted source code is not a step
    assert clean_log("\x1b[1mkey=abcdefgh\x1b[0m\r", ["abcdefgh", "abc"]) == "key=•••"


def test_the_default_command_is_the_terminal_command(tmp_path) -> None:
    runs = RunService(tmp_path, str(tmp_path / "config.json"))

    assert runs.pipeline_command() == [
        sys.executable, "-m", "lucidnews.main", "--data-dir", str(tmp_path.resolve()),
        "--config", str((tmp_path / "config.json").resolve()),
    ]


# Schedule ----------------------------------------------------------------------------


class FakeLaunchctl:
    def __init__(self, bootstrap_code: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.loaded = False
        self.bootstrap_code = bootstrap_code

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(args)
        code = 0
        if args[0] == "bootstrap":
            code = self.bootstrap_code
            self.loaded = code == 0
        elif args[0] == "bootout":
            code, self.loaded = (0 if self.loaded else 3), False
        elif args[0] == "print":
            code = 0 if self.loaded else 113
        return subprocess.CompletedProcess(args, code, "", "Bootstrap failed: 5: Input/output error" if code else "")


def schedule(tmp_path: Path, launchctl: FakeLaunchctl, platform: str = "darwin") -> ScheduleService:
    return ScheduleService(
        tmp_path / "data", project_root=ROOT, agents_dir=tmp_path / "LaunchAgents",
        label="com.lucidnews.test", launchctl=launchctl, platform=platform, python="/venv/bin/python",
    )


def test_a_daily_schedule_writes_and_loads_a_launchd_agent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", SECRET)
    launchctl = FakeLaunchctl()
    agent = schedule(tmp_path, launchctl)

    status, body = agent.update({"enabled": True, "hour": 7, "minute": 30, "weekdays": []})

    assert status == 200, body
    assert body["enabled"] and body["loaded"] and (body["hour"], body["minute"], body["weekdays"]) == (7, 30, [])
    plist = plistlib.loads(agent.plist_path.read_bytes())
    assert plist["ProgramArguments"] == ["/venv/bin/python", "-m", "lucidnews.main", "--data-dir", str((tmp_path / "data").resolve())]
    assert plist["WorkingDirectory"] == str(ROOT)
    assert plist["StartCalendarInterval"] == [{"Hour": 7, "Minute": 30}]
    assert plist["EnvironmentVariables"]["LUCIDNEWS_RUN_ORIGIN"] == "schedule"
    assert plist["StandardOutPath"].endswith("runs/scheduled.log")
    assert SECRET.encode() not in agent.plist_path.read_bytes()  # keys stay in .env
    assert [call[0] for call in launchctl.calls] == ["bootout", "bootstrap", "print"]
    if shutil.which("plutil"):
        assert subprocess.run(["plutil", "-lint", str(agent.plist_path)], capture_output=True).returncode == 0


def test_chosen_weekdays_become_one_interval_each(tmp_path) -> None:
    agent = schedule(tmp_path, FakeLaunchctl())

    status, body = agent.update({"enabled": True, "hour": 18, "minute": 0, "weekdays": [7, 1, 1]})

    assert status == 200 and body["weekdays"] == [1, 7]
    assert plistlib.loads(agent.plist_path.read_bytes())["StartCalendarInterval"] == [
        {"Hour": 18, "Minute": 0, "Weekday": 1}, {"Hour": 18, "Minute": 0, "Weekday": 7},
    ]


@pytest.mark.parametrize(
    "body, field",
    [
        ({"enabled": True, "hour": 24, "minute": 0}, "hour"),
        ({"enabled": True, "hour": 7, "minute": "00"}, "minute"),
        ({"enabled": True, "hour": 7, "minute": 0, "weekdays": [0]}, "weekdays"),
        ({"enabled": "yes"}, "enabled"),
    ],
)
def test_invalid_schedules_are_refused(tmp_path, body, field) -> None:
    agent = schedule(tmp_path, FakeLaunchctl())

    status, result = agent.update(body)

    assert status == 422 and field in result["fields"]
    assert not agent.plist_path.exists()


def test_a_schedule_launchd_refuses_is_not_left_behind(tmp_path) -> None:
    agent = schedule(tmp_path, FakeLaunchctl(bootstrap_code=5))

    status, body = agent.update({"enabled": True, "hour": 7, "minute": 0})

    assert status == 502 and body["detail"] == "Bootstrap failed: 5: Input/output error"
    assert not agent.plist_path.exists()


def test_turning_the_schedule_off_unloads_and_removes_the_agent(tmp_path) -> None:
    launchctl = FakeLaunchctl()
    agent = schedule(tmp_path, launchctl)
    agent.update({"enabled": True, "hour": 7, "minute": 0})

    status, body = agent.update({"enabled": False})

    assert status == 200 and body["enabled"] is False
    assert not agent.plist_path.exists() and launchctl.loaded is False


def test_scheduling_needs_macos(tmp_path) -> None:
    agent = schedule(tmp_path, FakeLaunchctl(), platform="linux")

    assert agent.get()[1] == {"supported": False, "enabled": False}
    assert agent.update({"enabled": True, "hour": 7, "minute": 0})[0] == 501


def test_next_run_follows_the_time_and_the_days() -> None:
    now = datetime(2026, 10, 7, 8, 0, tzinfo=timezone(timedelta(hours=2)))  # a Wednesday

    assert next_run(7, 0, [], now) == "2026-10-08T07:00+02:00"  # already past today
    assert next_run(9, 15, [], now) == "2026-10-07T09:15+02:00"
    assert next_run(7, 0, [1], now) == "2026-10-12T07:00+02:00"  # next Monday


# HTTP --------------------------------------------------------------------------------


def test_run_routes_are_local_and_list_every_run(tmp_path, monkeypatch) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    failed = archive.start_run(datetime.now(timezone.utc))
    archive.finish_run(failed, "failed", error="All 1 attempted sources failed")
    monkeypatch.chdir(ROOT)

    local = build_context(str(tmp_path), None, local_features=True)
    status, body = resolve(local, "/api/runs", {})
    assert status == 200 and body["runs"][0]["status"] == "failed"
    assert body["runs"][0]["error"] == "All 1 attempted sources failed"
    assert resolve(local, "/api/runs/current", {})[1]["running"] is False
    assert resolve_write(local, "DELETE", "/api/runs", {})[0] == 405

    remote = build_context(str(tmp_path), None)
    assert resolve(remote, "/api/runs", {})[0] == 403
    assert resolve_write(remote, "POST", "/api/runs", {})[0] == 403
    assert resolve(remote, "/api/schedule", {})[0] == 403
