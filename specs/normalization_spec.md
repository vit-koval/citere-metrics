# Spec: Normalization — Layer 1 (answers.parquet, citations.parquet)

Version 1.0 · For Claude Code · Input: `data/raw/corpus_master.json` + `config/*.yaml`. Output: two flat tables every metric module reads. **No metric module reads the raw JSON directly.**

---

## 1. Configs (create before running; stop if any is missing)

`config/brands.yaml`
```yaml
our_brand: ["Ozempic"]
our_inn: ["semaglutide"]
competitors:
  Mounjaro: ["Mounjaro"]
  Wegovy: ["Wegovy"]
  Zepbound: ["Zepbound"]
  Rybelsus: ["Rybelsus"]
  Trulicity: ["Trulicity"]
  Victoza: ["Victoza"]
  Jardiance: ["Jardiance"]
  Saxenda: ["Saxenda"]
competitor_inn:
  tirzepatide: ["Mounjaro", "Zepbound"]
  liraglutide: ["Victoza", "Saxenda"]
  dulaglutide: ["Trulicity"]
  empagliflozin: ["Jardiance"]
```
`config/models.yaml`
```yaml
families:
  claude: ["claude-sonnet-4-6", "claude-sonnet-5", "claude-web"]
  gpt: ["gpt-4o", "gpt-web"]
  gemini: ["gemini-2.5-flash", "gemini-web", "google-ai"]
  perplexity: ["perplexity-web"]
  grok: ["grok-web"]
drop: ["gemini-3.6-flash"]
surface_type:
  api: ["gemini-2.5-flash", "gpt-4o", "claude-sonnet-4-6", "claude-sonnet-5"]
  web: ["gpt-web", "claude-web", "grok-web", "gemini-web", "google-ai", "perplexity-web"]
weights: equal
```
`config/domains.yaml`
```yaml
owned: ["ozempic.com", "novonordisk.com", "novomedlink.com", "novocare.com"]
competitor:
  Mounjaro: ["mounjaro.lilly.com", "mounjaro.com"]
  Zepbound: ["zepbound.lilly.com"]
  Wegovy: ["wegovy.com"]
  Rybelsus: ["rybelsus.com"]
  Jardiance: ["jardiance.com", "boehringer-ingelheim.com"]
institutional_categories: ["regulatory", "gov_health", "wiki", "clinical"]
institutional_domains: ["fda.gov", "accessdata.fda.gov", "dailymed.nlm.nih.gov", "ema.europa.eu", "nih.gov", "cdc.gov", "nhs.uk", "medlineplus.gov", "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov", "cochrane.org", "wikipedia.org"]
artifacts: ["vertexaisearch.cloud.google.com"]
```
`config/thresholds.yaml`
```yaml
min_answer_chars: 100
max_truncation_share_per_surface: 0.10
sentiment_thresholds: [40, 60]
finding_min_critical_share: 0.5
finding_min_n: 3
min_group_prompts: 10
position_decay: 0.9
closure_coefficients: {owned: [0.05, 0.10], earned: [0.10, 0.22], commerce: [0.10, 0.22], comp_owned: [0.10, 0.22], ugc: [0.05, 0.15]}
```

---

## 2. answers.parquet — one row per answer

| Column | Rule |
|---|---|
| `pid, run, zone, status, text, code, sev, topic, subtopic, query_type, patient_stage, demand, lo, hi, basis` | copied from the prompt |
| `model` | raw model string |
| `model_family`, `surface_type` | from `models.yaml`; rows with `model` in `drop` are removed and counted |
| `repeat_idx` | 0..n−1 in order of appearance within `models[]` for the same `model` |
| `answer_raw` | as is |
| `answer_clean` | tail stripped: repeatedly remove trailing `\s*\[?[a-z0-9.-]+\]?\s*\+\d+$`, `\s*FDA Access Data$`, `\s*\[[a-z0-9.-]+\]$`, emoji, whitespace |
| `tail_cleaned` | bool — anything was stripped |
| `excluded`, `exclude_reason` | `too_short` if len(answer_clean) < 100; `truncated` if answer_clean does not end with `.!?)»"`; `chip_on_cut` if a chip pattern sits in the last 60 chars right after a non-terminal char |
| `class` | C1/C2/C3/C4 from `text` via brands.yaml (trade names only) |
| `status_mismatch` | bool — class disagrees with `status` |
| `we_present` | our trade name in `answer_clean` (word boundary, case-insensitive) |
| `inn_only` | our INN present and `we_present` = false |
| `we_pos` | 1-based order of first appearance of our trade name among all trade names (ours + competitors) in `answer_clean`; null if absent |
| `comps_present` | list of competitor trade names present |
| `comp_pos` | dict competitor → 1-based position |
| `answer_sentiment` | stored `sentiment`, float or null |
| `brand_sentiment` | null at this step (filled by the sentiment module) |
| `scores_json` | the raw `scores` dict, serialized — so modules can read run-specific fields (`our_status`, `winner`, `verdict`, …) |

Cross-check columns (computed, kept for audit): `our_status_scored` (from scores if present), `our_rank_scored`.

---

## 3. citations.parquet — one row per citation

| Column | Rule |
|---|---|
| `pid, run, model, model_family, repeat_idx, class, excluded` | joined from answers |
| `url` | as is |
| `domain` | lowercase, strip `www.`, registrable domain |
| `owner_data`, `category_data` | as stored |
| `is_artifact` | domain in `artifacts` → excluded from every metric |
| `is_institutional` | category in `institutional_categories` OR domain in `institutional_domains` |
| `owner` | `owned` if domain in `owned`; `competitor:<Brand>` if in `competitor`; `institutional` if is_institutional; `adversarial`/`noise`/`other` as stored; else `earned` (with `subtype` = `category_data`) |
| `we_present`, `comps_present` | joined from the answer |
| `dedup` | same domain twice in one answer → keep first only |

---

## 4. data_quality_report.md — written every run, read before anything else

Sections, each with a PASS/WARN/STOP line:
1. Prompts and answers per run × model; dropped models.
2. Repeats per prompt×model: min/median/max; share of single-run groups per run.
3. Tail cleaning share and **real truncation share per surface** — STOP if any surface > `max_truncation_share_per_surface`; print 10 examples.
4. Class distribution per run; `status_mismatch` share.
5. `we_present` vs `our_status_scored` agreement on R1 (expect: disagreement ≈ INN-only share).
6. `inn_only` share per model.
7. Sentiment: median `answer_sentiment` with vs without `we_present` (expect equal — confirms answer-level).
8. Citations: total, artifacts removed, owner distribution, top-30 `other`.
9. Topic groups: size distribution, number below `min_group_prompts`, groups with multiple demand values, empty subtopics.

STOP means: do not run any metric module until a human has read the report.

---

## 5. Do not

- Do not modify `corpus_master.json`.
- Do not classify by `status`.
- Do not count INN as brand.
- Do not drop excluded answers from the table — keep them with the flag, so audits can see them.
