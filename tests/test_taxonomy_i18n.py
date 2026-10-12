from datetime import datetime, timezone

from lucidnews.i18n import LANGUAGES, format_timestamp, messages, target_language_instruction
from lucidnews.models import ContentAnalysis
from lucidnews.taxonomy import (
    Category,
    Importance,
    category_catalog_text,
    category_label,
    importance_at_least,
    importance_from_score,
    normalize_categories,
)


def test_normalize_categories_maps_aliases_drops_unknown_and_caps() -> None:
    assert normalize_categories(["LLM", "security", "nonsense", "ai", "Databases", "web"]) == [
        "ai",
        "cybersecurity",
        "databases",
    ]


def test_analysis_keeps_only_known_categories() -> None:
    analysis = ContentAnalysis.model_validate(
        {"score": 7, "reason": "r", "summary": "s", "categories": ["devtools", "finance"]}
    )

    assert analysis.categories == ["developer-tools"]


def test_every_category_has_en_and_fr_labels_and_prompt_scope() -> None:
    catalog = category_catalog_text()
    for category in Category:
        assert category_label(category.value, "en")
        assert category_label(category.value, "fr")
        assert f"`{category.value}`" in catalog
    assert category_label("cybersecurity", "fr") == "Cybersécurité"
    assert category_label("cybersecurity", "de") == "Cybersecurity"


def test_importance_levels() -> None:
    assert importance_from_score(None) is None
    assert importance_from_score(9.0) is Importance.CRITICAL
    assert importance_from_score(7.0) is Importance.HIGH
    assert importance_from_score(5.5) is Importance.MEDIUM
    assert importance_from_score(2.0) is Importance.LOW
    assert importance_at_least(Importance.HIGH, Importance.MEDIUM)
    assert not importance_at_least(Importance.LOW, Importance.MEDIUM)
    assert not importance_at_least(None, Importance.LOW)


def test_languages_cover_en_fr_and_fall_back_to_english() -> None:
    assert {"en", "fr"} <= set(LANGUAGES)
    assert set(messages("fr")) == set(messages("en"))
    assert messages("fr")["background"] == "Contexte"
    assert messages("de")["background"] == "Background"
    assert "French" in target_language_instruction("fr")
    assert target_language_instruction("de") == "language `de`"


def test_format_timestamp_per_language() -> None:
    value = datetime(2026, 10, 5, 11, 17, tzinfo=timezone.utc)

    assert format_timestamp(value, "en") == "Oct 5, 11:17"
    assert format_timestamp(value, "fr") == "5 oct. 11:17"
    assert format_timestamp(value, "zh") == "10月5日 11:17"
