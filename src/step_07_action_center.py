"""Step 7 — Action Center (action_center_spec.md).

Reads  data/metrics/cycle_01/prioritization_summary.json, data/registry/label_findings_registry.json, config/thresholds.yaml
Writes data/registry/action_center_tasks.json (merge by task_id, never overwrites status), data/metrics/cycle_01/action_center_queue.csv,
       action_center_summary.json, action_center_report.md

Computes nothing new: rows become tasks; execution auto/manual/citere; impact ceiling_pp = gap × lever × 100 (Label: gap × 100),
expected_pp = ceiling × closure_coefficients (basis: prior). Label tasks stay out of the queue and counters while their
findings in the label registry are pending (cycle 1: all pending).
"""
import hashlib
import json
import sys

import pandas as pd

from src import common as C

CYCLE = 1
EXEC_BY_OWNER = {"owned": "auto", "earned": "manual", "commerce": "manual", "ugc": "manual", "comp_owned": "manual", "label": "manual"}


def task_id(group_id: str, owner: str) -> str:
    return hashlib.sha1("{}|{}".format(group_id, owner).encode("utf-8")).hexdigest()[:12]


def main() -> int:
    cfg = C.load_configs()
    coef = {k: list(v) for k, v in cfg["thresholds"]["closure_coefficients"].items()}
    prio = json.load(open(C.METRICS_DIR / "prioritization_summary.json", encoding="utf-8"))
    lab_path = C.REGISTRY_DIR / "label_findings_registry.json"
    lab = json.load(open(lab_path, encoding="utf-8")) if lab_path.exists() else {"findings": []}
    pending = sum(1 for f in lab["findings"] if f.get("signoff_status") == "pending")
    confirmed = sum(1 for f in lab["findings"] if f.get("signoff_status") == "confirmed")
    label_gate_open = pending == 0 and confirmed > 0

    reg_path = C.REGISTRY_DIR / "action_center_tasks.json"
    reg = json.load(open(reg_path, encoding="utf-8")) if reg_path.exists() else {"tasks": [], "citere_tasks": [], "label_tasks_awaiting_signoff": []}
    by_id = {t["task_id"]: t for t in reg.get("tasks", []) + reg.get("citere_tasks", []) + reg.get("label_tasks_awaiting_signoff", [])}
    seen = set()

    def make(row, is_label):
        tid = task_id(row["group_id"], row["owner"]); seen.add(tid)
        owner = row["owner"]
        execution = "citere" if "citere" in (row.get("who") or "").lower() else EXEC_BY_OWNER.get(owner, "manual")
        gap, lever = row["why"]["gap"], row["why"].get("lever")
        ceiling = round(gap * 100, 2) if is_label else round(gap * (lever or 0) * 100, 2)
        k = coef.get(owner)
        expected = None if is_label or not k else [round(ceiling * k[0], 2), round(ceiling * k[1], 2)]
        computed = {"group_id": row["group_id"], "group": row["group"], "owner": owner, "execution": execution, "priority": row["priority"], "rank": row["rank"], "score": row["score"],
                    "what": row["what"], "who": row["who"], "speed": row["speed"], "why": row["why"], "cause": row["cause"], "where": row["where"], "examples": row["examples"],
                    "impact": {"ceiling_pp": ceiling, "expected_pp": expected, "basis": "prior", "n_groups": None, "demand": row["why"]["demand"], "lo": row["why"]["lo"], "hi": row["why"]["hi"],
                               "demand_caption": "topic demand, Google, proxy"},
                    "is_label": is_label, "awaiting_label_signoff": is_label and not label_gate_open, "resolved_by_data": False}
        if tid in by_id:
            t = by_id[tid]; t.update(computed)  # status / dismiss_reason / cycle fields untouched
        else:
            t = dict(task_id=tid, **computed, status="open", dismiss_reason=None, cycle_opened=CYCLE, cycle_done=None); by_id[tid] = t
        return t

    for r in prio["recommendations"]:
        make(r, False)
    for r in prio["label_recommendations"]:
        make(r, True)
    for tid, t in by_id.items():
        if tid not in seen:
            t["resolved_by_data"] = True
    all_tasks = sorted(by_id.values(), key=lambda t: (-t["score"]))
    client = [t for t in all_tasks if t["execution"] in ("auto", "manual") and not t["awaiting_label_signoff"]]
    citere = [t for t in all_tasks if t["execution"] == "citere" and not t["awaiting_label_signoff"]]
    held = [t for t in all_tasks if t["awaiting_label_signoff"]]
    open_c = [t for t in client if t["status"] == "open"]
    by_who = {}
    for t in open_c:
        by_who[t["who"]] = by_who.get(t["who"], 0) + 1
    counters = {"open_total": len(open_c), "open_auto": sum(1 for t in open_c if t["execution"] == "auto"), "open_manual": sum(1 for t in open_c if t["execution"] == "manual"),
                "in_progress": sum(1 for t in client if t["status"] == "in_progress"), "done_this_cycle": sum(1 for t in client if t["cycle_done"] == CYCLE),
                "dismissed_total": sum(1 for t in client if t["status"] == "dismissed"), "by_who": dict(sorted(by_who.items(), key=lambda kv: -kv[1])),
                "top3_open": [t["task_id"] for t in open_c[:3]], "citere_tasks": len(citere), "label_tasks_awaiting_signoff": len(held), "label_findings_pending": pending}
    registry = {"cycle_current": CYCLE, "brand": prio["brand"], "tasks": client, "citere_tasks": citere, "label_tasks_awaiting_signoff": held, "counters": counters,
                "closure_coefficients": coef, "coefficient_basis": "prior",
                "label_gate": "Label tasks enter the queue only when every finding in label_findings_registry.json has signoff_status != pending ({} pending, {} confirmed).".format(pending, confirmed)}
    C.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(registry, open(reg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump({"cycle": CYCLE, "counters": counters, "top3_open": [{k: t[k] for k in ("task_id", "group_id", "owner", "execution", "priority", "who", "score", "impact")} for t in open_c[:3]]},
              open(C.METRICS_DIR / "action_center_summary.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    order = {"open": 0, "in_progress": 1, "done": 2, "dismissed": 3}
    q = pd.DataFrame([{"task_id": t["task_id"], "priority": t["priority"], "execution": t["execution"], "who": t["who"], "status": t["status"], "topic": t["group"]["topic"], "subtopic": t["group"]["subtopic"], "zone": t["group"]["zone"],
                       "owner": t["owner"], "what": t["what"], "ceiling_pp": t["impact"]["ceiling_pp"], "expected_lo_pp": (t["impact"]["expected_pp"] or [None, None])[0], "expected_hi_pp": (t["impact"]["expected_pp"] or [None, None])[1],
                       "basis": t["impact"]["basis"], "demand": t["impact"]["demand"], "top_domain": t["where"][0]["domain"] if t["where"] else "", "cycle_opened": t["cycle_opened"], "cycle_done": t["cycle_done"], "score": t["score"], "_o": order[t["status"]]}
                      for t in client + citere]).sort_values(["_o", "score"], ascending=[True, False]).drop(columns=["_o"])
    q.to_csv(C.METRICS_DIR / "action_center_queue.csv", index=False)

    def fmt(t):
        i = t["impact"]; exp = "n/a" if i["expected_pp"] is None else "{:.0f}…{:.0f} pp".format(*i["expected_pp"])
        return "{} → {} · P{} · {} · {} — losing {:.0%} of topic prompts ({} dominant) · {} = {:.0%} of citations — Ceiling: {:.0f} pp · Expected: {} ({}) · Topic demand ~{:,.0f}/month (Google, proxy)".format(
            t["group_id"], t["owner"], t["priority"], t["execution"], t["who"], t["why"]["gap"], t["why"]["dominant_run"], t["owner"], t["why"]["lever"] or 0, i["ceiling_pp"], exp, i["basis"], i["demand"])
    L = ["# Action Center — cycle 1 (step 7)",
         "Counters (client tasks, execution auto/manual): open {} (auto {}, manual {}); in progress {}; done this cycle {}; dismissed {}. By who: {}.".format(
             counters["open_total"], counters["open_auto"], counters["open_manual"], counters["in_progress"], counters["done_this_cycle"], counters["dismissed_total"], ", ".join("{} {}".format(k, v) for k, v in by_who.items())),
         "Citere tasks (own monitoring / re-check, excluded from client counters): {}. Label / Medical tasks held out of the queue while their findings await clinician sign-off: {} ({} findings pending in label_findings_registry.json).".format(len(citere), len(held), pending),
         "Impact: ceiling_pp = gap × lever × 100; expected_pp = ceiling × closure coefficients (basis: prior — {}); Label rows have no expected_pp.".format(", ".join("{} {}–{}".format(k, v[0], v[1]) for k, v in coef.items())),
         "Top-3 open tasks:"] + ["{}. {}".format(i + 1, fmt(t)) for i, t in enumerate(open_c[:3])] + [
         "Registry: `data/registry/action_center_tasks.json` — {} client + {} citere + {} held label tasks; task_id = sha1(group_id|owner)[:12]; status/dismiss_reason/cycle fields are never overwritten by computation.".format(len(client), len(citere), len(held)),
         "Outputs: action_center_queue.csv ({} rows, open first then by score), action_center_summary.json.".format(len(q))]
    (C.METRICS_DIR / "action_center_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
