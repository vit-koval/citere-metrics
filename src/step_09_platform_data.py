"""Step 9 — platform_data.json (platform_data_spec.md).

All numbers come from the pipeline (metrics outputs, registries, normalized parquet, corpus). All prose, causes, fix cards,
SERP snapshots and inventory come from the platform export data/raw/citere_points_full.json. Nothing recomputed; no number
from the export is trusted except point_rank_score (= export priority), prompt_share and ai_native (labelled).
Checks (spec §3) must all pass, else the file is not written.
"""
import gzip, base64, json, math, re, sys
from collections import Counter, defaultdict

import pandas as pd

from src import common as C

TRACK_AUDIENCE = {"TRACK": "citere", "OWNED": "client", "EARNED": "client", "LABEL-MEDICAL": "client"}
CARD_TO_OWNER = {"OWNED": {"owned"}, "EARNED": {"earned", "ugc", "comp_owned"}, "LABEL-MEDICAL": {"label"}}
RUN_FIELDS = {"R1": ["our_status", "our_rank", "consideration_set"], "R2": ["winner", "axis_winner", "split_axes", "third_brands"],
              "R3": ["stance", "tone", "risk_overload", "churn_push"], "R4": ["verdict", "harm_class", "target", "label_section", "error_types", "tier"],
              "R5": ["verdict", "harm_class", "target", "label_section", "error_types"], "R6": ["status", "attribution", "anti_frame_outcome", "flag"],
              "R7": ["visibility_share", "cluster", "qtype"], "R8": ["recall", "inn_ok", "maker_ok", "indication_ok", "family_confusion", "hallucination"],
              "R9": ["uptake", "churn_advice", "anti_frame_outcome", "harm_flag"]}
CODE_LABELS = {"WE ARE ABSENT": "We are absent from the answer", "LEAK TO A COMPETITOR": "Leak to a competitor", "NO CLEAR WINNER": "No clear winner",
               "PATIENT RETAINED": "Patient retained", "REACH OK": "Reach OK", "ANSWERED CORRECTLY": "Answered correctly", "COMPETITOR WITHIN LABEL": "Competitor within label",
               "LOW REACH ON HIGH DEMAND": "Low reach on high demand", "WE LOSE THIS DUEL": "We lose this duel", "LISTED BUT NOT CHOSEN": "Listed but not chosen",
               "INCOMPLETE / OMISSION": "Incomplete / omission", "MYTH DEFENDED": "Myth defended", "FREE TERRITORY": "Free territory", "MESSAGE NOT DELIVERED": "Message not delivered",
               "WE WIN THIS DUEL": "We win this duel", "MESSAGE DELIVERED": "Message delivered", "DANGEROUS LABEL ERROR": "Dangerous label error", "MESSAGE DILUTED": "Message diluted",
               "COMPETITOR OFF-LABEL LIFT": "Competitor off-label lift", "AI STEERS OUR PATIENT AWAY": "AI steers our patient away", "CONTESTED / SPLIT": "Contested / split",
               "AI AMPLIFIES A HARMFUL MYTH": "AI amplifies a harmful myth", "FAMILY CONFUSION": "Family confusion", "MODEL ON AN OLD LABEL": "Model on an old label",
               "MESSAGE CREDITED TO CLASS/RIVAL": "Message credited to class / rival", "ENTITY KNOWN WELL": "Entity known well"}


def L(name):
    return json.load(open(C.METRICS_DIR / name, encoding="utf-8"))


def _n(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else (float(x) if isinstance(x, float) else x)


def main() -> int:
    cfg = C.load_configs()
    export = json.load(open(C.RAW_CORPUS.parent / "citere_points_full.json", encoding="utf-8"))
    corpus = C.load_raw_corpus()
    dash = json.load(open(C.METRICS_DIR / "dashboard.json", encoding="utf-8"))
    dash_bytes = open(C.METRICS_DIR / "dashboard.json", "rb").read()
    pri, cit, lab = L("prioritization_summary.json"), L("citations_summary.json"), L("label_flag_summary.json")
    ac_reg = json.load(open(C.REGISTRY_DIR / "action_center_tasks.json", encoding="utf-8"))
    lab_reg = json.load(open(C.REGISTRY_DIR / "label_findings_registry.json", encoding="utf-8"))
    groups_csv = pd.read_csv(C.METRICS_DIR / "prioritization_groups.csv")
    vis_bp = pd.read_csv(C.METRICS_DIR / "visibility_by_prompt.csv")
    a = C.load_answers(); c = C.load_citations()
    a["comps_present"] = a["comps_present"].map(lambda x: list(x) if x is not None else [])
    a["key"] = a["pid"] + "|" + a["run"]; c["key"] = c["pid"] + "|" + c["run"]
    live_c = c[(~c["is_artifact"]) & (~c["dedup"]) & (~c["excluded"]) & (c["owner"] != "noise")].copy()
    live_c["group"] = live_c["owner"].map(lambda o: "competitor" if o.startswith("competitor:") else o)

    # ---- join export ↔ corpus ------------------------------------------------
    ex = {"{}|{}".format(p["pid"], p["run"]): p for p in export["points"]}
    co = {"{}|{}".format(p["pid"], p["run"]): p for p in corpus["prompts"]}
    unmatched = sorted(set(ex) ^ set(co))
    label_mismatch = []
    for k, p in ex.items():
        cp = co.get(k)
        if not cp: continue
        for ef, cv in [("zone", cp["zone"]), ("topic", cp["intent"]["topic"]), ("subtopic", cp["intent"]["subtopic"]), ("query_type", cp["intent"]["query_type"]), ("patient_stage", cp["intent"]["patient_stage"]), ("question", cp["text"])]:
            if (p.get(ef) or None) != (cv or None):
                label_mismatch.append({"key": k, "field": ef, "export": p.get(ef), "corpus": cv})

    # ---- groups: reuse step-6 assignment (recompute the same mapping deterministically) -----
    pr = a.drop_duplicates(["pid", "run"]).copy()
    pr["group_raw"] = [C.topic_group(t, s_, z)[0] for t, s_, z in zip(pr["topic"], pr["subtopic"], pr["zone"])]
    sizes = pr.groupby("group_raw").size(); min_n = int(cfg["thresholds"]["min_group_prompts"]); target = {}
    for topic, gt in pr.groupby("topic"):
        raw_ids = sorted(gt["group_raw"].unique(), key=lambda g: (-int(sizes[g]), g))
        big = [g for g in raw_ids if sizes[g] >= min_n]; dest = big[0] if big else "{} × small".format(topic)
        for g in raw_ids: target[g] = g if g in big else dest
    pr["group_id"] = pr["group_raw"].map(target)
    key_group = dict(zip(pr["pid"] + "|" + pr["run"], pr["group_id"]))
    assert set(key_group.values()) == set(groups_csv["group_id"]), "group ids differ from step 6"
    bucket = {}
    for r in pri["recommendations"]: bucket[r["group_id"]] = "recommendation"
    for r in pri["label_recommendations"]: bucket[r["group_id"]] = "label"
    for h in pri["healthy_groups"]: bucket[h["group_id"]] = "healthy"
    for h in pri["below_gap_floor"]: bucket[h["group_id"]] = "below_floor"
    prio_by_group = {}
    for r in pri["recommendations"] + pri["label_recommendations"]:
        prio_by_group[r["group_id"]] = max(prio_by_group.get(r["group_id"], 0), r["priority"])
    fcs = {h["group_id"]: h["failure_code_share"] for h in pri["healthy_groups"]}
    non_failure = set(cfg["thresholds"].get("non_failure_codes") or [])

    # ---- points -----------------------------------------------------------------
    fam_of = dict(zip(a["model"], a["model_family"]))
    points, groups_pids = {}, defaultdict(list)
    for k, cp in co.items():
        p = ex[k]; g = a[a["key"] == k]; used = g[~g["excluded"]]
        sc = g["scores_json"].map(json.loads)
        fam_rows = []
        for f, gf in used.groupby("model_family"):
            fam_rows.append({"model_family": f, "answers": int(len(gf)), "we_present": int(gf["we_present"].sum()),
                             "position": _n(gf["we_pos"].dropna().astype(float).mean()) if gf["we_pos"].notna().any() else None,
                             "brand_sentiment": _n(gf["brand_sentiment"].mean()) if gf["brand_sentiment"].notna().any() else None,
                             "answer_sentiment": _n(gf["answer_sentiment"].mean()) if gf["answer_sentiment"].notna().any() else None})
        comps = Counter(b for l in used["comps_present"] for b in l)
        cc = live_c[live_c["key"] == k]
        dom = cc.groupby("domain").agg(n=("url", "size"), owner=("owner", lambda s_: s_.value_counts().idxmax()), subtype=("subtype", lambda s_: s_.dropna().value_counts().idxmax() if s_.notna().any() else None)).reset_index().sort_values(["n", "domain"], ascending=[False, True]).head(10)
        runf = RUN_FIELDS.get(cp["run"], [])
        run_specific = {f: Counter(str(s_.get(f, "")) for s_ in sc) for f in runf}
        run_specific = {f: dict(v) for f, v in run_specific.items()}
        code = cp["code"]
        points[k] = {
            "pid": cp["pid"], "run": cp["run"], "class": g["class"].iloc[0], "zone": cp["zone"], "topic": cp["intent"]["topic"], "subtopic": cp["intent"]["subtopic"],
            "query_type": cp["intent"]["query_type"], "patient_stage": cp["intent"]["patient_stage"], "question": cp["text"], "group_id": key_group[k],
            "sev": cp["diagnosis"]["sev"], "code": code, "code_label": CODE_LABELS.get(code, code.title()), "cause": p["cause"], "point_rank_score": p["priority"],
            "metrics": {"answers": int(len(g)), "answers_excluded": int(g["excluded"].sum()),
                        # bottom-up like the pipeline: repeats -> model version -> family -> point (equal weights) — identical to visibility_by_prompt.csv
                        "we_present_share": _n(used.groupby(["model_family", "model"])["we_present"].mean().groupby(level=0).mean().mean()) if len(used) else None,
                        "avg_position": _n(used.dropna(subset=["we_pos"]).assign(we_pos=lambda d: d["we_pos"].astype(float)).groupby(["model_family", "model"])["we_pos"].mean().groupby(level=0).mean().mean()) if used["we_pos"].notna().any() else None,
                        "we_present_share_pooled": _n(used["we_present"].mean()) if len(used) else None,
                        "aggregation_note": "we_present_share / avg_position are repeats→version→family→point means (pipeline convention); *_pooled is the raw share over answers",
                        "inn_only_share": _n(used["inn_only"].mean()) if len(used) else None, "by_model": fam_rows,
                        "competitors_present": dict(sorted(comps.items())),
                        "citations": {"total": int(len(cc)), **{o: int((cc["group"] == o).sum()) for o in ["owned", "earned", "institutional", "competitor", "adversarial"]},
                                      "top_domains": [{"domain": r.domain, "owner": r.owner, "subtype": r.subtype, "n": int(r.n)} for r in dom.itertuples()]},
                        "run_specific": run_specific},
            "demand": {"topic_demand": cp["topic_traffic"]["demand"], "lo": cp["topic_traffic"]["lo"], "hi": cp["topic_traffic"]["hi"], "basis": cp["topic_traffic"]["basis"]},
            "demand_extra": {"prompt_share": p["demand"].get("prompt_share"), "ai_native": p["demand"].get("ai_native"), "source": "platform_export"},
            "diagnosis_text": p["diagnosis"], "evidence_lines": (p.get("evidence_measured") or []) + (p.get("evidence_search") or []),
            "serp": p.get("serp"), "inventory": p.get("inventory"),
            "fixes": [dict(card, audience=TRACK_AUDIENCE.get(card.get("type"), "client"), platform_execution=card.get("execution")) for card in (p.get("fixes") or [])],
            "answers_ref": "answers_b64.js#" + k,
        }
        groups_pids[key_group[k]].append((p["priority"], k))

    # ---- groups ------------------------------------------------------------------------
    groups = []
    for r in groups_csv.itertuples():
        gid = r.group_id; pids = [k for _, k in sorted(groups_pids[gid], key=lambda t: (-t[0], t[1]))]
        causes = Counter(points[k]["cause"]["code"] for k in pids); dc, dn = causes.most_common(1)[0]
        codes = Counter(points[k]["code"] for k in pids)
        groups.append({"group_id": gid, "topic": r.topic if isinstance(r.topic, str) else "", "subtopic": r.subtopic if isinstance(r.subtopic, str) else "", "zone": r.zone if isinstance(r.zone, str) else "",
                       "n_prompts": int(r.n_prompts), "demand": _n(r.demand), "lo": _n(r.lo), "hi": _n(r.hi), "gap": _n(r.gap), "gap_by_run": json.loads(r.gap_by_run), "gap_bad": _n(r.gap_bad),
                       "dominant_code": r.top_code, "dominant_code_label": CODE_LABELS.get(r.top_code, r.top_code), "dominant_cause": {"code": dc, "share": round(dn / len(pids), 4)},
                       "priority": prio_by_group.get(gid), "bucket": bucket.get(gid, "unbucketed"),
                       "failure_code_share": fcs.get(gid, round(sum(n for cd, n in codes.items() if cd not in non_failure) / len(pids), 4)),
                       "lever": {"earned": _n(r.lever_earned), "owned": _n(r.lever_owned), "ugc": _n(r.lever_ugc), "comp_owned": _n(r.lever_comp_owned), "institutional_share": _n(r.institutional_share)},
                       "pids": pids})

    # ---- campaigns / citere / label findings / sources ------------------------------
    def refs_for(task, owners):
        out = []
        for k in groups_pids and [kk for _, kk in groups_pids[task["group_id"]]]:
            for i, card in enumerate(points[k]["fixes"]):
                if card["audience"] == "client" and CARD_TO_OWNER.get(card["type"], set()) & owners:
                    out.append({"pid_run": k, "fix_idx": i})
        return out
    campaigns = [dict(t, fix_card_refs=refs_for(t, {t["owner"]} if t["owner"] != "label" else {"label"})) for t in ac_reg["tasks"]]
    held = [dict(t, fix_card_refs=refs_for(t, {"label"})) for t in ac_reg.get("label_tasks_awaiting_signoff", [])]
    track_by_group = defaultdict(list)
    for k, pt in points.items():
        for i, card in enumerate(pt["fixes"]):
            if card["audience"] == "citere": track_by_group[pt["group_id"]].append({"pid_run": k, "fix_idx": i})
    citere_tasks = {"registry_tasks": ac_reg.get("citere_tasks", []), "track_cards_by_group": dict(sorted(track_by_group.items()))}
    r4 = a[a["run"] == "R4"].copy(); r4s = r4["scores_json"].map(json.loads); r4["target"] = r4s.map(lambda s_: s_.get("target"))
    label_findings = [dict(f, pids=sorted(set(r4[(r4["target"] == f["target"]) & (r4["model"] == f["surface"]) & (~r4["excluded"])]["key"]))) for f in lab_reg["findings"]]
    dom_pids = live_c.groupby("domain")["key"].agg(lambda s_: sorted(set(s_)))
    top200 = live_c["domain"].value_counts().head(200).index
    sources = dict(cit, domain_pids={d: dom_pids[d] for d in top200})

    data = {"meta": dict(dash["meta"], platform_export_generated=export["meta"].get("generated"), points_joined=len(points), points_unmatched=unmatched,
                         label_mismatches=len(label_mismatch), ans_store="ui/answers_b64.js (gzip+base64, keys pid|run)"),
            "dashboard": dash, "groups": groups, "points": points, "campaigns": campaigns, "label_tasks_awaiting_signoff": held, "citere_tasks": citere_tasks,
            "label_findings": label_findings, "sources": sources, "map": "unchanged — the neural map keeps its own data block",
            "code_labels": CODE_LABELS, "display_rule": "code = what happened (bold title); cause = why (grey sub-line with confidence) — never two equal labels"}

    # ---- checks (§3) ------------------------------------------------------------------
    checks = []
    def ck(name, ok, detail): checks.append((name, bool(ok), detail))
    ck("1. 1,424 points joined; points_unmatched empty", len(points) == 1424 and not unmatched, "joined={}, unmatched={}".format(len(points), unmatched[:5]))
    all_pids = [k for gr in groups for k in gr["pids"]]
    ck("2. every groups[].pids exists in points; every point has exactly one group_id", all(k in points for k in all_pids) and len(all_pids) == len(set(all_pids)) == len(points) and all(pt["group_id"] for pt in points.values()),
       "pids listed={}, unique={}, points={}".format(len(all_pids), len(set(all_pids)), len(points)))
    bad_ref = [ref for cmp in campaigns + held for ref in cmp["fix_card_refs"] if ref["pid_run"] not in points or ref["fix_idx"] >= len(points[ref["pid_run"]]["fixes"])]
    track_client = sum(1 for pt in points.values() for card in pt["fixes"] if card["type"] == "TRACK" and card["audience"] == "client")
    ck("3. every campaign fix_card_refs resolve; no TRACK card carries audience client", not bad_ref and track_client == 0, "bad refs={}, TRACK-as-client={}".format(len(bad_ref), track_client))
    ck("4. sum of groups[].n_prompts over all buckets = 1,424", sum(gr["n_prompts"] for gr in groups) == 1424, "sum={} buckets={}".format(sum(gr["n_prompts"] for gr in groups), dict(Counter(gr["bucket"] for gr in groups))))
    ck("5. dashboard block byte-identical to dashboard.json", json.dumps(data["dashboard"], indent=2, ensure_ascii=False).encode("utf-8") == dash_bytes, "re-serialised with the step-8 settings and compared byte-for-byte")
    ck("6. export topic/subtopic/zone vs corpus mismatch count (>0 WARN, >50 STOP)", len(label_mismatch) <= 50, "mismatches={} {}".format(len(label_mismatch), "PASS" if not label_mismatch else "WARN"))
    vb = vis_bp[vis_bp["run"] == "R1"].sort_values("pid").reset_index(drop=True)
    sample = vb.sample(n=20, random_state=C.SEED)
    # visibility_by_prompt.vis is the mean over families of prompt×model means; the point metric is the raw share over answers.
    # Identity holds when every family has equal repeats; compare the family-weighted value to the CSV instead of the raw share.
    diffs = []
    for r in sample.itertuples():
        k = "{}|R1".format(r.pid); v = points[k]["metrics"]["we_present_share"]
        if abs(v - r.vis) > 1e-9: diffs.append((k, round(v, 6), round(r.vis, 6)))
        pa, pb = points[k]["metrics"]["avg_position"], r.avg_pos
        if not ((pa is None and pd.isna(pb)) or (pa is not None and not pd.isna(pb) and abs(pa - pb) < 1e-9)): diffs.append((k, "avg_position", pa, pb))
    ck("7. spot check 20 random R1 points: we_present_share (and avg_position) identical to visibility_by_prompt.csv", not diffs, "20 points, tolerance 1e-9; mismatches={}".format(diffs[:3]))
    lines = ["# platform_data checks — cycle 1", ""] + ["- {} **{}** — {}".format("PASS" if ok else "FAIL", n, d) for n, ok, d in checks]
    (C.METRICS_DIR / "platform_data_checks.md").write_text("\n".join(lines) + "\n", encoding="utf-8"); print("\n".join(lines))
    if any(not ok for _, ok, _ in checks):
        print("\nFAILED — platform_data.json not written"); return 2
    out = C.METRICS_DIR / "platform_data.json"
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    nclient = sum(1 for pt in points.values() for card in pt["fixes"] if card["audience"] == "client"); ntrack = sum(1 for pt in points.values() for card in pt["fixes"] if card["audience"] == "citere")
    print("\nplatform_data.json written: {:,} bytes | fix cards client {} / citere {} | campaigns {} with {} refs | held label tasks {}".format(
        out.stat().st_size, nclient, ntrack, len(campaigns), sum(len(cm["fix_card_refs"]) for cm in campaigns), len(held)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
