# PROJECT_KNOWLEDGE — NLP Feedback System

> **Last reconstructed:** 2026-08-11
> **Purpose:** Source of truth for AI/Codex/developers working on this repository.
>
> This document describes the **current architecture, verified V2 runtime state, and the separate V3-V5 experimental data track**.
>
> Do not assume older documentation, old ZIPs, old Docker images, previous AI conversations, or pre-merge architecture descriptions are still correct.
>
> Before modifying the project:
>
> 1. Read this file.
> 2. Read `AI_CHANGELOG.md`.
> 3. Read relevant audit/evaluation reports.
> 4. Inspect the actual source files affected by the requested change.
> 5. Never infer that an experimental model/result is scientific-final unless its artifact explicitly says so.

---

# 1. PROJECT IDENTITY

## 1.1 Project

**NLP Feedback System**

Course context:

**Tìm hiểu Rasa Chatbot và ứng dụng trong việc xây dựng module phân tích feedback người dùng**

Domain:

**Vietnamese e-commerce / online-shopping customer feedback**

The project is not intended to be merely:

* a rating dashboard;
* a keyword counter;
* a scripted chatbot;
* a topic keyword matcher.

Its NLP core is:

> **Vietnamese multi-aspect Aspect-Based Sentiment Analysis — ABSA**

The system should demonstrate that the text itself is semantically analyzed and can contain:

* multiple aspects;
* different sentiment for different aspects;
* negation;
* contrast;
* positive/negative/mixed opinions;
* feedback with no meaningful e-commerce aspect.

---

# 2. NON-NEGOTIABLE PROJECT SCOPE

This project intentionally keeps its scope focused.

Do **not** add features merely because they are interesting.

A change should normally be implemented only when it:

1. fixes a real current bug;
2. improves NLP/data/training/evaluation quality;
3. improves correctness of the existing customer/seller flow;
4. is required for course delivery/demo;
5. is required to integrate an already-approved project component safely.

Avoid unnecessary architecture rewrites.

Avoid introducing another NLP framework/model that competes with the current ABSA authority unless there is a strong project requirement.

---

# 3. SOURCE-OF-TRUTH PRIORITY

When documentation conflicts, use this priority:

1. **Current source code**
2. **Current model/data artifacts and their manifests**
3. **`AI_CHANGELOG.md`**
4. **Current audit reports**
5. **This `PROJECT_KNOWLEDGE.md`**
6. README / older documentation
7. Old chat history / old ZIPs / assumptions

If source and this file disagree:

> inspect the source, determine the actual behavior, then update both `AI_CHANGELOG.md` and this file if the difference is architectural/current-state relevant.

---

# 4. MANDATORY CHANGE HISTORY RULE

`AI_CHANGELOG.md` is mandatory.

Every significant AI/Codex development phase must append a dated entry containing at minimum:

* goal/scope;
* files changed;
* important implementation decisions;
* tests/checks executed;
* exact PASS/FAIL/NOT_RUN status;
* model/data artifacts touched;
* whether Train/Dev/Test/Challenge were read;
* remaining issues;
* next safe boundary.

Never silently make major project changes without updating the history.

This is necessary so the next AI does not need to audit the entire repository again.

---

# 5. FROZEN NLP TAXONOMY

## 5.1 Six aspects

Exactly six canonical aspects are used:

```text
product_quality
delivery
customer_service
packaging
price
other
```

Vietnamese display meanings:

```text
product_quality    = Chất lượng sản phẩm
delivery           = Giao hàng
customer_service   = Dịch vụ CSKH
packaging          = Đóng gói
price              = Giá cả
other              = Khác
```

All six are real project aspects.

Do not leave dashboard-only dummy categories.

Do not silently remove or rename them without an explicit migration decision.

---

## 5.2 Sentiment classes

Exactly four canonical sentiments:

```text
positive
neutral
negative
mixed
```

`mixed` is meaningful.

Example:

```text
"Áo đẹp nhưng đường may hơi ẩu."
```

may contain different/contrasting evidence and must not automatically collapse into a simple rating-derived label.

---

# 6. `other` VS `no_aspect`

These are **not the same thing**.

## `other`

Meaningful customer feedback that does not belong to the five core business aspects.

## `no_aspect`

Text where no usable project aspect should be emitted.

Examples may include:

* irrelevant text;
* noise;
* messages without meaningful feedback;
* conversational input that requires clarification.

Do not implement `no_aspect` as a seventh dashboard topic.

---

# 7. RATING IS NOT THE NLP MODEL

Rating is metadata.

Rating must remain separate from ABSA prediction.

Do not:

```text
1 star -> negative
5 stars -> positive
```

and call that NLP.

Rating may be displayed or compared against NLP results, but it is not the text model's automatic ground truth.

The key project value is analyzing **what the customer actually wrote**.

---

# 8. CURRENT HIGH-LEVEL ARCHITECTURE

Current main stack:

```text
Customer / Seller UI
        |
        v
FastAPI application
        |
        +--> Product/catalog services
        |
        +--> Chat/feedback services
        |
        +--> NLP runtime analyzer
        |        |
        |        +--> PhoBERT / configured backend
        |        |
        |        +--> ABSA result
        |        |
        |        +--> optional issue_extraction enrichment
        |
        +--> SQLAlchemy persistence
        |
        +--> Seller analytics
```

The application remains fundamentally one FastAPI/Jinja2/SQLAlchemy application.

Do not convert it into unnecessary microservices.

---

# 9. NLP RESPONSIBILITY

The canonical NLP responsibility is:

```text
raw Vietnamese feedback
        ↓
preprocessing
        ↓
Transformer / configured NLP backend
        ↓
aspect detection
        ↓
sentiment per detected aspect
        ↓
schema validation
        ↓
optional evidence/issue enrichment
        ↓
persistence
        ↓
chat response + seller analytics
```

The primary semantic output is an **aspect + sentiment pair set**.

Example:

```text
Input:
"Áo đẹp nhưng giao hơi chậm và hộp bị móp."

Possible ABSA meaning:

product_quality -> positive
delivery        -> negative
packaging       -> negative
```

A single overall sentiment is insufficient for this project.

---

# 10. PHOBERT AUTHORITY AFTER THE DONOR MERGE

This rule is critical.

After merging useful ideas from:

```text
nlp_engine.zip
```

the architecture remains:

> **PhoBERT/ABSA is the authority for aspect and sentiment.**

The donor project does **not** get authority to:

* add a new aspect;
* delete a PhoBERT aspect;
* override an aspect;
* change sentiment;
* alter ABSA persistence;
* replace PhoBERT;
* replace project preprocessing;
* replace the six-aspect taxonomy.

---

# 11. CONTROLLED DONOR MERGE

## 11.1 Donor

Source:

```text
nlp_engine.zip
```

The donor archive had no verified license declaration.

Therefore adapted donor concepts are for internal academic use.

See:

```text
docs/DONOR_FILE_MAP.md
```

for the merge audit.

---

## 11.2 What was NOT copied

The project intentionally did **not blindly copy**:

* donor NLP model;
* donor trained artifact;
* donor classifier;
* donor sentiment engine;
* donor framework;
* donor preprocessing pipeline;
* donor taxonomy;
* donor dataset.

No blind overwrite of the main project was allowed.

---

## 11.3 What was learned/adapted

A useful concept from the donor project was adapted as an isolated module:

```text
nlp/issue_extraction/
```

Its job is to provide more specific:

* issue details;
* evidence descriptions;
* customer-facing explanation.

Example conceptual flow:

```text
PhoBERT:
delivery -> negative

issue extraction:
"giao hàng chậm"
```

The issue extraction result is an **enrichment**, not a replacement prediction.

---

# 12. ISSUE EXTRACTION SAFETY CONTRACT

The issue extraction branch must obey all of the following.

## Rule 1 — filter against ABSA

An issue candidate is allowed only when its parent aspect already exists in the ABSA prediction.

Example:

```text
PhoBERT:
product_quality -> negative

Issue engine candidate:
delivery -> giao chậm
```

Result:

```text
delivery candidate MUST be rejected.
```

The issue engine cannot inject a missing aspect.

---

## Rule 2 — no sentiment authority

Issue extraction does not determine final sentiment.

---

## Rule 3 — no analytics double counting

Multiple issue details for one aspect must not generate duplicate core analysis rows.

Example:

```text
product_quality:
- bung chỉ
- đường may lỗi
```

still represents one ABSA `product_quality` aspect prediction.

---

## Rule 4 — issue failure must not break feedback

If issue extraction throws an exception:

```text
ABSA result + normal feedback persistence must still work.
```

---

## Rule 5 — feature flag rollback

The enrichment can be disabled with:

```text
ISSUE_EXTRACTION_ENABLED=false
```

Disabling it must preserve the original ABSA/persistence route.

---

# 13. CURRENT ISSUE EXTRACTION BEHAVIOR

Current implementation includes conservative handling for examples such as:

```text
giao hàng không hề chậm
hộp không bị móp
giá không quá cao
```

Local negation should prevent a false issue match.

It also includes business phrases such as:

```text
giao
giao hàng
cẩn thận
CSKH không trả lời
```

Category-dependent footwear issues such as:

```text
SOLE_HARD
COMFORT_POOR
```

must require authoritative footwear category context.

Do not apply footwear-specific issues to arbitrary products.

---

# 14. CUSTOMER-FACING CHAT BEHAVIOR

The chatbot should feel like a feedback assistant, not a raw classifier UI.

The customer should normally interact through:

```text
product context
    ↓
feedback conversation
    ↓
feedback confirmation / acknowledgement
    ↓
NLP analysis
    ↓
appropriate natural-language response
```

Internal labels such as:

```text
PRODUCT_QUALITY_NEGATIVE
SOLE_HARD
canonical issue ID
```

should not be exposed directly to customers.

Customer messages should use human-readable Vietnamese.

---

# 15. PRODUCT CONTEXT

Customer feedback flows may be pinned to a product.

Product context must not become an excuse to hallucinate NLP labels.

The product/category can be used only where the feature explicitly requires it, e.g.:

* category-specific issue extraction.

The text model remains responsible for the ABSA meaning.

---

# 16. FEEDBACK PERSISTENCE CONTRACT

Raw customer feedback must be persisted **before** NLP inference.

Required conceptual order:

```text
1. save raw feedback
2. commit
3. run NLP
4. validate NLP schema
5. persist analysis rows
6. update status/respond
```

Reason:

If model inference crashes, customer feedback must not disappear.

A recoverable NLP failure should preserve the feedback row and mark analysis appropriately instead of losing the original text.

---

# 17. ANALYSIS PERSISTENCE

Seller analytics should read stored analysis results.

Do not run the NLP model again whenever the dashboard is opened.

Expected concept:

```text
feedback
    |
    +--> raw text
    |
    +--> analysis rows
           |
           +--> aspect
           +--> sentiment
           +--> score/status as defined
```

Issue extraction details are currently not supposed to redefine the main analytics schema.

---

# 18. DUPLICATE ASPECT PROTECTION

A single feedback should not persist multiple identical core analysis rows for the same Transformer aspect merely because several evidence phrases were extracted.

Conceptually:

```text
one feedback
+
one predicted aspect
=
one unique core aspect analysis row
```

unless the schema is explicitly redesigned later.

---

# 19. RASA'S ROLE

Rasa is optional conversation infrastructure.

Its role is:

```text
intent / conversation flow
        ↓
call the SAME project ABSA API
```

Rasa must not implement a competing business sentiment/topic model.

Rasa may contain a DIET pipeline for conversational intent/entity needs.

That does **not** make DIET the project's main feedback ABSA model.

The main NLP research/model focus remains the ABSA pipeline.

---

# 20. DATASET PROVENANCE — IMPORTANT SCIENTIFIC WARNING

Current experimental data is **not scientific-final gold data**.

Never describe it as:

* fully human verified;
* final research gold;
* scientifically validated dataset.

Historical experimental sources include combinations of:

* Beauty ABSA 2022;
* UIT-ViSD4SA;
* project-authored examples/synthetic data.

Public-source mapping is deliberately conservative.

Unsafe labels should not be automatically mapped merely to increase dataset size.

---

# 21. PUBLIC DATA MAPPING RULES

Existing conservative decisions include:

* Beauty `others` is not automatically equivalent to project `other`;
* UIT `GENERAL` is excluded from automatic mapping;
* UIT `SER&ACC` is not blindly converted without resolving its meaning;
* unknown/unresolved aspects should not silently become negative labels for missing project aspects.

Do not loosen these mapping rules just to inflate training data.

---

# 22. EXPERIMENTAL V1 DATASET

V1 experimental split:

```text
Train:      15,358
Dev:         1,985
Test:        2,337
Challenge:      28
```

The V1 dataset passed the implemented leakage/schema checks used in that experimental phase.

However:

```text
is_scientific_gold = false
```

for the experimental workflow.

---

# 23. V1 CLASS IMBALANCE

V1 had severe sparse-aspect imbalance.

Approximate Train positive aspect counts:

```text
product_quality       10,635
delivery               4,338
customer_service          26
packaging              2,422
price                  2,873
other                     15
```

The raw aspect positive weighting formula is:

```text
negative_count / max(positive_count, 1)
```

This created very large weights for rare classes.

Examples from V1:

```text
customer_service ≈ 589.69
other            ≈ 1022.87
```

Do not mistake this for a divide-by-zero bug.

It is evidence that V1 data was extremely imbalanced.

---

# 24. BASELINE EXPERIMENT

Classical baselines were implemented for comparison.

Important candidates include:

* word + character TF-IDF;
* Logistic Regression;
* LinearSVM;
* transparent rule baseline.

V1 experimental baseline result:

```text
Selected model:
LinearSVM

Dev strict-union Pair Macro-F1:
0.4323665

Test strict-union Pair Macro-F1:
0.3711908

Rule baseline Test strict-union Pair Macro-F1:
0.1917379
```

Artifact:

```text
model_artifacts/experimental_baselines_v1/
```

These are experimental numbers.

Do not present them as scientific-final research results.

---

# 25. PRIMARY MODEL FAMILY

Current Transformer implementation is multitask ABSA.

Candidate backbones include:

```text
vinai/phobert-base-v2
BamiBERT candidate support
```

The project has actually trained PhoBERT V1.

BamiBERT should not be claimed as trained/final unless a real artifact proves it.

---

# 26. TRANSFORMER OUTPUT ARCHITECTURE

The implemented multitask Transformer uses:

```text
shared Transformer encoder
        |
        +--> 6 sigmoid aspect outputs
        |
        +--> sentiment outputs per aspect
```

Sentiment space:

```text
6 aspects × 4 sentiments
```

Loss architecture:

```text
aspect:
BCE-based multilabel loss

sentiment:
masked cross entropy
```

Sentiment loss must only be calculated for valid aspect sentiment targets.

---

# 27. IMPORTANT NaN FIX

An earlier PhoBERT run produced:

```text
train_loss = NaN
dev_loss   = NaN
```

Root cause:

Some batches contained only `no_aspect` samples.

Their sentiment targets were all:

```text
-100
```

Calling mean cross entropy when every target is ignored produced NaN.

The loss was fixed so sentiment CrossEntropy runs only when at least one valid sentiment target exists.

An all-no-aspect sentiment batch returns a proper zero sentiment loss tensor.

The old NaN artifact/run is invalid and must not be resumed or evaluated.

---

# 28. TRANSFORMER SAFETY CHECKS

Training now checks important numerical failures, including:

* non-finite aspect weights;
* non-finite sentiment weights;
* non-finite logits;
* non-finite loss components;
* non-finite total loss;
* non-finite gradients.

Native gradient clipping is used.

Do not reintroduce expensive Python per-parameter gradient scans into every training step.

---

# 29. PRE-FLIGHT TRAINING GATE

Expensive Transformer training is guarded by a preflight system.

A matching PASS report validates things such as:

* exact Train/Dev paths;
* fingerprints;
* taxonomy;
* backbone;
* max length;
* weighting strategy;
* loss edge cases;
* finite forward/backward behavior;
* dataset duplication/leakage checks;
* artifact save/load smoke behavior.

Training should fail closed when required preflight evidence is missing or mismatched.

Never bypass this gate casually.

---

# 30. VNCORENLP

PhoBERT preprocessing uses VnCoreNLP segmentation where configured.

Important Windows issue:

`py_vncorenlp` / JVM loading can fail when model/JAR resources reside under a Unicode-heavy workspace path.

A known working local path in the current Windows environment is:

```text
C:\vncorenlp
```

The directory must contain `VnCoreNLP-1.2.jar` and the `models/wordsegmenter/` resources. A portable Temurin JRE 21 under `.tools/jre21` was used during the 2026-08-11 diagnostic when the host had no system Java. The older path `C:\vncore` appears in historical reports and may work on earlier machines, but it is not the current documented local path.

For Kaggle, VnCoreNLP is attached as a separate read-only input directory. It must not be silently assumed to be embedded in the project archive.

Do not assume moving VnCoreNLP back into an arbitrary Unicode project path will work.

---

# 31. TRAIN/INFERENCE PARITY

Preprocessing used for training and runtime inference must stay compatible.

Cache validity depends on details such as:

* dataset SHA-256;
* split;
* preprocessing/cache version;
* segmenter signature;
* PhoBERT segmented-text mode.

Do not reuse a cache solely because its filename exists.

Cache metadata/signature must match.

---

# 32. TRAINING CACHE

Segmented Train and Dev text can be cached under:

```text
model_artifacts/cache/
```

Cache implementation supports:

* safe invalidation;
* corruption recovery;
* atomic writes;
* signature checking.

Held-out Test must not be casually cached/read by the Train/Dev trainer.

---

# 33. TRAINER CHECKPOINTING

Trainer supports:

```text
--save-every-steps
--resume
```

`last.pt` can include:

* model state;
* optimizer state;
* scheduler state;
* epoch cursor;
* completed batches;
* global step;
* best metric;
* patience;
* history;
* thresholds;
* run configuration;
* Train/Dev fingerprints;
* RNG states.

Resume must reject incompatible configurations.

A checkpoint being technically resume-capable does not automatically mean it is scientifically appropriate to resume.

---

# 34. GPU ENVIRONMENT VERIFIED

Verified training environment:

```text
GPU:
NVIDIA GeForce RTX 4060 Laptop GPU

VRAM:
~8 GB

torch:
2.13.0+cu130

torch CUDA:
13.0

CUDA available:
true
```

A CUDA tensor/matrix operation was successfully executed.

The prior CPU-only PyTorch environment was repaired.

---

# 35. WINDOWS PERFORMANCE FINDING

On this Windows environment, DataLoader multiprocessing was slower.

Measured V2-style bounded benchmark favored approximately:

```text
batch_size = 8
num_workers = 0
```

over worker counts 2 or 4.

Do not increase `num_workers` assuming Linux-like behavior.

Benchmark the actual machine.

---

# 36. PHOBERT V1 FULL TRAINING — COMPLETED

A real clean experimental PhoBERT Train/Dev run was completed.

Backbone:

```text
vinai/phobert-base-v2
```

Protocol:

```text
Train rows:       15,358
Dev rows:          1,985
Batch size:            8
Max length:          256
Learning rate:       2e-5
Weight decay:        0.01
Warmup:              0.1
Seed:                 42
Epochs:              5 / 5
Device:              CUDA
Resume:              NO
```

Run duration:

```text
~42m 20.6s
```

---

# 37. PHOBERT V1 TRAIN HISTORY

Observed history:

```text
Epoch 1
train_loss = 1.681619
dev_loss   = 1.363598
Dev strict-union Pair Macro-F1 = 0.389142

Epoch 2
train_loss = 0.797533
dev_loss   = 0.748034
Dev strict-union Pair Macro-F1 = 0.351275

Epoch 3
train_loss = 0.498290
dev_loss   = 0.793811
Dev strict-union Pair Macro-F1 = 0.456736

Epoch 4
train_loss = 0.375490
dev_loss   = 0.784884
Dev strict-union Pair Macro-F1 = 0.440482

Epoch 5
train_loss = 0.281554
dev_loss   = 0.781453
Dev strict-union Pair Macro-F1 = 0.466208
```

Best epoch:

```text
5
```

Best Dev strict-union Pair Macro-F1:

```text
0.4662078756996796
```

The model completed all five epochs.

No early stop occurred.

---

# 38. PHOBERT V1 ARTIFACT

Experimental V1 Transformer artifact:

```text
model_artifacts/experimental_phobert_absa_v1
```

Dev thresholds were tuned/saved from **Dev only**:

```text
thresholds.json
```

The training run experienced:

```text
no NaN/Inf
no CUDA OOM
non_finite_gradient_count = 0
```

This artifact is:

```text
experimental
```

It is **not scientific-final**.

---

# 39. V1 RUNTIME ACTIVATION

The experimental V1 PhoBERT artifact has been successfully loaded in a real runtime validation using:

```text
NLP_BACKEND=transformer

ALLOW_EXPERIMENTAL_TRANSFORMER=true

TRANSFORMER_ARTIFACT=model_artifacts/experimental_phobert_absa_v1

TRANSFORMER_DEVICE=cuda

ISSUE_EXTRACTION_ENABLED=true
```

Offline Transformer loading was also tested with:

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

The runtime validation proved that the actual backend was:

```text
transformer
```

and did **not** silently fall back to a baseline.

---

# 40. CURRENT EXPERIMENTAL V2 DATASET

A V2 Train/Dev dataset now exists.

Paths:

```text
nlp/data/experimental_v2/train.jsonl
nlp/data/experimental_v2/dev.jsonl
```

Counts:

```text
Train: 16,238
Dev:    2,205
```

Compared with V1:

```text
Train: +880
Dev:   +220
```

No retained V1 rows were removed by the V2 addition process reported in the audit.

---

# 41. V2 DATA PROVENANCE

The V2 additions are:

```text
project_authored_synthetic
```

Added:

```text
880 Train
220 Dev
```

They are not metadata-proven human gold.

Current V2 Train/Dev remain:

```text
is_scientific_gold = false
```

Do not call V2 a scientifically validated corpus.

---

# 42. V2 RARE-ASPECT IMPROVEMENT

V2 substantially reduces rare-aspect sparsity.

Train:

```text
customer_service:
26 -> 366

other:
15 -> 235

packaging:
2422 -> 2622

price:
2873 -> 3033
```

Dev:

```text
customer_service:
6 -> 91

other:
1 -> 56
```

This is materially better than V1, but still does not prove label quality.

---

# 43. V2 SENTIMENT COVERAGE

Example V2 Train distribution:

```text
customer_service:
positive 79
neutral 42
negative 203
mixed 42

other:
positive 72
neutral 36
negative 91
mixed 36
```

All sentiment classes occur for these rare aspects.

However, customer-service remains negative-heavy.

Do not treat mere class presence as proof of good semantic diversity.

---

# 44. V2 CLASS WEIGHT IMPROVEMENT

Using the unchanged raw weighting formula, rare aspect weights improved approximately:

```text
customer_service:
589.69 -> 43.37

other:
1022.87 -> 68.10
```

This is a major numerical improvement over V1.

The weighting formula itself was not changed/clamped merely to force better-looking numbers.

---

# 45. V2 DATA QUALITY CHECKS

The reported V2 readiness audit found:

```text
malformed rows: 0
normalized exact duplicates inside split: 0
exact Train/Dev duplicates: 0
conservative Train/Dev near duplicates: 0
```

Diagnostic project-authored sentences checked against Train/Dev also showed:

```text
exact overlap: 0
conservative near overlap: 0
```

This is leakage/format evidence.

It is not proof that every synthetic label is semantically perfect.

---

# 46. CURRENT V2 TRAINING STATUS — CRITICAL

**V2 has NOT completed a clean final full run.**

A partial V2 checkpoint exists.

Its known state:

```text
batch size: 2
epoch cursor: 4
current cursor batches completed: 143
global step: 24,500
best completed epoch: 3
```

The checkpoint is preserved for provenance/debugging.

It must currently be treated as:

```text
INCOMPLETE
DO NOT RESUME
```

---

# 47. NEXT V2 TRAINING RULE

If V2 full training is started:

> **start clean from pretrained PhoBERT weights.**

Do **not** resume the preserved partial V2 checkpoint.

Recommended verified Windows protocol:

```text
batch_size = 8
num_workers = 0
max_length = 256
matching VnCoreNLP cache/signature
matching PASS preflight
```

Do not change the protocol randomly in the middle of comparative experiments.

---

# 48. HELD-OUT DATA DISCIPLINE

Test is not a tuning split.

Never use Test to:

* choose thresholds;
* tune hyperparameters;
* choose epoch;
* decide model architecture;
* repair training;
* compare endless variants.

Model development belongs on:

```text
Train + Dev
```

Held-out Test should be opened only under the approved evaluation protocol.

Challenge should likewise remain isolated unless that evaluation stage is explicitly authorized.

---

# 49. POST-MERGE INTEGRATION VALIDATION

A dedicated post-merge validation was run with:

```text
real PhoBERT Transformer
+
issue extraction
+
FastAPI product chat
```

Diagnostic script:

```text
scripts/run_merged_issue_validation.py
```

Report:

```text
model_artifacts/experimental_phobert_absa_v1/runtime_checks/merged_issue_validation.json
```

The diagnostic includes:

```text
32 project-authored semantic cases
6 real FastAPI product-chat E2E flows
```

---

# 50. POST-MERGE VALIDATION RESULT

Result:

```text
32 cases

PASS: 23
WARN: 9
FAIL: 0
```

Failure ownership:

```text
PHOBERT          = 9
ISSUE_ENGINE     = 0
RESPONSE_BUILDER = 0
INTEGRATION      = 0
```

This distinction matters.

The controlled donor merge did **not** introduce a known integration failure in this suite.

Remaining warnings belong to the Transformer semantic layer.

---

# 51. RESPONSE QUALITY AFTER MERGE

Comparison:

```text
IMPROVED: 18
SAME:     14
WORSE:     0
```

The improvements came from grounded issue/evidence details.

They did not come from silently overriding PhoBERT aspect/sentiment predictions.

---

# 52. CURRENT PHOBERT SEMANTIC LIMITATIONS

The nine post-merge warnings indicate areas such as:

* positive product-quality recall in contrast sentences;
* subtle packaging language;
* customer-service polarity;
* customer-service multi-aspect recall.

This means the next major NLP improvement belongs primarily in:

```text
data quality
+
PhoBERT V2 training/evaluation
```

not in allowing issue extraction to override the Transformer.

Do not “fix” PhoBERT misses by injecting rule-based aspects into analytics.

That would hide the model weakness instead of solving it.

---

# 53. ISSUE ENGINE CURRENT STATUS

Post-merge tests indicate that the current issue layer:

* respects predicted aspects;
* handles local negation conservatively;
* does not inject unauthorized aspect rows;
* does not double count the same core aspect;
* degrades safely on exception;
* can be disabled cleanly.

Measured issue-only overhead was extremely small relative to Transformer inference, so it is not currently a performance concern.

Do not prematurely optimize it at the expense of correctness.

---

# 54. CURRENT NLP PRIORITY

The highest-value NLP priority is now:

> **clean PhoBERT V2 training and evaluation**

rather than another architecture merge.

Reasons:

1. V1 Transformer works end-to-end.
2. The issue merge works as an enrichment layer.
3. Post-merge failures are owned by PhoBERT semantics.
4. V2 data substantially improves rare-aspect coverage.
5. The existing partial V2 run is not valid for continuation.
6. A clean V2 experiment is the proper next comparison.

---

# 55. PRODUCT CATALOG

The project uses a Vietnamese Lazada-oriented catalog.

Materialized metadata target:

```text
3,000 products
```

The project deliberately does not bundle the huge Lazada image tree.

Product image metadata/remote paths are used where available.

Local fallback exists for missing images.

---

# 56. CATALOG CATEGORY BALANCE

A prepared catalog has been built with approximately:

```text
3,000 unique products
600 products × 5 categories
```

Remote image paths existed for most products.

The ~40 GB image dataset is not meant to be copied into the repository.

---

# 57. PRODUCT PRICE POLICY

The verified Lazada metadata source used by this project did not provide a trustworthy documented price field for the desired catalog workflow.

For demo/catalog functionality, deterministic mock prices were introduced.

These prices are:

* deterministic;
* category-aware;
* stable from product identity/version;
* usable for filtering/sorting/demo.

They are **not real Lazada prices**.

Never present them as scraped or verified marketplace prices.

They must never be used as NLP features or ground truth.

---

# 58. CATALOG RESET STATE

A catalog reset phase created:

```text
3,000 products
0 duplicate external IDs
0 missing/non-positive mock prices
```

At reset time old feedback/analysis rows were cleared as part of the approved catalog refresh.

Do not assume later test/diagnostic databases have the same row counts without inspecting the current DB.

---

# 59. PRODUCT PAGINATION

Expected catalog behavior:

```text
20 products per page
```

For 3,000 products:

```text
150 pages
```

Pagination hardening includes:

* page clamping;
* invalid page handling;
* filter preservation;
* blank filter normalization;
* image fallback.

Known regression coverage has included pages such as:

```text
1
2
3
10
50
149
150
```

Do not reintroduce the old page-2+ blank/black-page bug.

---

# 60. NUMERIC FILTER HANDLING

Blank HTML values such as:

```text
min_price=
max_price=
min_rating=
```

must not produce FastAPI `422`.

Web/API routes normalize optional numeric values before catalog querying.

Keep blank/malformed optional filters safe.

---

# 61. SELLER ANALYTICS

Seller analytics should derive from saved NLP analysis rows.

Required conceptual coverage includes all six aspects:

```text
Chất lượng SP
Giao hàng
Dịch vụ CSKH
Đóng gói
Giá cả
Khác
```

Dashboard labels must correspond to actual functional data flows.

Do not show six categories while only implementing three.

---

# 62. MODEL EVALUATION SCREEN

Model Evaluation is a first-class seller/admin feature.

It should present actual configured evaluation artifacts.

Experimental results must be marked clearly.

Scientific-final results must be fail-closed:

If no valid final artifact exists, the UI should say there is no final evaluated model rather than substituting demo numbers.

---

# 63. SCIENTIFIC FINAL ARTIFACT RULE

An artifact must not be called scientific-final merely because:

* training finished;
* F1 is high;
* it uses PhoBERT;
* it has a model file.

Scientific-final gating requires valid provenance and the explicit project contract.

Current V1 and V2 experimental workflows are not scientific-final.

---

# 64. EVALUATION METRICS

Important implemented metrics include:

```text
Pair Macro-F1
Pair Micro-F1
Exact Match
Aspect Macro-F1
Aspect Micro-F1
Conditional Sentiment Macro-F1
per-class metrics
bootstrap confidence intervals
paired bootstrap comparisons
challenge-slice metrics
```

The main development/model-selection metric currently emphasized is:

```text
strict-union Pair Macro-F1
```

This penalizes hallucinated aspect-sentiment pair classes more appropriately than a metric that only considers classes present in gold.

---

# 65. REQUIRED VISUAL EVALUATION SUPPORT

Evaluation tooling may include plots such as:

* dataset distribution;
* aspect × sentiment heatmap;
* review length;
* per-aspect F1;
* sentiment confusion matrix;
* Dev threshold curves;
* PR curves;
* model comparison;
* semantic challenge comparison;
* learning curve;
* Transformer train/dev history.

These are evaluation outputs, not decorations.

Do not fabricate plots from fake metrics.

---

# 66. BASELINE VS TRANSFORMER

The project should be explainable experimentally as:

```text
Rule baseline
        ↓ comparison

Classical ML baseline
TF-IDF + LinearSVM / Logistic Regression
        ↓ comparison

Transformer
PhoBERT multitask ABSA
```

This makes the NLP contribution visible.

Do not remove the baselines simply because Transformer is more modern.

They provide evidence that semantic modeling improves over simpler alternatives.

---

# 67. RUNTIME BACKEND MODES

Known conceptual backend modes include:

```text
demo
baseline
transformer
```

Do not use ambiguous obsolete values such as `auto` unless current source explicitly supports them.

A previous stale `NLP_BACKEND=auto` configuration prevented runtime tests and was corrected.

When `transformer` is selected, a missing/broken artifact should fail clearly rather than silently presenting a fake “Transformer” runtime backed by something else.

---

# 68. EXPERIMENTAL TRANSFORMER GATE

Loading an experimental Transformer requires explicit opt-in.

Known configuration concept:

```text
ALLOW_EXPERIMENTAL_TRANSFORMER=true
```

This prevents an experimental artifact from accidentally masquerading as production/scientific-final.

Preserve this fail-closed behavior.

---

# 69. OFFLINE TRANSFORMER RUNTIME

Transformer artifacts are designed to save sufficient local model/tokenizer/config state for offline loading.

Runtime should not silently require a fresh Hugging Face backbone download when a properly packaged artifact is used.

Offline validation has been explicitly exercised.

---

# 70. SECURITY / SESSION NOTES

The application includes basic security hardening such as:

* password hashing;
* signed sessions;
* role separation;
* seller-only analytics routes;
* redirect safety checks.

Do not weaken role checks while changing UI/API flows.

---

# 71. CUSTOMER AND SELLER ROLES

Main roles:

```text
customer/user
seller/admin
```

Avoid reintroducing unnecessary Staff/Admin role complexity unless the project explicitly requires it.

Customer and seller views have different responsibilities.

---

# 72. UI STYLE

Current desired visual direction:

> modern, simple, premium, e-commerce, not overly colorful

Customer and seller UI should share a coherent design language.

Typography/layout issues should be treated as actual UI bugs when they reduce readability, e.g.:

* cut-off headings;
* broken cards;
* black/blank pagination screens;
* inconsistent font stack.

Do not perform large decorative redesigns during NLP training/evaluation work.

---

# 73. DOCKER DELIVERY MODEL

Project delivery is designed to support simple Windows/Docker use.

The intended concept is:

```text
manual Docker/Compose startup
+
one-click batch launcher
```

Existing scripts should remain purpose-separated.

---

# 74. START SCRIPT RESPONSIBILITY

`START.bat` / current equivalent startup launcher should:

* start the packaged/current application;
* not unexpectedly publish images;
* not retrain models;
* not reset user data unless explicitly designed/documented.

---

# 75. FRESH SOURCE SCRIPT RESPONSIBILITY

A fresh-source launcher/build workflow is intended to:

* build current source;
* avoid accidentally using stale old Docker Hub code;
* recreate the current-source application;
* preserve separation from publishing.

Do not combine everything into one destructive script.

---

# 76. DOCKER HUB PUBLISH RESPONSIBILITY

`PUBLISH_DOCKERHUB.bat` is intended only for publishing/tagging an already-built image.

It must not secretly become:

* the normal START script;
* a training script;
* a database reset script.

Keep responsibilities separated.

---

# 77. DATABASE/VOLUME SAFETY

Do not casually delete Docker volumes/database as a generic “fix cache” solution.

Source/image cache and persistent application data are different things.

Explicit data resets must only happen when the task specifically authorizes a reset.

---

# 78. TESTING PHILOSOPHY

Do not state “fixed” only because code compiles.

Use the strongest available evidence:

```text
compile
↓
unit tests
↓
integration tests
↓
runtime validation
↓
browser/E2E validation where relevant
```

When a level is not run, say:

```text
NOT_RUN
```

Never convert “could not test” into PASS.

---

# 79. CURRENT POST-MERGE TEST EVIDENCE

The controlled donor merge itself was followed by focused tests.

Known evidence includes:

```text
compile PASS
forbidden donor import scan PASS
focused merge-related tests PASS
```

Post-merge real Transformer + issue validation later reported:

```text
25 passed
```

for the focused no-held-out suite during that phase.

Do not interpret this as “the entire repository can never have another failing test.”

Always rerun tests relevant to the new change.

---

# 80. DONOR IMPORT PROHIBITION

Do not later “simplify” the merge by directly importing donor modules/models.

The controlled integration deliberately avoided donor framework/source/model coupling.

`nlp/issue_extraction/` is the project-owned adapted implementation.

Preserve this isolation.

---

# 81. THINGS THAT MUST NOT HAPPEN

Future AI/developers must not:

1. Replace PhoBERT aspect/sentiment with donor rules without explicit approval.
2. Let issue extraction inject new analytics aspects.
3. Label experimental data/model as scientific-final.
4. Tune on held-out Test.
5. Resume the incomplete V2 checkpoint.
6. Change taxonomy casually.
7. Derive NLP sentiment from rating.
8. Use mock price as real Lazada price.
9. Re-download the huge Lazada image repository into the project.
10. Blindly overwrite files from another project during merge.
11. Reset database/volumes merely to solve Docker cache.
12. Add unnecessary features outside the approved project scope.
13. Hide Transformer weaknesses behind hand-written rules.
14. Invent metrics, artifacts, successful tests, or Docker runtime evidence.
15. Silently alter preprocessing between training and inference.

---

# 82. CURRENT VERIFIED MODEL STATE

At the time this Knowledge file was reconstructed:

## Baseline

```text
Experimental baseline exists.
LinearSVM has experimental Test metrics.
```

## PhoBERT V1

```text
TRAINED: YES
5/5 epochs completed
Best Dev strict-union Pair Macro-F1 ≈ 0.466208
Artifact exists:
model_artifacts/experimental_phobert_absa_v1

Status:
experimental
not scientific-final
```

## PhoBERT V2

```text
Dataset prepared/readiness audited: YES

Clean full run completed:
NO

Partial checkpoint exists:
YES

Partial checkpoint allowed for resume:
NO
```

## BamiBERT

```text
Supported/candidate in architecture.

Do not claim current final trained BamiBERT artifact
without inspecting real artifact evidence.
```

---

# 83. CURRENT VERIFIED MERGE STATE

Donor merge:

```text
DONE
```

Type:

```text
controlled / selective adaptation
```

Added core concept:

```text
nlp/issue_extraction/
```

ABSA authority:

```text
PhoBERT unchanged
```

Post-merge integration failures:

```text
0 known FAIL in the 32-case validation
```

Remaining warnings:

```text
9
```

Ownership:

```text
PhoBERT semantic/model quality
```

---

# 84. CURRENT VERIFIED CATALOG STATE

Target/materialized catalog:

```text
3,000 Lazada-derived product metadata rows
```

Pagination:

```text
20/page
~150 pages
```

Price:

```text
deterministic mock/demo price
NOT verified Lazada price
```

Images:

```text
remote metadata/path where available
local fallback where unavailable
no ~40 GB image tree bundled
```

---

# 85. CURRENT PRIMARY NEXT STEP

The safest next major NLP step is:

> **Train PhoBERT V2 cleanly from pretrained weights using the audited V2 Train/Dev data.**

Do not resume the previous partial V2 checkpoint.

Suggested already-benchmarked Windows execution profile:

```text
batch_size = 8
num_workers = 0
max_length = 256
CUDA
matching VnCoreNLP setup
matching PASS preflight
```

After training:

1. inspect Train/Dev history;
2. compare V2 Dev strict-union Pair Macro-F1 with V1;
3. inspect per-aspect performance, especially:

   * customer_service;
   * other;
   * packaging;
   * contrast/multi-aspect behavior;
4. run semantic diagnostic cases;
5. do not open/tune on held-out Test prematurely;
6. only move toward final evaluation once the protocol is frozen.

---

# 86. WHY V2 TRAINING MATTERS

The current post-merge architecture already works.

The main remaining weakness is semantic model quality.

V1 rare-aspect counts were extremely low.

V2 materially increases:

```text
customer_service
other
multi-aspect examples
mixed sentiment coverage
contrast/negation examples
```

Therefore V2 training is a more legitimate next improvement than adding another rule engine.

---

# 87. WHAT TO CHECK AFTER V2

Do not judge V2 only by one global number.

Compare at minimum:

```text
V1 vs V2 Dev strict-union Pair Macro-F1
per-aspect F1
customer_service recall/F1
other recall/F1
packaging behavior
sentiment Macro-F1
multi-aspect exact behavior
contrast sentences
negation sentences
no_aspect false positives
```

A higher global score that destroys a rare aspect is not automatically a better project model.

---

# 88. PROJECT DEMO NARRATIVE

The project should be explainable to a lecturer approximately like this:

```text
Khách hàng viết feedback tự nhiên
        ↓
PhoBERT hiểu nội dung
        ↓
phát hiện nhiều khía cạnh
        ↓
đánh giá cảm xúc riêng cho từng khía cạnh
        ↓
issue extraction giải thích chi tiết hơn
nhưng không thay đổi quyết định của model
        ↓
feedback + kết quả NLP được lưu
        ↓
chatbot phản hồi theo ngữ cảnh
        ↓
seller xem thống kê theo 6 khía cạnh
        ↓
Model Evaluation chứng minh chất lượng NLP
```

This is the central story.

---

# 89. EXAMPLE OF THE INTENDED NLP VALUE

Input:

```text
"Áo mặc đẹp nhưng giao chậm, hộp hơi móp và giá khá cao."
```

The system should conceptually understand:

```text
product_quality -> positive
delivery        -> negative
packaging       -> negative
price           -> negative
```

Possible enrichment:

```text
delivery:
giao chậm

packaging:
hộp móp

price:
giá cao
```

The enrichment must not create a new aspect unless PhoBERT already detected that aspect.

This example demonstrates why simple rating or one-label sentiment analysis is insufficient.

---

# 90. EXAMPLE OF NEGATION SAFETY

Input:

```text
"Giao hàng không hề chậm."
```

A simplistic keyword engine might see:

```text
"chậm"
```

and incorrectly flag delivery-negative.

The system should account for negation.

Likewise:

```text
"Hộp không bị móp."
"Giá không quá cao."
```

should not become complaints merely because keywords such as `móp` or `cao` exist.

This is one reason semantic NLP matters in the project.

---

# 91. EXAMPLE OF CONTRAST

Input:

```text
"Sản phẩm đẹp nhưng nhân viên hỗ trợ quá chậm."
```

Possible expected meaning:

```text
product_quality   -> positive
customer_service  -> negative
```

One global sentiment label loses important information.

The ABSA architecture exists specifically to solve this.

---

# 92. KNOWN SCIENTIFIC LIMITATION

Even after V2 data expansion, current experimental data is not equivalent to a fully human-adjudicated final corpus.

For academic reporting, distinguish between:

```text
engineering experiment
```

and:

```text
scientific final evaluation
```

Never overclaim.

A transparent experimental result is stronger than a fake “95% accurate” final claim.

---

# 93. FUTURE HUMAN-GOLD PATH

If the project later pursues scientific-final status, the intended path remains conceptually:

```text
annotation guideline
↓
human annotation
↓
agreement measurement
↓
adjudication
↓
strict gold assembly
↓
Train / Dev / Test separation
↓
model selection on Dev
↓
single frozen held-out evaluation
```

Existing annotation/data scripts may support this workflow.

Do not replace human gold with AI pseudo-labels and then call it human-verified.

---

# 94. IMPORTANT FILES / DIRECTORIES

Typical important areas:

```text
app/
    FastAPI routes/services/config/UI/backend

nlp/
    schema
    preprocessing
    models
    runtime
    training
    evaluation
    issue_extraction

nlp/issue_extraction/
    controlled post-merge enrichment

nlp/data/experimental/
    V1 experimental data

nlp/data/experimental_v2/
    V2 Train/Dev data

model_artifacts/
    baseline
    Transformer artifacts
    cache
    preflight/runtime reports

scripts/
    dataset/catalog/training/audit/validation utilities

rasa_bot/
    optional Rasa conversational integration

docs/
    architecture/data/annotation/model/merge documentation

AI_CHANGELOG.md
    chronological implementation truth

PROJECT_KNOWLEDGE.md
    current-state project knowledge
```

Always inspect exact current filenames before scripting against them.

---

# 95. IMPORTANT CURRENT ARTIFACTS

Known relevant artifacts/reports include:

```text
model_artifacts/experimental_baselines_v1/

model_artifacts/experimental_phobert_absa_v1/

model_artifacts/preflight_transformer_report.json

model_artifacts/preflight_transformer_report.md

model_artifacts/v2_readiness_audit.json

model_artifacts/experimental_phobert_absa_v1/runtime_checks/
    merged_issue_validation.json
```

Do not delete model artifacts casually.

Some are needed for provenance, comparison, or runtime validation.

---

# 96. MODEL ARTIFACT HYGIENE

Before activating any Transformer artifact, inspect:

* manifest;
* scientific/experimental status;
* taxonomy;
* backbone;
* thresholds;
* preprocessing contract;
* saved tokenizer/config;
* expected runtime backend;
* dataset fingerprints if relevant.

Do not point `TRANSFORMER_ARTIFACT` at an arbitrary folder because it contains `.pt` files.

---

# 97. WHEN MODIFYING TRAINING CODE

Training-code changes are high-risk.

Before a long run:

1. compile affected files;
2. run focused tests;
3. validate loss edge cases;
4. validate cache compatibility;
5. run/update preflight;
6. perform bounded CUDA smoke/benchmark when appropriate;
7. confirm Train/Dev paths;
8. confirm held-out Test is not accidentally read;
9. only then launch full training.

A 2-hour failed run because of a preventable startup bug is unacceptable.

---

# 98. WHEN MODIFYING MERGED ISSUE CODE

Any change to:

```text
nlp/issue_extraction/
```

must re-test at least:

* aspect authorization boundary;
* negation;
* multiple details for one aspect;
* category-bound issues;
* exception fallback;
* `ISSUE_EXTRACTION_ENABLED=false`;
* persistence uniqueness;
* response text;
* no donor forbidden imports.

Issue rules must never become a hidden secondary classifier.

---

# 99. WHEN MODIFYING CATALOG/UI

Do not touch NLP/training merely to repair:

* pagination;
* CSS;
* fonts;
* product cards;
* numeric query parsing;
* image fallback.

Keep scopes isolated.

Likewise, do not redesign UI during a model-training bug fix unless explicitly required.

---

# 100. WHEN MODIFYING NLP

Do not reset:

* product database;
* catalog;
* Docker volumes;
* UI;
* seller data;

just because a model/training task is being performed.

NLP development and application data lifecycle are separate concerns.

---

# 101. DEFINITION OF "DONE"

A future AI must not say a task is done merely because code was written.

Use evidence appropriate to the task.

Examples:

## Source bug

```text
code changed
+
regression test PASS
```

## Runtime bug

```text
source test PASS
+
real runtime reproduction now PASS
```

## Model training

```text
run completed
+
artifact saved
+
history/metric inspected
+
fresh-process load works
```

## Merge

```text
integration tests
+
boundary tests
+
real runtime flow
+
no forbidden coupling
```

---

# 102. CURRENT PROJECT SNAPSHOT

As of this reconstructed knowledge state:

```text
Core ABSA architecture:
IMPLEMENTED

6-aspect taxonomy:
ACTIVE

4 sentiments:
ACTIVE

FastAPI application:
IMPLEMENTED

Customer/seller flows:
IMPLEMENTED

3,000-product catalog:
IMPLEMENTED

Pagination/filtering hardening:
IMPLEMENTED

Classical baseline:
TRAINED EXPERIMENTALLY

PhoBERT V1:
TRAINED EXPERIMENTALLY

PhoBERT V1 runtime:
REAL TRANSFORMER LOAD VERIFIED

V2 dataset:
PREPARED + AUDITED

V2 clean full training:
NOT COMPLETED

V2 partial checkpoint:
PRESERVED, DO NOT RESUME

Donor issue extraction:
MERGED IN CONTROLLED FORM

Post-merge issue integration:
VALIDATED

Post-merge known integration FAIL:
0 in the dedicated suite

Post-merge semantic WARN:
9, owned by PhoBERT

Scientific-final Transformer:
NOT AVAILABLE

Held-out final scientific evaluation:
NOT CLAIMED
```

---

# 103. NEXT SAFE CONTINUATION

If no newer `AI_CHANGELOG.md` entry overrides this section, continue from:

```text
1. Keep current controlled merge architecture.
2. Do not redesign NLP.
3. Do not resume the old V2 partial checkpoint.
4. Launch a CLEAN PhoBERT V2 Train/Dev run when authorized.
5. Compare V2 against V1 on Dev.
6. Investigate the nine known PhoBERT semantic warning families.
7. Freeze the selected protocol before held-out evaluation.
8. Keep issue extraction subordinate to ABSA.
9. Update AI_CHANGELOG.md after every phase.
10. Update this file when current architecture/state materially changes.
```

---

# 104. FINAL RULE FOR FUTURE AI/CODEX

Before making any non-trivial change, ask internally:

```text
Am I fixing the actual current problem,
or am I unnecessarily redesigning the project?
```

For this project, the priority is:

```text
correct NLP
>
reliable evaluation
>
stable end-to-end flow
>
clear demo
>
extra features
```

And the current architectural rule that must not be forgotten is:

> **PhoBERT decides WHAT aspect/sentiment the feedback expresses.
> Issue extraction may explain the evidence in more detail, but it does not get to change PhoBERT's decision.**

That boundary is intentional and is the key safety property of the post-merge architecture.

---

# 105. NLP CORE STATUS — FROZEN FOR BACKEND DEVELOPMENT

The final no-held-out engineering gate completed on 2026-08-10.

```text
NLP_CORE_READY_FOR_BACKEND
```

Current experimental winner:

```text
PhoBERT V2 repaired
model_artifacts/experimental_phobert_absa_v2_repaired/
```

Runtime contract:

```text
backend: transformer
device: CUDA
fallback: false
offline local artifact: required and verified
entrypoint: app.services.nlp_service.get_analyzer()
```

Issue extraction remains subordinate evidence enrichment. It may add compatible
detail to presentation, but cannot add/remove canonical aspects or override
PhoBERT sentiment. The `ISSUE_EXTRACTION_ENABLED` flag is a safe enrichment
rollback, not an alternative classifier.

The V2 runtime materializes overlapping windows for slow PhoBERT tokenizers so
long Vietnamese feedback is not silently truncated. It preserves the frozen
training/runtime preprocessing contract: normalize → VnCoreNLP segmentation →
PhoBERT tokenizer, max length 256.

Known semantic warnings are documented and non-blocking: some multi-aspect /
contrast recall and packaging polarity/mixed cases remain PhoBERT limitations.
They must not be hidden by runtime rules. The current engineering diagnostics
match the frozen V2 references: 44-case `27/2/15`, semantic regression
`29/0/3`, merged integration `27/5/0` with zero issue/response/integration
failures.

```text
V2.1: retained provenance only; not winner and not runtime
Scientific final: NO
Held-out Test: UNREAD
Challenge: UNREAD
Further model training: NO during normal backend work unless a true new NLP blocker is explicitly authorized
```

See `model_artifacts/nlp_core_final_gate.json` and `.md` for the consolidated
artifact, provenance, runtime, schema, regression, and performance evidence.

## 106. Application feedback contract after the controlled remake

The application layer has one customer feedback workflow only:

```text
Product Detail inline assistant
  → POST /api/feedback
  → FeedbackService.submit_feedback
  → app.services.nlp_service.get_analyzer()
  → optional compatible issue evidence
  → response_builder
  → feedback + feedback_analysis persistence
  → Seller database analytics
```

The product identity/category is request metadata. It is not concatenated into
the feedback text sent to PhoBERT. Raw feedback is committed first as
`pending`; terminal states are `ok`, `no_aspect`, or `failed`. A failed model
run never deletes the raw feedback and never silently invokes demo/rule NLP.

Issue extraction remains subordinate to the canonical Transformer result. It
can supply compatible evidence for customer/seller presentation, but cannot
add an aspect, modify sentiment, or create additional `feedback_analysis`
rows. Evidence is persistently associated with the feedback so seller issue
counts remain traceable to stored data.

The floating chat state machine and its routes are retired. Browsing a product,
reviews, or Seller analytics reads persisted state only; it does not perform
inference. The Seller NLP Quality screen reads configured runtime identity and
real artifact metadata, labels V2 as experimental/non-scientific, and never
uses fabricated metrics.

---

# 107. CURRENT EXPERIMENTAL TRACK: V3-V5

This section records the current August 2026 data-improvement work. It
supplements, but does not replace, the frozen V2 runtime decision in Sections
105-106.

## 107.1 State boundaries that reports must preserve

There are three distinct states in this repository:

```text
Default application configuration
    .env.example uses the lightweight demo backend

Verified local experimental Transformer runtime
    model_artifacts/experimental_phobert_absa_v2_repaired/

V3/V4/V5 data experimentation
    Kaggle workflow; V5 data is prepared, but V5 is not trained yet
```

The application loads a Transformer only when explicitly configured with
`NLP_BACKEND=transformer`, `TRANSFORMER_ARTIFACT`, `VNCORENLP_DIR`, and
permission for an experimental artifact. The current local
`model_artifacts/` directory contains V1 and V2 artifacts only. A V3/V4
Kaggle run must not be presented as a locally deployed runtime artifact.

## 107.2 Why the data-improvement track began

The V2 diagnostic for the generic feedback below selected `delivery` and
`price` but missed a clearly expressed `product_quality` aspect:

```text
Sản phẩm đẹp, giá ổn nhưng giao hàng hơi lâu.
```

The diagnostic showed `product_quality` aspect score `0.1093` against threshold
`0.4200`; its sentiment head leaned positive but the aspect was not selected.
This implicated inconsistent generic product-quality supervision more strongly
than a threshold-only problem. Lowering the threshold to catch scores near zero
would have created broad false-positive risk.

The accepted corrective process is therefore:

```text
inspect score/threshold evidence
    -> audit labels independently
    -> make reversible experimental data changes
    -> validate schema, taxonomy, exact duplicates, and provenance
    -> run fresh preflight on the exact Train/Dev fingerprints
    -> train a new experimental artifact
    -> test with fixed diagnostic feedback
```

No runtime keyword rule was added to force an aspect. PhoBERT remains the sole
authority for canonical aspect and sentiment predictions.

## 107.3 Product-quality repair evidence

Two independent AI-assisted validation passes are retained as:

```text
model_artifacts/product_quality_bulk_validation.json
model_artifacts/product_quality_blind_validation.json
model_artifacts/product_quality_repair_plan_v2.json
```

The reviewed experimental repair changed annotations on existing data:

```text
add product_quality annotation:              171 rows
change product_quality sentiment:              7 rows
new rows from this operation:                  0 rows
```

This is experimental, AI-assisted label work. It must not be described as a
fully human-verified or scientific-gold corpus repair.

## 107.4 Current V5 input identity

The V5 candidate uses the same Train/Dev paths as earlier experiments, but the
Train contents have changed:

```text
nlp/data/experimental_v2/train.jsonl
nlp/data/experimental_v2/dev.jsonl
```

Current identity, recorded 2026-08-11:

```text
Train rows: 18,038
Train SHA-256: e08b8e2206de4b49c0a92dcc5cecd59acef3065659673f1356bb6d9818e0102e

Dev rows: 2,205
Dev SHA-256: 1162f2d47b03b42de8d68a3530e31df6b99d3867523db984e9c9e2630f7f1754
```

Train aspect occurrences are labels, not unique feedback counts, because one
feedback can carry multiple aspects:

| Aspect | Current Train occurrences |
|---|---:|
| `product_quality` | 11,355 |
| `delivery` | 4,936 |
| `customer_service` | 906 |
| `packaging` | 3,091 |
| `price` | 3,445 |
| `other` | 1,458 |

Dev was unchanged by the V3-V5 additions. This experimental data track did not
open held-out Test or Challenge splits.

## 107.5 Append-only V3-V5 data changes

Starting from the repaired 16,238-row Train base, the current file grew through
the following approved append operations:

| Operation | Added rows | Purpose |
|---|---:|---|
| `other_train_augmentation_500.jsonl` | 500 | Improve the sparse `other` aspect |
| `customer_service_augmentation_400.jsonl` | 400 | Improve customer-service coverage and polarity |
| `other_multi_aspect_augmentation_400.jsonl` | 400 | Improve `other` in multi-aspect feedback |
| accepted `hard_cases_augmentation_600.jsonl` subset | 500 | Stress contrast, multi-aspect, and threshold boundaries |
| **Total appended** | **1,800** | **Current Train: 18,038** |

The hard-cases input contained 600 rows. Rows `hard_extra_0500` through
`hard_extra_0599` had clearly meta/instructional wording rather than natural
customer feedback and were excluded. Only IDs `hard_extra_0000` through
`hard_extra_0499` were appended.

The accepted hard-case rows remain LLM-generated candidates with
`manual_verified=false`, `experimental_only=true`, and
`review_status=AI_GENERATED_PENDING_HUMAN_REVIEW`. Passing the structural,
JSONL, and exact-duplicate checks is not a claim of human semantic approval or
scientific-gold quality.

Before each data mutation a rollback copy was created in:

```text
nlp/data/experimental_v2/.codex_backups/
```

The preserved backups cover the product-quality annotation repair, the
500-row `other` append, the 800-row customer-service/other append, and the
500-row hard-case append. JSONL parsing and exact ID/text duplicate checks
passed after every merge. A new full preflight is still required for the final
V5 fingerprints.

## 107.6 V3 and V4 experimental observations

### V3: product-quality and `other` repair

Kaggle console evidence for
`experimental_phobert_absa_v3_product_quality_other_repair` reported:

```text
best epoch: 5
best Dev strict-union Pair Macro-F1: 0.8698432855
product_quality Dev F1: 0.9748316200
other Dev F1:           0.9911504425
```

The same run reported these Dev-tuned thresholds:

```text
product_quality 0.30    delivery 0.80    customer_service 0.32
packaging       0.70    price    0.80    other            0.38
```

This is Dev-only experimental evidence. It cannot be claimed as a held-out
scientific comparison with V2 because data composition changed.

### V4: customer-service and multi-aspect `other` repair

Kaggle used `experimental_phobert_absa_v4_cs_other_repair` after the two
400-row additions. Direct long-feedback diagnostics showed that a complaint
about ignored return requests selected `customer_service -> negative` together
with product quality, delivery, packaging, and price.

`other` remained the most fragile aspect in long multi-aspect feedback. One
diagnostic had `other=0.4468 < 0.6600`; a more explicit six-aspect diagnostic
selected `other` but only narrowly, `0.6661 >= 0.6600`. This was the reason for
the V5 hard-case focus.

No V4 aggregate Dev metric or V4 artifact is stored in this local repository.
Reports must not invent one.

## 107.7 V5 status and Kaggle contract

V5 is a **prepared dataset revision, not a trained model**. Intended output
locations are:

```text
model_artifacts/preflight_phobert_v5_hard_cases_final/
model_artifacts/experimental_phobert_absa_v5_hard_cases_final/
```

An older preflight PASS does not authorize V5 because its Train fingerprint is
different. The Kaggle order is fixed:

```text
copy V5 project to /kaggle/working/project
    -> install requirements-train.txt
    -> verify Java, VnCoreNLP, Python imports, and CUDA
    -> run focused regression tests
    -> run fresh preflight_transformer for current Train/Dev
    -> require overall_preflight=PASS and full_training_allowed=true
    -> run one clean --experimental train_transformer job
    -> inspect Dev metrics, thresholds, and fixed hard-case diagnostics
```

The verified Kaggle environment had Java 17, a VnCoreNLP input directory, and
two Tesla T4 GPUs available to PyTorch. The trainer tunes one threshold per
aspect only on Dev and saves the resulting `thresholds.json` with the best
checkpoint. Thresholds must not be manually replaced after training.

## 107.8 Required reporting language and immediate boundary

Use this wording for the report and slide deck:

```text
The system has a verified experimental PhoBERT V2 runtime and a separate V5
data-improvement experiment in preparation. V5 uses an expanded 18,038-row
experimental Train split with an unchanged 2,205-row Dev split. It has not yet
been preflighted or trained. Newly generated augmentation remains AI-assisted,
experimental, non-human-verified, and non-scientific-final.
```

Do not claim that V5 is deployed, final, human-verified, or evaluated on
held-out Test. The next safe boundary is fresh V5 preflight, followed by one
clean Kaggle training run and fixed-diagnostic evaluation before any
runtime-activation decision.
