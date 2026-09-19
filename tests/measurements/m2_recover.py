"""Task 2: can max_candidates be RECOVERED from the released artefact?
Records per work pair are bounded above by max_candidates (one record per
chosen candidate at most)."""
import json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
recs = [json.loads(l) for l in (ROOT/"logs/text_reuse_matches.ndjson").read_text(encoding="utf-8").splitlines() if l]
c = Counter((r["work_i"], r["work_j"]) for r in recs)
top = c.most_common(12)
print("records per work pair — top 12:")
for k, n in top:
    print(f"  {n:6d}  {k[0]} x {k[1]}")
print(f"\nmax records on any pair : {max(c.values())}")
print(f"pairs at exactly 1000   : {sum(1 for v in c.values() if v == 1000)}")
print(f"pairs > 1000            : {sum(1 for v in c.values() if v > 1000)}")
print(f"pairs in 900..1000      : {sorted(v for v in c.values() if 900 <= v <= 1000)}")
print(f"pairs > 4000            : {sum(1 for v in c.values() if v > 4000)}")
print(f"total records           : {sum(c.values())}")
