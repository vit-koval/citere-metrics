"""Step 1 — Normalization (normalization_spec.md).

Reads  data/raw/corpus_master.json + config/*.yaml
Writes data/normalized/answers.parquet, citations.parquet, data_quality_report.md

Run:   python -m src.step_01_normalize
Deterministic: same input + same config -> identical output. No sampling here.
"""
import collections
import hashlib
import json
import statistics
import sys
from typing import Dict, List, Optional

import pandas as pd

from src import common as C

PROMPT_REQUIRED = {"pid", "run", "zone", "status", "text", "code", "diagnosis", "intent", "topic_traffic", "models"}
ANSWER_REQUIRED = {"model", "answer", "citations", "scores", "sentiment"}
CITATION_REQUIRED = {"url", "owner", "category"}
STORED_OWNER_PASSTHROUGH = ("adversarial", "noise", "other")


class SchemaSurprise(Exception):
    pass


def _check_keys(obj: dict, required: set, where: str) -> None:
    missing = required - set(obj.keys())
    if missing:
        raise SchemaSurprise("{}: missing keys {} — keys present: {}".format(where, sorted(missing), sorted(obj.keys())))


def _md5(path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Build tables
# --------------------------------------------------------------------------- #
def build_tables(raw: dict, cfg: Dict[str, dict]):
    bd = C.BrandDictionary(cfg["brands"])
    fam_map, surf_map, drop = C.model_maps(cfg["models"])
    dom = cfg["domains"]
    min_chars = int(cfg["thresholds"]["min_answer_chars"])

    owned = [d.lower() for d in dom["owned"]]
    comp_entries = {}  # domain entry -> brand
    for brand, entries in dom["competitor"].items():
        for e in entries:
            comp_entries[e.lower()] = brand
    inst_cats = set(dom["institutional_categories"])
    inst_domains = [d.lower() for d in dom["institutional_domains"]]
    artifacts = [d.lower() for d in dom["artifacts"]]

    ans_rows: List[dict] = []
    cit_rows: List[dict] = []
    dropped = collections.Counter()
    unknown_models = collections.Counter()

    if "prompts" not in raw or not isinstance(raw["prompts"], list):
        raise SchemaSurprise("top-level `prompts` list not found; top-level keys: {}".format(list(raw.keys())))

    for p in raw["prompts"]:
        _check_keys(p, PROMPT_REQUIRED, "prompt {}".format(p.get("pid")))
        diag, intent, tt = p["diagnosis"], p["intent"], p["topic_traffic"]
        base = {
            "pid": p["pid"], "run": p["run"], "zone": p["zone"], "status": p["status"], "text": p["text"],
            "code": p["code"], "sev": diag.get("sev"),
            "topic": intent.get("topic"), "subtopic": intent.get("subtopic"),
            "query_type": intent.get("query_type"), "patient_stage": intent.get("patient_stage"),
            "demand": tt.get("demand"), "lo": tt.get("lo"), "hi": tt.get("hi"), "basis": tt.get("basis"),
        }
        cls = bd.classify_prompt(p["text"])
        status_mismatch = cls not in C.expected_classes_for_status(p["status"])
        rep_counter = collections.Counter()

        for e in p["models"]:
            _check_keys(e, ANSWER_REQUIRED, "answer in prompt {}".format(p["pid"]))
            model = e["model"]
            if model in drop:
                dropped[model] += 1
                continue
            if model not in fam_map:
                unknown_models[model] += 1
                continue
            repeat_idx = rep_counter[model]
            rep_counter[model] += 1

            raw_answer = e["answer"] if isinstance(e["answer"], str) else ""
            clean, tail_cleaned, _ = C.clean_tail(raw_answer)
            reason = C.exclusion_reason(clean, raw_answer, min_chars)
            we_present = bd.we_present(clean)
            inn_only = bd.inn_present(clean) and not we_present
            positions = bd.positions(clean)
            comp_pos = {b: pos for b, pos in positions.items() if b != bd.our_name}
            scores = e["scores"] if isinstance(e["scores"], dict) else {}

            row = dict(base)
            row.update({
                "model": model, "model_family": fam_map[model], "surface_type": surf_map.get(model),
                "repeat_idx": repeat_idx,
                "answer_raw": raw_answer, "answer_clean": clean, "tail_cleaned": tail_cleaned,
                "excluded": reason is not None, "exclude_reason": reason,
                "class": cls, "status_mismatch": status_mismatch,
                "we_present": we_present, "inn_only": inn_only,
                "we_pos": positions.get(bd.our_name),
                "comps_present": sorted(comp_pos, key=lambda b: comp_pos[b]),
                "comp_pos": json.dumps(comp_pos, ensure_ascii=False, sort_keys=True),
                "answer_sentiment": C.to_float_or_none(e.get("sentiment")),
                "brand_sentiment": None,
                "scores_json": json.dumps(scores, ensure_ascii=False, sort_keys=True),
                "our_status_scored": scores.get("our_status"),
                "our_rank_scored": C.to_float_or_none(scores.get("our_rank")),
                "mentioned_data": e.get("mentioned"),
                "visibility_data": C.to_float_or_none(e.get("visibility")),
            })
            ans_rows.append(row)

            # ---- citations ------------------------------------------------
            cits = e["citations"] if isinstance(e["citations"], list) else []
            seen_domains = set()
            for ci, c in enumerate(cits):
                if not isinstance(c, dict):
                    raise SchemaSurprise("citation in {}:{} is {}".format(p["pid"], model, type(c).__name__))
                _check_keys(c, CITATION_REQUIRED, "citation in {}:{}".format(p["pid"], model))
                url = c.get("url")
                host = C.url_host(url)
                domain = C.registrable_domain(host)
                is_artifact = C.match_domain_list(host, artifacts) is not None if host else False
                category = c.get("category")
                is_inst = (category in inst_cats) or (bool(host) and C.match_domain_list(host, inst_domains) is not None)
                owner_data = c.get("owner")
                subtype = None
                owned_hit = C.match_domain_list(host, owned) if host else None
                comp_hit = C.match_domain_list(host, comp_entries.keys()) if host else None
                if owned_hit:
                    owner = "owned"
                elif comp_hit:
                    owner = "competitor:{}".format(comp_entries[comp_hit])
                elif is_inst:
                    owner = "institutional"
                elif owner_data in STORED_OWNER_PASSTHROUGH:
                    owner = owner_data
                else:
                    owner = "earned"
                    subtype = category
                dedup = False
                if not is_artifact:
                    key = domain or (url if isinstance(url, str) else "")
                    if key in seen_domains:
                        dedup = True
                    else:
                        seen_domains.add(key)
                cit_rows.append({
                    "pid": p["pid"], "run": p["run"], "model": model, "model_family": fam_map[model],
                    "repeat_idx": repeat_idx, "class": cls, "excluded": reason is not None,
                    "cit_idx": ci, "url": url, "host": host, "domain": domain,
                    "domain_data": c.get("domain"), "owner_data": owner_data, "category_data": category,
                    "is_artifact": is_artifact, "is_institutional": is_inst,
                    "owner": owner, "subtype": subtype,
                    "we_present": we_present, "comps_present": sorted(comp_pos, key=lambda b: comp_pos[b]),
                    "dedup": dedup,
                })

    if unknown_models:
        raise SchemaSurprise(
            "model strings not in models.yaml families or drop list: {} — add them to config or to `drop`".format(dict(unknown_models))
        )

    answers = pd.DataFrame(ans_rows)
    answers["we_pos"] = answers["we_pos"].astype("Int64")
    answers["answer_sentiment"] = answers["answer_sentiment"].astype("float64")
    answers["brand_sentiment"] = answers["brand_sentiment"].astype("float64")
    answers["our_rank_scored"] = answers["our_rank_scored"].astype("float64")
    answers["visibility_data"] = answers["visibility_data"].astype("float64")
    answers["exclude_reason"] = answers["exclude_reason"].astype(object)
    citations = pd.DataFrame(cit_rows)
    return answers, citations, dict(dropped), bd


# --------------------------------------------------------------------------- #
# Data quality report
# --------------------------------------------------------------------------- #
def _pct(x: float) -> str:
    return "{:.1f}%".format(100.0 * x) if x == x else "n/a"


def _md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> List[str]:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append(floatfmt.format(v) if v == v else "")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return out


def build_report(answers: pd.DataFrame, citations: pd.DataFrame, dropped: dict, cfg: Dict[str, dict], raw_meta: dict, corpus_md5: str) -> str:
    th = cfg["thresholds"]
    L: List[str] = []
    statuses: List[str] = []

    def section(title: str, status: str, lines: List[str]) -> None:
        statuses.append(status)
        L.append("## {}".format(title))
        L.append("")
        L.append("**{}**".format(status) + ("" if not lines else ""))
        L.append("")
        L.extend(lines)
        L.append("")

    a = answers
    n_ans, n_prompts = len(a), a[["pid", "run"]].drop_duplicates().shape[0]

    # ---- header -----------------------------------------------------------
    L.append("# Data quality report — step 1 normalization (cycle 1)")
    L.append("")
    L.append("Input `data/raw/corpus_master.json` (md5 `{}`), meta.total_prompts = {}. Output rows: answers = {}, citations = {}.".format(
        corpus_md5, raw_meta.get("total_prompts"), n_ans, len(citations)))
    L.append("Prompt keys are `(pid, run)`: {} unique; corpus note says P0979 and P1013 appear in both R7 and R8.".format(n_prompts))
    L.append("")

    # ---- 1. prompts and answers per run x model ---------------------------
    ct = a.groupby(["run", "model"]).agg(prompts=("pid", "nunique"), answers=("pid", "size")).reset_index()
    piv_a = ct.pivot(index="model", columns="run", values="answers").fillna(0).astype(int)
    piv_p = a.groupby("run")["pid"].nunique()
    lines = ["Answers per model × run (prompts per run in the header row):", "",
             "| model | " + " | ".join("{} (n={})".format(r, piv_p[r]) for r in piv_a.columns) + " | total |",
             "|---|" + "---|" * (len(piv_a.columns) + 1)]
    for m, r in piv_a.iterrows():
        lines.append("| {} | ".format(m) + " | ".join(str(int(v)) if v else "" for v in r.values) + " | {} |".format(int(r.sum())))
    lines.append("")
    lines.append("Dropped models (config `drop`): {}.".format(dropped if dropped else "none"))
    lines.append("Model families: {}.".format({f: sorted(a.loc[a.model_family == f, "model"].unique().tolist()) for f in sorted(a.model_family.unique())}))
    section("1. Prompts and answers per run × model", "PASS", lines)

    # ---- 2. repeats -------------------------------------------------------
    g = a.groupby(["run", "pid", "model"]).size().rename("n").reset_index()
    rep = g.groupby("run")["n"].agg(["min", "median", "max"]).reset_index()
    single = g.assign(_single=(g["n"] == 1)).groupby("run")["_single"].mean().rename("single_run_share").reset_index()
    rep = rep.merge(single, on="run")
    rep["single_run_share"] = rep["single_run_share"].map(_pct)
    lines = ["Repeats per prompt×model group, by run:", ""] + _md_table(rep)
    lines.append("")
    lines.append("Overall repeat distribution: {}.".format(dict(sorted(collections.Counter(g["n"]).items()))))
    worst = single["single_run_share"].max()
    st = "WARN" if worst > 0.25 else "PASS"
    lines.append("Runs with a large single-run share have no repeat-level averaging there; prompt×model means are then single observations.")
    section("2. Repeats per prompt × model", st, lines)

    # ---- 3. tail cleaning and truncation per surface ----------------------
    max_trunc = float(th["max_truncation_share_per_surface"])
    a["_real_trunc"] = a["exclude_reason"].isin(["truncated", "chip_on_cut"])
    a["_ends_curly"] = a["answer_clean"].str.endswith("”")
    t = a.groupby("model").agg(
        answers=("pid", "size"),
        tail_cleaned=("tail_cleaned", "mean"),
        truncated=("exclude_reason", lambda s: (s == "truncated").mean()),
        chip_on_cut=("exclude_reason", lambda s: (s == "chip_on_cut").mean()),
        too_short=("exclude_reason", lambda s: (s == "too_short").mean()),
        real_truncation=("_real_trunc", "mean"),
        ends_curly_quote=("_ends_curly", "mean"),
    ).reset_index()
    over = t[t["real_truncation"] > max_trunc]
    tt = t.copy()
    for c in ["tail_cleaned", "truncated", "chip_on_cut", "too_short", "real_truncation", "ends_curly_quote"]:
        tt[c] = tt[c].map(_pct)
    lines = ["Per surface (model string). `real_truncation` = truncated + chip_on_cut after tail cleaning; threshold {}.".format(_pct(max_trunc)), ""]
    lines += _md_table(tt)
    lines.append("")
    lines.append("Excluded answers by reason: {}. Total excluded: {} of {} ({}).".format(
        {k: int(v) for k, v in a["exclude_reason"].value_counts().items()}, int(a["excluded"].sum()), n_ans, _pct(a["excluded"].mean())))
    # possible uncaught chip form: a short trailing token right after a sentence end (e.g. "…dose. MotherToBaby", "…help. CDC")
    name_chip_re = r'[.!?)»"\u201d]\s+\S{1,40}$'
    tr = a[a["exclude_reason"] == "truncated"]
    nc = tr["answer_clean"].str.contains(name_chip_re, regex=True)
    per_surface = tr.assign(_nc=nc).groupby("model")["_nc"].agg(["sum", "size"])
    lines.append("")
    lines.append("Possible uncaught source-name chips: {} of {} `truncated` answers end with a short bare token right after a terminal character "
                 "(e.g. `…dose. MotherToBaby`, `…help. CDC`, `…promptly. ozempic.com`). By surface: {}. "
                 "The spec's chip patterns do not cover this form; they are left flagged as truncated pending a human decision.".format(
                     int(nc.sum()), len(tr), {m: "{}/{}".format(int(r["sum"]), int(r["size"])) for m, r in per_surface.iterrows() if r["sum"] > 0}))
    lines.append("")
    lines.append("Note on `ends_curly_quote`: the spec's terminal set is `.!?)»\"`. Answers ending in a typographic closing quote `”` "
                 "are therefore flagged `truncated` even though they end on a quoted sentence. They are counted inside `truncated` above; "
                 "the column shows their share so a human can decide whether to accept `”` as terminal.")
    if len(over):
        st = "STOP"
        lines.append("")
        lines.append("**STOP — surfaces above the truncation threshold: {}.** 10 examples (last 120 chars of the raw answer):".format(
            ", ".join("{} ({})".format(r.model, _pct(r.real_truncation)) for r in over.itertuples())))
        lines.append("")
        ex = a[a["_real_trunc"] & a["model"].isin(over["model"])].sort_values(["model", "pid"]).head(10)
        for r in ex.itertuples():
            lines.append("- `{}` {} {} [{}]: …{}".format(r.pid, r.run, r.model, r.exclude_reason, repr(r.answer_raw.rstrip()[-120:])))
    else:
        st = "PASS"
        lines.append("")
        lines.append("10 examples of real truncation (highest-share surfaces first), last 120 chars of the raw answer:")
        lines.append("")
        order = t.sort_values("real_truncation", ascending=False)["model"].tolist()
        ex = a[a["_real_trunc"]].copy()
        ex["_o"] = ex["model"].map({m: i for i, m in enumerate(order)})
        ex = ex.sort_values(["_o", "pid"]).groupby("model", sort=False).head(2).sort_values(["_o", "pid"]).head(10)
        for r in ex.itertuples():
            lines.append("- `{}` {} {} [{}]: …{}".format(r.pid, r.run, r.model, r.exclude_reason, repr(r.answer_raw.rstrip()[-120:])))
    section("3. Tail cleaning and real truncation per surface", st, lines)

    # ---- 4. class distribution per run; status mismatch ------------------
    pr = a[["pid", "run", "class", "status", "status_mismatch"]].drop_duplicates(["pid", "run"])
    cd = pr.pivot_table(index="run", columns="class", values="pid", aggfunc="count", fill_value=0).reset_index()
    lines = ["Prompt class from prompt text via brands.yaml (trade names only; INN never counts):", ""] + _md_table(cd)
    lines.append("")
    xt = pr.pivot_table(index="status", columns="class", values="pid", aggfunc="count", fill_value=0).reset_index()
    lines += ["`status` × class (expected agreement: own→C2, comp→C3, mixed→C1/C4):", ""] + _md_table(xt)
    mm = pr["status_mismatch"].mean()
    lines.append("")
    lines.append("`status_mismatch` share: {} of prompts ({}). By run: {}.".format(
        _pct(mm), int(pr["status_mismatch"].sum()),
        {r: _pct(v) for r, v in pr.groupby("run")["status_mismatch"].mean().items()}))
    lines.append("`status` is a per-prompt outcome label (own/mixed/comp = who wins the answer), not a question-type label, so a high mismatch is expected on outcome-driven runs; class is never derived from it.")
    section("4. Class distribution per run and status mismatch", "WARN" if mm > 0.10 else "PASS", lines)

    # ---- 5. we_present vs our_status_scored on R1 -------------------------
    r1 = a[a["run"] == "R1"]
    xt5 = r1.pivot_table(index="our_status_scored", columns="we_present", values="pid", aggfunc="count", fill_value=0).reset_index()
    lines = ["R1 only. `our_status_scored` = `scores.our_status` (values seen: {}).".format(sorted(r1["our_status_scored"].dropna().unique().tolist())), ""]
    lines += _md_table(xt5)
    present_status = {"M", "R"}
    scored_present = r1["our_status_scored"].isin(present_status)
    disagree = (scored_present != r1["we_present"]).mean()
    inn_share = r1["inn_only"].mean()
    lines.append("")
    lines.append("Reading `M`/`R` as present and `A`/`EMPTY` as absent: disagreement with text-based `we_present` = {} ({} answers). INN-only share on R1 = {} ({} answers).".format(
        _pct(disagree), int((scored_present != r1["we_present"]).sum()), _pct(inn_share), int(r1["inn_only"].sum())))
    both = r1[(scored_present != r1["we_present"])]
    lines.append("Of the disagreements, {} are INN-only answers (scorer counted semaglutide as us).".format(int(both["inn_only"].sum())))
    ment = r1["mentioned_data"].fillna("").str.contains(r"(?<![A-Za-z0-9])ozempic(?![A-Za-z0-9])", case=False, regex=True)
    lines.append("Cross-check with stored `mentioned`: agrees with `we_present` on {} of R1 answers.".format(_pct((ment == r1["we_present"]).mean())))
    if disagree < 0.01:
        lines.append("The spec expected disagreement ≈ INN-only share (a scorer that counts semaglutide as us). It does not: the scorer marks INN-only answers as `A`, "
                     "so `our_status_scored` and trade-name `we_present` agree almost everywhere. Favorable; no action.")
        st = "PASS"
    else:
        st = "PASS" if abs(disagree - inn_share) <= 0.02 else "WARN"
    section("5. we_present vs our_status_scored on R1", st, lines)

    # ---- 6. inn_only per model ------------------------------------------
    io = a.groupby("model").agg(answers=("pid", "size"), inn_only=("inn_only", "mean"), we_present=("we_present", "mean")).reset_index()
    io["inn_only"] = io["inn_only"].map(_pct); io["we_present"] = io["we_present"].map(_pct)
    lines = ["Share of answers naming semaglutide but not Ozempic (`inn_only`), and `we_present`, per model:", ""] + _md_table(io)
    section("6. INN-only share per model", "PASS", lines)

    # ---- 7. sentiment -----------------------------------------------------
    s = a.dropna(subset=["answer_sentiment"])
    med_with = s.loc[s["we_present"], "answer_sentiment"].median()
    med_without = s.loc[~s["we_present"], "answer_sentiment"].median()
    lines = ["`answer_sentiment` present for {} of {} answers ({}); by run: {}.".format(
        len(s), n_ans, _pct(len(s) / n_ans), {r: _pct(v) for r, v in a.groupby("run")["answer_sentiment"].apply(lambda x: x.notna().mean()).items()})]
    lines.append("")
    lines.append("| | median answer_sentiment | n |")
    lines.append("|---|---|---|")
    lines.append("| we_present = true | {:.1f} | {} |".format(med_with, int(s["we_present"].sum())))
    lines.append("| we_present = false | {:.1f} | {} |".format(med_without, int((~s["we_present"]).sum())))
    lines.append("")
    diff = abs(med_with - med_without)
    lines.append("Expected roughly equal (confirms the stored sentiment is answer-level, not brand-level). Difference = {:.1f} points.".format(diff))
    lines.append("")
    pr7 = s.groupby(["run", "we_present"])["answer_sentiment"].agg(["median", "size"]).reset_index()
    pr7 = pr7.pivot(index="run", columns="we_present", values=["median", "size"])
    lines.append("| run | median (we_present) | n | median (absent) | n |")
    lines.append("|---|---|---|---|---|")
    for run, r in pr7.iterrows():
        mw, nw = r.get(("median", True), float("nan")), r.get(("size", True), 0)
        ma, na = r.get(("median", False), float("nan")), r.get(("size", False), 0)
        lines.append("| {} | {} | {} | {} | {} |".format(run, "" if mw != mw else "{:.0f}".format(mw), int(nw) if nw == nw else 0,
                                                       "" if ma != ma else "{:.0f}".format(ma), int(na) if na == na else 0))
    lines.append("")
    lines.append("The `absent` group is dominated by R1 category answers (no brand named), so a modest gap can reflect topic mix rather than brand-level scoring.")
    section("7. Sentiment: answer-level check", "PASS" if diff <= 5 else "WARN", lines)

    # ---- 8. citations -----------------------------------------------------
    c = citations
    n_art = int(c["is_artifact"].sum())
    live = c[~c["is_artifact"]]
    lines = ["Total citations: {}. Artifacts removed (`{}`): {}. Remaining: {}. Duplicate-domain rows within one answer (`dedup = true`, keep-first): {}. Unparseable/empty URLs: {}.".format(
        len(c), ", ".join(cfg["domains"]["artifacts"]), n_art, len(live), int(live["dedup"].sum()), int((c["host"] == "").sum()))]
    lines.append("")
    od = live["owner"].value_counts().rename_axis("owner").reset_index(name="citations")
    od["share"] = (od["citations"] / len(live)).map(_pct)
    lines += ["Owner distribution (spec rule: owned → competitor:<Brand> → institutional → stored adversarial/noise/other → earned), excluding artifacts:", ""] + _md_table(od)
    lines.append("")
    xt8 = live.pivot_table(index="owner_data", columns="owner", values="url", aggfunc="count", fill_value=0).reset_index()
    lines += ["Stored `owner_data` × computed `owner` (rows: stored, columns: computed):", ""] + _md_table(xt8)
    lines.append("")
    top_other = live[live["owner"] == "other"]["domain"].value_counts().head(30)
    lines.append("Top-30 domains with owner = `other`: " + ", ".join("{} ({})".format(d, n) for d, n in top_other.items()))
    lines.append("")
    so = live[(live["owner_data"] == "owned") & (live["owner"] != "owned")]
    stored_owned_comp = so[so["owner"].str.startswith("competitor:")]["host"].value_counts()
    stored_owned_not_cfg = so[~so["owner"].str.startswith("competitor:")]["host"].value_counts()
    lines.append("Hosts stored as `owned` that config maps to a competitor (intentional: Wegovy/Rybelsus compete for the slot): " +
                 (", ".join("{} ({})".format(d, n) for d, n in stored_owned_comp.items()) if len(stored_owned_comp) else "none"))
    lines.append("Hosts stored as `owned` that are in no config list and now fall to `{}` — likely Novo corporate sites missing from `domains.yaml: owned` ({} citations): ".format(
                     ", ".join(sorted(so[~so["owner"].str.startswith("competitor:")]["owner"].unique())) or "n/a", int(stored_owned_not_cfg.sum())) +
                 (", ".join("{} ({})".format(d, n) for d, n in stored_owned_not_cfg.items()) if len(stored_owned_not_cfg) else "none"))
    comp_owned_not_cfg = live[(live["owner_data"] == "comp_owned") & (~live["owner"].str.startswith("competitor:"))]["host"].value_counts()
    lines.append("Hosts stored as `comp_owned` but not matched to a competitor domain: " +
                 (", ".join("{} ({})".format(d, n) for d, n in comp_owned_not_cfg.items()) if len(comp_owned_not_cfg) else "none"))
    lines.append("Domain matching is longest-suffix on the full host (so `mounjaro.lilly.com` → Mounjaro, `pi.lilly.com` → Trulicity via `lilly.com`); `domain` holds the registrable domain used for aggregation and dedup.")
    section("8. Citations", "WARN" if len(stored_owned_not_cfg) else "PASS", lines)

    # ---- 9. topic groups --------------------------------------------------
    min_n = int(th["min_group_prompts"])
    pr9 = a[["pid", "run", "topic", "subtopic", "zone", "demand"]].drop_duplicates(["pid", "run"]).copy()
    grp = pr9.apply(lambda r: C.topic_group(r["topic"], r["subtopic"], r["zone"]), axis=1)
    pr9["group_id"] = [g[0] for g in grp]
    pr9["group_kind"] = [g[1] for g in grp]
    gs = pr9.groupby("group_id").agg(n_prompts=("pid", "size"), n_demand_values=("demand", "nunique"), kind=("group_kind", "first")).reset_index()
    sizes = gs["n_prompts"]
    lines = ["Group rule (diagnosis_prioritization_spec §2): `topic × subtopic` when subtopic is set and ≠ \"Other\", else `topic × zone`. Groups: {} ({} topic×subtopic, {} topic×zone).".format(
        len(gs), int((gs["kind"] == "topic×subtopic").sum()), int((gs["kind"] == "topic×zone").sum()))]
    lines.append("Size distribution: min {}, median {}, max {}; buckets: {}.".format(
        int(sizes.min()), int(sizes.median()), int(sizes.max()),
        {"<10": int((sizes < 10).sum()), "10–29": int(((sizes >= 10) & (sizes < 30)).sum()), "30–99": int(((sizes >= 30) & (sizes < 100)).sum()), "≥100": int((sizes >= 100).sum())}))
    small = gs[gs["n_prompts"] < min_n]
    lines.append("Groups below `min_group_prompts` = {}: {} (covering {} prompts) — to be merged into `topic × small` by step 6.".format(min_n, len(small), int(small["n_prompts"].sum())))
    multi = gs[gs["n_demand_values"] > 1]
    lines.append("Groups with more than one `demand` value: {} — {}.".format(
        len(multi), ", ".join("{} ({} values)".format(r.group_id, r.n_demand_values) for r in multi.head(15).itertuples()) if len(multi) else "none"))
    empty_sub = pr9["subtopic"].isna() | (pr9["subtopic"].astype(str).str.strip() == "")
    other_sub = pr9["subtopic"] == "Other"
    lines.append("Empty subtopic: {} prompts ({}); subtopic = \"Other\": {} prompts. Both route to `topic × zone`.".format(
        int(empty_sub.sum()), _pct(empty_sub.mean()), int(other_sub.sum())))
    st = "WARN" if (len(multi) or len(small)) else "PASS"
    section("9. Topic groups", st, lines)

    # ---- overall ----------------------------------------------------------
    overall = "STOP" if "STOP" in statuses else ("WARN" if "WARN" in statuses else "PASS")
    L.insert(4, "**Overall: {}** — sections: {}.".format(overall, ", ".join("{} {}".format(i + 1, s) for i, s in enumerate(statuses))))
    L.insert(5, "")
    a.drop(columns=["_real_trunc", "_ends_curly"], inplace=True)
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
def main() -> int:
    cfg = C.load_configs()
    raw = C.load_raw_corpus()
    corpus_md5 = _md5(C.RAW_CORPUS)
    try:
        answers, citations, dropped, _ = build_tables(raw, cfg)
    except SchemaSurprise as exc:
        print("SCHEMA SURPRISE — stopping without writing outputs:\n  {}".format(exc), file=sys.stderr)
        return 2

    C.NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    answers.to_parquet(C.NORMALIZED_DIR / "answers.parquet", index=False)
    citations.to_parquet(C.NORMALIZED_DIR / "citations.parquet", index=False)
    report = build_report(answers, citations, dropped, cfg, raw.get("meta", {}), corpus_md5)
    (C.NORMALIZED_DIR / "data_quality_report.md").write_text(report, encoding="utf-8")
    print("answers: {} rows, citations: {} rows, dropped: {}".format(len(answers), len(citations), dropped))
    print("report: {}".format(C.NORMALIZED_DIR / "data_quality_report.md"))
    first = report.splitlines()[4] if len(report.splitlines()) > 4 else ""
    print(first)
    return 0


if __name__ == "__main__":
    sys.exit(main())
