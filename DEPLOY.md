# Deploying the Citere platform

Handoff note for whoever puts this on GitHub. Read the whole thing before creating the repository —
one decision (§1) has to be made first, and one known gap (§4) will otherwise cost you a morning.

## 1. Decide repository visibility before you push

The repository contains client analysis, not a demo:

- revenue-at-risk figures for a named client and their competitors;
- full text of 12,314 model answers about a marketed drug;
- the raw corpus, `data/raw/corpus_master.json` (56 MB). It is not in the working tree — it was
  committed first and removed in `193bcc7` — but it is intact in history and anyone with access can
  recover it with `git show f528f2a:data/raw/corpus_master.json`. Removing a file from the tip does
  not remove it from a repository;
- 10 safety findings asserting that AI assistants contradict or omit parts of the Ozempic
  prescribing information. Every one of them is `signoff_status: "pending"`, and the platform
  itself states that pending findings do not enter the client report.

Publishing unsigned-off clinical claims about a real medicine is not a technical decision. Get it
answered by whoever owns the client relationship, then create the repository accordingly.

**Consequence for hosting:** GitHub Pages serves a private repository only on a paid plan
(Pro, Team or Enterprise). On a free account, private repository means no Pages URL — the site
still runs, but only from a local checkout or another host.

## 2. What actually gets deployed

A static site. No backend, no API, no database, no build step at serve time. Serve the `ui/`
directory; the entry point is `ui/index.html`.

```
ui/index.html                 the application, platform data inlined      10.5 MB
ui/tasks_data.js              task registry, loaded at startup             1.0 MB
ui/map_data.js                neural map, loaded when that screen opens    1.1 MB
ui/answers_R1.js … R9.js      answer texts, gzip+base64, per run          19.1 MB
ui/glossary.json              wording; already inlined into index.html
ui/template.html              source of index.html — not served
ui/evidence_base_legacy.html  build input — not served
```

Everything except `template.html` and `evidence_base_legacy.html` must be served from the same
directory: the app resolves `tasks_data.js`, `map_data.js` and `answers_R*.js` by relative path.

Routing is a hash router (`#/competitors`, `#/point/P1141|R4`). No rewrite rules, no SPA fallback,
no server configuration of any kind.

Browsers must support `DecompressionStream` — the answer bundles are gzipped. That is Chrome 80+,
Safari 16.4+, Firefox 113+. There is no fallback path; an older browser shows the site but cannot
open answer texts or the per-answer safety verdicts.

## 3. Putting it on GitHub

```bash
cd citere-metrics
gh repo create citere-metrics --private --source=. --remote=origin --push
```

Then, if Pages is wanted and the plan allows it:

```bash
gh api -X POST repos/:owner/citere-metrics/pages \
  -f 'source[branch]=main' -f 'source[path]=/ui'
```

The site lands at `https://<owner>.github.io/citere-metrics/`.

Sizes are within every GitHub limit: about 165 MB of history, largest tracked file 15 MB against
the 100 MB hard limit. Nothing needs Git LFS.

## 4. Known gap: a clean clone cannot rebuild the UI

`ui/index.html` and `ui/answers_R*.js` are committed as build artifacts, so **deploying works from
a clean clone**. Changing the UI takes two extra steps that are not obvious.

`src/step_10_build_ui.py` calls `build_answer_store()`, which reads `data/raw/corpus_master.json`
and `data/normalized/*.parquet`. None of the three is in the working tree: the corpus was removed
in `193bcc7`, and the parquets have never been committed. Run the build on a fresh clone and it
stops with `FileNotFoundError` before writing anything.

Both are recoverable, because the corpus survives in history and the parquets are derived from it:

```bash
git show f528f2a:data/raw/corpus_master.json > data/raw/corpus_master.json   # 56 MB, 1,424 prompts
.venv/bin/python -m src.step_01_normalize                                    # writes both parquets
.venv/bin/python -m src.step_10_build_ui                                     # now succeeds
```

Verified: the blob in `f528f2a` parses and holds all 1,424 prompts across R1–R9.

If UI work is going to be routine, make this less fragile — either commit the parquets (~40 MB,
which also settles it for anyone who never reads this file), or let `build_answer_store()` leave
the existing `ui/answers_R*.js` alone when the parquets are absent, so template and layout changes
rebuild `index.html` on its own.

## 5. Rebuilding, where the inputs exist

```bash
python3 -m venv .venv && .venv/bin/pip install pandas pyarrow PyYAML
.venv/bin/python -m src.step_10_build_ui
```

`RUNBOOK.md` specifies Python 3.12; the pipeline also runs on 3.9.6, which is what the current
artifacts were built with. Only step 10 rebuilds the UI — steps 1–9 recompute the metrics and are
not needed for a deployment.

The build is deterministic: same inputs and config produce byte-identical output (gzip is written
with `mtime=0`, nothing is timestamped). Run it twice and diff if you want to confirm it.

Keep every generated text file under 16 MB. That ceiling is why the task registry lives in
`tasks_data.js` rather than inside `index.html`, and why answer bodies are stripped from the
browser copy of the task data.

## 6. Task status is read-only at runtime

`tasks/task_state.json` is the source of truth for task status and assignment, baked in at build
time. The Action Center lets a user change status, assign work and drag cards between columns, but
the site is static and cannot write the file back. Changes are held in that browser's
`localStorage`, marked "unsaved", and exported through a button that copies a complete
`task_state.json` to the clipboard, to be committed and rebuilt.

If the client wants status to persist for everyone without a rebuild, that is a backend — a small
endpoint that reads and writes `task_state.json`, plus swapping the export button for a save call.
It is deliberately not built.

## 7. Before you hand the URL to anyone

- `#/` renders and every tile links somewhere.
- `#/safety` → click a findings row → it expands in place → open a question → per-answer verdicts
  appear. That path exercises the lazy-loaded gzip bundles; if `DecompressionStream` or the
  relative paths are wrong, this is where it shows.
- `#/actions` → Board and Table both render; changing a status marks it unsaved.
- Browser console is clean on first load.
- The page is readable in both light and dark themes — it follows the visitor's system setting.
