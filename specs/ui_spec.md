# Spec: Platform UI — three levels on one data file

Version 1.0 · For Claude Code · Reads `data/metrics/cycle_01/platform_data.json` (step 9) and, lazily, `data/raw/corpus_master.json` for answer texts. Builds on the existing Evidence Base HTML (`ui/evidence_base_legacy.html`): reuse its design tokens, table, point detail panel and the Neural map block unchanged; replace its embedded DATA and its own calculations entirely.

Rule: **the UI never computes.** Every number is read from `platform_data.json`. If a number is not in the file, the UI does not show it.

Output: `ui/index.html`, self-contained (data inlined at build time by `src/step_10_build_ui.py`), light/dark tokens, no external scripts except Google Fonts.

---

## Level 1 — Master Dashboard (route `#/`)

Eight tiles, grid as in the approved mockup (`citere_cmo_master_screen.html`), each showing exactly what `dashboard.<block>` holds. Deltas render only when `dashboard.before_after.available` is true; otherwise the tile shows "first cycle".

| Tile | Reads | Click → |
|---|---|---|
| Visibility Score | `dashboard.visibility` | `#/visibility` |
| Competitive Benchmarking | `dashboard.benchmarking` | `#/competitors` |
| Sentiment | `dashboard.sentiment` (R3 headline; R9 as a second line "under myth probes") | `#/sentiment` |
| Citation Tracking | `dashboard.citations` | `#/sources` |
| Diagnosis & Prioritization | `dashboard.prioritization` top-3 | `#/priorities` |
| Action Center | `dashboard.action_center` counters + top-3 | `#/actions` |
| Safety / Label | `dashboard.safety_label` traffic light + counts + "awaiting sign-off: N" | `#/safety` |
| Before / After | `dashboard.before_after` | disabled until available |

Header: brand, cycle, period, prompts/answers/surfaces from `meta`. One button "Export one-page PDF" → `window.print()` with a print stylesheet that renders only Level 1.

---

## Level 2 — working screens (routes `#/<block>`)

Each screen = its block's breakdowns + a filtered point table at the bottom. Filters are URL-hash parameters (`#/priorities?group=...`, `#/sources?domain=...`, `#/safety?target=...&surface=...`) so every drill is a link.

**#/visibility** — by model family (table + bars), by zone, by topic group; INN-only column; CI shown as a range, never hidden. Point table filter: `run=R1`.

**#/competitors** — leaderboard by Impact (with by_position / by_absence split), duel win rate by competitor, by zone, by family. Click a competitor → point table filtered to points where that competitor is present and we are absent or lower.

**#/sentiment** — R3 block: score, shares, B-themes with examples. R9 block, visually separated, titled "under myth probes (adversarial by design)": score, shares, NR-themes with negative rate per family. Point table filter: `run=R3` or `run=R9`, `sev=bad`.

**#/sources** — owner pie, earned subtypes, top-domains table, gap list, adversarial list (separate, red). Click a domain → point table of points citing it.

**#/priorities** — three sub-lists: Recommendations (groups, one row per group, owners as sub-rows with lever and ceiling), Healthy groups (with `failure_code_share`), Label / Medical rows. Each group row shows: three numbers (demand, gap with dominant run, lever), dominant code as title, dominant cause as sub-line, reach ceiling. Click a group → `#/priorities?group=<id>` — the point list of that group ordered by `point_rank_score`.

**#/actions** — campaigns (client tasks) grouped by status; each campaign expands to its fix cards (`audience: client`), each card shows type, platform_execution, MLR status, owner, speed, URL, why. Status controls (open / in progress / done / dismissed + reason) write to `localStorage` only and show a "not synced to registry" badge — persistence to the registry is out of scope for the UI. Collapsed section at the bottom: "Citere monitoring" (`citere_tasks`), hidden by default.

**#/safety** — traffic light, headline share with CI, findings table (class, cell, share, n, stability, sign-off status, scoring caveat), by surface, by target, top label sections, unstable cells list. Findings with `pending` are shown with a grey "awaiting sign-off" badge and are excluded from any count labelled "confirmed". Click a finding → point table of R4 answers in that cell.

**#/map** — the Neural map, unchanged.

---

## Level 3 — point (route `#/point/<pid>|<run>`)

Reuse the existing detail panel layout. Sections in order:
1. Question, zone, topic, stage, query type, class; sev + code label; dominant cause with confidence.
2. Metrics (from `points.metrics`): answers, presence share, position, INN-only, per-family row, competitors present, citation split, run-specific fields.
3. Diagnosis text (from export).
4. Evidence lines (from export).
5. Sources: top domains with owner/subtype; SERP snapshot; inventory.
6. Answers: loaded lazily from `corpus_master.json` by `answers_ref`; one per model × repeat, with `excluded` flag visible; citations under each.
7. Fix cards: client cards first, then a collapsed "Citere monitoring" block.

Prev/next within the current filtered list.

---

## Point table (shared component)

Columns: pid, run, question, topic/subtopic, sev, code, cause, presence %, position, models, demand, rank score. Sortable; default sort = the caller's order (group order by rank score, else demand desc). Filters: run, zone, topic, subtopic, model family, query type, stage, code, cause, sev, text search — the legacy filter bar, re-pointed at the new fields.

---

## Build

`src/step_10_build_ui.py`: reads `ui/template.html` + `platform_data.json` → writes `ui/index.html` with data inlined; also copies `corpus_master.json` next to it for lazy answer loading (or inlines the answers gzipped if the total stays under 16 MB — decide at build time, report which). Deterministic. Publish `ui/index.html` as the artifact.

---

## Do not

- No calculations in JS beyond formatting, sorting and filtering.
- No number shown without its source in `platform_data.json`.
- No `cause`, diagnosis or fix text edited or generated in the UI.
- No status persistence claims: localStorage only, badge says so.
