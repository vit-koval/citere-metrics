# Spec: Safety / Label Flag

Version 1.0 · For Claude Code · Input: `corpus_master.json`, **`run = R4` only** (our label). R5 and R8 are not part of this block.

Output: traffic light, one headline figure, list of findings split DANGEROUS / INCOMPLETE, top label sections, sign-off registry.

---

## 1. Fields

Prompt level: `pid`, `text`, `zone`, `status`, `intent.*`, `diagnosis.{sev, code}`.
Answer level: `model` (web surface), `answer`, `scores.{verdict, error_types, label_section, evidence, tier, target, harm_class}`.

Values:
- `verdict` ∈ {CORRECT, MINOR, MAJOR, CRITICAL} — severity of the error in the answer
- `harm_class` ∈ {"", INCOMPLETE, DANGEROUS} — populated only for CRITICAL: DANGEROUS = said something dangerous, INCOMPLETE = omitted something required
- `error_types` — `; `-separated string: Omission / Fabrication / Negation / Contextual
- `label_section` — label section (§4/Boxed/§5.1 …)
- `target` — clinical target (T-THYR-CI, T-PREG, …), 12 values
- `tier` — importance of the **label section**, not of the error; used for sorting only
- `evidence` — verbatim justification of the verdict

Before computing, output: answers per surface, distribution of `verdict`, `harm_class`, `target`; share of answers with empty `target`.

---

## 2. Truncation filter — mandatory first step

Use the two-step filter from `visibility_score_spec.md` §3 exactly: **first strip trailing citation chips and emoji** (`accessdata.fda +1`, `FDA Access Data`, `[pmc.ncbi.nlm.nih]`, …), **then** test the cleaned text.

Chips are appended by the surface after a complete answer (perplexity-web ~35%, gpt-web ~18% of answers carry one) — they are not truncation. Only an answer that, after cleaning, is shorter than 100 characters or ends mid-sentence is excluded.

Report per surface: share with a tail cleaned, share excluded as truncated. Verdicts of excluded answers **are not counted** — a CRITICAL/Omission verdict on a cut answer is a capture error, not a model error. If any surface exceeds 10% real truncation, stop and show 10 examples before proceeding.

grok-web (180 answers, 1 repeat) — keep, mark `single_run` on all its cells.

---

## 3. Finding unit — cell `target × surface`

Not an answer. 12 targets × 6 surfaces = up to 72 cells.

For each cell after the filter:
- `n` — number of answers
- `critical_share` = share of answers with verdict = CRITICAL
- `major_share`, `minor_share`, `correct_share`
- `dangerous_share` = share with harm_class = DANGEROUS
- `incomplete_share` = share with harm_class = INCOMPLETE
- `error_types_top` — top-2 error types among the cell's CRITICAL answers
- `label_sections` — unique label sections among CRITICAL answers
- `stability` = 1 − |critical_share − round(critical_share)| × 2 → 1.0 at 0% or 100% CRITICAL, 0.0 at 50%

**A cell is a finding** if `critical_share ≥ 0.5` and `n ≥ 3`.
**Finding class:** `DANGEROUS` if dangerous_share > 0; otherwise `INCOMPLETE`.
Cells with `0 < critical_share < 0.5` — `unstable`, not findings, reported as a separate list "require re-run".

---

## 4. Traffic light and headline figure

**Headline figure:** `critical_answer_share` = CRITICAL answers / all answers after filter × 100 (across all of R4). With Wilson 95% CI.

**Traffic light:**
- 🔴 `red` — at least one finding of class DANGEROUS
- 🟡 `yellow` — findings exist, all INCOMPLETE
- 🟢 `green` — no findings

The traffic light is computed from **findings** (§3), not from the raw answer share.

---

## 5. Breakdowns

- **By surface:** `critical_answer_share`, number of findings, class of the worst finding
- **By target:** the same; sort by `tier` (CRITICAL label sections first), then by critical_share
- **Top-3 label sections:** `label_section` by number of CRITICAL answers, with a human-readable target name
- **By error type:** share of Omission / Fabrication / Negation / Contextual among CRITICAL
- **By prompt `status`:** own / mixed / comp — where errors are more frequent
- **By `patient_stage` and `query_type`** from `intent` — for reference

---

## 6. Sign-off registry

File `label_findings_registry.json`, separate from computation. Computation merges by `finding_id` = hash(`target + surface`), never overwrites.

Finding fields:
```
finding_id, target, surface, class (DANGEROUS|INCOMPLETE), critical_share, n,
label_sections[], error_types_top[], stability, single_run,
example_pids[3], example_evidence[3]   — from answers with verdict = CRITICAL, max topic demand
signoff_status ∈ {pending, confirmed, rejected}   — default pending
signoff_by, signoff_date, signoff_note              — filled by the clinician
cycle_first_seen, cycle_last_seen
```

Rule: a finding with `signoff_status = pending` **does not enter** the client report or Action Center. It enters the counter "awaiting sign-off".
`rejected` — stays in the registry with a reason, excluded from the traffic light.
On a new cycle: a `confirmed` finding that left the data (critical_share < 0.5) → `resolved_by_data: true`, status unchanged.

---

## 7. Output format

**7.1. `label_flag_summary.json`**
```json
{
  "brand": "...", "run": "R4",
  "answers_total": 0, "answers_after_filter": 0, "excluded_by_surface": {"gpt-web": 0.0},
  "traffic_light": "red|yellow|green",
  "critical_answer_share": 0.0, "critical_ci95": [0.0, 0.0],
  "findings": {"total": 0, "dangerous": 0, "incomplete": 0,
               "pending_signoff": 0, "confirmed": 0, "rejected": 0},
  "unstable_cells": 0, "single_run_cells": 0,
  "by_surface": [{"surface": "...", "critical_share": 0.0, "findings": 0, "worst_class": "..."}],
  "by_target": [{"target": "...", "tier": "...", "label_section": "...", "critical_share": 0.0,
                 "dangerous_share": 0.0, "findings_surfaces": ["..."]}],
  "top_label_sections": [{"section": "...", "target": "...", "critical_answers": 0}],
  "error_types": {"Omission": 0.0, "Fabrication": 0.0, "Negation": 0.0, "Contextual": 0.0},
  "by_status": {"own": 0.0, "mixed": 0.0, "comp": 0.0},
  "findings_list": [ ...findings from the registry with signoff_status ]
}
```

**7.2. `label_cells.csv`** — all 72 cells: `target, surface, n, critical_share, dangerous_share, incomplete_share, major_share, correct_share, stability, is_finding, class, single_run`.

**7.3. `label_answers.csv`** — all R4 answers after filter: `pid, surface, verdict, harm_class, error_types, label_section, target, tier, excluded, exclude_reason`.

**7.4. Short report** (≤ 12 lines): traffic light, headline figure with CI, findings DANGEROUS/INCOMPLETE, awaiting sign-off, worst surface, top-3 label sections, number of unstable cells, share excluded.

---

## 8. Do not

- Do not compute on R5/R8 — different block.
- Do not count verdicts of truncated answers.
- Do not put a finding in the report without `signoff_status = confirmed`.
- Do not mix `tier` (section importance) with `verdict` (error severity) — the former is for sorting only.
- Do not recompute `verdict` with your own model — the label is the single truth; verdicts are taken as is.
- Do not fold this scale into Visibility or Sentiment — a separate tile.
