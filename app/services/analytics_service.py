from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Feedback, FeedbackAnalysis, Product
from nlp.schema import ASPECTS, SENTIMENTS, ASPECT_VI, SENTIMENT_VI


def dashboard_summary(session: Session) -> dict:
    total = int(session.scalar(select(func.count(Feedback.id))) or 0)
    avg = float(session.scalar(select(func.avg(Feedback.rating))) or 0.0)
    negative = int(session.scalar(select(func.count(FeedbackAnalysis.id)).where(FeedbackAnalysis.sentiment == "negative")) or 0)
    aspect_counts = dict(session.execute(select(FeedbackAnalysis.aspect, func.count(FeedbackAnalysis.id)).group_by(FeedbackAnalysis.aspect)).all())
    most_aspect = max(aspect_counts, key=aspect_counts.get) if aspect_counts else None
    return {"total_feedback": total, "average_rating": avg, "negative_mentions": negative, "most_reported_aspect": most_aspect, "most_reported_aspect_vi": ASPECT_VI.get(most_aspect, "—")}


def aspect_matrix(session: Session) -> list[dict]:
    rows = session.execute(select(FeedbackAnalysis.aspect, FeedbackAnalysis.sentiment, func.count(FeedbackAnalysis.id)).group_by(FeedbackAnalysis.aspect, FeedbackAnalysis.sentiment)).all()
    counts = defaultdict(lambda: defaultdict(int))
    for aspect, sentiment, count in rows: counts[aspect][sentiment] = int(count)
    out=[]
    for aspect in ASPECTS:
        total=sum(counts[aspect].values())
        out.append({"aspect":aspect,"aspect_vi":ASPECT_VI[aspect],"total":total,"sentiments":{s:counts[aspect][s] for s in SENTIMENTS},"percentages":{s:(counts[aspect][s]*100/total if total else 0) for s in SENTIMENTS}})
    return out


def product_analytics(session: Session, limit: int = 20) -> list[dict]:
    rows = session.execute(
        select(Product.id, Product.name, func.count(Feedback.id), func.avg(Feedback.rating))
        .join(Feedback, Feedback.product_id == Product.id, isouter=True)
        .group_by(Product.id)
        .order_by(func.count(Feedback.id).desc())
        .limit(limit)
    ).all()
    out=[]
    for pid,name,count,avg in rows:
        neg = int(session.scalar(select(func.count(FeedbackAnalysis.id)).join(Feedback).where(Feedback.product_id==pid, FeedbackAnalysis.sentiment=="negative")) or 0)
        out.append({"id":pid,"name":name,"feedback_count":int(count or 0),"average_rating":float(avg or 0),"negative_mentions":neg})
    return out


def issue_summary(session: Session, limit: int = 6) -> list[dict]:
    """Aggregate deterministic issue enrichment already stored with feedback."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    rows = session.scalars(
        select(Feedback.issue_details_json).where(Feedback.issue_details_json.is_not(None))
    ).all()
    for raw_details in rows:
        try:
            details = json.loads(raw_details or "[]")
        except (TypeError, ValueError):
            continue
        if not isinstance(details, list):
            continue
        for detail in details:
            if not isinstance(detail, dict):
                continue
            issue = detail.get("issue")
            aspect = detail.get("aspect")
            sentiment = detail.get("sentiment")
            if isinstance(issue, str) and isinstance(aspect, str) and sentiment in {"negative", "mixed"}:
                counts[(issue, aspect)] += 1

    return [
        {
            "issue": issue,
            "aspect": aspect,
            "aspect_vi": ASPECT_VI.get(aspect, aspect),
            "count": count,
        }
        for (issue, aspect), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][0]))[:limit]
    ]
