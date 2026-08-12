# NLP Feedback System

Vietnamese Aspect-Based Sentiment Analysis (ABSA) for e-commerce feedback.

The project is a FastAPI, Jinja2, and SQLAlchemy application. Customers submit feedback for a product; the system identifies every relevant business aspect and its sentiment, then stores the analysis for seller analytics. It does not reduce a review to one overall star-like sentiment.

## Current Status

| Item | Current state |
|---|---|
| Application architecture | FastAPI + Jinja2 + SQLAlchemy |
| Canonical taxonomy | 6 aspects and 4 sentiments, frozen |
| Verified local Transformer artifact | experimental_phobert_absa_v2_repaired |
| V2 scientific status | Experimental only; not scientific-final |
| V5 data track | Prepared locally; not yet preflighted or trained |
| V5 Train / Dev | 18,038 / 2,205 rows |
| Held-out Test / Challenge in V3-V5 work | Not read |
| Default .env.example backend | demo |

Important distinction: V2 is the locally verified experimental Transformer runtime. V3 and V4 are Kaggle experiment observations. V5 is the next prepared experiment, not a trained or deployed model.

## What the NLP Produces

One feedback can contain several aspects with different sentiments.

~~~
Input
"Sản phẩm đẹp, giá ổn nhưng giao hàng hơi lâu."

Output meaning
product_quality -> positive
price           -> positive
delivery        -> negative
~~~

| Aspect ID | Vietnamese meaning |
|---|---|
| product_quality | Chất lượng sản phẩm |
| delivery | Giao hàng |
| customer_service | Dịch vụ chăm sóc khách hàng |
| packaging | Đóng gói |
| price | Giá cả |
| other | Nội dung có ý nghĩa nhưng không thuộc năm aspect đầu |

Canonical sentiments are positive, neutral, negative, and mixed.

The other aspect is not noise. A message with no usable e-commerce aspect receives no_aspect; it is not stored as a seventh aspect.

## End-to-End Flow

~~~
Customer product page
    -> submit raw feedback and optional rating
    -> persist raw feedback with status=pending
    -> PhoBERT ABSA inference
    -> validate canonical result schema
    -> optional issue-evidence enrichment
    -> persist one FeedbackAnalysis row per selected aspect
    -> customer acknowledgement and seller analytics
~~~

Raw feedback is committed before inference. If the model fails, the feedback is retained and marked failed. The application does not silently substitute a rule model for a configured Transformer. Seller pages read persisted analysis and do not run inference again while browsing.

The issue-extraction module can explain an already selected aspect, for example delivery -> giao hàng chậm. It cannot add an aspect, change sentiment, or create duplicate core analysis rows.

Rasa resources are retained for optional conversation development. The supported feedback workflow does not depend on Rasa, and PhoBERT remains the ABSA authority.

## Model and Inference Design

The Transformer implementation uses PhoBERT as a shared encoder with two heads:

~~~
PhoBERT encoder
    -> 6 sigmoid outputs for multilabel aspect detection
    -> 6 x 4 outputs for sentiment per aspect
~~~

- Aspect loss: BCE-based multilabel loss.
- Sentiment loss: masked cross entropy, computed only for valid aspect targets.
- Long feedback: overlapping token windows prevent silent tail truncation.
- PhoBERT preprocessing: normalize Vietnamese text -> VnCoreNLP word segmentation -> PhoBERT tokenizer.
- Each aspect receives its own threshold tuned strictly on Dev. An aspect is selected only when aspect_score >= threshold.

The debug utility prints the complete score, threshold, margin, selection, and sentiment table:

~~~powershell
$env:VNCORENLP_DIR = 'C:\vncorenlp'
python scripts/debug_transformer_feedback.py "Sản phẩm đẹp, giá ổn nhưng giao hàng hơi lâu" --artifact model_artifacts/experimental_phobert_absa_v2_repaired --vncorenlp-dir $env:VNCORENLP_DIR --device cpu
~~~

Scores are model confidence-like values, not calibrated real-world probabilities. The threshold is a Dev-tuned selection policy, not a parameter learned directly by the model.

## V2, V3, V4, and V5

### V2 verified experimental runtime

The local artifact is:

~~~
model_artifacts/experimental_phobert_absa_v2_repaired/
~~~

It contains the local model state, tokenizer, encoder configuration, training manifest, Dev metrics, and thresholds. Its best recorded Dev strict-union Pair Macro-F1 is 0.8975828151903416.

V2 is not scientific-final because the data is experimental and the held-out final protocol has not been completed.

### V3 and V4 experimental observations

V3 addressed generic product-quality and other coverage. Its Kaggle console record reported best Dev strict-union Pair Macro-F1 0.8698432855, product-quality Dev F1 0.9748316200, and other Dev F1 0.9911504425.

V4 added customer-service and multi-aspect other coverage. It improved direct customer-service diagnostics, while other remained the most threshold-sensitive aspect in long, complex feedback.

V3 and V4 artifacts are not stored locally. They are Kaggle experiment observations, not local deployment claims or held-out scientific results.

### V5 prepared data revision

V5 expands the working experimental Train split while leaving Dev unchanged.

~~~
Train: 18,038 rows
SHA-256: e08b8e2206de4b49c0a92dcc5cecd59acef3065659673f1356bb6d9818e0102e

Dev: 2,205 rows
SHA-256: 1162f2d47b03b42de8d68a3530e31df6b99d3867523db984e9c9e2630f7f1754
~~~

The V5 track includes:

- 171 added product-quality annotations and 7 corrected product-quality sentiment labels on existing rows.
- 500 other augmentation rows.
- 400 customer-service and 400 multi-aspect other augmentation rows.
- 500 accepted hard-case rows. The remaining 100 rows of the 600-row hard-case source were rejected for meta/instructional wording.

All recent augmentation remains AI-assisted, experimental, non-human-verified, and non-scientific-final. V5 must receive a fresh preflight PASS before training; an earlier V4 preflight cannot authorize it.

## Run the Application

### Local V2 Transformer runtime

Requirements:

- Python environment with requirements-transformer-runtime.txt installed.
- Java available through JAVA_HOME or the portable JRE under .tools/jre21.
- VnCoreNLP directory at C:\vncorenlp containing VnCoreNLP-1.2.jar and models/wordsegmenter.

PowerShell example:

~~~powershell
python -m pip install -r requirements-transformer-runtime.txt

$env:NLP_BACKEND = 'transformer'
$env:TRANSFORMER_ARTIFACT = "$PWD\model_artifacts\experimental_phobert_absa_v2_repaired"
$env:VNCORENLP_DIR = 'C:\vncorenlp'
$env:ALLOW_EXPERIMENTAL_TRANSFORMER = 'true'
$env:TRANSFORMER_DEVICE = 'auto'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_OFFLINE = '1'

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

Open http://127.0.0.1:8000.

Demo credentials created by the bootstrap path:

~~~
Customer: customer@example.com / customer123
Seller:   seller@example.com / seller123
~~~

### Docker and demo-mode caveat

START.bat and docker compose up -d --build start the Docker application stack. However, this working tree currently does not contain model_artifacts/baseline_absa_v0/baseline.joblib, which the default demo backend requires.

Therefore a successful end-to-end demo startup must not be claimed from this checkout unless that baseline artifact is restored or an explicit supported runtime configuration is supplied.

The current docker-compose.yml also does not mount VnCoreNLP or pass ALLOW_EXPERIMENTAL_TRANSFORMER into the container. The local Python command above is the accurate V2 runtime path today. Docker Transformer deployment requires a separately controlled Compose configuration change.

## Train V5 on Kaggle

VnCoreNLP is attached to Kaggle as a separate input directory. Copy the project to /kaggle/working/project before installing dependencies or training.

Expected V5 output locations:

~~~
model_artifacts/preflight_phobert_v5_hard_cases_final/
model_artifacts/experimental_phobert_absa_v5_hard_cases_final/
~~~

Run fresh preflight first:

~~~bash
python -m nlp.training.preflight_transformer \
  --train nlp/data/experimental_v2/train.jsonl \
  --dev nlp/data/experimental_v2/dev.jsonl \
  --vncorenlp-dir "$VNCORENLP_DIR" \
  --output-dir model_artifacts/preflight_phobert_v5_hard_cases_final \
  --cuda-steps 20 \
  --forward-steps 8 \
  --mini-samples 64
~~~

Training is allowed only when:

~~~
overall_preflight = PASS
full_training_allowed = true
~~~

Then run one clean experimental job:

~~~bash
python -m nlp.training.train_transformer \
  --backbone phobert \
  --train nlp/data/experimental_v2/train.jsonl \
  --dev nlp/data/experimental_v2/dev.jsonl \
  --out model_artifacts/experimental_phobert_absa_v5_hard_cases_final \
  --vncorenlp-dir "$VNCORENLP_DIR" \
  --epochs 5 \
  --batch-size 8 \
  --max-length 256 \
  --device cuda \
  --experimental \
  --preflight-report model_artifacts/preflight_phobert_v5_hard_cases_final/preflight_transformer_report.json
~~~

After training, inspect saved Dev metrics, per-aspect thresholds, and fixed multi-aspect diagnostics. Do not tune thresholds manually or use held-out Test to choose V5.

## Evaluation

The primary selection metric is Dev strict-union Pair Macro-F1 over aspect#sentiment pairs. The project also records Pair Micro-F1, aspect F1, conditional sentiment F1, Exact Match, per-aspect metrics, threshold curves, and error slices.

Model selection and threshold tuning use Train/Dev only. Final held-out Test is reserved for a separately authorized scientific protocol after data, architecture, and selection policy are frozen.

To build the Seller Dev Validation dashboard from a frozen artifact without running inference or reading Test:

~~~powershell
python scripts/build_dev_evaluation.py model_artifacts/experimental_phobert_absa_v5_hard_cases_final
~~~

This creates `evaluation_dev/` with metric tables and plots for training history, Dev Pair Macro-F1, aspect and sentiment F1, support, conditional sentiment confusion, aspect-sentiment pair F1, and Dev threshold curves. These results must remain labelled as Dev validation / experimental, not held-out Test results.

## Project Structure

~~~
app/                FastAPI routes, services, templates, persistence
nlp/                schema, preprocessing, models, training, evaluation, inference
data/               SQLite data and catalog-related data
model_artifacts/    model checkpoints, reports, thresholds, audit artifacts
docs/               annotation, provenance, architecture, model documentation
scripts/            data preparation, diagnostics, audits, utility CLIs
rasa_bot/           optional Rasa resources
~~~

## Documentation

Read these before modifying the project:

1. [PROJECT_KNOWLEDGE.md](PROJECT_KNOWLEDGE.md) - architecture, runtime contract, V3-V5 state, and reporting language.
2. [AI_CHANGELOG.md](AI_CHANGELOG.md) - chronological changes, checks, and known boundaries.
3. [Annotation guideline](docs/ANNOTATION_GUIDELINE.md) - aspect and sentiment labeling rules.
4. [Data sources and mapping](docs/DATA_SOURCES_AND_MAPPING.md) - data source and mapping constraints.
5. [Architecture](docs/ARCHITECTURE.md) - module boundaries.
6. [Model card](docs/MODEL_CARD.md) - model claims and limitations.

## Scientific and Reporting Boundary

> The system has a verified experimental PhoBERT V2 runtime and a separate V5 data-improvement experiment in preparation. V5 has not yet been preflighted, trained, deployed, or evaluated on held-out Test data. Recent augmentation is AI-assisted experimental data, not a human-verified scientific-gold corpus.

No paid LLM or API is required for the application, model inference, or training pipeline.
