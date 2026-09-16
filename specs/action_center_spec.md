# Spec: Action Center

Version 1.0 · For Claude Code · Input: `prioritization_summary.json` (output of Diagnosis & Prioritization) + `corpus_master.json` for reference fields.

Action Center computes nothing new. It turns prioritization rows into tasks and tracks their status across measurement cycles.

---

## 1. Task = prioritization row

One row from `recommendations[]` or `label_recommendations[]` → one task. Fields carried over as is: `group`, `owner` (source type), `what`, `who`, `speed`, `priority`, `score`, `why`, `cause`, `where`, `examples`.

Five fields added: `execution`, `status`, `cycle`, `impact`, `task_id`.

`task_id` = stable hash of `group_id + owner` — so the task keeps its identity across cycles.

---

## 2. Execution type (`execution`)

By source type of the task:

| Source `owner` | `execution` | Meaning |
|---|---|---|
| `owned` | `auto` | extractability diagnostics and a prepared fix package for our domains; applied by the client's team, not by us |
| `earned`, `commerce`, `ugc`, `comp_owned` | `manual` | task for the client's team |
| Label rows (`lever = null`) | `manual` | Medical / Regulatory |

Separately: if `fixes[].owner` is `Citere` (monitoring, escalation, re-check) — this is our task, not the client's. Mark `execution: citere`, exclude from client counters, keep in a separate list.

---

## 3. Status and cycle

`status` ∈ {`open`, `in_progress`, `done`, `dismissed`}. Changed by the client's team, not by computation.
`dismiss_reason` — required when `dismissed`, free text.
`cycle_opened` — measurement cycle in which the task appeared.
`cycle_done` — cycle in which it was moved to `done`; null otherwise.

On a new cycle:
- a task with the same `task_id` already exists → keep status, update `why`/`score`/`priority` from the new computation
- task not present in the new computation (topic left the gap) → do not change status, mark `resolved_by_data: true`
- new row without a `task_id` in the registry → `open`, `cycle_opened` = current

The task registry is stored separately from the computation: `action_center_tasks.json`. Computation never overwrites it — only merges by `task_id`.

---

## 4. Expected impact (`impact`)

Two numbers, both from prioritization data:

**4.1. Ceiling** — `impact.ceiling_pp` = `gap × lever × 100`
How many percentage points of the topic's loss rest on this source type. For Label rows — `gap × 100` (no lever).

**4.2. Expected shift** — `impact.expected_pp` = `[ceiling_pp × k_lo, ceiling_pp × k_hi]`

Closure coefficients by task type — a prior from industry data, config `closure_coefficients`:

| `owner` | `k_lo` | `k_hi` |
|---|---|---|
| owned | 0.05 | 0.10 |
| earned, commerce, comp_owned | 0.10 | 0.22 |
| ugc | 0.05 | 0.15 |
| Label rows | not computed — `expected_pp: null` |

`impact.basis` = `prior` until measured values exist. After ≥2 Before/After cycles the coefficient is replaced by the measured one: median gap shift across groups with `done` tasks of that owner. Then `basis: measured`, `n_groups` — number of groups measured. Replace only if `n_groups ≥ 5`; otherwise stay on `prior`.

**4.3. Demand — for reference.** `impact.demand` = `demand`, `lo`, `hi` from the group. Do not show in the task headline as queries; caption in output: "topic demand, Google, proxy".

Example row:
```
Weight loss without diabetes → earned · P3 · manual · Digital + PR
Losing 71% of topic answers · earned = 58% of citations
Ceiling: 41 pp · Expected: −4…9 pp (prior) · Topic demand ~67K/month
```

---

## 5. Counters for the main screen

From the registry, client tasks only (`execution ∈ {auto, manual}`):

```
open_total, open_auto, open_manual
in_progress
done_this_cycle   — cycle_done == current
dismissed_total
top3_open         — three open tasks with the highest score
by_who            — open tasks by who (Digital / PR / Medical / …)
```

---

## 6. Output format

**6.1. `action_center_tasks.json`** — registry:
```json
{
  "cycle_current": 1,
  "tasks": [
    {"task_id": "...", "group": {...}, "owner": "earned", "execution": "manual",
     "priority": 3, "score": 0.0, "what": "...", "who": "Digital + PR", "speed": "weeks",
     "status": "open", "dismiss_reason": null, "cycle_opened": 1, "cycle_done": null,
     "resolved_by_data": false,
     "why": {...}, "cause": [...], "where": [...], "examples": [...],
     "impact": {"ceiling_pp": 0.0, "expected_pp": [0.0, 0.0], "basis": "prior", "n_groups": null,
                "demand": 0, "lo": 0, "hi": 0}}
  ],
  "citere_tasks": [ ...same format, "execution": "citere" ],
  "counters": {"open_total": 0, "open_auto": 0, "open_manual": 0, "in_progress": 0,
               "done_this_cycle": 0, "dismissed_total": 0,
               "by_who": {"Digital": 0, "PR": 0, "Medical": 0}},
  "closure_coefficients": {"owned": [0.05, 0.10], "earned": [0.10, 0.22], "commerce": [0.10, 0.22],
                           "comp_owned": [0.10, 0.22], "ugc": [0.05, 0.15]},
  "coefficient_basis": "prior"
}
```

**6.2. `action_center_queue.csv`** — one row per task: `task_id, priority, execution, who, status, topic, subtopic, zone, owner, what, ceiling_pp, expected_lo_pp, expected_hi_pp, basis, demand, top_domain, cycle_opened, cycle_done`. Sort: status (open → in_progress → done → dismissed), then score.

**6.3. Short report** (≤ 10 lines): counters, top-3 open tasks in the §4 row format, number of citere tasks.

---

## 7. Do not

- Do not recompute `score`, `gap`, `lever` — take from prioritization only.
- Do not change `status` by computation — only the team, via the registry.
- Do not delete tasks from the registry when they disappear from the computation — mark `resolved_by_data`.
- Do not show `expected_pp` without `basis`; do not show a single figure instead of a range.
- Do not write or publish content, even for `auto`.
- Do not estimate timelines or budget — `speed` is shown as a reference from the data.
