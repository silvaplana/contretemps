"""Formatted text in a publication (Seb, 19 November 2026; maquette « Texte
mis en forme », spec/modules/actualites.md §12.15): bold, underline and two
sizes, kept in the body as light tags so that the text stays plain text:
[g]gras[/g], [s]souligné[/s], [grand]…[/grand], [petit]…[/petit].
The screen reads the same tags (frontend texteRiche.js)."""

from __future__ import annotations

import re
from html import escape

TAG = re.compile(r"\[(/?)(g|s|grand|petit)\]")
HTML_OPEN = {
    "g": "<strong>",
    "s": "<u>",
    "grand": '<span style="font-size:22px;font-weight:700;line-height:1.3">',
    "petit": '<span style="font-size:15px">',
}
HTML_CLOSE = {"g": "</strong>", "s": "</u>", "grand": "</span>", "petit": "</span>"}


def plain(body: str) -> str:
    """The text without its tags: notifications, mail subject, text version."""
    return TAG.sub("", body or "")


def to_html(body: str) -> str:
    """Escaped HTML for the mail; a tag closed without being opened is dropped,
    one left open is closed at the end."""
    out, opened = [], []
    position = 0
    for match in TAG.finditer(body or ""):
        out.append(escape(body[position:match.start()]))
        position = match.end()
        closing, name = match.group(1) == "/", match.group(2)
        if not closing and name not in opened:
            opened.append(name)
            out.append(HTML_OPEN[name])
        elif closing and name in opened:
            # Close what was opened after it, then reopen it: tags never cross.
            after = opened[opened.index(name) + 1:]
            out.extend(HTML_CLOSE[n] for n in reversed(after))
            out.append(HTML_CLOSE[name])
            opened.remove(name)
            out.extend(HTML_OPEN[n] for n in after)
    out.append(escape((body or "")[position:]))
    out.extend(HTML_CLOSE[n] for n in reversed(opened))
    return "".join(out).replace("\n", "<br>")
