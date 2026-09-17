# Spec: Step 9 — platform_data.json (one file for the whole UI)

Version 1.0 · For Claude Code · Inputs: `data/metrics/cycle_01/*` (all step outputs), `data/registry/*`, `data/normalized/*`, `data/raw/corpus_master.json`, and the platform export `data/raw/citere_points_full.json`.

Goal: one JSON that the Master Dashboard and the Evidence Base both read. **All numbers come from the pipeline. All prose, causes, fix cards, SERP snapshots and inventory come from the platform export.** Nothing is recomputed here; nothing from the export is trusted as a number.

---

## 1. What the platform export contributes (keep) and what it does not (drop)

Join key: `(pid, run)` — same in both sources, 1,424 matches expected; report any point present on one side only.

| Field in export | Keep? | Reason |
|---|---|---|
| `cause` {code, label, confidence, evidence[], refine} | **keep** | root cause — not computed by the pipeline |
| `diagnosis` [paragraphs] | **keep** as `diagnosis_text` | plain-language narrative |
| `fixes` [cards] | **keep** | action cards with URLs, MLR status, agent, owner |
| `serp` {our, comp, occ, ov, fo} | **keep** | Google snapshot, not in corpus |
| `inventory` {v, url, miss, comp, curl} | **keep** | our-page inventory, not in corpus |
| `evidence_measured`, `evidence_search` | **keep** as `evidence_lines` | narrative evidence bullets (text) |
| `priority` (0–29.5 point score) | **keep** as `point_rank_score` | used ONLY to order points inside a topic group; never aggregated, never shown as a headline |
| `status`, `status_label`, `status_detail` | **drop** → replaced by pipeline `sev` + a label from `code` | numbers/labels must match the dashboard |
| `answers`, `sentiment`, `brand_mentions`, `other_brand_leak` | **drop** → from `answers.parquet` | pre-truncation, pre-INN, pre-new-competitors |
| `top_sources` | **drop** → from `citations.parquet` | owner taxonomy differs (`government` vs `institutional`) |
| `demand` | **drop** → from `topic_traffic` in corpus | keep only `prompt_share` and `ai_native` from export as `demand_extra`, flagged `source: platform_export` |
| `zone, topic, subtopic, query_type, patient_stage, question` | take from corpus (`intent`, `zone`, `text`); cross-check equality with export, report mismatches | one source of labels |

Fix cards: keep all four types but tag `audience`: `TRACK` → `citere`; `OWNED`, `EARNED`, `LABEL-MEDICAL` → `client`. UI shows `client` by default.

Fix-card `execution` in the export (`AGENT`, `AGENT+APPROVE`, `HUMAN TASK`) stays on the card as `execution` — one field, not duplicated; the campaign-level `execution` (auto/manual/citere) comes from the Action Center registry. Both are visible, neither overrides the other.

---

## 2. Output structure

```json
{
  "meta": { ...dashboard.meta, "platform_export_generated": "2026-09-16", "points_joined": 1424, "points_unmatched": [] },
  "dashboard": { ...dashboard.json verbatim, unchanged },
  "groups": [
    {"group_id": "...", "topic": "...", "subtopic": "...", "zone": "...", "n_prompts": 0,
     "demand": 0, "lo": 0, "hi": 0, "gap": 0.0, "gap_by_run": {...}, "gap_bad": 0.0,
     "dominant_code": "...", "dominant_cause": {"code": "...", "share": 0.0},
     "priority": 3, "bucket": "recommendation|healthy|below_floor|label",
     "failure_code_share": 0.0,
     "lever": {"earned": 0.0, "owned": 0.0, "ugc": 0.0, "comp_owned": 0.0, "institutional_share": 0.0},
     "pids": ["P0001|R1", ...]   — ordered by point_rank_score desc }
  ],
  "points": {
    "P0001|R1": {
      "pid": "P0001", "run": "R1", "class": "C1", "zone": "...", "topic": "...", "subtopic": "...",
      "query_type": "...", "patient_stage": "...", "question": "...",
      "group_id": "...",
      "sev": "good|warn|bad", "code": "...", "code_label": "...",
      "cause": {...from export...},
      "point_rank_score": 0.0,
      "metrics": {                      — ALL from answers.parquet / citations.parquet
        "answers": 0, "answers_excluded": 0,
        "we_present_share": 0.0, "avg_position": null, "inn_only_share": 0.0,
        "by_model": [{"model_family": "...", "answers": 0, "we_present": 0, "position": null,
                      "brand_sentiment": null, "answer_sentiment": null}],
        "competitors_present": {"Mounjaro": 0, ...}, "comp_present_answers": 0,
        "answer_sentiment": null, "brand_sentiment": null,          — point means over used answers (added for the Neural map)
        "citations": {"total": 0, "owned": 0, "earned": 0, "institutional": 0, "competitor": 0, "adversarial": 0,
                      "answers_with": {"any": 0, "owned": 0, "earned": 0, "institutional": 0, "competitor": 0, "adversarial": 0},
                      "top_domains": [{"domain": "...", "owner": "...", "subtype": "...", "n": 0}]},
        "run_specific": { ...scores fields relevant to the run: R1 our_status/our_rank, R2 winner, R4 verdict/harm_class/target/label_section, R6 status/attribution, R9 uptake/anti_frame_outcome... }
      },
      "demand": {"topic_demand": 0, "lo": 0, "hi": 0, "basis": "..."},
      "demand_extra": {"prompt_share": 0, "ai_native": false, "source": "platform_export"},
      "diagnosis_text": ["..."], "evidence_lines": ["..."],
      "serp": {...}, "inventory": {...},
      "fixes": [{...card..., "audience": "client|citere", "task_type": "plain name for the export's own `agent` field; the agent string stays on the card"}],
      "answers_ref": "corpus_master.json#P0001|R1"   — answer texts are NOT embedded here
    }
  },
  "campaigns/label_tasks_awaiting_signoff also carry": "rows derived in step 9 (task_id prefixed `d`, `source` field set) for client fix cards whose group already has tasks but none for their owner — step 6 can raise a label row only when a group has no citations at all, so label/medical cards on ordinary recommendation groups had no home. Derived rows carry no ceiling or expected shift (basis says so). Check 8 fails if any client card in a task-bearing group is unreferenced.",
  "campaigns": [ ...action_center_tasks.json client tasks, each with "fix_card_refs": [{"pid_run": "...", "fix_idx": 0}, ...]
                  = client fix cards whose point is in the campaign's group AND whose card type maps to the campaign owner
                  (OWNED→owned, EARNED→earned/ugc/comp_owned, LABEL-MEDICAL→label rows) ],
  "citere_tasks": [ ...registry citere tasks + all TRACK fix cards grouped by group_id ],
  "label_findings": [ ...label_findings_registry.json, with cell → pids of R4 answers in that cell ],
  "sources": { ...citations_summary.json + per-domain "pids" list (top 200 domains only, to bound size) },
  "groups[] also carry, for the Priorities screen (added after cycle-1 review; all carried, nothing recomputed)": {
    "headline": "plain-language title: subject phrase (topic × subtopic/zone) + the action for the top owner",
    "subject_label": "Side effects and daily life", "action_label": "get cited on drug directories", "source_label": "drug directories",
    "top_owner": "earned", "top_owner_lever": 0.754,
    "impact_reach": "step 6 impact_reach {point, lo, hi, caption} = topic demand × gap — the row's own number, not recomputed",
    "dominant_cause": "+ label and confidence (modal among the points carrying it)",
    "failing_cause": "{code, label, n, share, confidence} over points whose code is a failure code",
    "code_distribution": "[{code, label, n, share}]", "cause_distribution": "[{code, label, n, share}]",
    "top_domains": "[{domain, owner, subtype, citations, with_us}] top 8 over the group's answers",
    "owner_rows": "[{owner, what, who, speed, score, lever, impact_reach, top_domain, source_label, task_id, status, execution, ceiling_pp, expected_pp}]",
    "campaign_ids": "[]", "held_task_ids": "[]", "citere_task_ids": "[]",
    "no_campaign_reason": "one line saying why a group raised no client campaign (healthy / below floor / label awaiting sign-off / Citere monitoring)"
  },
  "campaigns[].impact.reach": "the same step-6 impact_reach, so the Action Center and the group agree",
  "breakdowns": {                    — carried verbatim from the step summaries (added after cycle-1 UI review)
    "visibility_by_zone":        [ visibility_summary.by_zone: {zone, n_prompts, n_answers, visibility_pct, visibility_ci95, average_position, ai_brand_score, inn_only_mention_pct, low_n} ],
    "visibility_by_topic_group": [ visibility_summary.by_topic_group: same fields keyed topic_group ],
    "benchmarking_by_zone":      [ benchmark_summary.by_zone: {zone, win_rate, n_overlap_answers, n_prompts, top_impact_competitor, top_impact} ],
    "safety_by_target":          [ label_flag_summary.by_target: {target, tier, label_section, n, critical_share, dangerous_share, findings_surfaces} ],
    "safety_unstable_cells":     [ label_flag_summary.unstable_cells_list: {target, surface, n, critical_share} ]
  },
  "map": "unchanged — the neural map keeps its own data block"
}
```

Answer texts stay in `corpus_master.json`; the UI loads them lazily by `answers_ref`. This keeps `platform_data.json` under ~15 MB.

---

## 3. Checks (all must pass, else do not write)

- 1,424 points joined; `points_unmatched` empty.
- Every `pids` entry in `groups` exists in `points`; every point has exactly one `group_id`.
- Every campaign's `fix_card_refs` resolve; no `TRACK` card carries `audience: client`.
- Sum of `groups[].n_prompts` over all buckets = 1,424.
- `dashboard` block is byte-identical to `dashboard.json`.
- Label-topic and run-topic cross-check: export `topic/subtopic/zone` vs corpus — report mismatch count; > 0 is WARN, > 50 is STOP.
- Spot check: for 20 random points, `metrics.we_present_share` equals the per-point value in `visibility_by_prompt.csv` (R1) — must be identical.

---

## 4. Do not

- Do not use any number from the export except `point_rank_score`, `prompt_share`, `ai_native` — and those only where labelled.
- Do not re-derive `cause` or rewrite `diagnosis_text` / fix cards.
- Do not embed answer texts.
- Do not aggregate `point_rank_score` upward.
