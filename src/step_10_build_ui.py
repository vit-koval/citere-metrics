"""Step 10 — build ui/index.html (ui_spec.md).

Inputs : ui/template.html, data/metrics/cycle_01/platform_data.json, ui/citere_cmo_master_screen.html (design source: style block verbatim),
         ui/evidence_base_legacy.html (map CSS, map view markup,
         map init function + the fix-engine helpers it calls, slimmed legacy DATA for the map only), normalized parquet + corpus
         (answer store).
Outputs: ui/index.html (platform_data inlined), ui/answers.js (full answer texts, gzip+base64, keyed pid|run, corpus order).
Deterministic: gzip mtime=0, no timestamps.
"""
import base64, collections, gzip, json, re, sys

import pandas as pd

from src import common as C

UI = C.ROOT / "ui"
OWNP_KEY = {"owned": "owned", "competitor": "comp_owned", "institutional": "government", "adversarial": "adversarial", "earned": "earned"}


def map_nodes(pd_data):
    """The Neural map's node list, built from platform_data.json — same field names the map's own code reads,
    so the visual code is unchanged and the map computes nothing. Keyed by (pid, run) and grouped by group_id."""
    groups = {g["group_id"]: g for g in pd_data["groups"]}
    nodes = []
    ans = oz_t = mn_t = 0
    for key, pt in pd_data["points"].items():
        m = pt["metrics"]; g = groups[pt["group_id"]]
        cz = pt.get("cause") or {}
        oz = sum(int(r["we_present"]) for r in m["by_model"])
        harm = (m.get("run_specific") or {}).get("harm_class") or {}
        crit = 1 if (pt["code"] == "DANGEROUS LABEL ERROR" or "DANGEROUS" in harm) else 0
        if pt["code"] == "FREE TERRITORY":
            st = "e"
        elif pt["sev"] == "good":
            st = "u"
        elif pt["sev"] == "bad":
            st = "t"
        else:
            st = "m"
        cards = [c for c in pt["fixes"] if c.get("audience") == "client"] or pt["fixes"]
        c0 = cards[0] if cards else {}
        act = c0.get("action") or "—"
        aw = m["citations"].get("answers_with") or {}
        dm = []
        for t in (m["citations"]["top_domains"] or [])[:4]:
            own = t.get("owner") or "other"
            key_own = "comp_owned" if own.startswith("competitor") else OWNP_KEY.get(own, "other")
            if own == "earned" and (t.get("subtype") or "") == "ugc":
                key_own = "ugc"
            dm.append([t["domain"], int(t["n"]), key_own])
        q = pt["question"]
        nodes.append({"p": pt["pid"], "t": (q[:110] + "\u2026") if len(q) > 110 else q, "s": st, "cr": crit,
                      "to": g["topic"], "su": (g["subtopic"] or g["zone"] or "(general)"), "gid": g["group_id"],
                      "rn": pt["run"], "qt": pt["query_type"], "sg": pt["patient_stage"],
                      "cz": cz.get("code"), "ch": cz.get("label") or cz.get("code"),
                      "sr": pt["code_label"], "sf": ("confidence " + cz["confidence"]) if cz.get("confidence") else "",
                      "oz": oz, "n": int(m["answers"]) - int(m["answers_excluded"]), "nx": int(m["answers_excluded"]),
                      "ot": int(m.get("comp_present_answers") or 0),
                      "vol": pt["demand_extra"].get("prompt_share") or 0, "tdm": pt["demand"]["topic_demand"],
                      "usd": pt["money"]["usd"], "pf": pt["money"]["pf"], "dc": pt["money"]["dc"],
                      "volx": pt["money"]["pt_demand_eff"], "gp": pt["money"]["gap"],
                      "db": pt["demand"].get("basis"), "ai": 1 if pt["demand_extra"].get("ai_native") else 0,
                      "se": m.get("answer_sentiment"),
                      "dg": [int(aw.get("any", 0)), int(aw.get("owned", 0)), int(aw.get("competitor", 0)),
                             int(aw.get("adversarial", 0)), int(aw.get("institutional", 0)), int(aw.get("earned", 0))],
                      "dm": dm,
                      "fx": (act[:170] + "\u2026") if len(act) > 170 else act, "ex": c0.get("platform_execution") or "AGENT"})
        ans += int(m["answers"]) - int(m["answers_excluded"]); oz_t += oz; mn_t += int((m.get("competitors_present") or {}).get("Mounjaro") or 0)
    # centre gauge denominator = scored answers, so it equals dashboard.visibility.named_any_scope_pct
    return {"points": nodes, "center": {"ans": ans, "oz": oz_t, "mn": mn_t, "pts": len(nodes)}}
ARTIFACT_TEXT_LIMIT = 16 * 1024 * 1024   # artifact publish ceiling per text file → answer store is split by run


def build_answer_store():
    a = C.load_answers(); c = C.load_citations(); corpus = C.load_raw_corpus()
    key = ["pid", "run", "model", "repeat_idx"]
    cit = {}
    for k, g in c[~c["is_artifact"]].groupby(key):
        cit[k] = [{"domain": d, "url": u, "owner": o} for d, u, o in zip(g["domain"], g["url"], g["owner"])]
    arow = a.set_index(key)

    # R4/R5 answers carry a per-answer label verdict in scores_json: what the model said, which
    # section of the prescribing information it breaks, and one sentence naming the error.
    # The Safety screen needs those per answer, not just as a per-cell count.
    LABEL_FIELDS = ("verdict", "tier", "harm_class", "error_types", "target", "label_section", "evidence")
    def label_of(r):
        raw = r.get("scores_json") if hasattr(r, "get") else r["scores_json"]
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return None
        try:
            d = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(d, dict) or not d.get("verdict"):
            return None
        return {k: d[k] for k in LABEL_FIELDS if d.get(k)}

    store = collections.OrderedDict()
    for p in corpus["prompts"]:
        k = "{}|{}".format(p["pid"], p["run"]); seen = collections.Counter(); rows = []
        for e in p["models"]:
            m = e["model"]; ri = seen[m]; seen[m] += 1
            if (p["pid"], p["run"], m, ri) not in arow.index:
                continue  # dropped model
            r = arow.loc[(p["pid"], p["run"], m, ri)]
            rows.append({"model": m, "repeat_idx": ri, "answer_raw": r["answer_raw"], "answer_clean": r["answer_clean"], "excluded": bool(r["excluded"]),
                         "exclude_reason": None if pd.isna(r["exclude_reason"]) else r["exclude_reason"], "citations": cit.get((p["pid"], p["run"], m, ri), [])})
            lab = label_of(r)
            if lab:
                rows[-1]["label"] = lab
        store[k] = rows
    by_run = collections.OrderedDict()
    for k, rows in store.items():
        by_run.setdefault(k.split("|")[1], collections.OrderedDict())[k] = rows
    out = collections.OrderedDict()
    for run, sub in by_run.items():
        raw = json.dumps(sub, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        out[run] = (base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii"), len(raw), len(sub), sum(len(v) for v in sub.values()))
    return out


def main() -> int:
    tpl = (UI / "template.html").read_text(encoding="utf-8")
    glossary = json.loads((UI / "glossary.json").read_text(encoding="utf-8"))   # plain-language wording, one file
    legacy = (UI / "evidence_base_legacy.html").read_text(encoding="utf-8")
    pdata = (C.METRICS_DIR / "platform_data.json").read_text(encoding="utf-8")

    # ---- legacy pieces reused unchanged ----------------------------------------------------
    # design source: the approved mockup — its <style> block (tokens, fonts, tiles, tables, tags, bars) is taken verbatim
    mock = (UI / "citere_cmo_master_screen.html").read_text(encoding="utf-8")
    style = mock[mock.index("<style>"): mock.index("</style>") + len("</style>")]
    # the Neural map keeps its own CSS from the legacy file (the block from #mapView{ up to the workbench rules); the legacy palette is not used
    lst = legacy.index("<style>\n"); lend = legacy.index("</style>", lst)
    lcss = legacy[lst:lend]
    map_css = "<style>\n" + lcss[lcss.index("#mapView{"): lcss.index("#wbView{")] + "</style>"
    assert "var(--" not in map_css, "legacy map CSS references legacy tokens: " + ", ".join(sorted(set(re.findall(r"var\((--[a-z0-9-]+)\)", map_css))))
    map_html = legacy[legacy.index('<div id="mapView">'): legacy.index('<div id="wbView">')]
    # the map's own header strip carried hard-coded cycle figures — re-point them at platform_data meta
    meta = json.loads(pdata)["meta"]
    old_strip = '<div class="s">GLP-1 · <b>Ozempic</b> vs <span style="color:#F4645C">Mounjaro</span> · US · <b>1,424</b> questions · <b>12,315</b> answers · cycle 1</div>'
    assert old_strip in map_html, "map header strip not found"
    vis8 = json.loads(pdata)["dashboard"]["visibility"]
    nas = vis8["named_any_scope"]
    map_html = map_html.replace(old_strip, ('<div class="s" data-g="screen_map">GLP-1 · <b>{}</b> vs <span style="color:#F4645C">{}</span> · {} · <b>{:,}</b> questions · <b>{:,}</b> answers · cycle {}</div>'
        '<div class="s" style="margin-top:34px" data-g="map_centre">Centre: named in <b>{:.0f}%</b> of all {:,} scored answers, across all {:,} tested questions. '
        'Visibility (<b>{}%</b>) is measured only on unbranded category questions (R1) and is the headline everywhere else.</div>').format(
        meta["brand"], meta["competitors"][0], meta["market"].split("/")[0], meta["prompts"], meta["answers"], meta["cycle"],
        vis8["named_any_scope_pct"], nas["answers_scored"], nas["points"], vis8["headline"]["visibility_pct"]))
    map_data = map_nodes(json.loads(pdata))
    _vis = json.loads(pdata)["dashboard"]["visibility"]
    _gauge = round(map_data["center"]["oz"] / map_data["center"]["ans"] * 100)
    assert _gauge == round(_vis["named_any_scope_pct"]), "map centre {} != dashboard named_any_scope_pct {}".format(_gauge, _vis["named_any_scope_pct"])
    app = legacy[legacy.index("<script>", legacy.index("const ANS_B64")) + len("<script>"):]
    app = app[: app.index("</script>")]
    lines = app.split("\n")
    def seg(start_pat, end_pat):
        s = next(i for i, l in enumerate(lines) if re.search(start_pat, l))
        e = next(i for i, l in enumerate(lines) if i > s and re.search(end_pat, l))
        return "\n".join(lines[s:e])
    nm = seg(r"^window\.__nmInited=false", r"^document\.getElementById\('mapLink'\)")  # __initNeuralMap + openMap/closeMap wiring
    # The node list now arrives ready-made from platform_data.json (map_nodes above); the legacy compute helpers
    # (CAUSE_CLS, HUMAN_CAUSE, the diagnosis and fix-card engines, dem, aiNative, pointPrio, medVol) are not carried.
    nm = re.sub(r"const NMP=P\.map\(p=>\{.*?\n\s*\}\);\n", "const NMP=P.map(q=>Object.assign({},q));\n", nm, count=1, flags=re.S)
    nm = re.sub(r"const NMC=\(\(\)=>\{.*?\}\)\(\);\n", "const NMC=DATA.center;\n", nm, count=1, flags=re.S)
    nm = nm.replace("${q.kw?`search trace <b>${q.kw.toLocaleString('en')}</b>/mo`:`<b>AI-native</b> \u2014 asked to AI, no Google trace`}",
                    "${q.ai?`<b>AI-native</b> \u2014 asked to AI, no Google trace`:`basis <b>${q.db}</b>`}")
    # labels only — no number changes. Each string below named a figure whose scope differs from the dashboard's word for it.
    relabels = [
        ("sp.className=layer[k]?'':'off';", "sp.className=layer[k]?'':'off'; sp.dataset.g={u:'map_we_hold',t:'map_we_lose',m:'map_contested',e:'map_unclaimed'}[k];"),
        ("ctx.fillText('VISIBILITY',sx(0),sy(0)+13);", "ctx.fillText('NAMED',sx(0),sy(0)+13);"),
        ("ctx.fillText('SHARE OF VOICE',sx(0),sy(0)+CR+18);", "ctx.fillText('OF ALL SCORED ANSWERS',sx(0),sy(0)+CR+18);"),
        ("'hold '+c.soa+'% · '+c.vis+' questions'", "'hold index '+c.soa+' · '+c.vis+' questions'"),
        ("◉ CLUSTER · hold ${cl.soa}%", "◉ CLUSTER · <span data-g=\"map_hold_index\">hold index ${cl.soa}</span>"),
        ("· sentiment <b>'+q.se+'</b>/100'", "· answer sentiment <b>'+q.se+'</b>/100'"),
        ("· sentiment <b>${q.se}</b>/100", "· <span data-g=\"answer_sentiment\">answer sentiment <b>${q.se}</b>/100</span>"),
        ("· demand <b>${q.vol.toLocaleString('en')}</b>/mo", "· <span data-g=\"question_share\">this question's share <b>${q.vol.toLocaleString('en')}</b>/mo</span>"),
        ('<div class="agg">${q.n} answers · ${q.qt} · ${q.sg}</div>',
         '<div class="agg">${q.n} scored answers · ${q.qt} · ${q.sg}${q.nx?` · <b>${q.nx}</b> excluded as unscoreable`:``}</div>'),
    ]
    for a_, b_ in relabels:
        assert a_ in nm, "map label not found: " + a_
        nm = nm.replace(a_, b_)
    for probe in ["const NMP=P.map(q=>Object.assign({},q));", "const NMC=DATA.center;", "basis <b>${q.db}</b>"]:
        assert probe in nm, "map data re-point failed: " + probe
    nm = nm.replace("tabM.classList.add('on');", "").replace("tabM.classList.remove('on');", "")
    nm = nm.replace("const tabM=document.getElementById('tabM');\ntabM.onclick=openMap;", "")
    nm = re.sub(r"window\.__nmGoPoint=pid=>\{.*?\};\n", "", nm, flags=re.S)
    nm = re.sub(r"window\.__nmGoFix=pid=>\{.*?\};\n", "", nm, flags=re.S)
    for gone in ["fixCards(", "dem(p)", "aiNative(p)", "HUMAN_CAUSE", "DATA.domIndex", "DATA.owners", "DATA.cats", "p.status", "p.bm"]:
        assert gone not in nm, "map still computes from legacy fields: " + gone

    # ---- revenue-at-risk lens (spec v2 §6) — radii/colour/labels only, positions untouched ----
    def _sub(pat, rep, why):
        nonlocal nm
        assert nm.count(pat) == 1, "map anchor not found ({}): {!r}".format(why, pat[:60])
        nm = nm.replace(pat, rep, 1)

    _sub("      q.r=(2.3+rnd()*1.6)*dsc; q.ph=rnd()*6.28; q.sub=sub; q.hide=false;",
         "      q.base=2.3+rnd()*1.6; q.dsc=dsc; q.r=q.base*dsc; q.ph=rnd()*6.28; q.sub=sub; q.hide=false;",
         "dot radius")

    _sub("const qsL=[...qs].sort((a,b)=>(b.cr-a.cr)||(PRI[a.s]-PRI[b.s])||((b.vol||0)-(a.vol||0)));",
         """let qsL=[];
const NM_PRICING=DATA.pricing||null;
let nmLens="dem", nmQT=[Infinity,Infinity];
function nmQuant(){
  const v=qs.filter(q=>!q.hide&&!q.pf&&q.usd&&q.usd[1]>0).map(q=>q.usd[1]).sort((a,b)=>b-a);
  return v.length?[v[Math.floor(v.length*0.10)],v[Math.floor(v.length*0.25)]]:[Infinity,Infinity];
}
function nmMult(q){
  if(nmLens!=="usd") return q.dsc;
  if(q.pf||!q.usd||!q.usd[1]) return 0.6;
  return q.usd[1]>=nmQT[0]?1.60 : q.usd[1]>=nmQT[1]?1.32 : 1.0;
}
function nmRelabel(){
  qsL = nmLens==="usd"
    ? [...qs].sort((a,b)=>(((b.usd&&b.usd[1])||0)-((a.usd&&a.usd[1])||0))||(b.cr-a.cr)||(PRI[a.s]-PRI[b.s])||((b.vol||0)-(a.vol||0)))
    : [...qs].sort((a,b)=>(b.cr-a.cr)||(PRI[a.s]-PRI[b.s])||((b.vol||0)-(a.vol||0)));
}
function nmU(v){ v=Math.round(v||0); const u=v>=1e6?1e6:v>=1000?1000:1, sfx=u===1e6?"M":u===1000?"K":"";
  const x=v/u; return (u===1e6?(x<10?x.toFixed(1):Math.round(x)):Math.round(x))+sfx; }
function nmUsd(f,m){ return "$"+nmU(f)+"\\u2013"+nmU(m); }
function nmSumUsd(list){ return list.reduce((a,q)=>(q.hide||q.pf||!q.usd)?a:[a[0]+q.usd[0],a[1]+q.usd[1]],[0,0]); }
function nmSetLens(l){
  nmLens=l; nmQT=nmQuant(); nmRelabel();
  const from=qs.map(q=>q.r), to=qs.map(q=>q.base*nmMult(q)), t0=performance.now();
  const step=()=>{ const p=Math.min(1,(performance.now()-t0)/300), e=p<.5?2*p*p:1-Math.pow(-2*p+2,2)/2;
    qs.forEach((q,i)=>{ q.r=from[i]+(to[i]-from[i])*e; });
    if(p<1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
nmRelabel();""",
         "label priority + lens state")

    _sub('function qCol(q){ return ov==="out"? COL[q.s] : FCOL[FAM[q.cz]||"phy"]; }',
         'function qCol(q){ if(q.pf) return "#8A94AC"; return ov==="out"? COL[q.s] : FCOL[FAM[q.cz]||"phy"]; }',
         "portfolio dots grey")

    _sub("          if(key!=='m'&&scale>.55){const gl=ctx.createRadialGradient(QX,QY,0,QX,QY,r*2.6);",
         "          if(key!=='m'&&scale>.55&&!q.pf){const gl=ctx.createRadialGradient(QX,QY,0,QX,QY,r*2.6);",
         "no halo on portfolio dots")

    _sub("function drawDonut(X,Y,br,cnt,vis){", "function drawDonut(X,Y,br,cnt,vis,host){", "donut signature")
    _sub("  ctx.textAlign='center';ctx.fillText(String(vis),X,Y+3.5);",
         """  ctx.textAlign='center';
  if(nmLens==="usd"&&host){ const v=nmSumUsd(host); ctx.font='600 '+Math.max(8,Math.min(11,br*.42))+'px "IBM Plex Mono"';
    ctx.fillText(nmUsd(v[0],v[1]),X,Y+3.5); } else ctx.fillText(String(vis),X,Y+3.5);""",
         "donut centre text")
    _sub("      drawDonut(X,Y,br,c.cnt,c.vis);", "      drawDonut(X,Y,br,c.cnt,c.vis,c.subs.flatMap(s=>s.qs));", "cluster donut call")
    _sub("          drawDonut(SX,SY,br,s.cnt,s.vis);", "          drawDonut(SX,SY,br,s.cnt,s.vis,s.qs);", "subtopic donut call")

    _sub("""    <a class="dcta" onclick="window.__nmGoPoint('${q.p}')">""",
         """    ${NM_PRICING&&q.usd?`<h3>$ at risk ${q.pf?"":"<span style=\\"color:#6A7590\\">(Google proxy, US \\u00b7 estimate)</span>"}</h3>
    <div class="agg">${q.pf?"Portfolio brand \\u2014 not counted as a loss"
      :`<b>${nmUsd(q.usd[0],q.usd[1])}</b>/mo \\u2014 ${(q.volx||0).toLocaleString("en")} searches/mo \\u00d7 ${Math.round((q.gp||0)*100)}% answers without Ozempic \\u00d7 $${NM_PRICING.floor.toFixed(2)}\\u2013${NM_PRICING.mid.toFixed(2)}`}</div>`:""}
    <a class="dcta" onclick="window.__nmGoPoint('${q.p}')">""",
         "drawer money block")

    _sub("window.__nmKick=()=>{",
         """window.__nmSetLens=nmSetLens;
(function(){ const s=document.getElementById('nm_fLens'); if(!s) return;
  if(!NM_PRICING){ s.style.display='none'; return; }
  if((location.hash||"").indexOf("lens=usd")>=0){ s.value="usd"; nmSetLens("usd"); }
  s.onchange=e=>nmSetLens(e.target.value);
})();
window.__nmKick=()=>{""",
         "lens control wiring")

    map_html = map_html.replace(
        '<select id="nm_fEx">',
        '<select id="nm_fLens"><option value="dem">Size: Demand</option><option value="usd">Size: $ at risk</option></select>\n  <select id="nm_fEx">', 1)
    map_js = ("<script>\nwindow.__mapBoot = function(){\n\"use strict\";\nconst DATA = window.MAP_DATA;\nconst P = DATA.points;\n" + nm +
              "\nwindow.__openMap=openMap; window.__closeMap=closeMap;\n};\n</script>")

    # ---- answer store --------------------------------------------------------------------
    stores = build_answer_store()
    ans_sizes = collections.OrderedDict(); n_pts = n_ans = 0
    for run, (b64, raw_len, npts, nans) in stores.items():
        js = ('// Full answer texts from corpus_master.json via data/normalized (step 1), run ' + run + ': gzip+base64 JSON keyed "pid|run",\n'
              '// each entry an array in corpus order of {model, repeat_idx, answer_raw, answer_clean, excluded, exclude_reason, citations[{domain,url,owner}]}.\n'
              'window.ANSWERS_B64_' + run + '="' + b64 + '";\n')
        (UI / "answers_{}.js".format(run)).write_text(js, encoding="utf-8")
        ans_sizes[run] = (UI / "answers_{}.js".format(run)).stat().st_size; n_pts += npts; n_ans += nans
        assert ans_sizes[run] <= ARTIFACT_TEXT_LIMIT, "answers_{}.js exceeds the artifact text-file ceiling".format(run)
    for stale in ["answers_b64.js", "answers.js"]:
        if (UI / stale).exists(): (UI / stale).unlink()
    # tasks layer (tasks/tasks.json + tasks/task_state.json) — the single source of "what to do"
    _tp, _sp = C.ROOT / "tasks" / "tasks.json", C.ROOT / "tasks" / "task_state.json"
    _tasks = json.loads(_tp.read_text(encoding="utf-8")) if _tp.exists() else {"tasks": []}
    _state = json.loads(_sp.read_text(encoding="utf-8")) if _sp.exists() else {}
    # The browser gets every field except the answer bodies: those already ship, gzipped, in
    # ui/answers_<run>.js, and duplicating 15.9MB of text here would double the page weight.
    # tasks/tasks.json keeps the full text as the source of truth.
    _slim = []
    for t in _tasks.get("tasks", []):
        t = dict(t)
        t["questions_all"] = [dict(r, answer_clean=None,
                                   models=[{k: v for k, v in m.items() if k != "answer_clean"}
                                           for m in (r.get("models") or [])])
                              for r in t.get("questions_all", [])]
        _slim.append(t)
    tasks_blob = json.dumps({"tasks": _slim, "state": _state,
                             "point_tasks": _tasks.get("point_tasks", {})},
                            ensure_ascii=False, separators=(",", ":"))
    # tasks layer: its own file, like map_data.js — the full answer texts would push index.html past the
    # 16MB artifact ceiling. Loaded by a plain <script src> before the app runs, so nothing is fetched at
    # render time.
    (UI / "tasks_data.js").write_text("window.TASKS=" + tasks_blob + ";\n", encoding="utf-8")
    tasks_size = (UI / "tasks_data.js").stat().st_size
    assert tasks_size <= ARTIFACT_TEXT_LIMIT, "tasks_data.js exceeds the artifact text-file ceiling"

    # map data block: separate file, loaded only when #/map opens
    pdj_pricing = json.loads(pdata).get("pricing")
    map_data["pricing"] = pdj_pricing   # revenue-at-risk v2 §4 — None when config/pricing.yaml is absent
    (UI / "map_data.js").write_text("window.MAP_DATA=" + json.dumps(map_data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    map_size = (UI / "map_data.js").stat().st_size
    assert map_size <= ARTIFACT_TEXT_LIMIT
    # node counts per topic group must equal groups[].n_prompts — the map and #/priorities read the same grouping
    pdj = json.loads(pdata); per_gid = collections.Counter(n["gid"] for n in map_data["points"])
    bad = [(g["group_id"], g["n_prompts"], per_gid.get(g["group_id"], 0)) for g in pdj["groups"] if per_gid.get(g["group_id"], 0) != g["n_prompts"]]
    assert not bad, "map node counts differ from groups[].n_prompts: {}".format(bad[:5])
    per_sub = collections.Counter((n["to"], n["su"]) for n in map_data["points"])
    assert len(per_sub) == len(per_gid), "map sub-clusters do not match topic groups one to one"

    # ---- assemble ------------------------------------------------------------------------
    out = tpl.replace("<!--MOCKUP_STYLE-->", style).replace("<!--LEGACY_MAP_CSS-->", map_css) \
             .replace("<!--LEGACY_MAP_HTML-->", map_html) \
             .replace("<script>/*GLOSSARY*/</script>", "<script>window.GLOSSARY=" + json.dumps(glossary, ensure_ascii=False, separators=(",", ":")) + ";</script>") \
             .replace("<script>/*PLATFORM_DATA*/</script>", "<script>window.PLATFORM_DATA=" + pdata + ";</script>") \
             .replace("<script>/*TASKS*/</script>", '<script src="tasks_data.js"></script>') \
             .replace("<!--LEGACY_MAP_JS-->", map_js)
    markup = tpl + map_js + map_html
    used = set(k for k in glossary if not k.startswith("_") and re.search(r'["\']' + re.escape(k) + r'["\']', markup))
    missing = sorted(used - set(glossary))
    assert not missing, "figures point at glossary entries that do not exist: {}".format(missing)
    unused = sorted(k for k in glossary if not k.startswith("_") and k not in used)
    (UI / "index.html").write_text(out, encoding="utf-8")
    print("glossary: {} entries, {} used by figures{}".format(len([k for k in glossary if not k.startswith("_")]), len(used), ", unused: " + ", ".join(unused) if unused else ""))
    print("tasks_data.js {:,} bytes".format(tasks_size))
    print("index.html {:,} bytes | map_data.js {:,} bytes ({} nodes, {} topic groups, from platform_data.json) | answer stores {} points, {} answers, total {:,} bytes:".format(
        (UI / "index.html").stat().st_size, map_size, len(map_data["points"]), len(per_gid), n_pts, n_ans, sum(ans_sizes.values())))
    for run, sz in ans_sizes.items():
        print("  answers_{}.js {:,} bytes".format(run, sz))
    return 0


if __name__ == "__main__":
    sys.exit(main())
