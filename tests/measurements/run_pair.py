"""Run the REAL engine on one work pair, uncapped, recording each emitted
record together with its candidate rank, so max_candidates=1000/4000 subsets
are exact without re-running."""
import sys, json, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
from flame import flame_pure as F
import cand as C

KW = dict(ngram=4, n_out=1, fuzz_threshold=0.75, min_chain_words=2)

def run(u1, u2, max_candidates=10**9, tag=""):
    t0 = time.time()
    recs, meta = [], None
    for ev in F.compare_iter(u1, u2, max_candidates=max_candidates, **KW):
        if ev["t"] == "meta":
            meta = ev
        elif ev["t"] == "pair":
            p = ev["pair"]
            recs.append({"i": p["i"], "j": p["j"],
                         "label_i": p["label_i"], "label_j": p["label_j"],
                         "chain_len": p["chain_len"], "matched_words": p["matched_words"],
                         "matched_words_j": len(p["matched_j"]),
                         "n_chained": p["n_chained"], "n_blocks": p["n_blocks"],
                         "word_range_i": p["word_range_i"], "word_range_j": p["word_range_j"],
                         "score": p["score"]})
    print(f"  [{tag}] cand={meta['n_candidates']} records={len(recs)} "
          f"vocab={meta['vocab_size']} auto_thr={meta['threshold']} used={meta['used_threshold']} "
          f"({time.time()-t0:.0f}s)", flush=True)
    return recs, meta

def rank_map(u1, u2):
    """(i,j) -> rank position in flame_pure's `ranked` list."""
    cd, _, _ = C.candidates(C.norm_units(u1), C.norm_units(u2))
    return {k: r for r, (k, _) in enumerate(C.ranked(cd, 10**9))}, cd
