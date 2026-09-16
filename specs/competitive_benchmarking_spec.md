# Spec: Competitive Benchmarking — Win Rate and Competitive Impact

Version 1.0 · For Claude Code · Input: the same consolidated JSON as `visibility_score_spec.md`. Brand dictionary, prompt classification (C1–C4), quality filters and position rules are **taken from that spec unchanged**. Only additions are described here.

INN rule applies here as in the visibility spec: a competitor is present only by trade name; "tirzepatide" alone is not Mounjaro and not Zepbound.

Two metrics:
- **Win Rate** — how often we rank above a competitor when both are in the same answer.
- **Competitive Impact** — how many answers a competitor takes from us.

---

## 1. Which answers we use

| Class | Used | Why |
|---|---|---|
| C1 · unbranded | **yes, primary** | neutral question, both brands on equal footing (Yext method: win rate on unbranded queries) |
| C2 · own-branded | no | our brand in the question → always first, duel is meaningless |
| C3 · comp-branded | no for Win Rate | competitor in the question → always first, mirror-meaningless |
| C4 · compare ("A vs B") | **yes, separately** — "Duel Verdict" block (§5) | a direct duel, but measured by verdict, not position |

Apply quality filters from visibility spec §3 before anything.

---

## 2. Per-answer level (C1)

For each answer and **each competitor X in the dictionary** determine:

- `we_present` ∈ {0,1}, `x_present` ∈ {0,1}
- `we_pos`, `x_pos` — position by order of first appearance in text (visibility spec §4.2); null if absent
- `overlap` = 1 if we_present = 1 **and** x_present = 1
- `win` = 1 if overlap = 1 and we_pos < x_pos; 0 if overlap = 1 and we_pos > x_pos; null if overlap = 0
  (equal positions are impossible — position is by first-character index; if they are nevertheless equal — `win` = 0.5, log it)
- `loss_type`:
  - `by_position` — overlap = 1 and win = 0
  - `by_absence` — x_present = 1 and we_present = 0
  - null — otherwise

Intermediate table (one row per answer × competitor):
```
pid, model, repeat_idx, competitor, we_present, x_present, we_pos, x_pos, overlap, win, loss_type
```

---

## 3. Win Rate

**Level 1 — prompt × model × competitor** (over repeats):
- `overlap_pm` = mean(overlap)
- `win_pm` = mean(win) over repeats with overlap = 1; null if none

**Level 2 — model × competitor** (over prompts where win_pm is not null):
- `win_m(X)` = mean(win_pm)
- `n_overlap_m(X)` = number of prompts with overlap_pm > 0

**Level 3 — overall × competitor** (over models, equal weights; `model_weights` from config if set):
- `Win Rate(X)` = mean(win_m(X)) × 100

**Overall Win Rate (all competitors):** mean of `Win Rate(X)`, weighted by each competitor's `n_overlap` — otherwise a rare competitor with 3 overlaps weighs as much as the main one with 300.

Threshold: if a competitor has < 20 overlap answers in total — report Win Rate(X) with flag `low_n`.

---

## 4. Competitive Impact

Answers: "how many answers does X take from us".

**Level 1 — prompt × model × competitor:**
- `lost_pm(X)` = share of repeats where loss_type ∈ {by_position, by_absence}
- `lost_pos_pm(X)` = share of repeats with loss_type = by_position
- `lost_abs_pm(X)` = share of repeats with loss_type = by_absence

**Levels 2 and 3** — mean over prompts, then over models, as in §3.

**Result per competitor:**
- `Impact(X)` = mean over all C1 prompt×model groups of `lost_pm(X)` × 100
  → "X takes N% of category answers from us"
- `Impact_split(X)` = {by_position: …, by_absence: …} — the same percentages separately

This is the prioritization: sort competitors by `Impact(X)`, not by Win Rate.

The split is the diagnosis:
- `by_position` dominates → we are named, but lower. Authority/position problem.
- `by_absence` dominates → we are not named where they are. Presence/topic-coverage problem.

---

## 5. Duel Verdict (class C4, separate block)

"A vs B" prompts are not scored by position — in a comparative answer the brand order is set by the question. Use the ready verdicts from `scores` (R2: `winner` ∈ {ours, comp, split, none, na}).

- `duel_win_rate` = (ours + 0.5 × split) / (ours + comp + split), over repeats → prompts → models
- `none` and `na` — excluded from the denominator, report their share separately (R2 — 48% na on `status=mixed` prompts; these are family pairs, not our duel pair)
- Breakdown by competitor in the prompt and by model (R2: gpt-4o is the most pro-competitor judge)

If the consolidated JSON has no verdict field — skip the block and report; do not derive a winner from text.

---

## 6. Mandatory breakdowns

For Win Rate and Impact — by competitor × by model. Additionally by prompt `zone` (already in the data) — "in which question zone do we lose the most".

Competitor leaderboard table (main output of the block):
```
competitor | overlap_answers | Win Rate | Impact | Impact by_position | Impact by_absence | worst_model | worst_zone
```
Sort — by Impact descending.

---

## 7. Reliability

- `stability` for prompt×model×competitor groups: share of repeats with identical `win`. Report share of unstable groups (R2 — 24% flip the winner between repeats).
- Wilson 95% CI for Win Rate(X) by number of overlap answers.
- Single-repeat groups — keep, mark `single_run`, report the share.

---

## 8. Output format

**8.1. `benchmark_summary.json`**
```json
{
  "brand": "...",
  "run_ids": [...],
  "answers_C1_used": 0,
  "overall": {"win_rate": 0.0, "win_rate_ci95": [0,0], "n_overlap_answers": 0},
  "leaderboard": [
    {"competitor": "Mounjaro", "overlap_answers": 0, "win_rate": 0.0, "win_rate_ci95": [0,0],
     "impact": 0.0, "impact_by_position": 0.0, "impact_by_absence": 0.0,
     "worst_model": "...", "worst_zone": "...", "low_n": false}
  ],
  "by_model": [
    {"model": "...", "win_rate": 0.0, "top_impact_competitor": "..."}
  ],
  "by_zone": [
    {"zone": "...", "win_rate": 0.0, "top_impact_competitor": "..."}
  ],
  "duel_verdict": {
    "available": true, "duel_win_rate": 0.0, "n_scored": 0, "excluded_na_pct": 0.0,
    "by_competitor": {"Mounjaro": 0.0}, "by_model": {"gpt-4o": 0.0}
  },
  "quality": {"unstable_groups_pct": 0.0, "single_run_groups_pct": 0.0, "ties_logged": 0}
}
```

**8.2. `benchmark_by_prompt.csv`** — C1 prompt × competitor: `pid, text, zone, competitor, overlap_pm, win_pm, lost_pm, lost_pos_pm, lost_abs_pm, stability`.

**8.3. `benchmark_pairs.csv`** — the full table from §2.

**8.4. Short report** (≤ 15 lines): overall Win Rate, top-3 competitors by Impact with position/absence split, worst model, worst zone, share of unstable groups.

---

## 9. Do not

- Do not compute Win Rate on C2/C3 — position there is set by the question.
- Do not merge position-based Win Rate (C1) and Duel Verdict (C4) into one figure — different nature.
- Do not include non-dictionary competitors in Impact; unknown brands go to `unknown_brands` of the visibility spec.
- Do not sort the leaderboard by Win Rate — only by Impact.
- On schema mismatch — stop and ask.
