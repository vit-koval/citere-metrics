# citere-metrics — Revenue-at-Risk Layer (spec v2, targeted at this repo)

Supersedes `citere_revenue_at_risk_spec.md` v1 (which referenced the legacy `build_master.py` / `DATA` codebase — do not use it). Every file, field and line below was confirmed by the Step 0 read-only reconnaissance of `citere-metrics` on 2026-09-24. Line numbers are as of that day; re-locate by the quoted code if they drift.

**Scope:** a money layer on top of the existing per-point demand. Display only: it never changes `point_rank_score`, group `score`, causes, fixes, campaign order, or map positions. With the config file absent, no money UI appears anywhere.

---

## 1. Formula

```
usd(p) = ptDemand_eff(p) × gap(p) × usdPerSearch
```

- `ptDemand(p)` = `demand_extra.prompt_share` (step_09:187). Despite the name it is absolute searches/mo per prompt, equal to legacy `td[4]`; Σ over corpus = 1 780 975. This is the ONLY demand field money may use. Never `demand.topic_demand` (a cell value repeated on every point of the cell; Σ over points = 49.8M, 28× inflated).
- `ptDemand_eff` = `ptDemand × dcf(cell)` — demand correction, §3.
- `gap(p)` = `1 − our/n`: `n` = number of answers, `our` = answers whose text matches the trade name in `brands.yaml: our_brand` (word boundary, case-insensitive). INN (`our_inn`) does not count. `mentioned[]` is never used.
- `usdPerSearch` = one constant per engagement, two values `floor` / `mid`. Every money figure is a range.

Because the constant is global, ranking and relative size by money depend only on measured data. This sentence goes into the tile tooltip.

---

## 2. Config

### 2.1 `config/pricing.yaml` (new, optional)

```yaml
market: US
currency: USD
usd_per_search:
  floor: 3.13
  mid: 9.30
benchmark_ad_spend_usd_yr: 225000000
sources:
  floor: "Replacement cost of a search visit: Novo Nordisk paid $7.5M for 2.4M paid visits to Ozempic.com, Apr 2022–Mar 2024 (JAMA Network Open, Nov 2025)"
  mid: "One new patient ($349/mo NovoCare cash price × 8.9 months expected time on therapy in year 1, from 46.5% 12-month discontinuation, JAMA Network Open 2025) × 0.3% search→patient rate (assumption)"
  benchmark_ad_spend_usd_yr: "Ozempic US advertising $169M Jan–Sep 2025 (MediaRadar via Reuters, Jan 2026), annualized ×12/9"
```

File absent → `pricing` is `null` everywhere and no money UI renders.

### 2.2 `config/brands.yaml` — one added key

```yaml
portfolio: ["Wegovy", "Rybelsus"]
```

`competitors` stays as is (Wegovy and Rybelsus remain competitors for SoV and visibility). For money only, define `COMP_MONEY = keys(competitors) − portfolio`.

---

## 3. Builder — `src/step_09_platform_data.py`

Read `config/pricing.yaml` (optional) and `brands.yaml: portfolio` at load time, next to the existing corpus/export loads (`:95`).

### 3.1 Demand correction factor `dcf` (cell level)

`topic_traffic.demand` was collected as √(lo×hi) over a keyword basket that did not include the R7 keywords; in 14 of 49 cells it is below the volume of the R7 keywords in the same cell.

- Cell key = `(zone | "*", subtopic | topic)` by `demand.basis`, exactly as the export used to compute `prompt_share`.
- `r7vol(cell)` = Σ `models[0].scores.volume` over corpus prompts with `run == "R7"` in the cell.
- `dcf(cell) = max(1, r7vol(cell) / topic_demand(cell))`. Cells without R7 prompts → 1.
- Because `prompt_share ∝ topic_demand` within a cell, `ptDemand_eff = prompt_share × dcf` is exactly the §6-style recomputation.
- Emit `dc = 1 if dcf > 1 else 0` on every point; log every corrected cell: key, topic_demand, r7vol, dcf. Expected: 14 cells, factors up to 49.4.

### 3.2 Per-point fields — add to the `points[k]` literal (`:167`–`:193`), right after `demand_extra` (`:187`)

```python
"money": {
  "pt_demand_eff": <int>,          # prompt_share × dcf
  "dc": 0|1,
  "gap": <float 0..1>,             # 1 − our/n, regex over answer text, trade name only
  "pf": 0|1,                       # portfolio rule, §3.3
  "usd": [<floor_usd_mo>, <mid_usd_mo>] | null,   # null when pricing.yaml absent
  "panel": "api" | "web"           # web = run in {R4, R5}
}
```

`gap`: check whether `metrics.we_present_share` (`:172`) is computed as trade-name regex over answer text. If yes, `gap = 1 − we_present_share`. If it uses `mentioned[]` or counts INN, compute `gap` fresh per §1 and say so in the step report.

### 3.3 Portfolio rule

`pf = 1` when `question` (`:168`) names ≥1 `portfolio` brand AND names no `COMP_MONEY` brand. `pf = 1` ⇒ `usd = [0, 0]`. Expected: 77 points, ≈62K/mo of pt_demand×gap excluded (uncorrected basis).

### 3.4 Top-level block

Add to the exported object (the `data` dict written at `:443`):

```python
"pricing": {"floor", "mid", "ad_spend_yr", "sources", "market"} | None,
"money_totals": {
  "api_usd_mo": [floor, mid],   # Σ usd over panel=api, pf=0
  "web_usd_mo": [floor, mid],   # Σ usd over panel=web, pf=0 — never added to api
  "excluded_pf_pt_demand_mo": <int>,
  "corrected_cells": <int>
}
```

`money_totals` is computed by the builder once so every UI element reads the same numbers (tile ↔ table agreement is a builder invariant, not a UI coincidence).

---

## 4. Map data — `src/step_10_build_ui.py`

In the node literal (`:52`–`:65`), next to `"vol"`/`"tdm"` (`:59`):

```python
"usd": pt["money"]["usd"], "pf": pt["money"]["pf"], "dc": pt["money"]["dc"],
"volx": pt["money"]["pt_demand_eff"],
```

Add `"pricing": data.get("pricing")` to the object written as `window.MAP_DATA` (`:185`). `window.PLATFORM_DATA` (`:199`) carries `pricing` and `money_totals` from step_09 automatically.

Do not change `vol` — the existing Demand sizing keeps working as today.

---

## 5. UI — `ui/template.html`

### 5.1 Overview: new first tile "Revenue at risk" — insert before Visibility Score (`:452`)

Renders only when `PLATFORM_DATA.pricing` is not null.

```
REVENUE AT RISK                              (Google proxy, US · estimate)
$28–84M / yr
[bar] 12–37% of annual Ozempic ad budget ($225M)

Top groups        <top-3 recommendation groups by Σ usd[1], each "$floor–mid/yr">
Web surfaces      $X–Y M/yr — separate panel, not added
Portfolio queries excluded — Wegovy, Rybelsus are the client's own brands
```

- Headline = `money_totals.api_usd_mo × 12`, format `$floor–midM / yr` (one decimal below $10M, integer above; `$285K` below $1M).
- Bar = headline ÷ `pricing.ad_spend_yr` as `floor%–mid%`.
- Tooltip (mandatory text): "Floor = what the brand already pays per search visit. Mid = value of a new patient × assumed conversion. Ranking of groups and points does not depend on either value. Demand is Google search demand, a proxy for AI demand." + the three `sources` strings.
- Click → Data points view sorted by `money.usd[1]` desc with `panel=api&pf=0` applied (§5.2). The footer there must show the same `money_totals.api_usd_mo`.

### 5.2 Data points table (`:574` area) and detail (`:877` area)

- New column **"$ at risk/mo"** after the existing Demand column: `$floor–mid`; `pf=1` rows show "portfolio" in grey; `panel=web` rows carry a "web" micro-marker. Header click sorts by `usd[1]` desc.
- Route params: `sort=usd`, `panel=api|web`, `pf=0`. Footer line: `Σ $ at risk: $floor–mid/mo · {panel} · portfolio {included|excluded}` — read from `money_totals` when the view equals the panel/pf preset, else summed over shown rows.
- Detail block (`:877`) gains two rows: `["$ at risk /mo", "$floor–mid"]` and `["How", "{pt_demand_eff}/mo searches × {gap%} answers without Ozempic × $3.13–9.30"]`. On `dc=1` add `["Demand note", "topic demand corrected upward to its own keyword volume"]`.
- **Observed, out of scope for this layer:** the existing Demand column (`:574`) and detail row (`:877`) display `demand.topic_demand`, the cell value repeated on every point (Σ = 49.8M vs 1.78M real). The money column uses `pt_demand_eff` and is therefore not comparable with that column. Recommended follow-up ticket: show `pt_demand_eff` there too. Not part of Steps 1–7.

### 5.3 Priorities tile (`:511`–`:514`)

Each of the top-3 groups gains a `$floor–mid/yr` line = Σ `usd` over the group's points (`panel=api`, `pf=0`) × 12. Group selection and order unchanged (still `score` from step_06).

### 5.4 Action Center (`:516`)

If the tile lists campaigns/groups, add `$ at stake/mo` per row with tooltip: "A point can belong to several groups — amounts are not additive. See the Revenue at risk tile for the total." Order unchanged.

---

## 6. Neural map — `ui/index.html`

### 6.1 Lens toggle
Header control **`Size: Demand | $ at risk`**, default Demand, hidden when `MAP_DATA.pricing` is null. Route param `lens=usd`.

### 6.2 Radius (`:1141`–`:1142`)
Today: `const d=q.vol||0, dsc = d>=1000?1.32 : d>=100?1.14 : d>0?1.0 : 0.85; q.r=(2.3+rnd()*1.6)*dsc;`

Keep the `rnd()` draw and the base exactly as is. Store `q.base = 2.3+rnd()*1.6` once at layout time; radius = `q.base × mult(lens)`:
- Demand lens: `mult = dsc` (unchanged).
- `$` lens: quantile of `usd[1]` over currently visible nodes with `pf=0` and `usd[1]>0`: top 10% → 1.60 · top 25% → 1.32 · other >0 → 1.0 · `usd=0` or `pf=1` → 0.6. Quantiles keep sizing independent of the constant.
- `crit` multiplier stays on top if present. Positions never change on toggle; only radii animate (≤300 ms).

### 6.3 Colors, hubs, labels, drawer
- Class colors unchanged. `pf=1` nodes grey, no halo, drawer line "Portfolio brand — not counted as a loss".
- Topic hub center text in `$` lens: `$floor–mid/mo at risk` (Σ over the hub's visible `panel=api`, `pf=0` nodes).
- Label priority in `$` lens: `usd[1]` desc first, then the existing class order.
- Drawer block: `$ at risk: $floor–mid/mo` + formula line `{volx} searches/mo × {gap%} answers without Ozempic × $3.13–9.30`.

---

## 7. Honesty rules

1. Every money figure is a `floor–mid` range labelled "(Google proxy, US · estimate)". Wording is "at risk", never "lost revenue".
2. Headline compares to annual ad spend, never to brand revenue.
3. API and web panels are never summed.
4. Portfolio-only questions are never counted.
5. Money never enters `score`, `point_rank_score`, causes, fixes or any ordering.
6. `demand.topic_demand` is never summed across points anywhere in this layer.

---

## 8. Verification references (from read-only dry runs on `data/raw/corpus_master.json`, 2026-09-24)

| check | value | tolerance |
|---|---|---|
| A. R7 only: Σ `scores.volume × gap` | **1 015 794 /mo** (competitor-named 892 194 + compare 123 600); gap vs `visibility_share` +0.16% | ±3% — a miss means `gap` is wrong |
| B. API panel, pf=0: Σ `pt_demand_eff × gap` | **754 508 /mo** (uncorrected 351 058); corrected cells 14/49 | ±10% |
| B → USD/yr | **$28.3M floor – $84.2M mid** | ±10% |
| Web panel, pf=0 | ≈ 32 601 /mo, shown separately | info |
| Portfolio excluded | 77 points | exact |
| Sanity | mid/yr ≤ ad spend $225M | must hold |

The earlier R7-only estimate ($38–113M/yr) is a different method; it is not a target here.

---

## 9. Acceptance tests

- **T1** No `config/pricing.yaml` → no money UI; `pricing` null; `money.usd` null on every point; everything else identical to a build with the file.
- **T2** With the file: `score`, `point_rank_score`, group order, cause codes, fix text and map node positions identical to T1's build.
- **T3** Tile headline ÷ 12 == `money_totals.api_usd_mo` == Data points footer at `panel=api&pf=0`. Exact.
- **T4** Every `pf=1` point has `usd=[0,0]` and contributes to no total.
- **T5** Headline contains no R4/R5 points; web line contains only R4/R5.
- **T6** Multiply `floor` and `mid` by k → every displayed $ scales by k; no ranking, radius or label order changes.
- **T7** Two builds byte-identical.
- **T8** Checks A and B from §8 within tolerance, logged with actual numbers.

---

## 10. Implementation steps (one Claude Code session each; next step only after the previous checks pass)

**Step 1 — Builder.** Create `config/pricing.yaml`; add `portfolio` to `config/brands.yaml`; in `src/step_09_platform_data.py` add `dcf`, the `money` block per point (§3.2), `pricing` and `money_totals` top-level (§3.4). State how `gap` was obtained (`we_present_share` reused or recomputed). Run T1, T2, T4, T5, T7, T8; print the corrected-cells list.

**Step 2 — Map data.** `src/step_10_build_ui.py`: node fields (§4), `MAP_DATA.pricing`. Check: `map_data.js` node count unchanged; positions unchanged (T2).

**Step 3 — Data points.** Column, sort, route params, footer, detail rows (§5.2). Run T3, T6.

**Step 4 — Overview.** Tile 0 (§5.1) + Priorities lines (§5.3) + Action Center column (§5.4). Run T1 (tile absent without config), T3.

**Step 5 — Map.** Lens toggle, radii, hub text, labels, drawer (§6). Run T2 on positions, T6 on radii, T7.

**Step 6 — Close.** Full T1–T8; write a `docs/` note "revenue-at-risk layer v1" with the §8 numbers as built; report every deviation from this spec across steps 1–5.

Each step ends with: files changed, each check with its actual number, deviations one line each. A deviation is reported, never silently resolved.
