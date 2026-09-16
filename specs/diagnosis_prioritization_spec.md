# Spec: Diagnosis & Prioritization

Version 1.0 · For Claude Code · Input: `corpus_master.json` (meta + prompts[1424]). Brand dictionary and quality filters — from `visibility_score_spec.md`.

Output: a **ranked list of recommendations**, each = topic × source owner, with priority 1–3, three justification numbers, cause, concrete domains, and expected reach.

---

## 1. Fields used

Prompt level: `pid`, `run`, `text`, `zone`, `status`, `intent.{topic, subtopic, query_type, patient_stage}`, `diagnosis.{sev, code, text, fixes[{do, owner, speed}]}`, `topic_traffic.{demand, lo, hi, basis}`.

Answer level (`models[i]`): `model`, `answer`, `mentioned`, `citations[{url, domain, owner, category}]`, `scores{...}`.

Before computing, output an inventory: prompts per `run`, `sev` distribution, answers with/without `citations` per `run`, prompts with empty `subtopic`, unique `owner` and `category` values in citations.

---

## 2. Topic group

Topic unit — `topic_group`:
- if `intent.subtopic` is populated and ≠ "Other" → `topic × subtopic`
- if empty or "Other" → `topic × zone`

Reason: `demand` is group-level demand, not per prompt; 452 prompts have empty subtopic, 92 are "Other" with anomalously large demand. Grouping by zone splits that bucket.

**Minimum group size: 10 prompts.** A group with fewer than 10 prompts is merged into its parent `topic` group (all small groups of one topic pooled together as `topic × small`), and takes the parent's `demand`. Reason: on cycle-1 data the top of the list was taken by groups of 2–4 prompts that inherited the 377K demand of the "Other" bucket. Config `min_group_prompts: 10`.

Output a group table: `group_id, topic, subtopic, zone, n_prompts, n_answers, demand, lo, hi, basis, merged_from[]`. If `demand` takes more than one value within a group — take the median, log the group.

---

## 3. Three numbers

**3.1. Demand_share(group)**
```
Demand_share = demand(group) / Σ demand over all groups
```
Computed **once per group**, never summed over prompts. Range: `lo_share`, `hi_share` — same using `lo` and `hi`.

**3.2. Gap(group)**
```
Gap = prompts in group with sev ∈ {warn, bad} / prompts in group
```
Also output `Gap_bad` (bad only) — for sorting within a priority tier.

Prompts with our brand in the question (class C2) are included in Gap — they carry their own codes (LEAK, STEERS AWAY, LABEL ERROR), which are also gaps.

**Gap mixes runs.** A topic group pools prompts from different runs, and `bad` means different things per run: R4 — label error, R6 — message not delivered, R2 — lost duel, R1 — absent from category answer. Gap is therefore "problem density on the topic", not one kind of failure. For every group also output `gap_by_run: {R1: 0.0, R2: 0.0, …}` and `n_by_run`, and show the dominant run in the recommendation row. Do not silently present Gap as a single-meaning metric.

**3.3. Lever(group, owner)**
```
Lever = citations with this owner in the group's answers / all citations in the group's answers
```
Owner taken from `citations[].owner` as is. Computed only over answers with non-empty `citations`.

Owner rules:
- `earned`, `commerce`, `ugc`, `owned` → participate, each as a separate recommendation row
- `comp_owned` → participates as the row "competitor feeds answers with its own domains" (action: build comparable owned content; owner = Digital)
- `adversarial` → not in recommendations; reported as a separate "threat sources" line with domains
- `noise`, `other` → excluded
- categories `regulatory`, `gov_health`, `wiki`, `clinical` under any owner → excluded from Lever (institutional — not fixable); report their share as `institutional_share(group)`

If no answer in the group has citations (R4/R5/R8-only groups) — Lever = null, the row goes to §5 as a Label recommendation without a source.

---

## 4. Priority

```
Score(group, owner) = Demand_share × Gap × Lever
```

Rank all rows by Score. Priority by terciles: top third = 3, middle = 2, bottom = 1. Within a tier — by `Gap_bad`, then by `demand`.

Output the tercile thresholds in the report (so the boundary is visible).

---

## 5. Rows without a source (Label codes)

Groups where the dominant `diagnosis.code` ∈ {DANGEROUS LABEL ERROR, INCOMPLETE / OMISSION, MODEL ON AN OLD LABEL, AI AMPLIFIES A HARMFUL MYTH, MYTH DEFENDED, FAMILY CONFUSION} and there are no citations:

```
Score = Demand_share × Gap
```
Action owner — from `fixes[].owner` (Medical / Regulatory / Comms). Lever = null, row flagged `no_source_data`. Ranked by the same tercile rule — but as a separate "Label / Medical" sub-list, not mixed with source rows.

---

## 6. Recommendation row content

For each row (group × owner):

| Field | Source |
|---|---|
| `what` | `fixes[0].do` of the group's dominant code (the code with the largest prompt share) |
| `who` | `fixes[0].owner` of the same code |
| `speed` | `fixes[0].speed` |
| `priority` | 1–3 from §4 |
| `why.demand` | `demand`, `lo`, `hi`, `Demand_share` |
| `why.gap` | `Gap`, `Gap_bad`, n prompts |
| `why.lever` | `Lever`, owner, `institutional_share` |
| `cause` | top-3 `diagnosis.code` of the group with prompt counts |
| `where` | top-5 domains of this owner in the group's answers: `domain, category, citations, with_us, with_comp` — `with_us` = answers with this domain where our brand is named; `with_comp` — where a competitor is named |
| `examples` | 2 `pid` + first 150 chars of `text` — the "worst" prompts of the group (sev = bad, max demand) |
| `impact_reach` | `demand × Gap`, with range `lo × Gap … hi × Gap` — "affects up to N queries/month" |

`impact_reach` is a ceiling, not a forecast: the caption is mandatory in output.

---

## 7. Output format

**7.1. `prioritization_summary.json`**
```json
{
  "brand": "...", "competitor": "...",
  "groups_total": 0, "rows_total": 0, "rows_label_only": 0,
  "tercile_thresholds": {"p3_min": 0.0, "p2_min": 0.0},
  "recommendations": [
    {"rank": 1, "priority": 3, "group": {"topic": "...", "subtopic": "...", "zone": "..."},
     "owner": "earned", "what": "...", "who": "Digital + PR", "speed": "weeks",
     "score": 0.0,
     "why": {"demand": 0, "lo": 0, "hi": 0, "demand_share": 0.0,
             "gap": 0.0, "gap_bad": 0.0, "n_prompts": 0,
             "lever": 0.0, "institutional_share": 0.0},
     "cause": [{"code": "...", "n": 0}],
     "where": [{"domain": "...", "category": "...", "citations": 0, "with_us": 0, "with_comp": 0}],
     "examples": [{"pid": "...", "text": "..."}],
     "impact_reach": {"point": 0, "lo": 0, "hi": 0}}
  ],
  "label_recommendations": [ ...same format, "lever": null, "no_source_data": true ],
  "adversarial_sources": [{"domain": "...", "category": "...", "citations": 0, "groups": ["..."]}],
  "quality": {"groups_with_multi_demand": 0, "groups_without_citations": 0, "answers_without_citations_pct": 0.0}
}
```

**7.2. `prioritization_groups.csv`** — all groups: `group_id, topic, subtopic, zone, n_prompts, demand, lo, hi, basis, gap, gap_bad, top_code, institutional_share, lever_earned, lever_commerce, lever_owned, lever_ugc, lever_comp_owned`.

**7.3. `prioritization_rows.csv`** — all group × owner rows with §6 fields (without nested lists).

**7.4. Short report** (≤ 15 lines): top-5 recommendations as one line each — "Topic → owner · P3 · demand · gap · lever · cause · top domain · affects up to N/month"; tercile thresholds; number of Label rows; top-3 adversarial domains.

---

## 8. Do not

- Do not sum `demand` over prompts — only per group.
- Do not recompute `sev`/`code` with your own model — take as is.
- Do not include institutional categories or `adversarial` in Lever.
- Do not estimate fix cost and do not add regulatory flags — not in this version.
- Do not rewrite `fixes` texts — only select the one matching the dominant code.
- On schema mismatch — stop and ask.
