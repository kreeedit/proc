"""FIX 2 verified sharply: with a corpus index, the same unit pair's score no
longer depends on what else was in the call.

This is the exact measurement of AUDIT finding 5, re-run against v2."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
import find_text_reuse as H
from flame import flame_pure as F1, flame_pure_v2 as F2
S = ROOT/"engine/samples"
u1 = H.build_units(S/"plato_respublica_598.json", "a")
u2 = H.build_units(S/"proclus_in_rem_publicam_101r.json", "b")
KW = dict(ngram=4, n_out=1, fuzz_threshold=0.75, min_chain_words=2,
          max_candidates=4000)

def score(F, units2, **kw):
    for ev in F.compare_iter(u1, units2, **KW, **kw):
        if ev.get("t") == "pair" and ev["pair"]["label_j"].endswith("#65"):
            return ev["pair"]["score"]

# The corpus index is built ONCE from the whole corpus; the calls below then
# see different slices of it, exactly as a sweep's work pairs do.
idx = F2.build_corpus_index([u1, u2], ngram=4, n_out=1)

print("same unit pair (598/#3 x 101r#65), different call composition:")
print("%-28s %-12s %-12s %-12s" % ("j side", "v1", "v2 per-call", "v2 corpus idf"))
base = None
for cut, label in ((95, "all 95 units"), (90, "first 90"), (80, "first 80"),
                   (66, "first 66")):
    a = score(F1, u2[:cut])
    b = score(F2, u2[:cut])
    c = score(F2, u2[:cut], corpus_index=idx)
    if base is None:
        base = c
    print("%-28s %-12.4f %-12.4f %-12.4f%s"
          % (label, a, b, c, "" if c == base else "   <-- CHANGED"))
print()
vals = {score(F2, u2[:c], corpus_index=idx) for c in (95, 90, 80, 66)}
print(f"v2 with corpus index — distinct scores across the 4 calls: {len(vals)} "
      f"({'invariant' if len(vals) == 1 else 'NOT invariant'})")
vals1 = {score(F1, u2[:c]) for c in (95, 90, 80, 66)}
print(f"v1                   — distinct scores across the 4 calls: {len(vals1)}")

# and the feature vector itself: is unit a_0's TF-IDF vector call-invariant?
print("\nunderlying cause, checked directly: is a unit's TF-IDF vector the same")
print("in two different calls?")
def vec(F, units2, **kw):
    """Rebuild what the engine builds for u1[0], via its own helpers."""
    U1 = F._units(u1); U2 = F._units(units2)
    ci = kw.get("corpus_index")
    if ci:
        vocab, base_, oov, idf = ci["vocab"], ci["base"], ci["oov"], ci["idf"]
        cnt = [F.Counter(F._hashes([vocab.get(s, oov) for s in subs], base_, 4, 1))
               for _, _, _, subs, _ in U1 + U2]
    else:
        vocab = {}
        for _, _, _, subs, _ in U1 + U2:
            for s in subs:
                vocab.setdefault(s, len(vocab))
        base_ = len(vocab) + 1
        cnt = [F.Counter(F._hashes([vocab[s] for s in subs], base_, 4, 1))
               for _, _, _, subs, _ in U1 + U2]
        idf = F._idf(cnt)
    return F._tfidf(cnt[0], idf)
for tag, kw in (("v1 / v2 per-call", {}), ("v2 corpus index", {"corpus_index": idx})):
    a = vec(F2, u2, **kw); b = vec(F2, u2[:66], **kw)
    print(f"  {tag:18s}: identical = {a == b}")
