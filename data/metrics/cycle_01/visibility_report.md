# Visibility Score — cycle 1 (step 2)
Headline (C1 unbranded prompts, families claude, gemini, gpt; equal weights): **Visibility 32.4%** [Wilson 95% 30.7–34.1], **Average Position 1.67**, **AI Brand Score 30.5**; brand-bearing-only visibility 75.3%; INN-only mention 16.9% (never added to visibility).
Scope: 328 C1 prompts (R1 250, R2 4, R3 7, R5 8, R6 59), 2911 C1 answers used after filters (59 excluded: {'truncated': 59}); surfaces covered: api, web; no C1 answers on: grok-web.
By family: claude 49.2% [46.0–52.4] pos 1.38 score 47.4 n=925; gemini 33.6% [30.7–36.6] pos 1.86 score 30.9 n=992; gpt 14.4% [12.4–16.8] pos 1.77 score 13.3 n=973; perplexity 54.2% [33.9–73.1] pos 2.00 score 49.7 n=21 low_n.
Cross-check (R1, same 2212 answers): visibility from `we_present` 27.28% vs from `our_status_scored` (M/R) 27.37% → diff 0.09 pts, within 0.5 — PASS.
Reliability: single-run groups 20.7%, unstable groups (repeats disagree on presence) 22.3% of multi-repeat groups; CI by number of answers (§7).
Decision 1 — position source: the spec says use `scores.our_rank` when present, but the scorer ranks among *all* brands it saw (Januvia, Farxiga, metformin…), not dictionary brands; 122 of 547 answers with both differ by >1. Text-based ordinal among dictionary brands is primary (also the only source for the 529 R6 C1 answers); with scored rank where present: Average Position 2.17, AI Brand Score 29.4.
Decision 2 — low_n families (perplexity) are flagged per §7 and left out of the headline mean (equal weights would give a ~22-answer family the same weight as 1,500 answers); all-families reference: Visibility 37.8%, Position 1.75, Score 35.3.
Anomaly 1 — C1 exists outside R1/R6: R2 4, R3 7, R5 8 prompts (forum-style posts naming only semaglutide or the nickname “Oz”, and R5 web probes “best weekly shot…”); included by the dictionary rule.
Anomaly 2 — `mentioned` tokens outside the dictionary are real drugs, not hallucinations: top Farxiga (389), Metformin (289), Invokana (271), American Diabetes Association (247), Januvia (193), Novo Nordisk (170); consider extending brands.yaml if they should count as competitors.
Anomaly 3 — R1 scorer marks 62 present answers with `our_rank = 0` (status M but no rank); legacy `visibility` field correlates 0.89 with our weight (reference only, not used).
Intrusion: competitor into our answers (C2) 29.4% [28.3–30.6], n=5830; ours into competitor answers (C3) 12.0% [10.8–13.4], n=2460; top competitor in C2: Wegovy.
Status vs text class mismatches: 813 prompts overall, 183 among C1 (class is never taken from `status`).
Audit: `audit/sample_visibility.csv` — 30 C1 answers (10 present / 10 absent / 10 INN-only, seed 42); stop for manual review, proceed if ≥ 90% agree.
Outputs: visibility_summary.json, visibility_by_prompt.csv (328 prompts), visibility_answers.csv (2970 rows incl. excluded).

---
Appendix — by model family (headline uses non-low_n families; versions pooled):

| family | versions | n_answers | groups | visibility % | CI95 | avg position | brand score | brand-bearing vis % | INN-only % | unstable groups % | single-run % | low_n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | claude-sonnet-4-6, claude-sonnet-5, claude-web | 925 | 587 | 49.2 | 46.0–52.4 | 1.38 | 47.4 | 88.9 | 7.8 | 8.0 | 44.5 |  |
| gemini | gemini-2.5-flash, gemini-web, google-ai | 992 | 336 | 33.6 | 30.7–36.6 | 1.86 | 30.9 | 76.3 | 11.1 | 28.3 | 0.0 |  |
| gpt | gpt-4o, gpt-web | 973 | 328 | 14.4 | 12.4–16.8 | 1.77 | 13.3 | 60.6 | 31.8 | 24.4 | 0.0 |  |
| perplexity | perplexity-web | 21 | 8 | 54.2 | 33.9–73.1 | 2.00 | 49.7 | 61.9 | 45.8 | 12.5 | 0.0 | yes |

By model version (reference only):

| version | family | n_answers | visibility % | CI95 | avg position | brand score | INN-only % | low_n |
|---|---|---|---|---|---|---|---|---|
| claude-sonnet-4-6 | claude | 643 | 54.1 | 50.2–57.9 | 1.37 | 52.2 | 7.0 |  |
| claude-sonnet-5 | claude | 261 | 42.5 | 36.6–48.5 | 1.37 | 41.0 | 8.5 |  |
| claude-web | claude | 21 | 72.9 | 51.5–87.2 | 1.93 | 66.3 | 16.7 | yes |
| gemini-2.5-flash | gemini | 950 | 30.7 | 27.9–33.7 | 1.80 | 28.4 | 11.2 |  |
| gemini-web | gemini | 21 | 85.4 | 65.0–94.9 | 2.50 | 73.7 | 14.6 | yes |
| google-ai | gemini | 21 | 95.8 | 78.2–99.3 | 2.33 | 84.4 | 4.2 | yes |
| gpt-4o | gpt | 952 | 13.1 | 11.1–15.4 | 1.74 | 12.2 | 31.7 |  |
| gpt-web | gpt | 21 | 66.7 | 45.4–82.8 | 2.33 | 59.3 | 33.3 | yes |
| perplexity-web | perplexity | 21 | 54.2 | 33.9–73.1 | 2.00 | 49.7 | 45.8 | yes |
