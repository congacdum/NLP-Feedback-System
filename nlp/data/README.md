# NLP data directories

- `demo/`: project-authored fixtures for pipeline/tests only; **not scientific gold**.
- `raw/`: on-demand upstream/candidate files. Not bundled by default.
- `mapped/`: conservative source-to-project mapping output. Still not automatically gold.
- `gold/`: final human-audited frozen Train/Dev/Test. Intentionally empty in the supplied build until the annotation gate is completed.
- `challenge/`: semantic challenge sets. The bundled `demo_challenge.jsonl` validates code only; create `final_challenge.jsonl` for scientific reporting.

Never copy `mapped/` directly into `gold/` merely because the script ran successfully. Read `docs/ANNOTATION_GUIDELINE.md` and `docs/DATA_SOURCES_AND_MAPPING.md` first.
