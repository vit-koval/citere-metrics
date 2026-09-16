"""Step 3a — Competitive Benchmarking (competitive_benchmarking_spec.md).

Reads  data/normalized/answers.parquet + config/*.yaml
Writes data/metrics/cycle_01/benchmark_summary.json, benchmark_by_prompt.csv, benchmark_pairs.csv, benchmark_report.md
       audit/sample_benchmarking.csv (40 R1 C1 answers with >=1 competitor, seed 42, one row per answer x competitor present)

Scope (cycle-1 decision, as for step 2): Win Rate and Impact on R1 C1 only; families pooled, equal weights; Wilson CI by
number of overlap answers. Duel Verdict from R2 `scores.winner` on C4 prompts.
"""
import json
import math
import sys
from typing import Dict, List, Optional

import pandas as pd

from src import common as C

HEADLINE_RUN = "R1"
LOW_N_OVERLAP = 20
SAMPLE_N = 40
WINNER_MAP = {"ours": 1.0, "comp": 0.0, "split": 0.5}


def _r(x, nd=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _weights(models_cfg: dict) -> Optional[Dict[str, float]]:
    w = models_cfg.get("weights", "equal")
    return None if w == "equal" else dict(w)


def build_pairs(c1: pd.DataFrame, competitors: List[str]) -> pd.DataFrame:
    rows = []
    for r in c1.itertuples():
        cp = json.loads(r.comp_pos)
        we_pos = None if pd.isna(r.we_pos) else int(r.we_pos)
        for x in competitors:
            x_pos = cp.get(x)
            x_present = x_pos is not None
            overlap = bool(r.we_present) and x_present
            win = None
            tie = False
            if overlap:
                if we_pos < x_pos:
                    win = 1.0
                elif we_pos > x_pos:
                    win = 0.0
                else:
                    win, tie = 0.5, True
            if overlap and win == 0.0:
                loss = "by_position"
            elif x_present and not r.we_present:
                loss = "by_absence"
            else:
                loss = None
            rows.append({"pid": r.pid, "run": r.run, "zone": r.zone, "model": r.model, "model_family": r.model_family,
                         "repeat_idx": r.repeat_idx, "competitor": x, "we_present": int(bool(r.we_present)), "x_present": int(x_present),
                         "we_pos": we_pos, "x_pos": x_pos, "overlap": int(overlap), "win": win, "loss_type": loss,
                         "lost": int(loss is not None), "lost_pos": int(loss == "by_position"), "lost_abs": int(loss == "by_absence"), "tie": tie})
    df = pd.DataFrame(rows)
    df["we_pos"] = df["we_pos"].astype("Int64"); df["x_pos"] = df["x_pos"].astype("Int64")
    return df


def main() -> int:
    cfg = C.load_configs()
    bd = C.BrandDictionary(cfg["brands"])
    weights = _weights(cfg["models"])
    fam_map, _, _ = C.model_maps(cfg["models"])
    competitors = list(bd.competitors)

    a = C.load_answers()
    a["comps_present"] = a["comps_present"].map(lambda x: list(x) if x is not None else [])
    used = a[(a["class"] == "C1") & (a["run"] == HEADLINE_RUN) & (~a["excluded"])].copy()
    pairs = build_pairs(used, competitors)
    ties = int(pairs["tie"].sum())

    # ---- level 1: prompt x model x competitor -----------------------------
    g = pairs.groupby(["pid", "run", "zone", "model", "model_family", "competitor"])
    pm = g.agg(overlap_pm=("overlap", "mean"), lost_pm=("lost", "mean"), lost_pos_pm=("lost_pos", "mean"),
               lost_abs_pm=("lost_abs", "mean"), n_repeats=("overlap", "size")).reset_index()
    ov = pairs[pairs["overlap"] == 1].groupby(["pid", "run", "model", "competitor"])["win"].agg(
        win_pm="mean", n_overlap="size",
        stability=lambda s: max(int((s == 1).sum()), int((s == 0).sum()), int((s == 0.5).sum())) / len(s)).reset_index()
    pm = pm.merge(ov, on=["pid", "run", "model", "competitor"], how="left")
    pm["single_run"] = pm["n_overlap"].fillna(0) < 2
    pm["unstable"] = (~pm["single_run"]) & (pm["stability"] < 1.0)

    # ---- levels 2/3 via shared helper -----------------------------------
    win_agg = C.aggregate_bottom_up(pairs, "win", by=["competitor"], ci_basis="answers", family_weights=weights)
    lost_agg = C.aggregate_bottom_up(pairs, "lost", by=["competitor"], ci_basis="answers", family_weights=weights)
    lpos_agg = C.aggregate_bottom_up(pairs, "lost_pos", by=["competitor"], ci_basis="answers", family_weights=weights)
    labs_agg = C.aggregate_bottom_up(pairs, "lost_abs", by=["competitor"], ci_basis="answers", family_weights=weights)
    win_zone = C.aggregate_bottom_up(pairs, "win", by=["zone", "competitor"], ci_basis="answers", family_weights=weights)
    lost_zone = C.aggregate_bottom_up(pairs, "lost", by=["zone", "competitor"], ci_basis="answers", family_weights=weights)

    fam_win = win_agg["family"].set_index(["competitor", "model_family"])
    fam_lost = lost_agg["family"].set_index(["competitor", "model_family"])
    zone_lost = lost_zone["overall"].set_index(["zone", "competitor"])
    leaderboard = []
    for x in competitors:
        w = win_agg["overall"].set_index("competitor").loc[x] if x in set(win_agg["overall"]["competitor"]) else None
        l = lost_agg["overall"].set_index("competitor").loc[x]
        lp = lpos_agg["overall"].set_index("competitor").loc[x]
        la = labs_agg["overall"].set_index("competitor").loc[x]
        n_ov = int(w["n_answers"]) if w is not None else 0
        fam_imp = fam_lost.loc[x] if x in fam_lost.index.get_level_values(0) else None
        worst_model = fam_imp["lost"].idxmax() if fam_imp is not None and len(fam_imp) else None
        zl = zone_lost.xs(x, level="competitor") if x in zone_lost.index.get_level_values(1) else None
        worst_zone = zl["lost"].idxmax() if zl is not None and len(zl) else None
        leaderboard.append({
            "competitor": x, "overlap_answers": n_ov,
            "win_rate": 100.0 * float(w["win"]) if w is not None else None,
            "win_rate_ci95": [100.0 * float(w["ci_lo"]), 100.0 * float(w["ci_hi"])] if w is not None else None,
            "impact": 100.0 * float(l["lost"]), "impact_by_position": 100.0 * float(lp["lost_pos"]), "impact_by_absence": 100.0 * float(la["lost_abs"]),
            "worst_model": worst_model, "worst_zone": worst_zone, "low_n": n_ov < LOW_N_OVERLAP,
            "by_model": {f: {"win_rate": _r(100.0 * float(fam_win.loc[(x, f), "win"]), 2) if (x, f) in fam_win.index else None,
                             "n_overlap_answers": int(fam_win.loc[(x, f), "n_answers"]) if (x, f) in fam_win.index else 0,
                             "impact": _r(100.0 * float(fam_lost.loc[(x, f), "lost"]), 2)} for f in sorted(fam_lost.loc[x].index)} if fam_imp is not None else {},
        })
    leaderboard.sort(key=lambda d: -d["impact"])
    # overall win rate: mean of Win Rate(X) weighted by overlap answers
    tot_ov = sum(d["overlap_answers"] for d in leaderboard)
    overall_wr = sum(d["win_rate"] * d["overlap_answers"] for d in leaderboard if d["win_rate"] is not None) / tot_ov if tot_ov else float("nan")
    lo, hi = C.wilson_ci(overall_wr / 100.0 * tot_ov, tot_ov)

    # by model (family): win rate weighted by overlap answers across competitors; top impact competitor
    by_model = []
    for f in sorted(pairs["model_family"].unique()):
        sub = fam_win.xs(f, level="model_family") if f in fam_win.index.get_level_values(1) else None
        n = int(sub["n_answers"].sum()) if sub is not None else 0
        wr = float((sub["win"] * sub["n_answers"]).sum() / n) if n else float("nan")
        imp = fam_lost.xs(f, level="model_family")["lost"]
        by_model.append({"model": f, "versions": sorted(pairs.loc[pairs["model_family"] == f, "model"].unique().tolist()),
                         "win_rate": 100.0 * wr, "n_overlap_answers": n, "top_impact_competitor": imp.idxmax(), "top_impact": 100.0 * float(imp.max())})
    # by zone
    zw = win_zone["overall"].set_index(["zone", "competitor"])
    by_zone = []
    for z in sorted(pairs["zone"].unique()):
        sub = zw.xs(z, level="zone") if z in zw.index.get_level_values(0) else None
        n = int(sub["n_answers"].sum()) if sub is not None else 0
        wr = float((sub["win"] * sub["n_answers"]).sum() / n) if n else float("nan")
        imp = zone_lost.xs(z, level="zone")["lost"]
        by_zone.append({"zone": z, "win_rate": 100.0 * wr, "n_overlap_answers": n, "n_prompts": int(used[used["zone"] == z].drop_duplicates(["pid", "run"]).shape[0]),
                        "top_impact_competitor": imp.idxmax(), "top_impact": 100.0 * float(imp.max())})

    # ---- Duel Verdict (R2, class C4, scores.winner) -----------------------
    r2 = a[(a["run"] == "R2") & (~a["excluded"])].copy()
    r2["winner"] = r2["scores_json"].map(lambda s: json.loads(s).get("winner"))
    duel = {"available": bool(r2["winner"].notna().any())}
    if duel["available"]:
        c4 = r2[r2["class"] == "C4"].copy()
        c4["duel"] = c4["winner"].map(WINNER_MAP)
        scored = c4.dropna(subset=["duel"])
        agg = C.aggregate_bottom_up(scored, "duel", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
        fam = C.aggregate_bottom_up(scored, "duel", ci_basis="answers")["family"].set_index("model_family")
        ver = C.aggregate_bottom_up(scored, "duel", family_col="model", ci_basis="answers")["family"].set_index("model")
        c4p = c4.drop_duplicates(["pid", "run"])[["pid", "run", "text"]].copy()
        c4p["comps"] = c4p["text"].map(bd.competitors_present)
        by_comp = {}
        for x in competitors:
            keys = c4p[c4p["comps"].map(lambda l: x in l)][["pid", "run"]]
            sub = scored.merge(keys, on=["pid", "run"])
            if len(sub):
                o = C.aggregate_bottom_up(sub, "duel", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
                by_comp[x] = {"duel_win_rate": _r(100.0 * float(o["duel"])), "n_prompts": int(len(keys)), "n_scored_answers": int(o["n_answers"]),
                              "ci95": [_r(100.0 * float(o["ci_lo"])), _r(100.0 * float(o["ci_hi"]))]}
        wv = r2["winner"].fillna("<null>").value_counts()
        duel.update({
            "scope": "R2 answers on C4 prompts (both brands in the question); winner ours=1, comp=0, split=0.5; none/na/third excluded from the denominator",
            "duel_win_rate": 100.0 * float(agg["duel"]), "duel_win_rate_ci95": [100.0 * float(agg["ci_lo"]), 100.0 * float(agg["ci_hi"])],
            "n_scored": int(agg["n_answers"]), "n_c4_answers": int(len(c4)), "n_c4_prompts": int(c4.drop_duplicates(["pid", "run"]).shape[0]),
            "excluded_na_pct": 100.0 * float((~c4["winner"].isin(WINNER_MAP)).mean()),
            "excluded_breakdown_c4": {k: int(v) for k, v in c4["winner"].fillna("<null>").value_counts().items() if k not in WINNER_MAP},
            "r2_winner_by_class": {cls: {k: int(v) for k, v in r2.loc[r2["class"] == cls, "winner"].fillna("<null>").value_counts().items()} for cls in sorted(r2["class"].unique())},
            "by_competitor": by_comp,
            "by_model": {f: {"duel_win_rate": _r(100.0 * float(fam.loc[f, "duel"])), "n_scored": int(fam.loc[f, "n_answers"])} for f in fam.index},
            "by_model_version": {v: {"duel_win_rate": _r(100.0 * float(ver.loc[v, "duel"])), "n_scored": int(ver.loc[v, "n_answers"])} for v in ver.index},
        })

    # ---- quality ----------------------------------------------------------
    ov_groups = pm[pm["n_overlap"].fillna(0) > 0]
    quality = {"unstable_groups_pct": _r(100.0 * float(ov_groups.loc[~ov_groups["single_run"], "unstable"].mean())) if (~ov_groups["single_run"]).any() else None,
               "single_run_groups_pct": _r(100.0 * float(ov_groups["single_run"].mean())) if len(ov_groups) else None,
               "n_overlap_groups": int(len(ov_groups)), "ties_logged": ties,
               "answers_C1_excluded": int(((a["class"] == "C1") & (a["run"] == HEADLINE_RUN) & a["excluded"]).sum())}

    summary = {
        "brand": bd.our_name, "run_ids": [HEADLINE_RUN], "headline_scope": "R1 C1 prompts only (cycle-1 decision, as in visibility)",
        "config": {"model_weights": "equal" if weights is None else weights, "low_n_overlap_threshold": LOW_N_OVERLAP,
                   "position_source": "text ordinal among dictionary brands (visibility decision 2)", "competitors": competitors},
        "answers_C1_used": int(len(used)), "prompts_C1_used": int(used.drop_duplicates(["pid", "run"]).shape[0]),
        "overall": {"win_rate": _r(overall_wr), "win_rate_ci95": [_r(100 * lo), _r(100 * hi)], "n_overlap_answers": tot_ov,
                    "note": "mean of Win Rate(X) weighted by each competitor's overlap answers; CI by total overlap answers"},
        "leaderboard": [{k: (_r(v) if isinstance(v, float) else ([_r(x) for x in v] if isinstance(v, list) else v)) for k, v in d.items()} for d in leaderboard],
        "by_model": [{k: (_r(v) if isinstance(v, float) else v) for k, v in d.items()} for d in by_model],
        "by_zone": [{k: (_r(v) if isinstance(v, float) else v) for k, v in d.items()} for d in by_zone],
        "duel_verdict": {k: (_r(v) if isinstance(v, float) else ([_r(x) for x in v] if isinstance(v, list) and v and isinstance(v[0], float) else v)) for k, v in duel.items()},
        "quality": quality,
    }

    # ---- outputs ----------------------------------------------------------
    C.METRICS_DIR.mkdir(parents=True, exist_ok=True); C.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(C.METRICS_DIR / "benchmark_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    meta = used.drop_duplicates(["pid", "run"]).set_index(["pid", "run"])["text"]
    bp = pm.groupby(["pid", "run", "zone", "competitor"]).agg(overlap_pm=("overlap_pm", "mean"), win_pm=("win_pm", "mean"), lost_pm=("lost_pm", "mean"),
                                                             lost_pos_pm=("lost_pos_pm", "mean"), lost_abs_pm=("lost_abs_pm", "mean"), stability=("stability", "mean")).reset_index()
    bp["text"] = [meta.loc[(p, r)] for p, r in zip(bp["pid"], bp["run"])]
    bp = bp[["pid", "run", "text", "zone", "competitor", "overlap_pm", "win_pm", "lost_pm", "lost_pos_pm", "lost_abs_pm", "stability"]].sort_values(["pid", "competitor"])
    bp.to_csv(C.METRICS_DIR / "benchmark_by_prompt.csv", index=False)
    pairs.drop(columns=["lost", "lost_pos", "lost_abs", "tie"]).sort_values(["pid", "model", "repeat_idx", "competitor"]).to_csv(C.METRICS_DIR / "benchmark_pairs.csv", index=False)

    # audit sample: 40 answers with >=1 competitor present; one row per answer x competitor present
    cand = used[used["comps_present"].map(len) > 0].sort_values(["pid", "model", "repeat_idx"]).reset_index(drop=True)
    samp = cand.sample(n=min(SAMPLE_N, len(cand)), random_state=C.SEED)
    keys = samp[["pid", "run", "model", "repeat_idx"]]
    sp = pairs.merge(keys, on=["pid", "run", "model", "repeat_idx"])
    sp = sp[sp["x_present"] == 1].merge(samp[["pid", "run", "model", "repeat_idx", "answer_clean"]], on=["pid", "run", "model", "repeat_idx"])
    sp["answer_id"] = sp["pid"] + ":" + sp["model"] + ":" + sp["repeat_idx"].astype(str)
    sample_out = sp[["answer_id", "pid", "run", "model", "repeat_idx", "competitor", "we_present", "we_pos", "x_pos", "overlap", "win", "loss_type", "answer_clean"]].copy()
    sample_out = sample_out.sort_values(["pid", "model", "repeat_idx", "competitor"])
    sample_out = C.carry_forward_review(sample_out, C.AUDIT_DIR / "sample_benchmarking.csv",
                                        keys=["pid", "run", "model", "repeat_idx", "competitor"], computed_cols=["overlap", "win", "loss_type"])
    sample_out.to_csv(C.AUDIT_DIR / "sample_benchmarking.csv", index=False)

    # ---- report (<= 15 lines) + leaderboard appendix ----------------------
    top3 = leaderboard[:3]
    worst_m = min(by_model, key=lambda d: d["win_rate"] if d["win_rate"] == d["win_rate"] else 1e9)
    worst_z = min([z for z in by_zone if z["n_overlap_answers"] >= LOW_N_OVERLAP] or by_zone, key=lambda d: d["win_rate"])
    L = [
        "# Competitive Benchmarking — cycle 1 (step 3a)",
        "Scope: R1 C1 category prompts ({} prompts, {} answers after filters); {} dictionary competitors; families pooled, equal weights; position = text ordinal among dictionary brands (INN never counts).".format(
            summary["prompts_C1_used"], summary["answers_C1_used"], len(competitors)),
        "**Overall Win Rate {:.1f}%** [Wilson 95% {:.1f}–{:.1f}] over {} overlap answers (answers naming both us and the competitor), weighted by each competitor's overlap count.".format(
            overall_wr, 100 * lo, 100 * hi, tot_ov),
        "Top-3 by Impact (share of C1 prompt×model groups the competitor takes from us): " + "; ".join(
            "{} {:.1f}% (position {:.1f} / absence {:.1f}; win rate {:.1f}%, n={})".format(d["competitor"], d["impact"], d["impact_by_position"], d["impact_by_absence"], d["win_rate"], d["overlap_answers"]) for d in top3) + ".",
        "Diagnosis: {} — {}.".format(
            "by_position dominates" if sum(d["impact_by_position"] for d in top3) > sum(d["impact_by_absence"] for d in top3) else "by_absence dominates",
            "we are named but ranked lower (authority/position problem)" if sum(d["impact_by_position"] for d in top3) > sum(d["impact_by_absence"] for d in top3) else "we are not named where they are (presence/topic-coverage problem)"),
        "Worst model family: {} (win rate {:.1f}%, top impact competitor {}); best: {}.".format(
            worst_m["model"], worst_m["win_rate"], worst_m["top_impact_competitor"], max(by_model, key=lambda d: d["win_rate"])["model"]),
        "Worst zone: {} (win rate {:.1f}% over {} overlap answers, top impact competitor {}).".format(worst_z["zone"], worst_z["win_rate"], worst_z["n_overlap_answers"], worst_z["top_impact_competitor"]),
        "Reliability: {} overlap groups; unstable (repeats flip the winner) {}%; single-run {}%; ties {}; low_n competitors (< {} overlap answers): {}.".format(
            quality["n_overlap_groups"], quality["unstable_groups_pct"], quality["single_run_groups_pct"], ties, LOW_N_OVERLAP,
            ", ".join(d["competitor"] for d in leaderboard if d["low_n"]) or "none"),
    ]
    if duel["available"]:
        L.append("Duel Verdict (R2, {} C4 prompts, {} scored answers of {}; none/na/third excluded {:.1f}%): **duel win rate {:.1f}%** [{:.1f}–{:.1f}]; by family: {}.".format(
            duel["n_c4_prompts"], duel["n_scored"], duel["n_c4_answers"], duel["excluded_na_pct"], duel["duel_win_rate"], *duel["duel_win_rate_ci95"],
            ", ".join("{} {:.1f}%".format(f, v["duel_win_rate"]) for f, v in duel["by_model"].items())))
        L.append("Duel by competitor asked: {}. R2 non-C4 prompts are family pairs (Wegovy vs Zepbound…): {} of {} answers there are `na` and are not our duel.".format(
            ", ".join("{} {:.1f}% (n={})".format(x, v["duel_win_rate"], v["n_scored_answers"]) for x, v in duel["by_competitor"].items()),
            sum(v.get("na", 0) for cls, v in duel["r2_winner_by_class"].items() if cls != "C4"), int((r2["class"] != "C4").sum())))
    L += [
        "Decision — worst_model / worst_zone in the leaderboard are by highest Impact (the prioritization metric), not lowest Win Rate.",
        "Audit: `audit/sample_benchmarking.csv` — {} R1 C1 answers with ≥1 competitor present (seed 42), one row per answer × competitor; review overlap / win / loss_type by eye.".format(len(samp)),
        "Outputs: benchmark_summary.json, benchmark_by_prompt.csv ({} prompt×competitor rows), benchmark_pairs.csv ({} rows).".format(len(bp), len(pairs)),
    ]
    tbl = ["", "---", "Leaderboard (sorted by Impact; Win Rate CI = Wilson 95% by overlap answers):", "",
           "| competitor | overlap answers | Win Rate % | CI95 | Impact % | by_position % | by_absence % | worst model | worst zone | low_n |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d in leaderboard:
        tbl.append("| {} | {} | {} | {} | {:.1f} | {:.1f} | {:.1f} | {} | {} | {} |".format(
            d["competitor"], d["overlap_answers"], "n/a" if d["win_rate"] is None else "{:.1f}".format(d["win_rate"]),
            "n/a" if d["win_rate_ci95"] is None else "{:.1f}–{:.1f}".format(*d["win_rate_ci95"]), d["impact"], d["impact_by_position"], d["impact_by_absence"],
            d["worst_model"], d["worst_zone"], "yes" if d["low_n"] else ""))
    tbl += ["", "By model family (R1 C1):", "", "| family | versions | win rate % | overlap answers | top impact competitor | its impact % |", "|---|---|---|---|---|---|"]
    for d in by_model:
        tbl.append("| {} | {} | {:.1f} | {} | {} | {:.1f} |".format(d["model"], ", ".join(d["versions"]), d["win_rate"], d["n_overlap_answers"], d["top_impact_competitor"], d["top_impact"]))
    tbl += ["", "By zone (R1 C1):", "", "| zone | prompts | win rate % | overlap answers | top impact competitor | its impact % |", "|---|---|---|---|---|---|"]
    for d in by_zone:
        tbl.append("| {} | {} | {:.1f} | {} | {} | {:.1f} |".format(d["zone"], d["n_prompts"], d["win_rate"], d["n_overlap_answers"], d["top_impact_competitor"], d["top_impact"]))
    (C.METRICS_DIR / "benchmark_report.md").write_text("\n".join(L + tbl) + "\n", encoding="utf-8")
    print("\n".join(L[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
