# Revenue-at-risk layer — v1, as built

Cycle 1 · Ozempic · US. Built against `citere_revenue_at_risk_spec_v2.md` (Steps 1–6).
Every number below is the value the current build actually produces, not a spec target.

## Formula

For each point, `usd = ptDemand_eff × gap × usdPerSearch`, where `ptDemand_eff` is the point's own
monthly search demand (`demand_extra.prompt_share`, the absolute per-prompt figure the platform export
carries, Σ = 1 780 975/mo) multiplied by a per-cell demand-correction factor `dcf = max(1, r7vol / topic_demand)`
that lifts a cell whose hand-built keyword basket came out below the R7 keyword volume measured in the same
cell; `gap = 1 − our/n` is the share of the point's answers that do not name the trade name Ozempic, recomputed
from the corpus by word-boundary regex over the answer text (INN never counts, `mentioned[]` never used); and
`usdPerSearch` is a single pair of engagement constants, floor $3.13 and mid $9.30, so every figure is a range
and the ranking of points and groups depends only on measured data. Questions that name only the client's own
portfolio brands are flagged `pf = 1` and carry `usd = [0, 0]`. API surfaces (R1–R3, R6–R9) and web surfaces
(R4, R5) are aggregated separately and never summed. All money is labelled "(Google proxy, US · estimate)"
and worded "at risk", never "lost revenue".

## Numbers as built

| figure | value |
|---|---|
| `money_totals.api_usd_mo` | **[2 370 093, 7 042 024]** /mo |
| headline (api × 12) | **$28 441 116 – $84 504 288** /yr — displayed `$28–85M / yr` |
| share of ad spend ($225M) | 13% – 38% |
| `money_totals.web_usd_mo` | [102 058, 303 247] /mo — separate panel, never added |
| `money_totals.excluded_pf_pt_demand_mo` | 158 107 /mo (corrected basis; 61 921 /mo on the uncorrected basis) |
| `money_totals.corrected_cells` | 14 of 49 |
| `money_totals.portfolio` | Rybelsus, Wegovy |
| portfolio points (`pf = 1`) | **76** |
| API points counted (`panel = api`, `pf = 0`) | 1 066 of 1 424 |
| web points counted | 282 |

### Demand correction — 14 corrected cells

| cell | topic_demand | r7vol | dcf |
|---|---|---|---|
| STARTING & SWITCHING / Efficacy & results | 5 600 | 276 800 | 49.43 |
| STARTING & SWITCHING / Other | 365 | 16 500 | 45.21 |
| * / Insurance & coverage | 8 198 | 111 600 | 13.61 |
| * / Titration & dose schedule | 23 610 | 179 600 | 7.61 |
| * / Site & volume | 12 920 | 59 300 | 4.59 |
| * / Coupons & savings | 121 227 | 384 500 | 3.17 |
| WEIGHT LOSS / Efficacy & results | 54 976 | 161 800 | 2.94 |
| * / Pen & device | 11 511 | 30 100 | 2.61 |
| * / Basics & mechanism | 89 149 | 170 600 | 1.91 |
| * / Body-change memes | 257 805 | 376 600 | 1.46 |
| * / Lawsuits & cover-up | 40 650 | 55 800 | 1.37 |
| * / Cost & price | 70 316 | 95 800 | 1.36 |
| * / GI & nausea | 9 872 | 11 500 | 1.16 |
| * / Other narratives | 31 005 | 34 900 | 1.13 |

### §8 verification checks

| check | built value | reference | deviation | tolerance |
|---|---|---|---|---|
| A · R7 Σ `scores.volume × gap` | **1 015 794** /mo | 1 015 794 | +0.00% | ±3% |
| B · API `pf=0` Σ `pt_demand_eff × gap` | **757 209** /mo | 754 508 | +0.36% | ±10% |
| B → floor USD/yr | **$28 441 116** | $28.3M | +0.50% | ±10% |
| B → mid USD/yr | **$84 504 288** | $84.2M | +0.36% | ±10% |
| web panel | 32 607 /mo | ~32 601 | +0.02% | info |
| portfolio excluded | 76 points | 77 | −1 point | exact — see deviation 2 |
| sanity: mid/yr ≤ ad spend | $84.5M ≤ $225M | — | 37.6% of budget | must hold |

## Deviations from the spec, steps 1–5

1. `gap` is recomputed from the corpus rather than reused from `metrics.we_present_share` (§3.2): the stored
   share is a repeats→model→family→point mean over non-excluded answers, not `our/n`. The underlying matching is
   already trade-name regex over answer text, so only the aggregation differs — 338 of 1 424 points, +0.1% on the
   API total.
2. `pf = 1` yields **76** points, not the 77 of §3.3: `COMP_MONEY = keys(competitors) − portfolio` (§2.2) includes
   Saxenda, so `P1011|R7` "Which is better, Saxenda or Wegovy?" is disqualified. Tirzepatide is an INN and not a
   `competitors` key, so it no longer blocks; no point is added back.
3. `excluded_pf_pt_demand_mo` is emitted on the corrected basis (158 107) while §3.3 quotes ≈62K on the
   uncorrected basis; the uncorrected figure is 61 921, confirming the expectation. §3.4 does not fix the basis.
4. `money_totals` is emitted even without `pricing.yaml`, with `api_usd_mo`/`web_usd_mo` null and the two
   non-money counters live; §3.4 does not describe the absent-config case.
5. `money_totals.portfolio` was added so the Overview tile can name the brands in the mandatory §5.1 line;
   §3.4 does not list the key.
6. `r7vol` reads `models[0].scores.volume` exactly as §3.2 states; the earlier dry runs took the first record
   carrying a volume — identical on this corpus.
7. A latent bug in the shared `tbl()` had to be fixed: it threw on an unknown `sortKey`, and §5.2's `sort=usd`
   is also read by the existing recommendations table on the same route.
8. The money column lives in the shared `pointTable`, so it appears on every screen that lists points; the
   repository has no standalone Data-points route, and the tile's click target is `#/priorities`.
9. The ad-spend benchmark is printed as a single value (`$225M`) via a dedicated formatter; §5.1 only specifies
   the range format.
10. §6 names `ui/index.html`, but that file is a build artifact; the map lens is implemented as guarded
    replacements over the extracted legacy map JS in `src/step_10_build_ui.py`, each asserting a unique anchor.
11. The map node carries an extra `gp` (money gap) field beyond the four of §4, because §6.3's drawer formula
    needs the gap and it cannot be derived from `oz/n` (different denominator).
12. §6.2 mentions keeping a `crit` radius multiplier "if present" — the current map has none; `cr` only affects
    label priority, so nothing was carried over.
13. `window.__nmSetLens` is exported alongside the existing `__nmGoPoint` / `__nmKick` hooks; §6 does not ask
    for it.

## Rounding note

`usd` is rounded per point, so scaling both constants by k reproduces every figure to within 1 unit rather than
exactly. Under k = 2: 283 of 1 424 points differ from an exact doubling by at most 1, which splits 14 previously
tied pairs. No pair with a strict order at k = 1 reverses, and no map radius multiplier changes.
