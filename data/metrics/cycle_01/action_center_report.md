# Action Center — cycle 1 (step 7)
Counters (client tasks, execution auto/manual): open 132 (auto 26, manual 106); in progress 0; done this cycle 0; dismissed 0. By who: Digital 81, Marketing + Medical 8, Medical + Digital 9, PR/Comms 12, Medical 8, Comms 8, Medical Affairs 2, Regulatory 4.
Citere tasks (own monitoring / re-check, excluded from client counters): 55. Label / Medical tasks held out of the queue while their findings await clinician sign-off: 2 (10 findings pending in label_findings_registry.json).
Impact: ceiling_pp = gap × lever × 100; expected_pp = ceiling × closure coefficients (basis: prior — owned 0.05–0.1, earned 0.1–0.22, commerce 0.1–0.22, comp_owned 0.1–0.22, ugc 0.05–0.15); Label rows have no expected_pp.
Top-3 open tasks:
1. Side effects & tolerability × LIVING ON THE DRUG → earned · P3 · manual · Digital — losing 79% of topic prompts (R2 dominant) · earned = 75% of citations — Ceiling: 60 pp · Expected: 6…13 pp (prior) · Topic demand ~247,764/month (Google, proxy)
2. Side effects & tolerability × WEIGHT LOSS → earned · P3 · manual · Digital — losing 72% of topic prompts (R2 dominant) · earned = 73% of citations — Ceiling: 53 pp · Expected: 5…12 pp (prior) · Topic demand ~160,011/month (Google, proxy)
3. Price, coverage & supply × Coupons & savings → earned · P3 · manual · Digital — losing 88% of topic prompts (R7 dominant) · earned = 70% of citations — Ceiling: 62 pp · Expected: 6…14 pp (prior) · Topic demand ~121,227/month (Google, proxy)
Registry: `data/registry/action_center_tasks.json` — 132 client + 55 citere + 2 held label tasks; task_id = sha1(group_id|owner)[:12]; status/dismiss_reason/cycle fields are never overwritten by computation.
Outputs: action_center_queue.csv (187 rows, open first then by score), action_center_summary.json.
