# Spec: Citation Tracking

Version 1.0 · For Claude Code · Input: the same consolidated JSON. Brand dictionary, prompt classification (C1–C4) and quality filters — from `visibility_score_spec.md`, unchanged.

Three outputs:
1. **Owner pie** — share of citations owned / earned / institutional / competitor, with delta
2. **Top-10 domains** — citation share, category, which answers
3. **Gap list** — domains that feed answers about the competitor and stay silent about us

---

## 1. Input data and limitations

- `citations[]` in `models[i]` — `{url, domain, owner, category}`. R4/R5/R8 have no citations — those runs are excluded; report their share of total answers.
- Normalize domains before computing: lowercase, strip `www.`, reduce to registrable domain (`sub.mayoclinic.org` → `mayoclinic.org`).
- `vertexaisearch.cloud.google.com` and other grounding redirect wrappers are **not sources** but collection artifacts. Exclude; report their share by model.
- The same citation twice in one answer counts once.

If `url` or position is present — use it (URL → registrable domain for aggregation, keep the URL in the table); report what was found.

---

## 2. Domain classification — four owners

If `citations[].owner` and `category` are already populated — use them as primary. Config (required, supplied separately) is used to verify and override:
```
OWNED: ["ozempic.com", "novonordisk.com", "novomedlink.com", ...]
COMPETITOR: {"Mounjaro": ["mounjaro.lilly.com", "lilly.com", ...], "Wegovy": [...], ...}
```

Rules:
- **owned** — domain in OWNED (data owner `owned`)
- **competitor** — domain in COMPETITOR (data owner `comp_owned`), with brand
- **institutional** — by list: regulators (fda.gov, ema.europa.eu, dailymed.nlm.nih.gov, accessdata.fda.gov), public health (nih.gov, cdc.gov, nhs.uk, medlineplus.gov), clinical databases (pubmed.ncbi.nlm.nih.gov, cochrane.org), Wikipedia. Data categories `regulatory`, `gov_health`, `wiki`, `clinical` map here. Config `INSTITUTIONAL`, starter set as listed, extend from data.
- **earned** — everything else: health media (webmd, healthline, drugs.com, goodrx), hospitals (mayoclinic, clevelandclinic), news, forums, Reddit, YouTube, telehealth, litigation sites. Data owners `earned`, `commerce`, `ugc` map here.

Inside `earned` — a subtype from data `category` where available: `health_media`, `hospital`, `directory` (drugs.com, goodrx), `ugc` (reddit, youtube, quora), `news`, `telehealth`, `litigation` (drugwatch, law-firm domains), `other`. Output the top-100 domains with their subtype for manual review.

Data owner `adversarial` — reported separately as "threat sources", not part of the pie. Data owner `noise` — excluded. Data owner `other` — classified `earned` with subtype `other` (changed after the cycle-1 data quality review; previously excluded).

Domains not in any config list and without a data category → `earned/other`. Output the top-30 of these for manual labeling.

---

## 3. Owner pie

Unit — a **citation** (one occurrence of a domain in one answer).

- `share(owner)` = owner citations / all citations × 100, for the four owners
- The same by model (Claude/Perplexity expected higher institutional, ChatGPT/Gemini — health media; verify)
- The same by prompt class C1–C4
- Inside `earned` — subtype shares

Additionally, one line: `owned_share_in_answers_with_us` — share of our domains in citations only in answers where our brand is named. Shows whether we are cited when we are discussed.

Aggregation — directly over citations (not repeats→prompts as in the other specs): here we measure the composition of the citation corpus, not a per-prompt probability. State this in the report.

---

## 4. Top-10 domains

For each domain:
- `citations` — number of occurrences; `share` — share of all citations
- `owner`, `subtype`
- `answers_pct` — share of answers in which the domain is cited
- `with_us_pct` — share of its citations in answers where our brand is named
- `with_comp_pct` — share of its citations in answers where a competitor (any) is named
- `by_model` — which model most often
- `by_zone` — which prompt zone most often

Output overall top-10 and top-5 per owner.

---

## 5. Gap list

Peec logic: domains that feed answers about the competitor and do not feed answers about us.

Computed on C1 (unbranded prompts) — brand presence in the answer is not set by the question there.

For each domain D:
- `cites_comp` = number of C1 answers where D is cited **and** a competitor is named but we are not
- `cites_us` = number of C1 answers where D is cited **and** we are named
- `gap_score` = cites_comp − cites_us (if ≤ 0 — not a gap)
- `competitors_fed` — how many distinct competitors D "feeds" (by brands named in those answers)

Sort — by `gap_score`, then by `competitors_fed`. Top-10.

For each gap domain: `owner` and `subtype` — this is the action type (health_media → PR, directory → data feed, ugc → monitor, institutional → not fixable).

Exclude `institutional` from the gap list — report as one line "institutional domains feeding the competitor: N", no action.

---

## 6. Output format

**6.1. `citations_summary.json`**
```json
{
  "brand": "...",
  "citations_total": 0, "answers_with_citations": 0, "answers_without_citations_pct": 0.0,
  "artifacts_removed": {"vertexaisearch.cloud.google.com": 0},
  "owner_shares": {"owned": 0.0, "earned": 0.0, "institutional": 0.0, "competitor": 0.0},
  "owner_shares_by_model": [{"model": "...", "owned": 0.0, "earned": 0.0, "institutional": 0.0, "competitor": 0.0}],
  "earned_subtypes": {"health_media": 0.0, "hospital": 0.0, "directory": 0.0, "ugc": 0.0, "news": 0.0, "telehealth": 0.0, "litigation": 0.0, "other": 0.0},
  "owned_share_in_answers_with_us": 0.0,
  "top_domains": [
    {"domain": "...", "citations": 0, "share": 0.0, "owner": "...", "subtype": "...",
     "answers_pct": 0.0, "with_us_pct": 0.0, "with_comp_pct": 0.0, "top_model": "...", "top_zone": "..."}
  ],
  "top_by_owner": {"owned": [...], "earned": [...], "institutional": [...], "competitor": [...]},
  "gap_list": [
    {"domain": "...", "gap_score": 0, "cites_comp": 0, "cites_us": 0, "competitors_fed": 0,
     "owner": "earned", "subtype": "...", "action_type": "PR"}
  ],
  "institutional_feeding_competitors": 0,
  "adversarial_sources": [{"domain": "...", "citations": 0}],
  "unclassified_top30": ["..."]
}
```

**6.2. `citations_domains.csv`** — all domains: `domain, citations, share, owner, subtype, answers_pct, with_us_pct, with_comp_pct, gap_score`.

**6.3. `citations_raw.csv`** — `pid, model, repeat_idx, class, domain, url, owner, subtype, we_present, comps_present[]`.

**6.4. Short report** (≤ 12 lines): pie, owned share in answers about us, top-5 domains, top-5 gaps with action type, share of answers without citations, share of artifacts.

---

## 7. Do not

- Do not analyze competitor page content — deferred until URL-level content is collected.
- Do not compute "used vs cited" — "used" is not collected.
- Do not assign an unknown domain to owned/competitor/institutional by guess — only `earned/other` and the review list.
- Do not compute source weights ("clinical portals .86") — that is the weight engine, a separate document.
- On schema mismatch — stop and ask.
