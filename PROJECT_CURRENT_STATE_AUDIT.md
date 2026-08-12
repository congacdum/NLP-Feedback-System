# Project Current State Audit

**Audit date:** 2026-08-12  
**Scope:** read-only audit of the working tree, the local SQLite database, the active local HTTP runtime, frozen artifacts, data files, scripts, tests, and `bao_cao_rasa_absa.pdf`.  
**Change boundary:** no report, source, data, model, configuration, or architecture was changed by this audit.

## 1. Executive Summary

The project is currently a FastAPI e-commerce feedback application with a frozen **experimental PhoBERT V5 ABSA** runtime, SQLite persistence, seller analytics derived from persisted ABSA results, and deterministic post-PhoBERT response/evidence enrichment. The local health endpoint responded successfully during this audit at `http://127.0.0.1:8006/health` with `nlp_backend: transformer`; the V5 artifact selected for that runtime is `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/`.

The semantic authority is the PhoBERT multitask model. The evidence/action layer may explain a detected result and compose a customer-facing reply, but it is explicitly filtered by the model output and cannot add or alter an aspect/sentiment. Rasa source exists and can call the same NLP API, but the normal website feedback path does not call Rasa.

The V5 model is technically trained, locally stored, evaluated, and loadable, but is **not scientific-final**. Its own `training_manifest.json` and both evaluation manifests set `scientific_final: false`; V5 Train/Dev/Test rows are marked `is_scientific_gold: false`. The natural held-out experimental Test and the Balanced V2 diagnostic should therefore be reported as experimental evaluation, never as final human-gold evidence.

The report PDF is mostly aligned with the intended architecture and safety boundaries, but it is behind the repository in several material places: it presents V2 as the current technical winner, gives Rasa a more central live role than the website currently uses, lists obsolete/nonexistent operational scripts, includes a nonexistent preview endpoint, and describes Docker handoff more strongly than the present Compose configuration supports.

## 2. Repository Map

| Area | Current role | Evidence |
| --- | --- | --- |
| `app/` | FastAPI app, HTML routes, API routes, services, SQLAlchemy models, templates/static UI. | `app/main.py`, `app/routers/`, `app/services/`, `app/models.py` |
| `nlp/` | Frozen taxonomy, preprocessing, model, training, inference, evaluation, issue extraction. | `nlp/schema.py`, `nlp/training/`, `nlp/inference/`, `nlp/evaluation/` |
| `model_artifacts/` | V1/V2/V5 Transformer artifacts and evaluation outputs. | `model_artifacts/experimental_phobert_absa_*` |
| `nlp/data/` | Demo, mapped, experimental V1/V2, raw candidates, and empty gold placeholders. | `nlp/data/README.md` |
| `rasa_bot/` | Optional Rasa NLU/rules/action-server configuration. | `rasa_bot/config.yml`, `rasa_bot/actions/actions.py` |
| `scripts/` | Dataset preparation, validation, training support, evaluation, runtime diagnostics. | `scripts/*.py` |
| `tests/` | Current automated web/feedback/response-builder tests. | `tests/test_feedback_submission.py`, `tests/test_feedback_ui.py`, `tests/test_response_builder.py` |
| `data/app.db` | Current SQLite application data. | `app/config.py:18`, observed database file |
| `docs/` and root docs | Architecture, data, model and protocol documentation. | `docs/ARCHITECTURE.md`, `docs/MODEL_CARD.md`, `PROJECT_KNOWLEDGE.md` |

## 3. Active Runtime Architecture

Observed runtime path:

```text
Browser / HTML form
  -> FastAPI router
  -> feedback_service.create_feedback
  -> SQLite: persist raw feedback as pending
  -> AnalyzerRegistry (configured TransformerAnalyzer)
  -> normalize -> VnCoreNLP word segmentation -> local PhoBERT V5 inference
  -> runtime schema validation
  -> deterministic evidence/action response enrichment
  -> SQLite: feedback status + one FeedbackAnalysis per aspect
  -> customer response and seller analytics views
```

`app/main.py:16-26` initializes the database and loads the analyzer once during FastAPI lifespan, then mounts static assets and registers auth/web/API/seller routers. `app/services/nlp_service.py:28-65` selects a strict Transformer path when `NLP_BACKEND=transformer`; it fails rather than falling back to demo/rules if the configured artifact cannot load. The active health response was `{"status":"ok","app":"nlp-feedback-system","nlp_backend":"transformer","scientific_runtime":true}`.

The health field name is misleading: `app/main.py:28-31` defines `scientific_runtime` as merely `analyzer.backend == "transformer"`. It does **not** read the artifact's scientific-final flag. The active V5 manifest explicitly says `scientific_final: false` and `experimental_only: true`.

## 4. Actual NLP Pipeline

1. `nlp/preprocessing/text.py:13-26` normalizes NFC/HTML/whitespace and masks URLs, emails and Vietnamese phone numbers while preserving accents, negation, emoji, casing and punctuation.
2. `nlp/preprocessing/segmenter.py:12-20` applies that normalization then VnCoreNLP word segmentation. Train and runtime share this function.
3. `nlp/inference/transformer_analyzer.py:142-190` tokenizes segmented text. Slow PhoBERT tokenization is split into overlapping windows for long feedback; payload length is `max_length - special_tokens`, overlap is capped at 48 tokens.
4. `nlp/models/multitask_transformer.py:22-70` uses `vinai/phobert-base-v2`, its CLS representation, dropout 0.1, a six-logit aspect head, and a six-by-four sentiment head.
5. `nlp/inference/transformer_analyzer.py:192-250` uses sigmoid aspect scores, softmax sentiment scores, max pooling for aspect confidence across windows, weighted sentiment pooling, a cross-window positive/negative conflict rule for `mixed`, and one frozen threshold per aspect. No top-1 aspect is forced; empty selection becomes `no_aspect`.
6. `nlp/schema.py:82-123` rejects invalid output, duplicate aspects, invalid status, and scores outside `[0,1]` before persistence.
7. `app/services/response_builder.py:229-337` adds compatible issue evidence and a Vietnamese reply only after the ABSA decision.

## 5. Actual Taxonomy

The fixed label contract is in `nlp/schema.py:6-28`:

| Aspects | Sentiments |
| --- | --- |
| `product_quality`, `delivery`, `customer_service`, `packaging`, `price`, `other` | `positive`, `neutral`, `negative`, `mixed` |

`no_aspect` is a result status with an empty aspect list, not a seventh aspect (`nlp/schema.py:89-119`). A feedback may have multiple aspects, but `normalize_annotations` collapses multiple labels for the same aspect into one final label, preferring `mixed` for positive-plus-negative conflict (`nlp/schema.py:44-69`). The database additionally enforces one persisted analysis per `(feedback_id, aspect)` in `app/models.py:57-65`.

## 6. Active Data Pipeline

The model V5 artifact identifies its training source as:

```text
Train: nlp/data/experimental_v2/train.jsonl
Dev:   nlp/data/experimental_v2/dev.jsonl
```

Evidence: `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/training_config.json`. The stored SHA-256 values are respectively `e08b8e2206de4b49c0a92dcc5cecd59acef3065659673f1356bb6d9818e0102e` and `1162f2d47b03b42de8d68a3530e31df6b99d3867523db984e9c9e2630f7f1754`, matching the current local files.

`nlp/training/train_transformer.py:150-169` requires a preflight report whose paths, hashes, taxonomy, backbone, maximum length, and weighting policy match exactly. It does not read Test during training. `scripts/check_dataset.py`, `scripts/audit_experimental_data.py`, `scripts/validate_balanced_test.py`, and provenance/data-quality JSON reports are validation/support tools; none makes experimental rows human gold.

## 7. Dataset Inventory

| Dataset | Rows / annotations | Role and status | Evidence |
| --- | ---: | --- | --- |
| `nlp/data/experimental_v2/train.jsonl` | 18,038 / 25,191 | Actual V5 Train; all observed rows `manual_verified=false`, `is_scientific_gold=false`. | file plus V5 `training_config.json` |
| `nlp/data/experimental_v2/dev.jsonl` | 2,205 / 2,936 | Actual V5 Dev; all observed rows non-gold. | file plus V5 `training_config.json` |
| `nlp/data/experimental/test.jsonl` | 2,337 / 2,919 | Natural held-out **experimental** Test used by V5 finalization. Severe aspect imbalance remains: 1,672 product quality, 544 delivery, 390 price, 297 packaging, 10 customer service, 6 other. | `evaluation/evaluation_manifest.json`; file count |
| `nlp/data/raw/test_balanced_v2_candidates.jsonl` | 1,800 / 2,160 | Balanced diagnostic candidate: 360 annotations/aspect; 120 no-aspect rows; all non-gold. | `docs/TEST_BALANCED_V2_PROTOCOL.md`; balanced metrics protocol |
| `nlp/data/experimental/*` | V1 train/dev/test/challenge lineage | Historical experimental data, not V5 Train/Dev. | `nlp/data/experimental/` |
| `nlp/data/demo/*` | Small fixtures | Test/demo only, not scientific evidence. | `nlp/data/README.md` |
| `nlp/data/mapped/*` | Source-mapped intermediate data | Not automatically gold; only four mapped aspects in observed files. | `nlp/data/README.md`, `docs/DATA_SOURCES_AND_MAPPING.md` |
| `nlp/data/gold/` | Empty except `.gitkeep` | No final human-audited gold Train/Dev/Test is bundled. | `nlp/data/gold/.gitkeep` |

The V5 Train aspect occurrences are product quality 11,355; delivery 4,936; price 3,445; packaging 3,091; other 1,458; customer service 906. This improves rare classes relative to V1 but remains an experimental, partially synthetic/AI-assisted track. A separate raw file, `nlp/data/raw/lazada_review_candidates.jsonl`, is malformed JSONL (an unterminated JSON string was found during scan); it is not referenced by V5 training/evaluation but is an ingestion-quality risk.

## 8. Training Pipeline

`nlp/training/train_transformer.py` is the active trainer. It uses deterministic per-epoch loader seeds (`seed + epoch`, line 190), Train-only aspect positive weights and normalized inverse-frequency sentiment weights (lines 104-121), AdamW and linear warmup (lines 292-296), gradient clipping at 1.0 and non-finite checks (lines 337-355), Dev-only threshold tuning (lines 364-367), and best-checkpoint selection by `dev_pair_macro_f1_strict_union` (lines 368-381).

V5 training configuration, from `training_config.json`:

| Parameter | Value |
| --- | --- |
| Backbone | `vinai/phobert-base-v2` |
| Epochs / best epoch | 5 / 5 |
| Batch size | 8 |
| Max length | 256 |
| Learning rate / weight decay | `2e-5` / `0.01` |
| Warmup ratio / patience | `0.1` / `2` |
| Seed / recorded device | `42` / `cuda` |
| Selection metric | Dev strict-union Pair Macro-F1 |

V5 history is persisted in `training_manifest.json`: train loss falls from 1.3791 to 0.1893, while Dev loss reaches its low point at epoch 3 (0.5510) and rises to 0.6225 at epoch 5. The selected Dev strict-union Pair Macro-F1 still rises to 0.8809 at epoch 5. This is a training signal to describe precisely, not proof of catastrophic failure and not a reason to tune on Test.

## 9. Final/Current Model Artifact

**Active observed artifact:** `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/`.

`nlp/inference/transformer_analyzer.py` requires `model.pt`, `thresholds.json`, `training_manifest.json`, `training_config.json`, `tokenizer/`, and `encoder_config/config.json`; all are present. The artifact also contains `last.pt` for resume state, which is not needed by inference. The artifact directory occupies about 2.07 GB including checkpoints and evaluation outputs; `model.pt` is the frozen model state used by runtime.

Frozen V5 thresholds from `thresholds.json` are:

| product_quality | delivery | customer_service | packaging | price | other |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.36 | 0.80 | 0.50 | 0.54 | 0.32 | 0.58 |

Older local artifacts are `experimental_phobert_absa_v1` (best Dev strict-union Pair Macro-F1 0.4662) and `experimental_phobert_absa_v2_repaired` (0.8976). Neither is the currently observed runtime artifact. `model_artifacts/kaggle_phobert_v5/` is an empty directory and not a usable model artifact.

## 10. Evaluation Pipeline

Core metrics are implemented in `nlp/evaluation/metrics.py`:

- Pair Macro-F1 and strict-union Pair Macro-F1 over `aspect#sentiment` pairs.
- Pair Micro-F1 and unseen-gold false-positive count.
- Exact set match per feedback.
- Aspect macro/micro F1 and per-aspect precision/recall/F1/support.
- Conditional sentiment macro F1, per-sentiment scores, per-aspect sentiment F1 and confusion matrix.
- `no_aspect` abstention metric (`compute_no_aspect_metrics`).
- Bootstrap interval support (`bootstrap_pair_macro_f1`) and paired bootstrap comparison support.

`nlp/training/finalize_transformer.py:55-222` evaluates a frozen artifact on Train/Dev/Test paths, writes metrics/predictions/errors/plots, and creates `final_evaluation.lock`. It rejects a scientific-final label when any supplied split has `is_scientific_gold != true`. Its stored natural evaluation manifest records that Test was not used for model selection.

`scripts/evaluate_balanced_transformer.py:57-129` evaluates a frozen artifact separately on a balanced diagnostic set, freezes the existing Dev thresholds, does not retrain, saves errors/predictions/metrics/plots, and explicitly writes `scientific_final: false`.

## 11. Threshold Pipeline

`nlp/evaluation/thresholds.py:11-30` searches each aspect threshold from 0.20 to 0.80 in increments of 0.02 and chooses the first maximum aspect F1 on **Dev only**. Training then reruns Dev prediction with those thresholds and saves `thresholds.json` with the best checkpoint (`nlp/training/train_transformer.py:364-378`). Runtime loads exactly that file (`nlp/inference/transformer_analyzer.py:205-240`).

The threshold chart and PR curves in the natural evaluation are correctly Dev plots, not Test plots: `finalize_transformer.py:201` and `:208-210`. The seller page's natural-Test per-aspect table currently displays `0.00` thresholds because `seller_model_eval.html` reads `metrics.get('thresholds')`, while the natural `evaluation/metrics.json` stores thresholds under neither its root nor `test`; the actual values are in the artifact's `thresholds.json`. This is a UI/reporting defect, not an indication that V5 used zero thresholds.

## 12. FastAPI / Backend

`app/routers/api.py` exposes product listing, feedback submission, direct NLP analysis, and seller summary APIs. `POST /api/feedback` requires a customer session and uses `create_feedback`; `POST /api/nlp/analyze` runs analysis without persistence. `app/routers/web.py` provides customer-facing catalog/product/review pages. `app/routers/seller.py` guards seller pages and reads saved evaluation artifacts rather than running inference on page load.

`app/services/feedback_service.py:16-92` validates product/rating/text, inserts and commits the raw feedback in `pending`, calls NLP, validates the result, builds its response/enrichment, persists `FeedbackAnalysis` rows and final status, or retains the original row as `failed` on exception. This is the actual durable feedback contract.

There is no current `POST /api/feedback/preview` route. The direct `/api/nlp/analyze` route is public by implementation and should be treated as an exposed analysis surface in any deployment/security discussion.

## 13. Rasa

Rasa is present but optional. `docker-compose.yml` places `rasa` and `rasa-actions` under the `rasa` profile; normal `docker compose up` starts only the app. `START_WITH_RASA.bat` trains a Rasa model and starts that optional profile.

`rasa_bot/actions/actions.py:20-48` calls `POST /api/nlp/analyze` and never implements a competing ABSA model. `rasa_bot/config.yml` uses a Vietnamese DIET intent/entity pipeline; `rasa_bot/data/rules.yml` defines dialogue rules. However, no normal FastAPI customer feedback route calls `settings.rasa_url`, and `app/services/feedback_service.py` goes directly to the configured analyzer and response builder. Therefore Rasa is currently available as optional conversational infrastructure, not the website's required feedback-state manager.

## 14. Database

The default database URL is SQLite at `data/app.db` (`app/config.py:18`; `app/db.py:11-25`). The observed database had 2 users, 3,000 products, 19 feedback rows, and 25 `feedback_analysis` rows: 18 feedback rows were `ok`, 1 was `no_aspect`, and all 19 recorded `model_version = experimental_phobert_absa_v5_hard_cases_final`.

Schema evidence (`app/models.py:15-65`):

- `users`: identity, email, password hash, role.
- `products`: catalog metadata and image references.
- `feedback`: user/product/rating/raw text/status/model version/evidence JSON/time.
- `feedback_analysis`: one aspect/sentiment/score record per persisted aspect.

The DB has a rating check constraint and a unique `(feedback_id, aspect)` constraint. Aspect, sentiment and status validity are enforced at the service/runtime layer, not by database enum/check constraints. `app/bootstrap.py:13-37` creates tables, creates demo accounts if none exist, and applies only the additive `issue_details_json` migration.

## 15. Evidence Extraction

`nlp/issue_extraction/pipeline.py` applies rule-based candidate extraction and local negation handling. `app/services/response_builder.py:229-337` filters those candidates using `compatible_issue_details(aspects, candidates)`, maps them to stable issue/action IDs, deduplicates them, and composes a Vietnamese customer reply.

The safety boundary is explicit in the module docstring and in `response_builder.py:12`: the layer consumes already-authorized ABSA predictions, does not call a model, and must not create/change aspects or sentiments. Its output is stored in `Feedback.issue_details_json`; seller analytics reads it as supplemental issue summaries, while main aspect counts come from `FeedbackAnalysis`.

## 16. Frontend / Seller Analytics

Customer pages submit feedback through the FastAPI feedback service and render the server-produced assistant message rather than exposing raw internal labels. Seller pages are role-guarded (`app/routers/seller.py:20-31`) and use persisted SQL data:

- `dashboard_summary`, `aspect_matrix`, `product_analytics`, and `issue_summary` in `app/services/analytics_service.py:14-61` aggregate database rows.
- `/seller/model-evaluation` reads artifact JSON and PNGs only; it does not run model inference (`app/routers/seller.py:64-145`).
- Natural and Balanced V2 evaluation are selectable separately. The page includes warnings for experimental and balanced-diagnostic status in `app/templates/seller_model_eval.html`.

Natural evaluation charts are generated by `finalize_transformer.py`; data distribution, aspect-by-sentiment and feedback-length charts use **Train**, F1/confusion use **Test**, and threshold/PR/history use **Dev**. Balanced charts are generated by `scripts/evaluate_balanced_transformer.py` from the Balanced V2 candidate data. This explains why a page may validly contain both Train and Dev labelled plots alongside Test metrics.

## 17. Docker / Deployment

`Dockerfile` installs `requirements.txt` by default and starts `uvicorn`. `docker-compose.yml` exposes port 8080, persists `./data`, mounts `./model_artifacts` read-only, and has a healthcheck that loads `/health` after lifespan initialization. This healthcheck is meaningful because lifespan attempts to initialize the analyzer.

Current deployment caveats:

1. `requirements.txt` does not include torch, transformers, sentencepiece or py_vncorenlp; Transformer runtime dependencies are in `requirements-transformer-runtime.txt`.
2. Compose exposes `TRANSFORMER_ARTIFACT`, `EVALUATION_ARTIFACT`, and `VNCORENLP_DIR`, but not `ALLOW_EXPERIMENTAL_TRANSFORMER` or `TRANSFORMER_DEVICE`.
3. Compose does not mount a VnCoreNLP resource directory or set Java.
4. Default backend is `demo`, but `model_artifacts/baseline_absa_v0/baseline.joblib` is absent. `app/services/nlp_service.py:59-63` will fail startup in that default mode.
5. `START.bat` starts this default Compose setup. `START_LOCAL_V5.bat` is the intended local V5 launcher, but hard-codes `VNCORENLP_DIR=C:\vncorenlp` and CPU. The observed active local run was separately configured as Transformer runtime.

Consequently, Docker configuration exists but a reproducible V5 Transformer Docker deployment has not been demonstrated by the current files alone.

## 18. Test Suites

Current automated tests are `tests/test_feedback_submission.py`, `tests/test_feedback_ui.py`, and `tests/test_response_builder.py`. This audit executed:

```text
python -m pytest -q -p no:cacheprovider
38 passed in 0.81s
```

Additional runnable diagnostic/support scripts include `scripts/run_transformer_semantic_regression.py`, `scripts/run_transformer_chat_e2e.py`, `scripts/run_feedback_response_scenarios.py`, `scripts/benchmark_runtime.py`, and `scripts/final_project_audit.py`. They are not equivalent to the 38 unit/integration tests. There is no evidence in this audit that Docker Compose, Rasa training, or a full browser E2E suite was rerun for the present V5 state.

## 19. Active vs Legacy Classification

| Item | Classification | Reason |
| --- | --- | --- |
| V5 artifact and `evaluation/` | Active runtime / current experimental evaluation | Observed local Transformer runtime uses V5; current seller page resolves configured artifact. |
| V5 `evaluation_balanced_v2/` | Current supplemental diagnostic | Newly generated separate frozen-model evaluation; not natural Test replacement. |
| V5 `evaluation_dev/` | Development-only artifact | Derived from saved Dev metrics; no held-out Test inference. |
| V1 and V2 artifacts | Legacy/local comparison artifacts | Present, but not observed active runtime. |
| `kaggle_phobert_v5/` | Empty legacy placeholder | Directory has no files. |
| `nlp/data/experimental_v2` | Active V5 Train/Dev data | Hashes match V5 manifest. |
| `nlp/data/experimental/test.jsonl` | Active natural experimental Test | Named in V5 natural evaluation manifest. |
| Balanced V2 candidate | Diagnostic candidate | Explicitly non-gold in data and manifest. |
| `nlp/data/experimental/*`, demo, mapped | Historical/source/fixture data | Not V5 Train/Dev artifact inputs. |
| `rasa_bot/` | Optional, not primary website runtime | Compose profile and no FastAPI feedback call. |
| `README.md`, much of `PROJECT_KNOWLEDGE.md` | Partly stale documentation | Multiple passages say V5 is not trained/local, contradicted by artifact and runtime. |
| `.codex_backups` / `.codex_frontend_backups` / logs | Historical backup/diagnostic material | Not referenced by app runtime. |

## 20. Data / Artifact Provenance

V5 is traceable to Kaggle paths stored in `training_config.json`, exact local dataset hashes, seed 42, model configuration, thresholds, Dev metrics, training history, tokenizer and encoder config. The natural evaluation manifest freezes the observed Train/Dev/Test paths and says `test_used_for_model_selection: false`. The Balanced V2 protocol stores a candidate-file hash `839f4b61158162cc001db7ce8eb8e59624b20f8ac2e9ad708d0364f2c5301e77`, frozen Dev thresholds, no retraining, and false manual/gold flags.

This is good technical reproducibility evidence, but it is not provenance sufficient for scientific-final claims because all active V5 data flags are false and `nlp/data/gold/` is empty. `docs/DATA_SOURCES_AND_MAPPING.md` correctly requires human audit/adjudication before mapped/custom rows become gold.

## 21. Values Requiring Final Training or Evaluation

These values now exist and may be cited only with their exact scope:

| Result | Value | Permitted wording |
| --- | ---: | --- |
| V5 best Dev strict-union Pair Macro-F1 | 0.8809 | Experimental Dev model-selection result. |
| Natural experimental Test strict-union Pair Macro-F1 | 0.5609 | Held-out within the experimental split, not human-gold scientific final. |
| Natural experimental Test Pair Micro-F1 / Aspect Macro-F1 / Sentiment Macro-F1 / Exact Match | 0.8843 / 0.9507 / 0.7745 / 0.8228 | Same natural experimental Test context; explain severe rare-class imbalance. |
| Balanced V2 diagnostic strict-union Pair Macro-F1 | 0.7961 | Candidate, structurally validated but LLM-generated/non-human-verified diagnostic. |
| Balanced V2 bootstrap 95% interval | 0.7780 to 0.8118 | Diagnostic uncertainty interval only. |
| Balanced V2 no-aspect accuracy | 0.625 (75/120) | Diagnostic abstention result, not final test claim. |

A future final result requires a human-verified frozen six-aspect gold Train/Dev/Test protocol, Dev-only checkpoint/threshold selection, fresh frozen artifact evaluation, and explicit scientific-final gate. `finalize_transformer.py:75-87` enforces the gold flag when `--scientific-final` is requested.

## 22. Current Report vs Current Project

The PDF correctly describes the six-aspect ABSA framing, multi-label aspects, four sentiment classes, rating independence, persistence-before-inference, post-model evidence boundary, VnCoreNLP parity, Dev-only threshold intent, and the need to distinguish experimental from scientific claims. These are supported by `nlp/schema.py`, preprocessing/model/inference code, feedback service, and artifact manifests.

The report was committed before the current V5 artifact (`git log` shows report commit `2888877`, while current backend/model integration is later `598ef57`). It should be treated as a strong design/report draft that needs a current-state update, not as proof of all present runtime facts.

## 23. Implemented but Missing From Report

1. A trained and locally active V5 artifact, its exact configuration, hashes, thresholds, history and V5 evaluation outputs.
2. Natural V5 experimental Test metrics and their rare-class imbalance caveat.
3. Balanced Diagnostic V2: equal 360 aspect annotations, 1,800 rows, error summary, no-aspect result and bootstrap interval, with explicit non-gold status.
4. Long-feedback sliding-window inference and cross-window mixed-sentiment aggregation (`transformer_analyzer.py:142-240`).
5. The customer-facing deterministic post-PhoBERT response builder and issue/action IDs; it replaced a required Rasa-led web conversation in normal use.
6. Seller model-evaluation page's separation of natural experimental Test, Dev-derived plots, and Balanced V2 diagnostic.
7. Current database observation: 3,000 products and V5-stamped feedback rows.
8. Current warning that `scientific_runtime` health naming does not equal `scientific_final`.
9. The raw malformed candidate JSONL discovery.

## 24. Report Claims Not Supported By Project

| Report claim/location | Audit finding |
| --- | --- |
| V2 is the current technical winner / V5 is only prepared (not trained/deployed). | Contradicted by V5 artifact, local health runtime and V5 evaluation output. |
| Rasa manages the live website feedback dialogue (PDF pp. 14-15, 23-25, conclusion). | Rasa actions exist, but normal FastAPI feedback service does not call Rasa; it is optional profile infrastructure. |
| `POST /api/feedback/preview` exists (PDF Appendix B, p. 33). | No such route exists in `app/routers/api.py`; direct analysis route is `/api/nlp/analyze`. |
| Operational scripts `RUN_FRESH_SOURCE.bat`, `PUBLISH_DOCKERHUB.bat`, `PACKAGE_FULL_PROJECT.ps1` exist (PDF pp. 27-28). | They are absent. Present launchers are `START.bat`, `START_LOCAL_V5.bat`, `START_WITH_RASA.bat`, and `STOP.bat`. |
| Docker handoff is ready as described. | Compose lacks Transformer dependencies/default baseline artifact, experimental opt-in, Java and mounted VnCoreNLP resource. |
| Table 6 records RTX 4060 Laptop GPU for the relevant V2/V2.1 runs (PDF p. 18). | V5 artifact records only `device: cuda` and Kaggle paths; this audit found no V5 hardware manifest proving that exact GPU. |
| Historical semantic PASS/WARN/FAIL counts should be current final evidence. | They require rerun/version-specific evidence after V5; existing scripts are diagnostics, not automatically V5 final results. |

## 25. Risks / Unverified Items

1. No active dataset is human-verified scientific gold; final scientific claims are unsupported.
2. The natural Test has support 10 for customer service and 6 for other, making per-aspect scores for those classes unstable and unsuitable for strong comparison claims.
3. Balanced V2 eliminates support imbalance but its labels are non-human-verified candidates; it cannot repair the scientific limitation.
4. Dev loss rises after epoch 3 while selection metric rises through epoch 5; report it transparently and avoid post-Test tuning.
5. Current seller natural-Test table renders 0.00 thresholds despite real frozen thresholds. This could confuse a demo or report screenshot.
6. The health endpoint's `scientific_runtime` flag can be misconstrued as scientific validation.
7. Docker default startup is expected to fail in this checkout unless a supported backend/artifact/dependency configuration is supplied.
8. VnCoreNLP and Java are external runtime prerequisites. `segmenter.py:23-53` warns that Windows may require an ASCII-only VnCoreNLP path; these resources are not bundled as a normal Docker mount.
9. The public `/api/nlp/analyze` route has no access-control guard.
10. The raw Lazada candidate file is malformed and should not be consumed without repair/validation.
11. Automated tests passed, but they do not prove Docker/Rasa/full-browser/V5 semantic behavior across all environments.

## 26. What Must Be Changed In The Report Later

1. Replace the “current model” narrative with the exact V5 artifact name and mark it experimental/non-scientific.
2. Add a provenance table for V5 Train/Dev hashes, configuration, Dev selection metric, frozen thresholds, and artifact components.
3. Add a separate results table for natural experimental Test, explicitly listing support per aspect and noting rare-class instability.
4. Add Balanced V2 only as a secondary diagnostic: state generated-candidate status, no retraining, frozen Dev thresholds, and that it does not replace natural Test.
5. Correct Rasa wording: it is optional conversation infrastructure; normal web feedback uses FastAPI plus response builder.
6. Remove/replace the nonexistent preview endpoint and stale operational script names.
7. Describe the actual feedback response pipeline, evidence storage, and seller evaluation behavior.
8. Correct Docker claims to “configuration present, Transformer deployment still requires explicit dependency/Java/VnCoreNLP/environment provisioning.”
9. Rename/qualify health semantics so technical Transformer availability is not conflated with scientific finality.
10. Update or remove historic V1/V2-only metric tables, GPU claims and old diagnostic counts unless their artifact/log evidence is retained and labelled historic.
11. Retain the report's data limitation section, but update it with the actual V5 experimental counts and the empty human-gold directory.

## 27. What Must NOT Be Changed In The Project

1. Do not change the fixed six-aspect/four-sentiment taxonomy merely to make metrics easier.
2. Do not use rating, product metadata, evidence rules, or Rasa to override PhoBERT aspect/sentiment decisions.
3. Do not tune thresholds, choose a checkpoint, or retrain based on either natural Test or Balanced V2 results.
4. Do not call experimental/generated labels human gold or scientific-final.
5. Do not silently replace the active V5 artifact with V1/V2/demo/baseline.
6. Do not reset/delete `data/app.db` or Docker volumes to solve model/runtime issues.
7. Do not remove raw-feedback-first persistence or the unique aspect-per-feedback constraint.
8. Do not alter train/runtime preprocessing parity: normalization -> VnCoreNLP word segmentation -> PhoBERT tokenization.

## 28. Final Project State Summary

At audit time, the project has a functioning local FastAPI Transformer runtime using frozen **experimental PhoBERT V5**, VnCoreNLP preprocessing, valid persisted feedback/analytics flows, post-model evidence and natural-language response enrichment, an optional Rasa implementation, and a seller evaluation UI backed by saved artifacts. The test suite passed 38 tests and the local health endpoint returned 200.

Its strongest technical evidence is reproducible artifact metadata plus experimental Dev, natural Test, and balanced-diagnostic outputs. Its decisive scientific limitation is unchanged: there is no human-verified final gold corpus or scientific-final artifact. The next report revision should align itself to that truth: document V5 accurately, report experimental results with scope and support counts, separate Rasa's optional role from the active web path, and avoid claiming Docker/preview APIs/final evaluation capabilities that the current source does not demonstrate.
