from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nlp.preprocessing.text import normalized_hash_text
from nlp.schema import ASPECTS, SENTIMENTS


def read(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _features(norm: str) -> list[str]:
    tokens = norm.split()
    if len(tokens) < 2:
        return tokens
    return tokens + [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


def _simhash64(norm: str) -> int:
    vec = [0] * 64
    for feature in _features(norm):
        h = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            vec[bit] += 1 if (h >> bit) & 1 else -1
    out = 0
    for bit, value in enumerate(vec):
        if value >= 0:
            out |= 1 << bit
    return out


def _shingles(norm: str) -> set[str]:
    tokens = norm.split()
    if len(tokens) <= 2:
        return set(tokens)
    return {" ".join(tokens[i:i+2]) for i in range(len(tokens) - 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def main() -> None:
    p = argparse.ArgumentParser(description="Validate ABSA split labels and leakage")
    p.add_argument("train", type=Path)
    p.add_argument("dev", type=Path)
    p.add_argument("test", type=Path, nargs="?", help="Held-out Test; omit only with --train-dev-only")
    p.add_argument("--train-dev-only", action="store_true", help="Validate only Train/Dev without opening held-out Test")
    p.add_argument("--near-jaccard", type=float, default=0.90, help="Cross-split near-duplicate bigram-Jaccard threshold after SimHash candidate filtering")
    args = p.parse_args()
    if args.train_dev_only and args.test is not None:
        raise SystemExit("--train-dev-only must not be used with a Test path")
    if not args.train_dev_only and args.test is None:
        raise SystemExit("Test path is required unless --train-dev-only is explicitly set")
    split_names = ["train", "dev"] if args.train_dev_only else ["train", "dev", "test"]
    sets = {k: read(getattr(args, k)) for k in split_names}
    errors: list[str] = []
    hashes: dict[str, tuple[str, str]] = {}

    # Conservative near-duplicate index: with <=3 SimHash bit differences, at
    # least one of four 16-bit bands must be identical. Jaccard verification
    # avoids treating an approximate hash collision as leakage.
    bands: dict[tuple[int, int], list[tuple[str, str, int, set[str], str]]] = defaultdict(list)
    near_pairs: list[dict] = []

    for split, rows in sets.items():
        for r in rows:
            text = str(r.get("text") or "").strip()
            if not text:
                errors.append(f"{split}: empty text {r.get('id')}")
            norm = normalized_hash_text(text)
            h = hashlib.sha256(norm.encode()).hexdigest()
            if h in hashes and hashes[h][0] != split:
                errors.append(f"cross-split duplicate: {r.get('id')} vs {hashes[h][1]}")
            else:
                hashes[h] = (split, str(r.get("id")))

            seen = set()
            for a in r.get("annotations", []):
                if a.get("aspect") not in ASPECTS:
                    errors.append(f"{split}: bad aspect {a}")
                if a.get("sentiment") not in SENTIMENTS:
                    errors.append(f"{split}: bad sentiment {a}")
                if a.get("aspect") in seen:
                    errors.append(f"{split}: duplicate aspect in {r.get('id')}")
                seen.add(a.get("aspect"))

            tokens = norm.split()
            if len(tokens) >= 5:
                sim = _simhash64(norm)
                shingles = _shingles(norm)
                candidates = {}
                for band in range(4):
                    key = (band, (sim >> (band * 16)) & 0xFFFF)
                    for item in bands.get(key, []):
                        candidates[(item[0], item[1])] = item
                for other_split, other_id, other_sim, other_shingles, other_text in candidates.values():
                    if other_split == split:
                        continue
                    if (sim ^ other_sim).bit_count() > 3:
                        continue
                    jac = _jaccard(shingles, other_shingles)
                    if jac >= args.near_jaccard:
                        pair = {
                            "a": f"{other_split}:{other_id}",
                            "b": f"{split}:{r.get('id')}",
                            "jaccard": round(jac, 4),
                            "a_text": other_text[:180],
                            "b_text": text[:180],
                        }
                        near_pairs.append(pair)
                        errors.append(f"cross-split near-duplicate: {pair['a']} vs {pair['b']} (jaccard={pair['jaccard']})")
                for band in range(4):
                    key = (band, (sim >> (band * 16)) & 0xFFFF)
                    bands[key].append((split, str(r.get("id")), sim, shingles, text))

    print(json.dumps({
        "rows": {k: len(v) for k, v in sets.items()},
        "errors": errors[:100],
        "error_count": len(errors),
        "near_duplicate_pairs": near_pairs[:50],
        "near_duplicate_policy": {"simhash_hamming_max": 3, "bigram_jaccard_min": args.near_jaccard, "minimum_tokens": 5},
        "held_out_test_opened": not args.train_dev_only,
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
