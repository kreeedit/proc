"""V2,V3,V4,V5,V6,V7,V9,V10(mechanism),V11,V12 — micro measurements against the
byte-identical engine."""
import sys, json, random, difflib, itertools, statistics, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
import find_text_reuse as H
from flame import flame_pure as F, bpe_pure as B

print("=== V2: levenshtein_ratio vs its difflib docstring ===")
for a, b in [("abc","abd"), ("abc","abc"), ("abc","xyz"), ("a","b"), ("abcd","abce")]:
    d = difflib.SequenceMatcher(None, a, b).ratio()
    print(f"  {a!r:8s} {b!r:8s} flame={F.levenshtein_ratio(a,b):.4f}  difflib={d:.4f}  "
          f"{'SAME' if abs(F.levenshtein_ratio(a,b)-d)<1e-9 else 'DIFFERENT'}")
# the floor for equal-length strings
floors = {}
for L in range(1, 9):
    a = "a"*L; b = "b"*L
    floors[L] = F.levenshtein_ratio(a, b)
print("  equal-length, fully different -> ratio:", floors)
print("  claimed floor 0.0, measured floor:", set(floors.values()))
print("  empty/empty:", F.levenshtein_ratio("",""))

print("\n=== V3: what fuzz=0.75 admits ===")
pairs = [("το","τω"),("δε","τε"),("των","την"),("μεν","μην"),("103","104"),
         ("605","603"),("18","13"),("και","κατα"),("ο","η"),("εστι","εστιν")]
for a,b in pairs:
    r = F.levenshtein_ratio(F.normalize(a), F.normalize(b))
    print(f"  {a:7s} ~ {b:7s} ratio={r:.4f}  match@0.75={F._word_match(F.normalize(a),F.normalize(b),0.75)}")
# how many of the letters may differ at equal length?
print("  at equal length L, ratio = 1 - subs/(2L) -> passes 0.75 while subs <= L/2:")
for L in (2,3,4,6,8):
    mx = max(s for s in range(L+1) if 1 - s/(2*L) >= 0.75)
    print(f"    L={L}: up to {mx} of {L} letters may differ ({100*mx/L:.0f}%)")

print("\n=== V5: length-prune soundness (property test) ===")
random.seed(7)
alpha = "αβγδεζηθικλμνξοπρστυφχψω"
bad = 0; n = 40000
for _ in range(n):
    a = "".join(random.choice(alpha) for _ in range(random.randint(0,10)))
    b = "".join(random.choice(alpha) for _ in range(random.randint(0,10)))
    for th in (0.5, 0.6, 0.75, 0.9, 1.0):
        pruned = F._word_match(a, b, th)
        exact  = True if a == b else (True if len(a)+len(b) == 0 else F.levenshtein_ratio(a,b) >= th)
        if pruned != exact:
            bad += 1
            if bad < 5: print(f"  MISMATCH a={a!r} b={b!r} th={th} pruned={pruned} exact={exact}")
print(f"  {n} random pairs x 5 thresholds: {bad} disagreements with the unpruned predicate")

print("\n=== V6: block algebra on the live engine (demo pair, every raw block) ===")
W = [("tlg0059.tlg030", ROOT/"engine/samples/plato_respublica_598.json"),
     ("tlg4036.tlg001", ROOT/"engine/samples/proclus_in_rem_publicam_101r.json")]
u1 = H.build_units(W[0][1], W[0][0]); u2 = H.build_units(W[1][1], W[1][0])
U1 = F._units(u1); U2 = F._units(u2)
nb = 0; viol = 0
for a in U1:
    for b in U2:
        for blk in F._fuzzy_blocks(a[2], b[2], 0.75, 1):
            nb += 1
            iis = [m[0] for m in blk["matches"]]; jjs = [m[1] for m in blk["matches"]]
            ok = (len(set(iis)) == len(set(jjs)) == blk["n"]
                  and all(iis[k] < iis[k+1] for k in range(len(iis)-1))
                  and all(jjs[k] < jjs[k+1] for k in range(len(jjs)-1))
                  and len({j-i for i,j in blk["matches"]}) == 1)
            if not ok: viol += 1
print(f"  {nb} blocks examined, {viol} violations of "
      f"'strictly increasing 1:1 single-diagonal pairing'")

print("\n=== V7: cnt_j / matched_words_j in the engine output vs the release ===")
recs = [json.loads(l) for l in (ROOT/"logs/text_reuse_matches.ndjson").read_text(encoding="utf-8").splitlines() if l]
import re as _re
src = (ROOT/"engine/flame/flame_pure.py").read_text(encoding="utf-8")
print("  flame_pure computes cnt_j     :", "cnt_j = _snippet" in src.replace("  "," ") or "cnt_j" in src)
print("  flame_pure emits matched_words_j:", "matched_words_j" in src)
print("  emits matched_j map           :", '"matched_j"' in src)
print("  released records with matched_words_j:", sum(1 for r in recs if "matched_words_j" in r), f"of {len(recs)}")
# asymmetry measured live
asym = 0; tot = 0
for ev in F.compare_iter(u1, u2, ngram=4, n_out=1, fuzz_threshold=0.75,
                         min_chain_words=2, max_candidates=4000):
    if ev.get("t") != "pair": continue
    p = ev["pair"]; tot += 1
    if p["matched_words"] != len(p["matched_j"]): asym += 1
    print(f"    {p['label_i']} x {p['label_j']}: cnt_i={p['matched_words']} "
          f"cnt_j={len(p['matched_j'])} blocks={p['n_chained']}")
print(f"  i/j counts differ on {asym} of {tot} demo records")

print("\n=== V9: emission order vs score, and the unused auto_threshold ===")
evs = list(F.compare_iter(u1, u2, ngram=4, n_out=1, fuzz_threshold=0.75,
                          min_chain_words=2, max_candidates=4000))
meta = evs[0]; pairs = [e["pair"] for e in evs if e.get("t") == "pair"]
sc = [p["score"] for p in pairs]
print("  emitted scores in order :", sc)
print("  monotone non-increasing :", all(sc[k] >= sc[k+1] for k in range(len(sc)-1)))
print("  auto_threshold computed :", meta["threshold"], " used_threshold:", meta["used_threshold"])
print("  records that WOULD be dropped if auto_threshold were applied:",
      sum(1 for s in sc if s < meta["threshold"]), "of", len(sc))

print("\n=== V10 mechanism: IDF is per-call, so `score` is not cross-run comparable ===")
def score_of(units2):
    for ev in F.compare_iter(u1, units2, ngram=4, n_out=1, fuzz_threshold=0.75,
                             min_chain_words=2, max_candidates=4000):
        if ev.get("t") == "pair" and ev["pair"]["label_j"].endswith("#65"):
            return ev["pair"]["score"]
full = score_of(u2)
for cut in (95, 70, 40, 20):
    s = score_of(u2[:cut])
    print(f"  same unit pair, j side truncated to {cut:3d} units -> score {s}"
          + ("  (baseline)" if cut == 95 else f"  delta={s-full:+.4f}"))
print("  -> the record's `score` depends on which OTHER units were in the same call")

print("\n=== V11: silent clamping and CAP_WORDS ===")
m = next(ev for ev in F.compare_iter(u1, u2, ngram=99, n_out=99, fuzz_threshold=0.1,
                                     min_chain_words=0, max_candidates=4000)
        if ev["t"] == "meta")
print(f"  asked ngram=99 n_out=99 fuzz=0.1 min_chain=0 -> engine used "
      f"ngram={m['ngram']} n_out={m['n_out']} fuzz={m['fuzz_threshold']} "
      f"min_chain_words={m['min_chain_words']}  (no warning emitted)")
print(f"  CAP_WORDS={F.CAP_WORDS}, CAP_SECTIONS={F.CAP_SECTIONS}")
long_unit = [{"label": "x", "text": " ".join(["λογος"]*900)}]
print(f"  a 900-word unit -> engine keeps {len(F._units(long_unit)[0][1])} words "
      f"(silently truncated)")
print(f"  demo units over CAP_WORDS: {sum(1 for u in u1+u2 if len(u['text'].split())>F.CAP_WORDS)} "
      f"(windowing caps at {H.MAX_UNIT_WORDS}, so CAP_WORDS never bites in this harness)")

print("\n=== V12: bpe_pure.tokenize_words() before load() ===")
import importlib
B2 = importlib.reload(B)
print("  fresh module, _RANKS is None:", B2._RANKS is None)
print("  tokenize_words('λογος') BEFORE any load():", B2.tokenize_words("λογος")[1])
B2.load()
print("  tokenize_words('λογος') AFTER  load()      :", B2.tokenize_words("λογος")[1])
print("  cause: `ranks = ... (_RANKS or {})` on line", 
      [i+1 for i,l in enumerate((ROOT/'engine/flame/bpe_pure.py').read_text().splitlines())
       if "_RANKS or {}" in l and "merge_ranks" in l])
