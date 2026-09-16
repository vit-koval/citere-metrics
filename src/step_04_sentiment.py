"""Step 4 — Sentiment Analysis, v1 (sentiment_analysis_spec.md).

Reads  data/normalized/answers.parquet + config/*.yaml
Writes data/metrics/cycle_01/sentiment_summary.json, sentiment_by_prompt.csv, sentiment_report.md

v1 scope (cycle-1 decision): class C2 only — questions about our brand (runs R3, R9), where the stored answer-level
sentiment ≈ brand sentiment. No LLM re-scoring in this version: C1/C3/C4 brand sentiment and the competitor comparison
are DEFERRED, and the answer-vs-brand correlation check (spec §1) is not applicable. Negative themes come from the stored
prompt tags (R3 tags.subtype B1–B7, R9 tags.narr_id NR-*), as spec §4 allows.
"""
import json
import math
import re
import sys
from typing import Dict, List, Optional

import pandas as pd

from src import common as C

SCOPE_RUNS = ("R3", "R9")
# R3 B-subtype labels inferred from the prompt texts (the corpus carries no legend); R9 narrative ids are self-describing.
B_LABELS = {
    "B1": "B1 · starting: expectations & fear of side effects",
    "B2": "B2 · administration: dose timing, injection site, pen & storage",
    "B3": "B3 · efficacy timeline: when sugar / weight respond",
    "B4": "B4 · side effects: nausea, fatigue, hair",
    "B5": "B5 · long-term use, stopping & weight regain",
    "B6": "B6 · lifestyle: food, alcohol, fasting, travel",
    "B7": "B7 · cost, insurance & access",
}
NR_LABELS = {
    "NR-PANC": "NR-PANC · pancreatitis / 'destroys your pancreas'", "NR-THEY-KNEW": "NR-THEY-KNEW · company hid the risks",
    "NR-BABIES": "NR-BABIES · birth-control failure / 'Ozempic babies'", "NR-STOMACH-PARALYSIS": "NR-STOMACH-PARALYSIS · gastroparesis",
    "NR-MUSCLE": "NR-MUSCLE · muscle loss", "NR-2B-BLIND": "NR-2B-BLIND · $2bn blindness lawsuit", "NR-ADDICTION": "NR-ADDICTION · addiction & withdrawal",
    "NR-FORLIFE": "NR-FORLIFE · forever drug / regain", "NR-BLINDNESS": "NR-BLINDNESS · blindness & vision loss (NAION)",
    "NR-THYROID": "NR-THYROID · thyroid cancer", "NR-COSMETIC": "NR-COSMETIC · 'Ozempic face' & body changes",
}


def _r(x, nd=1):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _weights(models_cfg: dict) -> Optional[Dict[str, float]]:
    w = models_cfg.get("weights", "equal")
    return None if w == "equal" else dict(w)


def snippet(text: str, brand_re: "re.Pattern", max_words: int = 25) -> str:
    """≤ 25 words around the first brand mention."""
    words = text.split()
    idx = next((i for i, w in enumerate(words) if brand_re.search(w)), 0)
    start = max(0, idx - 8)
    return " ".join(words[start:start + max_words])


def main() -> int:
    cfg = C.load_configs()
    bd = C.BrandDictionary(cfg["brands"])
    lo_t, hi_t = cfg["thresholds"]["sentiment_thresholds"]
    weights = _weights(cfg["models"])
    fam_map, _, _ = C.model_maps(cfg["models"])
    raw = C.load_raw_corpus()  # only for prompt-level tags (not stored in answers.parquet)
    tags = {(p["pid"], p["run"]): p.get("tags", {}) for p in raw["prompts"]}
    scores_extra = {}
    a = C.load_answers()
    a["comps_present"] = a["comps_present"].map(lambda x: list(x) if x is not None else [])

    c2_all = a[(a["class"] == "C2") & (~a["excluded"])]
    scope = c2_all[c2_all["run"].isin(SCOPE_RUNS)].copy()
    used = scope.dropna(subset=["answer_sentiment"]).copy()
    used["brand_sentiment"] = used["answer_sentiment"]  # C2: answer-level ≈ brand-level (spec §1)
    used["positive"] = (used["brand_sentiment"] >= hi_t).astype(int)
    used["negative"] = (used["brand_sentiment"] <= lo_t).astype(int)
    used["neutral"] = 1 - used["positive"] - used["negative"]
    used["theme_code"] = [tags.get((p, r), {}).get("subtype") or tags.get((p, r), {}).get("narr_id") for p, r in zip(used["pid"], used["run"])]
    used["theme"] = used["theme_code"].map(lambda k: B_LABELS.get(k, NR_LABELS.get(k, k)))
    used["mood"] = [tags.get((p, r), {}).get("mood") for p, r in zip(used["pid"], used["run"])]
    used["quote"] = used["scores_json"].map(lambda s: (json.loads(s).get("turning_phrase") or json.loads(s).get("evidence") or "").strip())

    # ---- score & shares: repeats -> prompt×model -> family -> overall ----
    def block(df: pd.DataFrame) -> dict:
        sc = C.aggregate_bottom_up(df, "brand_sentiment", ci_basis="answers", family_weights=weights)
        out = {"score": float(sc["overall"]["brand_sentiment"].iloc[0]), "n": int(sc["overall"]["n_answers"].iloc[0]),
               "n_prompts": int(df.drop_duplicates(["pid", "run"]).shape[0]), "by_model": {}}
        for k in ("positive", "neutral", "negative"):
            ag = C.aggregate_bottom_up(df, k, ci_basis="answers", family_weights=weights)
            o = ag["overall"].iloc[0]
            out[k + "_pct"] = 100.0 * float(o[k]); out[k + "_ci95"] = [100.0 * float(o["ci_lo"]), 100.0 * float(o["ci_hi"])]
            for r in ag["family"].itertuples():
                out["by_model"].setdefault(r.model_family, {})[k + "_pct"] = 100.0 * float(getattr(r, k))
                out["by_model"][r.model_family][k + "_ci95"] = [100.0 * float(r.ci_lo), 100.0 * float(r.ci_hi)]
        for r in sc["family"].itertuples():
            out["by_model"].setdefault(r.model_family, {})["score"] = float(r.brand_sentiment)
            out["by_model"][r.model_family]["n"] = int(r.n_answers)
        return out

    overall = block(used)
    by_run = {run: block(g) for run, g in used.groupby("run")}
    ver = C.aggregate_bottom_up(used, "brand_sentiment", family_col="model", ci_basis="answers")["family"]
    neg_ver = C.aggregate_bottom_up(used, "negative", family_col="model", ci_basis="answers")["family"]
    by_version = [{"model": r.model, "family": fam_map.get(r.model), "score": _r(r.brand_sentiment), "n": int(r.n_answers),
                   "negative_pct": _r(100.0 * float(neg_ver.set_index("model").loc[r.model, "negative"]))} for r in ver.itertuples()]

    # ---- negative themes from stored prompt tags -------------------------
    neg = used[used["negative"] == 1]
    n_neg, n_all = len(neg), len(used)
    themes = []
    for code, g in used.groupby("theme_code"):
        gn = g[g["negative"] == 1]
        fam_neg = g.groupby("model_family")["negative"].mean()
        ex = []
        for r in gn.sort_values("brand_sentiment").itertuples():
            q = r.quote if r.quote and len(r.quote.split()) <= 25 else snippet(r.answer_clean, bd._our_re)
            if q and q not in ex:
                ex.append(q)
            if len(ex) == 2:
                break
        themes.append({"theme": g["theme"].iloc[0], "code": code, "run": g["run"].iloc[0],
                       "pct_of_negative": 100.0 * len(gn) / n_neg if n_neg else None,
                       "pct_of_all": 100.0 * len(gn) / n_all,
                       "negative_rate_within_theme": 100.0 * float(g["negative"].mean()),
                       "n_answers": int(len(g)), "n_negative": int(len(gn)), "n_prompts": int(g.drop_duplicates(["pid", "run"]).shape[0]),
                       "worst_model": fam_neg.idxmax() if len(fam_neg) else None, "worst_model_negative_pct": 100.0 * float(fam_neg.max()) if len(fam_neg) else None,
                       "by_model_negative_pct": {k: _r(100.0 * v) for k, v in fam_neg.items()}, "examples": ex})
    themes.sort(key=lambda d: (-(d["pct_of_negative"] or 0), d["theme"]))
    top5 = themes[:5]

    # field inventory (what was found before choosing)
    def dist(run, getter):
        cnt = {}
        for p in raw["prompts"]:
            if p["run"] == run:
                v = getter(p); cnt[v] = cnt.get(v, 0) + 1
        return dict(sorted(cnt.items(), key=lambda kv: (-kv[1], str(kv[0]))))
    def adist(run, key):
        cnt = {}
        for p in raw["prompts"]:
            if p["run"] == run:
                for e in p["models"]:
                    v = str(e.get("scores", {}).get(key)); cnt[v] = cnt.get(v, 0) + 1
        return dict(sorted(cnt.items(), key=lambda kv: -kv[1])[:8])
    fields_found = {
        "R3": {"prompt_tags.subtype (B-code, no legend in corpus; labels inferred from prompt texts)": dist("R3", lambda p: p["tags"].get("subtype")),
               "prompt_tags.mood": dist("R3", lambda p: p["tags"].get("mood")), "prompt_tags.tenure": dist("R3", lambda p: p["tags"].get("tenure")),
               "answer_scores.stance": adist("R3", "stance"), "answer_scores.tone": adist("R3", "tone"), "answer_scores.risk_overload": adist("R3", "risk_overload"),
               "answer_scores.churn_push": adist("R3", "churn_push"), "answer_scores.turning_phrase": "free-text quote (500 distinct; used as verbatim example where ≤ 25 words)"},
        "R9": {"prompt_tags.narr_id (NR-narrative, self-describing)": dist("R9", lambda p: p["tags"].get("narr_id")),
               "prompt_tags.probe_type": dist("R9", lambda p: p["tags"].get("probe_type")),
               "answer_scores.uptake": adist("R9", "uptake"), "answer_scores.anti_frame_outcome": adist("R9", "anti_frame_outcome"),
               "answer_scores.harm_flag": adist("R9", "harm_flag"), "answer_scores.churn_advice": adist("R9", "churn_advice"),
               "answer_scores.evidence": "free-text quote (552 distinct; used as verbatim example where ≤ 25 words)"},
        "choice": "themes = R3 tags.subtype (B1–B7) + R9 tags.narr_id (NR-*): the only fields that name a problem per prompt; answer-level scores (stance/tone/uptake…) describe the answer's behaviour, not a problem attributed to the brand, and are reported as context only",
    }
    tone_ctx = {"R3_tone": adist("R3", "tone"), "R3_risk_overload": adist("R3", "risk_overload"), "R9_uptake": adist("R9", "uptake"), "R9_harm_flag": adist("R9", "harm_flag")}
    neg_by_mood = {str(k): _r(100.0 * v) for k, v in used.groupby("mood")["negative"].mean().items()} if used["mood"].notna().any() else {}

    def rd(d):
        return {k: (_r(v) if isinstance(v, float) else ([_r(x) for x in v] if isinstance(v, list) and v and isinstance(v[0], float) else ({kk: rd(vv) if isinstance(vv, dict) else (_r(vv) if isinstance(vv, float) else ([_r(x) for x in vv] if isinstance(vv, list) and vv and isinstance(vv[0], float) else vv)) for kk, vv in v.items()} if isinstance(v, dict) else v))) for k, v in d.items()}

    summary = {
        "brand": bd.our_name, "version": "v1 — C2 only, stored sentiment, no LLM re-scoring",
        "scope": {"classes_used": ["C2"], "runs_used": list(SCOPE_RUNS), "deferred": ["C1/C3/C4 brand-level re-scoring (LLM)", "competitor comparison (needs C3 re-scoring)", "answer-vs-brand sentiment correlation check (needs brand_sentiment)"],
                  "thresholds": {"negative_max": lo_t, "positive_min": hi_t}, "aggregation": "repeats → prompt×model → family (versions pooled) → overall, equal weights; Wilson CI by answers"},
        "answers_with_brand": int(len(c2_all)), "answers_in_scope": int(len(scope)), "answers_with_sentiment": int(len(used)),
        "sentiment_missing_pct": _r(100.0 * (1 - len(used) / len(scope))), "prompts_in_scope": int(scope.drop_duplicates(["pid", "run"]).shape[0]),
        "c2_answers_outside_scope_by_run": {k: int(v) for k, v in c2_all[~c2_all["run"].isin(SCOPE_RUNS)].groupby("run").size().items()},
        "score": _r(overall["score"]),
        "shares": {"positive_pct": _r(overall["positive_pct"]), "neutral_pct": _r(overall["neutral_pct"]), "negative_pct": _r(overall["negative_pct"]),
                   "positive_ci95": [_r(x) for x in overall["positive_ci95"]], "neutral_ci95": [_r(x) for x in overall["neutral_ci95"]], "negative_ci95": [_r(x) for x in overall["negative_ci95"]]},
        "by_model": [dict(model=f, **rd(v)) for f, v in sorted(overall["by_model"].items())],
        "by_model_version": by_version,
        "by_run": {run: rd({k: v for k, v in b.items() if k != "by_model"}) | {"by_model": {f: rd(v) for f, v in b["by_model"].items()}} for run, b in by_run.items()},
        "competitors": [], "competitors_note": "deferred — needs brand-level re-scoring of C3 answers (v2)",
        "top_negative_themes": [rd(t) for t in top5],
        "all_themes": [rd({k: v for k, v in t.items() if k != "examples"}) for t in themes],
        "theme_fields_found": fields_found, "answer_behaviour_context": tone_ctx, "negative_pct_by_prompt_mood_R3": neg_by_mood,
        "n_negative_answers": int(n_neg),
    }

    # ---- by prompt ----------------------------------------------------------
    pm = C.aggregate_bottom_up(used, "brand_sentiment", ci_basis="answers")["pm"]
    pmn = C.aggregate_bottom_up(used, "negative", ci_basis="answers")["pm"]
    fam = pm.groupby(["pid", "run", "model_family"])["brand_sentiment"].mean().reset_index()
    famn = pmn.groupby(["pid", "run", "model_family"])["negative"].mean().reset_index()
    meta = used.drop_duplicates(["pid", "run"]).set_index(["pid", "run"])[["text", "zone", "class", "theme"]]
    rows = []
    for (pid, run), g in fam.groupby(["pid", "run"]):
        gn = famn[(famn["pid"] == pid) & (famn["run"] == run)]
        rows.append({"pid": pid, "run": run, "text": meta.loc[(pid, run), "text"], "zone": meta.loc[(pid, run), "zone"], "class": "C2",
                     "n": int(used[(used["pid"] == pid) & (used["run"] == run)].shape[0]), "score": float(g["brand_sentiment"].mean()),
                     "negative_pct": 100.0 * float(gn["negative"].mean()), "themes": meta.loc[(pid, run), "theme"]})
    by_prompt = pd.DataFrame(rows).sort_values(["run", "pid"])

    C.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(C.METRICS_DIR / "sentiment_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    by_prompt.to_csv(C.METRICS_DIR / "sentiment_by_prompt.csv", index=False)

    # ---- report (≤ 10 lines) --------------------------------------------------
    bm = summary["by_model"]
    L = [
        "# Sentiment — cycle 1, v1 (step 4)",
        "Scope (cycle-1 decision): **class C2 only** — questions about Ozempic in R3 ({} prompts) and R9 ({} prompts), stored answer-level sentiment used as brand sentiment. C1/C3/C4 brand-level LLM re-scoring, the competitor comparison and the answer-vs-brand correlation check are **deferred to v2**. {} of {} in-scope answers lack a sentiment value ({:.1f}%, all R9) and are excluded.".format(
            by_run["R3"]["n_prompts"], by_run["R9"]["n_prompts"], len(scope) - len(used), len(scope), summary["sentiment_missing_pct"]),
        "**Sentiment Score {:.1f}** (families {}, equal weights, n={}); shares: positive {:.1f}% [{:.1f}–{:.1f}] · neutral {:.1f}% · **negative {:.1f}%** [{:.1f}–{:.1f}] (thresholds ≤{} negative, ≥{} positive).".format(
            summary["score"], ", ".join(d["model"] for d in bm), overall["n"], overall["positive_pct"], *overall["positive_ci95"], overall["neutral_pct"], overall["negative_pct"], *overall["negative_ci95"], lo_t, hi_t),
        "By family: " + "; ".join("{} score {:.1f}, negative {:.1f}% (n={})".format(d["model"], d["score"], d["negative_pct"], d["n"]) for d in bm) + ".",
        "By run: R3 (living on the drug) score {:.1f}, negative {:.1f}%; R9 (narrative probes) score {:.1f}, negative {:.1f}% — the negative pool is dominated by R9 myth prompts, so themes below are mostly narratives.".format(
            by_run["R3"]["score"], by_run["R3"]["negative_pct"], by_run["R9"]["score"], by_run["R9"]["negative_pct"]),
        "Theme source: stored prompt tags — R3 `tags.subtype` B1–B7 (no legend in the corpus; labels inferred from prompt texts) and R9 `tags.narr_id` NR-* (self-describing). Answer-level scores found (R3 stance/tone/risk_overload/churn_push, R9 uptake/anti_frame_outcome/harm_flag) describe answer behaviour, not a brand problem — kept as context in the JSON. `pct_of_all` = negative answers with the theme ÷ all in-scope answers; `negative rate` = negative ÷ answers carrying the theme.",
        "Top-5 negative themes ({} negative answers): ".format(n_neg) + "; ".join("**{}** {:.1f}% of negative / {:.1f}% of all (negative rate {:.0f}%, worst {} {:.0f}%)".format(
            t["theme"], t["pct_of_negative"], t["pct_of_all"], t["negative_rate_within_theme"], t["worst_model"], t["worst_model_negative_pct"]) for t in top5) + ".",
        "Examples: " + " | ".join("{}: “{}” / “{}”".format(t["code"], *(t["examples"] + ["", ""])[:2]) for t in top5) + ".",
        "Context: R3 answers with `tone=alarming` {} of {}, `risk_overload=yes` {}; R9 `uptake=as_fact` {} and `harm_flag=yes` {} of {}. Competitor scores: deferred.".format(
            tone_ctx["R3_tone"].get("alarming", 0), sum(tone_ctx["R3_tone"].values()), tone_ctx["R3_risk_overload"].get("yes", 0), tone_ctx["R9_uptake"].get("as_fact", 0), tone_ctx["R9_harm_flag"].get("yes", 0), sum(tone_ctx["R9_harm_flag"].values())),
        "Outputs: sentiment_summary.json, sentiment_by_prompt.csv ({} prompts). Gate: the spec's ≥ 0.6 correlation check needs brand_sentiment (v2); no audit sample in v1 since no new scoring was done.".format(len(by_prompt)),
    ]
    tbl = ["", "---", "All themes (sorted by share of negative answers):", "", "| theme | run | prompts | answers | negative | % of negative | % of all | negative rate % | worst family |", "|---|---|---|---|---|---|---|---|---|"]
    for t in themes:
        tbl.append("| {} | {} | {} | {} | {} | {:.1f} | {:.1f} | {:.1f} | {} ({:.0f}%) |".format(t["theme"], t["run"], t["n_prompts"], t["n_answers"], t["n_negative"], t["pct_of_negative"], t["pct_of_all"], t["negative_rate_within_theme"], t["worst_model"], t["worst_model_negative_pct"]))
    tbl += ["", "By model version:", "", "| version | family | n | score | negative % |", "|---|---|---|---|---|"]
    for d in by_version:
        tbl.append("| {} | {} | {} | {:.1f} | {:.1f} |".format(d["model"], d["family"], d["n"], d["score"], d["negative_pct"]))
    (C.METRICS_DIR / "sentiment_report.md").write_text("\n".join(L + tbl) + "\n", encoding="utf-8")
    print("\n".join(L[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
