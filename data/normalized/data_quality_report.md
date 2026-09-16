# Data quality report — step 1 normalization (cycle 1)

Input `data/raw/corpus_master.json` (md5 `7bd2f3f93da52991e5eec5e24c7094c8`), meta.total_prompts = 1424. Output rows: answers = 12314, citations = 78567.
Prompt keys are `(pid, run)`: 1424 unique; corpus note says P0979 and P1013 appear in both R7 and R8.
**Overall: WARN** — sections: 1 PASS, 2 WARN, 3 PASS, 4 WARN, 5 PASS, 6 PASS, 7 WARN, 8 WARN, 9 WARN.


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

| model | answers | tail_cleaned | truncated | chip_on_cut | too_short | real_truncation | ends_curly_quote |
|---|---|---|---|---|---|---|---|
| claude-sonnet-4-6 | 1768 | 18.3% | 0.2% | 0.0% | 0.0% | 0.2% | 0.0% |
| claude-sonnet-5 | 985 | 0.0% | 7.4% | 0.0% | 0.0% | 7.4% | 0.0% |
| claude-web | 773 | 0.0% | 2.3% | 0.0% | 0.0% | 2.3% | 0.0% |
| gemini-2.5-flash | 2753 | 0.0% | 0.4% | 0.0% | 1.1% | 0.4% | 0.0% |
| gemini-web | 773 | 0.0% | 3.4% | 0.0% | 0.0% | 3.4% | 0.0% |
| google-ai | 773 | 0.0% | 0.4% | 0.0% | 0.0% | 0.4% | 0.0% |
| gpt-4o | 2762 | 0.0% | 0.8% | 0.0% | 0.0% | 0.8% | 0.7% |
| gpt-web | 774 | 10.2% | 7.8% | 0.5% | 0.1% | 8.3% | 2.3% |
| grok-web | 180 | 0.0% | 2.8% | 0.0% | 0.0% | 2.8% | 2.8% |
| perplexity-web | 773 | 29.9% | 4.9% | 0.6% | 0.0% | 5.6% | 4.0% |

Excluded answers by reason: {'truncated': 260, 'too_short': 32, 'chip_on_cut': 9}. Total excluded: 301 of 12314 (2.4%).

Possible uncaught source-name chips: 43 of 260 `truncated` answers end with a short bare token right after a terminal character (e.g. `…dose. MotherToBaby`, `…help. CDC`, `…promptly. ozempic.com`). By surface: {'claude-sonnet-5': '4/73', 'claude-web': '13/18', 'gemini-2.5-flash': '1/12', 'gpt-web': '25/60'}. The spec's chip patterns do not cover this form; they are left flagged as truncated pending a human decision.

Note on `ends_curly_quote`: the spec's terminal set is `.!?)»"`. Answers ending in a typographic closing quote `”` are therefore flagged `truncated` even though they end on a quoted sentence. They are counted inside `truncated` above; the column shows their share so a human can decide whether to accept `”` as terminal.

10 examples of real truncation (highest-share surfaces first), last 120 chars of the raw answer:

- `P1147` R4 gpt-web [truncated]: …' I or anyone in my family ever had medullary thyroid cancer or MEN2?” rather than simply “Do I have a thyroid disorder?”'
- `P1155` R4 gpt-web [chip_on_cut]: …'nancy data are limited, and the labeling notes potential fetal risks based largely on animal studies. FDA Access Data +1'
- `P0001` R1 claude-sonnet-5 [truncated]: …" one new habit this week , and remember that small daily adjustments work because they're manageable, habit-forming, and"
- `P0021` R1 claude-sonnet-5 [truncated]: …"olled diabetes — but there's a very good chance her care team can find a combination of savings programs and/or a formul"
- `P1143` R4 perplexity-web [truncated]: …'bottom line is: treat this as “don’t start until clarified,” not “you definitely have thyroid cancer risk from Ozempic.”'
- `P1156` R4 perplexity-web [truncated]: …' my last-dose date, what will replace it, what glucose targets should I use, and when can we safely stop contraception?”'
- `P1154` R4 gemini-web [truncated]: …'y breathing or swallowing Severe hives, widespread rash, or intense itching Rapid heartbeat or sudden dizziness/fainting'
- `P1216` R4 gemini-web [truncated]: …'therapy is clinically indicated or if nutrition and behavioral support is the appropriate path. To explore this further:'
- `P1146` R4 grok-web [truncated]: …'ant” claim. The origin of the warning is rodent data; the official rule for family history of MTC is still “do not use.”'
- `P1149` R4 grok-web [truncated]: …'on that involved the airway needs follow-up with a clinician who has her history, not a restart once she “looks better.”'

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

**WARN**

Total citations: 78567. Artifacts removed (`vertexaisearch.cloud.google.com`): 4725. Remaining: 73842. Duplicate-domain rows within one answer (`dedup = true`, keep-first): 9601. Unparseable/empty URLs: 0.

Owner distribution (spec rule: owned → competitor:<Brand> → institutional → stored adversarial/noise/other → earned), excluding artifacts:

| owner | citations | share |
|---|---|---|
| earned | 45772 | 62.0% |
| institutional | 16955 | 23.0% |
| other | 6942 | 9.4% |
| owned | 1812 | 2.5% |
| adversarial | 1330 | 1.8% |
| competitor:Trulicity | 250 | 0.3% |
| competitor:Wegovy | 238 | 0.3% |
| competitor:Zepbound | 232 | 0.3% |
| competitor:Mounjaro | 196 | 0.3% |
| noise | 41 | 0.1% |
| competitor:Rybelsus | 41 | 0.1% |
| competitor:Jardiance | 13 | 0.0% |
| competitor:Victoza | 10 | 0.0% |
| competitor:Saxenda | 10 | 0.0% |

Stored `owner_data` × computed `owner` (rows: stored, columns: computed):

| owner_data | adversarial | competitor:Jardiance | competitor:Mounjaro | competitor:Rybelsus | competitor:Saxenda | competitor:Trulicity | competitor:Victoza | competitor:Wegovy | competitor:Zepbound | earned | institutional | noise | other | owned |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| adversarial | 1330 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| commerce | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 14414 | 0 | 0 | 0 | 0 |
| comp_owned | 0 | 0 | 196 | 0 | 0 | 250 | 0 | 0 | 232 | 0 | 0 | 0 | 0 | 0 |
| earned | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 29378 | 16955 | 0 | 0 | 0 |
| noise | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 41 | 0 | 0 |
| other | 0 | 13 | 0 | 0 | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 6942 | 0 |
| owned | 0 | 0 | 0 | 41 | 0 | 0 | 0 | 238 | 0 | 143 | 0 | 0 | 0 | 1812 |
| ugc | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1837 | 0 | 0 | 0 | 0 |

Top-30 domains with owner = `other`: luknermed.com (43), substack.com (27), sciencealert.com (25), superpower.com (23), abbott.com (21), justanswer.com (21), uspharmacist.com (19), premiummedicalcircle.com (19), htxheart.com (19), livescience.com (19), formhealth.co (19), infectiousdiseaseadvisor.com (19), adwdiabetes.com (18), omegaquant.com (18), managedhealthcareexecutive.com (18), nourishadl.com.au (18), getzealthy.com (18), aace.com (18), healthcare-bulletin.co.uk (18), megawecare.com (17), meto.co (17), weddingsdiet.com (17), amazon.com (17), medxdrg.com (17), knownwell.co (17), nighgoldenberg.com (17), davita.com (17), mydr.com.au (17), helloclue.com (17), baledoneen.com (16)

Hosts stored as `owned` that config maps to a competitor (intentional: Wegovy/Rybelsus compete for the slot): wegovy.com (202), rybelsus.com (41), mash.wegovy.com (26), heart.wegovy.com (10)
Hosts stored as `owned` that are in no config list and now fall to `earned` — likely Novo corporate sites missing from `domains.yaml: owned` (143 citations): pro.novonordisk.co.uk (54), novo-pi.com (46), novonordiskmedical.com (21), novonordisk-us.com (18), novonordisk.com.au (2), novonordisk.ca (1), pro.novonordisk.ae (1)
Hosts stored as `comp_owned` but not matched to a competitor domain: none
Domain matching is longest-suffix on the full host (so `mounjaro.lilly.com` → Mounjaro, `pi.lilly.com` → Trulicity via `lilly.com`); `domain` holds the registrable domain used for aggregation and dedup.

## 9. Topic groups

**WARN**

Group rule (diagnosis_prioritization_spec §2): `topic × subtopic` when subtopic is set and ≠ "Other", else `topic × zone`. Groups: 51 (32 topic×subtopic, 19 topic×zone).
Size distribution: min 2, median 16, max 125; buckets: {'<10': 12, '10–29': 24, '30–99': 12, '≥100': 3}.
Groups below `min_group_prompts` = 10: 12 (covering 59 prompts) — to be merged into `topic × small` by step 6.
Groups with more than one `demand` value: 2 — Indications & eligibility × Cardiovascular & renal indication (3 values), Indications & eligibility × Weight loss without diabetes (3 values).
Empty subtopic: 452 prompts (31.7%); subtopic = "Other": 92 prompts. Both route to `topic × zone`.

