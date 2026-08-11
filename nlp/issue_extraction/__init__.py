"""Non-authoritative issue/evidence enrichment for Vietnamese feedback.

This package is adapted for internal academic use from the donor archive
``nlp_engine.zip``.  It never predicts or mutates ABSA aspect/sentiment labels.
"""

from .pipeline import extract_issue_details

__all__ = ["extract_issue_details"]
