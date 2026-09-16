"""Step 8 — Dashboard Assembly (dashboard_assembly_spec.md).

Reads  the cycle-1 *_summary.json files, registries, config/, answers.parquet, prioritization_groups.csv
Writes data/metrics/cycle_01/dashboard.json + audit pack ONLY if every check passes; otherwise dashboard_assembly_errors.md.
       dashboard_checks.md is always written (pass/fail per check).

Cycle-1 adaptations (agreed): before_after.available = false, reason "first cycle"; sentiment = v1 scope — R3 headline plus a
separate narrative_resistance (R9) block, C1/C3/C4 brand-level sentiment deferred to v2.
Rounding: floats are rounded to 1 decimal here (never earlier); `score` fields keep 6 decimals because they are tiny products.
"""
import hashlib
import json
import subprocess
import sys
from datetime import date

import pandas as pd

from src import common as C

CYCLE = 1
PERIOD = "2026-09"
NEXT = "2026-12"
MARKET = "US/en"
KEEP_PRECISION = {"score", "best_score", "gap_score", "demand_share", "lo_share", "hi_share"}


def rnd(o, key=None):
    if isinstance(o, float):
        return round(o, 6) if key in KEEP_PRECISION else round(o, 1)
    if isinstance(o, dict):
        return {k: rnd(v, k) for k, v in o.items()}
    if isinstance(o, list):
        return [rnd(v, key) for v in o]
    return o


def load(name):
    return json.load(open(C.METRICS_DIR / name, encoding="utf-8"))


def main() -> int:
    cfg = C.load_configs()
    vis, ben, sen, cit, pri, ac, lab = (load(n) for n in ["visibility_summary.json", "benchmark_summary.json", "sentiment_summary.json", "citations_summary.json",
                                                            "prioritization_summary.json", "action_center_summary.json", "label_flag_summary.json"])
    ac_reg = json.load(open(C.REGISTRY_DIR / "action_center_tasks.json", encoding="utf-8"))
    lab_reg = json.load(open(C.REGISTRY_DIR / "label_findings_registry.json", encoding="utf-8"))
    a = C.load_answers()
    groups_csv = pd.read_csv(C.METRICS_DIR / "prioritization_groups.csv")
    try:
        version = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(C.ROOT)).decode().strip()
    except Exception:
        version = "unknown"
    config_hash = hashlib.sha1(b"".join(open(C.CONFIG_DIR / "{}.yaml".format(n), "rb").read() for n in C.CONFIG_NAMES)).hexdigest()[:12]
    fam_map, _, drop = C.model_maps(cfg["models"])

    # ---- assemble ---------------------------------------------------------------
    r3, r9 = sen["by_run"]["R3"], sen["by_run"]["R9"]
    themes_r9 = [t for t in sen["all_themes"] if t["run"] == "R9"]
    dash = {
        "meta": {"brand": vis["brand"], "cycle": CYCLE, "period": PERIOD, "market": MARKET, "competitors": list(cfg["brands"]["competitors"]),
                 "prompts": int(a.drop_duplicates(["pid", "run"]).shape[0]), "answers": int(len(a)), "answers_excluded_by_filter": int(a["excluded"].sum()),
                 "surfaces": int(a["model"].nunique()), "surface_list": sorted(a["model"].unique().tolist()), "dropped_models": sorted(drop),
                 "generated_at": str(date.today()), "pipeline_version": version, "config_hash": config_hash},
        "visibility": {"scope_note": vis["config"]["headline_scope"], "headline": vis["headline"], "headline_reference": vis["headline_reference"], "cross_check": vis["cross_check"],
                       "by_model": vis["by_model"], "scope": vis["scope"], "intrusion": vis["intrusion"], "c1_other_runs": {k: v["overall_all_families_equal_weight"] for k, v in vis["c1_other_runs"].items()}},
        "benchmarking": {"scope_note": ben["headline_scope"], "overall": ben["overall"], "leaderboard": [{k: v for k, v in d.items() if k != "by_model"} for d in ben["leaderboard"]],
                         "by_model": ben["by_model"], "duel_verdict": {k: v for k, v in ben["duel_verdict"].items() if k not in ("r2_winner_by_class",)}},
        "sentiment": {"scope_note": "v1: class C2 only (questions about the brand). Headline = R3 (living on the drug); narrative_resistance = R9 myth probes, reported separately. "
                                    "C1/C3/C4 brand-level LLM re-scoring and the competitor comparison are deferred to v2.",
                      "headline": {"run": "R3", "score": r3["score"], "shares": {"positive_pct": r3["positive_pct"], "neutral_pct": r3["neutral_pct"], "negative_pct": r3["negative_pct"]},
                                   "n": r3["n"], "n_prompts": r3["n_prompts"], "by_model": r3["by_model"]},
                      "narrative_resistance": {"run": "R9", "score": r9["score"], "shares": {"positive_pct": r9["positive_pct"], "neutral_pct": r9["neutral_pct"], "negative_pct": r9["negative_pct"]},
                                               "n": r9["n"], "n_prompts": r9["n_prompts"], "by_model": r9["by_model"], "themes": themes_r9},
                      "combined_c2": {"score": sen["score"], "shares": sen["shares"], "by_model": sen["by_model"]},
                      "competitors": [], "competitors_note": sen["competitors_note"], "top_negative_themes": sen["top_negative_themes"]},
        "citations": {"scope_note": cit["scope"], "owner_shares": cit["owner_shares"], "owner_shares_by_model": cit["owner_shares_by_model"], "earned_subtypes": cit["earned_subtypes"],
                      "owned_share_in_answers_with_us": cit["owned_share_in_answers_with_us"], "top_domains": cit["top_domains"][:10], "gap_list": cit["gap_list"][:10],
                      "adversarial_sources": cit["adversarial_sources"], "answers_without_citations_pct": cit["answers_without_citations_pct"]},
        "prioritization": {"recommendations": pri["top10_by_group"][:10], "label_recommendations": pri["label_recommendations"][:5], "tercile_thresholds": pri["tercile_thresholds"],
                           "tercile_thresholds_label": pri["tercile_thresholds_label"], "gap_note": pri["gap_note"], "healthy_groups_count": len(pri["healthy_groups"]),
                           "below_gap_floor_count": len(pri["below_gap_floor"]), "citere_rows_count": len(pri["citere_rows"]), "rows_total": pri["client_rows_total"]},
        "action_center": {"counters": ac["counters"], "top3_open": ac["top3_open"]},
        "safety_label": {"traffic_light": lab["traffic_light"], "critical_answer_share": lab["critical_answer_share"], "critical_ci95": lab["critical_ci95"],
                         "findings": lab["findings"], "by_surface": lab["by_surface"], "top_label_sections": lab["top_label_sections"], "error_types": lab["error_types"],
                         "scoring_caveat": lab["scoring_caveat"], "flagged_for_review": lab["flagged_for_review"],
                         "findings_list": [f for f in lab_reg["findings"] if f.get("signoff_status") == "confirmed"],
                         "findings_list_note": "filtered to signoff_status = confirmed; {} pending findings are counted in findings.pending_signoff only".format(lab["findings"]["pending_signoff"])},
        "before_after": {"available": False, "reason": "first cycle", "next_cycle_expected": NEXT},
    }
    dash = rnd(dash)

    # ---- checks (spec §2) --------------------------------------------------------
    checks = []
    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    triples = {"sentiment.headline": dash["sentiment"]["headline"]["shares"], "sentiment.narrative_resistance": dash["sentiment"]["narrative_resistance"]["shares"],
               "sentiment.combined_c2": dash["sentiment"]["combined_c2"]["shares"]}
    for d in dash["sentiment"]["headline"]["by_model"].items():
        triples["sentiment.headline.by_model." + d[0]] = {k: d[1][k] for k in ("positive_pct", "neutral_pct", "negative_pct")}
    TOL = 0.1 + 1e-9  # spec: 100 ± 0.1 (independent 1-decimal rounding of three shares can legitimately land on 100.1)
    sums = {k: round(sum(v[x] for x in ("positive_pct", "neutral_pct", "negative_pct")), 2) for k, v in triples.items()}
    bad = {k: v for k, v in sums.items() if abs(v - 100) > TOL}
    pie = dash["citations"]["owner_shares"]; pie_sum = round(sum(pie.values()), 2)
    if abs(pie_sum - 100) > TOL:
        bad["citations.owner_shares(4 owners)"] = pie_sum
    check("1. every shares triple sums to 100 ± 0.1", not bad, "checked {} sentiment triples + citations pie; sums = {}; pie = {}; off: {}".format(len(triples), sums, pie_sum, bad or "none"))

    cfg_fams = set(cfg["models"]["families"])
    dropped_fams = {f for f, vs in cfg["models"]["families"].items() if all(v in drop for v in vs)}
    expected = cfg_fams - dropped_fams
    got = {d["model"] for d in dash["visibility"]["by_model"]}
    fams_in_scope = set(a.loc[(a["run"] == vis["headline_run"]) & (a["class"] == "C1"), "model_family"].unique())
    # scope-aware (cycle-1 decision, spec §2 updated): validate against config families that have ≥1 answer in the headline scope
    excluded_fams = sorted(expected - fams_in_scope)
    check("2. visibility.by_model families = config families with answers in the headline scope (scope-aware)", got == (expected & fams_in_scope),
          "config minus dropped = {}; families with answers in {} C1 = {}; by_model = {}; excluded from validation (no {} C1 answers, web-only surfaces): {}".format(
              sorted(expected), vis["headline_run"], sorted(fams_in_scope), sorted(got), vis["headline_run"], excluded_fams or "none"))

    comps = {d["competitor"] for d in dash["benchmarking"]["leaderboard"]}
    check("3. benchmarking.leaderboard competitors ⊆ brands.yaml competitors", comps <= set(cfg["brands"]["competitors"]), "leaderboard {}; extra = {}".format(sorted(comps), sorted(comps - set(cfg["brands"]["competitors"])) or "none"))

    gids = set(groups_csv["group_id"])
    missing_g = [r["group_id"] for r in dash["prioritization"]["recommendations"] if r["group_id"] not in gids] + [r["group_id"] for r in dash["prioritization"]["label_recommendations"] if r["group_id"] not in gids]
    check("4. every prioritization recommendation group exists in prioritization_groups.csv", not missing_g, "missing = {}".format(missing_g or "none"))

    reg_ids = {t["task_id"] for t in ac_reg["tasks"] + ac_reg.get("citere_tasks", []) + ac_reg.get("label_tasks_awaiting_signoff", [])}
    missing_t = [t["task_id"] for t in dash["action_center"]["top3_open"] if t["task_id"] not in reg_ids]
    check("5. every action_center.top3_open task_id exists in the registry", not missing_t, "top3 = {}; missing = {}".format([t["task_id"] for t in dash["action_center"]["top3_open"]], missing_t or "none"))

    nonconf = [f["finding_id"] for f in dash["safety_label"]["findings_list"] if f.get("signoff_status") != "confirmed"]
    check("6. no safety_label.findings_list entry has signoff_status != confirmed", not nonconf, "findings_list has {} entries (all pending findings filtered out); non-confirmed = {}".format(len(dash["safety_label"]["findings_list"]), nonconf or "none"))

    # answers.parquet already excludes dropped models (normalization); rows − dropped rows in parquet (0) must equal meta.answers
    dropped_rows_in_parquet = int(a["model"].isin(drop).sum())
    check("7. meta.answers = rows in answers.parquet (incl. excluded) − dropped models", dash["meta"]["answers"] == len(a) - dropped_rows_in_parquet,
          "rows = {}, dropped-model rows present in parquet = {} (removed in step 1: {}), meta.answers = {}".format(len(a), dropped_rows_in_parquet, sorted(drop), dash["meta"]["answers"]))

    def max_decimals(o, key=None):
        if isinstance(o, float) and key not in KEEP_PRECISION:
            s = repr(o); return len(s.split(".")[1]) if "." in s else 0
        if isinstance(o, dict):
            return max([max_decimals(v, k) for k, v in o.items()] or [0])
        if isinstance(o, list):
            return max([max_decimals(v, key) for v in o] or [0])
        return 0
    md = max_decimals(dash)
    check("8. numbers rounded to 1 decimal only here", md <= 1, "max decimals in dashboard (excluding score-type keys kept at 6) = {}; upstream summaries keep 2+ decimals".format(md))

    lines = ["# Dashboard assembly checks — cycle {}".format(CYCLE), ""] + ["- {} **{}** — {}".format("PASS" if c["pass"] else "FAIL", c["check"], c["detail"]) for c in checks]
    (C.METRICS_DIR / "dashboard_checks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    failed = [c for c in checks if not c["pass"]]
    print("\n".join(lines))
    if failed:
        (C.METRICS_DIR / "dashboard_assembly_errors.md").write_text("\n".join(["# Dashboard assembly — errors (dashboard.json NOT written)", ""] + ["- {} — {}".format(c["check"], c["detail"]) for c in failed]) + "\n", encoding="utf-8")
        print("\nFAILED: {} check(s) — dashboard.json not written".format(len(failed)))
        return 2
    if (C.METRICS_DIR / "dashboard_assembly_errors.md").exists():
        (C.METRICS_DIR / "dashboard_assembly_errors.md").unlink()
    json.dump(dash, open(C.METRICS_DIR / "dashboard.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # ---- audit pack (spec §3) --------------------------------------------------------
    # Reviewed samples from steps 2/3/5 already exist under the spec's file names and carry review columns; they are kept as-is
    # (≥ 30 rows each). Only the two missing blocks are generated here: sentiment (brand_sentiment) and safety (verdict + is_finding).
    C.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    c2 = a[(a["class"] == "C2") & a["run"].isin(["R3", "R9"]) & (~a["excluded"]) & a["answer_sentiment"].notna()].sort_values(["run", "pid", "model", "repeat_idx"]).reset_index(drop=True)
    s = c2.sample(n=30, random_state=C.SEED)
    ss = pd.DataFrame({"pid": s["pid"], "run": s["run"], "model": s["model"], "repeat_idx": s["repeat_idx"], "text": s["text"], "answer_clean": s["answer_clean"], "brand_sentiment": s["answer_sentiment"],
                       "band": s["answer_sentiment"].map(lambda v: "negative" if v <= cfg["thresholds"]["sentiment_thresholds"][0] else ("positive" if v >= cfg["thresholds"]["sentiment_thresholds"][1] else "neutral"))})
    ss = C.carry_forward_review(ss, C.AUDIT_DIR / "sample_sentiment.csv", keys=["pid", "run", "model", "repeat_idx"], computed_cols=["brand_sentiment"])
    ss.to_csv(C.AUDIT_DIR / "sample_sentiment.csv", index=False)
    cells = pd.read_csv(C.METRICS_DIR / "label_cells.csv")
    r4 = a[(a["run"] == "R4") & (~a["excluded"])].sort_values(["pid", "model", "repeat_idx"]).reset_index(drop=True)
    sc = r4["scores_json"].map(json.loads)
    r4 = r4.assign(verdict=sc.map(lambda x: x.get("verdict")), target=sc.map(lambda x: x.get("target")), harm_class=sc.map(lambda x: x.get("harm_class")), evidence=sc.map(lambda x: x.get("evidence")))
    r4 = r4.merge(cells[["target", "surface", "is_finding", "class"]].rename(columns={"surface": "model", "class": "finding_class"}), on=["target", "model"], how="left")
    s4 = r4.sample(n=30, random_state=C.SEED)
    s4o = s4[["pid", "model", "repeat_idx", "text", "answer_clean", "verdict", "harm_class", "target", "evidence", "is_finding", "finding_class"]].copy()
    s4o = C.carry_forward_review(s4o, C.AUDIT_DIR / "sample_safety.csv", keys=["pid", "model", "repeat_idx"], computed_cols=["verdict", "is_finding"])
    s4o.to_csv(C.AUDIT_DIR / "sample_safety.csv", index=False)
    manifest = []
    for block, fname, agree_col in [("visibility", "sample_visibility.csv", "reviewer_agrees"), ("benchmarking", "sample_benchmarking.csv", "reviewer_agrees"), ("sentiment", "sample_sentiment.csv", "reviewer_agrees"),
                                    ("citations", "sample_citations.csv", "reviewer_agrees"), ("safety", "sample_safety.csv", "reviewer_agrees"), ("safety (verdict review, step 5)", "sample_label.csv", "reviewer_agrees")]:
        path = C.AUDIT_DIR / fname
        if not path.exists():
            manifest.append({"block": block, "file": fname, "rows": 0, "reviewed": 0, "agree": 0, "agreement_pct": None, "ships": False}); continue
        df = pd.read_csv(path)
        key = "answer_id" if "answer_id" in df.columns else None
        units = df.drop_duplicates(key) if key else df
        rev = units[units[agree_col].isin(["yes", "no"])] if agree_col in units.columns else units.iloc[0:0]
        agree = int((rev[agree_col] == "yes").sum()) if len(rev) else 0
        pct = round(100.0 * agree / len(rev), 1) if len(rev) else None
        manifest.append({"block": block, "file": fname, "rows": int(len(units)), "reviewed": int(len(rev)), "agree": agree, "agreement_pct": pct, "ships": bool(pct is not None and pct >= 90)})
    json.dump({"release_rule": "a block ships only when reviewer agreement >= 90% on its sample", "blocks": manifest}, open(C.AUDIT_DIR / "audit_pack_manifest.json", "w", encoding="utf-8"), indent=2)
    print("\ndashboard.json written; audit pack manifest:")
    for m in manifest:
        print("  {:38s} rows {:3d} reviewed {:3d} agree {:3d} → {} ships={}".format(m["block"], m["rows"], m["reviewed"], m["agree"], m["agreement_pct"], m["ships"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
