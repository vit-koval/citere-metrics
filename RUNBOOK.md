# Runbook — Citere metrics pipeline (cycle 1)

Read this first. Then the specs, in the order below. Each step ends with a stop for human review.

## Folder layout
```
citere-metrics/
  config/            brands.yaml, models.yaml, domains.yaml, thresholds.yaml
  specs/             the 9 spec files
  data/raw/          corpus_master.json  (read-only, never modified)
  data/normalized/   answers.parquet, citations.parquet, data_quality_report.md
  data/metrics/cycle_01/   *_summary.json, *.csv, short reports, dashboard.json
  data/registry/     action_center_tasks.json, label_findings_registry.json  (persist across cycles)
  audit/             sample_*.csv for manual review
  src/               one module per step, plus common.py (loaders, aggregation helpers, Wilson CI)
  tests/             unit tests on hand-made fixtures
```

## Order of steps
| Step | Spec | Reads | Writes | Stop for |
|---|---|---|---|---|
| 0 | RUNBOOK + configs | — | config/*.yaml | human confirms brand/domain lists |
| 1 | normalization_spec | data/raw | data/normalized/* + data_quality_report.md | **human reads the report** |
| 2 | visibility_score_spec | normalized | metrics/visibility_* + audit/sample_visibility.csv | 30-row manual audit ≥ 90% |
| 3a | competitive_benchmarking_spec | normalized | metrics/benchmark_* | audit |
| 3b | citation_tracking_spec | normalized | metrics/citations_* | audit |
| 4 | sentiment_analysis_spec | normalized (+LLM re-scoring, writes brand_sentiment back) | metrics/sentiment_* | correlation check ≥ 0.6, audit |
| 5 | safety_label_flag_spec | normalized (R4) + registry | metrics/label_* + registry | clinician sign-off is a separate human step |
| 6 | diagnosis_prioritization_spec | normalized + steps 2–5 outputs | metrics/prioritization_* | human reads top-10 |
| 7 | action_center_spec | step 6 + registry | registry + metrics/action_center_* | — |
| 8 | dashboard_assembly_spec | steps 2–7 | dashboard.json + audit pack | all checks pass |

## Common rules (apply in every module)
- Aggregation is always repeats → prompt×model → model family → overall, equal family weights, unless a spec says otherwise (citations aggregate over citations).
- Every percentage at family and overall level carries a Wilson 95% CI.
- Rounding only in the final report / dashboard.json.
- Any schema surprise: stop and print, never guess.
- Every module writes a short `<block>_report.md` (≤ 15 lines) next to its JSON.

## Conventions
- Python 3.12, pandas + pyarrow; tests with pytest; one command per step: `python -m src.step_01_normalize`, etc.
- `common.py` holds: config loading, brand matching, position extraction, tail cleaning, aggregation helpers, Wilson CI — modules must import these, not reimplement.
- Deterministic: same input + same config → identical output. Seed any sampling with 42.
