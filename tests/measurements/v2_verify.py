"""Verification of the v2 engine's three behavioural fixes, on real Greek at
production scale."""
import sys, itertools, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
from flame import flame_pure as F1, flame_pure_v2 as F2

CORP = Path(__file__).resolve().parent/"corpus"
W = [("tlg0016.tlg001","Herodotus"), ("tlg0003.tlg001","Thucydides"),
     ("tlg4029.tlg001","Procopius")]
units = {w: H.build_units(next(CORP.glob(f"{w}__*.json")), w) for w,_ in W}
KW = dict(ngram=4, n_out=1, fuzz_threshold=0.75, min_chain_words=2)

def cands(F, a, b, mc=10**9, **kw):
    m = next(ev for ev in F.compare_iter(a, b, max_candidates=mc, **KW, **kw)
             if ev["t"] == "meta")
    return m

print("=== FIX 1: direction independence (candidate level, uncapped) ===")
print("%-24s %10s %10s %10s %10s" % ("pair", "v1 fwd", "v1 rev", "v2 fwd", "v2 rev"))
for (a,an),(b,bn) in itertools.combinations(W,2):
    r = [cands(F1, units[a], units[b])["n_candidates"],
         cands(F1, units[b], units[a])["n_candidates"],
         cands(F2, units[a], units[b])["n_candidates"],
         cands(F2, units[b], units[a])["n_candidates"]]
    flag = "SYMMETRIC" if r[2] == r[3] else "STILL ASYMMETRIC"
    print("%-24s %10d %10d %10d %10d   v1 ratio %.2fx -> v2 %s"
          % (f"{an[:5]}x{bn[:5]}", *r, max(r[0],r[1])/min(r[0],r[1]), flag), flush=True)

print("\n=== FIX 2: corpus-level IDF -> one score scale for the whole sweep ===")
t0 = time.time()
idx = F2.build_corpus_index([units[w] for w,_ in W], ngram=4, n_out=1)
print(f"  build_corpus_index: {idx['n_works']} works, {idx['n_units']} units, "
      f"vocab {len(idx['vocab'])}, {time.time()-t0:.1f}s")

def top_scores(F, a, b, n=200, **kw):
    out = []
    for ev in F.compare_iter(units[a], units[b], max_candidates=n, **KW, **kw):
        if ev.get("t") == "pair":
            out.append(ev["pair"]["score"])
    return out

print("  per-pair score ranges (top-200 candidates each):")
print("  %-24s %-26s %-26s" % ("pair", "per-call IDF (v1 behaviour)", "corpus IDF (v2)"))
for (a,an),(b,bn) in itertools.combinations(W,2):
    s_call = top_scores(F2, a, b)
    s_corp = top_scores(F2, a, b, corpus_index=idx)
    f = lambda s: f"min={min(s):.5f} max={max(s):.5f}" if s else "n/a"
    print("  %-24s %-26s %-26s" % (f"{an[:5]}x{bn[:5]}", f(s_call), f(s_corp)), flush=True)

print("\n=== FIX 3: matched_words_j is emitted ===")
p = next(ev["pair"] for ev in F2.compare_iter(units["tlg0016.tlg001"],
         units["tlg0003.tlg001"], max_candidates=200, **KW) if ev.get("t") == "pair")
print(f"  sample record: matched_words={p['matched_words']} "
      f"matched_words_j={p['matched_words_j']}  (v1 emits neither name)")
