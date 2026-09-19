"""Which symmetric df criterion keeps recall? Candidate level, real scale."""
import sys, itertools
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
from flame import flame_pure as F
import cand as C

def gen(n1n, n2n, mode, min_shared=3, wn=2):
    n1, n2 = len(n1n), len(n2n)
    g1 = [F._word_ngrams(w, wn) for w in n1n]
    g2 = [F._word_ngrams(w, wn) for w in n2n]
    inv = {}
    for j, gs in enumerate(g2):
        for g in set(gs): inv.setdefault(g, []).append(j)
    df1 = Counter()
    for gs in g1:
        for g in set(gs): df1[g] += 1
    if mode == "shipped":
        cap = max(40, int(0.04*n2)); skip = lambda g, p: len(p) > cap
    elif mode == "min":
        cap = max(40, int(0.04*min(n1,n2))); skip = lambda g, p: df1[g] > cap or len(p) > cap
    elif mode == "union":                     # df over the union of both sides
        cap = max(40, int(0.04*(n1+n2))); skip = lambda g, p: df1[g] + len(p) > cap
    elif mode == "rate":                      # per-side rate, symmetric under swap
        cap = 0.04; floor1 = max(40, int(cap*n1)); floor2 = max(40, int(cap*n2))
        skip = lambda g, p: df1[g] > floor1 and len(p) > floor2
    out = {}
    for i in range(n1):
        local = {}
        for g in set(g1[i]):
            p = inv.get(g)
            if not p or skip(g, p): continue
            for j in p: local[j] = local.get(j, 0) + 1
        for j, sh in local.items():
            if sh >= min_shared: out[(i, j)] = sh
    return out

CORP = Path(__file__).resolve().parent/"corpus"
W = [("tlg0016.tlg001","Hero"), ("tlg0003.tlg001","Thuc"), ("tlg4029.tlg001","Proc")]
norm = {w: C.norm_units(H.build_units(next(CORP.glob(f"{w}__*.json")), w)) for w,_ in W}
for (a,an),(b,bn) in itertools.combinations(W,2):
    print(f"--- {an} x {bn}  (n1={len(norm[a])}, n2={len(norm[b])})")
    base = set(gen(norm[a], norm[b], "shipped"))
    for mode in ("shipped","min","union","rate"):
        f = gen(norm[a], norm[b], mode); r = gen(norm[b], norm[a], mode)
        Sf, Sr = set(f), {(j,i) for (i,j) in r}
        agree = all(f[k] == r[(k[1],k[0])] for k in Sf & Sr)
        print(f"  {mode:8s} fwd={len(Sf):6d} rev={len(Sr):6d} "
              f"jaccard={len(Sf&Sr)/len(Sf|Sr):.4f} counts_agree={agree}  "
              f"vs shipped-fwd: kept={len(Sf&base)} lost={len(base-Sf)} gained={len(Sf-base)}")
