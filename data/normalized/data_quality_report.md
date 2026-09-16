# Data quality report — step 1 normalization (cycle 1)

Input `data/raw/corpus_master.json` (md5 `7bd2f3f93da52991e5eec5e24c7094c8`), meta.total_prompts = 1424. Output rows: answers = 12314, citations = 78567.
Prompt keys are `(pid, run)`: 1424 unique; corpus note says P0979 and P1013 appear in both R7 and R8.
**Overall: WARN** — sections: 1 PASS, 2 WARN, 3 PASS, 4 WARN, 5 PASS, 6 PASS, 7 WARN, 8 PASS, 9 WARN.


## 1. Prompts and answers per run × model

**PASS**

Answers per model × run (prompts per run in the header row):

| model | R1 (n=250) | R2 (n=272) | R3 (n=246) | R4 (n=180) | R5 (n=102) | R6 (n=110) | R7 (n=178) | R8 (n=20) | R9 (n=66) | total |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-sonnet-4-6 | 506 | 547 | 497 |  |  | 218 |  |  |  | 1768 |
| claude-sonnet-5 | 250 |  |  |  |  | 115 | 222 | 200 | 198 | 985 |
| claude-web |  |  |  | 540 | 233 |  |  |  |  | 773 |
| gemini-2.5-flash | 754 | 547 | 494 |  |  | 331 | 225 | 200 | 202 | 2753 |
| gemini-web |  |  |  | 540 | 233 |  |  |  |  | 773 |
| google-ai |  |  |  | 540 | 233 |  |  |  |  | 773 |
| gpt-4o | 753 | 561 | 494 |  |  | 333 | 222 | 200 | 199 | 2762 |
| gpt-web |  |  |  | 541 | 233 |  |  |  |  | 774 |
| grok-web |  |  |  | 180 |  |  |  |  |  | 180 |
| perplexity-web |  |  |  | 540 | 233 |  |  |  |  | 773 |

Dropped models (config `drop`): {'gemini-3.6-flash': 1}.
Model families: {'claude': ['claude-sonnet-4-6', 'claude-sonnet-5', 'claude-web'], 'gemini': ['gemini-2.5-flash', 'gemini-web', 'google-ai'], 'gpt': ['gpt-4o', 'gpt-web'], 'grok': ['grok-web'], 'perplexity': ['perplexity-web']}.

## 2. Repeats per prompt × model

**WARN**

Repeats per prompt×model group, by run:

| run | min | median | max | single_run_share |
|---|---|---|---|---|
| R1 | 1 | 3.000 | 4 | 25.0% |
| R2 | 2 | 2.000 | 4 | 0.0% |
| R3 | 1 | 2.000 | 3 | 0.1% |
| R4 | 1 | 3.000 | 4 | 16.7% |
| R5 | 1 | 2.000 | 3 | 0.4% |
| R6 | 1 | 3.000 | 4 | 25.0% |
| R7 | 1 | 1.000 | 6 | 83.9% |
| R8 | 10 | 10.000 | 10 | 0.0% |
| R9 | 3 | 3.000 | 4 | 0.0% |

Overall repeat distribution: {1: 991, 2: 2298, 3: 1990, 4: 31, 5: 3, 6: 3, 10: 60}.
Runs with a large single-run share have no repeat-level averaging there; prompt×model means are then single observations.

## 3. Tail cleaning and real truncation per surface

**PASS**

Per surface (model string). `real_truncation` = truncated + chip_on_cut after tail cleaning; threshold 10.0%.

| model | answers | tail_cleaned | truncated | chip_on_cut | too_short | real_truncation | name_chip_stripped |
|---|---|---|---|---|---|---|---|
| claude-sonnet-4-6 | 1768 | 18.3% | 0.2% | 0.0% | 0.0% | 0.2% | 0.0% |
| claude-sonnet-5 | 985 | 0.0% | 7.4% | 0.0% | 0.0% | 7.4% | 0.0% |
| claude-web | 773 | 0.5% | 1.8% | 0.0% | 0.0% | 1.8% | 0.5% |
| gemini-2.5-flash | 2753 | 0.0% | 0.4% | 0.0% | 1.1% | 0.4% | 0.0% |
| gemini-web | 773 | 0.0% | 3.4% | 0.0% | 0.0% | 3.4% | 0.0% |
| google-ai | 773 | 0.0% | 0.4% | 0.0% | 0.0% | 0.4% | 0.0% |
| gpt-4o | 2762 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| gpt-web | 774 | 13.6% | 2.1% | 0.0% | 0.1% | 2.1% | 3.4% |
| grok-web | 180 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| perplexity-web | 773 | 29.9% | 1.6% | 0.0% | 0.0% | 1.6% | 0.0% |

Excluded answers by reason: {'truncated': 161, 'too_short': 32}. Total excluded: 193 of 12314 (1.6%).

Cycle-1 decisions applied here (deviations from normalization_spec §2 / visibility_score_spec §3, agreed after the first DQ pass):
- Terminal set extended with typographic closing quotes `”` and `’` (spec set `.!?)»"`).
- A source-name chip is stripped like other chips: one bare token right after a terminal character at the very end — a capitalized word of 2–20 letters (`MotherToBaby`, `CDC`) or a bare domain (`ozempic.com`). Share per surface in `name_chip_stripped`.
- `FDA Access Data +N` (chip with a count) is stripped as one chip.

10 examples of real truncation (highest-share surfaces first), last 120 chars of the raw answer:

- `P0001` R1 claude-sonnet-5 [truncated]: …" one new habit this week , and remember that small daily adjustments work because they're manageable, habit-forming, and"
- `P0021` R1 claude-sonnet-5 [truncated]: …"olled diabetes — but there's a very good chance her care team can find a combination of savings programs and/or a formul"
- `P1154` R4 gemini-web [truncated]: …'y breathing or swallowing Severe hives, widespread rash, or intense itching Rapid heartbeat or sudden dizziness/fainting'
- `P1216` R4 gemini-web [truncated]: …'therapy is clinically indicated or if nutrition and behavioral support is the appropriate path. To explore this further:'
- `P1169` R4 gpt-web [truncated]: …'romptly with the prescriber. If pancreatitis is suspected, Ozempic should be discontinued while it is evaluated. Novo Pi'
- `P1181` R4 gpt-web [truncated]: …'ent—but that decision should be based on your medical situation, not simply because Ozempic was added. Diabetes Journals'
- `P1211` R4 claude-web [truncated]: …'\'t get it for weight loss" perception comes from, even though the legal barrier isn\'t really there. Keck Medicine of USC'
- `P1212` R4 claude-web [truncated]: …"nly coverage restriction, so the off-label route is getting harder to get covered by insurance even where it's legal. ca"
- `P1156` R4 perplexity-web [truncated]: …'ption medication-transition plan that has me off semaglutide for at least two months and keeps my glucose at a safe targ'
- `P1222` R4 perplexity-web [truncated]: …' justify same-day clinical evaluation , and emergency evaluation if you cannot rehydrate or have any of the red flags ab'

## 4. Class distribution per run and status mismatch

**WARN**

Prompt class from prompt text via brands.yaml (trade names only; INN never counts):

| run | C1 | C2 | C3 | C4 |
|---|---|---|---|---|
| R1 | 250 | 0 | 0 | 0 |
| R2 | 4 | 0 | 127 | 141 |
| R3 | 7 | 239 | 0 | 0 |
| R4 | 0 | 179 | 0 | 1 |
| R5 | 8 | 0 | 94 | 0 |
| R6 | 59 | 51 | 0 | 0 |
| R7 | 0 | 70 | 100 | 8 |
| R8 | 0 | 9 | 10 | 1 |
| R9 | 0 | 66 | 0 | 0 |

`status` × class (expected agreement: own→C2, comp→C3, mixed→C1/C4):

| status | C1 | C2 | C3 | C4 |
|---|---|---|---|---|
| comp | 177 | 73 | 101 | 78 |
| mixed | 145 | 199 | 130 | 23 |
| own | 6 | 342 | 100 | 50 |

`status_mismatch` share: 57.1% of prompts (813). By run: {'R1': '51.6%', 'R2': '90.4%', 'R3': '57.3%', 'R4': '49.4%', 'R5': '84.3%', 'R6': '60.0%', 'R7': '15.7%', 'R8': '70.0%', 'R9': '21.2%'}.
`status` is a per-prompt outcome label (own/mixed/comp = who wins the answer), not a question-type label, so a high mismatch is expected on outcome-driven runs; class is never derived from it.

## 5. we_present vs our_status_scored on R1

**PASS**

R1 only. `our_status_scored` = `scores.our_status` (values seen: ['A', 'EMPTY', 'M', 'R']).

| our_status_scored | False | True |
|---|---|---|
| A | 1180 | 0 |
| EMPTY | 457 | 0 |
| M | 2 | 616 |
| R | 0 | 8 |

Reading `M`/`R` as present and `A`/`EMPTY` as absent: disagreement with text-based `we_present` = 0.1% (2 answers). INN-only share on R1 = 16.6% (375 answers).
Of the disagreements, 2 are INN-only answers (scorer counted semaglutide as us).
Cross-check with stored `mentioned`: agrees with `we_present` on 98.7% of R1 answers.
The spec expected disagreement ≈ INN-only share (a scorer that counts semaglutide as us). It does not: the scorer marks INN-only answers as `A`, so `our_status_scored` and trade-name `we_present` agree almost everywhere. Favorable; no action.

## 6. INN-only share per model

**PASS**

Share of answers naming semaglutide but not Ozempic (`inn_only`), and `we_present`, per model:

| model | answers | inn_only | we_present |
|---|---|---|---|
| claude-sonnet-4-6 | 1768 | 8.5% | 73.2% |
| claude-sonnet-5 | 985 | 7.6% | 65.5% |
| claude-web | 773 | 5.6% | 69.1% |
| gemini-2.5-flash | 2753 | 8.2% | 61.7% |
| gemini-web | 773 | 2.8% | 72.4% |
| google-ai | 773 | 0.9% | 74.0% |
| gpt-4o | 2762 | 16.6% | 54.7% |
| gpt-web | 774 | 2.6% | 71.8% |
| grok-web | 180 | 0.0% | 100.0% |
| perplexity-web | 773 | 3.1% | 71.3% |

## 7. Sentiment: answer-level check

**WARN**

`answer_sentiment` present for 7320 of 12314 answers (59.4%); by run: {'R1': '69.8%', 'R2': '99.3%', 'R3': '99.6%', 'R4': '0.0%', 'R5': '0.0%', 'R6': '85.5%', 'R7': '97.3%', 'R8': '99.3%', 'R9': '86.6%'}.

| | median answer_sentiment | n |
|---|---|---|
| we_present = true | 72.0 | 5009 |
| we_present = false | 78.0 | 2311 |

Expected roughly equal (confirms the stored sentiment is answer-level, not brand-level). Difference = 6.0 points.

| run | median (we_present) | n | median (absent) | n |
|---|---|---|---|---|
| R1 | 75 | 605 | 82 | 975 |
| R2 | 72 | 1088 | 75 | 555 |
| R3 | 72 | 1466 | 65 | 13 |
| R6 | 85 | 670 | 85 | 182 |
| R7 | 65 | 309 | 75 | 342 |
| R8 | 75 | 353 | 75 | 243 |
| R9 | 58 | 518 | 68 | 1 |

The `absent` group is dominated by R1 category answers (no brand named), so a modest gap can reflect topic mix rather than brand-level scoring.

## 8. Citations

**PASS**

Total citations: 78567. Artifacts removed (`vertexaisearch.cloud.google.com`): 4725. Remaining: 73842. Duplicate-domain rows within one answer (`dedup = true`, keep-first): 9601. Unparseable/empty URLs: 0.

Owner distribution (rule: owned → competitor:<Brand> → institutional → stored adversarial/noise → earned, with stored `other` → earned/other), excluding artifacts:

| owner | citations | share |
|---|---|---|
| earned | 52559 | 71.2% |
| institutional | 16955 | 23.0% |
| owned | 1955 | 2.6% |
| adversarial | 1330 | 1.8% |
| competitor:Wegovy | 238 | 0.3% |
| competitor:Zepbound | 232 | 0.3% |
| competitor:Mounjaro | 196 | 0.3% |
| competitor:Lilly corporate | 190 | 0.3% |
| competitor:Trulicity | 60 | 0.1% |
| noise | 41 | 0.1% |
| competitor:Rybelsus | 41 | 0.1% |
| competitor:Boehringer corporate | 13 | 0.0% |
| competitor:Farxiga | 12 | 0.0% |
| competitor:Victoza | 10 | 0.0% |
| competitor:Saxenda | 10 | 0.0% |

Stored `owner_data` × computed `owner` (rows: stored, columns: computed):

| owner_data | adversarial | competitor:Boehringer corporate | competitor:Farxiga | competitor:Lilly corporate | competitor:Mounjaro | competitor:Rybelsus | competitor:Saxenda | competitor:Trulicity | competitor:Victoza | competitor:Wegovy | competitor:Zepbound | earned | institutional | noise | owned |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| adversarial | 1330 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| commerce | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 14414 | 0 | 0 | 0 |
| comp_owned | 0 | 0 | 0 | 190 | 196 | 0 | 0 | 60 | 0 | 0 | 232 | 0 | 0 | 0 | 0 |
| earned | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 29378 | 16955 | 0 | 0 |
| noise | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 41 | 0 |
| other | 0 | 13 | 12 | 0 | 0 | 0 | 10 | 0 | 10 | 0 | 0 | 6930 | 0 | 0 | 0 |
| owned | 0 | 0 | 0 | 0 | 0 | 41 | 0 | 0 | 0 | 238 | 0 | 0 | 0 | 0 | 1955 |
| ugc | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1837 | 0 | 0 | 0 |

Cycle-1 decision: stored `owner_data = other` is no longer excluded — it is classified `earned` with subtype `other` (citation_tracking_spec §2 updated accordingly; only stored `noise` stays excluded, `adversarial` is reported separately). Top-30 earned/other domains for manual labeling: luknermed.com (43), substack.com (27), sciencealert.com (25), superpower.com (23), abbott.com (21), justanswer.com (21), uspharmacist.com (19), formhealth.co (19), infectiousdiseaseadvisor.com (19), htxheart.com (19), livescience.com (19), premiummedicalcircle.com (19), healthcare-bulletin.co.uk (18), adwdiabetes.com (18), omegaquant.com (18), managedhealthcareexecutive.com (18), aace.com (18), getzealthy.com (18), nourishadl.com.au (18), meto.co (17), helloclue.com (17), medxdrg.com (17), knownwell.co (17), weddingsdiet.com (17), megawecare.com (17), davita.com (17), mydr.com.au (17), amazon.com (17), nighgoldenberg.com (17), docwirenews.com (16)

Earned subtypes (from stored `category`): telehealth (14285), directory (9274), media (8962), other (6930), hospital (5484), advocacy (3787), ugc (1740), news_pr (1390), video (252), payer (229), pr_wire (129), social (97)

Hosts stored as `owned` that config maps to a competitor (intentional: Wegovy/Rybelsus compete for the slot): wegovy.com (202), rybelsus.com (41), mash.wegovy.com (26), heart.wegovy.com (10)
Hosts stored as `owned` that are in no config list and now fall to `n/a` — likely Novo corporate sites missing from `domains.yaml: owned` (0 citations): none
Hosts stored as `comp_owned` but not matched to a competitor domain: none
Domain matching is longest-suffix on the full host: `mounjaro.lilly.com` → Mounjaro, other `lilly.com` hosts → `competitor:Lilly corporate`, `boehringer-ingelheim.com` hosts → `competitor:Boehringer corporate`; `domain` holds the registrable domain used for aggregation and dedup.

## 9. Topic groups

**WARN**

Group rule (diagnosis_prioritization_spec §2): `topic × subtopic` when subtopic is set and ≠ "Other", else `topic × zone`. Groups: 51 (32 topic×subtopic, 19 topic×zone).
Size distribution: min 2, median 16, max 125; buckets: {'<10': 12, '10–29': 24, '30–99': 12, '≥100': 3}.
Groups below `min_group_prompts` = 10: 12 (covering 59 prompts) — to be merged into `topic × small` by step 6.
Groups with more than one `demand` value: 2 — Indications & eligibility × Cardiovascular & renal indication (3 values), Indications & eligibility × Weight loss without diabetes (3 values).
Empty subtopic: 452 prompts (31.7%); subtopic = "Other": 92 prompts. Both route to `topic × zone`.

