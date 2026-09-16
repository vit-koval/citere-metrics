# Cycle 1 — every decision, in one place

What cycle 1 measures and what it does not. One line per decision, grouped by step. Specs were edited only where noted; everything else is recorded in the step reports and JSON outputs. Environment: Python 3.9.6 (runbook says 3.12; none installed), pandas 2.3.3, pyarrow 21.0.0, seed 42, all steps byte-deterministic.

## Step 0 — configs
- Wegovy and Rybelsus are competitors although Novo products: in an AI answer they compete with Ozempic for the same slot.
- semaglutide stays out of competitor_inn (maps to us, Wegovy and Rybelsus at once); INN is never a brand match, only the `inn_only` counter.
- Trulicity/Victoza/Saxenda domains added; lilly.com and boehringer-ingelheim.com moved to `Lilly corporate` / `Boehringer corporate` competitor entries; trulicity.lilly.com kept under Trulicity via longest-suffix matching.
- Seven Novo corporate hosts (pro.novonordisk.co.uk, novo-pi.com, novonordiskmedical.com, novonordisk-us.com, novonordisk.com.au, novonordisk.ca, pro.novonordisk.ae) added to owned after the first DQ pass.
- Farxiga, Januvia, Invokana added as competitors with INNs and domains; metformin deliberately not added (generic, not a brand).
- Config overrides `adversarial_domains` (hmf-law.com), `noise_domains` (kcconvention.com) and the MHRA Azure host in institutional_domains; overrides apply first, all matched on the full host before registrable-domain reduction.
- domains.yaml carries a note that novonordisk.com and novocare.com also cover Wegovy and Rybelsus, so some owned citations come from answers about those brands.

## Step 1 — normalization
- Domain matching is longest-suffix on the full host; `domain` holds the registrable domain for aggregation and dedup (approximate public-suffix rule, no external list).
- Exclusion precedence: too_short, then chip_on_cut, then truncated.
- Terminal set extended with typographic closing quotes ” and ’ (spec set `.!?)»"`).
- Tail cleaning strips a bare source-name token after a terminal character (`MotherToBaby`, `CDC`, `ozempic.com`) and `FDA Access Data +N` as one chip; unit-tested.
- Stored citation owner `other` is classified earned/other (previously excluded); only `noise` is excluded — citation_tracking_spec §2 and normalization_spec §3 updated.
- `status` is never used for class; C1–C4 come from prompt text via the dictionary. 57% status/class mismatch is expected and reported.
- The R1 scorer already ignores INN (disagreement with text `we_present` 0.1%), contrary to the spec's expectation; favorable, no action.
- Prompt keys are (pid, run): P0979 and P1013 appear in both R7 and R8.
- Parquet outputs are gitignored (39 MB, reproducible in ~25 s); the data quality report is committed. data/raw is out of git history from the second commit on (the first commit still contains the corpus blob).

## Step 2 — visibility
- Headline Visibility / Average Position / AI Brand Score are computed on R1 C1 only (the category corpus); C1 prompts in R2/R3/R5/R6 are reported in `c1_other_runs` for reference — visibility_score_spec §2 updated.
- Position source is the text ordinal among dictionary brands; `scores.our_rank` ranks among all brands the scorer saw (metformin, Tradjenta…) and disagrees by >1 in 128 of 547 answers, so it is kept only as a check (scored-rank variant reported).
- Families with fewer than 30 C1 answers are flagged low_n and left out of the headline mean; none in the R1 headline after the scope decision.
- Cross-check: visibility from `our_status_scored` vs `we_present` on the same R1 answers differs by 0.09 points (PASS).
- Web surfaces have no R1 answers, so no visibility on web is measured this cycle.
- Independent review: 60/60 rows agree (20 present / 20 absent / 20 INN-only, seed 42).

## Step 3a — competitive benchmarking
- Win Rate and Impact on R1 C1 only, families pooled, equal weights, Wilson CI by overlap answers.
- Duel Verdict from R2 `scores.winner` on C4 prompts only; ours=1, comp=0, split=0.5; none/na/third excluded (6%); R2 non-C4 prompts are family pairs and are not our duel.
- `worst_model` / `worst_zone` in the leaderboard are by highest Impact (the prioritization metric), not lowest Win Rate.
- Independent review: 40/40 answers (165 answer×competitor pairs) agree.

## Step 3b — citation tracking
- Unit is a citation, deduplicated within an answer; aggregation directly over citations across all runs that carry them (R1, R2, R3, R6, R7, R9); R4/R5/R8 have none.
- Pie = owned + earned + institutional + competitor; adversarial reported separately; noise and artifacts removed; citations from quality-excluded answers dropped.
- Earned subtype mapping: media→health_media, news_pr/pr_wire→news, video/social→ugc; advocacy and payer kept as their own subtypes.
- Gap list computed on R1 C1 (headline scope).
- Audit pool is all classified domains (pie + adversarial + noise) so a reclassification does not shift the sample.
- Independent review: 37/40 domains agree; flagged for a future config pass: europepmc.org (should be institutional), healio.com (trade press, reads as earned), turkjfampract.org (spam-injected URL, should be noise).

## Step 4 — sentiment (v1)
- Scope is class C2 only (R3 living-on-the-drug, R9 narrative probes); stored answer-level sentiment used as brand sentiment; 83 R9 answers without a value excluded.
- No LLM re-scoring: C1/C3/C4 brand-level sentiment, the competitor comparison and the ≥0.6 correlation gate are deferred to v2.
- Thresholds ≤40 negative, ≥60 positive; families pooled, equal weights, Wilson CI by answers.
- Negative themes come from stored prompt tags: R3 `tags.subtype` B1–B7 (no legend in the corpus; labels inferred from prompt texts) and R9 `tags.narr_id` NR-* (self-describing); answer-level scores (stance/tone/uptake…) kept as context only.
- `pct_of_all` = negative answers with the theme ÷ all in-scope answers; `negative_rate_within_theme` added.
- R3 and R9 are reported separately in the dashboard (R3 headline, R9 `narrative_resistance`) because R9 myth prompts dominate the negative pool.
- claude-sonnet-4-6 answered only R3 and claude-sonnet-5 only R9, so their version-level figures reflect the run mix, not model behaviour.
- JSON keeps full precision; rounding to 1 decimal happens only in report text and in step 8.

## Step 5 — safety / label flag (R4)
- Truncation filter is the normalization `excluded` flag; nothing re-filtered. Verdicts taken as stored.
- Cell = `scores.target` × surface: 36 targets in the data (spec expected 12), 216 cells; finding = critical_share ≥ 0.5 and n ≥ 3; DANGEROUS if any harm_class = DANGEROUS in the cell.
- Traffic light RED from 10 findings (6 DANGEROUS, 4 INCOMPLETE); all pending clinician sign-off, so none enters the client report or the Action Center.
- Scoring caveat recorded on every finding: Omission is 94% of CRITICAL verdicts, and several T-THYR-CI cells mark an answer CRITICAL for omitting thyroid-symptom counselling after it correctly stated the family-history contraindication — first question for the reviewing clinician.
- Flagged for review, verdicts unchanged: P1308 grok-web and P1306 claude-web carry harm_class DANGEROUS that the answer text does not support.
- Independent review: 38/40 verdicts defensible; the two misses (P1144, P1283) are the T-THYR-CI counselling pattern above.
- 35 cells are unstable (0 < critical_share < 50%) and need a re-run before they can be called; grok-web has one repeat, all its cells single_run.

## Step 6 — diagnosis & prioritization
- Group = topic × subtopic when subtopic is set and ≠ Other, else topic × zone; groups under 10 prompts attach to the largest sibling of their topic, demand recomputed as the median across merged prompts (a topic with no 10+ group keeps `topic × small` with its own demand, never inherited).
- Gap pools different failure kinds across runs (R1 absent, R2 lost duel, R4 label error, R6 message not delivered); every row carries gap_by_run and its dominant run.
- Lever = owner citations ÷ all citations in the group's answers after removing noise/other; institutional categories excluded from Lever (reported as institutional_share); adversarial reported separately; commerce folded into earned as a subtype.
- Rows with gap = 0 dropped before terciles (none this cycle); `min_gap` 0.20 in thresholds.yaml — groups below it go to `below_gap_floor` (none this cycle).
- `non_failure_codes` in thresholds.yaml: REACH OK, PATIENT RETAINED, NO CLEAR WINNER, MYTH DEFENDED, COMPETITOR WITHIN LABEL, ANSWERED CORRECTLY, WE WIN THIS DUEL, ENTITY KNOWN WELL; MESSAGE DELIVERED stays a failure code (Claim Uptake dimension). A group whose dominant code is non-failure goes to `healthy_groups` (19 this cycle).
- Known v1 limitation: the dominant code alone decides inclusion; `failure_code_share` on healthy groups shows secondary failure density but is not acted on until v2.
- Rows whose `who` is Citere are our monitoring, listed separately from the client table (3 this cycle).
- Label rows (no citations, label codes) form a separate sub-list with Score = Demand_share × Gap (2 this cycle).

## Step 7 — action center
- Tasks come from step 6 rows; execution owned→auto, other owners→manual, `who` containing Citere→citere; impact ceiling_pp = gap × lever × 100, expected_pp = ceiling × closure coefficients, basis prior; Label rows have no expected_pp.
- Label tasks stay out of the queue and counters while any finding in the label registry is pending (2 held this cycle).
- The cycle-1 registry was regenerated after each step 6 revision (no cross-cycle carry-over exists yet); from cycle 2 the merge-by-task_id rule applies.

## Step 8 — dashboard assembly
- Check 2 is scope-aware: visibility families are validated against config families that have at least one answer in the R1 C1 headline scope; perplexity and grok are excluded from the validation because they have no R1 C1 answers (web-only) — dashboard_assembly_spec §2 updated.
- before_after.available = false, reason "first cycle", next cycle expected 2026-12.
- Sentiment block reflects v1 scope: R3 headline plus a separate narrative_resistance (R9) block; C1/C3/C4 brand-level sentiment deferred to v2.
- Floats rounded to 1 decimal in step 8 only; `score`-type keys keep 6 decimals because they are tiny products.
- Audit-sample carry-forward treats an empty cell and NaN as equal (a CSV round-trip had silently dropped 25 step-5 review rows; restored). Reviewed samples from steps 2/3/5 are kept as the audit pack under the spec's file names (they exceed 30 rows and carry reviews); step 8 adds sample_sentiment.csv and sample_safety.csv (30 random rows each, seed 42, unreviewed) and audit_pack_manifest.json with the ≥90% release rule.
- safety_label.findings_list is empty in the dashboard because no finding is confirmed yet.

## Not measured this cycle
- Visibility, Win Rate and Impact on web surfaces (no unbranded R1 prompts there).
- Brand-level sentiment outside C2, competitor sentiment, and the sentiment correlation gate.
- Before/after deltas (first cycle).
- Any label finding as confirmed — all await clinician sign-off.

## Step 10 — UI (`src/step_10_build_ui.py` → `ui/index.html`, `ui/answers.js`)

- **Answer store rebuilt from the corpus.** `ui/answers.js` holds full texts (no previews) for all 1,424 points / 12,314 answers, keyed `pid|run`, corpus order, with `excluded` / `exclude_reason` and per-answer citations; gzip (mtime 0) + base64, 19,892,346 bytes — under the 20 MB split threshold, so one file. The legacy preview store `ui/answers_b64.js` (texts cut at 2,000 chars) is deleted; `answers_ref` in platform_data.json now reads `answers.js#pid|run` (step 9 re-run, checks 7/7).
- **The UI computes nothing.** Every number on Levels 1–3 is read from `platform_data.json`; the JS only formats, sorts and filters. Level 1 = eight tiles; Level 2 = `#/visibility #/competitors #/sentiment #/sources #/priorities #/actions #/safety #/map`; Level 3 = `#/point/<pid>|<run>` with full answers loaded on demand.
- **Legacy reuse.** Design tokens and CSS, the `#mapView` markup and the Neural map init code are taken verbatim from `ui/evidence_base_legacy.html` at build time. The map keeps its own data block (`MAP_DATA`: legacy `points, domIndex, owners, cats, runs`, 3.8 MB) and the legacy helpers it calls (fix engine, HUMAN_CAUSE, dem, aiNative), all wrapped in one IIFE so nothing leaks into the new app. The map is the only place where legacy-computed numbers still appear (spec: "unchanged").
- **Legacy code dropped because it computed numbers not in platform_data.json:** share-of-voice / sentiment / index strip (`strip()`), per-row "Ozempic n/N" bars, status-chip counts, `pointPrio`, `diagParas` narrative generator, `topSource` shares, Sources-tab `oppScore` and "play" ranking, action-queue demand-weighted ranking, campaign simulations, Agent Workbench, ANS_B64 preview loader. Numbers the spec asks for but platform_data.json does not carry are not shown: visibility by zone / topic group, benchmarking by zone, safety by target and unstable-cell list.
- **Status controls** on `#/actions` write to `localStorage` only and show a "not synced to registry" badge.
- Build is deterministic (identical md5 on two consecutive builds).
- **Post-review fixes.** (a) Breakdowns carried into `platform_data.json` under `breakdowns` (spec §2): visibility by zone and by topic group (added to step 2 with the headline's scope and equal family weights; headline and dashboard.json unchanged), benchmarking by zone, safety by target and the unstable-cell list; rendered on `#/visibility`, `#/competitors`, `#/safety`. (b) The map's data block moved out of `index.html` into `ui/map_data.js`, loaded when `#/map` opens, and the answer store is split by run into `ui/answers_R1.js … answers_R9.js` (the point view loads only its run) because the artifact publish ceiling is 16 MB per text file. index.html 10.36 MB. Published at https://claude.ai/code/artifact/4a0406f3-422b-4e01-a25d-b940730c1c11.
