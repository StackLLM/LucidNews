"""Quality evaluation: hand-annotated items compared with the AI analysis."""

from .metrics import EvaluationReport, evaluate
from .models import Annotation
from .store import AnnotationStore

__all__ = ["Annotation", "AnnotationStore", "EvaluationReport", "evaluate"]
