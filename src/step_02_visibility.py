"""Step 2 — Visibility Score (visibility_score_spec.md).

Reads  data/normalized/answers.parquet + config/*.yaml   (never the raw JSON)
Writes data/metrics/cycle_01/visibility_summary.json, visibility_by_prompt.csv, visibility_answers.csv, visibility_report.md
       audit/sample_visibility.csv (30 C1 answers, seed 42)

Run:   python -m src.step_02_visibility
Aggregation (spec §5 / runbook): repeats -> prompt×model -> model family (versions pooled) -> overall, equal family weights.
Deviations from the spec are listed in the report under "Decisions".
"""
import json
import math
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src import common as C

LOW_N = 30          # spec §7: fewer than 30 C1 answers after filters -> low_n
HEADLINE_RUN = "R1"  # cycle-1 decision (spec §2): headline on the category corpus only
SAMPLE_PER_CASE = 10


def _r(x, nd=1):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _pct(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else "{:.1f}%".format(100 * x)


def _weights(models_cfg: dict) -> Optional[Dict[str, float]]:
    w = models_cfg.get("weights", "equal")
    return None if w == "equal" else dict(w)


# --------------------------------------------------------------------------- #
def brands_in_answer(row, our_name: str) -> List[str]:
    pos = json.loads(row["comp_pos"])
    if row["we_present"] and row["we_pos"] is not None and not (isinstance(row["we_pos"], float) and math.isnan(row["we_pos"])):
        pos[our_name] = int(row["we_pos"])
    return [b for b, _ in sorted(pos.items(), key=lambda kv: (kv[1], kv[0]))]


def stability_table(used: pd.DataFrame) -> pd.DataFrame:
    """Per prompt×model(version) group: n_repeats, stability (share of repeats equal to the majority `present`), single_run."""
    def _stab(s: pd.Series) -> float:
        n = len(s)
        return max(int(s.sum()), n - int(s.sum())) / n if n else float("nan")
    g = used.groupby(["pid", "run", "model", "model_family"])["present"].agg(n_repeats="size", stability=_stab).reset_index()
    g["single_run"] = g["n_repeats"] < 2
    g["unstable"] = (~g["single_run"]) & (g["stability"] < 1.0)
    return g


def family_block(used: pd.DataFrame, stab: pd.DataFrame, family_col: str, weights, versions_by_family: Dict[str, List[str]]) -> List[dict]:
    vis = C.aggregate_bottom_up(used, "present", family_col=family_col, ci_basis="answers")
    pos = C.aggregate_bottom_up(used, "position", family_col=family_col, ci_basis="answers")
    sco = C.aggregate_bottom_up(used, "weight", family_col=family_col, ci_basis="answers")
    inn = C.aggregate_bottom_up(used, "inn_only_i", family_col=family_col, ci_basis="answers")
    bb = C.aggregate_bottom_up(used, "present_bb", family_col=family_col, ci_basis="answers")
    st = stab.groupby(family_col).agg(unstable=("unstable", "mean"), single=("single_run", "mean"), n_groups=("n_repeats", "size")).reset_index()
    out = []
    for r in vis["family"].itertuples():
        fam = getattr(r, family_col)
        p = pos["family"].loc[pos["family"][family_col] == fam, "position"]
        s = sco["family"].loc[sco["family"][family_col] == fam, "weight"]
        i = inn["family"].loc[inn["family"][family_col] == fam, "inn_only_i"]
        b = bb["family"].loc[bb["family"][family_col] == fam, "present_bb"]
        stt = st.loc[st[family_col] == fam].iloc[0]
        out.append({
            "model": fam,
            "versions": versions_by_family.get(fam, [fam]) if family_col == "model_family" else [fam],
            "n_answers": int(r.n_answers), "n_prompt_model_groups": int(r.n_groups),
            "ai_brand_score": float(s.iloc[0]) if len(s) else None,
            "visibility_pct": 100.0 * float(r.present),
            "visibility_ci95": [100.0 * float(r.ci_lo), 100.0 * float(r.ci_hi)],
            "average_position": float(p.iloc[0]) if len(p) and not math.isnan(float(p.iloc[0])) else None,
            "visibility_pct_brand_bearing_only": 100.0 * float(b.iloc[0]) if len(b) and not math.isnan(float(b.iloc[0])) else None,
            "inn_only_mention_pct": 100.0 * float(i.iloc[0]) if len(i) else None,
            "unstable_groups_pct": 100.0 * float(stt["unstable"]),
            "single_run_groups_pct": 100.0 * float(stt["single"]),
            "low_n": int(r.n_answers) < LOW_N,
        })
    return out


def overall_block(used: pd.DataFrame, weights) -> dict:
    vis = C.aggregate_bottom_up(used, "present", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
    pos = C.aggregate_bottom_up(used, "position", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
    sco = C.aggregate_bottom_up(used, "weight", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
    inn = C.aggregate_bottom_up(used, "inn_only_i", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
    bb = C.aggregate_bottom_up(used, "present_bb", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
    return {
        "ai_brand_score": float(sco["weight"]),
        "visibility_pct": 100.0 * float(vis["present"]),
        "visibility_ci95": [100.0 * float(vis["ci_lo"]), 100.0 * float(vis["ci_hi"])],
        "average_position": float(pos["position"]),
        "visibility_pct_brand_bearing_only": 100.0 * float(bb["present_bb"]),
        "inn_only_mention_pct": 100.0 * float(inn["inn_only_i"]),
        "n_answers": int(vis["n_answers"]), "n_families": int(vis["n_families"]),
    }


def intrusion_block(a: pd.DataFrame, bd: C.BrandDictionary, weights) -> dict:
    out = {}
    c2 = a[(a["class"] == "C2") & (~a["excluded"])].copy()
    c2["comp_present"] = (c2["comps_present"].map(len) > 0).astype(int)
    ci = C.aggregate_bottom_up(c2, "comp_present", ci_basis="answers", family_weights=weights)
    out["competitor_into_ours_pct"] = 100.0 * float(ci["overall"]["comp_present"].iloc[0])
    out["competitor_into_ours_ci95"] = [100.0 * float(ci["overall"]["ci_lo"].iloc[0]), 100.0 * float(ci["overall"]["ci_hi"].iloc[0])]
    out["competitor_into_ours_n_answers"] = int(ci["overall"]["n_answers"].iloc[0])
    out["by_competitor"] = {}
    for comp in bd.competitors:
        c2["_c"] = c2["comps_present"].map(lambda l: int(comp in list(l)))
        out["by_competitor"][comp] = 100.0 * float(C.aggregate_bottom_up(c2, "_c", ci_basis="answers", family_weights=weights)["overall"]["_c"].iloc[0])
    c3 = a[(a["class"] == "C3") & (~a["excluded"])].copy()
    c3["present"] = c3["we_present"].astype(int)
    oi = C.aggregate_bottom_up(c3, "present", ci_basis="answers", family_weights=weights)
    out["ours_into_competitor_pct"] = 100.0 * float(oi["overall"]["present"].iloc[0])
    out["ours_into_competitor_ci95"] = [100.0 * float(oi["overall"]["ci_lo"].iloc[0]), 100.0 * float(oi["overall"]["ci_hi"].iloc[0])]
    out["ours_into_competitor_n_answers"] = int(oi["overall"]["n_answers"].iloc[0])
    asked = c3.drop_duplicates(["pid", "run"])[["pid", "run", "text"]].copy()
    asked["comps"] = asked["text"].map(bd.competitors_present)
    out["by_competitor_asked"] = {}
    for comp in bd.competitors:
        keys = asked[asked["comps"].map(lambda l: comp in l)][["pid", "run"]]
        sub = c3.merge(keys, on=["pid", "run"])
        if len(sub):
            r = C.aggregate_bottom_up(sub, "present", ci_basis="answers", family_weights=weights)["overall"].iloc[0]
            out["by_competitor_asked"][comp] = {"pct": 100.0 * float(r["present"]), "n_prompts": int(len(keys)), "n_answers": int(r["n_answers"])}
    return out


# --------------------------------------------------------------------------- #
def main() -> int:
    cfg = C.load_configs()
    bd = C.BrandDictionary(cfg["brands"])
    th = cfg["thresholds"]
    decay = float(th["position_decay"])
    weights = _weights(cfg["models"])
    fam_map, surf_map, _ = C.model_maps(cfg["models"])
    versions_by_family = {f: sorted(v) for f, v in cfg["models"]["families"].items()}

    a = C.load_answers()
    a["comps_present"] = a["comps_present"].map(lambda x: list(x) if x is not None else [])
    c1 = a[a["class"] == "C1"].copy()

    # ---- per-answer table (§4) ------------------------------------------
    t = c1.copy()
    t["present"] = t["we_present"].astype(int)
    t["position_text"] = t["we_pos"].astype("float64")
    sc = t["our_rank_scored"].astype("float64")
    t["position_scored"] = sc.where(sc > 0)
    t["position"] = t["position_text"]
    both = t["position_text"].notna() & t["position_scored"].notna()
    t["position_flag"] = both & ((t["position_text"] - t["position_scored"]).abs() > 1)
    t["weight"] = t["position"].map(lambda p: C.position_weight(p, decay))
    t["brands_in_answer"] = t.apply(lambda r: brands_in_answer(r, bd.our_name), axis=1)
    t["brand_bearing"] = t["brands_in_answer"].map(len) > 0
    t["present_bb"] = t["present"].where(t["brand_bearing"]).astype("float64")
    t["inn_only_i"] = t["inn_only"].astype(int)
    t["surface_type"] = t["model"].map(surf_map)

    used = t[~t["excluded"]].copy()
    used["in_headline"] = used["run"] == HEADLINE_RUN
    t["in_headline"] = t["run"] == HEADLINE_RUN
    head = used[used["in_headline"]].copy()          # R1 C1: the category corpus (cycle-1 decision, spec §2)
    other = used[~used["in_headline"]].copy()        # C1 prompts from R2/R3/R5/R6: reference only
    stab = stability_table(used)
    stab_head = stab[stab["run"] == HEADLINE_RUN]

    # ---- headline: by family / by version on R1 C1 ------------------------
    by_model = sorted(family_block(head, stab_head, "model_family", weights, versions_by_family), key=lambda d: d["model"])
    by_version = sorted(family_block(head, stab_head, "model", weights, versions_by_family), key=lambda d: d["model"])
    low_n_families = [d["model"] for d in by_model if d["low_n"]]
    headline_families = [d["model"] for d in by_model if not d["low_n"]]
    used_head = head[head["model_family"].isin(headline_families)]
    headline = overall_block(used_head, weights)
    pooled_all = overall_block(used[used["model_family"].isin([d["model"] for d in family_block(used, stab, "model_family", weights, versions_by_family) if not d["low_n"]])], weights)

    # scored-rank variant of average position (reference)
    alt = used_head.copy()
    alt["position"] = alt["position_scored"].where(alt["position_scored"].notna(), alt["position_text"])
    alt["weight"] = alt["position"].map(lambda p: C.position_weight(p, decay))
    alt_pos = float(C.aggregate_bottom_up(alt, "position", ci_basis="answers", family_weights=weights)["overall"]["position"].iloc[0])
    alt_score = float(C.aggregate_bottom_up(alt, "weight", ci_basis="answers", family_weights=weights)["overall"]["weight"].iloc[0])

    # ---- c1_other_runs: reference block per run ---------------------------
    c1_other_runs = {}
    for run, g in other.groupby("run"):
        stab_r = stab[stab["run"] == run]
        fams = family_block(g, stab_r, "model_family", weights, versions_by_family)
        ov = overall_block(g, weights)
        c1_other_runs[run] = {
            "n_prompts": int(g.drop_duplicates(["pid", "run"]).shape[0]), "n_answers": int(len(g)),
            "surfaces": sorted(g["surface_type"].dropna().unique().tolist()),
            "overall_all_families_equal_weight": {k: (_r(v, 2) if not isinstance(v, list) else [_r(x, 2) for x in v]) for k, v in ov.items()},
            "by_model": [{k: (_r(v, 2) if isinstance(v, float) else ([_r(x, 2) for x in v] if isinstance(v, list) and v and isinstance(v[0], float) else v)) for k, v in d.items()} for d in sorted(fams, key=lambda d: d["model"])],
        }

    # ---- cross-check: visibility from our_status_scored vs we_present (R1, same subset) ----
    r1 = used_head.copy()
    r1["present_scored"] = r1["our_status_scored"].isin(["M", "R"]).astype(int)
    xc_text = 100.0 * float(C.aggregate_bottom_up(r1, "present", ci_basis="answers", family_weights=weights)["overall"]["present"].iloc[0])
    xc_scored = 100.0 * float(C.aggregate_bottom_up(r1, "present_scored", ci_basis="answers", family_weights=weights)["overall"]["present_scored"].iloc[0])
    xc_ok = abs(xc_text - xc_scored) <= 0.5

    # ---- by prompt (§8.2): all C1 prompts, `in_headline` marks R1 ---------
    pm_vis = C.aggregate_bottom_up(used, "present", ci_basis="answers")["pm"]
    pm_pos = C.aggregate_bottom_up(used, "position", ci_basis="answers")["pm"]
    pm_sco = C.aggregate_bottom_up(used, "weight", ci_basis="answers")["pm"]
    pm = pm_vis.merge(pm_pos[["pid", "run", "model", "position"]], on=["pid", "run", "model"], how="left") \
               .merge(pm_sco[["pid", "run", "model", "weight"]], on=["pid", "run", "model"]) \
               .merge(stab[["pid", "run", "model", "stability"]], on=["pid", "run", "model"])
    fam_pm = pm.groupby(["pid", "run", "model_family"]).agg(vis=("present", "mean"), pos=("position", "mean"), score=("weight", "mean"),
                                                            stability=("stability", "mean"), n=("n_repeats", "sum")).reset_index()
    rows = []
    meta = used.drop_duplicates(["pid", "run"]).set_index(["pid", "run"])[["text", "zone"]]
    for (pid, run), g in fam_pm.groupby(["pid", "run"]):
        g = g.sort_values(["vis", "score", "model_family"], ascending=[False, False, True])
        rows.append({"pid": pid, "run": run, "in_headline": run == HEADLINE_RUN, "text": meta.loc[(pid, run), "text"], "zone": meta.loc[(pid, run), "zone"],
                     "n_answers": int(g["n"].sum()), "vis": float(g["vis"].mean()),
                     "avg_pos": float(g["pos"].mean()) if g["pos"].notna().any() else None,
                     "score": float(g["score"].mean()), "stability": float(g["stability"].mean()),
                     "best_model": g.iloc[0]["model_family"], "worst_model": g.iloc[-1]["model_family"]})
    by_prompt = pd.DataFrame(rows).sort_values(["run", "pid"])

    # ---- quality ----------------------------------------------------------
    excl = {k: int(v) for k, v in c1["exclude_reason"].value_counts().items()}
    excl_head = {k: int(v) for k, v in c1.loc[c1["run"] == HEADLINE_RUN, "exclude_reason"].value_counts().items()}
    dic = {x.lower() for x in bd.our_aliases} | {al.lower() for v in bd.competitors.values() for al in v}
    unk = {}
    for m in c1["mentioned_data"].fillna(""):
        for tok in [x.strip() for x in m.split(",") if x.strip()]:
            if tok.lower() not in dic:
                unk[tok] = unk.get(tok, 0) + 1
    unknown_top = dict(sorted(unk.items(), key=lambda kv: (-kv[1], kv[0]))[:20])
    prompts = a.drop_duplicates(["pid", "run"])
    mism_all = int(prompts["status_mismatch"].sum())
    mism_c1 = int(prompts.loc[prompts["class"] == "C1", "status_mismatch"].sum())
    n_flag = int(head["position_flag"].sum()); n_both = int((head["position_text"].notna() & head["position_scored"].notna()).sum())
    legacy = head.dropna(subset=["visibility_data"])
    legacy_corr = float(legacy["visibility_data"].corr(legacy["weight"])) if len(legacy) > 2 else None
    c1_runs = sorted(c1["run"].unique().tolist())
    c1_prompts_by_run = {r: int(n) for r, n in c1.drop_duplicates(["pid", "run"]).groupby("run").size().items()}
    surfaces_covered = sorted(head["surface_type"].dropna().unique().tolist())
    models_without_c1 = sorted(set(fam_map) - set(head["model"].unique()) - set(cfg["models"].get("drop") or []))
    intrusion = intrusion_block(a, bd, weights)
    n_head_prompts = int(head.drop_duplicates(["pid", "run"]).shape[0])

    def _rd(d):
        return {k: (_r(v, 2) if isinstance(v, float) else ([_r(x, 2) for x in v] if isinstance(v, list) and v and isinstance(v[0], float) else v)) for k, v in d.items()}

    summary = {
        "brand": bd.our_name,
        "run_ids": c1_runs,
        "headline_run": HEADLINE_RUN,
        "config": {"position_decay": decay, "model_weights": "equal" if weights is None else weights, "min_answer_len": int(th["min_answer_chars"]),
                   "low_n_threshold": LOW_N, "position_source": "text (ordinal among dictionary brands); scores.our_rank kept as a check",
                   "headline_scope": "R1 C1 prompts only (cycle-1 decision, visibility_score_spec §2)"},
        "counts": {"prompts_total": int(len(prompts)),
                   "prompts_by_class": {k: int(v) for k, v in prompts["class"].value_counts().sort_index().items()},
                   "answers_total": int(len(a)), "answers_excluded": int(a["excluded"].sum()),
                   "answers_C1_total": int(len(c1)), "answers_C1_excluded": int(c1["excluded"].sum()), "answers_C1_used": int(len(used)),
                   "prompts_C1_headline": n_head_prompts, "answers_C1_headline_used": int(len(used_head)), "answers_C1_headline_excluded": excl_head,
                   "c1_prompts_by_run": c1_prompts_by_run},
        "headline": {k: (_r(v, 2) if not isinstance(v, list) else [_r(x, 2) for x in v]) for k, v in headline.items() if k not in ("n_answers", "n_families")},
        "headline_reference": {
            "average_position_using_scored_rank_where_present": _r(alt_pos, 2),
            "ai_brand_score_using_scored_rank_where_present": _r(alt_score, 2),
            "all_c1_runs_pooled_non_low_n_families": {k: (_r(v, 2) if not isinstance(v, list) else [_r(x, 2) for x in v]) for k, v in pooled_all.items()},
            "headline_families": headline_families, "low_n_families_excluded_from_headline": low_n_families,
        },
        "cross_check": {"r1_visibility_pct_from_we_present": _r(xc_text, 2), "r1_visibility_pct_from_our_status_scored": _r(xc_scored, 2),
                        "abs_diff": _r(abs(xc_text - xc_scored), 2), "within_0_5": bool(xc_ok), "n_answers": int(len(r1))},
        "scope": {"c1_runs": c1_runs, "headline_runs": [HEADLINE_RUN], "surfaces_covered": surfaces_covered,
                  "surfaces_not_covered": models_without_c1,
                  "note": "Headline on R1 category prompts only; C1 prompts in R2/R3/R5/R6 are in c1_other_runs for reference. Web surfaces have no R1 answers."},
        "by_model": [_rd(d) for d in by_model],
        "by_model_version": [_rd(d) for d in by_version],
        "c1_other_runs": c1_other_runs,
        "intrusion": {k: (_r(v, 2) if isinstance(v, float) else ([_r(x, 2) for x in v] if isinstance(v, list) else
                          ({kk: (_r(vv, 2) if isinstance(vv, float) else {a_: (_r(b_, 2) if isinstance(b_, float) else b_) for a_, b_ in vv.items()}) for kk, vv in v.items()} if isinstance(v, dict) else v)))
                      for k, v in intrusion.items()},
        "quality": {"excluded_by_reason_C1": excl, "status_vs_text_mismatches": mism_all, "status_vs_text_mismatches_C1": mism_c1,
                    "unknown_brands_top20": unknown_top,
                    "single_run_groups_pct_headline": _r(100.0 * float(stab_head["single_run"].mean()), 2),
                    "unstable_groups_pct_headline": _r(100.0 * float(stab_head.loc[~stab_head["single_run"], "unstable"].mean()), 2),
                    "position_text_vs_scored_differ_gt1": {"n": n_flag, "of": n_both},
                    "legacy_visibility_field_corr_with_weight": _r(legacy_corr, 3)},
    }

    # ---- write outputs ----------------------------------------------------
    C.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    C.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(C.METRICS_DIR / "visibility_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    by_prompt.to_csv(C.METRICS_DIR / "visibility_by_prompt.csv", index=False)
    ans_cols = ["pid", "run", "in_headline", "model", "model_family", "surface_type", "repeat_idx", "class", "present", "position", "position_text",
                "position_scored", "position_flag", "weight", "brands_in_answer", "inn_only", "brand_bearing", "excluded", "exclude_reason", "visibility_data"]
    t_out = t[ans_cols].copy()
    t_out["brands_in_answer"] = t_out["brands_in_answer"].map(lambda l: json.dumps(l, ensure_ascii=False))
    t_out.sort_values(["run", "pid", "model", "repeat_idx"]).to_csv(C.METRICS_DIR / "visibility_answers.csv", index=False)

    # audit sample from the headline pool (R1 C1, non-excluded): 10 present / 10 absent (not INN-only) / 10 INN-only, seed 42
    pool = head.sort_values(["run", "pid", "model", "repeat_idx"]).reset_index(drop=True)
    strata = [("present", pool[pool["we_present"]]), ("absent", pool[(~pool["we_present"]) & (~pool["inn_only"])]), ("inn_only", pool[pool["inn_only"]])]
    parts = []
    for name, sub in strata:
        s_ = sub.sample(n=min(SAMPLE_PER_CASE, len(sub)), random_state=C.SEED).copy()
        s_["case"] = name
        parts.append(s_)
    sample = pd.concat(parts)
    sample_out = pd.DataFrame({
        "pid": sample["pid"], "model": sample["model"], "answer_clean": sample["answer_clean"],
        "we_present": sample["we_present"], "we_pos": sample["we_pos"], "inn_only": sample["inn_only"],
        "brands_in_answer": sample["brands_in_answer"].map(lambda l: json.dumps(l, ensure_ascii=False)),
        "reviewer_agrees": "", "case": sample["case"], "run": sample["run"], "repeat_idx": sample["repeat_idx"],
    })
    sample_out.to_csv(C.AUDIT_DIR / "sample_visibility.csv", index=False)

    # ---- report (≤ 15 lines) + appendix tables ---------------------------
    h = summary["headline"]
    fam_line = "; ".join("{} {:.1f}% [{:.1f}–{:.1f}] pos {} score {:.1f} n={}{}".format(
        d["model"], d["visibility_pct"], d["visibility_ci95"][0], d["visibility_ci95"][1],
        "n/a" if d["average_position"] is None else "{:.2f}".format(d["average_position"]), d["ai_brand_score"], d["n_answers"], " low_n" if d["low_n"] else "")
        for d in summary["by_model"])
    other_line = "; ".join("{} {} prompts/{} answers on {}: vis {:.1f}% pos {} score {:.1f}".format(
        run, v["n_prompts"], v["n_answers"], "+".join(v["surfaces"]), v["overall_all_families_equal_weight"]["visibility_pct"],
        "n/a" if v["overall_all_families_equal_weight"]["average_position"] is None else "{:.2f}".format(v["overall_all_families_equal_weight"]["average_position"]),
        v["overall_all_families_equal_weight"]["ai_brand_score"]) for run, v in sorted(c1_other_runs.items()))
    L = [
        "# Visibility Score — cycle 1 (step 2)",
        "Headline (R1 C1 category prompts, families {}; equal weights): **Visibility {:.1f}%** [Wilson 95% {:.1f}–{:.1f}], **Average Position {:.2f}**, **AI Brand Score {:.1f}**; brand-bearing-only visibility {:.1f}%; INN-only mention {:.1f}% (never added to visibility).".format(
            ", ".join(headline_families), h["visibility_pct"], h["visibility_ci95"][0], h["visibility_ci95"][1], h["average_position"], h["ai_brand_score"], h["visibility_pct_brand_bearing_only"], h["inn_only_mention_pct"]),
        "Scope: {} R1 C1 prompts, {} answers used after filters ({} excluded: {}); surfaces covered: {}; no R1 answers on: {}{}.".format(
            n_head_prompts, len(used_head), sum(excl_head.values()), excl_head or "none", ", ".join(surfaces_covered), ", ".join(models_without_c1) or "none",
            "; low_n families excluded from headline: " + ", ".join(low_n_families) if low_n_families else ""),
        "By family: " + fam_line + ".",
        "Cross-check (R1, same {} answers): visibility from `we_present` {:.2f}% vs from `our_status_scored` (M/R) {:.2f}% → diff {:.2f} pts, {}.".format(
            len(r1), xc_text, xc_scored, abs(xc_text - xc_scored), "within 0.5 — PASS" if xc_ok else "outside 0.5 — WARN"),
        "Reliability (R1): single-run groups {:.1f}%, unstable groups (repeats disagree on presence) {:.1f}% of multi-repeat groups; CI by number of answers (§7).".format(
            summary["quality"]["single_run_groups_pct_headline"], summary["quality"]["unstable_groups_pct_headline"]),
        "Decision 1 (cycle 1, spec §2) — headline scope is R1 C1 only: R6 prompts are message-triggered, R5 are web probes, R2/R3 are forum posts; none is a neutral category question. Reference `c1_other_runs`: {}. All C1 runs pooled would give Visibility {:.1f}%, Position {:.2f}, Score {:.1f}.".format(
            other_line, pooled_all["visibility_pct"], pooled_all["average_position"], pooled_all["ai_brand_score"]),
        "Decision 2 — position source: the spec says use `scores.our_rank` when present, but the scorer ranks among *all* brands it saw (metformin, Tradjenta, Actos…), not dictionary brands; {} of {} R1 answers with both differ by >1. Text-based ordinal among dictionary brands is primary; with scored rank where present: Average Position {:.2f}, AI Brand Score {:.1f}.".format(
            n_flag, n_both, alt_pos, alt_score),
        "Decision 3 — dictionary extended with Farxiga, Januvia, Invokana (+ INNs and domains) after the first pass; metformin stays out as a generic.",
        "Anomaly 1 — `mentioned` tokens still outside the dictionary (all C1): top {}.".format(
            ", ".join("{} ({})".format(k, v) for k, v in list(unknown_top.items())[:6])),
        "Anomaly 2 — R1 scorer marks {} present answers with `our_rank = 0` (status M but no rank); legacy `visibility` field correlates {} with our weight (reference only, not used).".format(
            int(((head["present"] == 1) & (head["our_rank_scored"] == 0)).sum()), "n/a" if legacy_corr is None else "{:.2f}".format(legacy_corr)),
        "Intrusion (all runs): competitor into our answers (C2) {:.1f}% [{:.1f}–{:.1f}], n={}; ours into competitor answers (C3) {:.1f}% [{:.1f}–{:.1f}], n={}; top competitor in C2: {}.".format(
            intrusion["competitor_into_ours_pct"], *intrusion["competitor_into_ours_ci95"], intrusion["competitor_into_ours_n_answers"],
            intrusion["ours_into_competitor_pct"], *intrusion["ours_into_competitor_ci95"], intrusion["ours_into_competitor_n_answers"],
            max(intrusion["by_competitor"].items(), key=lambda kv: kv[1])[0]),
        "Status vs text class mismatches: {} prompts overall, {} among C1 (class is never taken from `status`).".format(mism_all, mism_c1),
        "Audit: `audit/sample_visibility.csv` — 30 R1 C1 answers (10 present / 10 absent / 10 INN-only, seed 42); stop for manual review, proceed if ≥ 90% agree.",
        "Outputs: visibility_summary.json, visibility_by_prompt.csv ({} C1 prompts, `in_headline` marks R1), visibility_answers.csv ({} rows incl. excluded).".format(len(by_prompt), len(t_out)),
    ]
    tbl = ["", "---", "Appendix — by model family, R1 C1 (headline uses non-low_n families; versions pooled):", "",
           "| family | versions | n_answers | groups | visibility % | CI95 | avg position | brand score | brand-bearing vis % | INN-only % | unstable groups % | single-run % | low_n |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in summary["by_model"]:
        tbl.append("| {} | {} | {} | {} | {:.1f} | {:.1f}–{:.1f} | {} | {:.1f} | {} | {:.1f} | {:.1f} | {:.1f} | {} |".format(
            d["model"], ", ".join(v for v in d["versions"] if v in set(head["model"].unique())), d["n_answers"], d["n_prompt_model_groups"], d["visibility_pct"], d["visibility_ci95"][0], d["visibility_ci95"][1],
            "n/a" if d["average_position"] is None else "{:.2f}".format(d["average_position"]), d["ai_brand_score"],
            "n/a" if d["visibility_pct_brand_bearing_only"] is None else "{:.1f}".format(d["visibility_pct_brand_bearing_only"]),
            d["inn_only_mention_pct"], d["unstable_groups_pct"], d["single_run_groups_pct"], "yes" if d["low_n"] else ""))
    tbl += ["", "By model version, R1 C1 (reference only):", "", "| version | family | n_answers | visibility % | CI95 | avg position | brand score | INN-only % | low_n |", "|---|---|---|---|---|---|---|---|---|"]
    for d in summary["by_model_version"]:
        tbl.append("| {} | {} | {} | {:.1f} | {:.1f}–{:.1f} | {} | {:.1f} | {:.1f} | {} |".format(
            d["model"], fam_map.get(d["model"], ""), d["n_answers"], d["visibility_pct"], d["visibility_ci95"][0], d["visibility_ci95"][1],
            "n/a" if d["average_position"] is None else "{:.2f}".format(d["average_position"]), d["ai_brand_score"], d["inn_only_mention_pct"], "yes" if d["low_n"] else ""))
    tbl += ["", "C1 prompts in other runs (reference only, not in headline; all families equal weight, low_n flagged in JSON):", "",
            "| run | prompts | answers | surfaces | visibility % | CI95 | avg position | brand score | INN-only % |", "|---|---|---|---|---|---|---|---|---|"]
    for run, v in sorted(c1_other_runs.items()):
        o = v["overall_all_families_equal_weight"]
        tbl.append("| {} | {} | {} | {} | {:.1f} | {:.1f}–{:.1f} | {} | {:.1f} | {:.1f} |".format(
            run, v["n_prompts"], v["n_answers"], "+".join(v["surfaces"]), o["visibility_pct"], o["visibility_ci95"][0], o["visibility_ci95"][1],
            "n/a" if o["average_position"] is None else "{:.2f}".format(o["average_position"]), o["ai_brand_score"], o["inn_only_mention_pct"]))
    (C.METRICS_DIR / "visibility_report.md").write_text("\n".join(L + tbl) + "\n", encoding="utf-8")
    print("\n".join(L[:3]))
    print("cross-check within 0.5:", xc_ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
