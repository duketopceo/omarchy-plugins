"""Text cleaning for untrusted strings bound for a panel."""

from __future__ import annotations

MAX_STR = 200


def clean_text(value: object, limit: int = MAX_STR) -> str:
    """Replace C0/C1 controls (and DEL) with spaces, trim, clip to limit."""
    s = "" if value is None else str(value)
    s = "".join(" " if (ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F) else c for c in s)
    return s.strip()[: max(0, limit)]
