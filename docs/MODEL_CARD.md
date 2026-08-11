# Model Card — Project NLP State

## Current bundled runtime artifact

Name: `baseline_absa_v0`

Type: shared word/character TF-IDF representation + one binary Logistic Regression aspect classifier per aspect + per-aspect Logistic Regression sentiment classifiers.

Purpose: **runnable project/demo baseline and pipeline validation**.

It is not the claimed final scientific model.

## Training data for bundled artifact

Project-authored synthetic/demo fixtures under `nlp/data/demo/`.

These rows have `is_scientific_gold=false`. Evaluation artifacts also set `scientific_final=false` and contain a warning visible in the seller Model Evaluation page.

The demo artifact must not be used as evidence that the final Transformer understands Vietnamese semantics.

## Intended final model

Multi-task Vietnamese Transformer ABSA:

- shared encoder;
- six sigmoid aspect outputs;
- six four-class sentiment heads;
- masked sentiment loss for present aspects;
- Dev-only per-aspect thresholds.

Candidate backbones:

1. `vinai/phobert-base-v2`
2. `Qualcomm-AI-Research/BamiBERT`

Model selection is empirical, not predetermined.

### PhoBERT constraint

PhoBERT model documentation states raw Vietnamese should be word segmented consistently with VnCoreNLP/RDRSegmenter before use. This project therefore requires a local VnCoreNLP model directory for PhoBERT training/runtime.

### BamiBERT constraint

BamiBERT documentation states it operates on raw Vietnamese and supports up to 2048-token context. Its model card also notes possible dialect/domain limitations. These properties do not make it automatically superior for this project; it must win on the project Dev protocol.

## Taxonomy

Aspects:

- product_quality
- delivery
- customer_service
- packaging
- price
- other

Sentiment:

- positive
- neutral
- negative
- mixed

Noise/no meaningful evaluative content is runtime `no_aspect`, not `other`.

## Primary metric

`Pair Macro-F1` on `aspect#sentiment` pair classes present in the gold evaluation split.

Why: the production function is correct only when the system identifies the correct aspect and its corresponding polarity. Gold-defined macro averaging reduces dominance by frequent pair classes while keeping the denominator identical across candidate models. Hallucinated pair classes absent from gold are surfaced by Pair Micro-F1, Exact Match, strict-union Pair Macro-F1 and an unseen-pair false-positive count.

## Required final evidence before claiming success

A future final model is only promoted when all are true:

- human-verified 6-aspect gold dataset;
- annotation guideline frozen;
- agreement/adjudication process documented;
- no cross-split duplicate leakage;
- Train/Dev/Test protocol frozen;
- tiny-overfit sanity pass;
- label-shuffle sanity pass;
- baselines run on the same split;
- Transformer candidate selection uses Dev only;
- per-aspect thresholds tuned on Dev only;
- final held-out Test evaluation;
- semantic challenge evaluation;
- multiple random seeds;
- per-class metrics inspected for class collapse;
- final artifact/version persisted;
- backend integration regression tests pass.

## Known limitations of the bundled ZIP

The build environment used to generate the ZIP did not have a finalized project-specific human gold corpus, `transformers` package/model weights, GPU training access, or a Docker executable. Therefore:

- no final Transformer weights are fabricated;
- no fake Transformer F1 is shown;
- the full Transformer code/protocol is present and syntax-tested;
- the runnable baseline and web system are tested locally in Python;
- Docker files are statically audited but Docker runtime is not falsely reported as executed.

This is an intentional scientific-integrity choice, not an omitted claim.
