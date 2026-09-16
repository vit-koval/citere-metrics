# Citation Tracking — cycle 1 (step 3b)
Unit = citation (domain occurrence in one answer, deduplicated); aggregation directly over citations, not repeats→prompts. Runs with citations: R1, R2, R3, R6, R7, R9; no citations on R4, R5, R8 (4646 answers, 37.7% of all).
Pie (62041 citations): **owned 2.5% · earned 77.4% · institutional 18.9% · competitor 1.1%**; adversarial reported separately (1186 citations); noise 42 and artifacts 4725 removed; 9601 duplicates within answers dropped.
Owned share in answers where we are named: 3.6% (vs 0.6% where we are not). Competitor sites split: Mounjaro 166, Zepbound 158, Wegovy 147, Lilly corporate 117, Trulicity 47, Rybelsus 36, Boehringer corporate 13, Farxiga 12, Victoza 10, Saxenda 9.
By model: claude-sonnet-4-6 owned 1.9 / earned 84.0 / inst 13.7 / comp 0.5; claude-sonnet-5 owned 2.5 / earned 80.0 / inst 15.7 / comp 1.8; gemini-2.5-flash owned 2.9 / earned 86.2 / inst 9.8 / comp 1.2; gpt-4o owned 2.9 / earned 45.6 / inst 49.5 / comp 1.9.
Earned subtypes: telehealth 28.1%, health_media 17.1%, directory 16.7%, other 13.9%, hospital 10.7%, advocacy 7.4%, news 2.9%, ugc 2.7%, payer 0.5% (mapping: media→health_media, news_pr/pr_wire→news, video/social→ugc; advocacy/payer kept).
Top-5 domains: nih.gov 5.4% (institutional, with us 59%); goodrx.com 3.9% (earned, with us 75%); drugs.com 3.8% (earned, with us 77%); healthline.com 2.8% (earned, with us 63%); medicalnewstoday.com 2.2% (earned, with us 69%).
Top-5 gaps (R1 C1; feed competitor answers, silent about us): apnews.com gap 8 (14 comp / 6 us, feeds 7) → PR [news]; peakwellnessva.com gap 8 (9 comp / 1 us, feeds 4) → outreach [telehealth]; hillsideprimarycare.com gap 7 (11 comp / 4 us, feeds 5) → outreach [telehealth]; bodevolvebariatric.com gap 7 (9 comp / 2 us, feeds 4) → outreach [telehealth]; weightwatchers.com gap 5 (27 comp / 22 us, feeds 5) → outreach [telehealth].
Institutional domains feeding the competitor: 8 (no action). Adversarial top-3: drugwatch.com (475), motleyrice.com (185), bursor.com (111).
Answers without citations: 39.6% of all answers (3.1% within citation-bearing runs). Artifact share by model: {'gemini-2.5-flash': 16.45}.
Audit: `audit/sample_citations.csv` — 40 random domains (seed 42) with computed owner/subtype; review owner by eye. 30 earned/other domains listed for manual labeling in the JSON.
Outputs: citations_summary.json, citations_domains.csv (4184 domains), citations_raw.csv (62041 rows).

---
Top-10 domains:

| domain | citations | share % | owner | subtype | answers % | with us % | with comp % | top model | top zone |
|---|---|---|---|---|---|---|---|---|---|
| nih.gov | 3348 | 5.40 | institutional |  | 46.8 | 59.4 | 51.0 | gpt-4o | STARTING & SWITCHING |
| goodrx.com | 2393 | 3.86 | earned | directory | 33.5 | 75.3 | 67.3 | claude-sonnet-4-6 | STARTING & SWITCHING |
| drugs.com | 2343 | 3.78 | earned | directory | 32.8 | 77.3 | 70.3 | claude-sonnet-4-6 | STARTING & SWITCHING |
| healthline.com | 1725 | 2.78 | earned | health_media | 24.1 | 63.2 | 54.0 | gemini-2.5-flash | STARTING & SWITCHING |
| medicalnewstoday.com | 1393 | 2.25 | earned | health_media | 19.5 | 68.7 | 55.5 | gemini-2.5-flash | STARTING & SWITCHING |
| diabetesjournals.org | 1249 | 2.01 | institutional |  | 17.5 | 47.0 | 42.9 | gpt-4o | STARTING & SWITCHING |
| clevelandclinic.org | 1093 | 1.76 | earned | hospital | 15.3 | 59.5 | 50.5 | gemini-2.5-flash | STARTING & SWITCHING |
| webmd.com | 1023 | 1.65 | earned | directory | 14.3 | 67.2 | 48.6 | gemini-2.5-flash | STARTING & SWITCHING |
| diabetes.org | 909 | 1.47 | earned | health_media | 12.7 | 36.6 | 40.3 | gpt-4o | STARTING & SWITCHING |
| mayoclinic.org | 856 | 1.38 | earned | hospital | 12.0 | 38.1 | 40.8 | gemini-2.5-flash | STARTING & SWITCHING |

Gap list (R1 C1, top-10, institutional excluded):

| domain | gap | cites_comp | cites_us | competitors fed | owner | subtype | action |
|---|---|---|---|---|---|---|---|
| apnews.com | 8 | 14 | 6 | 7 | earned | news | PR |
| peakwellnessva.com | 8 | 9 | 1 | 4 | earned | telehealth | outreach |
| hillsideprimarycare.com | 7 | 11 | 4 | 5 | earned | telehealth | outreach |
| bodevolvebariatric.com | 7 | 9 | 2 | 4 | earned | telehealth | outreach |
| weightwatchers.com | 5 | 27 | 22 | 5 | earned | telehealth | outreach |
| reddit.com | 4 | 26 | 22 | 9 | earned | ugc | monitor |
| farxiga.com | 4 | 5 | 1 | 3 | competitor:Farxiga |  | n/a (competitor site) |
| skenmedspa.com | 4 | 4 | 0 | 3 | earned | telehealth | outreach |
| axios.com | 3 | 8 | 5 | 8 | earned | news | PR |
| livescience.com | 3 | 5 | 2 | 6 | earned | other | review |

Owner shares by class and by model:

| slice | n | owned % | earned % | institutional % | competitor % |
|---|---|---|---|---|---|
| class C1 | 24147 | 0.4 | 72.4 | 26.8 | 0.3 |
| class C2 | 20433 | 5.7 | 79.7 | 14.6 | 0.0 |
| class C3 | 9524 | 1.2 | 81.7 | 11.9 | 5.2 |
| class C4 | 7937 | 2.3 | 81.5 | 14.4 | 1.8 |
| claude-sonnet-4-6 | 20056 | 1.9 | 84.0 | 13.7 | 0.5 |
| claude-sonnet-5 | 7153 | 2.5 | 80.0 | 15.7 | 1.8 |
| gemini-2.5-flash | 23589 | 2.9 | 86.2 | 9.8 | 1.2 |
| gpt-4o | 11243 | 2.9 | 45.6 | 49.5 | 1.9 |
