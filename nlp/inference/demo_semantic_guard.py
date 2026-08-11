from __future__ import annotations

import re
from copy import deepcopy

QUALITY_CUES=("sản phẩm"," sp ","hàng","áo","quần","vải","chất liệu","đường may","màu","form","kích thước","thiết kế","dùng","lỗi","hỏng","bung chỉ")
SERVICE_POS=("tư vấn nhiệt tình","trả lời nhanh","rep nhanh","hỗ trợ nhanh","lịch sự")
SERVICE_NEG=("đổi trả" ,"hoàn tiền","bảo hành","khiếu nại","rep chậm","trả lời chậm","không hỗ trợ")
NEG_DELAY=("chậm","lâu","không giải quyết","không hỗ trợ","quá lâu")


def _upsert(result:dict, aspect:str, sentiment:str, score:float=0.82):
    for item in result.get("aspects",[]):
        if item["aspect"]==aspect:
            item["sentiment"]=sentiment; item["sentiment_score"]=max(float(item.get("sentiment_score",0)),score); return
    result.setdefault("aspects",[]).append({"aspect":aspect,"sentiment":sentiment,"aspect_score":score,"sentiment_score":score})


def apply_demo_semantic_guard(result:dict, text:str)->dict:
    """Small transparent corrections for the runnable baseline demo.

    This is *not* the final scientific model. It prevents a few obvious UX failures
    while the final Transformer awaits the human-verified gold corpus. Evaluation
    artifacts deliberately measure the unguarded baseline so rules cannot inflate
    reported model quality.
    """
    out=deepcopy(result); low=" "+text.casefold()+" "
    # Suppress a common lexical spillover: "đóng gói đẹp" should not become product quality.
    if any(k in low for k in ("đóng gói","gói hàng","bao bì","hộp")) and not any(k in low for k in QUALITY_CUES):
        out["aspects"]=[x for x in out.get("aspects",[]) if x["aspect"]!="product_quality"]
    # Vietnamese negation construction.
    if "không hề tệ" in low or "không tệ" in low:
        if any(x in low for x in ("đáng tiền","giá","rẻ","đắt")):_upsert(out,"price","positive",.86)
        _upsert(out,"product_quality","positive",.78)
    # Mild sarcasm pattern used in challenge/demo: praise + implausibly long delivery.
    if re.search(r"nhanh\s+(?:ghê|quá|thật).{0,25}(?:\d+|mười|cả)\s*(?:ngày|tuần)",low):
        _upsert(out,"delivery","negative",.88)
    # Same-aspect service conflict.
    if any(p in low for p in SERVICE_POS) and any(n in low for n in SERVICE_NEG) and any(d in low for d in NEG_DELAY):
        _upsert(out,"customer_service","mixed",.86)
    # Remove quality spillover when the only clear subject is service.
    if any(x in low for x in ("shop","nhân viên","tư vấn","đổi trả","hoàn tiền")) and not any(k in low for k in QUALITY_CUES):
        out["aspects"]=[x for x in out.get("aspects",[]) if x["aspect"]!="product_quality"]
    out["status"]="ok" if out.get("aspects") else "no_aspect"
    out["backend"]=str(out.get("backend","baseline"))+"+demo_semantic_guard"
    return out
