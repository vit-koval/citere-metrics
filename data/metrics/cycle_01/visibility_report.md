# Visibility Score — cycle 1 (step 2)
Headline (R1 C1 category prompts, families claude, gemini, gpt; equal weights): **Visibility 27.3%** [Wilson 95% 25.5–29.2], **Average Position 2.00**, **AI Brand Score 25.1**; brand-bearing-only visibility 72.0%; INN-only mention 16.5% (never added to visibility).
Scope: 250 R1 C1 prompts, 2212 answers used after filters (51 excluded: {'truncated': 51}); surfaces covered: api; no R1 answers on: claude-web, gemini-web, google-ai, gpt-web, grok-web, perplexity-web.
By family: claude 44.4% [40.8–48.0] pos 1.57 score 42.0 n=708; gemini 26.5% [23.4–29.7] pos 2.26 score 23.4 n=751; gpt 11.0% [9.0–13.4] pos 2.18 score 9.8 n=753.
Cross-check (R1, same 2212 answers): visibility from `we_present` 27.28% vs from `our_status_scored` (M/R) 27.37% → diff 0.09 pts, within 0.5 — PASS.
Reliability (R1): single-run groups 21.4%, unstable groups (repeats disagree on presence) 22.6% of multi-repeat groups; CI by number of answers (§7).
Decision 1 (cycle 1, spec §2) — headline scope is R1 C1 only: R6 prompts are message-triggered, R5 are web probes, R2/R3 are forum posts; none is a neutral category question. Reference `c1_other_runs`: R2 4 prompts/23 answers on api: vis 29.2% pos 1.00 score 29.2; R3 7 prompts/42 answers on api: vis 64.3% pos 1.15 score 63.6; R5 8 prompts/105 answers on web: vis 71.1% pos 2.17 score 63.6; R6 59 prompts/529 answers on api: vis 42.6% pos 2.07 score 38.6. All C1 runs pooled would give Visibility 32.4%, Position 1.99, Score 29.7.
Decision 2 — position source: the spec says use `scores.our_rank` when present, but the scorer ranks among *all* brands it saw (metformin, Tradjenta, Actos…), not dictionary brands; 128 of 547 R1 answers with both differ by >1. Text-based ordinal among dictionary brands is primary; with scored rank where present: Average Position 2.42, AI Brand Score 24.2.
Decision 3 — dictionary extended with Farxiga, Januvia, Invokana (+ INNs and domains) after the first pass; metformin stays out as a generic.
Anomaly 1 — `mentioned` tokens still outside the dictionary (all C1): top Metformin (289), American Diabetes Association (247), Novo Nordisk (170), semaglutide (145), Tradjenta (137), Awiqli (131).
Anomaly 2 — R1 scorer marks 62 present answers with `our_rank = 0` (status M but no rank); legacy `visibility` field correlates 0.90 with our weight (reference only, not used).
Intrusion (all runs): competitor into our answers (C2) 29.6% [28.4–30.8], n=5830; ours into competitor answers (C3) 12.0% [10.8–13.4], n=2460; top competitor in C2: Wegovy.
Status vs text class mismatches: 813 prompts overall, 183 among C1 (class is never taken from `status`).
Audit: `audit/sample_visibility.csv` — 30 R1 C1 answers (10 present / 10 absent / 10 INN-only, seed 42); stop for manual review, proceed if ≥ 90% agree.
Outputs: visibility_summary.json, visibility_by_prompt.csv (328 C1 prompts, `in_headline` marks R1), visibility_answers.csv (2970 rows incl. excluded).

---
Appendix — by model family, R1 C1 (headline uses non-low_n families; versions pooled):

| family | versions | n_answers | groups | visibility % | CI95 | avg position | brand score | brand-bearing vis % | INN-only % | unstable groups % | single-run % | low_n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | claude-sonnet-4-6, claude-sonnet-5 | 708 | 453 | 44.4 | 40.8–48.0 | 1.57 | 42.0 | 87.5 | 8.0 | 6.6 | 45.0 |  |
| gemini | gemini-2.5-flash | 751 | 250 | 26.5 | 23.4–29.7 | 2.26 | 23.4 | 73.2 | 10.6 | 28.4 | 0.0 |  |
| gpt | gpt-4o | 753 | 250 | 11.0 | 9.0–13.4 | 2.18 | 9.8 | 55.5 | 31.0 | 27.2 | 0.0 |  |

By model version, R1 C1 (reference only):

| version | family | n_answers | visibility % | CI95 | avg position | brand score | INN-only % | low_n |
|---|---|---|---|---|---|---|---|---|
| claude-sonnet-4-6 | claude | 505 | 49.2 | 44.9–53.5 | 1.55 | 46.7 | 7.2 |  |
| claude-sonnet-5 | claude | 203 | 38.4 | 32.0–45.3 | 1.59 | 36.3 | 8.9 |  |
| gemini-2.5-flash | gemini | 751 | 26.5 | 23.4–29.7 | 2.26 | 23.4 | 10.6 |  |
| gpt-4o | gpt | 753 | 11.0 | 9.0–13.4 | 2.18 | 9.8 | 31.0 |  |

C1 prompts in other runs (reference only, not in headline; all families equal weight, low_n flagged in JSON):

| run | prompts | answers | surfaces | visibility % | CI95 | avg position | brand score | INN-only % |
|---|---|---|---|---|---|---|---|---|
| R2 | 4 | 23 | api | 29.2 | 14.7–49.6 | 1.00 | 29.2 | 4.2 |
| R3 | 7 | 42 | api | 64.3 | 49.2–77.0 | 1.15 | 63.6 | 35.7 |
| R5 | 8 | 105 | web | 71.1 | 61.8–78.9 | 2.17 | 63.6 | 26.3 |
| R6 | 59 | 529 | api | 42.6 | 38.5–46.8 | 2.07 | 38.6 | 17.2 |
