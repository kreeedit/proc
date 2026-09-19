"""V8 + max_candidates at RECORD level, Herodotus x Thucydides (real scale)."""
import json
from pathlib import Path
d = json.loads(Path("herothuc.json").read_text(encoding="utf-8"))
fwd, rev = d["fwd"], d["rev"]

def key(r, swap=False):
    return (r["j"], r["i"]) if swap else (r["i"], r["j"])
def payload(r, swap=False):
    """The record's content, direction-normalized (i/j fields swapped back)."""
    if swap:
        return (r["chain_len"], r["matched_words_j"], r["matched_words"],
                r["n_chained"], r["word_range_j"], r["word_range_i"])
    return (r["chain_len"], r["matched_words"], r["matched_words_j"],
            r["n_chained"], r["word_range_i"], r["word_range_j"])

F = {key(r): r for r in fwd}
R = {key(r, True): r for r in rev}
sf, sr = set(F), set(R)
print("=== V8, record level (uncapped, so the cap is not a confound) ===")
print(f"  forward A->B : {len(fwd)} records from 3617 candidates")
print(f"  reverse B->A : {len(rev)} records from 8402 candidates")
print(f"  only forward : {len(sf-sr)}")
print(f"  only reverse : {len(sr-sf)}")
print(f"  in both      : {len(sf&sr)}   Jaccard = {len(sf&sr)/len(sf|sr):.4f}")
same = sum(1 for k in sf & sr if payload(F[k]) == payload(R[k], True))
print(f"  of the shared records, identical content (score excluded): {same}/{len(sf&sr)}")
diff = [k for k in sf & sr if payload(F[k]) != payload(R[k], True)]
for k in diff[:5]:
    print(f"    {k}: fwd {payload(F[k])}  rev {payload(R[k], True)}")
sc = sum(1 for k in sf & sr if F[k]["score"] != R[k]["score"])
print(f"  of the shared records, score differs: {sc}/{len(sf&sr)}")
big = [k for k in sr - sf if R[k]["chain_len"] >= 8]
print(f"  reverse-only records with chain >= 8 (i.e. reportable): {len(big)}")
print(f"  forward-only records with chain >= 8                  : "
      f"{sum(1 for k in sf-sr if F[k]['chain_len'] >= 8)}")
best_f = max(fwd, key=lambda r: r["chain_len"]); best_r = max(rev, key=lambda r: r["chain_len"])
print(f"  strongest forward: chain {best_f['chain_len']} {best_f['label_i']} x {best_f['label_j']}")
print(f"  strongest reverse: chain {best_r['chain_len']} {best_r['label_j']} x {best_r['label_i']}")

print("\n=== max_candidates at record level (forward direction) ===")
for cap in (1000, 4000, 10**9):
    sub = [r for r in fwd if r["rank"] < cap]
    tag = "uncapped" if cap > 10**6 else str(cap)
    print(f"  max_candidates={tag:>8s}: {len(sub):4d} records, "
          f"strongest chain {max((r['chain_len'] for r in sub), default=0)}, "
          f"chain>=8: {sum(1 for r in sub if r['chain_len']>=8)}")
r1 = {key(r) for r in fwd if r["rank"] < 1000}
r4 = {key(r) for r in fwd if r["rank"] < 4000}
print(f"  records present at 4000 but absent at 1000: {len(r4-r1)} "
      f"({100*len(r4-r1)/max(1,len(r4)):.1f}% of the 4000-run's records)")
lost = [F[k] for k in r4-r1]
if lost:
    print(f"    of those, chain>=8: {sum(1 for r in lost if r['chain_len']>=8)}, "
          f"max chain {max(r['chain_len'] for r in lost)}")
