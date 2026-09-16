# platform_data checks — cycle 1

- PASS **1. 1,424 points joined; points_unmatched empty** — joined=1424, unmatched=[]
- PASS **2. every groups[].pids exists in points; every point has exactly one group_id** — pids listed=1424, unique=1424, points=1424
- PASS **3. every campaign fix_card_refs resolve; no TRACK card carries audience client** — bad refs=0, TRACK-as-client=0
- PASS **4. sum of groups[].n_prompts over all buckets = 1,424** — sum=1424 buckets={'healthy': 19, 'recommendation': 18, 'label': 2}
- PASS **5. dashboard block byte-identical to dashboard.json** — re-serialised with the step-8 settings and compared byte-for-byte
- PASS **6. export topic/subtopic/zone vs corpus mismatch count (>0 WARN, >50 STOP)** — mismatches=0 PASS
- PASS **7. spot check 20 random R1 points: we_present_share (and avg_position) identical to visibility_by_prompt.csv** — 20 points, tolerance 1e-9; mismatches=[]
