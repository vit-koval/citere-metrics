# Diagnosis & Prioritization — cycle 1 (step 6)
Groups: 39 — small groups (< 10 prompts) attached to the largest sibling of their topic, demand recomputed as the median across merged prompts: Basics & mechanism × STARTING & SWITCHING ← Basics & mechanism × WEIGHT LOSS; Efficacy & results × STARTING & SWITCHING ← Efficacy & results × HEART & KIDNEY, Efficacy & results × PRICE & ACCESS, Efficacy & results × REPUTATION & ENTITY; Lifestyle & daily living × STARTING & SWITCHING ← Lifestyle & daily living × WEIGHT LOSS; Serious risks & contraindications × Thyroid / MTC ← Serious risks & contraindications × Elderly, Serious risks & contraindications × Gallbladder, Serious risks & contraindications × Immunosuppression & other, Serious risks & contraindications × Liver / hepatic; Side effects & tolerability × LIVING ON THE DRUG ← Side effects & tolerability × HEART & KIDNEY, Side effects & tolerability × PRICE & ACCESS, Side effects & tolerability × SAFETY & CONTRAINDICATIONS; 74 source rows (group × owner) + 2 Label/Medical rows (no citations, label codes); 0 rows with gap = 0 dropped before terciles (none); 0 groups without citations and without a label code: none.
Score = Demand_share × Gap × Lever (Label rows: Demand_share × Gap); owners earned (commerce folded in as a subtype), ugc, owned, comp_owned. Tercile thresholds (source rows): P3 ≥ 0.000542, P2 ≥ 5.2e-05; Label rows: P3 ≥ 0.000339, P2 ≥ 0.000275.
**Gap caveat:** Gap pools different failure kinds across runs — R1 absent from the category answer, R2 lost duel, R4 label error, R6 message not delivered — so it is problem density on the topic, not one kind of failure; every row carries gap_by_run and its dominant run.
Lever = owner citations ÷ all citations in the group's answers (noise/other removed; institutional categories excluded from Lever and reported as institutional_share; adversarial reported separately). `impact_reach` = demand × gap is a ceiling, not a forecast.
Excluded before ranking — healthy groups (dominant code in non_failure_codes ['COMPETITOR WITHIN LABEL', 'MYTH DEFENDED', 'NO CLEAR WINNER', 'PATIENT RETAINED', 'REACH OK']): 15 groups; below gap floor (gap < 20%, background not a problem worth spending on): 1 groups. Both listed in the appendix.
Top-5 client recommendations (rows whose `who` is Citere are our monitoring, listed separately below):
1. Side effects & tolerability / LIVING ON THE DRUG → earned · P3 · demand 247,764 · gap 79% (R2 dominant) · lever 75% · LEAK TO A COMPETITOR · drugs.com · affects up to 196,502/month
2. Side effects & tolerability / WEIGHT LOSS → earned · P3 · demand 160,011 · gap 72% (R2 dominant) · lever 73% · LEAK TO A COMPETITOR · drugs.com · affects up to 115,564/month
3. Price, coverage & supply / Coupons & savings → earned · P3 · demand 121,227 · gap 88% (R7 dominant) · lever 70% · LOW REACH ON HIGH DEMAND · goodrx.com · affects up to 106,680/month
4. Efficacy & results / WEIGHT LOSS → earned · P3 · demand 54,976 · gap 85% (R2 dominant) · lever 76% · WE LOSE THIS DUEL · drugs.com · affects up to 46,620/month
5. Indications & eligibility / Weight loss without diabetes → earned · P3 · demand 66,818 · gap 66% (R3 dominant) · lever 74% · LEAK TO A COMPETITOR · drugs.com · affects up to 44,125/month
Label / Medical rows (2): Serious risks & contraindications × Allergy & hypersensitivity · P3 · gap 50% · INCOMPLETE / OMISSION · who: Medical + Digital; Indications & eligibility × Pediatrics & teens · P2 · gap 64% · INCOMPLETE / OMISSION · who: Medical + Digital.
Top-3 adversarial (threat) sources: drugwatch.com (475 citations, litigation); motleyrice.com (185 citations, litigation); bursor.com (111 citations, litigation) — excluded from Lever.
Quality: multi-demand groups 5 (median taken); answers without citations 41.9%; `who` values include `Citere` for 9 rows (own monitoring tasks — routed by step 7).
Outputs: prioritization_summary.json, prioritization_groups.csv (39 groups), prioritization_rows.csv (76 rows).

---
Top-10 client recommendations by topic group (one row per group = best score; owners beneath with their own lever and ceiling; Citere rows excluded):

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
| 4 | 3 | **Efficacy & results × WEIGHT LOSS** | 0.02807 | 54,976 | 85% (R2) | 27% | | | WE LOSE THIS DUEL | Marketing + Medical | weeks | 46,620 |
| | P3 | ↳ earned | 0.02807 | | | | 76% | 64.3 | drugs.com (earned) | | | |
| | P3 | ↳ owned | 0.00072 | | | | 2% | 1.7 | ozempic.com (owned) | | | |
| | P3 | ↳ ugc | 0.00063 | | | | 2% | 1.4 | reddit.com (ugc) | | | |
| | P2 | ↳ comp_owned | 0.00023 | | | | 1% | 0.5 | lilly.com (comp_owned) | | | |
| 5 | 3 | **Indications & eligibility × Weight loss without diabetes** | 0.02588 | 66,818 | 66% (R3) | 25% | | | LEAK TO A COMPETITOR | Digital | weeks | 44,125 |
| | P3 | ↳ earned | 0.02588 | | | | 74% | 48.8 | drugs.com (earned) | | | |
| | P2 | ↳ ugc | 0.00049 | | | | 1% | 0.9 | reddit.com (ugc) | | | |
| | P2 | ↳ owned | 0.00045 | | | | 1% | 0.9 | novonordisk.com (owned) | | | |
| | P2 | ↳ comp_owned | 0.00009 | | | | 0% | 0.2 | lilly.com (comp_owned) | | | |
| 6 | 3 | **Dosing & administration × Pen & device** | 0.00431 | 11,511 | 69% (R6) | 38% | | | MESSAGE NOT DELIVERED | Medical + Digital | weeks | 7,914 |
| | P3 | ↳ earned | 0.00431 | | | | 69% | 47.2 | drugs.com (earned) | | | |
| | P3 | ↳ owned | 0.00054 | | | | 9% | 5.9 | ozempic.com (owned) | | | |
| | P2 | ↳ ugc | 0.00021 | | | | 3% | 2.3 | reddit.com (ugc) | | | |
| | P2 | ↳ comp_owned | 0.00020 | | | | 3% | 2.2 | lilly.com (comp_owned) | | | |
| 7 | 3 | **Price, coverage & supply × Insurance & coverage** | 0.00414 | 8,198 | 85% (R7) | 52% | | | LOW REACH ON HIGH DEMAND | Digital | weeks | 6,937 |
| | P3 | ↳ earned | 0.00414 | | | | 75% | 63.6 | goodrx.com (earned) | | | |
| | P2 | ↳ owned | 0.00026 | | | | 5% | 4.0 | novocare.com (owned) | | | |
| | P2 | ↳ ugc | 0.00014 | | | | 3% | 2.2 | reddit.com (ugc) | | | |
| | P2 | ↳ comp_owned | 0.00008 | | | | 1% | 1.2 | lilly.com (comp_owned) | | | |
| 8 | 3 | **Dosing & administration × Timing, food & storage** | 0.00239 | 10,583 | 40% (R2) | 20% | | | WE WIN THIS DUEL | Digital | days | 4,233 |
| | P3 | ↳ earned | 0.00239 | | | | 71% | 28.5 | goodrx.com (earned) | | | |
| | P2 | ↳ owned | 0.00023 | | | | 7% | 2.7 | ozempic.com (owned) | | | |
| | P2 | ↳ ugc | 0.00006 | | | | 2% | 0.7 | reddit.com (ugc) | | | |
| | P1 | ↳ comp_owned | 0.00004 | | | | 1% | 0.4 | lilly.com (comp_owned) | | | |
| 9 | 3 | **Efficacy & results × STARTING & SWITCHING** | 0.00235 | 5,600 | 75% (R1) | 35% | | | WE ARE ABSENT | PR/Comms | weeks | 4,220 |
| | P3 | ↳ earned | 0.00235 | | | | 70% | 52.8 | drugs.com (earned) | | | |
| | P2 | ↳ owned | 0.00006 | | | | 2% | 1.4 | ozempic.com (owned) | | | |
| | P2 | ↳ ugc | 0.00006 | | | | 2% | 1.4 | reddit.com (ugc) | | | |
| | P1 | ↳ comp_owned | 0.00002 | | | | 0% | 0.4 | lilly.com (comp_owned) | | | |
| 10 | 3 | **Efficacy & results × LIVING ON THE DRUG** | 0.00182 | 3,041 | 100% (R1) | 50% | | | WE ARE ABSENT | PR/Comms | weeks | 3,041 |
| | P3 | ↳ earned | 0.00182 | | | | 75% | 75.2 | diabetes.org (earned) | | | |
| | P1 | ↳ ugc | 0.00005 | | | | 2% | 1.9 | reddit.com (ugc) | | | |
| | P1 | ↳ comp_owned | 0.00003 | | | | 1% | 1.2 | lilly.com (comp_owned) | | | |
| | P1 | ↳ owned | 0.00001 | | | | 0% | 0.2 | novonordiskmedical.com (owned) | | | |

Our monitoring, not client work (`who` = Citere; routed as citere tasks in step 7):

| group | P | best score | gap (dominant run) | cause | owners (lever) | what |
|---|---|---|---|---|---|---|
| Reputation & narratives × Lawsuits & cover-up | 3 | 0.00854 | 63% (R9) | AI AMPLIFIES A HARMFUL MYTH | earned 42%, ugc 2%, owned 1% | Run forensics on the cited domains first — whois dates + copied-text across sites — BEFORE |
| Dosing & administration × Site & volume | 3 | 0.00330 | 39% (R7) | ANSWERED CORRECTLY | earned 83%, owned 10%, ugc 1% | No action — keep this target in the monitoring set for the next cycle. |
| Serious risks & contraindications × Kidney safety | 2 | 0.00006 | 47% (R4) | ANSWERED CORRECTLY | earned 49%, owned 5%, ugc 1% | No action — keep this target in the monitoring set for the next cycle. |

Healthy groups (dominant code is not a failure — checked, nothing to fix):

| group | dominant code | prompts | demand | gap | gap_bad |
|---|---|---|---|---|---|
| Reputation & narratives × Body-change memes | REACH OK | 16 | 257,805 | 6% | 6% |
| Basics & mechanism × STARTING & SWITCHING | REACH OK | 39 | 89,149 | 69% | 38% |
| Price, coverage & supply × Cost & price | NO CLEAR WINNER | 48 | 70,316 | 75% | 29% |
| Reputation & narratives × Other narratives | MYTH DEFENDED | 13 | 31,005 | 31% | 8% |
| Dosing & administration × Titration & dose schedule | PATIENT RETAINED | 111 | 23,610 | 72% | 40% |
| Side effects & tolerability × GI & nausea | NO CLEAR WINNER | 49 | 9,872 | 69% | 16% |
| Indications & eligibility × Cosmetic & small-weight | COMPETITOR WITHIN LABEL | 10 | 7,305 | 50% | 40% |
| Serious risks & contraindications × Thyroid / MTC | COMPETITOR WITHIN LABEL | 97 | 4,600 | 49% | 13% |
| Lifestyle & daily living × LIVING ON THE DRUG | PATIENT RETAINED | 10 | 4,065 | 30% | 0% |
| Lifestyle & daily living × STARTING & SWITCHING | PATIENT RETAINED | 20 | 4,065 | 25% | 0% |
| Serious risks & contraindications × Pregnancy & lactation | COMPETITOR WITHIN LABEL | 43 | 2,083 | 44% | 30% |
| Serious risks & contraindications × Pancreatitis | COMPETITOR WITHIN LABEL | 25 | 1,196 | 24% | 4% |
| Side effects & tolerability × Fatigue & energy | NO CLEAR WINNER | 10 | 801 | 80% | 0% |
| Side effects & tolerability × STARTING & SWITCHING | NO CLEAR WINNER | 16 | 365 | 75% | 31% |
| Serious risks & contraindications × Vision & retinopathy | MYTH DEFENDED | 13 | 164 | 8% | 8% |

Below gap floor (gap < 20% — background, not a problem worth spending on):

| group | dominant code | prompts | demand | gap | gap_bad |
|---|---|---|---|---|---|
| Serious risks & contraindications × Hypoglycemia | ANSWERED CORRECTLY | 20 | 173 | 15% | 5% |

Label / Medical rows:

| # | P | group | score | demand | gap | gap_bad | cause | who | speed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | Serious risks & contraindications × Allergy & hypersensitivity | 0.00034 | 853 | 50% | 19% | INCOMPLETE / OMISSION | Medical + Digital | weeks |
| 2 | 2 | Indications & eligibility × Pediatrics & teens | 0.00028 | 539 | 64% | 36% | INCOMPLETE / OMISSION | Medical + Digital | weeks |
