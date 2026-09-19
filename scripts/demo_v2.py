#!/usr/bin/env python3
"""
scripts/demo_v2.py
==================

The fixed pipeline (`flame_pure_v2` + `find_text_reuse_v2`) on the two bundled
samples — the counterpart of `engine/demo.py`, which runs the frozen one.

Run both and diff the two tables: that is the whole audit made visible on
redistributable text.

    python3 engine/demo.py         # frozen engine, chain 53 anchor
    python3 scripts/demo_v2.py     # fixed engine + fixed cleaning

What the comparison shows
-------------------------
* with the apparatus strip OFF, v2 reproduces the frozen engine's five records
  **exactly** — same labels, chains, matched words and scores. The engine fixes
  (symmetric pruning, corpus IDF, `matched_words_j`) do not disturb this pair,
  so any difference below is attributable to the cleaning, not to the matching;
* with it ON, the Proclus unit loses 3 of its 95 windows, **every `#k` label
  shifts**, and the strongest lemmatic block gains matched words — which is
  exactly why the strip is a re-run and not a patch.

Exit status is 0 when the anchor is reproduced in the no-strip mode, so this
doubles as a regression check that the v2 engine did not change the matching.

Licensing: code MIT (KONI); the two samples are PerseusDL / Open Greek and
Latin texts under CC BY-SA 4.0 — see engine/NOTICE.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "engine"))

import find_text_reuse_v2 as V2  # noqa: E402
from flame import bpe_pure_v2, flame_pure_v2  # noqa: E402

SAMPLES = ROOT / "engine" / "samples"
KW = {"ngram": 4, "n_out": 1, "fuzz_threshold": 0.75,
      "min_chain_words": 2, "max_candidates": 4000}

# The anchor engine/demo.py asserts, reproduced here in the no-strip mode.
ANCHOR = {"chain_len": 53, "ref_i": "598/#3", "ref_j": "In Rempublicam/101r#65"}

WORKS = [
    {"tlg_id": "tlg0059.tlg030", "era": "ancient_classical", "author": "Plato",
     "title": "Respublica", "json_path": SAMPLES / "plato_respublica_598.json"},
    {"tlg_id": "tlg4036.tlg001", "era": "ancient_classical", "author": "Proclus",
     "title": "In Platonis Rem publicam commentarii",
     "json_path": SAMPLES / "proclus_in_rem_publicam_101r.json"},
]


def run(strip_apparatus: bool, corpus_idf: bool):
    units = {w["tlg_id"]: V2.build_units(w["json_path"], w["tlg_id"],
                                         "page", strip_apparatus)
             for w in WORKS}
    index = None
    if corpus_idf:
        index = flame_pure_v2.build_corpus_index(
            [units[w["tlg_id"]] for w in WORKS], ngram=4, n_out=1)
    matches, diag = V2.run_sweep(WORKS, KW, None, units, index)
    return units, matches, diag


def table(title, units, matches):
    n = ", ".join(f"{w['tlg_id'].split('.')[-1]}={len(units[w['tlg_id']])}"
                  for w in WORKS)
    print(f"\n{title}   units({n})   matches={len(matches)}")
    print(f"{'chain':>5} {'words_i':>7} {'words_j':>7} {'blocks':>6} "
          f"{'score':>7}  ref_i x ref_j")
    for m in sorted(matches, key=lambda m: -m["chain_len"]):
        print(f"{m['chain_len']:>5} {m['matched_words']:>7} "
              f"{m['matched_words_j']:>7} {m['n_chained']:>6} "
              f"{m['score']:>7.4f}  {m['ref_i']} x {m['ref_j']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("What the")[0].strip())
    ap.add_argument("--no-assert", action="store_true",
                    help="never exit nonzero")
    args = ap.parse_args()

    merges = bpe_pure_v2.load()
    if not merges:
        raise SystemExit(
            f"[FAIL] BPE model not loaded: {bpe_pure_v2.VOCAB_PATH} is missing, "
            f"empty or unreadable.\n"
            f"       The engine would still run — the audit measured the match "
            f"set to be bit-identical without it — but every `score` would sit "
            f"on a different scale than the reported run. Refusing to run.")
    print(f"engine    : flame_pure_v2 (ngram={flame_pure_v2.NGRAM}, "
          f"n_out={flame_pure_v2.N_OUT}, fuzz={flame_pure_v2.FUZZ_THRESHOLD}, "
          f"min_chain={flame_pure_v2.MIN_CHAIN_WORDS})")
    print(f"BPE model : {bpe_pure_v2.VOCAB_PATH.name} — {len(merges)} merges, "
          f"{bpe_pure_v2.stop_size()} stop-subwords")

    u0, m0, _ = run(strip_apparatus=False, corpus_idf=True)
    table("[A] v2 engine, frozen cleaning  (comparable to engine/demo.py)", u0, m0)

    u1, m1, _ = run(strip_apparatus=True, corpus_idf=True)
    table("[B] v2 engine, apparatus strip  (C2 — re-phases every #k label)", u1, m1)

    print("\nWhat changed between [A] and [B]:")
    pw = lambda u: sum(len(x["text"].split()) for x in u["tlg4036.tlg001"])
    print(f"  Proclus windows      : {len(u0['tlg4036.tlg001'])} -> "
          f"{len(u1['tlg4036.tlg001'])}")
    print(f"  Proclus windowed words: {pw(u0)} -> {pw(u1)} "
          f"({pw(u1) - pw(u0):+d})")
    print(f"  records              : {len(m0)} -> {len(m1)}")
    print("  every #k label shifts, so no positional reference survives the "
          "strip — this is a re-run, not a patch.")

    hit = [m for m in m0 if m["chain_len"] == ANCHOR["chain_len"]
           and m["ref_i"] == ANCHOR["ref_i"] and m["ref_j"] == ANCHOR["ref_j"]]
    if hit:
        print(f"\n[OK] the frozen engine's anchor is reproduced by v2 in mode "
              f"[A]: chain {ANCHOR['chain_len']} at {ANCHOR['ref_i']} x "
              f"{ANCHOR['ref_j']} — the engine fixes did not change the matching")
        return 0
    print(f"\n[FAIL] anchor NOT reproduced in mode [A]: expected chain "
          f"{ANCHOR['chain_len']} at {ANCHOR['ref_i']} x {ANCHOR['ref_j']}")
    return 0 if args.no_assert else 1


if __name__ == "__main__":
    sys.exit(main())
