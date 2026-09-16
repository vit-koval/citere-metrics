# Diagnosis & Prioritization — cycle 1 (step 6)
Groups: 39 — small groups (< 10 prompts) attached to the largest sibling of their topic, demand recomputed as the median across merged prompts: Basics & mechanism × STARTING & SWITCHING ← Basics & mechanism × WEIGHT LOSS; Efficacy & results × STARTING & SWITCHING ← Efficacy & results × HEART & KIDNEY, Efficacy & results × PRICE & ACCESS, Efficacy & results × REPUTATION & ENTITY; Lifestyle & daily living × STARTING & SWITCHING ← Lifestyle & daily living × WEIGHT LOSS; Serious risks & contraindications × Thyroid / MTC ← Serious risks & contraindications × Elderly, Serious risks & contraindications × Gallbladder, Serious risks & contraindications × Immunosuppression & other, Serious risks & contraindications × Liver / hepatic; Side effects & tolerability × LIVING ON THE DRUG ← Side effects & tolerability × HEART & KIDNEY, Side effects & tolerability × PRICE & ACCESS, Side effects & tolerability × SAFETY & CONTRAINDICATIONS; 127 source rows (group × owner) + 2 Label/Medical rows (no citations, label codes); 0 rows with gap = 0 dropped before terciles (none); 0 groups without citations and without a label code: none.
Score = Demand_share × Gap × Lever (Label rows: Demand_share × Gap); owners earned (commerce folded in as a subtype), ugc, owned, comp_owned. Tercile thresholds (source rows): P3 ≥ 0.000507, P2 ≥ 3e-05; Label rows: P3 ≥ 0.000339, P2 ≥ 0.000275.
**Gap caveat:** Gap pools different failure kinds across runs — R1 absent from the category answer, R2 lost duel, R4 label error, R6 message not delivered — so it is problem density on the topic, not one kind of failure; every row carries gap_by_run and its dominant run.
Lever = owner citations ÷ all citations in the group's answers (noise/other removed; institutional categories excluded from Lever and reported as institutional_share; adversarial reported separately). `impact_reach` = demand × gap is a ceiling, not a forecast.
Top-5 recommendations:
1. Side effects & tolerability / LIVING ON THE DRUG → earned · P3 · demand 247,764 · gap 79% (R2 dominant) · lever 75% · LEAK TO A COMPETITOR · drugs.com · affects up to 196,502/month
2. Side effects & tolerability / WEIGHT LOSS → earned · P3 · demand 160,011 · gap 72% (R2 dominant) · lever 73% · LEAK TO A COMPETITOR · drugs.com · affects up to 115,564/month
3. Price, coverage & supply / Coupons & savings → earned · P3 · demand 121,227 · gap 88% (R7 dominant) · lever 70% · LOW REACH ON HIGH DEMAND · goodrx.com · affects up to 106,680/month
4. Basics & mechanism / STARTING & SWITCHING → earned · P3 · demand 89,149 · gap 69% (R7 dominant) · lever 68% · REACH OK · drugs.com · affects up to 61,719/month
5. Price, coverage & supply / Cost & price → earned · P3 · demand 70,316 · gap 75% (R2 dominant) · lever 78% · NO CLEAR WINNER · goodrx.com · affects up to 52,737/month
Label / Medical rows (2): Serious risks & contraindications × Allergy & hypersensitivity · P3 · gap 50% · INCOMPLETE / OMISSION · who: Medical + Digital; Indications & eligibility × Pediatrics & teens · P2 · gap 64% · INCOMPLETE / OMISSION · who: Medical + Digital.
Top-3 adversarial (threat) sources: drugwatch.com (475 citations, litigation); motleyrice.com (185 citations, litigation); bursor.com (111 citations, litigation) — excluded from Lever.
Quality: multi-demand groups 5 (median taken); answers without citations 41.9%; `who` values include `Citere` for 35 rows (own monitoring tasks — routed by step 7).
Outputs: prioritization_summary.json, prioritization_groups.csv (39 groups), prioritization_rows.csv (129 rows).

---
Top-10 recommendations by topic group (one row per group = best score; owners beneath with their own lever and ceiling):

| # | P | group / ↳ owner | score | demand | gap (dominant run) | gap_bad | lever | ceiling pp | cause / top domain | who | speed | reach ceiling |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | **Side effects & tolerability × LIVING ON THE DRUG** | 0.11770 | 247,764 | 79% (R2) | 29% | | | LEAK TO A COMPETITOR | Digital | weeks | 196,502 |
| | P3 | ↳ earned | 0.11770 | | | | 75% | 59.8 | drugs.com (earned) | | | |
| | P3 | ↳ owned | 0.00539 | | | | 3% | 2.7 | ozempic.com (owned) | | | |
| | P3 | ↳ ugc | 0.00257 | | | | 2% | 1.3 | reddit.com (ugc) | | | |
| | P3 | ↳ comp_owned | 0.00238 | | | | 2% | 1.2 | lilly.com (comp_owned) | | | |
| 2 | 3 | **Side effects & tolerability × WEIGHT LOSS** | 0.06684 | 160,011 | 72% (R2) | 22% | | | LEAK TO A COMPETITOR | Digital | weeks | 115,564 |
| | P3 | ↳ earned | 0.06684 | | | | 73% | 52.6 | drugs.com (earned) | | | |
| | P3 | ↳ ugc | 0.00187 | | | | 2% | 1.5 | reddit.com (ugc) | | | |
| | P3 | ↳ owned | 0.00138 | | | | 2% | 1.1 | ozempic.com (owned) | | | |
| | P3 | ↳ comp_owned | 0.00059 | | | | 1% | 0.5 | lilly.com (comp_owned) | | | |
| 3 | 3 | **Price, coverage & supply × Coupons & savings** | 0.05954 | 121,227 | 88% (R7) | 68% | | | LOW REACH ON HIGH DEMAND | Digital | weeks | 106,680 |
| | P3 | ↳ earned | 0.05954 | | | | 70% | 61.8 | goodrx.com (earned) | | | |
| | P3 | ↳ owned | 0.01201 | | | | 14% | 12.5 | novocare.com (owned) | | | |
| | P3 | ↳ comp_owned | 0.00418 | | | | 5% | 4.3 | lilly.com (comp_owned) | | | |
| | P3 | ↳ ugc | 0.00144 | | | | 2% | 1.5 | reddit.com (ugc) | | | |
| 4 | 3 | **Basics & mechanism × STARTING & SWITCHING** | 0.03354 | 89,149 | 69% (R7) | 38% | | | REACH OK | Digital | days | 61,719 |
| | P3 | ↳ earned | 0.03354 | | | | 68% | 47.4 | drugs.com (earned) | | | |
| | P3 | ↳ owned | 0.00257 | | | | 5% | 3.6 | ozempic.com (owned) | | | |
| | P3 | ↳ comp_owned | 0.00108 | | | | 2% | 1.5 | lilly.com (comp_owned) | | | |
| | P2 | ↳ ugc | 0.00034 | | | | 1% | 0.5 | diabetesteam.com (ugc) | | | |
| 5 | 3 | **Price, coverage & supply × Cost & price** | 0.03274 | 70,316 | 75% (R2) | 29% | | | NO CLEAR WINNER | Digital | weeks | 52,737 |
| | P3 | ↳ earned | 0.03274 | | | | 78% | 58.6 | goodrx.com (earned) | | | |
| | P3 | ↳ owned | 0.00270 | | | | 6% | 4.8 | novocare.com (owned) | | | |
| | P3 | ↳ ugc | 0.00085 | | | | 2% | 1.5 | reddit.com (ugc) | | | |
| | P3 | ↳ comp_owned | 0.00072 | | | | 2% | 1.3 | lilly.com (comp_owned) | | | |
| 6 | 3 | **Efficacy & results × WEIGHT LOSS** | 0.02807 | 54,976 | 85% (R2) | 27% | | | WE LOSE THIS DUEL | Marketing + Medical | weeks | 46,620 |
| | P3 | ↳ earned | 0.02807 | | | | 76% | 64.3 | drugs.com (earned) | | | |
| | P3 | ↳ owned | 0.00072 | | | | 2% | 1.7 | ozempic.com (owned) | | | |
| | P3 | ↳ ugc | 0.00063 | | | | 2% | 1.4 | reddit.com (ugc) | | | |
| | P2 | ↳ comp_owned | 0.00023 | | | | 1% | 0.5 | lilly.com (comp_owned) | | | |
| 7 | 3 | **Indications & eligibility × Weight loss without diabetes** | 0.02588 | 66,818 | 66% (R3) | 25% | | | LEAK TO A COMPETITOR | Digital | weeks | 44,125 |
| | P3 | ↳ earned | 0.02588 | | | | 74% | 48.8 | drugs.com (earned) | | | |
| | P2 | ↳ ugc | 0.00049 | | | | 1% | 0.9 | reddit.com (ugc) | | | |
| | P2 | ↳ owned | 0.00045 | | | | 1% | 0.9 | novonordisk.com (owned) | | | |
| | P2 | ↳ comp_owned | 0.00009 | | | | 0% | 0.2 | lilly.com (comp_owned) | | | |
| 8 | 3 | **Reputation & narratives × Body-change memes** | 0.01087 | 257,805 | 6% (R7) | 6% | | | REACH OK | Digital | days | 16,113 |
| | P3 | ↳ earned | 0.01087 | | | | 85% | 5.3 | clevelandclinic.org (earned) | | | |
| | P2 | ↳ owned | 0.00025 | | | | 2% | 0.1 | ozempic.com (owned) | | | |
| | P2 | ↳ ugc | 0.00010 | | | | 1% | 0.0 | facebook.com (ugc) | | | |
| 9 | 3 | **Dosing & administration × Titration & dose schedule** | 0.00989 | 23,610 | 72% (R3) | 40% | | | PATIENT RETAINED | Citere | cycle | 17,016 |
| | P3 | ↳ earned | 0.00989 | | | | 73% | 52.7 | drugs.com (earned) | | | |
| | P3 | ↳ owned | 0.00069 | | | | 5% | 3.7 | ozempic.com (owned) | | | |
| | P2 | ↳ ugc | 0.00032 | | | | 2% | 1.7 | reddit.com (ugc) | | | |
| | P2 | ↳ comp_owned | 0.00014 | | | | 1% | 0.8 | lilly.com (comp_owned) | | | |
| 10 | 3 | **Reputation & narratives × Lawsuits & cover-up** | 0.00854 | 40,650 | 63% (R9) | 48% | | | AI AMPLIFIES A HARMFUL MYTH | Citere | varies | 25,594 |
| | P3 | ↳ earned | 0.00854 | | | | 42% | 26.4 | clevelandclinic.org (earned) | | | |
| | P3 | ↳ ugc | 0.00051 | | | | 2% | 1.6 | facebook.com (ugc) | | | |
| | P2 | ↳ owned | 0.00017 | | | | 1% | 0.5 | ozempic.com (owned) | | | |

Label / Medical rows:

| # | P | group | score | demand | gap | gap_bad | cause | who | speed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | Serious risks & contraindications × Allergy & hypersensitivity | 0.00034 | 853 | 50% | 19% | INCOMPLETE / OMISSION | Medical + Digital | weeks |
| 2 | 2 | Indications & eligibility × Pediatrics & teens | 0.00028 | 539 | 64% | 36% | INCOMPLETE / OMISSION | Medical + Digital | weeks |
