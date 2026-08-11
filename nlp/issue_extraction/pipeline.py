"""Fail-safe evidence extraction, adapted from donor issue/canonicalization ideas.

This branch receives raw text separately from PhoBERT preprocessing.  Its
return value is UI/developer enrichment only and cannot alter ABSA output.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from .clause_splitter import split_clauses
from .models import IssueDetail, ProductIssueContext
from .taxonomy import ISSUE_RULES

_NEGATION = re.compile(r"\b(?:không|chẳng|chả|chưa)\b", re.IGNORECASE)


def _normalize_for_issue_matching(text: str) -> str:
    """Keep an independent, conservative issue-engine matching branch."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text).casefold()).strip()


def product_context_from_payload(payload: Mapping | None) -> ProductIssueContext:
    """Accept only the main app's already-authoritative product identifier."""
    payload = payload or {}
    raw_id = payload.get("product_id")
    try:
        product_id = int(raw_id) if raw_id is not None else None
    except (TypeError, ValueError):
        product_id = None
    return ProductIssueContext(
        product_id=product_id,
        category=str(payload.get("category") or "") or None,
    )


def _category_is_compatible(rule, context: ProductIssueContext) -> bool:
    """Require explicit authoritative category support for narrow sub-issues."""
    if not rule.allowed_category_terms:
        return True
    category = _normalize_for_issue_matching(context.category or "")
    return bool(category) and any(term in category for term in rule.allowed_category_terms)


def _is_negated(clause: str, match: re.Match[str]) -> bool:
    """Reject a candidate when a Vietnamese negator occurs in its local span.

    The issue branch is intentionally conservative: it is preferable to omit
    a detail than to present a negated complaint as a factual issue.
    """
    window = clause[max(0, match.start() - 8):match.end()]
    return bool(_NEGATION.search(window))


def extract_issue_details(text: str, *, product_context: Mapping | None = None) -> list[dict]:
    """Extract canonical issue details without producing ABSA predictions."""
    if not isinstance(text, str) or not text.strip():
        return []
    # Constructing context intentionally performs no CSV/name/fuzzy lookup.
    context = product_context_from_payload(product_context)
    details: list[IssueDetail] = []
    seen: set[str] = set()
    for raw_clause in split_clauses(text) or [text.strip()]:
        clause = _normalize_for_issue_matching(raw_clause)
        for rule in ISSUE_RULES:
            match = re.search(rule.pattern, clause, flags=re.IGNORECASE)
            if (
                not match
                or rule.canonical_issue in seen
                or (_is_negated(clause, match) and not rule.allow_negated_match)
                or not _category_is_compatible(rule, context)
            ):
                continue
            seen.add(rule.canonical_issue)
            details.append(IssueDetail(
                canonical_issue=rule.canonical_issue,
                core_aspect=rule.core_aspect,
                evidence=raw_clause.strip(),
                ui_keyword=match.group(0).strip(),
            ))
    return [detail.to_dict() for detail in details]


def compatible_issue_details(aspects: list[Mapping], issue_details: list[Mapping]) -> list[dict]:
    """Attach only details compatible with an already-detected core aspect."""
    detected = {str(item.get("aspect") or "") for item in aspects}
    return [dict(item) for item in issue_details if str(item.get("core_aspect") or "") in detected]
