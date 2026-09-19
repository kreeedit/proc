import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/"engine"))
import find_text_reuse as H
import run_pair as R

CORP = Path(__file__).resolve().parent/"corpus"
A, B = "tlg0016.tlg001", "tlg0003.tlg001"   # Herodotus x Thucydides (smallest cand set)
ua = H.build_units(next(CORP.glob(f"{A}__*.json")), A)
ub = H.build_units(next(CORP.glob(f"{B}__*.json")), B)
print(f"Herodotus units={len(ua)}  Thucydides units={len(ub)}")

fwd, mf = R.run(ua, ub, tag="fwd A->B")
rev, mr = R.run(ub, ua, tag="rev B->A")
rmf, cf = R.rank_map(ua, ub)
rmr, cr = R.rank_map(ub, ua)
for r in fwd: r["rank"] = rmf[(r["i"], r["j"])]
for r in rev: r["rank"] = rmr[(r["i"], r["j"])]
# sanity: emitted order must be rank order
assert all(fwd[k]["rank"] <= fwd[k+1]["rank"] for k in range(len(fwd)-1)), "rank order mismatch fwd"
assert all(rev[k]["rank"] <= rev[k+1]["rank"] for k in range(len(rev)-1)), "rank order mismatch rev"
print("OK: emitted order == candidate rank order (reimplementation exact at scale)")
out = Path(__file__).resolve().parent/"herothuc.json"
out.write_text(json.dumps({"fwd": fwd, "rev": rev,
                           "meta_f": mf, "meta_r": mr}, ensure_ascii=False))
print("saved", out)
