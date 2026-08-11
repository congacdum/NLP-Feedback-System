from __future__ import annotations

import html
import re
import unicodedata

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){8,10}(?!\d)")
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str, *, mask_contacts: bool = True) -> str:
    """Conservative Vietnamese normalization.

    Deliberately preserves accents, negation, emoji, casing cues and punctuation.
    Only Unicode/HTML/whitespace normalization and optional contact masking are used.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    text = unicodedata.normalize("NFC", html.unescape(text)).strip()
    if mask_contacts:
        text = _URL_RE.sub(" <URL> ", text)
        text = _EMAIL_RE.sub(" <EMAIL> ", text)
        text = _PHONE_RE.sub(" <PHONE> ", text)
    return _SPACE_RE.sub(" ", text).strip()


def normalized_hash_text(text: str) -> str:
    """Normalization used only for duplicate/leakage detection."""
    text = normalize_text(text, mask_contacts=True).casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return _SPACE_RE.sub(" ", text).strip()
