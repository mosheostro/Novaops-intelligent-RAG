"""Neutralize links in model/user text before it is shown through st.markdown.

The answer model copies corpus Markdown links such as
`[state and family leave](stateFMLA.md)`; st.markdown would turn them into real
links that the browser resolves against the app's own URL
(`http://localhost:8501/stateFMLA.md`), and it auto-links bare URLs too. Policy
(Option A): EVERY link becomes non-clickable text — relative, internal,
localhost, file:// and external alike. A link keeps its label, an image its alt
text; a bare URL / angle-bracket link / e-mail is shown as a code span, which
Markdown never links. Everything else (headings, emphasis, lists, tables,
existing code) is left exactly as it is.

Presentation only: stored answers (AskResult, EvaluationResult) are never
changed; source cards show raw chunk text with st.text and do not use this.
"""
import re

# Existing code is never rewritten: fenced blocks first, then inline code spans.
_CODE = re.compile(r"(```.*?```|~~~.*?~~~|`[^`\n]*`)", re.S)

_TITLE = r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?"""
_TARGET = r"<?[^\s()<>]*(?:\([^\s()]*\)[^\s()<>]*)*>?"  # allows one level of (parentheses) in a URL

_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*" + _TARGET + _TITLE + r"\s*\)")
_INLINE_LINK = re.compile(r"\[([^\]]*)\]\(\s*" + _TARGET + _TITLE + r"\s*\)")
_REFERENCE_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_REFERENCE_DEFINITION = re.compile(r"^[ ]{0,3}\[[^\]]+\]:[ \t]*\S+" + _TITLE + r"[ \t]*$\n?", re.M)

# One pass, so text already turned into a code span is never matched again.
_AUTOLINKABLE = re.compile(
    r"<((?:[a-z][a-z0-9+.-]*:|www\.)[^\s<>]*|[^\s<>@]+@[^\s<>@]+)>"      # <https://…>, <mailto:…>, <a@b.c>
    r"|(?<![\w`])((?:https?|ftp|file)://[^\s<>`]+|www\.[^\s<>`]+)"       # bare URL / www.
    r"|(?<![\w.+`-])([\w.+-]+@[\w-]+(?:\.[\w-]+)+)",                     # bare e-mail
    re.I,
)
_TRAILING_PUNCTUATION = ".,;:!?'\")]"


def _as_code(match: re.Match) -> str:
    angle, bare, email = match.groups()
    if angle is not None:
        return f"`{angle}`"
    if email is not None:
        return f"`{email}`"
    url = bare.rstrip(_TRAILING_PUNCTUATION)  # "see https://x.io." — the period is prose, not URL
    return f"`{url}`{bare[len(url):]}"


def _neutralize_prose(text: str) -> str:
    text = _IMAGE.sub(r"\1", text)
    text = _INLINE_LINK.sub(r"\1", text)
    text = _REFERENCE_DEFINITION.sub("", text)
    text = _REFERENCE_LINK.sub(r"\1", text)
    return _AUTOLINKABLE.sub(_as_code, text)


def neutralize_links(text: str) -> str:
    """Return `text` with every Markdown link, image, autolink, bare URL and
    e-mail made non-clickable; code and all other formatting unchanged."""
    parts = _CODE.split(text)  # odd indices are code
    return "".join(part if i % 2 else _neutralize_prose(part) for i, part in enumerate(parts))
