"""B class, measured: where the 8353.9 s actually goes, and which proposed
speed-ups are real."""
import sys, time, itertools
from functools import lru_cache
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
import find_text_reuse as H
from flame import flame_pure as F

CORP = Path(__file__).resolve().parent/"corpus"
ua = H.build_units(next(CORP.glob("tlg0016.tlg001__*.json")), "a")
ub = H.build_units(next(CORP.glob("tlg0003.tlg001__*.json")), "b")
U1 = F._units(ua[:60]); U2 = F._units(ub[:60])
pairs = [(U1[k][2], U2[k][2]) for k in range(60)]

n_calls = sum(len(a)*len(b) for a, b in pairs)
distinct = len({(x, y) for a, b in pairs for x in a for y in b})
print(f"_word_match calls over 60 unit pairs : {n_calls}")
print(f"distinct (word_i, word_j) arguments  : {distinct} ({100*distinct/n_calls:.1f}%)")

t = time.time()
for a, b in pairs: F._fuzzy_blocks(a, b, 0.75, 1)
t_orig = time.time() - t
print(f"\n_fuzzy_blocks as shipped             : {t_orig:.2f}s  ({t_orig/60*1000:.0f} ms/pair)")

# proposal 1: memoize the predicate (behaviour-preserving, pure function)
@lru_cache(maxsize=2_000_000)
def wm(a, b, th): return F._word_match(a, b, th)
def fuzzy_memo(ni, nj, threshold, n_out):
    old = F._word_match
    F._word_match = wm
    try: return F._fuzzy_blocks(ni, nj, threshold, n_out)
    finally: F._word_match = old
t = time.time()
out_memo = [fuzzy_memo(a, b, 0.75, 1) for a, b in pairs]
t_memo = time.time() - t
out_orig = [F._fuzzy_blocks(a, b, 0.75, 1) for a, b in pairs]
print(f"with a memoized _word_match          : {t_memo:.2f}s  "
      f"speedup {t_orig/t_memo:.2f}x   identical output: {out_memo == out_orig}")

# proposal 2: length-bucket the j side before building the matrix
def fuzzy_bucket(ni, nj, threshold, n_out):
    li, lj = len(ni), len(nj)
    if li == 0 or lj == 0: return []
    maxgap = {}
    M = []
    for i in range(li):
        a = ni[i]; la = len(a); row = []
        for j in range(lj):
            b = nj[j]; lb = len(b)
            if a == b: row.append(True); continue
            tot = la + lb
            if tot == 0: row.append(True); continue
            if abs(la-lb) > (1.0-threshold)*tot: row.append(False); continue
            row.append(F.levenshtein_ratio(a, b) >= threshold)
        M.append(row)
    return M
t = time.time()
for a, b in pairs: fuzzy_bucket(a, b, 0.75, 1)
t_inline = time.time() - t
print(f"with the predicate inlined (matrix)  : {t_inline:.2f}s  speedup {t_orig/t_inline:.2f}x")

print(f"\nExtrapolation to the reported sweep (8353.9 s over 406 pairs):")
print(f"  memoized predicate would save roughly {100*(1-t_memo/t_orig):.0f}% of the")
print(f"  matching time, i.e. ~{8353.9*(1-t_memo/t_orig):.0f} s of the 8353.9 s "
      f"(upper bound: matching dominates the run).")
