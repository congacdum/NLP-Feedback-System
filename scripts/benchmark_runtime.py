from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.nlp_service import get_analyzer

CASES = [
    "Áo đẹp nhưng giao hàng quá chậm.",
    "Đóng gói kỹ, ship nhanh nhưng giá hơi cao.",
    "Shop tư vấn nhiệt tình nhưng đổi trả cực chậm.",
    "Đặt từ tuần trước giờ mới tới.",
    "Vải mềm nhưng đường may rất ẩu.",
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    i = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[i]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--out", type=Path, default=ROOT / "model_artifacts/runtime_benchmark.json")
    args = p.parse_args()
    t0 = time.perf_counter()
    analyzer = get_analyzer()
    load_ms = (time.perf_counter() - t0) * 1000
    # warmup
    for text in CASES:
        analyzer.analyze(text)
    times = []
    for _ in range(args.rounds):
        for text in CASES:
            t = time.perf_counter()
            analyzer.analyze(text)
            times.append((time.perf_counter() - t) * 1000)
    result = {
        "backend": analyzer.primary_name,
        "load_ms": load_ms,
        "n": len(times),
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": percentile(times, 0.95),
        "max_ms": max(times),
        "note": "Measured in the current environment; hardware/backend must be recorded when reporting performance.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
