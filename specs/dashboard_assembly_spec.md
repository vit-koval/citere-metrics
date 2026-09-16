# Spec: Dashboard Assembly — dashboard.json

Version 1.0 · For Claude Code · Input: the seven `*_summary.json` files of one cycle + `config/`. Output: one `dashboard.json` the UI reads. Registries (`action_center_tasks.json`, `label_findings_registry.json`) are **not** embedded — the UI reads them separately.

---

## 1. Schema

```json
{
  "meta": {"brand": "Ozempic", "cycle": 1, "period": "2026-09", "market": "US/en",
           "competitors": [...], "prompts": 1424, "answers": 12315, "surfaces": 9,
           "generated_at": "...", "pipeline_version": "...", "config_hash": "..."},
  "visibility":     { ...visibility_summary.headline + by_model + scope + intrusion },
  "benchmarking":   { ...overall + leaderboard + duel_verdict },
  "sentiment":      { ...score + shares + by_model + competitors + top_negative_themes },
  "citations":      { ...owner_shares + top_domains(10) + gap_list(10) + adversarial_sources },
  "prioritization": { ...recommendations(top 10) + label_recommendations(top 5) + tercile_thresholds },
  "action_center":  { ...counters only + top3_open },
  "safety_label":   { ...traffic_light + critical_answer_share + ci + findings counts + by_surface + top_label_sections
                       — findings_list filtered to signoff_status = confirmed },
  "before_after":   {"available": false, "reason": "first cycle", "next_cycle_expected": "2026-12"}
}
```
From cycle 2: `before_after` holds, per metric, `{current, previous, delta, comparable: bool}` — `comparable` is false if prompt set, surface list, brand dictionary or pipeline version changed between cycles.

---

## 2. Checks before writing (all must pass)

- Every shares triple sums to 100 ± 0.1.
- `visibility.by_model` families = families in `config/models.yaml` minus dropped.
- `benchmarking.leaderboard` competitors ⊆ `config/brands.yaml.competitors`.
- Every `prioritization.recommendations[].group` exists in `prioritization_groups.csv`.
- Every `action_center.top3_open[].task_id` exists in the registry.
- No `safety_label.findings_list` entry has `signoff_status != confirmed`.
- `meta.answers` = rows in answers.parquet (including excluded) − dropped models.
- Numbers rounded to 1 decimal only here, never earlier.

On any failure: write `dashboard_assembly_errors.md`, do not write `dashboard.json`.

---

## 3. Manual audit pack (written alongside)

`audit/sample_<block>.csv` — 30 random rows per block: the answer text (clean), the computed values for that block, and an empty `reviewer_agrees` column. Blocks: visibility (we_present, we_pos, inn_only), benchmarking (win, loss_type per competitor), sentiment (brand_sentiment), citations (owner per domain), safety (verdict as stored, is_finding for its cell).

Release rule: a block ships only when reviewer agreement ≥ 90% on its sample.
