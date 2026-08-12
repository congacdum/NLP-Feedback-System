# System Architecture

## 1. Design principles

1. NLP output has one canonical schema: aspect-sentiment pairs.
2. The inline feedback assistant gathers rating and text; ABSA handles feedback semantics.
3. Raw feedback is durable before NLP begins.
4. Inference happens once at ingestion; analytics query stored results.
5. Training and runtime are separate pipelines.
6. Test data is held out from model-selection decisions.
7. No paid external inference/storage service is required.
8. UI and seller analytics are presentation layers over real database state, not hard-coded NLP charts.

## 2. Runtime flow

```text
Guest/customer
   │
   ├── browse/search/filter products
   │
   └── authenticated review submit
              │
              ▼
          FastAPI route
              │
              ▼
       create_feedback()
              │
      COMMIT raw feedback
       status = pending
              │
              ▼
       AnalyzerRegistry
       ┌──────┼────────┐
       │      │        │
 final Transformer  bundled baseline  transparent rule fallback
       │      │        │
       └──────┼────────┘
              ▼
       schema validation
              │
              ▼
   FeedbackAnalysis rows
              │
              ▼
       COMMIT analysis
              │
              ├── product rating (rating metadata)
              ├── feedback detail
              ├── aspect matrix
              └── product analytics
```

If inference fails after raw commit, feedback remains and is marked `failed`. If the process dies after raw commit but before recovery code executes, it remains `pending`, which is visible/recoverable instead of lost.

## 3. Database

### `users`

- `id`
- `name`
- `email`
- `password_hash` (scrypt)
- `role`: customer/seller
- `created_at`

### `products`

- `id`
- `external_id`
- `name`
- `category`
- `price`
- `description`
- `image_path`
- `image_url`

### `feedback`

- `id`
- `user_id`
- `product_id`
- `rating` 1–5
- `text_raw`
- `analysis_status`: pending/ok/no_aspect/failed
- `model_version`
- `created_at`

### `feedback_analysis`

One row per detected aspect:

- `feedback_id`
- `aspect`
- `sentiment`
- `aspect_score`
- `sentiment_score`

Unique `(feedback_id, aspect)`.

SQLite foreign keys are explicitly enabled.

## 4. Analyzer selection

`AnalyzerRegistry` loads once per application process.

Order:

1. configured frozen Transformer artifact, when dependencies/artifact exist;
2. bundled TF-IDF demo baseline;
3. deterministic rules if baseline cannot load.

A meaningfulness gate returns `no_aspect` for obvious noise.

The bundled baseline has a narrow `demo_semantic_guard` for deterministic demo correctness. This guard is **not** used in baseline evaluation and is explicitly documented so it cannot be mistaken for learned intelligence.

## 5. Transformer model

Shared encoder:

```text
Vietnamese text
     │
     ▼
PhoBERT or BamiBERT
     │
     ├── 6 sigmoid aspect logits
     │
     └── 6 × 4 sentiment logits
```

Loss:

- aspect: `BCEWithLogitsLoss`, with Train-only positive weights;
- sentiment: masked `CrossEntropyLoss`, only for gold-present aspects;
- joint loss = aspect loss + sentiment loss by default.

PhoBERT raw input is word segmented using VnCoreNLP. BamiBERT accepts raw Vietnamese and supports a longer native context.

Runtime long feedback uses overlapping tokenizer windows rather than silently discarding the tail. Aspect scores are pooled across windows and polarity conflicts across confident windows can aggregate to `mixed`.

## 6. Training protocol

```text
Gold Train ──> weights
Gold Dev ────> checkpoint + thresholds + architecture selection
Gold Test ───> final held-out evaluation only
```

Candidate architecture selection uses mean best Dev Pair Macro-F1 over seeds 42/52/62. Test is not read by `run_bakeoff.py`.

After freezing, `finalize_transformer.py` performs final Test evaluation and creates a lock to discourage repeated Test-driven iteration.

## 7. Evaluation schema

Primary: Pair Macro-F1 over `aspect#sentiment` classes that are present in gold for the evaluation split. Using a gold-defined label denominator keeps the primary macro score comparable across candidate models.

Predicted pair classes that never occur in gold are not ignored: Pair Micro-F1 and Exact Match penalize them, and `pair_macro_f1_strict_union` / `pair_unseen_gold_false_positives` are reported as explicit diagnostics. An all-`no_aspect` slice uses exact set agreement because pair F1 has no positive class there.

Secondary:

- strict-union Pair Macro-F1 diagnostic
- unseen-gold false-positive pair count
- Pair Micro-F1
- Exact Match
- Aspect Macro/Micro-F1
- conditional Sentiment Macro-F1
- per-class metrics
- bootstrap CI
- paired bootstrap delta
- challenge slices

## 8. Rasa

Rasa is retained only for optional conversational development:

- intent classification;
- optional entity extraction;
- rule/dialogue flow;
- custom action calling the same FastAPI `/api/nlp/analyze` endpoint.

Rasa does not contain a duplicate sentiment/topic classifier. It is not part of the customer feedback ingestion path: the floating state-machine chat and its routes are retired. Normal app startup does not require Rasa; `scripts/windows/START_WITH_RASA.bat` trains and launches the optional Rasa profile.

## 9. Product images

Browser fetches remote image URL directly. Backend returns metadata only; it does not proxy image bytes.

UI strategy:

- 20 products per page;
- first visible product images eager/high priority;
- remaining images native lazy loaded;
- async decode;
- image fallback;
- browser cache naturally applies according to upstream HTTP headers.

No Cloudflare/S3/R2/Cloudinary paid dependency.

## 10. UI architecture

Customer:

- Home
- Product Listing
- Product Detail + reviews
- Login/Register
- My Reviews
- Chat widget

Seller:

- Dashboard
- Feedback List
- Feedback Detail
- Aspect Analytics
- Product Analytics
- Model Evaluation
- Settings

Visual language is inspired by the supplied Figma e-commerce template: editorial serif headings, clean sans-serif body, strong whitespace, black/white/off-white neutrals, thin borders, restrained semantic colors. Customer and seller share one design system.

## 11. Trust boundaries

- `/api/products`: public.
- `/api/nlp/analyze`: public analysis endpoint for Rasa/app integration; no persistence.
- `/api/feedback`: authenticated customer.
- `/api/analytics/summary`: seller only.
- seller web routes: seller only.

## 12. Failure behavior

- NLP inference error during review → raw feedback survives and status becomes failed;
- remote product image error → local placeholder;
- no meaningful text → `no_aspect`, no analysis rows;
- invalid analyzer schema → feedback marked failed rather than corrupt analytics.


## Frozen Transformer runtime artifact

A Dev-best Transformer artifact stores `model.pt`, a local tokenizer, `encoder_config/`, thresholds and a training manifest. Runtime instantiates the encoder from the local config and loads the saved state dict, so it does not silently download the pretrained backbone during app startup. Docker can switch from the default lightweight requirements to `requirements-transformer-runtime.txt` through the `REQUIREMENTS_FILE` build argument once a final Transformer exists. PhoBERT still requires local VnCoreNLP resources.
