from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import ROOT, settings
from app.dependencies import current_user, get_db
from app.models import Feedback
from app.services.analytics_service import aspect_matrix, dashboard_summary, issue_summary, product_analytics
from nlp.schema import ASPECT_VI, SENTIMENT_VI

router=APIRouter(prefix="/seller")


def seller_ctx(request:Request,db:Session,**extra):
    user=current_user(request,db)
    return {"request":request,"user":user,"aspect_vi":ASPECT_VI,"sentiment_vi":SENTIMENT_VI,**extra}


def seller_guard(request:Request,db:Session):
    user=current_user(request,db)
    return user if user and user.role=="seller" else None

@router.get("/login")
def seller_login_page(request:Request,error:str="",db:Session=Depends(get_db)):
    return request.app.state.templates.TemplateResponse(request=request, name="seller_login.html", context=seller_ctx(request,db,error=error))

@router.get("")
def seller_dashboard(request:Request,db:Session=Depends(get_db)):
    if not seller_guard(request,db): return RedirectResponse("/seller/login",status_code=303)
    recent=db.scalars(select(Feedback).options(selectinload(Feedback.product),selectinload(Feedback.analyses)).order_by(Feedback.created_at.desc()).limit(8)).all()
    return request.app.state.templates.TemplateResponse(request=request, name="seller_dashboard.html", context=seller_ctx(request,db,summary=dashboard_summary(db),matrix=aspect_matrix(db),recent=recent,products=product_analytics(db,6),issues=issue_summary(db)))

@router.get("/feedback")
def seller_feedback(request:Request,db:Session=Depends(get_db)):
    if not seller_guard(request,db): return RedirectResponse("/seller/login",status_code=303)
    rows=db.scalars(select(Feedback).options(selectinload(Feedback.product),selectinload(Feedback.user),selectinload(Feedback.analyses)).order_by(Feedback.created_at.desc())).all()
    return request.app.state.templates.TemplateResponse(request=request, name="seller_feedback.html", context=seller_ctx(request,db,feedbacks=rows))

@router.get("/feedback/{feedback_id}")
def seller_feedback_detail(feedback_id:int,request:Request,db:Session=Depends(get_db)):
    if not seller_guard(request,db): return RedirectResponse("/seller/login",status_code=303)
    row=db.scalar(select(Feedback).where(Feedback.id==feedback_id).options(selectinload(Feedback.product),selectinload(Feedback.user),selectinload(Feedback.analyses)))
    if not row:return RedirectResponse("/seller/feedback",status_code=303)
    try:
        enrichment = json.loads(row.issue_details_json or "[]")
    except (TypeError, ValueError):
        enrichment = []
    return request.app.state.templates.TemplateResponse(request=request, name="seller_feedback_detail.html", context=seller_ctx(request,db,feedback=row,enrichment=enrichment))

@router.get("/aspects")
def seller_aspects(request:Request,db:Session=Depends(get_db)):
    if not seller_guard(request,db): return RedirectResponse("/seller/login",status_code=303)
    return request.app.state.templates.TemplateResponse(request=request, name="seller_aspects.html", context=seller_ctx(request,db,matrix=aspect_matrix(db)))

@router.get("/products")
def seller_products(request:Request,db:Session=Depends(get_db)):
    if not seller_guard(request,db): return RedirectResponse("/seller/login",status_code=303)
    return request.app.state.templates.TemplateResponse(request=request, name="seller_products.html", context=seller_ctx(request,db,products=product_analytics(db,100)))

@router.get("/model-evaluation")
def model_evaluation(request:Request,db:Session=Depends(get_db),view:str="natural"):
    if not seller_guard(request,db): return RedirectResponse("/seller/login",status_code=303)

    candidates = []
    if settings.evaluation_artifact:
        candidate = Path(settings.evaluation_artifact)
        if not candidate.is_absolute(): candidate = ROOT / candidate
        if candidate.exists(): candidates.append(candidate)
    if settings.transformer_artifact:
        candidate = Path(settings.transformer_artifact)
        if not candidate.is_absolute(): candidate = ROOT / candidate
        if candidate.exists(): candidates.append(candidate)

    requested_balanced = view == "balanced"
    natural_available = any((candidate / "evaluation" / "metrics.json").exists() for candidate in candidates)
    balanced_available = any((candidate / "evaluation_balanced_v2" / "metrics.json").exists() for candidate in candidates)
    artifact_root = None
    eval_dir = None
    evaluation_kind = None
    if requested_balanced:
        for candidate in candidates:
            if (candidate / "evaluation_balanced_v2" / "metrics.json").exists():
                artifact_root, eval_dir, evaluation_kind = candidate, candidate / "evaluation_balanced_v2", "balanced"
                break
    else:
        for candidate in candidates:
            if (candidate / "evaluation" / "metrics.json").exists():
                artifact_root, eval_dir, evaluation_kind = candidate, candidate / "evaluation", "final"
                break
    if eval_dir is None and not requested_balanced:
        for candidate in candidates:
            if (candidate / "evaluation_dev" / "metrics.json").exists():
                artifact_root, eval_dir, evaluation_kind = candidate, candidate / "evaluation_dev", "dev"
                break
    if artifact_root is None or eval_dir is None:
        return request.app.state.templates.TemplateResponse(
            request=request, name="seller_model_eval.html",
            context=seller_ctx(request, db, metrics={}, plots=[], artifact_rel="", artifact_name=None, no_evaluation=True),
        )

    metrics={}
    try: metrics=json.loads((eval_dir/"metrics.json").read_text(encoding="utf-8"))
    except Exception: pass
    if metrics.get("artifact_kind") == "demo_baseline":
        return request.app.state.templates.TemplateResponse(
            request=request, name="seller_model_eval.html",
            context=seller_ctx(request, db, metrics={}, plots=[], artifact_rel="", artifact_name=None, no_evaluation=True),
        )
    if not metrics:
        return request.app.state.templates.TemplateResponse(
            request=request, name="seller_model_eval.html",
            context=seller_ctx(request, db, metrics={}, plots=[], artifact_rel="", artifact_name=None, no_evaluation=True),
        )
    plot_names = (
        [
            ("dataset_distribution.png", "Balanced Test aspect distribution"),
            ("aspect_sentiment_heatmap.png", "Balanced Test aspect by sentiment"),
            ("review_length_distribution.png", "Balanced Test feedback length"),
            ("aspect_f1.png", "F1 by aspect"),
            ("sentiment_f1.png", "F1 by sentiment"),
            ("aspect_sentiment_f1.png", "F1 by aspect and sentiment"),
            ("sentiment_confusion.png", "Sentiment confusion matrix"),
        ]
        if evaluation_kind == "balanced" else
        [
            ("train_dev_loss.png", "Train / Dev loss"),
            ("dev_pair_f1.png", "Strict-union Pair Macro-F1 theo epoch"),
            ("aspect_f1.png", "F1 theo khía cạnh"),
            ("sentiment_f1.png", "F1 theo sentiment"),
            ("aspect_support.png", "Support theo khía cạnh"),
            ("aspect_sentiment_f1.png", "F1 khía cạnh × sentiment"),
            ("sentiment_confusion.png", "Ma trận nhầm lẫn sentiment"),
            ("threshold_f1.png", "Threshold tối ưu trên Dev"),
        ]
        if evaluation_kind == "dev" else [
            ("dataset_distribution.png","Phân bố aspect trong Train"),
            ("aspect_sentiment_heatmap.png","Khía cạnh × cảm xúc"),
            ("train_dev_loss.png","Train / Dev Loss"),
            ("dev_pair_f1.png","Dev Pair Macro-F1"),
            ("aspect_f1.png","F1 theo khía cạnh"),
            ("sentiment_confusion.png","Ma trận nhầm lẫn sentiment"),
            ("threshold_f1.png","Threshold trên Dev"),
            ("pr_curves_dev.png","Precision–Recall trên Dev"),
            ("model_comparison.png","So sánh mô hình"),
            ("challenge_performance.png","Semantic Challenge"),
            ("learning_curve.png","Learning Curve"),
        ]
    )
    plots=[{"file":name,"title":title} for name,title in plot_names if (eval_dir/"plots"/name).exists()]
    try:
        artifact_rel = artifact_root.resolve().relative_to((ROOT/"model_artifacts").resolve()).as_posix()
    except Exception:
        artifact_rel = "baseline_absa_v0"
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="seller_model_eval.html", context=seller_ctx(
            request, db, metrics=metrics, plots=plots, artifact_rel=artifact_rel,
            artifact_name=artifact_root.name, evaluation_dir_name=eval_dir.name,
            no_evaluation=False, evaluation_kind=evaluation_kind,
            evaluation_metrics=metrics.get("dev", {}) if evaluation_kind == "dev" else metrics.get("test", {}),
            experimental=metrics.get("scientific_final") is not True,
            evaluation_is_balanced=evaluation_kind == "balanced",
            natural_evaluation_available=natural_available,
            balanced_evaluation_available=balanced_available,
        ),
    )

@router.get("/settings")
def seller_settings(request:Request,db:Session=Depends(get_db)):
    if not seller_guard(request,db): return RedirectResponse("/seller/login",status_code=303)
    return request.app.state.templates.TemplateResponse(request=request, name="seller_settings.html", context=seller_ctx(request,db))
