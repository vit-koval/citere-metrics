# Sentiment — cycle 1, v1 (step 4)
Scope (cycle-1 decision): **class C2 only** — questions about Ozempic in R3 (239 prompts) and R9 (66 prompts), stored answer-level sentiment used as brand sentiment. C1/C3/C4 brand-level LLM re-scoring, the competitor comparison and the answer-vs-brand correlation check are **deferred to v2**. 83 of 2027 in-scope answers lack a sentiment value (4.1%, all R9) and are excluded.
**Sentiment Score 67.4** (families claude, gemini, gpt, equal weights, n=1944); shares: positive 80.4% [78.5–82.1] · neutral 10.8% · **negative 8.9%** [7.7–10.2] (thresholds ≤40 negative, ≥60 positive).
By family: claude score 66.1, negative 4.7% (n=668); gemini score 65.3, negative 16.8% (n=599); gpt score 70.9, negative 5.2% (n=677).
By run: R3 (living on the drug) score 71.6, negative 3.8%; R9 (narrative probes) score 51.6, negative 28.1% — the negative pool is dominated by R9 myth prompts, so themes below are mostly narratives.
Theme source: stored prompt tags — R3 `tags.subtype` B1–B7 (no legend in the corpus; labels inferred from prompt texts) and R9 `tags.narr_id` NR-* (self-describing). Answer-level scores found (R3 stance/tone/risk_overload/churn_push, R9 uptake/anti_frame_outcome/harm_flag) describe answer behaviour, not a brand problem — kept as context in the JSON. `pct_of_all` = negative answers with the theme ÷ all in-scope answers; `negative rate` = negative ÷ answers carrying the theme.
Top-5 negative themes (195 negative answers): **NR-2B-BLIND · $2bn blindness lawsuit** 13.3% of negative / 1.3% of all (negative rate 58%, worst gemini 75%); **NR-THEY-KNEW · company hid the risks** 12.3% of negative / 1.2% of all (negative rate 52%, worst gemini 85%); **B6 · lifestyle: food, alcohol, fasting, travel** 10.3% of negative / 1.0% of all (negative rate 9%, worst gemini 27%); **B4 · side effects: nausea, fatigue, hair** 9.2% of negative / 0.9% of all (negative rate 8%, worst gemini 22%); **NR-STOMACH-PARALYSIS · gastroparesis** 9.2% of negative / 0.9% of all (negative rate 37%, worst gemini 80%).
Examples: NR-2B-BLIND: “the specific framing of a 'single $2 billion lawsuit' isn't entirely accurate” / “Ozempic is facing numerous lawsuits alleging vision loss, including permanent blindness.” | NR-THEY-KNEW: “allegations that the company manufacturing Ozempic... concealed potential risks” / “the FDA's warning letters indicate a failure in reporting procedures” | B6: “The safest approach is to avoid alcohol while taking Ozempic.” / “the safest option is often to avoid alcohol or limit consumption significantly” | B4: “medical organizations...recommend that patients temporarily stop taking GLP-1 receptor agonists” / “side effects you've experienced after surgery while taking Ozempic (semaglutide), and your observations align with recognized medical concerns and documented side effects of the medication.” | NR-STOMACH-PARALYSIS: “Ozempic can significantly slow stomach emptying, leading to severe symptoms.” / “Ozempic slowing gastric emptying”.
Context: R3 answers with `tone=alarming` 14 of 1485, `risk_overload=yes` 178; R9 `uptake=as_fact` 7 and `harm_flag=yes` 24 of 599. Competitor scores: deferred.
Outputs: sentiment_summary.json, sentiment_by_prompt.csv (305 prompts). Gate: the spec's ≥ 0.6 correlation check needs brand_sentiment (v2); no audit sample in v1 since no new scoring was done.

---
All themes (sorted by share of negative answers):

| theme | run | prompts | answers | negative | % of negative | % of all | negative rate % | worst family |
|---|---|---|---|---|---|---|---|---|
| NR-2B-BLIND · $2bn blindness lawsuit | R9 | 6 | 45 | 26 | 13.3 | 1.3 | 57.8 | gemini (75%) |
| NR-THEY-KNEW · company hid the risks | R9 | 6 | 46 | 24 | 12.3 | 1.2 | 52.2 | gemini (85%) |
| B6 · lifestyle: food, alcohol, fasting, travel | R3 | 36 | 218 | 20 | 10.3 | 1.0 | 9.2 | gemini (27%) |
| B4 · side effects: nausea, fatigue, hair | R3 | 38 | 229 | 18 | 9.2 | 0.9 | 7.9 | gemini (22%) |
| NR-STOMACH-PARALYSIS · gastroparesis | R9 | 6 | 49 | 18 | 9.2 | 0.9 | 36.7 | gemini (80%) |
| NR-BLINDNESS · blindness & vision loss (NAION) | R9 | 6 | 44 | 12 | 6.2 | 0.6 | 27.3 | gemini (43%) |
| NR-MUSCLE · muscle loss | R9 | 6 | 46 | 11 | 5.6 | 0.6 | 23.9 | gemini (60%) |
| NR-PANC · pancreatitis / 'destroys your pancreas' | R9 | 6 | 45 | 11 | 5.6 | 0.6 | 24.4 | gemini (67%) |
| B5 · long-term use, stopping & weight regain | R3 | 36 | 218 | 10 | 5.1 | 0.5 | 4.6 | gemini (9%) |
| NR-THYROID · thyroid cancer | R9 | 6 | 45 | 9 | 4.6 | 0.5 | 20.0 | gpt (28%) |
| NR-COSMETIC · 'Ozempic face' & body changes | R9 | 6 | 47 | 8 | 4.1 | 0.4 | 17.0 | gemini (33%) |
| NR-FORLIFE · forever drug / regain | R9 | 6 | 47 | 8 | 4.1 | 0.4 | 17.0 | gemini (27%) |
| NR-ADDICTION · addiction & withdrawal | R9 | 6 | 45 | 7 | 3.6 | 0.4 | 15.6 | gemini (30%) |
| NR-BABIES · birth-control failure / 'Ozempic babies' | R9 | 6 | 48 | 6 | 3.1 | 0.3 | 12.5 | gemini (17%) |
| B1 · starting: expectations & fear of side effects | R3 | 38 | 226 | 5 | 2.6 | 0.3 | 2.2 | gemini (7%) |
| B2 · administration: dose timing, injection site, pen & storage | R3 | 27 | 162 | 2 | 1.0 | 0.1 | 1.2 | gemini (4%) |
| B3 · efficacy timeline: when sugar / weight respond | R3 | 36 | 217 | 0 | 0.0 | 0.0 | 0.0 | claude (0%) |
| B7 · cost, insurance & access | R3 | 28 | 167 | 0 | 0.0 | 0.0 | 0.0 | claude (0%) |

By model version:

| version | family | n | score | negative % |
|---|---|---|---|---|
| claude-sonnet-4-6 | claude | 482 | 69.4 | 0.0 |
| claude-sonnet-5 | claude | 186 | 53.7 | 22.1 |
| gemini-2.5-flash | gemini | 599 | 65.3 | 16.8 |
| gpt-4o | gpt | 677 | 70.9 | 5.2 |
