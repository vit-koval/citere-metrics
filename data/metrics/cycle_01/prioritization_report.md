# Diagnosis & Prioritization — cycle 1 (step 6)
Groups: 44 (5 merged into `topic × small` at min 10 prompts: Basics & mechanism × small, Efficacy & results × small, Lifestyle & daily living × small, Serious risks & contraindications × small, Side effects & tolerability × small); 187 source rows (group × owner) + 2 Label/Medical rows (no citations, label codes); 0 groups without citations and without a label code: none.
Score = Demand_share × Gap × Lever (Label rows: Demand_share × Gap). Tercile thresholds (source rows): P3 ≥ 0.0006, P2 ≥ 0.0; Label rows: P3 ≥ 0.0003, P2 ≥ 0.0002.
**Gap caveat:** Gap pools different failure kinds across runs — R1 absent from the category answer, R2 lost duel, R4 label error, R6 message not delivered — so it is problem density on the topic, not one kind of failure; every row carries gap_by_run and its dominant run.
Lever = owner citations ÷ all citations in the group's answers (noise/other removed; institutional categories excluded from Lever and reported as institutional_share; adversarial reported separately). `impact_reach` = demand × gap is a ceiling, not a forecast.
Top-5 recommendations:
1. Side effects & tolerability / LIVING ON THE DRUG → earned · P3 · demand 247,764 · gap 76% (R7 dominant) · lever 50% · NO CLEAR WINNER · drugs.com · affects up to 188,301/month
2. Side effects & tolerability / small → earned · P3 · demand 160,011 · gap 100% (R2 dominant) · lever 45% · LEAK TO A COMPETITOR · goodrx.com · affects up to 160,011/month
3. Side effects & tolerability / WEIGHT LOSS → earned · P3 · demand 160,011 · gap 72% (R2 dominant) · lever 49% · LEAK TO A COMPETITOR · drugs.com · affects up to 115,564/month
4. Side effects & tolerability / LIVING ON THE DRUG → commerce · P3 · demand 247,764 · gap 76% (R7 dominant) · lever 28% · NO CLEAR WINNER · plexusdx.com · affects up to 188,301/month
5. Price, coverage & supply / Coupons & savings → earned · P3 · demand 121,227 · gap 88% (R7 dominant) · lever 42% · LOW REACH ON HIGH DEMAND · goodrx.com · affects up to 106,680/month
Label / Medical rows (2): Serious risks & contraindications × Allergy & hypersensitivity · P3 · gap 50% · INCOMPLETE / OMISSION · who: Medical + Digital; Indications & eligibility × Pediatrics & teens · P2 · gap 64% · INCOMPLETE / OMISSION · who: Medical + Digital.
Top-3 adversarial (threat) sources: drugwatch.com (475 citations, litigation); motleyrice.com (185 citations, litigation); bursor.com (111 citations, litigation) — excluded from Lever.
Quality: multi-demand groups 2 (median taken); answers without citations 41.9%; `who` values include `Citere` for 52 rows (own monitoring tasks — routed by step 7).
Outputs: prioritization_summary.json, prioritization_groups.csv (44 groups), prioritization_rows.csv (189 rows).

---
Top-10 recommendations (source rows):

| # | P | group | owner | score | demand | gap (dominant run) | gap_bad | lever | inst. share | cause | top domain | who | speed | reach ceiling |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | Side effects & tolerability × LIVING ON THE DRUG | earned | 0.06152 | 247,764 | 76% (R7) | 30% | 50% | 13% | NO CLEAR WINNER | drugs.com | Digital | weeks | 188,301 |
| 2 | 3 | Side effects & tolerability × small | earned | 0.04768 | 160,011 | 100% (R2) | 25% | 45% | 25% | LEAK TO A COMPETITOR | goodrx.com | Digital | weeks | 160,011 |
| 3 | 3 | Side effects & tolerability × WEIGHT LOSS | earned | 0.03756 | 160,011 | 72% (R2) | 22% | 49% | 20% | LEAK TO A COMPETITOR | drugs.com | Digital | weeks | 115,564 |
| 4 | 3 | Side effects & tolerability × LIVING ON THE DRUG | commerce | 0.03413 | 247,764 | 76% (R7) | 30% | 28% | 13% | NO CLEAR WINNER | plexusdx.com | Digital | weeks | 188,301 |
| 5 | 3 | Price, coverage & supply × Coupons & savings | earned | 0.02944 | 121,227 | 88% (R7) | 68% | 42% | 9% | LOW REACH ON HIGH DEMAND | goodrx.com | Digital | weeks | 106,680 |
| 6 | 3 | Basics & mechanism × STARTING & SWITCHING | earned | 0.02259 | 89,149 | 69% (R7) | 34% | 56% | 25% | REACH OK | drugs.com | Digital | days | 61,131 |
| 7 | 3 | Side effects & tolerability × small | commerce | 0.02221 | 160,011 | 100% (R2) | 25% | 21% | 25% | LEAK TO A COMPETITOR | doctronic.ai | Digital | weeks | 160,011 |
| 8 | 3 | Price, coverage & supply × Coupons & savings | commerce | 0.01992 | 121,227 | 88% (R7) | 68% | 28% | 9% | LOW REACH ON HIGH DEMAND | doctronic.ai | Digital | weeks | 106,680 |
| 9 | 3 | Basics & mechanism × small | earned | 0.01887 | 89,149 | 75% (R7) | 75% | 43% | 14% | LOW REACH ON HIGH DEMAND | drugs.com | Digital | weeks | 66,862 |
| 10 | 3 | Side effects & tolerability × WEIGHT LOSS | commerce | 0.01784 | 160,011 | 72% (R2) | 22% | 23% | 20% | LEAK TO A COMPETITOR | plexusdx.com | Digital | weeks | 115,564 |

Label / Medical rows:

| # | P | group | score | demand | gap | gap_bad | cause | who | speed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | Serious risks & contraindications × Allergy & hypersensitivity | 0.00028 | 853 | 50% | 19% | INCOMPLETE / OMISSION | Medical + Digital | weeks |
| 2 | 2 | Indications & eligibility × Pediatrics & teens | 0.00023 | 539 | 64% | 36% | INCOMPLETE / OMISSION | Medical + Digital | weeks |
