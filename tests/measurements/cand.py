"""Exact reimplementation of flame_pure's candidate-generation block
(flame_pure.py:372-393), used to count candidates without paying for matching.
Verified against the real engine's meta['n_candidates'] in verify_cand.py."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
from flame import flame_pure as F

def norm_units(sections):
    """u[2] (norm word lists) exactly as flame_pure._units builds them.
    BPE-independent: orig comes from the same \\b\\w+\\b regex either way."""
    return [u[2] for u in F._units(sections)]

def candidates(n1_norm, n2_norm, min_shared=3, wn=2):
    """Returns dict[(i,j)] = shared bigram count, plus df_cap used."""
    n2 = len(n2_norm)
    grams2 = [F._word_ngrams(w, wn) for w in n2_norm]
    inv = {}
    for j, gs in enumerate(grams2):
        for g in set(gs):
            inv.setdefault(g, []).append(j)
    df_cap = max(40, int(0.04 * n2))
    cand = {}
    skipped = 0
    for i in range(len(n1_norm)):
        local = {}
        for g in set(F._word_ngrams(n1_norm[i], wn)):
            posting = inv.get(g)
            if not posting:
                continue
            if len(posting) > df_cap:
                skipped += 1
                continue
            for j in posting:
                local[j] = local.get(j, 0) + 1
        for j, shared in local.items():
            if shared >= min_shared:
                cand[(i, j)] = shared
    return cand, df_cap, skipped

def ranked(cand, max_candidates):
    return sorted(cand.items(), key=lambda kv: kv[1], reverse=True)[:max_candidates]
