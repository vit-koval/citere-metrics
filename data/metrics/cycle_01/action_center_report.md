# Action Center — cycle 1 (step 7)
Counters (client tasks, execution auto/manual): open 135 (auto 27, manual 108); in progress 0; done this cycle 0; dismissed 0. By who: Digital 81, Marketing + Medical 8, Medical + Digital 12, PR/Comms 12, Medical 8, Comms 8, Medical Affairs 2, Regulatory 4.
Citere tasks (own monitoring / re-check, excluded from client counters): 52. Label / Medical tasks held out of the queue while their findings await clinician sign-off: 2 (10 findings pending in label_findings_registry.json).
Impact: ceiling_pp = gap × lever × 100; expected_pp = ceiling × closure coefficients (basis: prior — owned 0.05–0.1, earned 0.1–0.22, commerce 0.1–0.22, comp_owned 0.1–0.22, ugc 0.05–0.15); Label rows have no expected_pp.
Top-3 open tasks:
1. Side effects & tolerability × LIVING ON THE DRUG → earned · P3 · manual · Digital — losing 76% of topic prompts (R7 dominant) · earned = 50% of citations — Ceiling: 38 pp · Expected: 4…8 pp (prior) · Topic demand ~247,764/month (Google, proxy)
2. Side effects & tolerability × small → earned · P3 · manual · Digital — losing 100% of topic prompts (R2 dominant) · earned = 45% of citations — Ceiling: 45 pp · Expected: 5…10 pp (prior) · Topic demand ~160,011/month (Google, proxy)
3. Side effects & tolerability × WEIGHT LOSS → earned · P3 · manual · Digital — losing 72% of topic prompts (R2 dominant) · earned = 49% of citations — Ceiling: 36 pp · Expected: 4…8 pp (prior) · Topic demand ~160,011/month (Google, proxy)
Registry: `data/registry/action_center_tasks.json` — 135 client + 52 citere + 2 held label tasks; task_id = sha1(group_id|owner)[:12]; status/dismiss_reason/cycle fields are never overwritten by computation.
Outputs: action_center_queue.csv (187 rows, open first then by score), action_center_summary.json.
