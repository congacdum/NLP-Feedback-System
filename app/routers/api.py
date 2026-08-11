from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db
from app.models import Product
from app.services.analytics_service import aspect_matrix, dashboard_summary
from app.services.chat_service import begin_product_chat, chat_reply, consume_confirmed_feedback
from app.services.feedback_service import create_feedback
from app.services.nlp_service import get_analyzer
from app.services.product_service import list_products, parse_optional_float, resolved_image_url

router = APIRouter(prefix="/api")


class FeedbackIn(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1, max_length=5000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    sender: str = "web-user"
    product_id: int | None = None


class ChatStartIn(BaseModel):
    product_id: int
    sender: str = "web-user"


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
    return {"id": feedback.id, "analysis_status": feedback.analysis_status, "model_version": feedback.model_version}


@router.post("/nlp/analyze")
def api_analyze(payload: AnalyzeIn):
    return get_analyzer().analyze(payload.text)


@router.post("/chat/start")
def api_chat_start(payload: ChatStartIn, db: Session = Depends(get_db)):
    """Bind a chat session to a product ID validated by the database."""
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return begin_product_chat(payload.sender, {
        "product_id": product.id,
        "product_name": product.name,
        "image_url": resolved_image_url(product),
        "price": product.price if product.price > 0 else None,
    })


@router.post("/chat")
async def api_chat(payload: ChatIn, request: Request, db: Session = Depends(get_db)):
    reply = await chat_reply(payload.message, payload.sender, product_id=payload.product_id)
    if not reply.get("ready_to_save"):
        return reply

    if not payload.product_id:
        reply.update(ready_to_save=False, text="Mình cần xác định sản phẩm trước khi lưu đánh giá. Hãy mở chatbot từ trang chi tiết sản phẩm.")
        return reply
    user = current_user(request, db)
    if not user or user.role != "customer":
        reply.update(ready_to_save=False, text="Đánh giá của bạn đã được xác nhận. Hãy đăng nhập để hệ thống lưu đúng vào sản phẩm này.")
        return reply
    confirmed = consume_confirmed_feedback(payload.sender, product_id=payload.product_id)
    if not confirmed:
        reply.update(ready_to_save=False, text="Phiên đánh giá không còn khớp với sản phẩm hiện tại. Hãy mở lại phần đánh giá của sản phẩm này.")
        return reply
    feedback = create_feedback(db, user_id=user.id, product_id=confirmed["product_id"], rating=confirmed["rating"], text=confirmed["text"])
    reply.update(text="Cảm ơn bạn. Đánh giá đã được lưu thành công.", feedback_id=feedback.id)
    return reply


@router.get("/analytics/summary")
def api_summary(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "seller":
        raise HTTPException(403, "Seller access required")
    return {"summary": dashboard_summary(db), "aspects": aspect_matrix(db)}
