"""Read-only HTTP API over the run archive (``lucidnews-api``), used by the web frontend.

Endpoints (JSON, GET only):

- ``/api/editions``: recent runs that published a digest.
- ``/api/editions/latest?lang=fr``: the latest edition in one language.
- ``/api/editions/<run_id>?lang=fr``: one edition.
- ``/api/items/<item_id>?lang=fr``: one item with its reliability details and editions.
- ``/api/sources?days=14``: source health (configured sources) and per-run volumes.

Subscriber preferences (local only, see ``subscribers_api``):

- ``GET /api/preferences/options``, ``GET /api/subscribers``
- ``POST /api/subscribers``, ``PUT /api/subscribers/<id>``, ``DELETE /api/subscribers/<id>``

The server binds to localhost by default and never writes to the archive. The
subscriber routes exist only on a loopback bind, accept only localhost Host headers
(DNS rebinding) and, for writes, a JSON body from a localhost Origin (cross-site
requests).
"""

import argparse
import ipaddress
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlsplit

from ._cli import add_data_dir_arguments
from .archive import ItemArchive, RunRecord
from .i18n import DEFAULT_LANGUAGE, is_supported
from .models import ContentItem
from .processing import ProfileRegistry
from .source_health import assess_health, configured_source_keys, health_to_dict
from .storage.manager import StorageManager
from .subscribers_api import SubscriberService
from .taxonomy import importance_from_score

RUN_ID = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
ITEM_ID = re.compile(r"^[^\x00-\x1f\x7f]{1,300}$")
SUBSCRIBER_ID = re.compile(r"^[0-9a-f]{16}$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MAX_BODY_BYTES = 64 * 1024
LOCAL_ONLY = {"error": "subscriber management is only available when the API is bound to localhost"}


@dataclass
class ApiContext:
    archive: ItemArchive
    profile_names: Dict[str, Dict[str, str]] = field(default_factory=dict)
    profile_order: List[str] = field(default_factory=list)
    default_language: str = DEFAULT_LANGUAGE
    # source key -> type, for the sources still in the config (empty = show all)
    configured_sources: Dict[str, str] = field(default_factory=dict)
    # None when the API is not bound to loopback: subscriber routes are then refused.
    subscribers: Optional[SubscriberService] = None


def _profile_id(item: ContentItem) -> str:
    if item.processing:
        return item.processing.classification.profile
    return item.profile if isinstance(item.profile, str) else "unclassified"


def _profile_name(ctx: ApiContext, profile_id: str, language: str) -> str:
    names = ctx.profile_names.get(profile_id, {})
    return names.get(language, names.get("default", profile_id.replace("-", " ").title()))


def item_payload(item: ContentItem, language: str) -> Dict[str, Any]:
    processing = item.processing
    analysis = processing.analysis if processing else None
    artifact = processing.artifacts.get(language) if processing else None
    reliability = processing.reliability if processing else None

    primary = next((block for block in artifact.blocks if block.primary), None) if artifact else None
    score = analysis.score if analysis else None
    importance = importance_from_score(score)
    return {
        "id": item.id,
        "title": artifact.title if artifact else item.title,
        "url": str(item.url),
        "score": score,
        "importance": importance.value if importance else None,
        "categories": list(analysis.categories) if analysis else [],
        "tags": list(analysis.tags) if analysis else [],
        "summary": primary.content if primary else (analysis.summary if analysis else ""),
        "sections": [
            {"id": block.id, "title": block.title, "content": block.content}
            for block in (artifact.blocks if artifact else [])
            if not block.primary
        ],
        "reliability": reliability.model_dump(mode="json") if reliability else None,
        "source_type": item.source_type.value,
        "author": item.author,
        "published_at": item.published_at.isoformat(),
        "discussion_url": item.metadata.get("discussion_url"),
        "translated": artifact is not None,
    }


def item_detail_payload(ctx: "ApiContext", item: ContentItem, language: str) -> Dict[str, Any]:
    processing = item.processing
    analysis = processing.analysis if processing else None
    claim = analysis.claim if analysis else None
    return {
        **item_payload(item, language),
        "language": language,
        "available_languages": sorted(processing.artifacts) if processing else [],
        "profile": _profile_id(item),
        "profile_name": _profile_name(ctx, _profile_id(item), language),
        # The claim evidence comes from the AI analysis, which is written in English.
        "claim": {"status": claim.status.value, "evidence": claim.evidence} if claim else None,
        "editions": [run_payload(run) for run in ctx.archive.runs_selecting(item.id)],
    }


def run_payload(run: RunRecord) -> Dict[str, Any]:
    return {
        "id": run.id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "fetched_count": run.fetched_count,
        "selected_count": run.selected_count,
    }


def list_editions(ctx: ApiContext, limit: int = 30) -> Dict[str, Any]:
    runs = [
        run
        for run in ctx.archive.list_runs(limit=limit * 3)
        if run.status == "success" and run.selected_count > 0
    ]
    return {"editions": [run_payload(run) for run in runs[:limit]]}


def edition_payload(ctx: ApiContext, run: RunRecord, language: str) -> Dict[str, Any]:
    items = list(ctx.archive.get_items(ctx.archive.run_item_ids(run.id, selected_only=True)).values())
    items.sort(
        key=lambda item: (
            -(item.processing.analysis.score or 0)
            if item.processing and item.processing.analysis
            else 0,
            -item.published_at.timestamp(),
        )
    )

    groups: Dict[str, List[ContentItem]] = {}
    for item in items:
        groups.setdefault(_profile_id(item), []).append(item)
    order = {profile_id: index for index, profile_id in enumerate(ctx.profile_order)}
    ordered = sorted(groups.items(), key=lambda group: order.get(group[0], len(order)))

    languages = sorted(
        {lang for item in items if item.processing for lang in item.processing.artifacts}
    )
    return {
        **run_payload(run),
        "language": language,
        "available_languages": languages,
        "sections": [
            {
                "profile": profile_id,
                "name": _profile_name(ctx, profile_id, language),
                "items": [item_payload(item, language) for item in group_items],
            }
            for profile_id, group_items in ordered
        ],
    }


MAX_HEALTH_DAYS = 90


def source_health_payload(ctx: ApiContext, days: int) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    report = assess_health(ctx.archive.source_run_rows(since))
    seen = {health.source_key for health in report}
    if ctx.configured_sources:
        report = [health for health in report if health.source_key in ctx.configured_sources]
    runs = [
        run
        for run in ctx.archive.list_runs(limit=500)
        if run.status != "running" and run.started_at >= since.isoformat()
    ]
    return {
        "days": days,
        "sources": [health_to_dict(health) for health in report],
        "configured_without_history": sorted(set(ctx.configured_sources) - seen),
        "runs": [run_payload(run) for run in reversed(runs)],  # oldest first
    }


def resolve(ctx: ApiContext, path: str, query: Dict[str, List[str]]) -> tuple[int, Dict[str, Any]]:
    """Route a GET request to a JSON payload: (status, body)."""
    language = (query.get("lang") or [ctx.default_language])[0].lower()
    if not is_supported(language):
        return HTTPStatus.BAD_REQUEST, {"error": f"unsupported language: {language}"}

    path = path.rstrip("/")
    if path == "/api/health":
        return HTTPStatus.OK, {"status": "ok"}
    if path == "/api/editions":
        return HTTPStatus.OK, list_editions(ctx)
    if path == "/api/sources":
        try:
            days = int((query.get("days") or ["14"])[0])
        except ValueError:
            return HTTPStatus.BAD_REQUEST, {"error": "days must be an integer"}
        if not 1 <= days <= MAX_HEALTH_DAYS:
            return HTTPStatus.BAD_REQUEST, {"error": f"days must be between 1 and {MAX_HEALTH_DAYS}"}
        return HTTPStatus.OK, source_health_payload(ctx, days)
    if path == "/api/preferences/options":
        if ctx.subscribers is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        return HTTPStatus.OK, ctx.subscribers.options()
    if path == "/api/subscribers":
        if ctx.subscribers is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        return ctx.subscribers.list()
    if path.startswith("/api/items/"):
        item_id = unquote(path.removeprefix("/api/items/"))
        if not ITEM_ID.match(item_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid item id"}
        item = ctx.archive.get_item(item_id)
        if item is None or not item.processing or not item.processing.analysis:
            return HTTPStatus.NOT_FOUND, {"error": "item not found"}
        return HTTPStatus.OK, item_detail_payload(ctx, item, language)
    if path.startswith("/api/editions/"):
        key = path.removeprefix("/api/editions/")
        if key == "latest":
            run = ctx.archive.latest_published_run()
        elif RUN_ID.match(key):
            run = ctx.archive.get_run(key)
        else:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid edition id"}
        if run is None:
            return HTTPStatus.NOT_FOUND, {"error": "edition not found"}
        return HTTPStatus.OK, edition_payload(ctx, run, language)
    return HTTPStatus.NOT_FOUND, {"error": "not found"}


def resolve_write(ctx: ApiContext, method: str, path: str, body: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
    """Route a POST/PUT/DELETE request (subscriber preferences only)."""
    if ctx.subscribers is None:
        return HTTPStatus.FORBIDDEN, LOCAL_ONLY
    path = path.rstrip("/")
    if path == "/api/subscribers" and method == "POST":
        return ctx.subscribers.create(body)
    if path.startswith("/api/subscribers/"):
        sub_id = path.removeprefix("/api/subscribers/")
        if not SUBSCRIBER_ID.match(sub_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid subscriber id"}
        if method == "PUT":
            return ctx.subscribers.update(sub_id, body)
        if method == "DELETE":
            return ctx.subscribers.delete(sub_id)
    return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}


def _hostname(value: str) -> str:
    """Host part of a Host header or Origin: ``[::1]:8765`` -> ``::1``."""
    value = value.strip().lower()
    if "//" in value:
        value = urlsplit(value).netloc
    if value.startswith("["):
        return value[1 : value.find("]")] if "]" in value else value
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def is_local_request(host: Optional[str], origin: Optional[str]) -> bool:
    """Same-machine request: localhost Host (no DNS rebinding) and, if sent, localhost Origin."""
    if not host or _hostname(host) not in LOCAL_HOSTS:
        return False
    return origin is None or _hostname(origin) in LOCAL_HOSTS


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def make_handler(ctx: ApiContext) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "LucidNewsAPI/1.0"

        def _send(self, status: int, body: Dict[str, Any]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _guarded(self, handler) -> None:
            try:
                status, body = handler()
            except Exception as exc:  # never leak a traceback to the client
                self.log_error("request failed: %r", exc)
                status, body = HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal error"}
            self._send(status, body)

        def do_GET(self) -> None:  # noqa: N802 (stdlib name)
            parts = urlsplit(self.path)
            if parts.path.startswith(("/api/subscribers", "/api/preferences")) and not is_local_request(
                self.headers.get("Host"), self.headers.get("Origin")
            ):
                self._send(HTTPStatus.FORBIDDEN, {"error": "local requests only"})
                return
            self._guarded(lambda: resolve(ctx, parts.path, parse_qs(parts.query)))

        def _write(self, method: str) -> None:
            if not is_local_request(self.headers.get("Host"), self.headers.get("Origin")):
                self._send(HTTPStatus.FORBIDDEN, {"error": "local requests only"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
                return
            body: Any = {}
            if length:
                # JSON only: a cross-site form post cannot send it without a CORS preflight.
                if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                    self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "expected application/json"})
                    return
                try:
                    body = json.loads(self.rfile.read(length))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                    return
            if not isinstance(body, dict):
                self._send(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON object"})
                return
            self._guarded(lambda: resolve_write(ctx, method, urlsplit(self.path).path, body))

        def do_POST(self) -> None:  # noqa: N802
            self._write("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._write("PUT")

        def do_DELETE(self) -> None:  # noqa: N802
            self._write("DELETE")

    return Handler


def build_context(data_dir: str, config_path: Optional[str], *, manage_subscribers: bool = False) -> ApiContext:
    storage = StorageManager(data_dir=data_dir, config_path=config_path)
    config = storage.load_config()
    archive_path = Path(config.archive.path)
    if not archive_path.is_absolute():
        archive_path = Path(data_dir) / archive_path
    if not archive_path.exists():
        raise FileNotFoundError(f"No archive at {archive_path}. Run `uv run lucidnews` first.")
    profiles = ProfileRegistry.load(
        Path(config.processing.profiles_dir), config.processing.default_profile
    )
    return ApiContext(
        archive=ItemArchive(archive_path),
        profile_names=profiles.names,
        profile_order=list(config.digest.profile_order),
        default_language=(config.ai.languages or [DEFAULT_LANGUAGE])[0],
        configured_sources=configured_source_keys(config),
        subscribers=(
            SubscriberService(storage.subscribers, config.ai.languages, configured_source_keys(config))
            if manage_subscribers
            else None
        ),
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LucidNews web API (archive read-only, local preferences)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    add_data_dir_arguments(parser)
    args = parser.parse_args(argv)

    try:
        # Subscriber data is personal: only served on a loopback bind.
        ctx = build_context(args.data_dir, args.config, manage_subscribers=is_loopback(args.host))
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    server = ThreadingHTTPServer((args.host, args.port), make_handler(ctx))
    print(f"LucidNews API on http://{args.host}:{args.port}/api/editions/latest", file=sys.stderr)
    if ctx.subscribers is None:
        print("Subscriber preferences disabled (not bound to localhost).", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
