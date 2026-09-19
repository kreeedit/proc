"""v2 vs v1 at RECORD level, uncapped, both directions — Herodotus x Thucydides.

Answers two things the candidate counts cannot:
  * does the symmetric pruning make the *record set* direction-free?
  * what does it cost or gain in recall against the shipped engine?
Slow (~50 min): three uncapped runs of a 1,609 x 1,306-window pair.
"""
import sys, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
from flame import flame_pure as F1, flame_pure_v2 as F2

KW = dict(ngram=4, n_out=1, fuzz_threshold=0.75, min_chain_words=2)
CORP = Path(__file__).resolve().parent / "corpus"
A, B = "tlg0016.tlg001", "tlg0003.tlg001"
ua = H.build_units(next(CORP.glob(f"{A}__*.json")), A)
ub = H.build_units(next(CORP.glob(f"{B}__*.json")), B)


def run(F, x, y, tag, **kw):
    t0 = time.time()
    recs = []
    for ev in F.compare_iter(x, y, max_candidates=10**9, **KW, **kw):
        if ev.get("t") == "pair":
            p = ev["pair"]
            recs.append({"i": p["i"], "j": p["j"], "chain_len": p["chain_len"],
                         "matched_words": p["matched_words"],
                         "n_chained": p["n_chained"],
                         "word_range_i": p["word_range_i"],
                         "word_range_j": p["word_range_j"]})
    print(f"  [{tag}] {len(recs)} records ({time.time() - t0:.0f}s)", flush=True)
    return recs


out = {"v1_fwd": run(F1, ua, ub, "v1 fwd"),
       "v2_fwd": run(F2, ua, ub, "v2 fwd"),
       "v2_rev": run(F2, ub, ua, "v2 rev")}
(Path(__file__).resolve().parent / "v2_records.json").write_text(
    json.dumps(out), encoding="utf-8")
print("saved v2_records.json")
