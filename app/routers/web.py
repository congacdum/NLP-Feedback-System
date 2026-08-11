from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.dependencies import current_user, get_db
from app.models import Feedback, Product
from app.services.feedback_service import create_feedback
from app.services.product_service import category_counts, list_products, parse_optional_float, product_rating, resolved_image_url

router=APIRouter()


def ctx(request, db, **extra):
    return {"request":request,"user":current_user(request,db),**extra}


def pagination_prefix(request: Request) -> str:
    """Preserve every current filter while allowing the template to change page."""
    pairs = [(key, value) for key, value in request.query_params.multi_items() if key != "page" and value.strip()]
    query = urlencode(pairs)
    return f"?{query}&page=" if query else "?page="

@router.get("/")
def home(request: Request, db: Session=Depends(get_db)):
    listing=list_products(db,limit=8)
    categories=category_counts(db)
    return request.app.state.templates.TemplateResponse(request=request, name="home.html", context=ctx(request,db,products=listing["items"],categories=categories))

@router.get("/products")
def products(request: Request,q:str="",category:str="",min_price:str|None=None,max_price:str|None=None,min_rating:str|None=None,sort:str="newest",page:str="1",db:Session=Depends(get_db)):
    min_price_value = parse_optional_float(min_price)
    max_price_value = parse_optional_float(max_price)
    min_rating_value = parse_optional_float(min_rating)
    listing=list_products(db,q=q,category=category,min_price=min_price_value,max_price=max_price_value,min_rating=min_rating_value,sort=sort,page=page,limit=20)
    categories=category_counts(db)
    return request.app.state.templates.TemplateResponse(request=request, name="products.html", context=ctx(request,db,listing=listing,categories=categories,filters={"q":q,"category":category,"min_price":min_price_value,"max_price":max_price_value,"min_rating":min_rating_value,"sort":sort},pagination_prefix=pagination_prefix(request)))

@router.get("/products/{product_id}")
def product_detail(product_id:int,request:Request,db:Session=Depends(get_db)):
    product=db.get(Product,product_id)
    if not product: return RedirectResponse("/products",status_code=303)
    reviews=db.scalars(select(Feedback).where(Feedback.product_id==product_id).options(selectinload(Feedback.user),selectinload(Feedback.analyses)).order_by(Feedback.created_at.desc())).all()
    avg,count=product_rating(db,product_id)
    return request.app.state.templates.TemplateResponse(request=request, name="product_detail.html", context=ctx(request,db,product=product,image_url=resolved_image_url(product),reviews=reviews,avg_rating=avg,review_count=count))

@router.post("/products/{product_id}/review")
async def submit_review(product_id:int,request:Request,db:Session=Depends(get_db)):
    user=current_user(request,db)
    if not user or user.role!="customer": return RedirectResponse(f"/login?next=/products/{product_id}",status_code=303)
    form=await request.form()
    try:
        create_feedback(db,user_id=user.id,product_id=product_id,rating=int(form.get("rating",0)),text=str(form.get("text","")))
    except Exception as e:
        db.rollback(); return RedirectResponse(f"/products/{product_id}?review_error=1",status_code=303)
    return RedirectResponse(f"/products/{product_id}?review_ok=1",status_code=303)

@router.get("/login")
def login_page(request:Request,next:str="/",error:str="",db:Session=Depends(get_db)):
    return request.app.state.templates.TemplateResponse(request=request, name="login.html", context=ctx(request,db,next=next,error=error))

@router.get("/register")
def register_page(request:Request,error:str="",db:Session=Depends(get_db)):
    return request.app.state.templates.TemplateResponse(request=request, name="register.html", context=ctx(request,db,error=error))

@router.get("/my-reviews")
def my_reviews(request:Request,db:Session=Depends(get_db)):
    user=current_user(request,db)
    if not user: return RedirectResponse("/login?next=/my-reviews",status_code=303)
    rows=db.scalars(select(Feedback).where(Feedback.user_id==user.id).options(selectinload(Feedback.product),selectinload(Feedback.analyses)).order_by(Feedback.created_at.desc())).all()
    return request.app.state.templates.TemplateResponse(request=request, name="my_reviews.html", context=ctx(request,db,reviews=rows))
