from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.bootstrap import initialize_database
from app.config import ROOT, settings
from app.routers import api, auth, seller, web
from app.services.nlp_service import get_analyzer

@asynccontextmanager
async def lifespan(app:FastAPI):
    initialize_database()
    get_analyzer()  # Load the frozen runtime model once.
    yield

app=FastAPI(title=settings.app_name,version="1.0.0",lifespan=lifespan)
app.mount("/static",StaticFiles(directory=ROOT/"app/static"),name="static")
app.mount("/model-artifacts",StaticFiles(directory=ROOT/"model_artifacts"),name="model-artifacts")
app.state.templates=Jinja2Templates(directory=ROOT/"app/templates")
app.include_router(auth.router); app.include_router(web.router); app.include_router(api.router); app.include_router(seller.router)

@app.get("/health")
def health():
    analyzer=get_analyzer()
    return {"status":"ok","app":"nlp-feedback-system","nlp_backend":analyzer.primary_name,"scientific_runtime":analyzer.backend == "transformer"}
