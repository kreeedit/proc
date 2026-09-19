#!/usr/bin/env python3
"""Behavioural regression tests for the shipped FLAME engine.

These tests run against **`engine/flame/flame_pure.py` exactly as released**
(byte-identical to its KONI source) and against the released match data in
`logs/text_reuse_matches.ndjson`.  They record what the engine *does*, not
what its documentation says it does.

Naming convention
-----------------
``test_DOC_*``  — the recorded behaviour **contradicts a docstring, the
                  engine README or the paper draft**.  Each such test names
                  the claim it falsifies.  Changing the engine to match its
                  documentation would break these tests *on purpose*: they are
                  a ratchet, not an endorsement of the behaviour.
``test_*``      — a genuine invariant of the engine worth protecting against
                  regression, or a measured property with no doc conflict.

Run
---
    python3 -m unittest discover -s tests -v      # stdlib only, no pytest

Runtime is a few seconds; the two heavy properties (length-prune soundness,
block algebra) are sampled rather than exhaustive, with fixed seeds.
"""

from __future__ import annotations

import difflib
import json
import random
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import find_text_reuse as H  # noqa: E402  (the release's localized harness)
from flame import bpe_pure, flame_pure as F  # noqa: E402

SAMPLES = ENGINE / "samples"
NDJSON = ROOT / "logs" / "text_reuse_matches.ndjson"

# `scripts/filter_by_wp_v2.py` is the one module in this package that needs a
# third-party library. The tests that exercise it are skipped when it is
# absent, so that `python3 -m unittest discover -s tests` still passes on a
# bare interpreter, as the README promises.
try:
    import pandas  # noqa: F401
    HAVE_PANDAS = True
except Exception:
    HAVE_PANDAS = False

# The parameters of the reported sweep (max_candidates is the code default here;
# see test_max_candidates_saturation_signature for what the run actually used).
KW = {"ngram": 4, "n_out": 1, "fuzz_threshold": 0.75,
      "min_chain_words": 2, "max_candidates": 4000}


# --------------------------------------------------------------------------
# shared fixtures (built once — unit construction costs ~1 s)
# --------------------------------------------------------------------------

def _units_plato():
    return H.build_units(SAMPLES / "plato_respublica_598.json", "tlg0059.tlg030")


def _units_proclus():
    return H.build_units(SAMPLES / "proclus_in_rem_publicam_101r.json",
                         "tlg4036.tlg001")


class _Fixture(unittest.TestCase):
    """Base class holding the demo pair and its records."""

    u1 = u2 = None
    records = None

    @classmethod
    def setUpClass(cls):
        bpe_pure.load(force=True)
        cls.u1 = _units_plato()
        cls.u2 = _units_proclus()
        cls.records = [ev["pair"] for ev in F.compare_iter(cls.u1, cls.u2, **KW)
                       if ev.get("t") == "pair"]
        cls.meta = next(ev for ev in F.compare_iter(cls.u1, cls.u2, **KW)
                        if ev.get("t") == "meta")


# --------------------------------------------------------------------------
# baseline: the demo anchor
# --------------------------------------------------------------------------

class TestBaseline(_Fixture):

    def test_demo_anchor_is_reproduced(self):
        """engine/README.md and demo.py promise a chain of 53 at
        `598/#3` x `In Rempublicam/101r#65`.  Measured: it is there."""
        hit = [r for r in self.records
               if r["label_i"] == "598/#3"
               and r["label_j"] == "In Rempublicam/101r#65"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["chain_len"], 53)
        self.assertEqual(hit[0]["matched_words"], 53)

    def test_demo_record_set_is_stable(self):
        """The five demo records, with the numbers the README quotes for them.
        Guards the whole pipeline (cleaning -> windowing -> matching) at once."""
        got = sorted((r["label_i"], r["label_j"], r["chain_len"],
                      r["matched_words"], r["n_chained"]) for r in self.records)
        self.assertEqual(got, sorted([
            ("598/#1", "In Rempublicam/101r#36", 49, 90, 4),
            ("598/#1", "In Rempublicam/101r#37", 24, 36, 2),
            ("598/#1", "In Rempublicam/101r#52", 5, 5, 1),
            ("598/#3", "In Rempublicam/101r#64", 29, 29, 1),
            ("598/#3", "In Rempublicam/101r#65", 53, 53, 1),
        ]))

    def test_window_phase_matches_the_sample_provenance_note(self):
        """The samples' `sample_provenance` note claims build_units()
        reproduces the original unit labels and window numbering.  Measured:
        3 Plato windows and 95 Proclus windows, labelled `<page>#k`."""
        self.assertEqual(len(self.u1), 3)
        self.assertEqual(len(self.u2), 95)
        self.assertEqual(self.u1[0]["label"], "598/#1")
        self.assertEqual(self.u2[64]["label"], "In Rempublicam/101r#65")


# --------------------------------------------------------------------------
# V1 — the BPE model and the match set
# --------------------------------------------------------------------------

class TestBPEModel(_Fixture):
    """`demo.py`'s `check_engine_ready()` warns of "silent degradation ...
    while still returning plausible-looking matches", which reads as a degraded
    *match set*.  Measured: the match set is bit-identical; only `score`
    moves.  The guard is still right, for the other reason."""

    @staticmethod
    def _set_trained(on: bool) -> bool:
        if on:
            bpe_pure._MERGES = bpe_pure._STOP = bpe_pure._RANKS = None
            bpe_pure.load(force=True)
        else:
            bpe_pure._MERGES, bpe_pure._STOP, bpe_pure._RANKS = [], set(), {}
        return bpe_pure.is_trained()

    def tearDown(self):
        self._set_trained(True)

    def test_orig_and_norm_word_lists_are_bpe_independent(self):
        """Both branches tokenize with the same `\\b\\w+\\b`, so every input of
        candidate generation and of Levenshtein matching is BPE-independent.
        Only `subs` (the cosine's input) differs."""
        self.assertTrue(self._set_trained(True))
        trained = F._units(self.u2)
        self.assertFalse(self._set_trained(False))
        untrained = F._units(self.u2)
        for a, b in zip(trained, untrained):
            self.assertEqual(a[0], b[0])          # label
            self.assertEqual(a[1], b[1])          # orig words
            self.assertEqual(a[2], b[2])          # norm words (Phase 2 input)
        self.assertNotEqual([a[3] for a in trained], [b[3] for b in untrained])

    def test_DOC_bpe_model_does_not_change_the_match_set(self):
        """Falsifies `demo.py`'s stated reason for refusing to run without the
        model — "still returning plausible-looking matches", which implies a
        different and worse match set.

        Measured: identical records, field for field, `score` excluded.
        (Also verified at production scale on a 1609 x 1306-unit real Greek
        pair: 56 vs 56 records, 56/56 identical ignoring score.)"""
        def run():
            out = []
            for ev in F.compare_iter(self.u1, self.u2, **KW):
                if ev.get("t") != "pair":
                    continue
                p = ev["pair"]
                out.append({k: p[k] for k in
                            ("i", "j", "label_i", "label_j", "chain_len",
                             "matched_words", "n_chained", "n_blocks",
                             "word_range_i", "word_range_j",
                             "snippet_i", "snippet_j")}
                           | {"mi": sorted(p["matched_i"]),
                              "mj": sorted(p["matched_j"])})
            return out
        self._set_trained(True)
        a = run()
        self._set_trained(False)
        b = run()
        self.assertEqual(a, b, "the BPE model changed the match set")

    def test_bpe_model_changes_score_and_score_ranking(self):
        """What the model *does* control: the reported cosine.  On the demo
        pair every score moves; at production scale the score *ranking* moves
        too — so a missing model invalidates `score`, not recall."""
        def scores():
            return [ev["pair"]["score"]
                    for ev in F.compare_iter(self.u1, self.u2, **KW)
                    if ev.get("t") == "pair"]
        self._set_trained(True)
        a = scores()
        self._set_trained(False)
        b = scores()
        self.assertEqual(len(a), len(b))
        self.assertNotEqual(a, b)
        self.assertTrue(all(x != y for x, y in zip(a, b)))

    def test_similarity_threshold_is_the_only_bpe_sensitive_gate(self):
        """The cosine can gate — but only through `similarity_threshold`,
        which the harness exposes no flag for and which defaults to
        `None` -> 0.0, a value every non-negative score passes."""
        kw = dict(KW)
        kw["similarity_threshold"] = 0.20
        self._set_trained(True)
        a = sum(1 for ev in F.compare_iter(self.u1, self.u2, **kw)
                if ev.get("t") == "pair")
        self._set_trained(False)
        b = sum(1 for ev in F.compare_iter(self.u1, self.u2, **kw)
                if ev.get("t") == "pair")
        self.assertNotEqual(a, b, "expected the BPE model to matter once the "
                                  "cosine actually gates")
        # and the default really is the pass-everything value
        self.assertEqual(self.meta["used_threshold"], 0.0)


# --------------------------------------------------------------------------
# V2, V3 — levenshtein_ratio and what fuzz=0.75 admits
# --------------------------------------------------------------------------

class TestLevenshtein(unittest.TestCase):

    def test_DOC_levenshtein_ratio_is_not_the_difflib_convention(self):
        """Falsifies: `levenshtein_ratio.__doc__` — "Similarity ratio in
        [0.0, 1.0] (difflib ratio convention)".

        The formula is `1 - dist/(len(a)+len(b))`, which is *not* difflib's
        `2*M/T`.  They disagree on ordinary inputs."""
        for a, b in [("abc", "abd"), ("abc", "xyz"), ("abcd", "abce")]:
            self.assertNotAlmostEqual(
                F.levenshtein_ratio(a, b),
                difflib.SequenceMatcher(None, a, b).ratio(),
                places=6, msg=f"{a}/{b} happened to agree")
        self.assertAlmostEqual(F.levenshtein_ratio("abc", "abd"), 0.8333, places=4)
        self.assertAlmostEqual(
            difflib.SequenceMatcher(None, "abc", "abd").ratio(), 0.6667, places=4)

    def test_DOC_ratio_floor_for_equal_length_words_is_one_half(self):
        """Falsifies: `levenshtein_ratio.__doc__` — "0.0 = completely
        different same-length strings".

        For equal-length strings the distance is at most the length, so
        `ratio >= 1 - L/(2L) = 0.5`.  The floor is 0.5, never 0.0."""
        for L in range(1, 12):
            self.assertAlmostEqual(F.levenshtein_ratio("a" * L, "b" * L), 0.5)
        self.assertEqual(F.levenshtein_ratio("", ""), 1.0)

    def test_fuzz_075_admits_half_the_letters_differing_at_equal_length(self):
        """Consequence of the floor: at equal length L the predicate passes
        while up to floor(L/2) letters differ."""
        for L in (2, 4, 6, 8):
            half = L // 2
            a = "α" * L
            near = "β" * half + "α" * (L - half)
            self.assertTrue(F._word_match(a, near, 0.75),
                            f"L={L}: {half}/{L} letters differing should pass")
            worse = "β" * (half + 1) + "α" * (L - half - 1)
            self.assertFalse(F._word_match(a, worse, 0.75))

    def test_fuzz_075_admits_greek_particles_and_bare_numerals(self):
        """Measured pairs that pass at 0.75.  The numerals matter because the
        Proclus text carries the Teubner apparatus inline (see
        test_apparatus_tokens_survive_clean_text)."""
        for a, b in [("το", "τω"), ("δε", "τε"), ("των", "την"),
                     ("μεν", "μην"), ("103", "104"), ("605", "603"),
                     ("18", "13")]:
            self.assertTrue(F._word_match(F.normalize(a), F.normalize(b), 0.75),
                            f"{a} ~ {b} should pass at 0.75")

    def test_DOC_particle_matches_are_killed_by_core_not_by_fuzz(self):
        """Falsifies: the module docstring — "The strict core/chain filters
        kill short particle matches (τε, καὶ, δὲ)" reads as if `fuzz` shared
        the work.  It does not: `fuzz=0.75` *admits* those pairs (above), and
        the whole reduction is done by `core >= ngram`."""
        ni = ["τε", "και", "δε", "το", "μεν", "γαρ"]
        nj = ["τε", "και", "δε", "τω", "μην", "γαρ"]
        raw = F._fuzzy_blocks(ni, nj, 0.75, 1)
        self.assertTrue(raw, "fuzz alone accepts the particle run")
        self.assertGreaterEqual(max(b["n"] for b in raw), 6)
        kept = [b for b in raw if b["core"] >= 4 and b["n"] >= 2]
        self.assertTrue(kept, "core>=4 keeps this run — it is 6 long")
        # shorten it below `ngram` and the same fuzz threshold now yields nothing
        raw2 = F._fuzzy_blocks(ni[:3], nj[:3], 0.75, 1)
        self.assertTrue(raw2)
        self.assertEqual([b for b in raw2 if b["core"] >= 4 and b["n"] >= 2], [])


# --------------------------------------------------------------------------
# V5 — the length prune is sound
# --------------------------------------------------------------------------

class TestLengthPrune(unittest.TestCase):

    def test_length_prune_never_rejects_a_passing_pair(self):
        """A real guarantee of the engine, worth a regression test: the cheap
        length prune in `_word_match` is *sound* — it agrees with the
        unpruned predicate on every input.  20,000 random Greek pairs x 5
        thresholds, fixed seed."""
        rng = random.Random(20260919)
        alpha = "αβγδεζηθικλμνξοπρστυφχψω"
        bad = []
        for _ in range(20000):
            a = "".join(rng.choice(alpha) for _ in range(rng.randint(0, 10)))
            b = "".join(rng.choice(alpha) for _ in range(rng.randint(0, 10)))
            for th in (0.5, 0.6, 0.75, 0.9, 1.0):
                pruned = F._word_match(a, b, th)
                if a == b or len(a) + len(b) == 0:
                    exact = True
                else:
                    exact = F.levenshtein_ratio(a, b) >= th
                if pruned != exact:
                    bad.append((a, b, th, pruned, exact))
        self.assertEqual(bad[:5], [], f"{len(bad)} prune disagreements")


# --------------------------------------------------------------------------
# V6 — block algebra
# --------------------------------------------------------------------------

class TestBlockAlgebra(_Fixture):

    def test_blocks_are_strictly_increasing_one_to_one_single_diagonal(self):
        """The other real guarantee: every block pairs `(s+k, s+k+d)` on one
        diagonal, so both sides contribute exactly `n` distinct, strictly
        increasing indices.  This is *why* `chain_len` is two-sided and why no
        `chain_j` is needed.  Measured over every raw block of a 3 x 40 unit
        slice of the demo pair."""
        U1 = F._units(self.u1)
        U2 = F._units(self.u2)[:40]
        n_blocks = 0
        for a in U1:
            for b in U2:
                for blk in F._fuzzy_blocks(a[2], b[2], 0.75, 1):
                    n_blocks += 1
                    ii = [m[0] for m in blk["matches"]]
                    jj = [m[1] for m in blk["matches"]]
                    self.assertEqual(len(set(ii)), blk["n"])
                    self.assertEqual(len(set(jj)), blk["n"])
                    self.assertTrue(all(ii[k] < ii[k + 1] for k in range(len(ii) - 1)))
                    self.assertTrue(all(jj[k] < jj[k + 1] for k in range(len(jj) - 1)))
                    self.assertEqual(len({j - i for i, j in blk["matches"]}), 1)
        self.assertGreater(n_blocks, 10000)

    def test_chain_len_equals_both_side_counts_when_there_is_one_block(self):
        """The invariant the report legend states, checked on live records."""
        for r in self.records:
            if r["n_chained"] == 1:
                self.assertEqual(r["chain_len"], r["matched_words"])
                self.assertEqual(r["chain_len"], len(r["matched_j"]))
            else:
                self.assertLessEqual(r["chain_len"], r["matched_words"])


# --------------------------------------------------------------------------
# V7 — the j-side count is computed and thrown away
# --------------------------------------------------------------------------

class TestJSideCount(_Fixture):

    def test_DOC_engine_computes_cnt_j_but_never_emits_it(self):
        """`compare_iter` calls `snip_j, rng_j, cnt_j = _snippet(...)` and then
        emits `matched_words` (= cnt_i) only.  The j-side count survives solely
        as the `matched_j` map, which the harness has to re-count itself."""
        src = (ENGINE / "flame" / "flame_pure.py").read_text(encoding="utf-8")
        self.assertIn("cnt_j = _snippet", src.replace("  ", " ") or src)
        self.assertNotIn("matched_words_j", src)
        for r in self.records:
            self.assertNotIn("matched_words_j", r)
            self.assertIn("matched_j", r)

    def test_released_records_have_no_j_side_count(self):
        """All 35,753 archived records predate the harness field, so any
        `gap_j` computed for them from `matched_words` would be the i side's
        count measured against the j side's span."""
        n = miss = 0
        with NDJSON.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                n += 1
                if "matched_words_j" not in json.loads(line):
                    miss += 1
        self.assertEqual(n, 35753)
        self.assertEqual(miss, 35753)


# --------------------------------------------------------------------------
# V8 — compare() is not symmetric
# --------------------------------------------------------------------------

class TestDirectionDependence(_Fixture):

    def test_DOC_compare_is_not_symmetric(self):
        """Falsifies: `find_text_reuse.py`'s docstring — "all-pairs (i<j,
        irányítatlan)", i.e. *undirected*.

        `df_cap = max(40, int(0.04 * n2))` prunes the inverted index built over
        **side 2 only**; side 1's bigrams carry no frequency cap at all.  So
        swapping the arguments changes which bigrams are pruned, hence the
        candidate set, hence the records."""
        def cands(a, b):
            n2 = len(b)
            inv = defaultdict(list)
            for j, u in enumerate(b):
                for g in set(F._word_ngrams(u[2], 2)):
                    inv[g].append(j)
            cap = max(40, int(0.04 * n2))
            out = {}
            for i, u in enumerate(a):
                local = Counter()
                for g in set(F._word_ngrams(u[2], 2)):
                    p = inv.get(g)
                    if p and len(p) <= cap:
                        local.update(p)
                for j, sh in local.items():
                    if sh >= 3:
                        out[(i, j)] = sh
            return out
        # a synthetic pair where the cap bites in one direction only
        many = [{"label": f"m{k}", "text": "αλφα βητα γαμμα δελτα εψιλον ζητα"}
                for k in range(200)]
        one = [{"label": "o", "text": "αλφα βητα γαμμα δελτα εψιλον ζητα"}]
        U_many = F._units(many)
        U_one = F._units(one)
        fwd = cands(U_one, U_many)      # n2 = 200 -> cap 40, postings of 200 -> all pruned
        rev = cands(U_many, U_one)      # n2 = 1   -> cap 40, postings of 1   -> nothing pruned
        self.assertEqual(len(fwd), 0)
        self.assertEqual(len(rev), 200)

    def test_df_cap_depends_only_on_the_second_argument(self):
        """The asymmetry in one line: the cap's *value* is a function of n2."""
        self.assertEqual(max(40, int(0.04 * 1306)), 52)
        self.assertEqual(max(40, int(0.04 * 1609)), 64)
        src = (ENGINE / "flame" / "flame_pure.py").read_text(encoding="utf-8")
        self.assertIn("df_cap = max(40, int(0.04 * n2))", src)
        # and it is consulted only while walking side 1's grams against `inv`
        self.assertEqual(src.count("df_cap"), 2)


# --------------------------------------------------------------------------
# V9, V10 — the cosine orders nothing, gates nothing, and is per-call
# --------------------------------------------------------------------------

class TestScore(_Fixture):

    def test_auto_threshold_is_computed_and_never_applied(self):
        """`auto_threshold` lands in `meta['threshold']`; the value actually
        used is `meta['used_threshold']` = 0.0.  On the demo pair applying it
        would drop 3 of the 5 records."""
        self.assertGreater(self.meta["threshold"], 0.0)
        self.assertEqual(self.meta["used_threshold"], 0.0)
        below = sum(1 for r in self.records if r["score"] < self.meta["threshold"])
        self.assertEqual(below, 3)
        self.assertEqual(len(self.records), 5)

    def test_DOC_released_record_order_is_not_score_order(self):
        """The emission order is the shared-bigram order, not the score order.
        Measured on the archive: 331 of the 359 multi-record work pairs are not
        score-monotone in file order.  (The demo pair happens to be monotone —
        it must not be used to illustrate the point.)"""
        by_pair = defaultdict(list)
        with NDJSON.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    by_pair[(r["work_i"], r["work_j"])].append(r["score"])
        multi = {k: v for k, v in by_pair.items() if len(v) >= 2}
        mono = sum(1 for v in multi.values()
                   if all(v[i] >= v[i + 1] for i in range(len(v) - 1)))
        self.assertEqual(len(multi), 359)
        self.assertEqual(mono, 28)

    def test_DOC_score_is_not_comparable_across_calls(self):
        """Falsifies any cross-pair use of `score` (the WP gates in
        `scripts/filter_by_wp.py` are exactly that).

        `_idf(counters1 + counters2)` is computed per *call*, so the IDF — and
        therefore the cosine — depends on which other units were in the same
        call.  Same unit pair, different call composition, different score."""
        def score_of(units2):
            for ev in F.compare_iter(self.u1, units2, **KW):
                if ev.get("t") == "pair" and ev["pair"]["label_j"].endswith("#65"):
                    return ev["pair"]["score"]
            return None
        full = score_of(self.u2)
        self.assertEqual(full, 0.3069)
        self.assertNotEqual(score_of(self.u2[:80]), full)
        self.assertNotEqual(score_of(self.u2[60:71]), full)

    def test_released_score_scales_differ_between_work_pairs(self):
        """The same point on the archive: per-pair score ranges span the whole
        [0, 1] interval, so one absolute threshold means different things on
        different pairs."""
        by_pair = defaultdict(list)
        with NDJSON.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    by_pair[(r["work_i"], r["work_j"])].append(r["score"])
        maxes = [max(v) for v in by_pair.values()]
        self.assertAlmostEqual(max(maxes), 1.0)
        self.assertEqual(min(maxes), 0.0)


# --------------------------------------------------------------------------
# V11 — silent clamping and truncation
# --------------------------------------------------------------------------

class TestSilentClamping(_Fixture):

    def test_DOC_out_of_range_parameters_are_clamped_without_warning(self):
        """The engine emits no diagnostic of any kind, and that is the defect:
        a caller asking for `ngram=99` silently gets 8.  `flame_pure_v2`
        reports the override in `meta["clamped"]` instead."""
        meta = next(ev for ev in F.compare_iter(
            self.u1, self.u2, ngram=99, n_out=99, fuzz_threshold=0.1,
            min_chain_words=0, max_candidates=4000) if ev["t"] == "meta")
        self.assertEqual(meta["ngram"], 8)
        self.assertEqual(meta["n_out"], 2)
        self.assertEqual(meta["fuzz_threshold"], 0.5)
        self.assertEqual(meta["min_chain_words"], 1)

    def test_cap_words_truncates_units_silently(self):
        """`CAP_WORDS = 400`.  Harmless under this harness (windows are 140
        words) but a trap for any other caller."""
        self.assertEqual(F.CAP_WORDS, 400)
        long_unit = [{"label": "x", "text": " ".join(["λογος"] * 900)}]
        self.assertEqual(len(F._units(long_unit)[0][1]), 400)
        self.assertLessEqual(max(len(u["text"].split()) for u in self.u1 + self.u2),
                             H.MAX_UNIT_WORDS)


# --------------------------------------------------------------------------
# V12 — bpe_pure ordering bug
# --------------------------------------------------------------------------

class TestBpeOrderingBug(unittest.TestCase):

    def test_DOC_tokenize_words_before_load_returns_characters(self):
        """`tokenize_words()` evaluates `_RANKS` *before* calling `load()`, so
        a first call on a fresh module encodes character-by-character.  Latent
        only because `flame_pure._units()` calls `is_trained()` first."""
        import importlib
        mod = importlib.reload(bpe_pure)
        self.assertIsNone(mod._RANKS)
        first = mod.tokenize_words("λογος")[1]
        self.assertEqual(first, ["λ", "ο", "γ", "ο", "ς", "</w>"])
        mod.load()
        second = mod.tokenize_words("λογος")[1]
        self.assertNotEqual(second, first)
        self.assertEqual(len(second), 1)
        # leave the module in the loaded state for any later test
        importlib.reload(bpe_pure).load(force=True)


# --------------------------------------------------------------------------
# provenance of the released run
# --------------------------------------------------------------------------

class TestReleasedRun(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.recs = [json.loads(l) for l in
                    NDJSON.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_record_count_is_the_reported_one(self):
        self.assertEqual(len(self.recs), 35753)

    def test_DOC_max_candidates_is_recoverable_from_the_artefact(self):
        """The reported run recorded no run-parameter metadata, but the value
        of `max_candidates` is nonetheless recoverable from the released data.

        A record can only exist for a *chosen candidate*, so records-per-pair
        is bounded by `max_candidates`.  Measured: the maximum over all 376
        populated pairs is exactly 1000, and that pair (Arethas x Arethas,
        a near-duplicate pair whose scores reach 1.0) shows the saturation
        signature — its chain lengths start at 19, while every unsaturated
        pair is dominated by chain 4-8.  That is rank truncation, and it fixes
        the production value at `--max-candidates 1000`, as the project log
        recorded."""
        per_pair = Counter((r["work_i"], r["work_j"]) for r in self.recs)
        self.assertEqual(max(per_pair.values()), 1000)
        self.assertEqual(sum(1 for v in per_pair.values() if v > 1000), 0)
        saturated = [r for r in self.recs
                     if (r["work_i"], r["work_j"]) == ("2130.038", "2130.039")]
        self.assertEqual(len(saturated), 1000)
        self.assertGreaterEqual(min(r["chain_len"] for r in saturated), 19)
        # contrast: the next-largest pair is not truncated
        other = [r for r in self.recs
                 if (r["work_i"], r["work_j"]) == ("3104.005", "3104.006")]
        self.assertEqual(len(other), 965)
        self.assertLessEqual(min(r["chain_len"] for r in other), 4)

    def test_absolute_score_gate_decides_the_wp1_and_wp2_counts(self):
        """`scripts/filter_by_wp.py` applies `score >= 0.001` (WP1/WP2) and
        `score >= 0.01` (WP3) across *all* work pairs.  Because the cosine is
        per-call normalized, that gate is not comparable across pairs — and it
        is not a rounding detail: it removes the majority of WP1 and WP2."""
        gates = [({"ancient_classical", "7th_8th"}, 6, 0.001, 19, 7),
                 ({"ancient_classical", "9th_10th"}, 6, 0.001, 33, 14),
                 ({"ancient_classical", "11th_12th"}, 8, 0.01, 693, 678)]
        for eras, cmin, smin, exp_chain, exp_final in gates:
            sel = [r for r in self.recs
                   if {r["era_i"], r["era_j"]} == eras
                   and r["author_i"] != r["author_j"]
                   and r["chain_len"] >= cmin]
            self.assertEqual(len(sel), exp_chain)
            self.assertEqual(sum(1 for r in sel if r["score"] >= smin), exp_final)


# --------------------------------------------------------------------------
# D3 — the Proclus apparatus survives _clean_text
# --------------------------------------------------------------------------

class TestApparatus(unittest.TestCase):

    def test_apparatus_tokens_survive_clean_text(self):
        """The Teubner apparatus is interleaved with the Proclus running text
        and `_clean_text()` does not remove it.  On the shipped sample, bare
        numerals alone are 2.36% of the tokens the engine sees and Latin-script
        tokens a further 4.44%; the cleaning stage removes 87 tokens and no
        numeral at all."""
        data = json.loads((SAMPLES / "proclus_in_rem_publicam_101r.json")
                          .read_text(encoding="utf-8"))
        raw = " ".join(s["text"] for s in data["segments"])
        cleaned = H._clean_text(raw)
        words = F._WORD_RE.findall(F._strip_milestones(cleaned))
        digits = [w for w in words if w.isdigit()]
        latin = [w for w in words if w.isascii() and w.isalpha()]
        self.assertGreater(len(digits) / len(words), 0.02)
        self.assertGreater(len(latin) / len(words), 0.04)
        self.assertEqual(len(digits), 255)
        self.assertEqual(len(latin), 476)
        # the apparatus sigla the paper's §4 claims are removed
        self.assertIn("ss", latin)
        self.assertIn("cf", latin)


# --------------------------------------------------------------------------
# the frozen files must stay frozen
# --------------------------------------------------------------------------

class TestFrozenFiles(unittest.TestCase):

    def test_frozen_files_are_untouched(self):
        """The release's hard constraint, as a test: the four protected files
        still match `engine/MANIFEST.sha256`.  Every fix lives in a `_v2`
        fork precisely so this keeps passing."""
        import hashlib
        want = {}
        for line in (ENGINE / "MANIFEST.sha256").read_text().splitlines():
            if line.strip():
                h, name = line.split(None, 1)
                want[name.strip()] = h
        for name in ("flame/flame_pure.py", "flame/bpe_pure.py",
                     "data/bpe_vocab.json", "LICENSE"):
            got = hashlib.sha256((ENGINE / name).read_bytes()).hexdigest()
            self.assertEqual(got, want[name], f"{name} is no longer byte-identical")

    def test_frozen_engine_still_drives_the_release(self):
        """Nothing in the release was rewired to the fork: `demo.py` and both
        harness copies still import `flame_pure`, so the reported run stays
        reproducible from the frozen engine."""
        for path in (ENGINE / "demo.py", ENGINE / "find_text_reuse.py",
                     ROOT / "scripts" / "find_text_reuse.py"):
            src = path.read_text(encoding="utf-8")
            self.assertNotIn("flame_pure_v2", src, f"{path.name} was rewired")
            self.assertNotIn("bpe_pure_v2", src, f"{path.name} was rewired")


# --------------------------------------------------------------------------
# the fixed fork: what changed, what deliberately did not
# --------------------------------------------------------------------------

def _fn_asts(src: str) -> dict:
    """Top-level function name -> AST dump with its docstring stripped."""
    import ast
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node = ast.parse(ast.unparse(node)).body[0]
                node.body = node.body[1:] or [ast.Pass()]
            out[node.name] = ast.dump(ast.fix_missing_locations(node))
    return out


class TestFixedFork(_Fixture):
    """`engine/flame/flame_pure_v2.py` is where the corrections live, since
    `flame_pure.py` is byte-frozen.  These tests pin both halves of the claim:
    what the fork changes, and — just as important — what it does not."""

    # The matching stage is what produces the matches, and it was found
    # sound.  Every one of these must stay byte-identical to the frozen engine.
    UNCHANGED = ("normalize", "_strip_milestones", "_units", "_hashes", "_idf",
                 "_tfidf", "cosine", "auto_threshold", "_lev_dist",
                 "levenshtein_ratio", "_word_match", "fuzz_ratio",
                 "_fuzzy_blocks", "_block_word_maps", "_block_bridge_maps",
                 "_snippet", "_word_ngrams", "compare")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from flame import flame_pure_v2
        cls.F2 = flame_pure_v2

    def test_matching_stage_is_untouched_by_the_fork(self):
        """The strongest guarantee available without a corpus: every function
        of the matching pipeline has an identical AST in both modules, so the
        fork cannot have changed what counts as a match."""
        a = _fn_asts((ENGINE / "flame" / "flame_pure.py").read_text(encoding="utf-8"))
        b = _fn_asts((ENGINE / "flame" / "flame_pure_v2.py").read_text(encoding="utf-8"))
        for name in self.UNCHANGED:
            self.assertIn(name, a)
            self.assertIn(name, b)
            self.assertEqual(a[name], b[name], f"{name}() diverged in the fork")
        # and exactly one function is allowed to differ, plus one new one
        differ = {n for n in a if n in b and a[n] != b[n]}
        self.assertEqual(differ, {"compare_iter"})
        self.assertEqual(set(b) - set(a), {"build_corpus_index"})

    def test_v2_reproduces_the_frozen_demo_records_exactly(self):
        """On the demo pair the fixes are inert — same records, same scores.
        So `scripts/demo_v2.py`'s mode [B] differences are attributable to the
        cleaning change, not to the engine."""
        got = [ev["pair"] for ev in self.F2.compare_iter(self.u1, self.u2, **KW)
               if ev.get("t") == "pair"]
        self.assertEqual([(r["label_i"], r["label_j"], r["chain_len"],
                           r["matched_words"], r["score"]) for r in got],
                         [(r["label_i"], r["label_j"], r["chain_len"],
                           r["matched_words"], r["score"]) for r in self.records])

    def test_FIX_candidate_retrieval_is_symmetric(self):
        """Fixes the directional retrieval.  The frozen engine caps side 2's
        postings only;
        the fork caps each side by its own unit count and drops a bigram only
        when it is over-frequent on both, which is invariant under a swap.

        The synthetic pair here is the one `TestDirectionDependence` uses to
        show the frozen engine failing: 0 candidates one way, 200 the other."""
        many = [{"label": f"m{k}", "text": "αλφα βητα γαμμα δελτα εψιλον ζητα"}
                for k in range(200)]
        one = [{"label": "o", "text": "αλφα βητα γαμμα δελτα εψιλον ζητα"}]
        kw = dict(KW, min_chain_words=2)
        def n_cand(F, a, b):
            return next(ev for ev in F.compare_iter(a, b, **kw)
                        if ev["t"] == "meta")["n_candidates"]
        self.assertNotEqual(n_cand(F, one, many), n_cand(F, many, one))
        self.assertEqual(n_cand(self.F2, one, many), n_cand(self.F2, many, one))

    def test_FIX_corpus_index_makes_score_call_invariant(self):
        """Fixes the per-call score scale.  The same unit pair must score the
        same however the
        call around it is composed — which is what an absolute cross-pair
        threshold silently assumes."""
        index = self.F2.build_corpus_index([self.u1, self.u2], ngram=4, n_out=1)
        def score(units2, **kw):
            for ev in self.F2.compare_iter(self.u1, units2, **KW, **kw):
                if ev.get("t") == "pair" and ev["pair"]["label_j"].endswith("#65"):
                    return ev["pair"]["score"]
        per_call = {score(self.u2[:c]) for c in (95, 90, 80, 66)}
        corpus = {score(self.u2[:c], corpus_index=index) for c in (95, 90, 80, 66)}
        self.assertEqual(len(per_call), 4, "per-call IDF should drift")
        self.assertEqual(len(corpus), 1, "corpus IDF must not drift")
        self.assertEqual(corpus, {0.3069})

    def test_corpus_index_idf_matches_the_engines_own(self):
        """`build_corpus_index` streams document frequencies instead of holding
        a Counter per unit (which would be several GB on a 29-work sweep). It
        has to produce exactly what `_idf` would have, so the corpus-scoped and
        call-scoped paths differ only in *scope*, never in formula. Checked on a
        single work, where the two scopes coincide."""
        index = self.F2.build_corpus_index([self.u2], ngram=4, n_out=1)
        units = self.F2._units(self.u2)
        counters = [Counter(self.F2._hashes(
            [index["vocab"].get(s, index["oov"]) for s in subs],
            index["base"], 4, 1)) for _, _, _, subs, _ in units]
        self.assertEqual(index["idf"], self.F2._idf(counters))
        self.assertEqual(index["n_units"], len(units))
        self.assertEqual(index["n_works"], 1)

    def test_corpus_index_tolerates_unseen_subwords(self):
        """An index built on one work must still score a unit from another —
        otherwise `--only` subsets or a late corpus addition would crash rather
        than degrade."""
        index = self.F2.build_corpus_index([self.u1], ngram=4, n_out=1)
        got = [ev["pair"] for ev in
               self.F2.compare_iter(self.u1, self.u2, **KW, corpus_index=index)
               if ev.get("t") == "pair"]
        self.assertEqual(len(got), 5)
        self.assertTrue(all(0.0 <= p["score"] <= 1.0 for p in got))

    def test_FIX_matched_words_j_is_emitted(self):
        """Fixes the discarded j-side count: `cnt_j` was computed and thrown
        away, so no released record carries it."""
        for ev in self.F2.compare_iter(self.u1, self.u2, **KW):
            if ev.get("t") == "pair":
                p = ev["pair"]
                self.assertIn("matched_words_j", p)
                self.assertEqual(p["matched_words_j"], len(p["matched_j"]))

    def test_FIX_silent_behaviour_is_reported(self):
        """Fixes the silent clamping.  The clamping still happens — changing it
        would
        change results — but `meta` now names it."""
        meta = next(ev for ev in self.F2.compare_iter(
            self.u1, self.u2, ngram=99, n_out=99, fuzz_threshold=0.1,
            min_chain_words=0, max_candidates=4000) if ev["t"] == "meta")
        self.assertEqual(meta["ngram"], 8)
        self.assertEqual(meta["clamped"]["ngram"],
                         {"requested": 99, "used": 8})
        self.assertEqual(set(meta["clamped"]),
                         {"ngram", "n_out", "fuzz_threshold", "min_chain_words"})
        clean = next(ev for ev in self.F2.compare_iter(self.u1, self.u2, **KW)
                     if ev["t"] == "meta")
        self.assertEqual(clean["clamped"], {})
        for key in ("cap_hit", "n_candidates_before_cap", "units_truncated",
                    "idf_scope", "bpe_trained", "max_candidates"):
            self.assertIn(key, clean)

    def test_FIX_cap_hit_is_reported(self):
        meta = next(ev for ev in self.F2.compare_iter(
            self.u1, self.u2, **dict(KW, max_candidates=3)) if ev["t"] == "meta")
        self.assertTrue(meta["cap_hit"])
        self.assertEqual(meta["n_candidates"], 3)
        self.assertEqual(meta["n_candidates_before_cap"], 10)

    def test_FIX_bpe_load_order(self):
        """Fixes the load-order defect: `tokenize_words()` before `load()`
        returned
        characters in the frozen module."""
        import importlib
        from flame import bpe_pure_v2
        mod = importlib.reload(bpe_pure_v2)
        self.assertIsNone(mod._RANKS)
        self.assertEqual(mod.tokenize_words("λογος")[1], ["λογος</w>"])
        importlib.reload(bpe_pure_v2).load(force=True)


# --------------------------------------------------------------------------
# the fixed pipeline around the fixed engine
# --------------------------------------------------------------------------

class TestFixedPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "scripts"))
        import find_text_reuse_v2
        cls.V2 = find_text_reuse_v2

    def test_FIX_apparatus_tokens_are_stripped(self):
        """Fixes the surviving apparatus.  The frozen `_clean_text` leaves 255
        bare numerals
        and 476 Latin tokens in the Proclus sample; the v2 cleaning removes
        them — and, because the word stream shortens, re-phases the windows."""
        data = json.loads((SAMPLES / "proclus_in_rem_publicam_101r.json")
                          .read_text(encoding="utf-8"))
        raw = " ".join(s["text"] for s in data["segments"])
        cleaned = self.V2.clean_text(raw, strip_apparatus=True)
        words = F._WORD_RE.findall(F._strip_milestones(cleaned))
        self.assertEqual([w for w in words if w.isdigit()], [])
        self.assertEqual([w for w in words if w.isascii() and w.isalpha()], [])
        # the frozen path is unchanged and still carries them
        frozen = F._WORD_RE.findall(F._strip_milestones(H._clean_text(raw)))
        self.assertEqual(sum(1 for w in frozen if w.isdigit()), 255)

    def test_apparatus_strip_is_off_for_non_greek_segments(self):
        """The guard that makes the strip safe: a majority-Latin segment keeps
        its Latin words, so the filter cannot eat a Latin work."""
        latin = "omnis homo naturaliter scire desiderat signum autem est"
        self.assertFalse(self.V2.is_greek_segment(latin))
        self.assertEqual(self.V2.clean_text(latin, True), latin)

    def test_FIX_windows_rephase_under_the_strip(self):
        """The cost of the apparatus filter, stated as a test: every `#k` label
        moves, so no positional reference survives it."""
        frozen = self.V2.build_units(SAMPLES / "proclus_in_rem_publicam_101r.json",
                                     "x", strip_apparatus=False)
        fixed = self.V2.build_units(SAMPLES / "proclus_in_rem_publicam_101r.json",
                                    "x", strip_apparatus=True)
        self.assertEqual(len(frozen), 95)
        self.assertEqual(len(fixed), 92)
        self.assertNotEqual(frozen[64]["text"], fixed[64]["text"])

    def test_build_units_without_strip_matches_the_frozen_harness(self):
        """With the strip off, the v2 harness reproduces the frozen units
        exactly — so the strip is the only cleaning difference."""
        for name in ("plato_respublica_598.json",
                     "proclus_in_rem_publicam_101r.json"):
            a = H.build_units(SAMPLES / name, "x")
            b = self.V2.build_units(SAMPLES / name, "x", strip_apparatus=False)
            self.assertEqual(a, b, name)

    def test_v2_outputs_do_not_overwrite_released_artefacts(self):
        """The other hard constraint: the corrected pipeline writes beside
        the release, never over it."""
        import find_text_reuse_v2 as V2
        self.assertEqual(V2.DEFAULT_OUT_DIR, ROOT / "logs" / "v2")
        self.assertTrue((ROOT / "logs" / "text_reuse_matches.ndjson").is_file())
        # Read the filter's default out of the source rather than importing it:
        # that module needs pandas, and this assertion does not.
        src = (ROOT / "scripts" / "filter_by_wp_v2.py").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_OUT = ROOT / "logs" / "clean_by_wp_v2"', src)


@unittest.skipUnless(HAVE_PANDAS, "pandas is not installed")
class TestFixedWorkPackageFilter(unittest.TestCase):
    """`scripts/filter_by_wp_v2.py` on the released data: with no run
    provenance beside it, the score scale is per-call, so the absolute gate is
    switched off and the counts revert to what chain length alone selects.

    Skipped without pandas, which is the one third-party dependency anywhere
    in this package — the engine, both harnesses and the rest of these tests
    are standard library only, and a reader who clones the repository and runs
    the suite must not be told it failed because of an optional filter."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "scripts"))

    def test_score_scope_detected_as_per_call_for_the_released_sweep(self):
        import filter_by_wp_v2 as W2
        scope, _ = W2.detect_score_scope(
            ROOT / "logs" / "overlap_filter_global" / "byz_byz_tagged.tsv")
        self.assertEqual(scope, "call")

    def test_counts_without_the_cross_pair_score_gate(self):
        import filter_by_wp_v2 as W2
        df = W2.load_base(ROOT / "logs" / "overlap_filter_global"
                          / "byz_byz_tagged.tsv")
        expect = {"wp1_implicit": (19, 7), "wp2_canon": (33, 14),
                  "wp3_explicit": (693, 678)}
        for key, cfg in W2.WP.items():
            out, _ = W2.filter_wp(df, cfg, "none", 0.0)
            gated, _ = W2.filter_wp(df, cfg, "absolute", 0.0)
            self.assertEqual((len(out), len(gated)), expect[key], key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
