"""Task 2 (max_candidates) + Task 3 (V8 direction dependence), candidate level,
on real Greek at production scale (Herodotus/Thucydides/Procopius, 1306-1953 units)."""
import sys, itertools, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
import cand as C

CORP = Path(__file__).resolve().parent/"corpus"
WORKS = [("tlg0016.tlg001","Herodotus"), ("tlg0003.tlg001","Thucydides"), ("tlg4029.tlg001","Procopius")]
paths = {w: next(CORP.glob(f"{w}__*.json")) for w,_ in WORKS}

norm = {}
for w,a in WORKS:
    t0=time.time()
    norm[w] = C.norm_units(H.build_units(paths[w], w))
    print(f"{a:11s} units={len(norm[w]):5d}  ({time.time()-t0:.1f}s)", flush=True)

print("\n%-26s %7s %7s %8s %8s %8s %8s" % ("pair","n1","n2","cand_fwd","cand_rev","dfc_fwd","dfc_rev"))
res={}
for (a,an),(b,bn) in itertools.combinations(WORKS,2):
    cf, dcf, _ = C.candidates(norm[a], norm[b])
    cr, dcr, _ = C.candidates(norm[b], norm[a])
    res[(a,b)]=(cf,cr)
    # symmetric comparison: transpose the reverse direction
    sf = set(cf); sr = {(j,i) for (i,j) in cr}
    print("%-26s %7d %7d %8d %8d %8d %8d" % (f"{an[:4]}x{bn[:4]}", len(norm[a]), len(norm[b]),
          len(cf), len(cr), dcf, dcr), flush=True)
    print("      set diff: only_fwd=%d only_rev=%d both=%d  jaccard=%.4f" %
          (len(sf-sr), len(sr-sf), len(sf&sr), len(sf&sr)/len(sf|sr)))
    # shared-count disagreement on the intersection
    dis = sum(1 for k in (sf&sr) if cf[k] != cr[(k[1],k[0])])
    print("      shared-count differs on %d of %d common pairs" % (dis, len(sf&sr)))
    for mc in (1000, 4000):
        rf = C.ranked(cf, mc); rr = C.ranked(cr, mc)
        print("      max_candidates=%5d -> fwd keeps %d (%.1f%% of %d), rev keeps %d" %
              (mc, len(rf), 100*len(rf)/max(1,len(cf)), len(cf), len(rr)))
    # how many of the top-4000 fwd are NOT in top-1000 fwd (= the records that differ)
    r1 = {k for k,_ in C.ranked(cf,1000)}; r4 = {k for k,_ in C.ranked(cf,4000)}
    print("      pairs present at 4000 but absent at 1000: %d" % len(r4-r1))
    print()
