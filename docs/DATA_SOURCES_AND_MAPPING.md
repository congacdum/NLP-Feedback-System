# Data Sources, Provenance and Mapping Policy

This file prevents a future developer/AI from “merging more data” in a way that silently corrupts the 6-aspect task.

## 1. Product/catalog source

### Lazada Vietnamese Multimodal Product Reviews (2024)

Source: `https://huggingface.co/datasets/trucmtnguyen/multimodal-product-reviews-lazada`

Verified dataset-card facts during the 2026-08 build:

- language: Vietnamese;
- product information contains product images and textual product information;
- user reviews contain review text and optional review images;
- five root groups used here: babies/toys, electronic, fashion, health/beauty, home/lifestyle;
- repository size is about 40.9 GB because of image folders;
- root metadata JSON files are only about 5–6 MB each;
- license shown by the dataset card: `CC BY-NC-ND 4.0`.

Project policy:

- do not redistribute or copy the 40.9 GB image folders into the ZIP;
- `scripts/prepare_lazada_products.py` fetches root metadata only;
- database stores `image_path` and browser resolves the remote Hugging Face URL;
- review images are ignored because this project is text NLP, not multimodal;
- raw review text may be used as a **candidate pool** for human annotation;
- raw Lazada reviews are not ABSA gold labels;
- the public schema used by this project does not document a price field. The catalog therefore assigns a documented **deterministic category-aware mock price** from fixed commercial price points based on `product_id + category`. It is only for UI/filter/sort, is stable across re-imports, and is never a Lazada price or an NLP/evaluation feature.

The bundled `data/demo_products.json` remains an explicit test fixture only. Production catalog reset/import uses `scripts/import_products_to_db.py data/lazada_products.json --reset-catalog-and-feedback` so fixture rows and fixture feedback do not coexist with the Lazada catalog.

## 2. Vietnamese Beauty ABSA source

Repository:

`https://github.com/linh222/Aspect-based-Sentiment-Analysis-for-Vietnamese-Reviews-about-Beauty-Product-on-E-commerce-Websites`

Files fetched on demand:

- `data/data_train.csv`
- `data/data_val.csv`
- `data/data_test.csv`

Observed columns:

```text
data, stayingpower, texture, smell, price, others, colour, shipping, packing
```

Conservative project mapping:

| Source | Project |
|---|---|
| stayingpower | product_quality |
| texture | product_quality |
| smell | product_quality |
| colour | product_quality |
| price | price |
| shipping | delivery |
| packing | packaging |
| others | **do not map to project other** |

When finer labels mapping to `product_quality` contain both positive and negative polarity in one review, aggregate to project `mixed`.

The source `others` field is treated as source-specific spam/noise for this integration, not as semantic project `other`.

Redistribution note: no explicit license file was verified by this build in the repository root. For that reason raw files are **not bundled** in the final ZIP; `scripts/fetch_public_nlp_data.py` downloads them explicitly when the user chooses to use the source. Cite the original paper/repository in academic work and verify current terms before publication/redistribution.

## 3. UIT-ViSD4SA

Repository:

`https://github.com/kimkim00/UIT-ViSD4SA`

Paper: “Span Detection for Aspect-Based Sentiment Analysis in Vietnamese”, PACLIC 2021.

Repository README states:

- 11,122 Vietnamese smartphone feedback comments;
- 35,396 human-annotated spans;
- official Train 7,784 / Dev 1,113 / Test 2,225.

JSONL records contain `text` and span labels such as `ASPECT#SENTIMENT`.

Conservative mapping:

| Source | Project |
|---|---|
| SCREEN | product_quality |
| CAMERA | product_quality |
| FEATURES | product_quality |
| BATTERY | product_quality |
| PERFORMANCE | product_quality |
| STORAGE | product_quality |
| DESIGN | product_quality |
| PRICE | price |
| GENERAL | exclude from auto mapping |
| SER&ACC | manual review by default |

Why `SER&ACC` is not automatically CSKH: the source category mixes service and accessories, so unconditional mapping creates label noise. `scripts/prepare_unified_dataset.py --allow-conservative-seracc` can mine candidate service spans containing clear service terms, but its output still requires human review.

Redistribution note: no explicit license file was verified in the repository root during this build. Raw data is fetched on demand and is not repackaged inside the ZIP.

## 4. ViCloABSA

Reference: Vietnamese Clothing ABSA, PACLIC 2024.

Useful source aspects include MATERIAL, DESIGN, PRICE, SERVICE, GENERAL. `MATERIAL`/`DESIGN` can conceptually contribute to product quality and PRICE to project price. However source `SERVICE` combines service-related concepts that can cross project CSKH and delivery boundaries, so it must not be blindly mapped.

This build **does not auto-download ViCloABSA**, because a stable official machine-readable distribution URL was not verified in the build pipeline. A future developer may add it only after verifying provenance, schema, split and usage terms.

## 5. Project-specific human gold data

Public sources do not cleanly cover the exact six-aspect taxonomy. The final corpus should therefore add approximately 2,500–3,000 project-specific human-verified reviews sampled from Vietnamese e-commerce candidate pools, emphasizing:

- customer_service;
- project `other`;
- mixed sentiment;
- implicit aspect expressions;
- slang/teencode/no accents;
- noisy/no_aspect cases;
- multi-aspect reviews;
- cross-domain products.

AI pre-labeling may be used only to accelerate annotation. It is not ground truth until human-verified.

## 6. Split policy

- Keep official public splits when using a source benchmark for comparable experiments.
- For project-specific Lazada reviews, group by `product_id` before Train/Dev/Test split so reviews of the same product do not leak across splits.
- Deduplicate before splitting.
- Near-duplicate review variants must be audited.
- Test is never used for threshold, checkpoint, feature, taxonomy or hyperparameter selection.

## 7. Unified mapping output is not automatically “gold”

`scripts/prepare_unified_dataset.py` writes `nlp/data/mapped/*.jsonl`. Treat this directory as an **intermediate mapping layer**.

Only after human audit/adjudication should approved frozen files be copied/versioned into `nlp/data/gold/`.

## 8. Rating

Do not derive sentiment labels from star rating. Rating remains separate metadata for product-average display and discrepancy analysis.

A 5-star review may still contain `delivery#negative`, and the NLP model must be able to represent that fact.


## Final gold safety gate

`prepare_unified_dataset.py` marks each mapped public row with `safe_for_auto_gold`. Beauty mappings are deterministic for the supported fields; its upstream `others` spam field is never mapped to project `other`. UIT-ViSD4SA rows containing `GENERAL`, `SER&ACC`, or any unknown upstream aspect are marked `requires_manual_review=true` and `safe_for_auto_gold=false`, even if the same row also contains a safely mapped aspect. This prevents missing unresolved aspects from becoming false-negative labels.

`build_final_gold_dataset.py` is the authoritative assembler. It excludes unsafe mapped rows, accepts custom rows only when explicitly human verified, and refuses cross-split duplicates. `--strict-scientific` additionally checks aspect/core-sentiment coverage before training.
