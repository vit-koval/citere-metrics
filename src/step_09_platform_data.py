"""Step 9 — platform_data.json (platform_data_spec.md).

All numbers come from the pipeline (metrics outputs, registries, normalized parquet, corpus). All prose, causes, fix cards,
SERP snapshots and inventory come from the platform export data/raw/citere_points_full.json. Nothing recomputed; no number
from the export is trusted except point_rank_score (= export priority), prompt_share and ai_native (labelled).
Checks (spec §3) must all pass, else the file is not written.
"""
import gzip, base64, hashlib, json, math, re, sys
from collections import Counter, defaultdict

import pandas as pd

from src import common as C

# Plain-language vocabulary for the Priorities screen. Labels only — every number stays as the pipeline produced it.
ZONE_PLAIN = {"LIVING ON THE DRUG": "daily life", "STARTING & SWITCHING": "starting or switching", "WEIGHT LOSS": "weight loss",
              "PRICE & ACCESS": "price and access", "SAFETY & CONTRAINDICATIONS": "safety", "BLOOD SUGAR & GLYCEMIC CONTROL": "blood sugar",
              "HEART & KIDNEY": "heart and kidney"}
CATEGORY_PLAIN = {"directory": "drug directories", "media": "health media", "health_media": "health media", "forum": "community forums",
                  "ugc": "community forums", "hospital": "hospital sites", "news": "news sites", "telehealth": "telehealth sites",
                  "advocacy": "advocacy sites", "payer": "insurer sites", "government": "government sites", "other": "third-party sites"}
OWNER_ACTION = {"owned": "make our own pages the answer", "ugc": "show up in community answers",
                "comp_owned": "counter competitor-owned pages", "label": "publish the missing label fact"}
OWNER_SOURCE = {"owned": "our own pages", "ugc": "community forums", "comp_owned": "competitor pages", "label": "label pages"}
CONF_PLAIN = {"high": "high", "med": "medium", "medium": "medium", "low": "low"}


def subject_phrase(topic, subtopic, zone):
    """`Side effects & tolerability` × `LIVING ON THE DRUG` -> `Side effects and daily life`."""
    lead = re.split(r"\s*[&,]\s*", (topic or "").strip())[0].strip()
    ctx = (subtopic or "").strip() or ZONE_PLAIN.get(zone, (zone or "").lower())
    ctx = ctx.replace(" & ", " and ")
    first = ctx.split(" ")[0]
    if ctx[:1].isupper() and not first.isupper():          # keep acronyms (PCOS, GI) as written
        ctx = ctx[:1].lower() + ctx[1:]
    if not lead:
        return ctx[:1].upper() + ctx[1:]
    return lead + (", " if " and " in ctx else " and ") + ctx


# Task type: the export's own `agent` field, grouped into plain names. The agent string stays on the card,
# so nothing here is invented — every key below appears verbatim in the export.
TASK_TYPE = {
    "H22": "Monitor & alert", "A2": "Rewrite page", "A2/A6": "Rewrite page", "A1/A7": "Create page / evidence",
    "B8/C12": "Fix listings & directories", "B10": "Fix listings & directories", "A1": "Draft label content",
    "F18/C12": "PR & outreach", "E16/E17": "Reference sites", "G20": "Provider error reports",
    "Task for the client's Commercial team": "Commercial decision",
    "Task for the client's Medical/Regulatory": "Medical / Regulatory",
    "Task for the client's Legal": "Legal",
    "Decision for the client": "CMO decision",
    "Task for Regulatory; A1 agent builds only after the go": "Regulatory go",
    "Task for the client's team": "Client team",
}


def task_type(agent):
    """Plain name for the export's `agent` string: the agent code before ' · ', else the human-task wording."""
    a = (agent or "").strip()
    head = a.split(" · ")[0].strip()
    if head in TASK_TYPE:
        return TASK_TYPE[head]
    for key, name in TASK_TYPE.items():
        if a.startswith(key):
            return name
    return "Other"


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



# --------------------------------------------------------------------------- #
# Revenue-at-risk layer (citere_revenue_at_risk_spec_v2 §3). Display only: nothing
# here feeds point_rank_score, group score, causes, fixes or any ordering.
# --------------------------------------------------------------------------- #
WEB_RUNS = ("R4", "R5")


def money_cell_key(cp):
    """(zone | "*", subtopic | topic) by demand.basis — the cell the export used for prompt_share."""
    tt = cp.get("topic_traffic") or {}
    it = cp.get("intent") or {}
    basis = tt.get("basis") or ""
    topic, sub = it.get("topic"), it.get("subtopic")
    if basis == "topic-google:zone\u00d7subtopic":
        return (cp.get("zone"), sub or topic)
    if basis == "topic-google:subtopic":
        return ("*", sub or topic)
    return ("*", topic)


def r7_volume(cp):
    """models[0].scores.volume — the R7 keyword volume stored on the prompt."""
    ms = cp.get("models") or []
    if not ms:
        return 0.0
    try:
        return float((ms[0].get("scores") or {}).get("volume"))
    except (TypeError, ValueError):
        return 0.0


def demand_correction(corpus):
    """dcf(cell) = max(1, r7vol / topic_demand) (§3.1). Returns (factor by cell, corrected rows)."""
    topic_demand, r7 = {}, defaultdict(float)
    for cp in corpus["prompts"]:
        key = money_cell_key(cp)
        topic_demand.setdefault(key, (cp.get("topic_traffic") or {}).get("demand") or 0)
        if cp["run"] == "R7":
            r7[key] += r7_volume(cp)
    factor, corrected = {}, []
    for key, dem in topic_demand.items():
        vol = r7.get(key, 0.0)
        f = max(1.0, vol / dem) if dem else 1.0
        factor[key] = f
        if f > 1:
            corrected.append({"cell": "{} / {}".format(key[0], key[1]), "topic_demand": dem,
                              "r7vol": int(round(vol)), "dcf": round(f, 4)})
    corrected.sort(key=lambda r: (-r["dcf"], r["cell"]))
    return factor, corrected


def point_money(cp, export_point, factor, bd, portfolio, comp_money, usd_per_search):
    """The per-point `money` block (§3.2). `usd` is None when pricing.yaml is absent."""
    models = cp.get("models") or []
    n = len(models)
    # gap is recomputed here, not taken from metrics.we_present_share — see the step report.
    our = sum(1 for m in models if bd.we_present(m.get("answer") or ""))
    gap = (1.0 - our / n) if n else 0.0
    named = set(bd.competitors_present(cp.get("text") or ""))
    pf = 1 if (named & portfolio) and not (named & comp_money) else 0
    f = factor.get(money_cell_key(cp), 1.0)
    pt_demand_eff = int(round((export_point["demand"].get("prompt_share") or 0) * f))
    if usd_per_search is None:
        usd = None
    elif pf:
        usd = [0, 0]
    else:
        usd = [int(round(pt_demand_eff * gap * usd_per_search["floor"])),
               int(round(pt_demand_eff * gap * usd_per_search["mid"]))]
    return {"pt_demand_eff": pt_demand_eff, "dc": 1 if f > 1 else 0, "gap": round(gap, 6),
            "pf": pf, "usd": usd, "panel": "web" if cp["run"] in WEB_RUNS else "api"}


def money_totals(points, corrected_cells, has_pricing):
    api = [0, 0]
    web = [0, 0]
    excluded = 0.0
    for pt in points.values():
        m = pt["money"]
        if m["pf"]:
            excluded += m["pt_demand_eff"] * m["gap"]
            continue
        if m["usd"] is None:
            continue
        bucket = api if m["panel"] == "api" else web
        bucket[0] += m["usd"][0]
        bucket[1] += m["usd"][1]
    return {"api_usd_mo": api if has_pricing else None, "web_usd_mo": web if has_pricing else None,
            "excluded_pf_pt_demand_mo": int(round(excluded)), "corrected_cells": corrected_cells}


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
    pricing_cfg = C.load_config("pricing") if (C.CONFIG_DIR / "pricing.yaml").exists() else None
    usd_per_search = (pricing_cfg or {}).get("usd_per_search") or None
    portfolio = set(cfg["brands"].get("portfolio") or [])
    comp_money = set(cfg["brands"]["competitors"]) - portfolio
    bd_money = C.BrandDictionary(cfg["brands"])
    dcf_by_cell, corrected_cells = demand_correction(corpus)
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
        ans_keys = cc.drop_duplicates(["model", "repeat_idx"])
        answers_with = {"any": int(len(ans_keys))}
        for _o in ["owned", "earned", "institutional", "competitor", "adversarial"]:
            answers_with[_o] = int(cc[cc["group"] == _o].drop_duplicates(["model", "repeat_idx"]).shape[0])
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
                        "answer_sentiment": _n(used["answer_sentiment"].mean()) if used["answer_sentiment"].notna().any() else None,
                        "brand_sentiment": _n(used["brand_sentiment"].mean()) if used["brand_sentiment"].notna().any() else None,
                        "competitors_present": dict(sorted(comps.items())),
                        "comp_present_answers": int((used["comps_present"].map(len) > 0).sum()),
                        "citations": {"total": int(len(cc)), **{o: int((cc["group"] == o).sum()) for o in ["owned", "earned", "institutional", "competitor", "adversarial"]},
                                      "answers_with": answers_with,
                                      "top_domains": [{"domain": r.domain, "owner": r.owner, "subtype": r.subtype, "n": int(r.n)} for r in dom.itertuples()]},
                        "run_specific": run_specific},
            "demand": {"topic_demand": cp["topic_traffic"]["demand"], "lo": cp["topic_traffic"]["lo"], "hi": cp["topic_traffic"]["hi"], "basis": cp["topic_traffic"]["basis"]},
            "demand_extra": {"prompt_share": p["demand"].get("prompt_share"), "ai_native": p["demand"].get("ai_native"), "source": "platform_export"},
            "money": point_money(cp, p, dcf_by_cell, bd_money, portfolio, comp_money, usd_per_search),
            "diagnosis_text": p["diagnosis"], "evidence_lines": (p.get("evidence_measured") or []) + (p.get("evidence_search") or []),
            "serp": p.get("serp"), "inventory": p.get("inventory"),
            # `execution` is the export's own AGENT / AGENT+APPROVE / HUMAN TASK — one field, not duplicated
            "fixes": [dict(card, audience=TRACK_AUDIENCE.get(card.get("type"), "client"), task_type=task_type(card.get("agent"))) for card in (p.get("fixes") or [])],
            "answers_ref": "answers.js#" + k,
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

    # ---- Priorities screen: plain-language headline, reach, distributions, sources (all carried, nothing recomputed) ----
    rows_by_owner = {}
    for r in pri["recommendations"] + pri["label_recommendations"]:
        rows_by_owner[(r["group_id"], r["owner"])] = r
    best_row = {}
    for r in pri["recommendations"] + pri["label_recommendations"]:
        cur = best_row.get(r["group_id"])
        if cur is None or r["score"] > cur["score"]:
            best_row[r["group_id"]] = r
    citere_groups = {r["group_id"] for r in pri.get("citere_rows", [])}
    live_c["_group"] = live_c["key"].map(key_group)
    dom_by_group = {}
    for gid, sub in live_c.groupby("_group"):
        agg = sub.groupby(["domain", "owner", "subtype"], dropna=False).agg(citations=("url", "size"), with_us=("we_present", "sum")).reset_index()
        agg = agg.sort_values(["citations", "domain"], ascending=[False, True]).head(8)
        dom_by_group[gid] = [{"domain": t.domain, "owner": t.owner, "subtype": "" if not isinstance(t.subtype, str) else t.subtype,
                              "citations": int(t.citations), "with_us": int(t.with_us)} for t in agg.itertuples()]
    for g in groups:
        gid = g["group_id"]; pts = [points[k] for k in g["pids"]]
        row = best_row.get(gid)
        def _dist(vals, labels):
            cnt = Counter(vals)
            return [{"code": c, "label": labels.get(c, c), "n": int(n), "share": round(n / len(pts), 4)} for c, n in cnt.most_common()]
        cause_labels = {}
        for pt in pts:
            cz = pt.get("cause") or {}
            if cz.get("code") and cz.get("label"):
                cause_labels.setdefault(cz["code"], cz["label"])
        g["code_distribution"] = _dist([pt["code"] for pt in pts], CODE_LABELS)
        g["cause_distribution"] = _dist([(pt.get("cause") or {}).get("code") for pt in pts], cause_labels)
        def _cause_block(sel):
            if not sel:
                return None
            cd, cn = Counter((pt.get("cause") or {}).get("code") for pt in sel).most_common(1)[0]
            same = [pt for pt in sel if ((pt.get("cause") or {}).get("code")) == cd]
            conf = Counter(((pt.get("cause") or {}).get("confidence") or "").lower() for pt in same).most_common(1)[0][0]
            return {"code": cd, "label": cause_labels.get(cd, cd), "n": len(same), "share": round(len(same) / len(sel), 4),
                    "confidence": CONF_PLAIN.get(conf, conf or None)}
        g["dominant_cause"] = dict(g["dominant_cause"], **{k: v for k, v in (_cause_block(pts) or {}).items() if k in ("label", "confidence")})
        g["failing_cause"] = _cause_block([pt for pt in pts if pt["code"] not in non_failure])
        g["top_domains"] = dom_by_group.get(gid, [])
        g["impact_reach"] = row["impact_reach"] if row else None
        g["top_owner"] = row["owner"] if row else None
        g["top_owner_lever"] = (row["why"].get("lever") if row else None)
        cat = (row["where"][0].get("category") if row and row.get("where") else None)
        src = OWNER_SOURCE.get(g["top_owner"]) or CATEGORY_PLAIN.get(cat, "third-party sites")
        g["source_label"] = src if g["top_owner"] else None
        g["action_label"] = OWNER_ACTION.get(g["top_owner"], "get cited on " + src) if g["top_owner"] else None
        subject = subject_phrase(g["topic"], g["subtopic"], g["zone"])
        g["subject_label"] = subject
        g["headline"] = subject + (" — " + g["action_label"] if g["action_label"] else "")
        g["owner_rows"] = [{"owner": o, "what": rw["what"], "who": rw["who"], "speed": rw["speed"], "score": rw["score"],
                            "lever": rw["why"].get("lever"), "impact_reach": rw["impact_reach"],
                            "top_domain": (rw["where"][0]["domain"] if rw.get("where") else None),
                            "source_label": (OWNER_SOURCE.get(o) or CATEGORY_PLAIN.get((rw["where"][0].get("category") if rw.get("where") else None), "third-party sites"))}
                           for (gg, o), rw in sorted(rows_by_owner.items(), key=lambda kv: -kv[1]["score"]) if gg == gid]
        g["_citere_only"] = gid in citere_groups

    # ---- campaigns / citere / label findings / sources ------------------------------
    def refs_for(task, owners):
        out = []
        for k in groups_pids and [kk for _, kk in groups_pids[task["group_id"]]]:
            for i, card in enumerate(points[k]["fixes"]):
                if card["audience"] == "client" and CARD_TO_OWNER.get(card["type"], set()) & owners:
                    out.append({"pid_run": k, "fix_idx": i})
        return out
    def _task_types(refs):
        seen = []
        for r in refs:
            tt = points[r["pid_run"]]["fixes"][r["fix_idx"]].get("task_type")
            if tt and tt not in seen: seen.append(tt)
        return sorted(seen)

    def _with_reach(t):
        rw = rows_by_owner.get((t["group_id"], t["owner"]))
        return dict(t, impact=dict(t["impact"], reach=(rw["impact_reach"] if rw else None)))
    campaigns = []
    for t in ac_reg["tasks"]:
        refs = refs_for(t, {t["owner"]} if t["owner"] != "label" else {"label"})
        campaigns.append(dict(_with_reach(t), fix_card_refs=refs, task_types=_task_types(refs)))
    held = []
    for t in ac_reg.get("label_tasks_awaiting_signoff", []):
        refs = refs_for(t, {"label"})
        held.append(dict(_with_reach(t), fix_card_refs=refs, task_types=_task_types(refs)))
    track_by_group = defaultdict(list)
    for k, pt in points.items():
        for i, card in enumerate(pt["fixes"]):
            if card["audience"] == "citere": track_by_group[pt["group_id"]].append({"pid_run": k, "fix_idx": i})
    citere_tasks = {"registry_tasks": ac_reg.get("citere_tasks", []), "track_cards_by_group": dict(sorted(track_by_group.items()))}
    # ---- derived rows: client fix cards in a group that already has tasks, but no task for their owner ----
    # Step 6 raises a label row only when a group has no citations at all (its `elif`), so label/medical fix cards on
    # points of ordinary recommendation groups had nowhere to attach. The export knows that work exists and the registry
    # does not, so the join layer raises the row here, held for sign-off like every other label row.
    OWNER_FOR_CARD = {"OWNED": "owned", "EARNED": "earned", "LABEL-MEDICAL": "label"}
    referenced = set()
    for t in campaigns + held:
        for r in t["fix_card_refs"]: referenced.add((r["pid_run"], r["fix_idx"]))
    have_owner = defaultdict(set)
    for t in campaigns + held: have_owner[t["group_id"]].add(t["owner"])
    orphan_by = defaultdict(list)
    for k, pt in points.items():
        for i, card in enumerate(pt["fixes"]):
            if card["audience"] != "client" or (k, i) in referenced: continue
            gid = pt["group_id"]
            if not have_owner.get(gid): continue                      # healthy / below-floor / Citere-only: no task by design
            if CARD_TO_OWNER.get(card["type"], set()) & have_owner[gid]: continue
            orphan_by[(gid, OWNER_FOR_CARD.get(card["type"], "label"))].append({"pid_run": k, "fix_idx": i})
    group_by_id = {g["group_id"]: g for g in groups}
    derived = []
    for (gid, owner), refs in sorted(orphan_by.items()):
        g = group_by_id[gid]
        cards = [points[r["pid_run"]]["fixes"][r["fix_idx"]] for r in refs]
        who = Counter(c.get("owner") for c in cards).most_common(1)[0][0]
        speed = Counter(c.get("speed") for c in cards).most_common(1)[0][0]
        tid = "d" + hashlib.md5((gid + "|" + owner).encode("utf-8")).hexdigest()[:11]
        derived.append({"task_id": tid, "group_id": gid, "group": {"topic": g["topic"], "subtopic": g["subtopic"], "zone": g["zone"]},
                        "owner": owner, "execution": "manual", "priority": g["priority"], "rank": None, "score": None,
                        "what": "{} {} fix card{} on this topic carry no task in the registry — raised here so the work is visible{}".format(
                            len(refs), owner, "" if len(refs) == 1 else "s", "; needs clinician sign-off" if owner == "label" else ""),
                        "who": who, "speed": speed,
                        "why": {"demand": g["demand"], "lo": g["lo"], "hi": g["hi"], "gap": g["gap"], "gap_by_run": g["gap_by_run"],
                                "n_prompts": g["n_prompts"], "dominant_run": max(g["gap_by_run"], key=g["gap_by_run"].get) if g["gap_by_run"] else None,
                                "lever": None, "institutional_share": g["lever"].get("institutional_share")},
                        "cause": [], "where": [],
                        "impact": {"ceiling_pp": None, "expected_pp": None, "basis": "not estimated — raised from the export, not scored by the pipeline",
                                   "n_groups": None, "demand": g["demand"], "lo": g["lo"], "hi": g["hi"],
                                   "demand_caption": "topic demand, Google, proxy", "reach": g.get("impact_reach")},
                        "is_label": owner == "label", "awaiting_label_signoff": owner == "label", "resolved_by_data": False,
                        "status": "open", "dismiss_reason": None, "cycle_opened": dash["meta"]["cycle"], "cycle_done": None,
                        "source": "derived in step 9: fix cards present in the export with no registry row for their owner",
                        "fix_card_refs": refs, "task_types": _task_types(refs)})
    held += [t for t in derived if t["is_label"]]
    campaigns += [t for t in derived if not t["is_label"]]

    camp_by_group = defaultdict(list); held_by_group = defaultdict(list)
    for t in campaigns:
        camp_by_group[t["group_id"]].append(t["task_id"])
    for t in held:
        held_by_group[t["group_id"]].append(t["task_id"])
    citere_by_group = defaultdict(list)
    for t in ac_reg.get("citere_tasks", []):
        citere_by_group[t["group_id"]].append(t.get("task_id"))
    min_gap = pri.get("min_gap")
    for g in groups:
        gid = g["group_id"]
        by_owner = {}
        for t in campaigns + held:
            if t["group_id"] == gid:
                by_owner[t["owner"]] = t
        for o in g["owner_rows"]:
            t = by_owner.get(o["owner"])
            o["task_id"] = t["task_id"] if t else None
            o["status"] = t["status"] if t else None
            o["execution"] = t["execution"] if t else None
            o["ceiling_pp"] = t["impact"]["ceiling_pp"] if t else None
            o["expected_pp"] = t["impact"]["expected_pp"] if t else None
            o["awaiting_label_signoff"] = bool(t.get("awaiting_label_signoff")) if t else False
        g["campaign_ids"] = camp_by_group.get(gid, [])
        g["held_task_ids"] = held_by_group.get(gid, [])
        g["citere_task_ids"] = citere_by_group.get(gid, [])
        if g["campaign_ids"]:
            g["no_campaign_reason"] = None
        elif g["held_task_ids"] or g["bucket"] == "label":
            g["no_campaign_reason"] = "No campaign yet — the label finding on this topic is held until a clinician signs it off."
        elif g.pop("_citere_only", False) or g["citere_task_ids"]:
            g["no_campaign_reason"] = "No client campaign — the rows on this topic are adversarial-source monitoring, kept with Citere."
        elif g["bucket"] == "healthy":
            g["no_campaign_reason"] = "No campaign — the dominant code on this topic is not a failure, so nothing was raised."
        elif g["bucket"] == "below_floor":
            g["no_campaign_reason"] = "No campaign — the gap is below the {:.0%} floor, treated as background noise.".format(min_gap or 0)
        else:
            g["no_campaign_reason"] = "No campaign raised for this group."
        g.pop("_citere_only", None)

    r4 = a[a["run"] == "R4"].copy(); r4s = r4["scores_json"].map(json.loads); r4["target"] = r4s.map(lambda s_: s_.get("target"))
    label_findings = [dict(f, pids=sorted(set(r4[(r4["target"] == f["target"]) & (r4["model"] == f["surface"]) & (~r4["excluded"])]["key"]))) for f in lab_reg["findings"]]
    dom_pids = live_c.groupby("domain")["key"].agg(lambda s_: sorted(set(s_)))
    top200 = live_c["domain"].value_counts().head(200).index
    sources = dict(cit, domain_pids={d: dom_pids[d] for d in top200})

    vis_s, ben_s, lab_s = L("visibility_summary.json"), L("benchmark_summary.json"), L("label_flag_summary.json")
    breakdowns = {"note": "carried verbatim from the step summaries: visibility/benchmarking on the R1 C1 headline scope, safety on R4",
                  "visibility_by_zone": vis_s["by_zone"], "visibility_by_topic_group": vis_s["by_topic_group"],
                  "benchmarking_by_zone": ben_s["by_zone"], "safety_by_target": lab_s["by_target"], "safety_unstable_cells": lab_s["unstable_cells_list"]}
    data = {"meta": dict(dash["meta"], platform_export_generated=export["meta"].get("generated"), points_joined=len(points), points_unmatched=unmatched,
                         competitors_found_in_data=list(cfg["brands"].get("competitors_found_in_data") or []),
                         competitors_found_in_data_note="entered the dictionary mid-cycle after showing up in answers; R1 and R2 were designed against the GLP-1 set",
                         label_mismatches=len(label_mismatch), ans_store="ui/answers.js (built by step 10 from the corpus: gzip+base64, keys pid|run, full texts)"),
            "dashboard": dash, "groups": groups, "points": points, "campaigns": campaigns, "label_tasks_awaiting_signoff": held, "citere_tasks": citere_tasks,
            "label_findings": label_findings, "sources": sources, "breakdowns": breakdowns, "map": "unchanged — the neural map keeps its own data block",
            "pricing": ({"floor": usd_per_search["floor"], "mid": usd_per_search["mid"],
                         "ad_spend_yr": pricing_cfg.get("benchmark_ad_spend_usd_yr"),
                         "sources": pricing_cfg.get("sources"), "market": pricing_cfg.get("market")}
                        if pricing_cfg else None),
            "money_totals": money_totals(points, len(corrected_cells), pricing_cfg is not None),
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
    ref2 = set()
    for t in campaigns + held:
        for r in t["fix_card_refs"]: ref2.add((r["pid_run"], r["fix_idx"]))
    orph = defaultdict(int)
    for k, pt in points.items():
        for i, card in enumerate(pt["fixes"]):
            if card["audience"] == "client" and (k, i) not in ref2:
                orph["IN A GROUP THAT HAS TASKS" if have_owner.get(pt["group_id"]) else group_by_id[pt["group_id"]]["bucket"] + " group, raises no task by design"] += 1
    ck("8. every client fix card is reachable from a task, except in groups that raise none by design",
       orph.get("IN A GROUP THAT HAS TASKS", 0) == 0,
       "orphans by reason: {} | derived rows raised: {} ({} label held, {} client)".format(
           dict(orph) or "none", len(derived), sum(1 for t in derived if t["is_label"]), sum(1 for t in derived if not t["is_label"])))
    ck("7. spot check 20 random R1 points: we_present_share (and avg_position) identical to visibility_by_prompt.csv", not diffs, "20 points, tolerance 1e-9; mismatches={}".format(diffs[:3]))
    print("\ndemand correction (§3.1): {} cells corrected".format(len(corrected_cells)))
    for r in corrected_cells:
        print("  {:<52} topic_demand {:>9,}  r7vol {:>9,}  dcf {:>7.2f}".format(r["cell"][:52], r["topic_demand"], r["r7vol"], r["dcf"]))
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
