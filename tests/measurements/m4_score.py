"""V10: is the per-run-normalized `score` compared ACROSS work pairs anywhere
that feeds a paper number?  Measured on the released 35,753-record NDJSON and
on the WP score gates in scripts/filter_by_wp.py."""
import json, statistics
from collections import defaultdict, Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

recs = [json.loads(l) for l in (ROOT/"logs/text_reuse_matches.ndjson").read_text(encoding="utf-8").splitlines() if l]
print("records:", len(recs))
print("fields :", sorted(recs[0].keys()))
print("matched_words_j present:", sum(1 for r in recs if "matched_words_j" in r))
print("n_chained present     :", sum(1 for r in recs if "n_chained" in r))

by_pair = defaultdict(list)
for r in recs:
    by_pair[(r["work_i"], r["work_j"])].append(r)
print("work pairs with >=1 record:", len(by_pair))

# --- per-pair score scale: how differently are pairs scaled? ---
stats = []
for k, ms in by_pair.items():
    sc = [m["score"] for m in ms]
    stats.append((k, len(ms), min(sc), statistics.median(sc), max(sc)))
stats.sort(key=lambda t: -t[4])
print("\nper-pair score ranges (top 8 by max, bottom 5 by max):")
for k, n, lo, med, hi in stats[:8] + stats[-5:]:
    print(f"  {k[0]} x {k[1]:16s} n={n:6d}  min={lo:.4f} med={med:.4f} max={hi:.4f}")
maxes = [t[4] for t in stats]
print(f"\nmax-score per pair: min={min(maxes):.4f} max={max(maxes):.4f}  ratio={max(maxes)/max(1e-9,min(maxes)):.0f}x")

# --- the WP score gates are ABSOLUTE and applied across pairs ---
GATES = [("WP1 anc<->7th_8th",  {"ancient_classical","7th_8th"},  6, 0.001),
         ("WP2 anc<->9th_10th", {"ancient_classical","9th_10th"}, 6, 0.001),
         ("WP3 anc<->11th_12th",{"ancient_classical","11th_12th"},8, 0.01)]
print("\n--- effect of the absolute score gate (on the RAW ndjson, before the")
print("    tag/self-match filtering filter_by_wp does; upper bound on the gate's reach) ---")
for name, eras, cmin, smin in GATES:
    sel = [m for m in recs if {m["era_i"], m["era_j"]} == eras and m["author_i"] != m["author_j"]]
    after_chain = [m for m in sel if m["chain_len"] >= cmin]
    after_score = [m for m in after_chain if m["score"] >= smin]
    dropped = len(after_chain) - len(after_score)
    print(f"  {name:22s} era-pair={len(sel):6d}  chain>={cmin}: {len(after_chain):6d}  "
          f"+score>={smin}: {len(after_score):6d}   score gate drops {dropped} "
          f"({100*dropped/max(1,len(after_chain)):.1f}%)")
    # which work pairs lose records to the score gate only
    lost = Counter((m["work_i"], m["work_j"]) for m in after_chain if m["score"] < smin)
    if lost:
        print(f"     work pairs losing records to the score gate: {len(lost)} -> {lost.most_common(4)}")
