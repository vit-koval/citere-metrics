"""Step 10 — build ui/index.html (ui_spec.md).

Inputs : ui/template.html, data/metrics/cycle_01/platform_data.json, ui/evidence_base_legacy.html (style block, map view markup,
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
SPLIT_LIMIT = 20 * 1024 * 1024


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
    raw = json.dumps(store, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")
    return store, b64, len(raw)


def main() -> int:
    tpl = (UI / "template.html").read_text(encoding="utf-8")
    legacy = (UI / "evidence_base_legacy.html").read_text(encoding="utf-8")
    pdata = (C.METRICS_DIR / "platform_data.json").read_text(encoding="utf-8")

    # ---- legacy pieces reused unchanged ----------------------------------------------------
    st0 = legacy.index("<style>\n")  # the real block (line 4); line 1 holds only the artifact wrapper reset
    style = legacy[st0: legacy.index("</style>", st0) + len("</style>")]
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
    map_js = ("<script>\n(function(){\n\"use strict\";\nconst DATA = window.MAP_DATA;\n" + consts + "\n" + engine + "\n" + nm +
              "\nwindow.__openMap=openMap; window.__closeMap=closeMap;\n})();\n</script>")

    # ---- answer store --------------------------------------------------------------------
    store, b64, raw_len = build_answer_store()
    js = ('// Full answer texts from corpus_master.json via data/normalized (step 1): gzip+base64 JSON keyed "pid|run",\n'
          '// each entry an array in corpus order of {model, repeat_idx, answer_raw, answer_clean, excluded, exclude_reason, citations[{domain,url,owner}]}.\n'
          'window.ANSWERS_B64="' + b64 + '";\n')
    (UI / "answers.js").write_text(js, encoding="utf-8")
    ans_size = (UI / "answers.js").stat().st_size
    if ans_size > SPLIT_LIMIT:
        print("answers.js is {:,} bytes > 20 MB — split by run required (not implemented in this build)".format(ans_size)); return 2
    for stale in ["answers_b64.js"]:
        if (UI / stale).exists(): (UI / stale).unlink()

    # ---- assemble ------------------------------------------------------------------------
    out = tpl.replace("<!--LEGACY_STYLE-->", style) \
             .replace("<!--LEGACY_MAP_HTML-->", map_html) \
             .replace("<script>/*PLATFORM_DATA*/</script>", "<script>window.PLATFORM_DATA=" + pdata + ";</script>") \
             .replace("<script>/*MAP_DATA*/</script>", "<script>window.MAP_DATA=" + json.dumps(map_data, ensure_ascii=False, separators=(",", ":")) + ";</script>") \
             .replace("<!--LEGACY_MAP_JS-->", map_js)
    (UI / "index.html").write_text(out, encoding="utf-8")
    print("index.html {:,} bytes | answers.js {:,} bytes ({:,} bytes JSON, {} points, {} answers) | map data {:,} bytes ({})".format(
        (UI / "index.html").stat().st_size, ans_size, raw_len, len(store), sum(len(v) for v in store.values()),
        len(json.dumps(map_data, separators=(",", ":"))), ", ".join(MAP_DATA_KEYS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
