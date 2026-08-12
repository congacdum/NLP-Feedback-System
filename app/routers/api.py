from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db
from app.services.analytics_service import aspect_matrix, dashboard_summary
from app.services.feedback_service import create_feedback
from app.services.nlp_service import get_analyzer
from app.services.product_service import list_products, parse_optional_float

router = APIRouter(prefix="/api")


class FeedbackIn(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1, max_length=5000)


class AnalyzeIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@router.get("/products")
def api_products(page: str = "1", limit: str = "20", q: str = "", category: str = "", min_price: str | None = None, max_price: str | None = None, min_rating: str | None = None, sort: str = "newest", db: Session = Depends(get_db)):
    listing = list_products(db, page=page, limit=limit, q=q, category=category, min_price=parse_optional_float(min_price), max_price=parse_optional_float(max_price), min_rating=parse_optional_float(min_rating), sort=sort)
    return {"page": listing["page"], "pages": listing["pages"], "total": listing["total"], "items": [{"id": item["product"].id, "name": item["product"].name, "category": item["product"].category, "price": item["product"].price if item["product"].price > 0 else None, "image_url": item["image_url_resolved"], "rating": item["avg_rating"], "review_count": item["review_count"]} for item in listing["items"]]}


@router.post("/feedback")
def api_feedback(payload: FeedbackIn, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "customer":
        raise HTTPException(401, "Login required")
    feedback = create_feedback(db, user_id=user.id, product_id=payload.product_id, rating=payload.rating, text=payload.text)
    if feedback.analysis_status == "failed":
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": "analysis_unavailable",
                "message": "Chưa thể phân tích phản hồi lúc này. Nội dung của bạn đã được lưu để xử lý lại.",
            },
        )
    analysis = list(getattr(feedback, "response_analysis", []))
    return {
        "success": True,
        "feedback_id": feedback.id,
        "id": feedback.id,
        "rating": feedback.rating,
        "analysis_status": feedback.analysis_status,
        "model_version": feedback.model_version,
        "analysis": analysis,
        "aspects": analysis,
        "assistant_message": getattr(feedback, "assistant_message", "Cảm ơn bạn đã chia sẻ. Phản hồi của bạn đã được ghi nhận."),
    }


@router.post("/nlp/analyze")
def api_analyze(payload: AnalyzeIn):
    return get_analyzer().analyze(payload.text)


@router.get("/analytics/summary")
def api_summary(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "seller":
        raise HTTPException(403, "Seller access required")
    return {"summary": dashboard_summary(db), "aspects": aspect_matrix(db)}
