import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
import find_text_reuse as H
from flame import flame_pure as F
CORP = Path(__file__).resolve().parent/"corpus"
ua = H.build_units(next(CORP.glob("tlg0016.tlg001__*.json")), "a")
ub = H.build_units(next(CORP.glob("tlg0003.tlg001__*.json")), "b")
t=time.time(); U1=F._units(ua[:200]); print(f"_units 200 units: {time.time()-t:.1f}s")
t=time.time(); U2=F._units(ub[:200]); print(f"_units 200 units: {time.time()-t:.1f}s")
vocab={}
for _,_,_,subs,_ in U1+U2:
    for s in subs:
        vocab.setdefault(s,len(vocab))
base=len(vocab)+1
t=time.time()
hs=[F._hashes([vocab[s] for s in subs],base,4,1) for _,_,_,subs,_ in U1]
print(f"_hashes 200 units: {time.time()-t:.1f}s  (hashes/unit={len(hs[0])})")
t=time.time()
for k in range(30):
    F._fuzzy_blocks(U1[k][2], U2[k][2], 0.75, 1)
print(f"_fuzzy_blocks x30: {time.time()-t:.2f}s -> {(time.time()-t)/30*1000:.0f} ms/pair")
