"""Independent clause splitting adapted from donor issue-extraction ideas."""
from __future__ import annotations

import re

_BOUNDARY = re.compile(r"\s+(?:nhưng|tuy nhiên|còn|trong khi)\s+|[,;.!?]+", re.IGNORECASE)


def split_clauses(text: str) -> list[str]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return [part.strip() for part in _BOUNDARY.split(text.strip()) if part.strip()]
