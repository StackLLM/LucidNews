"""Annotation file (``<data_dir>/eval/annotations.json``), versioned with the project."""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, Optional

from pydantic import ValidationError

from .._file_utils import _atomic_write_text
from .models import Annotation

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1


class AnnotationStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def load(self) -> Dict[str, Annotation]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.error("Ignoring unreadable annotation file %s", self.path)
            return {}
        annotations: Dict[str, Annotation] = {}
        for entry in raw.get("annotations", []) if isinstance(raw, dict) else []:
            try:
                annotation = Annotation.model_validate(entry)
            except ValidationError as exc:
                logger.warning("Skipping invalid annotation %r: %s", entry, exc)
                continue
            annotations[annotation.item_id] = annotation
        return annotations

    def _save(self, annotations: Dict[str, Annotation]) -> None:
        payload = {
            "version": FORMAT_VERSION,
            "annotations": [
                annotation.model_dump(mode="json")
                for annotation in sorted(annotations.values(), key=lambda a: a.item_id)
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(self.path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def upsert(self, annotation: Annotation) -> Annotation:
        with self._lock:
            annotations = self.load()
            annotations[annotation.item_id] = annotation
            self._save(annotations)
        return annotation

    def delete(self, item_id: str) -> bool:
        with self._lock:
            annotations = self.load()
            if annotations.pop(item_id, None) is None:
                return False
            self._save(annotations)
        return True

    def get(self, item_id: str) -> Optional[Annotation]:
        return self.load().get(item_id)
