#!/usr/bin/env python3
"""
engine/demo.py
==============

Runnable, self-contained demonstration of the text-reuse engine that produced the
paper's sweep — on **redistributable** text, with no TLG data and no third-party
packages.

What it does
------------
Runs the production code path end to end on two bundled samples:

    engine/samples/plato_respublica_598.json          (Plato, Respublica 598)
    engine/samples/proclus_in_rem_publicam_101r.json  (Proclus, In Remp., unit In Rempublicam/101r)

    1. build_units()      — the production corpus-JSON -> comparison-unit step
    2. run_sweep()        — the production all-pairs driver over the engine
    3. write_ndjson/tsv/markdown() — the production writers

Those samples are the two corpus units of the strongest cross-author
correspondence in the released match data (logs/text_reuse_matches.ndjson), so
the run is a **verifiable reproduction**, not an illustration: the demo asserts
that the chain of 53 words at `598/#3` x `In Rempublicam/101r#65` comes back out.
(The manuscript itself cites other Proclus loci, so "strongest in the data" is
not a claim about its role in the argument.)

Usage
-----
    python engine/demo.py                 # run, write engine/demo_out/, exit 0 on match
    python engine/demo.py --out-dir /tmp/x
    python engine/demo.py --no-assert     # report only, never exit nonzero

Exit status is 0 only if the expected anchor match is reproduced (unless
--no-assert), so this doubles as a smoke test of the shipped engine.

Licensing: code MIT (KONI) — see LICENSE / NOTICE.md. The two samples are
PerseusDL / Open Greek and Latin texts under CC BY-SA 4.0; see NOTICE.md.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

import find_text_reuse as H  # noqa: E402  (production harness, imported as a library)
from flame import bpe_pure, flame_pure  # noqa: E402

SAMPLES_DIR = ENGINE_DIR / "samples"

# The strongest cross-author correspondence in the released match data
# (logs/text_reuse_matches.ndjson: chain of 53 words; next best cross-author is 51).
ANCHOR = {"chain_len": 53, "matched_words": 53,
          "ref_i": "598/#3", "ref_j": "In Rempublicam/101r#65"}

# Sweep parameters used by this demo.  ngram/n_out/fuzz/min_chain are the values
# recorded for the reported run; max_candidates is the CODE DEFAULT (4000) and was
# NOT recoverable from that run's artefacts — see README.md, "One parameter is not
# pinned down".  Nothing here should be read as the production value.
KW = {"ngram": 4, "n_out": 1, "fuzz_threshold": 0.75,
      "min_chain_words": 2, "max_candidates": 4000}

WORKS = [
    {"tlg_id": "tlg0059.tlg030", "era": "ancient_classical", "author": "Plato",
     "title": "Respublica", "json_path": SAMPLES_DIR / "plato_respublica_598.json"},
    {"tlg_id": "tlg4036.tlg001", "era": "ancient_classical", "author": "Proclus",
     "title": "In Platonis Rem publicam commentarii",
     "json_path": SAMPLES_DIR / "proclus_in_rem_publicam_101r.json"},
]


def _samples_ref() -> str:
    """A korpusz-verzió hivatkozási pontja ehhez a demóhoz.

    A kiadás nem tartalmazza a `corpus_manifest.yaml`-t, ezért a fejlécbe a
    két minta együttes hash-e kerül — így egy régi és egy új demó-riport
    megkülönböztethető (az era-címkék és az offszetek változása is ezen
    keresztül látszik)."""
    h = hashlib.sha256()
    for w in WORKS:
        h.update(w["json_path"].read_bytes())
    return (f"bundled samples sha256 {h.hexdigest()[:16]}… — this package ships no "
            f"corpus_manifest.yaml; the full sweep's manifest hash is in the release "
            f"README")


def check_engine_ready() -> None:
    """Fail loudly if the BPE model is missing or unreadable.

    The engine degrades SILENTLY when the model is absent: bpe_pure.load() falls
    back to empty merges and flame_pure switches to plain normalized-word hashing
    (no subword tokenization, no stop-word filtering) while still returning
    plausible-looking matches. A reviewer must never see that state, so this
    checks it explicitly instead of trusting the run."""
    merges = bpe_pure.load()
    if not merges:
        raise SystemExit(
            f"[FAIL] BPE model not loaded: {bpe_pure.VOCAB_PATH} is missing, "
            f"empty or unreadable.\n"
            f"       The engine would still run, but with silent degradation "
            f"(no subword tokenization). Refusing to run the demo.")
    print(f"engine    : {flame_pure.__name__} "
          f"(ngram={flame_pure.NGRAM}, n_out={flame_pure.N_OUT}, "
          f"fuzz={flame_pure.FUZZ_THRESHOLD}, "
          f"min_chain={flame_pure.MIN_CHAIN_WORDS})")
    print(f"BPE model : {bpe_pure.VOCAB_PATH.name} — {len(merges)} merges, "
          f"{bpe_pure.stop_size()} stop-subwords, is_trained={bpe_pure.is_trained()}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("What it does")[0].strip())
    ap.add_argument("--out-dir", default=str(ENGINE_DIR / "demo_out"),
                    help="output directory for the NDJSON/TSV/Markdown artefacts")
    ap.add_argument("--no-assert", action="store_true",
                    help="do not exit nonzero when the anchor match is absent")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    check_engine_ready()

    print(f"samples   : {len(WORKS)} works")
    for w in WORKS:
        try:
            ok = w["json_path"].is_file()
        except OSError as e:  # unreadable parent dir -> a diagnosable failure, not a traceback
            raise SystemExit(f"[FAIL] sample not readable: {w['json_path']} ({e})")
        if not ok:
            raise SystemExit(f"[FAIL] sample missing: {w['json_path']}")

    flame = H.load_flame()  # bundled engine/flame/ (no KONI checkout needed)
    matches = H.run_sweep(WORKS, flame, KW, limit_pairs=None)

    outputs = (out_dir / "demo_matches.ndjson",
               out_dir / "demo_matches.tsv",
               out_dir / "demo_report.md")
    # A `write_text()` nem feltétlenül fut le: egy korai `return` a
    # `write_markdown()` belsejében némán üres kézzel hagyta a futást, a demo
    # pedig sikeresnek jelentette magát.  A puszta létezés-ellenőrzés viszont
    # NEM elég: egy KORÁBBI futásból ottmaradt fájl pontosan ugyanígy átmegy
    # rajta — az eredeti hiba épp az volt, hogy a régi artefakt a helyén maradt.
    # Ezért a FRISSESSÉGRE megyünk: a kezdés előtt rögzítjük az mtime-okat, és
    # megköveteljük, hogy minden kimenet ezután íródott, nem üres, és nem
    # bit-azonos a futás előtti tartalmával.
    t0 = time.time()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        H.write_ndjson(matches, outputs[0])
        H.write_tsv(matches, outputs[1])
        H.write_markdown(matches, WORKS, outputs[2], 10, KW, 6,
                         manifest_ref=_samples_ref(), scope=H.DEMO_SCOPE)
        stale = [f.name for f in outputs
                 if not f.is_file() or f.stat().st_size == 0
                 # 2 s ráhagyás a fájlrendszer időbélyeg-granularitására
                 or f.stat().st_mtime < t0 - 2.0]
        if stale:
            raise SystemExit(
                f"[FAIL] writer produced no fresh output: {', '.join(stale)} "
                f"(the file is missing, empty, or predates this run)")
    except OSError as e:
        # mkdir(exist_ok=True) succeeds silently on an existing read-only
        # directory, so the failure surfaces on the first write; catch it here
        # too, or the demo dies with a traceback instead of a diagnosable line.
        raise SystemExit(f"[FAIL] output directory not writable: {out_dir} ({e})")

    print(f"\nmatches   : {len(matches)}  ->  {out_dir}")
    print(f"{'chain':>5} {'words':>5} {'score':>7}  ref_i x ref_j")
    for m in sorted(matches, key=lambda m: -m["chain_len"])[:10]:
        print(f"{m['chain_len']:>5} {m['matched_words']:>5} {m['score']:>7.4f}  "
              f"{m['ref_i']} x {m['ref_j']}")

    hit = [m for m in matches
           if m["chain_len"] == ANCHOR["chain_len"]
           and m["ref_i"] == ANCHOR["ref_i"] and m["ref_j"] == ANCHOR["ref_j"]]
    if hit:
        print(f"\n[OK] anchor reproduced: chain "
              f"{hit[0]['chain_len']} words at {hit[0]['ref_i']} x {hit[0]['ref_j']}")
        return 0
    msg = (f"[FAIL] anchor NOT reproduced: expected chain "
           f"{ANCHOR['chain_len']} at {ANCHOR['ref_i']} x {ANCHOR['ref_j']}")
    print("\n" + msg)
    return 0 if args.no_assert else 1


if __name__ == "__main__":
    sys.exit(main())
