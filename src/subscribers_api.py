"""Subscriber preferences for the web app: the write routes of ``lucidnews-api``.

Local-only by design (no accounts yet): the API serves them only when bound to a
loopback address, and every write must come from a same-machine origin (see
``web_api.write_allowed``). Subscribers are addressed by an opaque id derived from
the e-mail, so addresses never appear in URLs or browser history.
"""

import hashlib
import threading
from http import HTTPStatus
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import ValidationError

from .i18n import LANGUAGES
from .newsletter.models import DetailLevel, DigestPreferences, Frequency, Subscriber
from .newsletter.plans import PLAN_LIMITS
from .newsletter.store import SubscriberStore
from .taxonomy import IMPORTANCE_ORDER, Category

Response = tuple[int, Dict[str, Any]]


def subscriber_id(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]


def subscriber_payload(subscriber: Subscriber) -> Dict[str, Any]:
    return {
        "id": subscriber_id(subscriber.email),
        "email": subscriber.email,
        "plan": subscriber.plan.value,
        "preferences": subscriber.preferences.model_dump(mode="json"),
        "created_at": subscriber.created_at.isoformat(),
    }


def source_options(configured_sources: Mapping[str, str]) -> List[Dict[str, str]]:
    """Values accepted by ``DigestPreferences.sources``: source types, then named sub-sources.

    GitHub user feeds are left out: their items carry the event's repository, not the
    user, so a filter on the user name would never match.
    """
    options: List[Dict[str, str]] = []
    types = sorted(set(configured_sources.values()))
    options.extend({"value": source_type, "type": source_type, "kind": "type"} for source_type in types)
    named: List[Dict[str, str]] = []
    for key, source_type in configured_sources.items():
        prefix = f"{source_type}/"
        if not key.startswith(prefix):
            continue
        name = key.removeprefix(prefix)
        if source_type == "github" and name.startswith("@"):
            continue
        name = name.removeprefix("r/").removeprefix("@")
        named.append({"value": name, "type": source_type, "kind": "source"})
    options.extend(sorted(named, key=lambda option: (option["type"], option["value"].lower())))
    return options


def _validation_errors(exc: ValidationError) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for error in exc.errors():
        key = ".".join(str(part) for part in error["loc"]) or "body"
        fields.setdefault(key, error["msg"].removeprefix("Value error, "))
    return fields


class SubscriberService:
    def __init__(
        self,
        store: SubscriberStore,
        languages: Sequence[str],
        configured_sources: Mapping[str, str],
        weekly_day: int = 0,
    ):
        self.store = store
        self.weekly_day = weekly_day
        self.languages = [code for code in languages if code in LANGUAGES] or ["en"]
        self.configured_sources = dict(configured_sources)
        self._lock = threading.Lock()  # one writer at a time on the JSON file

    def options(self) -> Dict[str, Any]:
        return {
            "languages": [
                {"code": code, "name": LANGUAGES[code].native_name} for code in self.languages
            ],
            "categories": [category.value for category in Category],
            "frequencies": [frequency.value for frequency in Frequency],
            "detail_levels": [level.value for level in DetailLevel],
            "weekly_day": self.weekly_day,
            "importance_levels": [level.value for level in IMPORTANCE_ORDER],
            "sources": source_options(self.configured_sources),
            # Both plans are unlimited until the product is validated: shown, never billed.
            "plans": [
                {
                    "id": plan.value,
                    "max_categories": limits.max_categories,
                    "max_sources": limits.max_sources,
                    "max_items": limits.max_items,
                }
                for plan, limits in PLAN_LIMITS.items()
            ],
        }

    def _language_error(self, preferences: DigestPreferences) -> Optional[Response]:
        if preferences.language in self.languages:
            return None
        return HTTPStatus.UNPROCESSABLE_ENTITY, {
            "error": "invalid preferences",
            "fields": {"language": f"not produced by this instance (available: {', '.join(self.languages)})"},
        }

    def list(self) -> Response:
        subscribers = sorted(self.store.load(), key=lambda s: s.created_at)
        return HTTPStatus.OK, {"subscribers": [subscriber_payload(s) for s in subscribers]}

    def get(self, sub_id: str) -> Optional[Subscriber]:
        subscribers = self.store.load()
        index = self._find(subscribers, sub_id)
        return subscribers[index] if index is not None else None

    def _find(self, subscribers: List[Subscriber], sub_id: str) -> Optional[int]:
        return next((i for i, s in enumerate(subscribers) if subscriber_id(s.email) == sub_id), None)

    def create(self, body: Mapping[str, Any]) -> Response:
        try:
            preferences = DigestPreferences.model_validate(
                body.get("preferences") or {"language": self.languages[0]}
            )
            subscriber = Subscriber(email=str(body.get("email", "")), preferences=preferences)
        except ValidationError as exc:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid subscriber", "fields": _validation_errors(exc)}
        if error := self._language_error(preferences):
            return error
        with self._lock:
            subscribers = self.store.load()
            if self._find(subscribers, subscriber_id(subscriber.email)) is not None:
                return HTTPStatus.CONFLICT, {"error": "subscriber already exists", "fields": {"email": "already subscribed"}}
            subscribers.append(subscriber)
            self.store.save(subscribers)
        return HTTPStatus.CREATED, subscriber_payload(subscriber)

    def update(self, sub_id: str, body: Mapping[str, Any]) -> Response:
        try:
            preferences = DigestPreferences.model_validate(body.get("preferences"))
        except ValidationError as exc:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid preferences", "fields": _validation_errors(exc)}
        if error := self._language_error(preferences):
            return error
        with self._lock:
            subscribers = self.store.load()
            index = self._find(subscribers, sub_id)
            if index is None:
                return HTTPStatus.NOT_FOUND, {"error": "subscriber not found"}
            # The plan is display-only: no billing, so the web app cannot change it.
            subscribers[index] = subscribers[index].model_copy(update={"preferences": preferences})
            self.store.save(subscribers)
        return HTTPStatus.OK, subscriber_payload(subscribers[index])

    def delete(self, sub_id: str) -> Response:
        with self._lock:
            subscribers = self.store.load()
            index = self._find(subscribers, sub_id)
            if index is None:
                return HTTPStatus.NOT_FOUND, {"error": "subscriber not found"}
            # Unsubscribing removes everything; nothing is kept.
            del subscribers[index]
            self.store.save(subscribers)
        return HTTPStatus.OK, {"deleted": sub_id}

