# Dashboard assembly checks — cycle 1

- PASS **1. every shares triple sums to 100 ± 0.1** — checked 6 sentiment triples + citations pie; sums = {'sentiment.headline': 100.0, 'sentiment.narrative_resistance': 100.0, 'sentiment.combined_c2': 100.1, 'sentiment.headline.by_model.claude': 100.0, 'sentiment.headline.by_model.gemini': 100.0, 'sentiment.headline.by_model.gpt': 100.0}; pie = 99.9; off: none
- FAIL **2. visibility.by_model families = config families minus dropped** — config minus dropped = ['claude', 'gemini', 'gpt', 'grok', 'perplexity']; by_model = ['claude', 'gemini', 'gpt']; missing = ['grok', 'perplexity'] (these families have no answers in the headline scope R1 C1; scope-aware variant [families with answers in scope] = ['claude', 'gemini', 'gpt'] → PASS)
- PASS **3. benchmarking.leaderboard competitors ⊆ brands.yaml competitors** — leaderboard ['Farxiga', 'Invokana', 'Januvia', 'Jardiance', 'Mounjaro', 'Rybelsus', 'Saxenda', 'Trulicity', 'Victoza', 'Wegovy', 'Zepbound']; extra = none
- PASS **4. every prioritization recommendation group exists in prioritization_groups.csv** — missing = none
- PASS **5. every action_center.top3_open task_id exists in the registry** — top3 = ['c66030d94d01', '92361d73f3e1', '34099e60975f']; missing = none
- PASS **6. no safety_label.findings_list entry has signoff_status != confirmed** — findings_list has 0 entries (all pending findings filtered out); non-confirmed = none
- PASS **7. meta.answers = rows in answers.parquet (incl. excluded) − dropped models** — rows = 12314, dropped-model rows present in parquet = 0 (removed in step 1: ['gemini-3.6-flash']), meta.answers = 12314
- PASS **8. numbers rounded to 1 decimal only here** — max decimals in dashboard (excluding score-type keys kept at 6) = 1; upstream summaries keep 2+ decimals
