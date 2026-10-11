"""Settings and API keys editable from the web app (local API routes only).

Configuration: ``config.json`` is edited **raw**. Only whitelisted fields change,
``${VARIABLE}`` placeholders elsewhere stay untouched, and a field holding a
placeholder cannot be edited (it is reported as locked). Every write is checked
by loading the result through ``Config``, saved atomically, and preceded by a
timestamped backup that can be restored. A version (hash of the file) makes a
write fail if the file changed since it was read.

API keys: written to the project's ``.env`` file (ignored by Git, mode 600), the
file ``lucidnews`` loads at start. Only variable names the configuration refers
to are accepted. A value is never returned, logged or echoed in an error: the
API only says whether a key is set, and where.
"""

import copy
import hashlib
import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from dotenv import dotenv_values
from pydantic import ValidationError

from .i18n import LANGUAGES
from .models import AI_PROVIDER_DEFAULTS, AIProvider, Config
from .processing import ProfileRegistry
from .reliability import ReliabilityLabel
from .storage.manager import _ENV_VAR_PATTERN, _expand_env_vars

PROJECT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
# Same prefixes as ai.client: a value starting with one is a key, not a variable name.
KEY_PREFIXES = ("sk-", "sk_", "AIza", "xai-", "gsk_", "hf_")
BACKUP_NAME = re.compile(r"^config-\d{8}T\d{6}(?:\d{6})?Z\.json$")
MAX_BACKUPS = 10
MAX_SECRET_LENGTH = 4096

Response = Tuple[int, Dict[str, Any]]

# Editable fields: public path -> path in config.json. Profiles are handled apart.
FIELDS: Dict[str, Tuple[str, ...]] = {
    "ai.provider": ("ai", "provider"),
    "ai.model": ("ai", "model"),
    "ai.api_key_env": ("ai", "api_key_env"),
    "ai.languages": ("ai", "languages"),
    "ai.max_requests_per_minute": ("ai", "max_requests_per_minute"),
    "ai.max_tokens_per_run": ("ai", "max_tokens_per_run"),
    "collection.time_window_hours": ("collection", "time_window_hours"),
    "digest.max_items": ("digest", "max_items"),
    "digest.unanalyzed_max_items": ("digest", "unanalyzed_max_items"),
    "digest.source_quality_days": ("digest", "source_quality_days"),
    "digest.watched_categories": ("digest", "watched_categories"),
    "digest.only_watched_categories": ("digest", "only_watched_categories"),
    "digest.coverage_min_sources": ("digest", "coverage_min_sources"),
    "digest.coverage_min_items": ("digest", "coverage_min_items"),
    "reliability.exclude_labels": ("reliability", "exclude_labels"),
    "reliability.corroboration_lookback_hours": ("reliability", "corroboration_lookback_hours"),
    "reliability.corroboration_max_references": ("reliability", "corroboration_max_references"),
    "archive.reuse_analysis": ("archive", "reuse_analysis"),
    "archive.reuse_enrichment": ("archive", "reuse_enrichment"),
}
PROFILE_FIELDS = ("threshold", "topic_dedup")


def _get(data: Dict[str, Any], path: Tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def _set(data: Dict[str, Any], path: Tuple[str, ...], value: Any) -> None:
    for key in path[:-1]:
        data = data.setdefault(key, {})
    data[path[-1]] = value


def _model_value(config: Config, path: Tuple[str, ...]) -> Any:
    value: Any = config
    for key in path:
        value = getattr(value, key)
    if isinstance(value, list):
        return [entry.value if hasattr(entry, "value") else entry for entry in value]
    return value.value if hasattr(value, "value") else value


def _has_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_ENV_VAR_PATTERN.search(value))
    if isinstance(value, list):
        return any(_has_placeholder(entry) for entry in value)
    return False


def _field_errors(exc: ValidationError) -> Dict[str, str]:
    """Map pydantic locations back to public field paths (messages never echo inputs)."""
    reverse = {path: name for name, path in FIELDS.items()}
    fields: Dict[str, str] = {}
    for error in exc.errors(include_url=False, include_input=False):
        loc = tuple(str(part) for part in error["loc"])
        name = None
        for length in range(len(loc), 0, -1):
            if loc[:length] in reverse:
                name = reverse[loc[:length]]
                break
        if name is None and loc[:2] == ("processing", "profile_settings") and len(loc) >= 4:
            name = f"profiles.{loc[2]}.{loc[3]}"
        fields.setdefault(name or ".".join(loc), error["msg"].removeprefix("Value error, "))
    return fields


def _atomic_write(path: Path, text: str, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


@dataclass
class SettingsService:
    config_path: Path
    backup_dir: Path
    profiles: ProfileRegistry
    env_path: Path = PROJECT_ENV_FILE
    # Called after a successful write so the API serves the new configuration.
    on_change: Optional[Callable[[], None]] = None

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    # Configuration ----------------------------------------------------------------

    def _read_raw(self) -> Tuple[Dict[str, Any], str]:
        text = self.config_path.read_text(encoding="utf-8")
        return json.loads(text), hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _validate(self, raw: Dict[str, Any]) -> Config:
        config = Config.model_validate(_expand_env_vars(copy.deepcopy(raw)))
        for profile_id in config.processing.profile_settings:
            if profile_id not in self.profiles.ids:
                raise ValueError(f"unknown profile: {profile_id}")
        return config

    def get(self) -> Response:
        raw, version = self._read_raw()
        config = self._validate(raw)
        values: Dict[str, Any] = {}
        for name, path in FIELDS.items():
            section, key = name.split(".")
            values.setdefault(section, {})[key] = _model_value(config, path)
        values["profiles"] = {
            profile.id: {
                "threshold": (config.processing.profile_settings.get(profile.id).threshold
                              if profile.id in config.processing.profile_settings else None),
                "topic_dedup": (config.processing.profile_settings.get(profile.id).topic_dedup
                                if profile.id in config.processing.profile_settings else True),
            }
            for profile in self.profiles.profiles
        }
        locked = [name for name, path in FIELDS.items() if _has_placeholder(_get(raw, path))]
        return HTTPStatus.OK, {
            "version": version,
            "values": values,
            "locked": locked,
            "options": {
                "providers": [
                    {
                        "id": provider.value,
                        "model": AI_PROVIDER_DEFAULTS.get(provider, {}).get("model", ""),
                        "api_key_env": AI_PROVIDER_DEFAULTS.get(provider, {}).get("api_key_env", ""),
                    }
                    for provider in AIProvider
                ],
                "languages": [
                    {"code": language.code, "name": language.native_name} for language in LANGUAGES.values()
                ],
                "labels": [label.value for label in ReliabilityLabel],
                "profiles": [
                    {"id": profile.id, "names": self.profiles.names.get(profile.id, {})}
                    for profile in self.profiles.profiles
                ],
            },
        }

    def update(self, body: Dict[str, Any]) -> Response:
        values = body.get("values")
        if not isinstance(values, dict):
            return HTTPStatus.BAD_REQUEST, {"error": "expected {version, values}"}
        with self._lock:
            raw, version = self._read_raw()
            if body.get("version") != version:
                return HTTPStatus.CONFLICT, {"error": "the configuration changed since it was read"}
            updated = copy.deepcopy(raw)
            current = self._validate(raw)
            changed: List[Tuple[str, ...]] = []
            fields: Dict[str, str] = {}
            for section, entries in values.items():
                if not isinstance(entries, dict):
                    return HTTPStatus.BAD_REQUEST, {"error": f"{section}: expected an object"}
                for key, value in entries.items():
                    if section == "profiles":
                        if key not in self.profiles.ids or not isinstance(value, dict):
                            fields[f"profiles.{key}"] = "unknown profile"
                            continue
                        for profile_field, profile_value in value.items():
                            if profile_field not in PROFILE_FIELDS:
                                fields[f"profiles.{key}.{profile_field}"] = "not editable"
                                continue
                            existing = current.processing.profile_settings.get(key)
                            effective = getattr(existing, profile_field) if existing else (
                                None if profile_field == "threshold" else True
                            )
                            if profile_value == effective:
                                continue  # unchanged: keep the file as it is
                            path = ("processing", "profile_settings", key, profile_field)
                            _set(updated, path, profile_value)
                            changed.append(path)
                        continue
                    name = f"{section}.{key}"
                    path = FIELDS.get(name)
                    if path is None:
                        fields[name] = "not editable"
                        continue
                    if value == _model_value(current, path):
                        continue  # unchanged: defaults stay implicit, the file stays as it is
                    if _has_placeholder(_get(raw, path)):
                        fields[name] = "set through an environment variable in config.json"
                        continue
                    if name == "ai.api_key_env" and not (
                        isinstance(value, str) and ENV_NAME.match(value) and not value.startswith(KEY_PREFIXES)
                    ):
                        # Also stops an API key pasted into the variable-name field.
                        fields[name] = "must be an environment variable name, not a key"
                        continue
                    _set(updated, path, value)
                    changed.append(path)
            if fields:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid settings", "fields": fields}
            if not changed:
                return self.get()
            try:
                config = self._validate(updated)
            except ValidationError as exc:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid settings", "fields": _field_errors(exc)}
            except ValueError as exc:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid settings", "fields": {"profiles": str(exc)}}
            # Store normalized values ("5" -> 5, enums as strings).
            for path in changed:
                if path[0] == "processing":
                    settings = config.processing.profile_settings[path[2]]
                    _set(updated, path, getattr(settings, path[3]))
                else:
                    _set(updated, path, _model_value(config, path))
            self._write_config(updated)
        if self.on_change:
            self.on_change()
        return self.get()

    def snapshot(self) -> Tuple[Dict[str, Any], str, Config]:
        """Raw file, its version and the validated configuration (for other editors)."""
        raw, version = self._read_raw()
        return raw, version, self._validate(raw)

    def edit_raw(
        self,
        version: Any,
        mutate: Callable[[Dict[str, Any]], Optional[Response]],
        on_invalid: Callable[[ValidationError], Response],
    ) -> Optional[Response]:
        """Apply ``mutate`` to a copy of the raw file and write it like ``update`` does.

        Returns None once written, or the refusal: 409 on a stale version, the
        response ``mutate`` returned, or ``on_invalid`` when ``Config`` rejects it.
        """
        with self._lock:
            raw, current = self._read_raw()
            if version != current:
                return HTTPStatus.CONFLICT, {"error": "the configuration changed since it was read"}
            updated = copy.deepcopy(raw)
            refusal = mutate(updated)
            if refusal is not None:
                return refusal
            if updated == raw:
                return None
            try:
                self._validate(updated)
            except ValidationError as exc:
                return on_invalid(exc)
            except ValueError as exc:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
            self._write_config(updated)
        if self.on_change:
            self.on_change()
        return None

    def _write_config(self, data: Dict[str, Any]) -> None:
        self._backup()
        _atomic_write(self.config_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def _backup(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.backup_dir / f"config-{stamp}.json"
        target.write_text(self.config_path.read_text(encoding="utf-8"), encoding="utf-8")
        for old in self._backup_files()[MAX_BACKUPS:]:
            old.unlink()

    def _backup_files(self) -> List[Path]:
        if not self.backup_dir.exists():
            return []
        return sorted(
            (path for path in self.backup_dir.iterdir() if BACKUP_NAME.match(path.name)),
            key=lambda path: path.name,
            reverse=True,
        )

    def backups(self) -> Response:
        return HTTPStatus.OK, {
            "backups": [
                {"name": path.name, "saved_at": _backup_time(path.name)} for path in self._backup_files()
            ]
        }

    def restore(self, body: Dict[str, Any]) -> Response:
        name = body.get("name")
        if not isinstance(name, str) or not BACKUP_NAME.match(name):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid backup name"}
        path = self.backup_dir / name
        if not path.is_file():
            return HTTPStatus.NOT_FOUND, {"error": "backup not found"}
        with self._lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._validate(data)
            except (ValueError, ValidationError):
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "this backup is not a valid configuration"}
            self._write_config(data)
        if self.on_change:
            self.on_change()
        return self.get()

    # API keys ---------------------------------------------------------------------

    def _declared_secrets(self) -> Dict[str, List[str]]:
        """Environment variables the configuration refers to, with what uses them."""
        raw, _ = self._read_raw()
        config = self._validate(raw)
        declared: Dict[str, List[str]] = {}

        def add(name: Optional[str], used_by: str) -> None:
            if name and ENV_NAME.match(name):
                declared.setdefault(name, [])
                if used_by not in declared[name]:
                    declared[name].append(used_by)

        ai = config.ai
        if ai.provider is not AIProvider.OLLAMA:
            add(ai.api_key_env, f"ai:{ai.provider.value}")
        add(ai.azure_endpoint_env, "ai:azure")
        for name in (ai.provider_chain or "").split(","):
            try:
                provider = AIProvider(name.strip())
            except ValueError:
                continue
            add(AI_PROVIDER_DEFAULTS.get(provider, {}).get("api_key_env"), f"ai:{provider.value}")
        if config.email is not None:
            add(config.email.password_env, "email")
            add(config.email.signing_key_env, "newsletter-links")
            if config.email.provider == "resend":
                add(config.email.resend_api_key_env, "email:resend")
        if config.webhook is not None:
            add(config.webhook.url_env, "webhook")
        if config.sources.twitter is not None:
            add(config.sources.twitter.apify_token_env, "twitter")
        for match in _ENV_VAR_PATTERN.finditer(json.dumps(raw)):
            add(match.group(1), "config")
        return declared

    def secret_values(self) -> List[str]:
        """Current values of the secrets the configuration uses (to hide them from logs)."""
        try:
            names = self._declared_secrets()
        except (OSError, ValueError, ValidationError):
            names = {}
        in_file = self._env_file_values()
        values = {os.environ.get(name) or "" for name in names} | {in_file.get(name) or "" for name in names}
        return sorted((value for value in values if value), key=len, reverse=True)

    def _env_file_values(self) -> Dict[str, Optional[str]]:
        return dict(dotenv_values(self.env_path)) if self.env_path.exists() else {}

    def secrets(self) -> Response:
        in_file = self._env_file_values()
        return HTTPStatus.OK, {
            "env_file": ".env",
            "secrets": [
                {
                    "name": name,
                    "used_by": used_by,
                    "in_file": bool(in_file.get(name)),
                    # Set in the shell that started the API: it wins over .env.
                    "in_environment": bool(os.environ.get(name)),
                }
                for name, used_by in sorted(self._declared_secrets().items())
            ],
        }

    def set_secret(self, name: str, body: Dict[str, Any]) -> Response:
        if name not in self._declared_secrets():
            return HTTPStatus.NOT_FOUND, {"error": "unknown variable: the configuration does not use it"}
        value = body.get("value")
        if not isinstance(value, str):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid value", "fields": {"value": "required"}}
        value = value.strip()
        if not value or len(value) > MAX_SECRET_LENGTH or any(ord(char) < 32 or ord(char) == 127 for char in value):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {
                "error": "invalid value",
                "fields": {"value": f"1 to {MAX_SECRET_LENGTH} printable characters, on one line"},
            }
        with self._lock:
            self._write_env(name, value)
        return HTTPStatus.OK, {"name": name, "in_file": True}

    def delete_secret(self, name: str) -> Response:
        if not ENV_NAME.match(name):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid variable name"}
        with self._lock:
            removed = self._write_env(name, None)
        if not removed:
            return HTTPStatus.NOT_FOUND, {"error": "not set in .env"}
        return HTTPStatus.OK, {"name": name, "in_file": False}

    def _write_env(self, name: str, value: Optional[str]) -> bool:
        """Set (or remove, with ``None``) one variable in .env; keeps other lines as they are."""
        lines = self.env_path.read_text(encoding="utf-8").splitlines() if self.env_path.exists() else []
        pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=")
        kept = [line for line in lines if not pattern.match(line)]
        found = len(kept) != len(lines)
        if value is not None:
            kept.append(f"{name}={_quote_env(value)}")
        elif not found:
            return False
        _atomic_write(self.env_path, "\n".join(kept) + "\n", mode=0o600)
        return True


def _backup_time(name: str) -> str:
    stamp = name.removeprefix("config-").removesuffix(".json")
    fmt = "%Y%m%dT%H%M%S%fZ" if len(stamp) > 16 else "%Y%m%dT%H%M%SZ"
    return datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def _quote_env(value: str) -> str:
    """Quote a value so python-dotenv reads it back unchanged."""
    if "'" not in value:
        return f"'{value}'"  # single quotes: taken literally
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
