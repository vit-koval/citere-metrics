# Tasks layer — v1, as built

Cycle 1 · Ozempic · US. Built against `citere_tasks_integration_spec.md` (Steps 1–6). Replaces the platform's
task logic with `tasks/tasks.json` as the single source of "what to do". Money is untouched: the revenue-at-risk
layer (`docs/revenue_at_risk_layer_v1.md`) still owns every figure, and the full T1–T8 suite was re-run to prove it.

## What was built

| step | what |
|---|---|
| 1 | Read-only reconnaissance: `expected_pp` lives on `campaigns[]` (`step_07:49`), not on groups; `execution` 3 values, `agent` 16, `mlr` 2; the platform is fully static with no write path. |
| 2 | `expected_pp`, `execution`, `agent_id`, `agent_desc`, `mlr_gate` added to every task; `tasks/task_state.json` created with the archive-on-removal rule. |
| 3 | `#/priorities` rebuilt: tasks grouped by zone, zones by Σ $/week; lane B by severity; lane C by $/yr. Three old tables and the `?group=` route retired; tile 6 lists tasks. |
| 4 | `#/actions` rebuilt read-only: counters and status from `task_state.json`, filters lane/execution/mlr/status, deep link `?task=<id>`; all `localStorage` status code removed. |
| 5 | Point detail shows the task that covers the question; shared `taskDetailPanel` opens from both screens; `point_tasks` index added because per-task `pids` is capped at 40. |
| 6 | Dead code removed, glossary pruned, spec §7 corrected, this note written. |

## Final numbers

| | value |
|---|---|
| tasks | **79** — lane A 60 · lane B 9 · lane C 10 |
| types | T4 29 · T6 10 · T12 8 · T3 7 · T5 5 · T10 5 · T2 4 · T8 4 · T7 3 · T9 3 · T1 1 |
| lane A money | **$12 475 812 – $37 067 820** /yr, $5 357 200/week |
| lane C money | **$11 659 812 – $34 643 832** /yr |
| A + C | **$24 135 624 – $71 711 652** = `money_totals.api_usd_mo × 12` exactly |
| lane B | no money; ranked by severity; web-panel figure shown as information only |
| `expected_pp` | computed for 61 tasks (all 60 lane A + T1); null for T7/T8/T9 and T12 |
| `execution` | AGENT 44 · AGENT+APPROVE 23 · HUMAN TASK 12 |
| `agent_id` | A1 28 · A2 15 · B8 14 · F18 5 · G20 3 · E16 1 · H22 1 · null 12 |
| `mlr_gate` | true on 6 of 9 lane B tasks; the 3 false are the T9 provider-error-report tasks |
| status | 79 `open` in `tasks/task_state.json`, archive empty |

### Zones (lane A)

| zone | tasks | Σ $/yr | Σ $/week |
|---|---|---|---|
| STARTING & SWITCHING | 29 | $6.1–18M | $2 385 768 |
| WEIGHT LOSS | 17 | $3.5–10M | $1 618 624 |
| LIVING ON THE DRUG | 8 | $1.9–5.7M | $903 463 |
| BLOOD SUGAR & GLYCEMIC CONTROL | 2 | $0.7–1.9M | $322 794 |
| PRICE & ACCESS | 1 | $239–709K | $118 128 |
| SAFETY & CONTRAINDICATIONS | 3 | $20–60K | $8 423 |

### Closure-coefficient mapping (§1)

T2/T3/T4 → `owned` [0.05, 0.10] · T5 → `comp_owned` [0.10, 0.22] · T6 and T10 → `earned` [0.10, 0.22] ·
T1 → `ugc` [0.05, 0.15] · T7/T8/T9/T12 → null. The class also selects which owner-class lever to read out of
`groups[].lever`, which is a dict per owner class, not a scalar. `commerce` is defined in the config and unused.

## Invariants

| # | invariant | result |
|---|---|---|
| 2 | Σ lane A + lane C `usd_yr` == `api_usd_mo × 12` | **PASS**, exact |
| 3 | every api `pf=0` point in exactly one lane A/C task | **PASS**, 1 062 of 1 062, 0 duplicates, 0 missing; lane B covers 325 points separately |
| 4 | `task_state.json` ⊆ `tasks.json` ids | **PASS**, 79 == 79, archive empty |
| 5 | no screen reads `campaigns`, `label_tasks_awaiting_signoff`, `track_cards_by_group`, `prioritization.recommendations` | **PASS**, 0 references in the code of `ui/template.html` and `ui/index.html` |
| 6 | every point-detail task link resolves to a live task id | **PASS**, 1 424 points checked, 1 387 links, 0 broken |

### Money spec re-run after the integration

T1 PASS · T2 PASS · T3 PASS · T4 PASS (80 portfolio points) · T5 PASS (api 1 062 / web 282) ·
T6 PASS (0 strict ranking reversals at k=2) · T7 PASS (`platform_data.json` and `index.html` byte-identical) ·
T8 PASS (A = 1 015 794, +0.00%; B = 642 579, +0.00%; $24 135 624 – $71 711 652 /yr).

## The 92-point finding

§7 assumed a point without a task must be portfolio. It is not the only case. Of 1 424 points, 172 carry no task:

- **80** portfolio (`pf=1`) — as the spec expected;
- **92** web-panel points, all run R4, all cause `WORKING`, whose only fix card is "Keep this position: monitor
  the sources feeding it". They are type T1 (monitoring), and the T1 task is built only from api-panel orphans,
  so web-panel holders fall outside every lane. "Monitored only — no active task" is the correct reading for
  them; the spec's wording was too narrow and has been corrected in §7.

Also more common than §7 assumed: 104 points carry more than one task line (73 with two, 31 with three) because
lane B overlaps lane A/C and a point with T7+T8+T9 cards belongs to three lane B tasks.

## Deviations, steps 1–6

1. `groups[].lever` is a dict per owner class, not a scalar; the closure class selects which entry to read.
2. §1 maps no class to T12, so its 8 lane-C tasks carry `expected_pp: null` — a decision has no content lever.
3. The T2→T4 retype (page does not exist) left one point without a card of its new type; the original card is
   now carried across so `execution`/`agent_id` are never empty.
4. `ops_fields` reads the card of the task's own type, not every card on the point; §3 does not say which.
5. `agent_id` keeps only the first code of a composite (`A1/A7`→A1, `A2/A6`→A2, `B8/C12`→B8, `F18/C12`→F18,
   `E16/E17`→E16); the full string survives in `agent_desc`.
6. `mlr-compatible` on lane B was reported as 54 in Step 1 — an undercount from a truncated pid list. The true
   figure is 133 of 325 cards (T7 0/88, T8 102/206, T9 31/31). The spec was corrected.
7. Step 3 had to change `src/step_10_build_ui.py` to inline `tasks.json`; a static page cannot read it otherwise.
8. Helpers had to be hoisted functions, not `const`: the built file calls `render()` above their declarations.
9. `?group=` was redirected to the point's zone rather than deleted, so existing deep links keep working.
10. No "No action needed" section was built — `bucket=healthy` is empty in cycle 1.
11. Step 4 had to build `taskDetailPanel` (a §6 item) early, because §5's deep link needs somewhere to land.
12. `$ at stake/mo` is derived as `usd_yr / 12`; there is no monthly field in `tasks.json`.
13. Step 5 had to change the builder: per-task `pids` is capped at 40, hiding 433 points, so a full
    `point_tasks` index is emitted at the top level of `tasks.json`.
14. The point-detail section was renamed "What is being done about it"; the old title promised a card list.
15. The `#/point/<key>?open=<fix index>` deep link was removed with the cards it opened.
16. Tiles 0 and 7 were re-pointed at the tasks layer in Step 6: tile 0 lists top zones, tile 7 counts tasks by
    status and lists the three open tasks with the highest $/week.
17. Four glossary entries (`failure_code_share`, `no_campaign`, `task_actions`, `view_toggle`) were removed after
    confirming zero references; eight more are now unused but still referenced conceptually and were left alone.
