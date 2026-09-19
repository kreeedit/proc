"""C1 impact: symmetric df_cap — does it make direction irrelevant, and how
many candidate pairs change vs. the shipped asymmetric version?"""
import sys, itertools
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
from flame import flame_pure as F
import cand as C

def candidates_sym(n1_norm, n2_norm, min_shared=3, wn=2):
    """The C1 patch, in isolation: both sides capped, cap sized from min(n1,n2)."""
    n1, n2 = len(n1_norm), len(n2_norm)
    grams1 = [F._word_ngrams(w, wn) for w in n1_norm]
    grams2 = [F._word_ngrams(w, wn) for w in n2_norm]
    inv = {}
    for j, gs in enumerate(grams2):
        for g in set(gs): inv.setdefault(g, []).append(j)
    df1 = Counter()
    for gs in grams1:
        for g in set(gs): df1[g] += 1
    cap = max(40, int(0.04 * min(n1, n2)))
    out = {}
    for i in range(n1):
        local = {}
        for g in set(grams1[i]):
            if df1[g] > cap: continue
            p = inv.get(g)
            if not p or len(p) > cap: continue
            for j in p: local[j] = local.get(j, 0) + 1
        for j, sh in local.items():
            if sh >= min_shared: out[(i, j)] = sh
    return out, cap

CORP = Path(__file__).resolve().parent/"corpus"
WORKS = [("tlg0016.tlg001","Hero"), ("tlg0003.tlg001","Thuc"), ("tlg4029.tlg001","Proc")]
norm = {w: C.norm_units(H.build_units(next(CORP.glob(f"{w}__*.json")), w)) for w,_ in WORKS}

for (a,an),(b,bn) in itertools.combinations(WORKS,2):
    sf,_,_ = C.candidates(norm[a], norm[b]); sr,_,_ = C.candidates(norm[b], norm[a])
    yf,capf = candidates_sym(norm[a], norm[b]); yr,capr = candidates_sym(norm[b], norm[a])
    Sf=set(sf); Sr={(j,i) for (i,j) in sr}; Yf=set(yf); Yr={(j,i) for (i,j) in yr}
    print(f"{an}x{bn}")
    print(f"  shipped   : fwd={len(Sf):6d} rev={len(Sr):6d} jaccard={len(Sf&Sr)/len(Sf|Sr):.4f}"
          f"  shared-count agrees on {sum(1 for k in Sf&Sr if sf[k]==sr[(k[1],k[0])])}/{len(Sf&Sr)}")
    print(f"  C1 patch  : fwd={len(Yf):6d} rev={len(Yr):6d} jaccard={len(Yf&Yr)/len(Yf|Yr):.4f}"
          f"  shared-count agrees on {sum(1 for k in Yf&Yr if yf[k]==yr[(k[1],k[0])])}/{len(Yf&Yr)}"
          f"  cap={capf}/{capr}")
    print(f"  C1 vs shipped(fwd): kept={len(Yf&Sf)} lost={len(Sf-Yf)} gained={len(Yf-Sf)}"
          f"  -> {100*len(Sf^Yf)/len(Sf|Yf):.1f}% of the candidate set changes")
