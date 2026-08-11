"""Data contracts for the isolated issue-extraction enrichment branch."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProductIssueContext:
    """Context copied from an already-authoritative database product payload."""

    product_id: int | None
    category: str | None = None


@dataclass(frozen=True)
class IssueDetail:
    canonical_issue: str
    core_aspect: str
    evidence: str
    ui_keyword: str
    source: str = "donor_adapted_rule"

    def to_dict(self) -> dict:
        return asdict(self)
