# Competitive Benchmarking — cycle 1 (step 3a)
Scope: R1 C1 category prompts (250 prompts, 2212 answers after filters); 11 dictionary competitors; families pooled, equal weights; position = text ordinal among dictionary brands (INN never counts).
**Overall Win Rate 76.6%** [Wilson 95% 74.9–78.2] over 2471 overlap answers (answers naming both us and the competitor), weighted by each competitor's overlap count.
Top-3 by Impact (share of C1 prompt×model groups the competitor takes from us): Jardiance 6.8% (position 4.6 / absence 2.1; win rate 63.1%, n=301); Wegovy 5.8% (position 1.7 / absence 4.1; win rate 79.4%, n=250); Farxiga 5.7% (position 3.7 / absence 2.0; win rate 64.2%, n=261).
Diagnosis: by_position dominates — we are named but ranked lower (authority/position problem).
Worst model family: gemini (win rate 70.0%, top impact competitor Jardiance); best: claude.
Worst zone: HEART & KIDNEY (win rate 46.3% over 27 overlap answers, top impact competitor Farxiga).
Reliability: 1700 overlap groups; unstable (repeats flip the winner) 17.42%; single-run 61.18%; ties 0; low_n competitors (< 20 overlap answers): none.
Duel Verdict (R2, 141 C4 prompts, 799 scored answers of 850; none/na/third excluded 6.0%): **duel win rate 36.9%** [33.6–40.3]; by family: claude 36.7%, gemini 37.3%, gpt 36.6%.
Duel by competitor asked: Mounjaro 23.2% (n=412), Wegovy 13.8% (n=85), Zepbound 19.7% (n=63), Rybelsus 71.8% (n=108), Trulicity 61.1% (n=102), Saxenda 82.1% (n=41). R2 non-C4 prompts are family pairs (Wegovy vs Zepbound…): 791 of 797 answers there are `na` and are not our duel.
Decision — worst_model / worst_zone in the leaderboard are by highest Impact (the prioritization metric), not lowest Win Rate.
Audit: `audit/sample_benchmarking.csv` — 40 R1 C1 answers with ≥1 competitor present (seed 42), one row per answer × competitor; review overlap / win / loss_type by eye.
Outputs: benchmark_summary.json, benchmark_by_prompt.csv (2750 prompt×competitor rows), benchmark_pairs.csv (24332 rows).

---
Leaderboard (sorted by Impact; Win Rate CI = Wilson 95% by overlap answers):

| competitor | overlap answers | Win Rate % | CI95 | Impact % | by_position % | by_absence % | worst model | worst zone | low_n |
|---|---|---|---|---|---|---|---|---|---|
| Jardiance | 301 | 63.1 | 57.5–68.3 | 6.8 | 4.6 | 2.1 | gemini | HEART & KIDNEY |  |
| Wegovy | 250 | 79.4 | 74.0–83.9 | 5.8 | 1.7 | 4.1 | gpt | PRICE & ACCESS |  |
| Farxiga | 261 | 64.2 | 58.2–69.7 | 5.7 | 3.7 | 2.0 | gemini | HEART & KIDNEY |  |
| Mounjaro | 411 | 85.9 | 82.2–89.0 | 4.8 | 2.5 | 2.3 | gemini | STARTING & SWITCHING |  |
| Zepbound | 136 | 75.7 | 67.9–82.2 | 4.2 | 1.3 | 3.0 | gpt | PRICE & ACCESS |  |
| Invokana | 177 | 62.2 | 54.9–69.1 | 3.9 | 2.8 | 1.1 | gemini | SAFETY & CONTRAINDICATIONS |  |
| Rybelsus | 252 | 88.0 | 83.4–91.4 | 3.3 | 1.4 | 1.9 | gemini | STARTING & SWITCHING |  |
| Januvia | 162 | 74.3 | 67.1–80.4 | 2.9 | 2.0 | 0.9 | gemini | LIVING ON THE DRUG |  |
| Victoza | 238 | 84.3 | 79.1–88.4 | 2.5 | 1.7 | 0.7 | gemini | STARTING & SWITCHING |  |
| Saxenda | 49 | 71.3 | 57.5–82.1 | 2.3 | 0.6 | 1.7 | gemini | PRICE & ACCESS |  |
| Trulicity | 234 | 82.1 | 76.7–86.5 | 2.3 | 2.1 | 0.2 | gemini | LIVING ON THE DRUG |  |

By model family (R1 C1):

| family | versions | win rate % | overlap answers | top impact competitor | its impact % |
|---|---|---|---|---|---|
| claude | claude-sonnet-4-6, claude-sonnet-5 | 84.8 | 1229 | Jardiance | 7.2 |
| gemini | gemini-2.5-flash | 70.0 | 848 | Jardiance | 8.6 |
| gpt | gpt-4o | 75.0 | 394 | Wegovy | 7.3 |

By zone (R1 C1):

| zone | prompts | win rate % | overlap answers | top impact competitor | its impact % |
|---|---|---|---|---|---|
| BLOOD SUGAR & GLYCEMIC CONTROL | 49 | 84.5 | 437 | Jardiance | 5.5 |
| HEART & KIDNEY | 4 | 46.3 | 27 | Farxiga | 21.5 |
| LIVING ON THE DRUG | 18 | 73.5 | 185 | Januvia | 10.2 |
| PRICE & ACCESS | 14 | 75.3 | 119 | Wegovy | 26.8 |
| SAFETY & CONTRAINDICATIONS | 22 | 60.1 | 190 | Farxiga | 11.3 |
| STARTING & SWITCHING | 92 | 77.8 | 1205 | Jardiance | 9.7 |
| WEIGHT LOSS | 51 | 79.9 | 308 | Wegovy | 14.7 |
