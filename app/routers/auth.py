from __future__ import annotations

from urllib.parse import quote
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.models import User
from app.security import create_session_token, hash_password, verify_password

router=APIRouter()


def _redirect_login_error(path: str, message: str):
    return RedirectResponse(f"{path}?error={quote(message)}", status_code=303)

@router.post("/auth/login")
async def login(request: Request, db: Session=Depends(get_db)):
    form=await request.form(); email=str(form.get("email","")).strip().casefold(); password=str(form.get("password", "")); next_url=str(form.get("next","/"))
    user=db.scalar(select(User).where(User.email==email))
    if not user or not verify_password(password,user.password_hash): return _redirect_login_error("/login","Email hoặc mật khẩu không đúng")
    if user.role != "customer": return _redirect_login_error("/login","Tài khoản này không thuộc khu vực khách hàng")
    safe_next = next_url if next_url.startswith("/") and not next_url.startswith("//") else "/"
    resp=RedirectResponse(safe_next,status_code=303)
    resp.set_cookie(settings.cookie_name,create_session_token(user.id,user.role),httponly=True,samesite="lax")
    return resp

@router.post("/auth/register")
async def register(request: Request, db: Session=Depends(get_db)):
    form=await request.form(); name=str(form.get("name","")).strip(); email=str(form.get("email","")).strip().casefold(); password=str(form.get("password", "")); confirm=str(form.get("confirm_password", ""))
    if not name or "@" not in email: return _redirect_login_error("/register","Thông tin đăng ký chưa hợp lệ")
    if password != confirm: return _redirect_login_error("/register","Mật khẩu xác nhận không khớp")
    if db.scalar(select(User.id).where(User.email==email)): return _redirect_login_error("/register","Email đã tồn tại")
    try: hashed=hash_password(password)
    except ValueError as e: return _redirect_login_error("/register",str(e))
    user=User(name=name,email=email,password_hash=hashed,role="customer"); db.add(user); db.commit(); db.refresh(user)
    resp=RedirectResponse("/",status_code=303); resp.set_cookie(settings.cookie_name,create_session_token(user.id,user.role),httponly=True,samesite="lax"); return resp

@router.post("/seller/auth/login")
async def seller_login(request: Request, db: Session=Depends(get_db)):
    form=await request.form(); email=str(form.get("email","")).strip().casefold(); password=str(form.get("password",""))
    user=db.scalar(select(User).where(User.email==email))
    if not user or user.role!="seller" or not verify_password(password,user.password_hash): return _redirect_login_error("/seller/login","Tài khoản seller không hợp lệ")
    resp=RedirectResponse("/seller",status_code=303); resp.set_cookie(settings.cookie_name,create_session_token(user.id,user.role),httponly=True,samesite="lax"); return resp

@router.post("/auth/logout")
async def logout():
    resp=RedirectResponse("/",status_code=303); resp.delete_cookie(settings.cookie_name); return resp
