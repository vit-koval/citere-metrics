# Spec: Platform UI — three levels on one data file

Version 1.0 · For Claude Code · Reads `data/metrics/cycle_01/platform_data.json` (step 9) and, lazily, `data/raw/corpus_master.json` for answer texts. Design source: the approved mockup `ui/citere_cmo_master_screen.html` is the design system for the whole platform — its `:root` token blocks (light and dark), font pairing (Fraunces for figures and headings, Public Sans for text and labels), tile shape and spacing, table, tag and bar styles and overall density are taken verbatim at build time and apply to Level 1, every Level 2 screen and the point view; no second palette. From the legacy Evidence Base (`ui/evidence_base_legacy.html`) keep only the DOM structure where useful (point table filter bar, detail panel sections) and the Neural map's visual code untouched (layout, drawing, interactions, its own CSS); its palette, typography and calculations are not used. The map's data comes from `platform_data.json` like every other screen: `src/step_10_build_ui.py` builds `ui/map_data.js` — one node per point keyed by (pid, run), carrying the map's own field names, clustered by topic and by `group_id` so a sub-cluster's point count equals that group's `n_prompts` in #/priorities (asserted at build time). The legacy compute helpers (diagnosis and fix-card engines, dem, aiNative, pointPrio, HUMAN_CAUSE, CAUSE_CLS) are not carried, and the map's hard-coded header figures are re-pointed at `meta`.

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

**#/actions** — **the unit is one fix card**. Each of the referenced client fix cards renders directly as its own task: action text, task type, execution, owner, speed, MLR status, why, expected effect, verify line, target, and a link to its point. A campaign is metadata on the card, shown as a breadcrumb (topic · owner) linking to that group in Priorities; it is never a container. Board columns are task-level status; the action buttons act on one card, or on a whole group when identical actions are collapsed. Grouping identical action text is an opt-in density control, off by default. The 61 campaigns and their aggregate potential live in Priorities, whose campaign pills jump here filtered to that topic and owner. Also: a summary bar, a Board / Table toggle over one filtered state, five filters (who, how it runs, source type, priority, task type) plus text search, all combining with AND and addressable in the hash so a filtered board is a link. Task type is the export's own `agent` field grouped into plain names, with the agent code on hover. The Board groups tasks by status and collapses repeated templated action text to one line with a count; the Table sorts by potential and shows the task-type column. Send to agent, Assign, Mark done and Dismiss write to `localStorage` in both views and show the "not synced to registry" badge. Original behaviour: campaigns (client tasks) grouped by status; each campaign expands to its fix cards (`audience: client`), each card shows type, platform_execution, MLR status, owner, speed, URL, why. Status controls (open / in progress / done / dismissed + reason) write to `localStorage` only and show a "not synced to registry" badge — persistence to the registry is out of scope for the UI. Collapsed section at the bottom: "Citere monitoring" (`citere_tasks`), hidden by default.

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

## Plain language

Every figure carries a hover explanation and every screen and tile carries a visible one-line description. The wording lives in one file, `ui/glossary.json`, keyed by metric id: `text` is the hover explanation (two or three sentences: what it means, how it was measured, what a good value looks like), `lead` is the visible line under a heading. No interval names, no class codes, no internal vocabulary. The build inlines the file and fails if any figure points at an id the file does not define; it also lists ids the interface never uses, so the file and the screens stay in step.

## Do not

- No calculations in JS beyond formatting, sorting and filtering.
- No number shown without its source in `platform_data.json`.
- No `cause`, diagnosis or fix text edited or generated in the UI.
- No status persistence claims: localStorage only, badge says so.

---

## Display rule — code vs cause (cycle-1 decision, fixed)

The two vocabularies are hierarchical, not parallel. The pipeline `code` is **what happened** and is always the row title; the export `cause` is **why** and is always a sub-line beneath it with its confidence. Format everywhere a point or group is titled:

- line 1: `code_label` — **bold**
- line 2: `cause.label · confidence: high/med/low` — grey, smaller

Never render code and cause as two equal labels, chips or columns.

## Answer texts (cycle-1 decision)

Do not lazy-load `corpus_master.json`. Answer texts come from `ui/answers_<run>.js` (one file per run, R1…R9), built by `src/step_10_build_ui.py` from the normalized corpus (`answers.parquet` + `citations.parquet`, i.e. `corpus_master.json` after step 1): full texts, no previews; gzip + base64 JSON keyed `pid|run`, each entry an array in corpus order of `{model, repeat_idx, answer_raw, answer_clean, excluded, exclude_reason, citations:[{domain, url, owner}]}`. The point view loads only the file of the point's run. Split by run because the artifact publish ceiling is 16 MB per text file (a single store would be 19.9 MB); the same ceiling moves the Neural map's data block out of `index.html` into `ui/map_data.js`, loaded when `#/map` opens. The earlier preview store `ui/answers_b64.js` (texts cut at 2,000 chars) is deleted.
