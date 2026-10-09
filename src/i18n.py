"""Output languages and localized digest strings.

Adding a language means adding a ``Language`` entry and, optionally, a message
table. Any key missing from a table falls back to English, so a new language
works immediately (AI-generated content is written in the target language by the
enrichment stage; only the fixed digest labels need translating).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

BRAND = "LucidNews"
DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class Language:
    code: str
    english_name: str
    native_name: str
    prompt_name: str  # how the AI is told which language to write


LANGUAGES: Dict[str, Language] = {
    "en": Language("en", "English", "English", "English (language tag `en`)"),
    "fr": Language("fr", "French", "Français", "French (language tag `fr`), using natural, professional French"),
    "zh": Language("zh", "Chinese", "简体中文", "Simplified Chinese (language tag `zh`)"),
}


def is_supported(code: str) -> bool:
    return code.lower() in LANGUAGES


def target_language_instruction(code: str) -> str:
    language = LANGUAGES.get(code.lower())
    return language.prompt_name if language else f"language `{code}`"


_EN: Dict[str, str] = {
    "header": f"{BRAND} Daily",
    "source": "Source",
    "background": "Background",
    "discussion": "Discussion",
    "references": "References",
    "tags": "Tags",
    "reliability": "Reliability",
    "selected_items": "From {total} items, {selected} important content pieces were selected",
    "empty_analyzed": "Analyzed {total} items, but none met the importance threshold.",
    "empty_body": (
        "No significant developments today. This might indicate:\n"
        "- A quiet day in your tracked sources\n"
        "- The AI score threshold is too high\n"
        "- Your information sources need expansion\n\n"
        "Consider:\n"
        "1. Lowering the configured profile threshold\n"
        "2. Adding more diverse information sources\n"
        "3. Checking if the AI model is working correctly\n"
    ),
    "overview_selected": "Selected {selected} important items from {total} fetched items.",
    "overview_details": "Details will be sent item by item so you can read only the topics you care about.",
    "item_prefix": "Item {index}/{total}",
    "title_daily": BRAND + " {date} Daily",
    "title_overview": BRAND + " {date} Overview",
    "title_collapsible": BRAND + " {date} Collapsible Daily",
    "collapsible_empty": "Analyzed {total} items, but none met the importance threshold.",
    "collapsible_hint": "Expand the panels below to read the full briefing inside Feishu/Lark.",
    "email_subject": BRAND + " — {date}",
    "label_confirmed": "Confirmed",
    "label_reliable": "Reliable",
    "label_unverified": "Unverified — not confirmed by an official or reputable source",
    "label_rumor": "Rumor — speculation or leak, not a confirmed fact",
    "tier_official": "official source",
    "tier_reputable": "reputable source",
    "tier_community": "community source",
    "tier_unknown": "unrecognized source",
    "corroborated": "corroborated by {count} independent source(s)",
    "unanalyzed_title": "Not analyzed by the AI",
    "unanalyzed_notice": (
        "The AI quota ran out during this run. These {count} item(s) were not analyzed: "
        "no summary, no score, no claim check. Original headlines, to be verified."
    ),
    "unanalyzed_only": "The AI quota ran out: {count} item(s) are listed without analysis.",
}

_FR: Dict[str, str] = {
    "header": f"{BRAND} Quotidien",
    "source": "Source",
    "background": "Contexte",
    "discussion": "Discussion",
    "references": "Références",
    "tags": "Tags",
    "reliability": "Fiabilité",
    "selected_items": "Sur {total} contenus, {selected} informations importantes ont été retenues",
    "empty_analyzed": "{total} contenus analysés, mais aucun n'atteint le seuil d'importance.",
    "empty_body": (
        "Aucune actualité marquante aujourd'hui. Causes possibles :\n"
        "- Journée calme sur les sources suivies\n"
        "- Seuil de score IA trop élevé\n"
        "- Sources d'information à élargir\n\n"
        "Pistes :\n"
        "1. Abaisser le seuil du profil concerné\n"
        "2. Ajouter des sources plus variées\n"
        "3. Vérifier que le modèle IA fonctionne correctement\n"
    ),
    "overview_selected": "{selected} informations importantes retenues sur {total} contenus collectés.",
    "overview_details": "Le détail est envoyé article par article : lisez seulement les sujets qui vous intéressent.",
    "item_prefix": "Article {index}/{total}",
    "title_daily": BRAND + " {date} — Quotidien",
    "title_overview": BRAND + " {date} — Sommaire",
    "title_collapsible": BRAND + " {date} — Quotidien (replié)",
    "collapsible_empty": "{total} contenus analysés, mais aucun n'atteint le seuil d'importance.",
    "collapsible_hint": "Dépliez les panneaux ci-dessous pour lire le briefing complet dans Feishu/Lark.",
    "email_subject": BRAND + " — {date}",
    "label_confirmed": "Confirmé",
    "label_reliable": "Fiable",
    "label_unverified": "Non vérifié — pas confirmé par une source officielle ou reconnue",
    "label_rumor": "Rumeur — spéculation ou fuite, pas un fait confirmé",
    "tier_official": "source officielle",
    "tier_reputable": "source reconnue",
    "tier_community": "source communautaire",
    "tier_unknown": "source non référencée",
    "corroborated": "corroboré par {count} source(s) indépendante(s)",
    "unanalyzed_title": "Sans analyse IA",
    "unanalyzed_notice": (
        "Le quota IA a été épuisé pendant ce run. Ces {count} news n'ont pas été analysées : "
        "ni résumé, ni score, ni vérification. Titres d'origine, à vérifier."
    ),
    "unanalyzed_only": "Le quota IA est épuisé : {count} news sont listées sans analyse.",
}

_ZH: Dict[str, str] = {
    "header": f"{BRAND} 每日速递",
    "source": "来源",
    "background": "背景",
    "discussion": "社区讨论",
    "references": "参考链接",
    "tags": "标签",
    "reliability": "可信度",
    "selected_items": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
    "empty_analyzed": "已分析 {total} 条内容，但没有达到重要性阈值的条目。",
    "empty_body": (
        "今日暂无重要动态，可能原因：\n"
        "- 今天关注的信息源较平静\n"
        "- AI 评分阈值设置过高\n"
        "- 信息源种类有待扩充\n\n"
        "建议：\n"
        "1. 降低当前 Profile 的过滤阈值\n"
        "2. 添加更多多样化的信息源\n"
        "3. 检查 AI 模型是否正常工作\n"
    ),
    "overview_selected": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
    "overview_details": "下面会按内容逐条发送详情，你可以只看感兴趣的标题。",
    "item_prefix": "第 {index}/{total} 条",
    "title_daily": BRAND + " {date} 日报",
    "title_overview": BRAND + " {date} 总览",
    "title_collapsible": BRAND + " {date} 折叠日报",
    "collapsible_empty": "已分析 {total} 条内容，暂无达到重要性阈值的资讯。",
    "collapsible_hint": "点击下方新闻面板即可在飞书内展开阅读全文。",
    "email_subject": BRAND + " — {date}",
    "label_confirmed": "已确认",
    "label_reliable": "可信",
    "label_unverified": "未经证实——尚无官方或可信来源确认",
    "label_rumor": "传闻——猜测或泄露信息，并非已确认事实",
    "tier_official": "官方来源",
    "tier_reputable": "可信来源",
    "tier_community": "社区来源",
    "tier_unknown": "未收录来源",
    "corroborated": "{count} 个独立来源佐证",
}

MESSAGES: Dict[str, Dict[str, str]] = {"en": _EN, "fr": _FR, "zh": _ZH}


def messages(language: str) -> Dict[str, str]:
    """Return the message table for a language, falling back to English per key."""
    return {**_EN, **MESSAGES.get(language.lower(), {})}


_FR_MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def format_timestamp(value: datetime, language: str) -> str:
    """Short publication timestamp used on each digest item."""
    language = language.lower()
    if language == "zh":
        return f"{value.month}月{value.day}日 {value:%H:%M}"
    if language == "fr":
        return f"{value.day} {_FR_MONTHS[value.month - 1]} {value:%H:%M}"
    return f"{value:%b} {value.day}, {value:%H:%M}"
