"""Step 3b — Citation Tracking (citation_tracking_spec.md).

Reads  data/normalized/citations.parquet + answers.parquet + config/*.yaml
Writes data/metrics/cycle_01/citations_summary.json, citations_domains.csv, citations_raw.csv, citations_report.md
       audit/sample_citations.csv (40 random domains, seed 42)

Unit is a citation (one domain occurrence in one answer, deduplicated within the answer). Aggregation is directly over
citations across all runs that carry them (R1, R2, R3, R6, R7, R9) — not repeats -> prompts as in the other specs.
Pie = owned + earned + institutional + competitor. Adversarial reported separately; noise and artifacts excluded;
citations from quality-excluded answers dropped. Gap list on R1 C1 (headline scope).
"""
import json
import math
import sys
from typing import Dict

import pandas as pd

from src import common as C

HEADLINE_RUN = "R1"
SAMPLE_N = 40
SUBTYPE_MAP = {"media": "health_media", "hospital": "hospital", "directory": "directory", "ugc": "ugc", "video": "ugc", "social": "ugc",
               "news_pr": "news", "pr_wire": "news", "telehealth": "telehealth", "litigation": "litigation", "other": "other",
               "advocacy": "advocacy", "payer": "payer"}
ACTION_TYPE = {"health_media": "PR", "news": "PR", "hospital": "PR", "advocacy": "PR", "directory": "data feed", "payer": "data feed",
               "ugc": "monitor", "telehealth": "outreach", "other": "review"}


def _r(x, nd=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def owner_group(o: str) -> str:
    return "competitor" if isinstance(o, str) and o.startswith("competitor:") else o


def main() -> int:
    cfg = C.load_configs()
    bd = C.BrandDictionary(cfg["brands"])
    a = C.load_answers()
    c = C.load_citations()
    a["comps_present"] = a["comps_present"].map(lambda x: list(x) if x is not None else [])
    c["comps_present"] = c["comps_present"].map(lambda x: list(x) if x is not None else [])
    ans_key = ["pid", "run", "model", "repeat_idx"]
    c = c.merge(a[ans_key + ["zone", "model_family"]].rename(columns={"model_family": "fam"}), on=ans_key, how="left")
    c["model_family"] = c["fam"]; c = c.drop(columns=["fam"])

    n_total = len(c)
    art = c[c["is_artifact"]]
    artifacts_by_model = {m: _r(100.0 * float(v)) for m, v in c.groupby("model")["is_artifact"].mean().items() if v > 0}
    live = c[(~c["is_artifact"]) & (~c["dedup"]) & (~c["excluded"]) & (c["owner"] != "noise")].copy()
    live["group"] = live["owner"].map(owner_group)
    live["subtype"] = live.apply(lambda r: SUBTYPE_MAP.get(r["category_data"], r["category_data"]) if r["group"] == "earned" else None, axis=1)
    pie = live[live["group"].isin(["owned", "earned", "institutional", "competitor"])].copy()
    adv = live[live["group"] == "adversarial"]

    # ---- coverage ---------------------------------------------------------
    runs_with = sorted(c["run"].unique().tolist())
    ans_with = c.drop_duplicates(ans_key).shape[0]
    n_answers_all = len(a)
    ans_in_runs = int(a["run"].isin(runs_with).sum())
    runs_without = sorted(set(a["run"].unique()) - set(runs_with))

    # ---- owner pie --------------------------------------------------------
    def shares(df: pd.DataFrame) -> Dict[str, float]:
        n = len(df)
        return {g: _r(100.0 * float((df["group"] == g).sum()) / n) if n else None for g in ["owned", "earned", "institutional", "competitor"]}
    owner_shares = shares(pie)
    by_model = [dict(model=m, n=int(len(g)), **shares(g)) for m, g in pie.groupby("model")]
    by_family = [dict(model=m, n=int(len(g)), **shares(g)) for m, g in pie.groupby("model_family")]
    by_class = [dict(cls=k, n=int(len(g)), **shares(g)) for k, g in pie.groupby("class")]
    by_run = [dict(run=k, n=int(len(g)), **shares(g)) for k, g in pie.groupby("run")]
    earned = pie[pie["group"] == "earned"]
    earned_sub = {k: _r(100.0 * float(v) / len(earned)) for k, v in earned["subtype"].value_counts().items()}
    comp_split = {k.split(":", 1)[1]: int(v) for k, v in pie.loc[pie["group"] == "competitor", "owner"].value_counts().items()}
    with_us = pie[pie["we_present"]]
    owned_share_with_us = _r(100.0 * float((with_us["group"] == "owned").mean())) if len(with_us) else None
    owned_share_without_us = _r(100.0 * float((pie.loc[~pie["we_present"], "group"] == "owned").mean()))

    # ---- domain table -----------------------------------------------------
    pie["has_comp"] = pie["comps_present"].map(len) > 0
    n_ans_pie = pie.drop_duplicates(ans_key).shape[0]
    dom = pie.groupby("domain").agg(citations=("url", "size"), answers=("pid", lambda s: 0)).reset_index()
    dom["answers"] = pie.drop_duplicates(ans_key + ["domain"]).groupby("domain").size().reindex(dom["domain"]).values
    dom["share"] = 100.0 * dom["citations"] / len(pie)
    dom["answers_pct"] = 100.0 * dom["answers"] / n_ans_pie
    dom["owner"] = pie.groupby("domain")["owner"].agg(lambda s: s.value_counts().idxmax()).reindex(dom["domain"]).values
    dom["group"] = dom["owner"].map(owner_group)
    dom["subtype"] = pie.groupby("domain")["subtype"].agg(lambda s: s.value_counts().idxmax() if s.notna().any() else None).reindex(dom["domain"]).values
    dom["with_us_pct"] = 100.0 * pie.groupby("domain")["we_present"].mean().reindex(dom["domain"]).values
    dom["with_comp_pct"] = 100.0 * pie.groupby("domain")["has_comp"].mean().reindex(dom["domain"]).values
    dom["top_model"] = pie.groupby("domain")["model"].agg(lambda s: s.value_counts().idxmax()).reindex(dom["domain"]).values
    dom["top_zone"] = pie.groupby("domain")["zone"].agg(lambda s: s.value_counts().idxmax()).reindex(dom["domain"]).values
    dom["sample_url"] = pie.groupby("domain")["url"].first().reindex(dom["domain"]).values

    # ---- gap list (R1 C1) --------------------------------------------------
    g1 = pie[(pie["class"] == "C1") & (pie["run"] == HEADLINE_RUN)].copy()
    g1["comp_not_us"] = g1["has_comp"] & (~g1["we_present"])
    ga = g1.drop_duplicates(ans_key + ["domain"])
    gap = ga.groupby("domain").agg(cites_comp=("comp_not_us", "sum"), cites_us=("we_present", "sum")).reset_index()
    fed = ga[ga["comp_not_us"]].groupby("domain")["comps_present"].agg(lambda s: len({b for l in s for b in l}))
    gap["competitors_fed"] = gap["domain"].map(fed).fillna(0).astype(int)
    gap["gap_score"] = gap["cites_comp"].astype(int) - gap["cites_us"].astype(int)
    dom = dom.merge(gap[["domain", "gap_score", "cites_comp", "cites_us", "competitors_fed"]], on="domain", how="left")
    dom["gap_score"] = dom["gap_score"].fillna(0).astype(int)
    gaps = dom[(dom["gap_score"] > 0)].copy()
    inst_gap = int((gaps["group"] == "institutional").sum())
    gaps = gaps[gaps["group"] != "institutional"].sort_values(["gap_score", "competitors_fed", "domain"], ascending=[False, False, True])
    gaps["action_type"] = gaps.apply(lambda r: ACTION_TYPE.get(r["subtype"], "review") if r["group"] == "earned" else ("n/a (competitor site)" if r["group"] == "competitor" else "n/a"), axis=1)

    def dom_rec(r) -> dict:
        return {"domain": r["domain"], "citations": int(r["citations"]), "share": _r(r["share"]), "owner": r["owner"], "subtype": r["subtype"] if isinstance(r["subtype"], str) else None,
                "answers_pct": _r(r["answers_pct"]), "with_us_pct": _r(r["with_us_pct"]), "with_comp_pct": _r(r["with_comp_pct"]), "top_model": r["top_model"], "top_zone": r["top_zone"]}
    dom_sorted = dom.sort_values(["citations", "domain"], ascending=[False, True])
    top10 = [dom_rec(r) for _, r in dom_sorted.head(10).iterrows()]
    top_by_owner = {g: [dom_rec(r) for _, r in dom_sorted[dom_sorted["group"] == g].head(5).iterrows()] for g in ["owned", "earned", "institutional", "competitor"]}
    top100_earned = dom_sorted[dom_sorted["group"] == "earned"].head(100)
    uncl = dom_sorted[(dom_sorted["group"] == "earned") & (dom_sorted["subtype"] == "other")].head(30)["domain"].tolist()
    adv_top = [{"domain": d, "citations": int(n)} for d, n in adv["domain"].value_counts().head(15).items()]

    summary = {
        "brand": bd.our_name,
        "scope": {"runs_with_citations": runs_with, "runs_without_citations": runs_without, "unit": "citation (domain occurrence in one answer, deduplicated within the answer)",
                  "aggregation": "directly over citations (not repeats -> prompts)", "gap_list_scope": "R1 C1 answers (headline scope)"},
        "citations_total": int(n_total), "citations_in_pie": int(len(pie)),
        "answers_with_citations": int(ans_with), "answers_total": int(n_answers_all),
        "answers_without_citations_pct": _r(100.0 * (1 - ans_with / n_answers_all)),
        "answers_without_citations_pct_within_citation_runs": _r(100.0 * (1 - ans_with / ans_in_runs)),
        "artifacts_removed": {d: int(n) for d, n in art["host"].value_counts().items()}, "artifacts_share_by_model_pct": artifacts_by_model,
        "removed": {"noise": int((c["owner"] == "noise").sum() - ((c["owner"] == "noise") & c["is_artifact"]).sum()), "duplicates_within_answer": int(c["dedup"].sum()),
                    "from_quality_excluded_answers": int(((~c["is_artifact"]) & (~c["dedup"]) & c["excluded"]).sum()), "adversarial_reported_separately": int(len(adv))},
        "owner_shares": owner_shares, "competitor_split": comp_split,
        "owner_shares_by_model": by_model, "owner_shares_by_family": by_family, "owner_shares_by_class": by_class, "owner_shares_by_run": by_run,
        "earned_subtypes": earned_sub, "subtype_mapping": SUBTYPE_MAP,
        "owned_share_in_answers_with_us": owned_share_with_us, "owned_share_in_answers_without_us": owned_share_without_us,
        "top_domains": top10, "top_by_owner": top_by_owner,
        "gap_list": [{"domain": r["domain"], "gap_score": int(r["gap_score"]), "cites_comp": int(r["cites_comp"]), "cites_us": int(r["cites_us"]), "competitors_fed": int(r["competitors_fed"]),
                      "owner": r["owner"], "subtype": r["subtype"] if isinstance(r["subtype"], str) else None, "action_type": r["action_type"]} for _, r in gaps.head(10).iterrows()],
        "gap_domains_total": int(len(gaps)), "institutional_feeding_competitors": inst_gap,
        "adversarial_sources": adv_top, "unclassified_top30": uncl,
        "domains_total": int(len(dom)),
    }

    C.METRICS_DIR.mkdir(parents=True, exist_ok=True); C.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(C.METRICS_DIR / "citations_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    dom_out = dom_sorted[["domain", "citations", "share", "owner", "subtype", "answers_pct", "with_us_pct", "with_comp_pct", "gap_score", "cites_comp", "cites_us", "competitors_fed", "top_model", "top_zone"]]
    dom_out.to_csv(C.METRICS_DIR / "citations_domains.csv", index=False)
    raw = pie[["pid", "run", "model", "repeat_idx", "class", "domain", "url", "owner", "subtype", "we_present", "comps_present"]].copy()
    raw["comps_present"] = raw["comps_present"].map(lambda l: json.dumps(l, ensure_ascii=False))
    raw.sort_values(["run", "pid", "model", "repeat_idx"]).to_csv(C.METRICS_DIR / "citations_raw.csv", index=False)

    # audit sample: 40 random domains (seed 42) with computed owner/subtype
    pool = dom_sorted.sort_values("domain").reset_index(drop=True)
    samp = pool.sample(n=min(SAMPLE_N, len(pool)), random_state=C.SEED).sort_values("domain")
    samp_out = samp[["domain", "citations", "owner", "subtype", "sample_url", "top_model"]].copy()
    samp_out["owner_group"] = samp_out["owner"].map(owner_group)
    samp_out = C.carry_forward_review(samp_out, C.AUDIT_DIR / "sample_citations.csv", keys=["domain"], computed_cols=["owner", "subtype"])
    samp_out.to_csv(C.AUDIT_DIR / "sample_citations.csv", index=False)

    # ---- report (<= 12 lines) -------------------------------------------
    L = [
        "# Citation Tracking — cycle 1 (step 3b)",
        "Unit = citation (domain occurrence in one answer, deduplicated); aggregation directly over citations, not repeats→prompts. Runs with citations: {}; no citations on {} ({} answers, {:.1f}% of all).".format(
            ", ".join(runs_with), ", ".join(runs_without), n_answers_all - ans_in_runs, 100.0 * (n_answers_all - ans_in_runs) / n_answers_all),
        "Pie ({} citations): **owned {:.1f}% · earned {:.1f}% · institutional {:.1f}% · competitor {:.1f}%**; adversarial reported separately ({} citations); noise {} and artifacts {} removed; {} duplicates within answers dropped.".format(
            len(pie), owner_shares["owned"], owner_shares["earned"], owner_shares["institutional"], owner_shares["competitor"], len(adv), summary["removed"]["noise"], len(art), summary["removed"]["duplicates_within_answer"]),
        "Owned share in answers where we are named: {:.1f}% (vs {:.1f}% where we are not). Competitor sites split: {}.".format(
            owned_share_with_us, owned_share_without_us, ", ".join("{} {}".format(k, v) for k, v in sorted(comp_split.items(), key=lambda kv: -kv[1]))),
        "By model: " + "; ".join("{} owned {:.1f} / earned {:.1f} / inst {:.1f} / comp {:.1f}".format(d["model"], d["owned"], d["earned"], d["institutional"], d["competitor"]) for d in by_model) + ".",
        "Earned subtypes: " + ", ".join("{} {:.1f}%".format(k, v) for k, v in sorted(earned_sub.items(), key=lambda kv: -kv[1])) + " (mapping: media→health_media, news_pr/pr_wire→news, video/social→ugc; advocacy/payer kept).",
        "Top-5 domains: " + "; ".join("{} {:.1f}% ({}, with us {:.0f}%)".format(d["domain"], d["share"], owner_group(d["owner"]), d["with_us_pct"]) for d in top10[:5]) + ".",
        "Top-5 gaps (R1 C1; feed competitor answers, silent about us): " + ("; ".join("{} gap {} ({} comp / {} us, feeds {}) → {} [{}]".format(
            g["domain"], g["gap_score"], g["cites_comp"], g["cites_us"], g["competitors_fed"], g["action_type"], g["subtype"] or owner_group(g["owner"])) for g in summary["gap_list"][:5]) or "none") + ".",
        "Institutional domains feeding the competitor: {} (no action). Adversarial top-3: {}.".format(inst_gap, ", ".join("{} ({})".format(d["domain"], d["citations"]) for d in adv_top[:3])),
        "Answers without citations: {:.1f}% of all answers ({:.1f}% within citation-bearing runs). Artifact share by model: {}.".format(
            summary["answers_without_citations_pct"], summary["answers_without_citations_pct_within_citation_runs"], artifacts_by_model),
        "Audit: `audit/sample_citations.csv` — {} random domains (seed 42) with computed owner/subtype; review owner by eye. {} earned/other domains listed for manual labeling in the JSON.".format(len(samp_out), len(uncl)),
        "Outputs: citations_summary.json, citations_domains.csv ({} domains), citations_raw.csv ({} rows).".format(len(dom), len(raw)),
    ]
    tbl = ["", "---", "Top-10 domains:", "", "| domain | citations | share % | owner | subtype | answers % | with us % | with comp % | top model | top zone |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d in top10:
        tbl.append("| {} | {} | {:.2f} | {} | {} | {:.1f} | {:.1f} | {:.1f} | {} | {} |".format(d["domain"], d["citations"], d["share"], d["owner"], d["subtype"] or "", d["answers_pct"], d["with_us_pct"], d["with_comp_pct"], d["top_model"], d["top_zone"]))
    tbl += ["", "Gap list (R1 C1, top-10, institutional excluded):", "", "| domain | gap | cites_comp | cites_us | competitors fed | owner | subtype | action |", "|---|---|---|---|---|---|---|---|"]
    for g in summary["gap_list"]:
        tbl.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(g["domain"], g["gap_score"], g["cites_comp"], g["cites_us"], g["competitors_fed"], g["owner"], g["subtype"] or "", g["action_type"]))
    tbl += ["", "Owner shares by class and by model:", "", "| slice | n | owned % | earned % | institutional % | competitor % |", "|---|---|---|---|---|---|"]
    for d in by_class:
        tbl.append("| class {} | {} | {:.1f} | {:.1f} | {:.1f} | {:.1f} |".format(d["cls"], d["n"], d["owned"], d["earned"], d["institutional"], d["competitor"]))
    for d in by_model:
        tbl.append("| {} | {} | {:.1f} | {:.1f} | {:.1f} | {:.1f} |".format(d["model"], d["n"], d["owned"], d["earned"], d["institutional"], d["competitor"]))
    (C.METRICS_DIR / "citations_report.md").write_text("\n".join(L + tbl) + "\n", encoding="utf-8")
    print("\n".join(L[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
