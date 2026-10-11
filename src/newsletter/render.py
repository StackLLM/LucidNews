"""Render a digest as an e-mail: the single path used to send it and to preview it.

The Markdown comes from ``DailySummarizer``, which escapes every source text. Any ``<`` left
is made literal here before conversion, so nothing a source published can become markup:
the page carries no script, no remote image and no form.
"""

import html
import re
from dataclasses import dataclass

try:
    import markdown
except ImportError:  # the text version is still sent
    markdown = None

from ..ai.markdown_utils import clean_app_summary_markdown
from ..i18n import messages

# Same palette as the web app (frontend/src/styles.css).
_STYLE = """
body { margin: 0; padding: 24px 12px; background: #f4f5fa; color: #0f1530;
  font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; font-size: 15px; }
.card { max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 18px;
  padding: 28px 32px; box-shadow: 0 1px 3px rgba(15, 21, 48, 0.08); }
h1 { font-family: Georgia, 'Times New Roman', serif; font-size: 26px; line-height: 1.25; margin: 0 0 12px; color: #0f1530; }
h2 { font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: #4c3fd8; margin: 32px 0 4px; }
h3 { font-size: 18px; line-height: 1.35; margin: 22px 0 6px; color: #0f1530; }
p { margin: 8px 0; }
a { color: #4c3fd8; text-decoration: none; }
blockquote { margin: 12px 0; padding: 10px 14px; background: #eeecfc; border-radius: 10px; color: #362bb0; }
blockquote p { margin: 0; }
hr { border: 0; border-top: 1px solid #e6e8f0; margin: 22px 0; }
code { background: #f1f2f8; padding: 1px 6px; border-radius: 5px; font-size: 13px; }
pre { background: #f1f2f8; padding: 12px; border-radius: 10px; white-space: pre-wrap; }
.footer { max-width: 680px; margin: 16px auto 0; text-align: center; font-size: 12px; color: #5b6478; }
""".strip()


_BARE_AMPERSAND = re.compile(r"&(?!(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#[xX][0-9A-Fa-f]+);)")


# Python-Markdown needs a blank line between a bold group title and its numbered list.
_LIST_AFTER_TITLE = re.compile(r"(?m)^(\*\*[^\n]+\*\*)\n(?=\d+\. )")


def _escape_markup(text: str) -> str:
    """Make ``<`` literal, so no tag can open. Entities already written by the summarizer
    stay as they are (escaping them again would show "&lt;" to the reader), and ``>`` stays
    because a quote line starts with it and a lone ``>`` cannot open anything."""
    return _BARE_AMPERSAND.sub("&amp;", text).replace("<", "&lt;")


@dataclass(frozen=True)
class RenderedEmail:
    html: str
    text: str


# Replaced by each reader's own signed link when the e-mail is sent.
UNSUBSCRIBE_PLACEHOLDER = "{{unsubscribe_url}}"


def render_email(
    summary_md: str,
    *,
    language: str,
    sender_name: str,
    unsubscribe_keyword: str,
    unsubscribe_link: bool = False,
) -> RenderedEmail:
    """``unsubscribe_link``: footer carries ``UNSUBSCRIBE_PLACEHOLDER`` instead of the reply keyword."""
    labels = messages(language)
    text = clean_app_summary_markdown(summary_md)
    safe = _LIST_AFTER_TITLE.sub(r"\1\n\n", _escape_markup(text))
    body = markdown.markdown(safe) if markdown else f"<pre>{safe}</pre>"
    if unsubscribe_link:
        footer_line = f'<a href="{UNSUBSCRIBE_PLACEHOLDER}">{html.escape(labels["email_footer_link"])}</a>'
        text += f"\n\n{labels['email_footer_link']}: {UNSUBSCRIBE_PLACEHOLDER}\n"
    else:
        footer_line = html.escape(labels["email_footer_reply"].format(keyword=unsubscribe_keyword))
    footer = f"<p>{html.escape(labels['email_footer_sent_by'].format(sender=sender_name))}</p><p>{footer_line}</p>"
    page = (
        "<!DOCTYPE html>\n"
        f'<html lang="{html.escape(language, quote=True)}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<style>\n{_STYLE}\n</style>\n</head>\n<body>\n"
        f'<div class="card">\n{body}\n</div>\n<div class="footer">{footer}</div>\n</body>\n</html>\n'
    )
    return RenderedEmail(html=page, text=text)
