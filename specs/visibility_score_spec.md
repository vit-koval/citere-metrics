# Spec: Visibility Score (Evertune method, adapted)

Version 1.0 · For Claude Code · Input: consolidated run JSON for the drug (`corpus_master.json`).

Goal: compute three brand-visibility metrics and two "intrusion" metrics; output JSON + tables. Every decision below is fixed — do not change without a note in the report.

---

## 1. Input data

Expected structure:

```
{meta, prompts: [{pid, run, text, zone, tags, status, code, diagnosis, n, intent, models[], topic_traffic}]}
models[i]: {model, answer, citations[], sentiment, visibility, mentioned, scores{...}}
```

- `status` on the prompt: `own` / `comp` / `mixed` — whose brand is in the question text (a hint, not ground truth — see §2).
- `models[]` — list of answers; one element = one answer (prompt × model × repeat).
- `scores` may contain `our_rank` / `our_status` (M/R/A/EMPTY) / `consideration_set` — use when present.
- `mentioned` — brands in the answer (free strings; normalize via the dictionary).

**Step one — schema inspection.** Before computing, print: prompt-level and answer-level fields, list of models, repeats per prompt×model (min/median/max), share of answers with empty `mentioned`. If fields differ from the above — report and propose a mapping; do not guess.

**Brand dictionary** (required config, supplied separately):
```
OUR_BRAND: ["Ozempic"]                                   # trade name spellings only
OUR_INN: ["semaglutide"]                                 # active ingredient — NOT a brand match
COMPETITORS: {"Mounjaro": ["Mounjaro"], "Wegovy": ["Wegovy"], "Zepbound": ["Zepbound"], ...}
COMPETITOR_INN: {"tirzepatide": ["Mounjaro", "Zepbound"], "liraglutide": ["Victoza", "Saxenda"], ...}
```
Matching — normalized string (lowercase, no punctuation), word boundaries.

**Brand = trade name only.** An INN does not count as brand presence: "semaglutide" without "Ozempic" may mean Wegovy or Rybelsus; "tirzepatide" may mean Mounjaro or Zepbound. This matches the existing R1 scoring (`our_status = A` on 371 answers that mention only semaglutide). INN mentions are tracked as a separate counter `inn_only_mention` — "active ingredient named without the brand" — reported next to Visibility, never added to it. The same rule applies to competitors: an INN mention is not attributed to any competitor brand.

Brands not in the dictionary are ignored but counted and reported as `unknown_brands` (hallucination check, e.g. "Garzulys").

---

## 2. Prompt classification

Classify **by prompt text via the dictionary**, not by the `status` field. `status` is for cross-checking; report mismatches.

| Class | Condition | What we compute |
|---|---|---|
| **C1 · unbranded** | no dictionary brand in the text | Visibility %, Average Position, AI Brand Score |
| **C2 · own-branded** | our brand present, no competitors | Competitor Intrusion |
| **C3 · comp-branded** | competitor(s) present, ours absent | Our Intrusion |
| **C4 · compare** | both ours and a competitor | excluded here (goes to Competitive Benchmarking) |

Rule: **Visibility Score is computed on C1 only.** C2 prompts must not be included — our brand appears in almost every answer there (R7: 100% trivially) and would inflate the number.

Cycle-1 decision: the headline Visibility %, Average Position and AI Brand Score are computed on **R1 C1 prompts only** (the category corpus). C1 prompts from other runs (R2, R3, R5, R6) are reported in a separate `c1_other_runs` block for reference and are not in the headline — R6 prompts are message-triggered and R5 are web probes; neither is a neutral category question.

---

## 3. Quality filters (apply before computing)

**3.1. Clean the tail first.** Strip from the end of `answer`, repeatedly, until nothing matches:
- citation chips: `\s*\[?[a-z0-9.-]+\]?\s*\+\d+$`, `\s*FDA Access Data$`, `\s*\[[a-z0-9.-]+\]$` (e.g. `accessdata.fda +1`, `[accessdata.fda]`, `FDA Access Data`)
- trailing emoji and whitespace

These are appended by the surface after a complete answer (perplexity-web ~35%, gpt-web ~18%, Claude emoji sign-offs ~18%) — they are **not** truncation.

**3.2. Then exclude** an answer if, after cleaning:
- it is empty or shorter than 100 characters;
- it does not end with `.!?)»"` — the text is cut mid-sentence (real truncation);
- the last 60 characters contain a chip pattern from 3.1 immediately preceded by a non-terminal character (chip glued to a cut sentence, e.g. `is contraind FDA Access Data`).

Report: how many answers excluded, by reason, by model; and separately the share of answers that had a tail cleaned. Expected real truncation after cleaning: low single digits per surface; if a surface exceeds 10%, stop and show 10 examples before proceeding.

**3.3. Drop** the single stray `gemini-3.6-flash` record (1 answer).

---

## 4. Per-answer computation (C1)

For each answer determine:

**4.1. present** — is our brand in the answer (dictionary match on full `answer`; `mentioned` field for cross-check). `present ∈ {0, 1}`.

**4.2. position** — ordinal of our brand among all dictionary brands by **order of first appearance in the answer text**. First brand mentioned = position 1. If `scores.our_rank` already holds a position — use it, attach the text-based computation as a check; flag if they differ by >1.
If `present = 0` — `position = null`.

**4.3. weight** — Evertune position weight:
```
weight(pos) = 100 × 0.9^(pos − 1)
```
Position 1 → 100, 2 → 90, 3 → 81, 4 → 72.9, 5 → 65.6, … Absent → 0.

Intermediate table (one row per answer):
```
pid, model, repeat_idx, class, present, position, weight, brands_in_answer[], excluded, exclude_reason
```

---

## 5. Aggregation

Strictly bottom-up, simple mean at every level. Do not mix levels.

**Level 1 — prompt × model** (mean over repeats):
- `vis_pm` = mean(present)
- `pos_pm` = mean(position) over answers with present = 1; null if none
- `score_pm` = mean(weight)

**Level 2 — model** (mean over C1 prompts):
- `vis_m` = mean(vis_pm)
- `pos_m` = mean(pos_pm) over prompts where pos_pm is not null
- `score_m` = mean(score_pm)

**Level 3 — overall** (mean over models, equal weights):
- `Visibility %` = mean(vis_m) × 100
- `Average Position` = mean(pos_m)
- `AI Brand Score` = mean(score_m)

Why repeats first, then prompts: otherwise prompts with more repeats (R8 — ×10) outweigh prompts with ×2–3.

Why equal model weights: country-level model usage shares are not defined yet. Keep a `model_weights` config parameter defaulting to "equal"; if set — weighted mean at level 3.

**Model families.** Several versions of one vendor's model appear in the data (R1: `claude-sonnet-4-6` and `claude-sonnet-5` — the panel changed mid-run). Treat versions of one family as **one model** at level 2 (pool their prompt×model groups under `claude`), otherwise the family gets double weight at level 3. Config `model_families: {"claude": ["claude-sonnet-4-6", "claude-sonnet-5"], ...}`. Report the per-version figures in `by_model_version` for reference only.

**Scope note.** C1 exists only in R1 (250 prompts) and R6 (59), all on API models. There are no unbranded prompts on web surfaces (ChatGPT web, Perplexity, Google AI Overviews) — R4/R5 are branded. Visibility on web surfaces cannot be computed from this corpus; state this explicitly in the report rather than leaving those surfaces blank.

**Additional (not headline):**
- `Visibility % among brand-bearing answers` — same, but the denominator is only answers containing at least one dictionary brand (Profound method). Report alongside; do not mix.

---

## 6. Intrusion (classes C2 and C3)

**C2 · Competitor Intrusion** — "in answers about us, a competitor appears in X%":
- per answer: `comp_present` = 1 if at least one dictionary competitor is in the answer;
- aggregate as in §5 (repeats → prompts → models → overall);
- additionally, per competitor: share of answers with each specific competitor.

**C3 · Our Intrusion** — "in answers about a competitor, we appear in Y%":
- per answer: `present` of our brand (as in §4.1);
- aggregate as in §5;
- breakdown by which competitor the question was about.

---

## 7. Reliability

- **Repeats.** For each prompt×model group compute `stability` = share of repeats with identical `present`. Report share of unstable groups (R1 — 44%, R2 — 24%). If repeats < 2 — mark the group `single_run`, keep in aggregation, report the share of such groups.
- **Confidence interval** for `Visibility %` at model and overall level — Wilson 95% by number of answers (not prompts). Output as `[low, high]`.
- **Minimum publication threshold:** if a model has fewer than 30 C1 answers after filters — flag the model's figures `low_n`.

---

## 8. Output format

**8.1. `visibility_summary.json`**
```json
{
  "brand": "...",
  "run_ids": [...],
  "config": {"position_decay": 0.9, "model_weights": "equal", "min_answer_len": 100},
  "counts": {"prompts_total": 0, "prompts_by_class": {"C1":0,"C2":0,"C3":0,"C4":0},
             "answers_total": 0, "answers_excluded": 0, "answers_C1_used": 0},
  "headline": {
    "ai_brand_score": 0.0,
    "visibility_pct": 0.0, "visibility_ci95": [0.0, 0.0],
    "average_position": 0.0,
    "visibility_pct_brand_bearing_only": 0.0,
    "inn_only_mention_pct": 0.0
  },
  "scope": {"c1_runs": ["R1"], "surfaces_covered": ["api"], "surfaces_not_covered": ["gpt-web", "perplexity-web", "google-ai", "gemini-web", "claude-web", "grok-web"]},
  "by_model": [
    {"model": "claude", "versions": ["claude-sonnet-4-6", "claude-sonnet-5"], "n_answers": 0, "ai_brand_score": 0.0, "visibility_pct": 0.0,
     "visibility_ci95": [0,0], "average_position": 0.0, "inn_only_mention_pct": 0.0, "unstable_groups_pct": 0.0, "single_run_groups_pct": 0.0, "low_n": false}
  ],
  "by_model_version": [ ...same fields per raw model string, reference only ],
  "intrusion": {
    "competitor_into_ours_pct": 0.0, "by_competitor": {"Mounjaro": 0.0},
    "ours_into_competitor_pct": 0.0, "by_competitor_asked": {"Mounjaro": 0.0}
  },
  "quality": {"excluded_by_reason": {...}, "status_vs_text_mismatches": 0,
              "unknown_brands": {"Garzulys": 3}, "single_run_groups_pct": 0.0}
}
```

**8.2. `visibility_by_prompt.csv`** — one row per C1 prompt: `pid, text, zone, n_answers, vis, avg_pos, score, stability, best_model, worst_model`.

**8.3. `visibility_answers.csv`** — the full intermediate table from §4 (for audit).

**8.4. Short text report** (≤ 15 lines): headline figures, spread across models, share excluded, three main data anomalies.

---

## 9. Do not

- Do not weight prompts by search volume — in this version all C1 prompts are equal.
- Do not mix C2/C4 into Visibility Score at any level.
- Do not use the `visibility` (0–100) score field as a ready metric — it is a legacy field of a different nature; you may report its correlation with our `score_pm` for reference.
- Do not smooth or round to integers at intermediate levels; rounding only in the final report (1 decimal).
- On any schema ambiguity — stop and ask instead of picking an interpretation.
