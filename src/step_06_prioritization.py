"""Step 6 — Diagnosis & Prioritization (diagnosis_prioritization_spec.md).

Reads  data/normalized/answers.parquet + citations.parquet, raw corpus (diagnosis.fixes only), config/*.yaml
Writes data/metrics/cycle_01/prioritization_summary.json, prioritization_groups.csv, prioritization_rows.csv, prioritization_report.md

Group = topic × subtopic (subtopic set and ≠ Other) else topic × zone; groups < min_group_prompts merge into `topic × small`
and take the parent topic's demand. Gap pools different failure kinds across runs (gap_by_run is always shown).
Lever = citations of an owner (stored owner_data) ÷ all citations in the group's answers after removing noise/other;
institutional categories are excluded from Lever and reported as institutional_share.
"""
import json
import math
import statistics
import sys
from typing import Dict, List

import pandas as pd

from src import common as C

LEVER_OWNERS = ["earned", "commerce", "ugc", "owned", "comp_owned"]
INST_CATS = {"regulatory", "gov_health", "wiki", "clinical"}
LABEL_CODES = {"DANGEROUS LABEL ERROR", "INCOMPLETE / OMISSION", "MODEL ON AN OLD LABEL", "AI AMPLIFIES A HARMFUL MYTH", "MYTH DEFENDED", "FAMILY CONFUSION"}


def _r(x, nd=4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def terciles(rows: List[dict]) -> Dict[str, float]:
    """Assign priority 3/2/1 by score terciles (rank-based thirds); returns thresholds."""
    rows.sort(key=lambda r: (-r["score"], -r["why"]["gap_bad"], -r["why"]["demand"]))
    n = len(rows)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        r["priority"] = 3 if i < n / 3 else (2 if i < 2 * n / 3 else 1)
    p3 = [r["score"] for r in rows if r["priority"] == 3]; p2 = [r["score"] for r in rows if r["priority"] == 2]
    return {"p3_min": _r(min(p3)) if p3 else None, "p2_min": _r(min(p2)) if p2 else None}


def main() -> int:
    cfg = C.load_configs()
    bd = C.BrandDictionary(cfg["brands"])
    min_n = int(cfg["thresholds"]["min_group_prompts"])
    raw = C.load_raw_corpus()
    fixes_by_code = {}
    for p in raw["prompts"]:
        fx = p["diagnosis"].get("fixes") or []
        if fx and p["code"] not in fixes_by_code:
            fixes_by_code[p["code"]] = fx[0]
    a = C.load_answers()
    a["comps_present"] = a["comps_present"].map(lambda x: list(x) if x is not None else [])
    c = C.load_citations()
    c = c[(~c["is_artifact"]) & (~c["dedup"]) & (~c["excluded"])].merge(a[["pid", "run", "model", "repeat_idx", "zone"]], on=["pid", "run", "model", "repeat_idx"])

    # ---- inventory ----------------------------------------------------------
    pr = a.drop_duplicates(["pid", "run"]).copy()
    ans_key = ["pid", "run", "model", "repeat_idx"]
    with_c = c.drop_duplicates(ans_key)[ans_key].assign(has=True)
    aa = a.merge(with_c, on=ans_key, how="left"); aa["has"] = aa["has"].eq(True)
    inventory = {"prompts_per_run": {k: int(v) for k, v in pr.groupby("run").size().items()},
                 "sev": {k: int(v) for k, v in pr["sev"].value_counts().items()},
                 "answers_with_citations_per_run": {k: {"with": int(g["has"].sum()), "without": int((~g["has"]).sum())} for k, g in aa.groupby("run")},
                 "prompts_empty_subtopic": int(pr["subtopic"].isna().sum()), "prompts_subtopic_other": int((pr["subtopic"] == "Other").sum()),
                 "citation_owner_values": sorted(c["owner_data"].dropna().unique().tolist()), "citation_category_values": sorted(c["category_data"].dropna().unique().tolist())}

    # ---- groups ---------------------------------------------------------------
    pr["group_raw"] = [C.topic_group(t, s, z)[0] for t, s, z in zip(pr["topic"], pr["subtopic"], pr["zone"])]
    sizes = pr.groupby("group_raw").size()
    topic_demand = pr.groupby("topic")["demand"].median()
    pr["group_id"] = [g if sizes[g] >= min_n else "{} × small".format(t) for g, t in zip(pr["group_raw"], pr["topic"])]
    merged_from = {t: sorted(set(pr.loc[(pr["group_id"] == "{} × small".format(t)), "group_raw"])) for t in pr["topic"].unique()}
    multi_demand = []
    groups = []
    for gid, g in pr.groupby("group_id"):
        is_small = gid.endswith(" × small")
        topic = g["topic"].iloc[0]
        if is_small:
            demand, lo, hi, basis = float(topic_demand[topic]), float(pr.loc[pr["topic"] == topic, "lo"].median()), float(pr.loc[pr["topic"] == topic, "hi"].median()), "parent topic (median)"
        else:
            dvals = sorted(g["demand"].unique().tolist())
            if len(dvals) > 1:
                multi_demand.append({"group_id": gid, "values": dvals})
            demand, lo, hi, basis = float(g["demand"].median()), float(g["lo"].median()), float(g["hi"].median()), g["basis"].iloc[0]
        n = len(g)
        codes = g["code"].value_counts()
        gap_by_run = {r: _r(float(x["sev"].isin(["warn", "bad"]).mean())) for r, x in g.groupby("run")}
        n_by_run = {r: int(len(x)) for r, x in g.groupby("run")}
        dom_run = max(n_by_run, key=lambda r: (n_by_run[r], r))
        groups.append({"group_id": gid, "topic": topic, "subtopic": g["subtopic"].iloc[0] if not is_small and gid.startswith(topic + " × ") and (g["subtopic"].iloc[0] or "") == gid.split(" × ", 1)[1] else "",
                       "zone": g["zone"].iloc[0] if not is_small and gid.split(" × ", 1)[1] == g["zone"].iloc[0] else "", "n_prompts": n,
                       "n_answers": int(a[a["pid"].isin(g["pid"]) & a["run"].isin(g["run"])].shape[0]),
                       "demand": demand, "lo": lo, "hi": hi, "basis": basis, "merged_from": merged_from.get(topic, []) if is_small else [],
                       "gap": float(g["sev"].isin(["warn", "bad"]).mean()), "gap_bad": float((g["sev"] == "bad").mean()),
                       "gap_by_run": gap_by_run, "n_by_run": n_by_run, "dominant_run": dom_run,
                       "codes": [{"code": k, "n": int(v)} for k, v in codes.items()], "top_code": codes.index[0],
                       "pids": list(zip(g["pid"], g["run"]))})
    total_demand = sum(x["demand"] for x in groups)
    for x in groups:
        x["demand_share"] = x["demand"] / total_demand; x["lo_share"] = x["lo"] / total_demand; x["hi_share"] = x["hi"] / total_demand

    # ---- lever per group ------------------------------------------------------
    c["is_inst"] = c["category_data"].isin(INST_CATS)
    c_lever = c[~c["owner_data"].isin(["noise", "other"])]
    key_to_group = {k: x["group_id"] for x in groups for k in x["pids"]}
    c_lever = c_lever.assign(group_id=[key_to_group.get((p, r)) for p, r in zip(c_lever["pid"], c_lever["run"])])
    c_lever["has_comp"] = c_lever["comps_present"].map(len) > 0
    for x in groups:
        gc = c_lever[c_lever["group_id"] == x["group_id"]]
        tot = len(gc)
        x["n_citations"] = int(tot)
        x["institutional_share"] = float(gc["is_inst"].mean()) if tot else None
        x["adversarial_share"] = float((gc["owner_data"] == "adversarial").mean()) if tot else None
        x["lever"] = {o: (float(((gc["owner_data"] == o) & (~gc["is_inst"])).mean()) if tot else None) for o in LEVER_OWNERS}
        x["_gc"] = gc

    # ---- rows -------------------------------------------------------------------
    def examples(x):
        g = pr[pr["group_id"] == x["group_id"]].copy()
        g["_bad"] = (g["sev"] == "bad").astype(int)
        ex = g.sort_values(["_bad", "demand", "pid"], ascending=[False, False, True]).head(2)
        return [{"pid": r.pid, "run": r.run, "sev": r.sev, "text": r.text[:150]} for r in ex.itertuples()]

    def where(x, owner):
        gc = x["_gc"]; sub = gc[(gc["owner_data"] == owner) & (~gc["is_inst"])]
        out = []
        for d, s in sorted(sub.groupby("domain"), key=lambda kv: (-len(kv[1]), kv[0]))[:5]:
            ans = s.drop_duplicates(ans_key)
            out.append({"domain": d, "category": s["category_data"].value_counts().idxmax(), "citations": int(len(s)), "with_us": int(ans["we_present"].sum()), "with_comp": int(ans["has_comp"].sum())})
        return out

    def base_row(x, owner):
        fx = fixes_by_code.get(x["top_code"], {})
        return {"group_id": x["group_id"], "group": {"topic": x["topic"], "subtopic": x["subtopic"], "zone": x["zone"]}, "owner": owner,
                "what": fx.get("do", ""), "who": fx.get("owner", ""), "speed": fx.get("speed", ""),
                "why": {"demand": _r(x["demand"], 0), "lo": _r(x["lo"], 0), "hi": _r(x["hi"], 0), "demand_share": _r(x["demand_share"]),
                        "gap": _r(x["gap"]), "gap_bad": _r(x["gap_bad"]), "n_prompts": x["n_prompts"], "gap_by_run": x["gap_by_run"], "n_by_run": x["n_by_run"], "dominant_run": x["dominant_run"],
                        "lever": _r(x["lever"].get(owner)) if owner else None, "institutional_share": _r(x["institutional_share"])},
                "cause": x["codes"][:3], "examples": examples(x),
                "impact_reach": {"point": _r(x["demand"] * x["gap"], 0), "lo": _r(x["lo"] * x["gap"], 0), "hi": _r(x["hi"] * x["gap"], 0),
                                 "caption": "ceiling, not a forecast — topic demand (Google proxy) × gap"}}

    source_rows, label_rows, no_source_other = [], [], []
    for x in groups:
        if x["n_citations"] > 0:
            for o in LEVER_OWNERS:
                lv = x["lever"][o]
                if lv and lv > 0:
                    r = base_row(x, o); r["score"] = x["demand_share"] * x["gap"] * lv; r["where"] = where(x, o); r["no_source_data"] = False
                    if o == "comp_owned":
                        r["what"] = "Competitor feeds answers with its own domains — build comparable owned content: " + r["what"]; r["who"] = "Digital"
                    source_rows.append(r)
        elif x["top_code"] in LABEL_CODES:
            r = base_row(x, None); r["owner"] = "label"; r["score"] = x["demand_share"] * x["gap"]; r["where"] = []; r["no_source_data"] = True
            label_rows.append(r)
        else:
            no_source_other.append({"group_id": x["group_id"], "top_code": x["top_code"]})
    th_src = terciles(source_rows); th_lab = terciles(label_rows) if label_rows else {"p3_min": None, "p2_min": None}
    for r in source_rows + label_rows:
        r["score"] = _r(r["score"], 6)

    adv = c[c["owner_data"] == "adversarial"].assign(group_id=[key_to_group.get((p, r)) for p, r in zip(c.loc[c["owner_data"] == "adversarial", "pid"], c.loc[c["owner_data"] == "adversarial", "run"])])
    adversarial = [{"domain": d, "category": s["category_data"].value_counts().idxmax(), "citations": int(len(s)), "groups": sorted(s["group_id"].dropna().unique().tolist())[:8]}
                   for d, s in sorted(adv.groupby("domain"), key=lambda kv: -len(kv[1]))[:10]]

    summary = {"brand": bd.our_name, "competitor": raw["meta"].get("competitor"), "cycle": "cycle_01",
               "config": {"min_group_prompts": min_n, "lever_denominator": "all citations in the group's answers after removing noise/other (institutional and adversarial stay in the denominator)"},
               "inventory": inventory, "groups_total": len(groups), "rows_total": len(source_rows), "rows_label_only": len(label_rows),
               "tercile_thresholds": th_src, "tercile_thresholds_label": th_lab,
               "gap_note": "Gap pools different failure kinds across runs (R1 absent from category answer, R2 lost duel, R4 label error, R6 message not delivered…); it is problem density on the topic, not one kind of failure — see gap_by_run / dominant_run on every row.",
               "recommendations": [{k: v for k, v in r.items()} for r in source_rows], "label_recommendations": label_rows,
               "groups_without_source_not_label": no_source_other, "adversarial_sources": adversarial,
               "quality": {"groups_with_multi_demand": multi_demand, "groups_merged_small": [x["group_id"] for x in groups if x["merged_from"]],
                           "groups_without_citations": [x["group_id"] for x in groups if x["n_citations"] == 0],
                           "answers_without_citations_pct": _r(100.0 * float((~aa["has"]).mean()), 2)}}
    C.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(C.METRICS_DIR / "prioritization_summary.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    gdf = pd.DataFrame([{"group_id": x["group_id"], "topic": x["topic"], "subtopic": x["subtopic"], "zone": x["zone"], "n_prompts": x["n_prompts"], "n_answers": x["n_answers"],
                         "demand": x["demand"], "lo": x["lo"], "hi": x["hi"], "basis": x["basis"], "demand_share": x["demand_share"], "gap": x["gap"], "gap_bad": x["gap_bad"],
                         "dominant_run": x["dominant_run"], "gap_by_run": json.dumps(x["gap_by_run"]), "top_code": x["top_code"], "n_citations": x["n_citations"],
                         "institutional_share": x["institutional_share"], **{"lever_" + o: x["lever"][o] for o in LEVER_OWNERS}, "merged_from": json.dumps(x["merged_from"], ensure_ascii=False)} for x in groups])
    gdf.sort_values("group_id").to_csv(C.METRICS_DIR / "prioritization_groups.csv", index=False)
    rdf = pd.DataFrame([{"rank": r["rank"], "priority": r["priority"], "list": "label" if r["no_source_data"] else "source", "group_id": r["group_id"], "topic": r["group"]["topic"], "subtopic": r["group"]["subtopic"], "zone": r["group"]["zone"],
                         "owner": r["owner"], "score": r["score"], "what": r["what"], "who": r["who"], "speed": r["speed"], **{"why_" + k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r["why"].items()},
                         "top_code": r["cause"][0]["code"], "top_domain": r["where"][0]["domain"] if r["where"] else "", "impact_reach": r["impact_reach"]["point"]} for r in source_rows + label_rows])
    rdf.to_csv(C.METRICS_DIR / "prioritization_rows.csv", index=False)

    def line(r):
        return "{}{} → {} · P{} · demand {:,.0f} · gap {:.0%} ({} {}) · lever {} · {} · {} · affects up to {:,.0f}/month".format(
            r["group"]["topic"], " / " + (r["group"]["subtopic"] or r["group"]["zone"]) if (r["group"]["subtopic"] or r["group"]["zone"]) else " / small", r["owner"], r["priority"], r["why"]["demand"], r["why"]["gap"],
            r["why"]["dominant_run"], "dominant", "n/a" if r["why"]["lever"] is None else "{:.0%}".format(r["why"]["lever"]), r["cause"][0]["code"], r["where"][0]["domain"] if r["where"] else "no source", r["impact_reach"]["point"])
    L = ["# Diagnosis & Prioritization — cycle 1 (step 6)",
         "Groups: {} ({} merged into `topic × small` at min {} prompts: {}); {} source rows (group × owner) + {} Label/Medical rows (no citations, label codes); {} groups without citations and without a label code: {}.".format(
             len(groups), len(summary["quality"]["groups_merged_small"]), min_n, ", ".join(summary["quality"]["groups_merged_small"]), len(source_rows), len(label_rows), len(no_source_other), ", ".join(x["group_id"] for x in no_source_other) or "none"),
         "Score = Demand_share × Gap × Lever (Label rows: Demand_share × Gap). Tercile thresholds (source rows): P3 ≥ {}, P2 ≥ {}; Label rows: P3 ≥ {}, P2 ≥ {}.".format(th_src["p3_min"], th_src["p2_min"], th_lab["p3_min"], th_lab["p2_min"]),
         "**Gap caveat:** Gap pools different failure kinds across runs — R1 absent from the category answer, R2 lost duel, R4 label error, R6 message not delivered — so it is problem density on the topic, not one kind of failure; every row carries gap_by_run and its dominant run.",
         "Lever = owner citations ÷ all citations in the group's answers (noise/other removed; institutional categories excluded from Lever and reported as institutional_share; adversarial reported separately). `impact_reach` = demand × gap is a ceiling, not a forecast.",
         "Top-5 recommendations:"] + ["{}. ".format(i + 1) + line(r) for i, r in enumerate(source_rows[:5])] + [
         "Label / Medical rows ({}): ".format(len(label_rows)) + ("; ".join("{} · P{} · gap {:.0%} · {} · who: {}".format(r["group_id"], r["priority"], r["why"]["gap"], r["cause"][0]["code"], r["who"]) for r in label_rows) or "none") + ".",
         "Top-3 adversarial (threat) sources: " + "; ".join("{} ({} citations, {})".format(d["domain"], d["citations"], d["category"]) for d in adversarial[:3]) + " — excluded from Lever.",
         "Quality: multi-demand groups {} (median taken); answers without citations {:.1f}%; `who` values include `Citere` for {} rows (own monitoring tasks — routed by step 7).".format(
             len(multi_demand), summary["quality"]["answers_without_citations_pct"], sum(1 for r in source_rows + label_rows if "Citere" in r["who"])),
         "Outputs: prioritization_summary.json, prioritization_groups.csv ({} groups), prioritization_rows.csv ({} rows).".format(len(groups), len(source_rows) + len(label_rows))]
    tbl = ["", "---", "Top-10 recommendations (source rows):", "", "| # | P | group | owner | score | demand | gap (dominant run) | gap_bad | lever | inst. share | cause | top domain | who | speed | reach ceiling |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in source_rows[:10]:
        tbl.append("| {} | {} | {} | {} | {:.5f} | {:,.0f} | {:.0%} ({}) | {:.0%} | {:.0%} | {:.0%} | {} | {} | {} | {} | {:,.0f} |".format(
            r["rank"], r["priority"], r["group_id"], r["owner"], r["score"], r["why"]["demand"], r["why"]["gap"], r["why"]["dominant_run"], r["why"]["gap_bad"], r["why"]["lever"], r["why"]["institutional_share"] or 0,
            r["cause"][0]["code"], r["where"][0]["domain"] if r["where"] else "", r["who"], r["speed"], r["impact_reach"]["point"]))
    tbl += ["", "Label / Medical rows:", "", "| # | P | group | score | demand | gap | gap_bad | cause | who | speed |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in label_rows:
        tbl.append("| {} | {} | {} | {:.5f} | {:,.0f} | {:.0%} | {:.0%} | {} | {} | {} |".format(r["rank"], r["priority"], r["group_id"], r["score"], r["why"]["demand"], r["why"]["gap"], r["why"]["gap_bad"], r["cause"][0]["code"], r["who"], r["speed"]))
    (C.METRICS_DIR / "prioritization_report.md").write_text("\n".join(L + tbl) + "\n", encoding="utf-8")
    print("\n".join(L[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
