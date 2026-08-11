from __future__ import annotations

"""Developer-only behavioral inspection for a frozen Transformer artifact.

This deliberately uses project-authored sentences only.  It has no dataset or
evaluator imports, so it cannot read held-out Test/Challenge data or tune a
model.  Its report is diagnostic evidence, not a scientific evaluation.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.inference.transformer_analyzer import TransformerAnalyzer
from nlp.schema import validate_runtime_result


CASES = [
    ("single_aspect", "Áo bị bung chỉ sau hai lần mặc.", [("product_quality", "negative")], [], "required", []),
    ("single_aspect", "Giao hàng quá chậm.", [("delivery", "negative")], [], "required", []),
    ("single_aspect", "Hộp đóng gói rất chắc chắn.", [("packaging", "positive")], [], "required", []),
    ("single_aspect", "Giá này khá hợp lý.", [("price", "positive")], [], "required", []),
    ("customer_service", "Nhân viên hỗ trợ rất nhiệt tình.", [("customer_service", "positive")], [], "required", []),
    ("negation", "Giao hàng không hề chậm.", [], [("delivery", "negative")], "required", ["không"]),
    ("negation", "Sản phẩm không tệ.", [], [("product_quality", "negative")], "required", ["không"]),
    ("negation", "Mức giá này chưa đến mức quá đắt.", [], [("price", "negative")], "required", ["chưa"]),
    ("contrast", "Sản phẩm đẹp nhưng giao hàng quá lâu.", [("delivery", "negative")], [], "required", ["nhưng"]),
    ("contrast", "Giá hơi cao nhưng chất lượng rất tốt.", [("price", "negative"), ("product_quality", "positive")], [], "required", ["nhưng"]),
    ("contrast", "Hộp bị móp nhưng sản phẩm bên trong vẫn ổn.", [("packaging", "negative")], [], "required", ["nhưng"]),
    ("multi_aspect", "Ship lâu, hộp móp và nhân viên hỗ trợ còn trả lời khó chịu.", [("delivery", "negative"), ("packaging", "negative"), ("customer_service", "negative")], [], "required", []),
    ("multi_aspect", "Sản phẩm tốt, giá ổn nhưng giao hàng hơi chậm.", [("product_quality", "positive"), ("price", "positive"), ("delivery", "negative")], [], "required", ["nhưng"]),
    ("teencode", "sp ok nhưng ship lâu vl", [], [], "diagnostic", ["nhưng"]),
    ("teencode", "cskh rep chậm, nói chuyện khó chịu", [], [], "diagnostic", []),
    ("teencode", "hàng đẹpppp nhưng đóng gói chán", [], [], "diagnostic", ["nhưng"]),
    ("teencode", "shop giao nhanh, sp ổn", [], [], "diagnostic", []),
    ("no_aspect", "abc123", [], [], "required_no_aspect", []),
    ("no_aspect", "hello", [], [], "required_no_aspect", []),
    ("no_aspect", "...", [], [], "required_no_aspect", []),
    ("mixed_subtle", "Không phải hàng tệ, nhưng với giá này thì mình thấy chưa đáng tiền.", [("price", "negative")], [("product_quality", "negative")], "required", ["không", "nhưng", "chưa"]),
    ("mixed_subtle", "Đóng gói đẹp đấy, mở ra thì hộp bên trong móp hết.", [("packaging", "negative")], [], "required", []),
    ("mixed_subtle", "May mà hàng không sao chứ hộp nhìn như bị quăng.", [("packaging", "negative")], [], "required", ["không"]),
    ("customer_service", "Shop rep tin nhắn quá chậm.", [("customer_service", "negative")], [], "diagnostic", []),
    ("customer_service", "CSKH nói chuyện rất khó chịu.", [("customer_service", "negative")], [], "diagnostic", []),
    ("customer_service", "Shop xử lý bảo hành rất nhanh.", [("customer_service", "positive")], [], "diagnostic", []),
    ("customer_service", "Tôi cần shop hỗ trợ đổi size.", [("customer_service", "neutral")], [], "diagnostic", []),
    ("other", "Quà tặng kèm bị thiếu.", [("other", "negative")], [], "diagnostic", []),
    ("other", "Phụ kiện tặng kèm khá hữu ích.", [("other", "positive")], [], "diagnostic", []),
    ("other", "Sản phẩm tặng kèm không đúng như mô tả.", [("other", "negative")], [], "diagnostic", ["không"]),
    ("other", "Voucher tặng kèm không áp dụng được.", [("other", "negative")], [], "diagnostic", ["không"]),
    ("other", "Mình hài lòng với quà tặng kèm.", [("other", "positive")], [], "diagnostic", []),
]


def _classify(case, result: dict, preprocess: dict) -> tuple[str, str | None]:
    category, _text, expected, forbidden, severity, preserve = case
    pairs = {(item["aspect"], item["sentiment"]) for item in result["aspects"]}
    if any(token.casefold() not in preprocess["normalized_text"].casefold() for token in preserve):
        return "FAIL", "preprocessing_bug"
    if severity == "required_no_aspect":
        return ("PASS", None) if result["status"] == "no_aspect" else ("FAIL", "model_weakness")
    mismatched = [pair for pair in expected if pair not in pairs] + [pair for pair in forbidden if pair in pairs]
    if not mismatched:
        return "PASS", None
    return ("WARN", "model_weakness") if severity == "diagnostic" else ("FAIL", "model_weakness")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run project-authored semantic diagnostics against a local frozen Transformer.")
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--vncorenlp-dir", required=True, type=Path)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    analyzer = TransformerAnalyzer(args.artifact, vncorenlp_dir=args.vncorenlp_dir, allow_experimental=True, device=args.device)
    rows = []
    durations = []
    for case in CASES:
        category, text, expected, forbidden, _severity, _preserve = case
        preprocess = analyzer.debug_preprocess(text)
        started = time.perf_counter()
        result = analyzer.analyze(text)
        durations.append(time.perf_counter() - started)
        try:
            validate_runtime_result(result)
            schema_valid = True
        except ValueError as exc:
            schema_valid = False
            result["schema_error"] = str(exc)
        status, classification = _classify(case, result, preprocess)
        if not schema_valid:
            status, classification = "FAIL", "runtime_schema_bug"
        rows.append({
            "category": category,
            "raw_text": text,
            "normalized_text": preprocess["normalized_text"],
            "segmented_text": preprocess["segmented_text"],
            "actual_backend": result.get("backend"),
            "detected_aspects": result.get("aspects", []),
            "aspect_probabilities": result.get("aspect_scores", {}),
            "applied_thresholds": analyzer.thresholds,
            "sentiment_probabilities": result.get("sentiment_scores", {}),
            "schema_valid": schema_valid,
            "expected_semantic_target": {"include": expected, "exclude": forbidden},
            "status": status,
            "classification": classification,
        })
    summary = {state: sum(row["status"] == state for row in rows) for state in ("PASS", "WARN", "FAIL")}
    latency_ms = sorted(value * 1000 for value in durations)
    report = {
        "report_type": "project_authored_runtime_semantic_diagnostic_not_scientific_evaluation",
        "artifact": str(analyzer.artifact_dir),
        "backend": "transformer",
        "device": str(analyzer.device),
        "preprocessing_version": analyzer.preprocessing_version,
        "total": len(rows),
        "summary": summary,
        "latency_ms": {"mean": sum(latency_ms) / len(latency_ms), "median": latency_ms[len(latency_ms) // 2], "p95": latency_ms[max(0, int(len(latency_ms) * .95) - 1)]},
        "cases": rows,
    }
    output = args.output or args.artifact / "runtime_checks" / "semantic_regression.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": summary, "latency_ms": report["latency_ms"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
