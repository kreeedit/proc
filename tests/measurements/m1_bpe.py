"""V1: does the BPE model affect the MATCH SET, or only `score`?

Two levels of evidence:
  (a) structural  — which inputs of each stage depend on the BPE model at all
  (b) empirical   — trained vs. untrained run, records compared field-by-field
                    with `score` excluded, on the demo pair AND on a real
                    production-scale Greek pair.
"""
import sys, json, itertools
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_text_reuse as H
from flame import flame_pure as F, bpe_pure as B
import cand as C

KW = dict(ngram=4, n_out=1, fuzz_threshold=0.75, min_chain_words=2)

def set_trained(on: bool):
    """Flip the engine between the trained and the degraded (no-model) branch."""
    if on:
        B._MERGES = None; B._STOP = None; B._RANKS = None
        B.load(force=True)
    else:
        B._MERGES = []; B._STOP = set(); B._RANKS = {}
    return B.is_trained()

def run(u1, u2, max_candidates, sim=None):
    recs, meta = [], None
    kw = dict(KW)
    if sim is not None:
        kw["similarity_threshold"] = sim
    for ev in F.compare_iter(u1, u2, max_candidates=max_candidates, **kw):
        if ev["t"] == "meta": meta = ev
        elif ev["t"] == "pair":
            p = ev["pair"]
            recs.append({k: p[k] for k in ("i","j","label_i","label_j","chain_len",
                "matched_words","n_chained","n_blocks","word_range_i","word_range_j",
                "snippet_i","snippet_j")} | {"matched_words_j": len(p["matched_j"]),
                "matched_i_keys": sorted(p["matched_i"]), "matched_j_keys": sorted(p["matched_j"]),
                "bridges_i": sorted(p["bridges_i"].items()), "score": p["score"]})
    return recs, meta

def compare(a, b, label):
    print(f"\n  --- {label}: {len(a)} vs {len(b)} records")
    if len(a) != len(b):
        print("     RECORD COUNT DIFFERS -> BPE changes the match set"); return False
    nsame_wo_score = 0; nscore_diff = 0; fields_diff = set()
    for ra, rb in zip(a, b):
        sa = {k:v for k,v in ra.items() if k != "score"}
        sb = {k:v for k,v in rb.items() if k != "score"}
        if sa == sb: nsame_wo_score += 1
        else:
            fields_diff |= {k for k in sa if sa[k] != sb[k]}
        if ra["score"] != rb["score"]: nscore_diff += 1
    print(f"     identical ignoring score : {nsame_wo_score}/{len(a)}")
    print(f"     score differs            : {nscore_diff}/{len(a)}")
    if fields_diff: print(f"     DIFFERING NON-SCORE FIELDS: {sorted(fields_diff)}")
    return nsame_wo_score == len(a)

# ---------- (a) structural check ----------
print("=== (a) structural: which stage inputs depend on the BPE model? ===")
W = [("tlg0059.tlg030", ROOT/"engine/samples/plato_respublica_598.json"),
     ("tlg4036.tlg001", ROOT/"engine/samples/proclus_in_rem_publicam_101r.json")]
u1 = H.build_units(W[0][1], W[0][0]); u2 = H.build_units(W[1][1], W[1][0])
set_trained(True);  t1 = F._units(u2)
set_trained(False); t0 = F._units(u2)
print("  orig word lists identical (u[1]) :", all(a[1] == b[1] for a, b in zip(t1, t0)))
print("  norm word lists identical (u[2]) :", all(a[2] == b[2] for a, b in zip(t1, t0)))
print("  subword lists identical   (u[3]) :", all(a[3] == b[3] for a, b in zip(t1, t0)))
print("  labels identical          (u[0]) :", all(a[0] == b[0] for a, b in zip(t1, t0)))
set_trained(True)
cd_t, _, _ = C.candidates([x[2] for x in t1], [x[2] for x in t1])
set_trained(False)
cd_u, _, _ = C.candidates([x[2] for x in t0], [x[2] for x in t0])
print("  candidate dict identical         :", cd_t == cd_u,
      f"(and its iteration order: {list(cd_t) == list(cd_u)})")

# ---------- (b) empirical ----------
print("\n=== (b) empirical: demo pair (Plato 598 x Proclus 101r), max_candidates=4000 ===")
print("  trained  :", set_trained(True));  a, ma = run(u1, u2, 4000)
print("  untrained:", set_trained(False)); b, mb = run(u1, u2, 4000)
ok_demo = compare(a, b, "demo pair")
print(f"     vocab_size trained={ma['vocab_size']} untrained={mb['vocab_size']}  "
      f"n_candidates {ma['n_candidates']}/{mb['n_candidates']}  "
      f"auto_threshold {ma['threshold']}/{mb['threshold']}")
print("     scores trained  :", [r["score"] for r in a])
print("     scores untrained:", [r["score"] for r in b])

# ---------- (c) the one code path where BPE WOULD gate ----------
print("\n=== (c) counterfactual: similarity_threshold > 0 (NOT reachable from the harness) ===")
for sim in (0.0, 0.25):
    print(f"  similarity_threshold={sim}")
    set_trained(True);  x, _ = run(u1, u2, 4000, sim=sim)
    set_trained(False); y, _ = run(u1, u2, 4000, sim=sim)
    print(f"     trained -> {len(x)} records, untrained -> {len(y)} records")

# ---------- (d) real production-scale pair ----------
CORP = Path(__file__).resolve().parent/"corpus"
A, Bw = "tlg0016.tlg001", "tlg0003.tlg001"
ua = H.build_units(next(CORP.glob(f"{A}__*.json")), A)
ub = H.build_units(next(CORP.glob(f"{Bw}__*.json")), Bw)
MC = 400   # keep the run tractable; the cap is applied identically in both branches
print(f"\n=== (d) real scale: Herodotus({len(ua)} units) x Thucydides({len(ub)} units), "
      f"max_candidates={MC} ===")
print("  trained  :", set_trained(True));  a2, m2a = run(ua, ub, MC)
print("  untrained:", set_trained(False)); b2, m2b = run(ua, ub, MC)
ok_real = compare(a2, b2, "Herodotus x Thucydides")
print(f"     vocab_size trained={m2a['vocab_size']} untrained={m2b['vocab_size']}")
import statistics as st
sa = [r["score"] for r in a2]; sb = [r["score"] for r in b2]
if sa:
    print(f"     score mean trained={st.fmean(sa):.4f} untrained={st.fmean(sb):.4f}; "
          f"max {max(sa):.4f}/{max(sb):.4f}")
    # does the score ORDER change? (relevant to any cross-record use of score)
    ra = sorted(range(len(sa)), key=lambda k: -sa[k]); rb = sorted(range(len(sb)), key=lambda k: -sb[k])
    print(f"     score ranking identical  : {ra == rb}")
set_trained(True)
print(f"\nVERDICT  demo pair match set BPE-independent: {ok_demo}")
print(f"VERDICT  real-scale match set BPE-independent: {ok_real}")
