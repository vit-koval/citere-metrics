# Spec: Sentiment Analysis

Version 1.0 · For Claude Code · Input: the same consolidated JSON. Brand dictionary, prompt classification (C1–C4) and quality filters — from `visibility_score_spec.md`, unchanged.

Three outputs:
1. **Sentiment Score** 0–100 — one figure, with delta, competitor alongside
2. **Shares** positive / neutral / negative
3. **Top-5 negative themes** — the words models use to describe problems

---

## 1. Which answers we use — and why the stored field is not enough

**Known fact about the data:** the stored `sentiment` field is answer-level, not brand-level. Median sentiment is 75 both in answers that name our brand and in answers that do not (1,489 answers without the brand carry a sentiment value). It measures how friendly the answer is, not how AI describes us.

Therefore:
- **Class C2 (question about our brand) — primary.** There the answer is about us, so answer-level ≈ brand-level. Runs R3, R9 (R4 has no sentiment). Use the stored field.
- **Classes C1, C3, C4 — brand-level re-scoring is mandatory**, not optional. For every answer where our brand is present, score with a fixed LLM prompt: "Rate 0–100 how favorably this answer presents brand X specifically — not the topic, not other brands." Store as `brand_sentiment`. Do the same for each competitor present. The stored `sentiment` is kept as `answer_sentiment` for reference.
- An answer without the brand has no brand sentiment — excluded.

Report the correlation between `answer_sentiment` and `brand_sentiment` on C2 as a sanity check; if it is below 0.6, stop and show 20 examples.

Apply quality filters from the visibility spec first.

---

## 2. Sentiment Score

**Source:** `brand_sentiment` (0–100) — the stored field on C2, the re-scored value elsewhere (§1). Answers where neither is available are excluded; report the share.

**Aggregation** (as in the visibility spec): repeats → prompt×model → model → overall, equal model weights.

- `Sentiment Score` = mean, 1 decimal
- `by_model` — the same per model
- `competitor` — the same figure per competitor, over answers where that competitor is present

---

## 3. Shares

Per answer, by thresholds:
- **positive** — sentiment ≥ 60
- **neutral** — 40 < sentiment < 60
- **negative** — sentiment ≤ 40

Thresholds — config parameter `sentiment_thresholds: [40, 60]`.

Aggregate shares as in §2. Output: `positive_pct`, `neutral_pct`, `negative_pct` (sum 100), overall and per model, and the same for competitors.

---

## 4. Top-5 negative themes

**What:** recurring problems models attribute to our brand in negative answers (sentiment ≤ 40).

**How:**
1. Take all negative answers containing our brand.
2. Extract problem phrases from each — short (1–4 words), normalized: `shortage`, `thyroid cancer risk`, `expensive`, `not approved for weight loss`, `stop taking`. Extraction — LLM call with a fixed prompt: "List the problems/risks/negative characteristics the answer attributes to brand X. Noun phrases only, no judgments, up to 5 per answer."
3. Normalize synonyms (`cost` / `expensive` / `price` → one theme) — LLM clustering into 15–30 themes; output the theme list for manual review.
4. Theme frequency = share of negative answers containing it. Also — share of **all** answers with the brand.
5. Top-5 by frequency. For each theme: `answers_pct`, `by_model` (which model most often), 2 verbatim quotes from answers (≤ 25 words) as evidence.

If `scores` already contains ready problem tags (R3 B-subtypes, R4 T-targets, R9 NR-narratives) — use them as the primary theme source, LLM extraction as a supplement; report what was found.

---

## 5. Output format

**5.1. `sentiment_summary.json`**
```json
{
  "brand": "...",
  "answers_with_brand": 0, "answers_with_sentiment": 0, "sentiment_missing_pct": 0.0,
  "score": 0.0,
  "shares": {"positive_pct": 0.0, "neutral_pct": 0.0, "negative_pct": 0.0},
  "by_model": [{"model": "...", "score": 0.0, "negative_pct": 0.0, "n": 0}],
  "competitors": [{"competitor": "...", "score": 0.0, "negative_pct": 0.0, "n": 0}],
  "top_negative_themes": [
    {"theme": "shortage", "pct_of_negative": 0.0, "pct_of_all": 0.0,
     "worst_model": "...", "examples": ["...", "..."]}
  ],
  "all_themes": [{"theme": "...", "pct_of_negative": 0.0}]
}
```

**5.2. `sentiment_by_prompt.csv`** — `pid, text, zone, class, n, score, negative_pct, themes`.

**5.3. Short report** (≤ 10 lines): Score and shares, spread across models, competitor Scores alongside, top-5 themes with percentages.

---

## 6. Do not

- Do not use the stored answer-level `sentiment` as brand sentiment outside C2.
- Do not split negative into on-label / beyond-label — next version, linked to Label Flag.
- Do not build attributes-vs-competitors or word clouds — not in this version.
- Do not change the 40/60 thresholds without a note in the report.
