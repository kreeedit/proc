"""V10 mechanism (fixed), V9 on the RELEASED data, V4 false-positive rate,
and the B-class _hashes speed-up."""
import sys, json, time, statistics, itertools
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
import find_text_reuse as H
from flame import flame_pure as F, bpe_pure as B

W = [("tlg0059.tlg030", ROOT/"engine/samples/plato_respublica_598.json"),
     ("tlg4036.tlg001", ROOT/"engine/samples/proclus_in_rem_publicam_101r.json")]
u1 = H.build_units(W[0][1], W[0][0]); u2 = H.build_units(W[1][1], W[1][0])
KW = dict(ngram=4, n_out=1, fuzz_threshold=0.75, min_chain_words=2, max_candidates=4000)

print("=== V10 mechanism: same unit pair, different call composition ===")
def score_of(units2, want="#65"):
    for ev in F.compare_iter(u1, units2, **KW):
        if ev.get("t") == "pair" and ev["pair"]["label_j"].endswith(want):
            return ev["pair"]["score"]
    return None
full = score_of(u2)
print(f"  baseline (all 95 j units)            -> {full}")
for cut in (90, 80, 70, 66):
    s = score_of(u2[:cut])
    print(f"  j side truncated to {cut:3d} units       -> {s}   delta={s-full:+.4f}")
# padding with unrelated units from the same work shifts it the other way
print(f"  j side = only units 60..70 (11 units) -> {score_of(u2[60:71])}")
print("  -> the record's `score` is a function of the whole CALL, not of the pair")

print("\n=== V9: is the released record order score-monotone within a work pair? ===")
recs = [json.loads(l) for l in (ROOT/"logs/text_reuse_matches.ndjson").read_text(encoding="utf-8").splitlines() if l]
by_pair = defaultdict(list)
for k, r in enumerate(recs):
    by_pair[(r["work_i"], r["work_j"])].append((k, r))
mono = nonmono = 0; worst = None
for key, items in by_pair.items():
    if len(items) < 2: continue
    sc = [r["score"] for _, r in items]
    if all(sc[i] >= sc[i+1] for i in range(len(sc)-1)):
        mono += 1
    else:
        nonmono += 1
        inv = sum(1 for i in range(len(sc)-1) if sc[i] < sc[i+1])
        if worst is None or inv > worst[1]: worst = (key, inv, len(sc))
print(f"  work pairs with >=2 records: {mono+nonmono}")
print(f"    score-monotone in file order : {mono}")
print(f"    NOT monotone                 : {nonmono}")
print(f"    worst pair: {worst[0]} — {worst[1]} inversions over {worst[2]} records")
# and: does chain_len order match file order?
cmono = sum(1 for key, items in by_pair.items() if len(items) >= 2 and
            all(items[i][1]["chain_len"] >= items[i+1][1]["chain_len"] for i in range(len(items)-1)))
print(f"    chain_len-monotone in file order: {cmono} of {mono+nonmono} "
      f"-> file order is NOT chain_len order either (it is shared-bigram rank)")

print("\n=== V4: fuzzy-match false-positive rate on the demo pair (live engine) ===")
U1 = {u[0]: u for u in F._units(u1)}; U2 = {u[0]: u for u in F._units(u2)}
tot = same = 0; diffs = Counter()
for ev in F.compare_iter(u1, u2, **KW):
    if ev.get("t") != "pair": continue
    p = ev["pair"]
    ni = U1[p["label_i"]][2]; nj = U2[p["label_j"]][2]
    raw = F._fuzzy_blocks(ni, nj, 0.75, 1)
    kept = [b for b in raw if b["core"] >= 4 and b["n"] >= 2]
    for b in kept:
        for wi, wj in b["matches"]:
            tot += 1
            if ni[wi] == nj[wj]: same += 1
            else: diffs[(ni[wi], nj[wj])] += 1
print(f"  matched word pairs in kept blocks: {tot};  identical: {same};  fuzzy: {tot-same} "
      f"({100*(tot-same)/tot:.1f}%)")
for (a, b), n in diffs.most_common():
    print(f"    {a} ~ {b}  x{n}  ratio={F.levenshtein_ratio(a,b):.4f}")
print("  what the core>=ngram filter removes: ", end="")
allb = sum(len(F._fuzzy_blocks(U1[k][2], U2[m][2], 0.75, 1)) for k in U1 for m in list(U2)[:20])
print(f"{allb} raw blocks on 3x20 unit pairs vs "
      f"{sum(1 for k in U1 for m in list(U2)[:20] for b in F._fuzzy_blocks(U1[k][2],U2[m][2],0.75,1) if b['core']>=4 and b['n']>=2)} kept")

print("\n=== B class: _hashes with precomputed powers (identical output, faster) ===")
def hashes_fast(int_tokens, base, ngram, n_out):
    if len(int_tokens) < ngram: return []
    if n_out <= 0:
        pw = [pow(base, p, F.MOD) for p in range(ngram)]
        return [sum(v*pw[p] for p, v in enumerate(int_tokens[i:i+ngram])) % F.MOD
                for i in range(len(int_tokens)-ngram+1)]
    keep = max(1, ngram - n_out)
    pw = [pow(base, p, F.MOD) for p in range(keep)]
    out = []
    for i in range(len(int_tokens)-ngram+1):
        for combo in itertools.combinations(int_tokens[i:i+ngram], keep):
            out.append(sum(v*pw[p] for p, v in enumerate(combo)) % F.MOD)
    return out
U = F._units(u2)
vocab = {}
for _,_,_,subs,_ in U:
    for s in subs: vocab.setdefault(s, len(vocab))
base = len(vocab)+1
toks = [[vocab[s] for s in subs] for _,_,_,subs,_ in U]
for ng, no in ((4,1),(4,0),(6,1)):
    t=time.time(); a=[F._hashes(t_,base,ng,no) for t_ in toks]; ta=time.time()-t
    t=time.time(); b=[hashes_fast(t_,base,ng,no) for t_ in toks]; tb=time.time()-t
    print(f"  ngram={ng} n_out={no}: identical={a==b}  orig={ta:.2f}s fast={tb:.2f}s "
          f"speedup={ta/max(tb,1e-9):.2f}x")
