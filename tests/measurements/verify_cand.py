import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
from flame import flame_pure as F
import cand as C

W = [("tlg0059.tlg030", ROOT/"engine/samples/plato_respublica_598.json"),
     ("tlg4036.tlg001", ROOT/"engine/samples/proclus_in_rem_publicam_101r.json")]
u1 = H.build_units(W[0][1], W[0][0]); u2 = H.build_units(W[1][1], W[1][0])
KW = dict(ngram=4, n_out=1, fuzz_threshold=0.75, min_chain_words=2, max_candidates=4000)
meta = next(ev for ev in F.compare_iter(u1, u2, **KW) if ev["t"] == "meta")
mine, dfc, sk = C.candidates(C.norm_units(u1), C.norm_units(u2))
print("engine meta n_candidates =", meta["n_candidates"])
print("reimpl  len(ranked@4000) =", len(C.ranked(mine, 4000)), " uncapped =", len(mine), " df_cap =", dfc)
assert len(C.ranked(mine,4000)) == meta["n_candidates"], "reimplementation MISMATCH"
print("OK: candidate reimplementation is exact")
