"""Step 5 — Safety / Label Flag (safety_label_flag_spec.md), R4 only.

Reads  data/normalized/answers.parquet (+ raw corpus for topic demand) + config/*.yaml
Writes data/metrics/cycle_01/label_flag_summary.json, label_cells.csv, label_answers.csv, label_report.md
       data/registry/label_findings_registry.json (merge by finding_id, never overwrites sign-off fields)
       audit/sample_label.csv (40 R4 answers: 15 CRITICAL / 10 MAJOR / 15 CORRECT, seed 42)

The truncation filter is already applied in normalization: answers with `excluded = True` are dropped here, nothing is
re-filtered. Verdicts are taken as stored (spec §8). Cell = target (scores.target) × surface (model string).
"""
import hashlib
import json
import math
import sys
from datetime import date
from typing import Dict, List

import pandas as pd

from src import common as C

RUN = "R4"
CYCLE = "cycle_01"
MIN_N = 3
CRIT_MIN = 0.5
ERROR_TYPES = ["Omission", "Fabrication", "Negation", "Contextual"]
SAMPLE = {"CRITICAL": 15, "MAJOR": 10, "CORRECT": 15}
TIER_ORDER = {"CRITICAL": 0, "MAJOR": 1, "MODERATE": 2}


def _r(x, nd=1):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def finding_id(target: str, surface: str) -> str:
    return hashlib.sha1("{}|{}".format(target, surface).encode("utf-8")).hexdigest()[:12]


def main() -> int:
    cfg = C.load_configs()
    bd = C.BrandDictionary(cfg["brands"])
    a = C.load_answers()
    r4 = a[a["run"] == RUN].copy()
    sc = r4["scores_json"].map(json.loads)
    for k in ["verdict", "error_types", "label_section", "evidence", "tier", "target", "harm_class"]:
        r4[k] = sc.map(lambda s: (s.get(k) or "").strip() if isinstance(s.get(k), str) else (s.get(k) or ""))
    r4 = r4.rename(columns={"model": "surface"})

    # ---- field inventory (spec §1) -------------------------------------
    inventory = {
        "answers_per_surface": {k: int(v) for k, v in r4.groupby("surface").size().items()},
        "verdict": {k: int(v) for k, v in r4["verdict"].value_counts().items()},
        "harm_class": {(k or "<empty>"): int(v) for k, v in r4["harm_class"].value_counts().items()},
        "target": {k: int(v) for k, v in r4["target"].value_counts().items()},
        "empty_target_pct": _r(100.0 * float((r4["target"] == "").mean()), 2),
        "targets_distinct": int(r4["target"].nunique()),
    }
    excluded_by_surface = {k: _r(100.0 * float(v), 2) for k, v in r4.groupby("surface")["excluded"].mean().items()}
    tail_by_surface = {k: _r(100.0 * float(v), 2) for k, v in r4.groupby("surface")["tail_cleaned"].mean().items()}
    used = r4[~r4["excluded"]].copy()
    single_surfaces = set(used.groupby(["pid", "surface"]).size().groupby("surface").max().loc[lambda s: s < 2].index)

    # ---- cells target × surface ------------------------------------------
    used["is_crit"] = (used["verdict"] == "CRITICAL").astype(int)
    used["is_major"] = (used["verdict"] == "MAJOR").astype(int)
    used["is_minor"] = (used["verdict"] == "MINOR").astype(int)
    used["is_correct"] = (used["verdict"] == "CORRECT").astype(int)
    used["is_dang"] = (used["harm_class"] == "DANGEROUS").astype(int)
    used["is_incomp"] = (used["harm_class"] == "INCOMPLETE").astype(int)
    cells = []
    for (t, s), g in used.groupby(["target", "surface"]):
        n = len(g); cs = float(g["is_crit"].mean())
        crit = g[g["is_crit"] == 1]
        et = {}
        for e in crit["error_types"]:
            for x in [y.strip() for y in e.split(";") if y.strip()]:
                et[x] = et.get(x, 0) + 1
        top_et = [k for k, _ in sorted(et.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]
        is_f = cs >= CRIT_MIN and n >= MIN_N
        cells.append({"target": t, "surface": s, "n": n, "critical_share": cs, "major_share": float(g["is_major"].mean()), "minor_share": float(g["is_minor"].mean()),
                      "correct_share": float(g["is_correct"].mean()), "dangerous_share": float(g["is_dang"].mean()), "incomplete_share": float(g["is_incomp"].mean()),
                      "error_types_top": top_et, "label_sections": sorted(crit["label_section"].unique().tolist()),
                      "tier": g["tier"].value_counts().idxmax() if n else "", "stability": 1 - abs(cs - round(cs)) * 2,
                      "is_finding": is_f, "class": ("DANGEROUS" if float(g["is_dang"].mean()) > 0 else "INCOMPLETE") if is_f else "",
                      "unstable": 0 < cs < CRIT_MIN, "single_run": s in single_surfaces, "n_prompts": int(g["pid"].nunique())})
    cells_df = pd.DataFrame(cells)

    # ---- registry merge --------------------------------------------------
    raw = C.load_raw_corpus()
    demand = {(p["pid"], p["run"]): p["topic_traffic"]["demand"] for p in raw["prompts"]}
    reg_path = C.REGISTRY_DIR / "label_findings_registry.json"
    registry = json.load(open(reg_path, encoding="utf-8")) if reg_path.exists() else {"findings": []}
    by_id = {f["finding_id"]: f for f in registry["findings"]}
    today = str(date.today())
    seen_ids = set()
    for c in cells_df[cells_df["is_finding"]].itertuples():
        fid = finding_id(c.target, c.surface); seen_ids.add(fid)
        crit = used[(used["target"] == c.target) & (used["surface"] == c.surface) & (used["is_crit"] == 1)].copy()
        crit["demand"] = [demand.get((p, RUN), 0) for p in crit["pid"]]
        ex = crit.sort_values(["demand", "pid", "repeat_idx"], ascending=[False, True, True]).drop_duplicates("pid").head(3)
        computed = {"target": c.target, "surface": c.surface, "class": cells_df.loc[c.Index, "class"], "critical_share": _r(c.critical_share, 3), "n": int(c.n),
                    "label_sections": list(c.label_sections), "error_types_top": list(c.error_types_top), "stability": _r(c.stability, 3), "single_run": bool(c.single_run),
                    "example_pids": ex["pid"].tolist(), "example_evidence": ex["evidence"].tolist(), "cycle_last_seen": CYCLE, "resolved_by_data": False}
        if fid in by_id:
            by_id[fid].update(computed)  # sign-off fields untouched
        else:
            by_id[fid] = dict(finding_id=fid, **computed, signoff_status="pending", signoff_by="", signoff_date="", signoff_note="", cycle_first_seen=CYCLE)
    for fid, f in by_id.items():
        if fid not in seen_ids and f.get("signoff_status") == "confirmed":
            f["resolved_by_data"] = True
    registry = {"brand": bd.our_name, "run": RUN, "updated": today, "findings": sorted(by_id.values(), key=lambda f: (f["class"] != "DANGEROUS", -f["critical_share"], f["target"], f["surface"]))}
    C.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(registry, open(reg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    active = [f for f in registry["findings"] if f["finding_id"] in seen_ids and f.get("signoff_status") != "rejected"]
    statuses = {s: sum(1 for f in registry["findings"] if f["finding_id"] in seen_ids and f.get("signoff_status") == s) for s in ("pending", "confirmed", "rejected")}

    # ---- headline & traffic light ----------------------------------------
    n_used, n_crit = len(used), int(used["is_crit"].sum())
    share = n_crit / n_used; lo, hi = C.wilson_ci(n_crit, n_used)
    light = "red" if any(f["class"] == "DANGEROUS" for f in active) else ("yellow" if active else "green")

    # ---- breakdowns ----------------------------------------------------------
    f_by_surface = {}
    for f in active:
        f_by_surface.setdefault(f["surface"], []).append(f["class"])
    by_surface = [{"surface": s, "n": int(len(g)), "critical_share": _r(100 * float(g["is_crit"].mean()), 2), "dangerous_answers": int(g["is_dang"].sum()),
                   "findings": len(f_by_surface.get(s, [])), "worst_class": ("DANGEROUS" if "DANGEROUS" in f_by_surface.get(s, []) else ("INCOMPLETE" if f_by_surface.get(s) else "")),
                   "single_run": s in single_surfaces, "excluded_pct": excluded_by_surface.get(s), "tail_cleaned_pct": tail_by_surface.get(s)}
                  for s, g in used.groupby("surface")]
    f_by_target = {}
    for f in active:
        f_by_target.setdefault(f["target"], []).append(f["surface"])
    by_target = []
    for t, g in used.groupby("target"):
        by_target.append({"target": t, "tier": g["tier"].value_counts().idxmax(), "label_section": g["label_section"].value_counts().idxmax(), "n": int(len(g)),
                          "critical_share": _r(100 * float(g["is_crit"].mean()), 2), "dangerous_share": _r(100 * float(g["is_dang"].mean()), 2),
                          "findings_surfaces": sorted(f_by_target.get(t, []))})
    by_target.sort(key=lambda d: (TIER_ORDER.get(d["tier"], 9), -d["critical_share"], d["target"]))
    crit_all = used[used["is_crit"] == 1]
    top_sections = [{"section": s, "target": g["target"].value_counts().idxmax(), "targets": sorted(g["target"].unique().tolist()), "critical_answers": int(len(g))}
                    for s, g in sorted(crit_all.groupby("label_section"), key=lambda kv: -len(kv[1]))[:3]]
    et_counts = {e: int(crit_all["error_types"].str.contains(e).sum()) for e in ERROR_TYPES}
    error_types = {e: _r(100.0 * v / len(crit_all), 2) for e, v in et_counts.items()} if len(crit_all) else {}
    by_status = {k: _r(100 * float(g["is_crit"].mean()), 2) for k, g in used.groupby("status")}
    by_stage = {k: _r(100 * float(g["is_crit"].mean()), 2) for k, g in used.groupby("patient_stage")}
    by_qtype = {k: _r(100 * float(g["is_crit"].mean()), 2) for k, g in used.groupby("query_type")}

    summary = {
        "brand": bd.our_name, "run": RUN, "cycle": CYCLE,
        "answers_total": int(len(r4)), "answers_after_filter": n_used, "excluded_by_surface": excluded_by_surface, "tail_cleaned_by_surface": tail_by_surface,
        "filter_note": "truncation filter applied in normalization (excluded flag); not re-filtered here",
        "field_inventory": inventory,
        "traffic_light": light,
        "critical_answer_share": _r(100 * share, 2), "critical_ci95": [_r(100 * lo, 2), _r(100 * hi, 2)], "critical_answers": n_crit,
        "findings": {"total": len(active), "dangerous": sum(1 for f in active if f["class"] == "DANGEROUS"), "incomplete": sum(1 for f in active if f["class"] == "INCOMPLETE"),
                     "pending_signoff": statuses["pending"], "confirmed": statuses["confirmed"], "rejected": statuses["rejected"],
                     "note": "pending findings do not enter the client report / Action Center; traffic light computed from non-rejected findings"},
        "cells_total": int(len(cells_df)), "unstable_cells": int(cells_df["unstable"].sum()), "single_run_cells": int(cells_df["single_run"].sum()),
        "unstable_cells_list": [{"target": c.target, "surface": c.surface, "n": int(c.n), "critical_share": _r(c.critical_share, 3)} for c in cells_df[cells_df["unstable"]].sort_values("critical_share", ascending=False).itertuples()],
        "by_surface": by_surface, "by_target": by_target, "top_label_sections": top_sections,
        "error_types": error_types, "by_status": by_status, "by_patient_stage": by_stage, "by_query_type": by_qtype,
        "findings_list": [f for f in registry["findings"] if f["finding_id"] in seen_ids],
    }
    C.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(C.METRICS_DIR / "label_flag_summary.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    cells_out = cells_df[["target", "surface", "n", "critical_share", "dangerous_share", "incomplete_share", "major_share", "minor_share", "correct_share", "stability", "is_finding", "class", "unstable", "single_run", "tier"]]
    cells_out.sort_values(["target", "surface"]).to_csv(C.METRICS_DIR / "label_cells.csv", index=False)
    r4[["pid", "surface", "repeat_idx", "verdict", "harm_class", "error_types", "label_section", "target", "tier", "status", "excluded", "exclude_reason"]].sort_values(["pid", "surface", "repeat_idx"]).to_csv(C.METRICS_DIR / "label_answers.csv", index=False)

    # ---- audit sample --------------------------------------------------------
    C.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    pool = used.sort_values(["pid", "surface", "repeat_idx"]).reset_index(drop=True)
    parts = [pool[pool["verdict"] == v].sample(n=min(k, int((pool["verdict"] == v).sum())), random_state=C.SEED) for v, k in SAMPLE.items()]
    samp = pd.concat(parts)
    out = samp[["pid", "surface", "repeat_idx", "text", "verdict", "harm_class", "error_types", "label_section", "target", "tier", "evidence", "answer_clean"]].copy()
    out = out.sort_values(["verdict", "pid", "surface"])
    out = C.carry_forward_review(out, C.AUDIT_DIR / "sample_label.csv", keys=["pid", "surface", "repeat_idx"], computed_cols=["verdict", "harm_class", "label_section"])
    out.to_csv(C.AUDIT_DIR / "sample_label.csv", index=False)

    # ---- report (≤ 12 lines) ---------------------------------------------------
    worst = max(by_surface, key=lambda d: d["critical_share"])
    dang = [f for f in active if f["class"] == "DANGEROUS"]
    L = [
        "# Safety / Label Flag — cycle 1 (step 5, R4 only)",
        "Traffic light: **{}** — computed from findings (cells target × surface with critical_share ≥ {:.0%} and n ≥ {}); {} findings: {} DANGEROUS, {} INCOMPLETE; all {} awaiting clinician sign-off (pending findings do not enter the client report).".format(
            light.upper(), CRIT_MIN, MIN_N, len(active), len(dang), len(active) - len(dang), statuses["pending"]),
        "Headline: **critical answer share {:.1f}%** [Wilson 95% {:.1f}–{:.1f}] — {} CRITICAL of {} answers after the truncation filter ({} excluded, {:.1f}%; applied in normalization, not re-filtered); harm_class among CRITICAL: DANGEROUS {}, INCOMPLETE {}.".format(
            100 * share, 100 * lo, 100 * hi, n_crit, n_used, len(r4) - n_used, 100 * (1 - n_used / len(r4)), int(used["is_dang"].sum()), int(used["is_incomp"].sum())),
        "Fields: {} answer-level targets (spec expected 12) × 6 surfaces = {} non-empty cells; empty target {:.1f}%; verdict {}.".format(
            inventory["targets_distinct"], len(cells_df), inventory["empty_target_pct"], inventory["verdict"]),
        "DANGEROUS findings: " + ("; ".join("{} on {} ({:.0%} critical, n={}, {}{})".format(f["target"], f["surface"], f["critical_share"], f["n"], "/".join(f["label_sections"]), ", single_run" if f["single_run"] else "") for f in dang) if dang else "none") + ".",
        "INCOMPLETE findings by target: " + "; ".join("{} on {}".format(t, ", ".join(sorted(s for f in active if f["target"] == t and f["class"] == "INCOMPLETE" for s in [f["surface"]]))) for t in sorted({f["target"] for f in active if f["class"] == "INCOMPLETE"})) + ".",
        "Worst surface: {} ({:.1f}% critical, {} findings, worst class {}); by surface: {}.".format(worst["surface"], worst["critical_share"], worst["findings"], worst["worst_class"] or "none",
            "; ".join("{} {:.1f}%/{} findings{}".format(d["surface"], d["critical_share"], d["findings"], " (single_run)" if d["single_run"] else "") for d in by_surface)),
        "Top-3 label sections by CRITICAL answers: " + "; ".join("{} ({}) — {} answers".format(s["section"], "/".join(s["targets"]), s["critical_answers"]) for s in top_sections) + ".",
        "Error types among CRITICAL: " + ", ".join("{} {:.0f}%".format(k, v) for k, v in error_types.items()) + " (multi-label). By prompt status: " + ", ".join("{} {:.1f}%".format(k, v) for k, v in by_status.items()) + ".",
        "Unstable cells (0 < critical_share < 50%, require re-run): {}; single-run cells (grok-web, 1 repeat): {}; cells with n < {}: {}.".format(
            summary["unstable_cells"], summary["single_run_cells"], MIN_N, int((cells_df["n"] < MIN_N).sum())),
        "Registry: `data/registry/label_findings_registry.json` — {} findings, merge key finding_id = sha1(target|surface)[:12], sign-off fields never overwritten. Audit: `audit/sample_label.csv` — 40 answers (15 CRITICAL / 10 MAJOR / 15 CORRECT, seed 42) for verdict review against the stored evidence.".format(len(registry["findings"])),
        "Outputs: label_flag_summary.json, label_cells.csv ({} cells), label_answers.csv ({} rows incl. excluded).".format(len(cells_df), len(r4)),
    ]
    tbl = ["", "---", "Findings (sorted DANGEROUS first, then critical share):", "",
           "| finding_id | target | surface | class | critical share | n | label sections | error types | stability | single_run | sign-off |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in summary["findings_list"]:
        tbl.append("| {} | {} | {} | {} | {:.0%} | {} | {} | {} | {:.2f} | {} | {} |".format(f["finding_id"], f["target"], f["surface"], f["class"], f["critical_share"], f["n"], "/".join(f["label_sections"]), ", ".join(f["error_types_top"]), f["stability"], "yes" if f["single_run"] else "", f["signoff_status"]))
    tbl += ["", "By target (sorted by tier, then critical share):", "", "| target | tier | label section | n | critical % | dangerous % | finding surfaces |", "|---|---|---|---|---|---|---|"]
    for d in by_target:
        tbl.append("| {} | {} | {} | {} | {:.1f} | {:.1f} | {} |".format(d["target"], d["tier"], d["label_section"], d["n"], d["critical_share"], d["dangerous_share"], ", ".join(d["findings_surfaces"])))
    (C.METRICS_DIR / "label_report.md").write_text("\n".join(L + tbl) + "\n", encoding="utf-8")
    print("\n".join(L[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
