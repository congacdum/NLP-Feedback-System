from __future__ import annotations

"""Materialise a lightweight, balanced Lazada catalog from metadata only.

This command intentionally downloads the five root JSON metadata files, never
the 40GB+ image directories.  Product images remain ``image_path`` values that
the browser resolves directly from Hugging Face at runtime.
"""

import argparse
import concurrent.futures
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
HF_BASE = "https://huggingface.co/datasets/trucmtnguyen/multimodal-product-reviews-lazada/resolve/main/"
FILES = {
    "Mẹ & Bé / Đồ chơi": "babies_toys.json",
    "Điện tử": "electronic.json",
    "Thời trang": "fashion.json",
    "Sức khỏe & Làm đẹp": "health_beauty.json",
    "Nhà cửa & Đời sống": "home_lifestyle.json",
}
PRICE_POINTS = {
    "Mẹ & Bé / Đồ chơi": (49000, 79000, 99000, 119000, 149000, 199000, 249000, 299000, 399000, 499000, 699000, 899000, 1290000),
    "Điện tử": (199000, 299000, 499000, 699000, 899000, 1290000, 1590000, 1990000, 2990000, 3990000, 4990000, 6990000, 8990000, 11990000),
    "Thời trang": (79000, 99000, 119000, 149000, 199000, 249000, 299000, 399000, 499000, 699000, 899000),
    "Sức khỏe & Làm đẹp": (49000, 79000, 99000, 149000, 199000, 249000, 299000, 399000, 499000, 699000, 899000, 1290000, 1499000),
    "Nhà cửa & Đời sống": (59000, 79000, 99000, 149000, 199000, 299000, 399000, 499000, 699000, 899000, 1290000, 1990000, 2990000, 3990000),
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _request(url: str, *, timeout: float, attempts: int = 3, method: str = "GET"):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "NLP-Feedback-System/1.0"})
            return urllib.request.urlopen(req, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"Request failed after {attempts} attempts: {url}") from last_error


def download_json(filename: str, cache_dir: Path, *, timeout: float) -> Any:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / filename
    if not target.exists():
        print(f"Downloading metadata only: {filename}")
        with _request(HF_BASE + filename, timeout=timeout) as response:
            target.write_bytes(response.read())
    return json.loads(target.read_text(encoding="utf-8"))


def iter_product_records(obj: Any) -> Iterable[dict]:
    if isinstance(obj, list):
        for value in obj:
            yield from iter_product_records(value)
    elif isinstance(obj, dict):
        if "product_id" in obj and "product_information" in obj:
            yield obj
        else:
            for value in obj.values():
                yield from iter_product_records(value)


def _clean_image_paths(value: Any) -> list[str]:
    paths: list[str] = []
    for item in value or []:
        if not isinstance(item, str):
            continue
        path = item.strip().lstrip("/")
        if path and path not in paths:
            paths.append(path)
    return paths


def remote_url(image_path: str) -> str:
    return HF_BASE + image_path.lstrip("/")


def deterministic_mock_price(external_id: str, category: str) -> int:
    """Stable e-commerce-like mock price; never an upstream Lazada claim."""
    points = PRICE_POINTS[category]
    digest = hashlib.sha256(f"{external_id}|{category}|nlp-feedback-price-v1".encode("utf-8")).digest()
    return int(points[int.from_bytes(digest[:8], "big") % len(points)])


def validate_image_path(image_path: str, timeout: float) -> bool:
    """Validate a bounded candidate sample without downloading image bytes."""
    try:
        with _request(remote_url(image_path), timeout=timeout, attempts=2, method="HEAD") as response:
            return 200 <= int(getattr(response, "status", response.getcode())) < 400
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a balanced lightweight Lazada catalog without downloading image folders")
    parser.add_argument("--limit", type=int, default=3000, help="Target catalog size (default: 3000)")
    parser.add_argument("--out", type=Path, default=ROOT / "data/lazada_products.json")
    parser.add_argument("--review-out", type=Path, default=ROOT / "nlp/data/raw/lazada_review_candidates.jsonl")
    parser.add_argument("--stats-out", type=Path, default=ROOT / "data/lazada_catalog_stats.json")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/lazada_metadata_cache")
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--validate-images", action="store_true", help="Probe a bounded, representative sample of remote image URLs")
    parser.add_argument("--image-validation-sample", type=int, default=100, help="Maximum image URLs to probe when --validate-images is set")
    parser.add_argument("--image-validation-workers", type=int, default=6)
    parser.add_argument("--allow-missing-images", action="store_true", help="Keep records without image_path (default keeps image-backed catalog only)")
    args = parser.parse_args()
    if args.limit < len(FILES):
        raise SystemExit(f"--limit must be at least {len(FILES)} so every category can be represented")

    products: list[dict] = []
    reviews: list[dict] = []
    selected_ids: set[str] = set()
    target_by_category = {name: args.limit // len(FILES) for name in FILES}
    for name in list(FILES)[: args.limit % len(FILES)]:
        target_by_category[name] += 1

    for category, filename in FILES.items():
        data = download_json(filename, args.cache_dir, timeout=args.timeout)
        count = 0
        for record in iter_product_records(data):
            if count >= target_by_category[category]:
                break
            info = record.get("product_information") or {}
            external_id = str(record.get("product_id") or "").strip()
            if not external_id or external_id in selected_ids:
                continue
            images = _clean_image_paths(info.get("product_images"))
            name = str(info.get("product_info") or "").strip()
            if not name or (not images and not args.allow_missing_images):
                continue
            selected_ids.add(external_id)
            products.append({
                "external_id": external_id,
                "name": name,
                "category": category,
                "price": deterministic_mock_price(external_id, category),
                "price_source": "deterministic_mock_v1_not_lazada_price",
                "description": name,
                "image_path": images[0] if images else None,
                "image_paths": images[:5],
                "source": "trucmtnguyen/multimodal-product-reviews-lazada",
            })
            count += 1
            for review_index, review in enumerate(record.get("reviews") or []):
                comment = review.get("comment") if isinstance(review, dict) else None
                if isinstance(comment, str) and comment.strip():
                    reviews.append({
                        "id": f"lazada_candidate_{external_id}_{review_index}",
                        "product_id": external_id,
                        "category": category,
                        "text": comment.strip(),
                        "source": "lazada_multimodal_2024_raw_candidate",
                        "source_id": str(review.get("review_id") or review_index) if isinstance(review, dict) else str(review_index),
                        "original_labels": [],
                        "mapping_method": "raw_candidate_only",
                        "manual_verified": False,
                        "is_scientific_gold": False,
                    })
        print(f"{category}: selected {count}/{target_by_category[category]}")

    validation: dict[str, Any] = {"requested": bool(args.validate_images), "sampled": 0, "valid": 0, "invalid": 0}
    if args.validate_images:
        by_category: dict[str, list[str]] = {category: [] for category in FILES}
        for row in products:
            if row.get("image_path"):
                by_category[row["category"]].append(row["image_path"])
        candidates: list[str] = []
        # Round-robin selection produces a bounded representative probe rather
        # than checking only the alphabetically first source directory.
        while len(candidates) < args.image_validation_sample and any(by_category.values()):
            for category in FILES:
                if by_category[category] and len(candidates) < args.image_validation_sample:
                    candidates.append(by_category[category].pop(0))
        sample = candidates
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.image_validation_workers, 8))) as pool:
            results = list(pool.map(lambda path: validate_image_path(path, args.timeout), sample))
        validation.update({"sampled": len(sample), "valid": int(sum(results)), "invalid": int(len(sample) - sum(results))})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    args.review_out.parent.mkdir(parents=True, exist_ok=True)
    with args.review_out.open("w", encoding="utf-8") as handle:
        for row in reviews:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {
        "target": args.limit,
        "materialized": len(products),
        "category_counts": dict(Counter(row["category"] for row in products)),
        "products_with_image_path": sum(1 for row in products if row.get("image_path")),
        "products_without_image_path": sum(1 for row in products if not row.get("image_path")),
        "review_candidates": len(reviews),
        "price_policy": "deterministic category-aware mock price for UI/filter/sort only; never upstream Lazada price or NLP feature",
        "price_points": {category: list(points) for category, points in PRICE_POINTS.items()},
        "remote_image_validation": validation,
        "source": "trucmtnguyen/multimodal-product-reviews-lazada",
    }
    args.stats_out.parent.mkdir(parents=True, exist_ok=True)
    args.stats_out.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("No product/review image folder was downloaded. Browsers resolve image_path directly from Hugging Face.")


if __name__ == "__main__":
    main()
