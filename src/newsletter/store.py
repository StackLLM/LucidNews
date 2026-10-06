"""File-backed subscriber store (``data/subscribers.json``).

Format: ``{"version": 1, "subscribers": [Subscriber, ...]}``. The legacy format, a
plain list of email strings, is read transparently and rewritten in the new format
on the next save. The interface is small on purpose so a database-backed store
can replace it without touching delivery code.
"""

import json
import logging
from pathlib import Path
from typing import Iterable, List, Optional

from pydantic import ValidationError

from .._file_utils import _atomic_write_text
from .models import DigestPreferences, Subscriber

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1


class SubscriberStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> List[Subscriber]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.error("Ignoring unreadable subscriber file %s", self.path)
            return []

        entries = raw.get("subscribers", []) if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            return []
        subscribers: List[Subscriber] = []
        seen: set[str] = set()
        for entry in entries:
            try:
                subscriber = (
                    Subscriber(email=entry)
                    if isinstance(entry, str)
                    else Subscriber.model_validate(entry)
                )
            except ValidationError as exc:
                logger.warning("Skipping invalid subscriber entry %r: %s", entry, exc)
                continue
            key = subscriber.email.lower()
            if key not in seen:
                seen.add(key)
                subscribers.append(subscriber)
        return subscribers

    def save(self, subscribers: Iterable[Subscriber]) -> None:
        payload = {
            "version": FORMAT_VERSION,
            "subscribers": [s.model_dump(mode="json") for s in subscribers],
        }
        _atomic_write_text(self.path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def get(self, email: str) -> Optional[Subscriber]:
        key = email.strip().lower()
        return next((s for s in self.load() if s.email.lower() == key), None)

    def add(self, email: str, preferences: Optional[DigestPreferences] = None) -> Subscriber:
        """Create a subscriber, or update preferences of an existing one."""
        subscribers = self.load()
        key = email.strip().lower()
        for index, existing in enumerate(subscribers):
            if existing.email.lower() == key:
                if preferences is not None:
                    subscribers[index] = existing.model_copy(update={"preferences": preferences})
                    self.save(subscribers)
                return subscribers[index]
        subscriber = Subscriber(email=email, preferences=preferences or DigestPreferences())
        subscribers.append(subscriber)
        self.save(subscribers)
        return subscriber

    def remove(self, email: str) -> bool:
        """Delete a subscriber entirely (no data is kept after unsubscribing)."""
        subscribers = self.load()
        key = email.strip().lower()
        remaining = [s for s in subscribers if s.email.lower() != key]
        if len(remaining) == len(subscribers):
            return False
        self.save(remaining)
        return True
