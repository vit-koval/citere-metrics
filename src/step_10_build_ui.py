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
MAP_DATA_KEYS = ["points", "domIndex", "owners", "cats", "runs"]
ARTIFACT_TEXT_LIMIT = 16 * 1024 * 1024   # artifact publish ceiling per text file → answer store is split by run


def build_answer_store():
    a = C.load_answers(); c = C.load_citations(); corpus = C.load_raw_corpus()
    key = ["pid", "run", "model", "repeat_idx"]
    cit = {}
    for k, g in c[~c["is_artifact"]].groupby(key):
        cit[k] = [{"domain": d, "url": u, "owner": o} for d, u, o in zip(g["domain"], g["url"], g["owner"])]
    arow = a.set_index(key)
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
    m = re.search(r'const DATA=(\{.*?\});\n', legacy, re.S)
    full = json.loads(m.group(1))
    map_data = {k: full[k] for k in MAP_DATA_KEYS}
    app = legacy[legacy.index("<script>", legacy.index("const ANS_B64")) + len("<script>"):]
    app = app[: app.index("</script>")]
    lines = app.split("\n")
    def seg(start_pat, end_pat):
        s = next(i for i, l in enumerate(lines) if re.search(start_pat, l))
        e = next(i for i, l in enumerate(lines) if i > s and re.search(end_pat, l))
        return "\n".join(lines[s:e])
    consts = seg(r"^const STATUS = \{", r"^const fmtVol")                       # STATUS
    consts += seg(r"^const CAUSE_CLS", r"^// ---- plain-language diagnosis")   # CAUSE_CLS, BRAND_COLOR
    engine = seg(r"^// ---- plain-language diagnosis", r"^function strip\(")   # HUMAN_CAUSE … fixCards, dem, aiNative, pointPrio
    nm = seg(r"^window\.__nmInited=false", r"^document\.getElementById\('mapLink'\)")  # __initNeuralMap + openMap/closeMap wiring
    nm = nm.replace("tabM.classList.add('on');", "").replace("tabM.classList.remove('on');", "")
    nm = nm.replace("const tabM=document.getElementById('tabM');\ntabM.onclick=openMap;", "")
    nm = re.sub(r"window\.__nmGoPoint=pid=>\{.*?\};\n", "", nm, flags=re.S)
    nm = re.sub(r"window\.__nmGoFix=pid=>\{.*?\};\n", "", nm, flags=re.S)
    for chunk, name in [(consts, "consts"), (engine, "engine")]:
        assert "document." not in chunk, "legacy {} touches the DOM at load time".format(name)
    map_js = ("<script>\nwindow.__mapBoot = function(){\n\"use strict\";\nconst DATA = window.MAP_DATA;\n" + consts + "\n" + engine + "\n" + nm +
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
    # map data block: separate file, loaded only when #/map opens
    (UI / "map_data.js").write_text("window.MAP_DATA=" + json.dumps(map_data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    map_size = (UI / "map_data.js").stat().st_size
    assert map_size <= ARTIFACT_TEXT_LIMIT

    # ---- assemble ------------------------------------------------------------------------
    out = tpl.replace("<!--MOCKUP_STYLE-->", style).replace("<!--LEGACY_MAP_CSS-->", map_css) \
             .replace("<!--LEGACY_MAP_HTML-->", map_html) \
             .replace("<script>/*PLATFORM_DATA*/</script>", "<script>window.PLATFORM_DATA=" + pdata + ";</script>") \
             .replace("<!--LEGACY_MAP_JS-->", map_js)
    (UI / "index.html").write_text(out, encoding="utf-8")
    print("index.html {:,} bytes | map_data.js {:,} bytes ({}) | answer stores {} points, {} answers, total {:,} bytes:".format(
        (UI / "index.html").stat().st_size, map_size, ", ".join(MAP_DATA_KEYS), n_pts, n_ans, sum(ans_sizes.values())))
    for run, sz in ans_sizes.items():
        print("  answers_{}.js {:,} bytes".format(run, sz))
    return 0


if __name__ == "__main__":
    sys.exit(main())
