# Balanced Test V2 Protocol

## Purpose

`test_balanced_v2` is a diagnostic test set. It complements, but never replaces,
the natural held-out test set used to estimate deployment performance.

Use it to compare the six aspects fairly, inspect failure modes, and report
macro metrics. Report overall deployment metrics from a separate natural,
held-out gold set.

## Target distribution

The target is 2,160 aspect-sentiment annotations plus 120 feedback records with
no aspect. Counts are annotations, not feedback records: a feedback item can
contain more than one aspect.

| Aspect | positive | negative | neutral | mixed | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `product_quality` | 120 | 120 | 72 | 48 | 360 |
| `delivery` | 120 | 120 | 72 | 48 | 360 |
| `customer_service` | 120 | 120 | 72 | 48 | 360 |
| `packaging` | 120 | 120 | 72 | 48 | 360 |
| `price` | 120 | 120 | 72 | 48 | 360 |
| `other` | 120 | 120 | 72 | 48 | 360 |
| **Total** | **720** | **720** | **432** | **288** | **2,160** |

Aim for 1,820-2,020 feedback records: 70-75% single-aspect records, 25-30%
multi-aspect records, and exactly 120 records with an empty `annotations` list.
The last group checks false positives on generic statements such as order-status
notes that make no quality claim. Do not force a record to have multiple aspects
merely to reduce the file size.

## Required provenance

1. Keep generated candidates in `nlp/data/raw/`; they are not gold data.
2. An annotator checks each candidate against `docs/ANNOTATION_GUIDELINE.md`.
3. A second reviewer adjudicates disagreements before any record is marked as
   `is_scientific_gold: true`.
4. Ensure no exact or near duplicate occurs in Train, Dev, either test set, or
   the challenge set.
5. Never use this test set to select thresholds, choose checkpoints, or retrain
   the model. Those decisions remain Dev-only.

The test set may initially use `is_scientific_gold: false` and
`experimental_only: true`. Change it to gold only after the review gate.

## Recommended reporting

- Natural test: Pair Micro-F1, Exact Match, and a per-aspect table.
- Balanced test: Pair Macro-F1, Aspect Macro-F1, Sentiment Macro-F1, per-aspect
  Precision/Recall/F1, and confusion matrices.
- State that the balanced set is controlled diagnostic evaluation and include
  its label distribution in the report.

## Validation

After producing the JSONL file, run:

```powershell
python scripts/validate_balanced_test.py nlp/data/raw/test_balanced_v2_candidates.jsonl `
  --against nlp/data/experimental_v2/train.jsonl `
  --against nlp/data/experimental_v2/dev.jsonl `
  --against nlp/data/experimental/test.jsonl
```

The command fails on invalid labels, duplicate ids/texts, incorrect quota, or
exact text leakage from the supplied comparison sets.
