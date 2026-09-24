"""Standalone task layer — reads data/metrics/cycle_01/platform_data.json only.

Writes tasks/task_types.md, tasks/tasks.json, tasks/tasks.md. Touches nothing in src/ or ui/.
Deterministic: every sort carries a stable tiebreak, JSON is written with sorted separators.
"""
import json, re, collections, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "metrics" / "cycle_01" / "platform_data.json"
OUT = ROOT / "tasks"
MIN_TASK_USD_MO = 5000

# ---------------------------------------------------------------- taxonomy
TYPES = {
 "T2":  dict(name="Expand an existing owned page", weeks=6, owner="Digital + Medical", lane="A",
             deliverable="An existing brand page is extended into a full answer for one patient intent, to the citability spec."),
 "T3":  dict(name="Citability rewrite of a losing page", weeks=6, owner="Digital + Medical", lane="A",
             deliverable="A page of ours that is already cited but loses the answer is audited and rewritten against the pages that win it."),
 "T4":  dict(name="Publish a new owned evidence page", weeks=6, owner="Digital + Medical", lane="A",
             deliverable="A new MLR-compatible citable page for an intent we own nothing on."),
 "T5":  dict(name="Listings, directory & reference-web data", weeks=12, owner="Digital + Medical", lane="A",
             deliverable="Our brand data is correct and present in the directories, drug-listing services and reference sites these answers cite."),
 "T6":  dict(name="Third-party placement (commercial & editorial)", weeks=12, owner="Digital + PR", lane="A",
             deliverable="The brand enters the commercial and editorial pages that actually answer the question."),
 "T10": dict(name="Hostile source response", weeks=12, owner="Legal + PR", lane="A",
             deliverable="One litigation-linked domain is handled end to end: legal decision first, then PR displacement with authoritative content.",
             tracks=["legal decision", "PR displacement"]),
 "T7":  dict(name="Label-clarity content", weeks=6, owner="Medical + Digital", lane="B",
             deliverable="Content carrying the exact prescribing-information citation the models misread."),
 "T8":  dict(name="Medical/Regulatory escalation & off-label dossier", weeks=6, owner="Medical / Regulatory", lane="B",
             deliverable="A dossier of affected questions plus the regulatory decision on whether content may be built."),
 "T9":  dict(name="Provider error reports", weeks=6, owner="Citere + Medical", lane="B",
             deliverable="Structured error reports filed with the model vendors, citing the prescribing information."),
 "T12": dict(name="Executive decision (commercial / channel floor)", weeks=2, owner="Commercial / CMO", lane="C",
             deliverable="A decision, not content: accept the channel floor or fix the commercial program."),
 "T1":  dict(name="Monitor & verify position", weeks=None, owner="Citere", lane="P",
             deliverable="Standing monitoring of the sources feeding a held position, with drift alerts."),
}
RULES = [
 ("T1",  r"^(Keep this position: monitor|Track this point's leak rate)"),
 ("T2",  r"^Expand our existing page"),
 ("T3",  r"^Audit and rewrite the cited-but-losing"),
 ("T4",  r"^(Create or rewrite an owned page|Publish an MLR-compatible|Occupy the empty|Create a citable owned page|Publish counter-framing content)"),
 ("T5",  r"^(Get our current data into|Served by the standing B10|Update our entries in the drug-listing|Reference-web hygiene)"),
 ("T6",  r"^(Secure presence in the reachable|Enter the brand-carrying commercial|Pitch updated)"),
 ("T7",  r"^Draft label-clarity content"),
 ("T8",  r"^(If this misreading recurs|Regulatory decision first|Compile a compliance dossier)"),
 ("T9",  r"^File structured error reports"),
 ("T10", r"^(Legal decision: official response|Displace )"),
 ("T12", r"^(Commercial reality check|CMO decision|Channel floor|Hold: the evidence is mixed)"),
]
RX = [(t, re.compile(p)) for t, p in RULES]
# primary pick: fewest weeks first, then owned page -> listings -> third-party -> hostile
PRIMARY_ORDER = {"T12": (2, 0), "T2": (6, 1), "T3": (6, 2), "T4": (6, 3), "T5": (12, 4), "T6": (12, 5), "T10": (12, 6)}

URL_RE = re.compile(r"https?://[^\s,;)]+")
DOM_RE = re.compile(r"\b((?:[a-z0-9][a-z0-9-]*\.)+[a-z]{2,})\b")


def classify(action):
    for t, r in RX:
        if r.match(action):
            return t
    return None


def pages_for(t, action, point):
    if t == "T2":
        return URL_RE.findall(action)[:1]
    if t in ("T3", "T5", "T6", "T10"):
        tail = action.split(":", 1)[-1] if ":" in action else action
        doms = [d for d in DOM_RE.findall(tail) if not d.endswith(".com.") ]
        if t == "T3":
            m = re.search(r"cited-but-losing page on ([^\s]+)", action)
            return [m.group(1)] if m else doms[:1]
        return doms[:3]
    return []


def main():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    P, MT = d["points"], d["money_totals"]
    applicable = collections.defaultdict(set)
    fix_of = collections.defaultdict(dict)
    for k, p in P.items():
        for c in (p.get("fixes") or []):
            t = classify(c["action"])
            if t:
                applicable[k].add(t)
                fix_of[k].setdefault(t, c["action"])
    api = sorted(k for k in P if P[k]["money"]["panel"] == "api" and not P[k]["money"]["pf"])
    primary, orphan = {}, []
    for k in api:
        cand = [t for t in applicable[k] if t in PRIMARY_ORDER]
        if not cand:
            orphan.append(k); continue
        primary[k] = min(cand, key=lambda t: PRIMARY_ORDER[t])
    return d, P, MT, api, applicable, fix_of, primary, orphan



# ---------------------------------------------------------------- task assembly
def slug(s, n=44):
    s = re.sub(r"https?://(www\.)?", "", s or "")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n] or "x"


def build(d, P, MT, api, applicable, fix_of, primary, orphan):
    money = lambda k: P[k]["money"]
    tasks = []

    def group_key(t, k):
        p = P[k]
        g = p.get("subtopic") or p.get("topic") or p.get("zone") or "(general)"
        pg = ""
        if t in ("T2", "T3", "T6", "T10"):
            pp = pages_for(t, fix_of[k].get(t, ""), p)
            pg = pp[0] if pp else ""
        return (g, pg)

    buckets = collections.defaultdict(list)
    for k in api:
        if k in primary:
            buckets[(primary[k],) + group_key(primary[k], k)].append(k)
    # orphans: held positions and regulatory-blocked points — no content task can move them
    for k in orphan:
        t = "T8" if "T8" in applicable[k] and "T1" not in applicable[k] else "T1"
        buckets[(t, "held positions" if t == "T1" else "regulatory hold", "")].append(k)

    # merge thin buckets into one "other" per type
    merged = collections.defaultdict(list)
    for key, ks in buckets.items():
        mid = sum(money(k)["usd"][1] for k in ks)
        merged[key if mid >= MIN_TASK_USD_MO or key[0] in ("T1", "T8") else (key[0], "other", "")].extend(ks)

    for (t, g, pg), ks in merged.items():
        ks = sorted(ks, key=lambda k: (-money(k)["usd"][1], k))
        info = TYPES[t]
        lane = "C" if t in ("T12", "T1", "T8") else info["lane"]
        f = sum(money(k)["usd"][0] for k in ks); m = sum(money(k)["usd"][1] for k in ks)
        by = collections.Counter()
        for k in ks:
            for b, v in (money(k).get("by_comp") or {}).items():
                by[b] += (v or [0, 0])[1]
        pages = []
        for k in ks:
            for x in pages_for(t, fix_of[k].get(t, ""), P[k]):
                if x not in pages:
                    pages.append(x)
        if pg and pg in pages:
            pages = [pg] + [x for x in pages if x != pg]
        also = sorted({x for k in ks for x in applicable[k]} - {t, "T1"}, key=lambda x: PRIMARY_ORDER.get(x, (99, 99)))
        wk = info["weeks"]
        tasks.append(dict(
            id="{}-{}-{}".format(lane, t, slug(pg or g)),
            lane=lane, type=t, type_name=info["name"],
            title=title_for(t, g, pg, len(ks)),
            owner=info["owner"], weeks=wk,
            usd_yr=[f * 12, m * 12], usd_per_week=round(m * 12 / wk) if wk else None,
            demand_mo=sum(money(k)["pt_demand_eff"] for k in ks),
            points=dict(count=len(ks), pids=[k for k in ks[:40]]), _all_pids=ks,
            questions=[P[k]["question"][:180] for k in ks[:3]],
            pages=pages[:6],
            competitors_leaking=[{"brand": b, "usd_mo": v} for b, v in by.most_common(3) if v],
            cause_codes=[c for c, _ in collections.Counter(P[k]["cause"]["code"] for k in ks).most_common(4)],
            also_addresses=also,
            evidence_refs=dict(answers=[P[k]["answers_ref"] for k in ks[:3]],
                               serp=sum(1 for k in ks if P[k].get("serp")),
                               inventory=sum(1 for k in ks if P[k].get("inventory")))))

    # lane B — label & regulatory, no money in the ranking
    bb = collections.defaultdict(list)
    for k, ts in applicable.items():
        for t in ("T7", "T8", "T9"):
            if t in ts:
                bb[(t, P[k].get("topic") or P[k].get("zone") or "(general)")].append(k)
    for (t, g), ks in bb.items():
        ks = sorted(ks, key=lambda k: ({"bad": 0, "warn": 1, "good": 2}.get(P[k]["sev"], 3), k))
        info = TYPES[t]
        web = [k for k in ks if money(k)["panel"] == "web"]
        tasks.append(dict(
            id="B-{}-{}".format(t, slug(g)), lane="B", type=t, type_name=info["name"],
            title=title_for(t, g, "", len(ks)), owner=info["owner"], weeks=info["weeks"],
            usd_yr=[0, 0], usd_per_week=None,
            web_usd_yr_info=[sum(money(k)["usd"][0] for k in web) * 12, sum(money(k)["usd"][1] for k in web) * 12],
            severity=dict(bad=sum(1 for k in ks if P[k]["sev"] == "bad"), warn=sum(1 for k in ks if P[k]["sev"] == "warn")),
            demand_mo=sum(money(k)["pt_demand_eff"] for k in ks),
            points=dict(count=len(ks), pids=[k for k in ks[:40]]), _all_pids=ks,
            questions=[P[k]["question"][:180] for k in ks[:3]],
            pages=[], competitors_leaking=[],
            cause_codes=[c for c, _ in collections.Counter(P[k]["cause"]["code"] for k in ks).most_common(4)],
            also_addresses=[], evidence_refs=dict(answers=[P[k]["answers_ref"] for k in ks[:3]],
                                                  serp=sum(1 for k in ks if P[k].get("serp")),
                                                  inventory=sum(1 for k in ks if P[k].get("inventory")))))
    return tasks


def title_for(t, g, pg, n):
    if t == "T2":  return "Expand {} into a full answer for “{}” ({} questions)".format(pg or "our page", g, n)
    if t == "T3":  return "Rewrite the cited-but-losing page on {} for “{}” ({} questions)".format(pg or "our domain", g, n)
    if t == "T4":  return "Publish a citable owned page for “{}” ({} questions)".format(g, n)
    if t == "T5":  return "Correct our listing data on {} for “{}” ({} questions)".format(pg or "the cited directories", g, n)
    if t == "T6":  return "Get the brand onto {} for “{}” ({} questions)".format(pg or "the cited commercial pages", g, n)
    if t == "T10": return "Handle {}: legal decision, then PR displacement (“{}”, {} questions)".format(pg or "the litigation sources", g, n)
    if t == "T7":  return "Draft label-clarity content for “{}” ({} questions)".format(g, n)
    if t == "T8":  return "Regulatory dossier and decision for “{}” ({} questions)".format(g, n)
    if t == "T9":  return "File provider error reports for “{}” ({} questions)".format(g, n)
    if t == "T12": return "Decision: accept the floor or fix the program for “{}” ({} questions)".format(g, n)
    if t == "T1":  return "Held positions — monitoring only, no content action ({} questions)".format(n)
    return g


# ---------------------------------------------------------------- rendering
def usd(v):
    v = round(v or 0)
    if v >= 1e6: x = v / 1e6; return "${}M".format("{:.1f}".format(x) if x < 10 else int(round(x)))
    if v >= 1000: return "${}K".format(int(round(v / 1000)))
    return "${}".format(v)


def rng(a):
    f, m = round(a[0] or 0), round(a[1] or 0)
    u = 1e6 if max(f, m) >= 1e6 else (1000 if max(f, m) >= 1000 else 1)
    s = "M" if u == 1e6 else ("K" if u == 1000 else "")
    one = lambda v: ("{:.1f}".format(v / u) if u == 1e6 and v / u < 10 else str(int(round(v / u))))
    return "${}–{}{}".format(one(f), one(m), s)


def write_types():
    L = ["# Task types — standalone task layer v1", "",
         "Eleven repeatable units of work. One owner, one deliverable, one speed class each.",
         "Weeks to result: decision 2 · weeks 6 · months 12 · cycles 24 · continuous = standing program.", "",
         "| # | type | deliverable | owner | weeks | lane |", "|---|---|---|---|---|---|"]
    for t in ["T2","T3","T4","T5","T6","T10","T7","T8","T9","T12","T1"]:
        i = TYPES[t]
        L.append("| {} | {} | {} | {} | {} | {} |".format(
            t, i["name"], i["deliverable"], i["owner"], i["weeks"] if i["weeks"] else "program", i["lane"]))
    L += ["", "`T10 Hostile source response` runs two tracks in order: **legal decision** (cease-and-desist / public",
          "statement / ignore) and then **PR displacement** with authoritative content and earned coverage.", "",
          "## Causes and evidence per type", "",
          "| # | cause codes it answers | evidence available in the data |", "|---|---|---|"]
    EV = {
     "T2": ("COMP-CONTENT, SOURCE-PREF, SOURCE-LEAK, UNCLAIMED", "our page URL from inventory, cited domains, SERP rank, sample answers, $ and demand"),
     "T3": ("SYNTH", "our cited domain, the winning domains, SERP rank, sample answers, $ and demand"),
     "T4": ("SOURCE-LEAK, SOURCE-PREF, COMP-CONTENT, UNCLAIMED", "subtopic, cited domains, SERP gap, inventory verdict (none/partial), $ and demand"),
     "T5": ("SOURCE-PREF, INSTITUTIONAL, NOT-CHOSEN, KNOW", "the exact directory domains cited, SERP occupiers, $ and demand"),
     "T6": ("COMP-CONTENT, COMMERCIAL-GAP, NOT-CHOSEN", "the commercial domains cited, competitor split, $ and demand"),
     "T10": ("HOSTILE", "the litigation domains cited, affected questions, sample answers, $ and demand"),
     "T7": ("LABEL-GAP", "subtopic and the label section; no cited domains (R4/R5 answers rarely cite) — evidence is the answer text"),
     "T8": ("COMP-OFFLABEL, LABEL-GAP", "subtopic, affected questions, sample answers; cited domains present on only 8% of points"),
     "T9": ("LABEL-GAP", "subtopic, sample answers, the PI citation; no cited domains"),
     "T12": ("INSTITUTIONAL, SYNTH, COMP-CONTENT, SOURCE-PREF", "cited institutional domains, channel split, $ and demand — shown to justify NOT spending"),
     "T1": ("WORKING, SOURCE-LEAK", "the source set feeding the held answer, drift baseline"),
    }
    for t in ["T2","T3","T4","T5","T6","T10","T7","T8","T9","T12","T1"]:
        L.append("| {} | {} | {} |".format(t, EV[t][0], EV[t][1]))
    (OUT / "task_types.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_md(tasks, MT, P, api):
    A = sorted([t for t in tasks if t["lane"] == "A"], key=lambda t: (-t["usd_per_week"], -t["demand_mo"], t["id"]))
    B = sorted([t for t in tasks if t["lane"] == "B"], key=lambda t: (-t["severity"]["bad"], -t["points"]["count"], t["id"]))
    C = sorted([t for t in tasks if t["lane"] == "C"], key=lambda t: (-t["usd_yr"][1], t["id"]))
    tot = [MT["api_usd_mo"][0] * 12, MT["api_usd_mo"][1] * 12]
    sa = [sum(t["usd_yr"][i] for t in A) for i in (0, 1)]
    sc = [sum(t["usd_yr"][i] for t in C) for i in (0, 1)]
    L = ["# Revenue at risk — the task plan", "",
         "Cycle 1 · Ozempic · US · API surfaces (R1–R3, R6–R9), portfolio questions excluded.",
         "All money is a floor–mid range, (Google proxy, US · estimate), and is **at risk**, not lost.", "",
         "| | /yr |", "|---|---|",
         "| **Total at risk** | **{}** |".format(rng(tot)),
         "| Addressable by the tasks below (lane A) | {} |".format(rng(sa)),
         "| At risk but not recoverable by content (lane C) | {} |".format(rng(sc)),
         "| Label & regulatory risk (lane B) | no $ — ranked by severity, web-panel money shown as info only |", "",
         "## 2 / 4 / 6 month plan", "",
         "Cumulative money **addressed** if lane A is worked in priority order. Addressed means the task that owns",
         "that money is done — not that the money returns.", "",
         "| by | tasks | cumulative /yr | share of total |", "|---|---|---|---|"]
    for mon, wk in ((2, 8), (4, 16), (6, 24)):
        sel = [t for t in A if t["weeks"] <= wk]
        s = [sum(t["usd_yr"][i] for t in sel) for i in (0, 1)]
        L.append("| month {} (≤{} weeks) | {} | {} | {:.0f}–{:.0f}% |".format(
            mon, wk, len(sel), rng(s), s[0] / tot[0] * 100, s[1] / tot[1] * 100))
    L += ["", "## Lane A — Revenue", "",
          "| # | task | owner | wks | $/yr | $/week | demand/mo | pts | top competitor |", "|---|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(A, 1):
        cl = t["competitors_leaking"]
        L.append("| {} | {} | {} | {} | {} | {} | {:,} | {} | {} |".format(
            i, t["title"], t["owner"], t["weeks"], rng(t["usd_yr"]), usd(t["usd_per_week"]),
            t["demand_mo"], t["points"]["count"], cl[0]["brand"] if cl else "—"))
    L += ["", "## Lane B — Label & regulatory", "",
          "Ranked by severity, never by money. The money column is the web panel (R4/R5) and is **never added** to lane A.", "",
          "| # | task | owner | wks | bad | warn | pts | web $/yr (info) |", "|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(B, 1):
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            i, t["title"], t["owner"], t["weeks"], t["severity"]["bad"], t["severity"]["warn"],
            t["points"]["count"], rng(t["web_usd_yr_info"])))
    L += ["", "## Lane C — Decisions", "",
          "**{} /yr at risk but not recoverable by content.** These need a decision, not a page.".format(rng(sc)), "",
          "| # | task | owner | wks | $/yr | pts |", "|---|---|---|---|---|---|"]
    for i, t in enumerate(C, 1):
        L.append("| {} | {} | {} | {} | {} | {} |".format(
            i, t["title"], t["owner"], t["weeks"] or "program", rng(t["usd_yr"]), t["points"]["count"]))
    prog = [t for t in C if t["type"] == "T1"]
    L += ["", "## Citere program — monitoring scope (not ranked)", ""]
    for t in prog:
        L.append("- {} — {} questions, {} /yr sitting on held positions, watched for drift.".format(
            t["title"], t["points"]["count"], rng(t["usd_yr"])))
    L += ["", "## Appendix — task detail", ""]
    for t in A + B + C:
        L += ["### {} · {}".format(t["id"], t["title"]), "",
              "- **Type** {} ({}) · **owner** {} · **{} weeks**".format(t["type"], t["type_name"], t["owner"], t["weeks"] or "program"),
              "- **Money** {} /yr{}".format(rng(t["usd_yr"]), " · {}/week".format(usd(t["usd_per_week"])) if t["usd_per_week"] else ""),
              "- **Demand** {:,}/mo · **points** {}".format(t["demand_mo"], t["points"]["count"]),
              "- **Causes** {}".format(", ".join(t["cause_codes"]) or "—"),
              "- **Pages / domains** {}".format(", ".join(t["pages"]) or "—"),
              "- **Competitors taking these answers** {}".format(
                  ", ".join("{} {}".format(c["brand"], usd(c["usd_mo"] * 12)) for c in t["competitors_leaking"]) or "—"),
              "- **Also addresses** {}".format(", ".join(t["also_addresses"]) or "—"),
              "- **Sample questions**"]
        L += ["  - {}".format(q) for q in t["questions"]]
        L += ["- **Evidence** answers: {} · serp on {} points · inventory on {} points".format(
            ", ".join(t["evidence_refs"]["answers"]) or "—", t["evidence_refs"]["serp"], t["evidence_refs"]["inventory"]), ""]
    (OUT / "tasks.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return A, B, C


def run():
    d, P, MT, api, applicable, fix_of, primary, orphan = main()
    tasks = build(d, P, MT, api, applicable, fix_of, primary, orphan)
    write_types()
    A, B, C = write_md(tasks, MT, P, api)
    order = {"A": 0, "B": 1, "C": 2}
    tasks_sorted = A + B + C
    (OUT / "tasks.json").write_text(json.dumps(
        {"meta": {"source": "data/metrics/cycle_01/platform_data.json",
                  "api_usd_mo": MT["api_usd_mo"], "generated_by": "tasks/build_tasks.py"},
         "tasks": [{k: v for k, v in t.items() if k != "_all_pids"} for t in tasks_sorted]},
        ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    return d, P, MT, api, applicable, primary, orphan, tasks_sorted, A, B, C


if __name__ == "__main__":
    d, P, MT, api, applicable, primary, orphan, T, A, B, C = run()
    tot = [MT["api_usd_mo"][i] * 12 for i in (0, 1)]
    sa = [sum(t["usd_yr"][i] for t in A) for i in (0, 1)]
    sc = [sum(t["usd_yr"][i] for t in C) for i in (0, 1)]
    print("tasks: {} total | A {} | B {} | C {}".format(len(T), len(A), len(B), len(C)))
    print("by type:", dict(collections.Counter(t["type"] for t in T).most_common()))
    print("lane A  {:>14,} / {:>14,}".format(*sa))
    print("lane C  {:>14,} / {:>14,}".format(*sc))
    print("A+C     {:>14,} / {:>14,}".format(sa[0]+sc[0], sa[1]+sc[1]))
    print("api x12 {:>14,} / {:>14,}".format(*tot))
    print("EXACT:", [sa[i]+sc[i] == tot[i] for i in (0, 1)])
    seen = collections.Counter()
    for t in A + C:
        for k in t["_all_pids"]:
            seen[k] += 1
    print("api points covered once:", sum(1 for k in api if seen[k] == 1), "of", len(api),
          "| duplicated:", sum(1 for k in api if seen[k] > 1), "| missing:", sum(1 for k in api if seen[k] == 0))
    bad = [t["id"] for t in A if not t["pages"] and t["type"] not in ("T4", "T8", "T9")]
    print("lane A tasks with no page/domain (outside T4/T8/T9):", len(bad), bad[:5])
