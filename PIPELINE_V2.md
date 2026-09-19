# The corrected pipeline

The engine that produced the reported matches was examined in September 2026
against the shipped code, the released match data, and real Greek texts at a
scale comparable to the corpus's largest work. Six defects were established by
measurement. This document records them, the remedies, and the cost of each.

The remedies are implemented in a parallel set of files. The released pipeline
is untouched: `engine/flame/flame_pure.py`, `engine/flame/bpe_pure.py`,
`engine/data/bpe_vocab.json` and `engine/LICENSE` remain byte-identical to
their sources, `engine/demo.py` still loads the frozen engine and still
reproduces the chain-53 anchor, and no released artefact was rewritten. The
reported figures change only when the 406-pair sweep is repeated with the
corrected pipeline, which requires the TLG-derived corpus that this archive
does not contain.

The engine's method, and the limitations of the reported run in the terms a
reader of the paper needs, are described in
[`engine/README.md`](engine/README.md).

---

## Files

| file | replaces | why it is a separate file |
|---|---|---|
| `engine/flame/flame_pure_v2.py` | `engine/flame/flame_pure.py` | the original is byte-identical to its source and the release advertises that with `cmp` and `MANIFEST.sha256` |
| `engine/flame/bpe_pure_v2.py` | `engine/flame/bpe_pure.py` | as above |
| `scripts/find_text_reuse_v2.py` | `scripts/find_text_reuse.py` | the original is covered by the root `MANIFEST.sha256` and the release is frozen |
| `scripts/filter_by_wp_v2.py` | `scripts/filter_by_wp.py` | as above |
| `scripts/demo_v2.py` | `engine/demo.py` | the frozen demonstration verifies the frozen engine; this one verifies the corrected engine against it |

## Running it

```bash
python3 engine/demo.py                   # frozen pipeline: chain-53 anchor, exit 0
python3 scripts/demo_v2.py               # corrected pipeline on the same samples
python3 -m unittest discover -s tests     # 49 tests, roughly 40 s, standard library only
```

`demo_v2.py` prints two tables. Table **[A]** applies the corrected engine with
the frozen cleaning, and reproduces `engine/demo.py`'s five records exactly:
identical labels, chains, matched words and scores. That is the point of it —
the engine corrections do not alter what counts as a match. Table **[B]** adds
the apparatus filter, so every difference between the two is attributable to
the cleaning alone.

The full sweep, where a corpus is available:

```bash
python3 scripts/find_text_reuse_v2.py    # writes logs/v2/
python3 scripts/filter_by_wp_v2.py       # writes logs/clean_by_wp_v2/
```

Both default to new output directories. `logs/text_reuse_matches.ndjson`,
`logs/clean_by_wp/` and `results/reported_numbers.json` are never written.

---

## The defects and their remedies

### 1. Candidate retrieval was directional

`flame_pure` discards a word bigram when its posting list on the **second**
side exceeds `max(40, 0.04 × n2)`. The first side's bigrams are subject to no
cap, and the cap's value is a function of `n2` alone. Exchanging the arguments
therefore prunes a different set of bigrams and returns a different set of
matches.

Measured on Herodotus × Thucydides, 1,609 × 1,306 windows: 3,617 candidates in
one direction against 8,402 in the other, a Jaccard overlap of 0.264. Two
further pairs of comparable size give 6,707 against 6,805 and 11,574 against
8,642. Carried through to completion, the first pair yields 304 records against
515, and at a chain threshold of 6 — the criterion applied to the
intra-Byzantine set — 6 records against 12. Where a record is found in both
directions its content is identical in every field, including the score, so
the effect is confined to recall: the asymmetry governs which unit pairs are
examined, never what is found within a pair that is examined. The sweep's
`i < j` enumeration fixed one direction per work pair according to the
corpus's chronological sort order.

**Remedy.** Each side receives a cap derived from its own unit count, and a
bigram is discarded only when it is over-frequent on **both**. The predicate
`df1[g] > cap1 and df2[g] > cap2` maps to itself when the two sides are
exchanged, which is precisely what a swap does. Ties in the candidate ranking
are additionally broken on `(i, j)`, so that the `max_candidates` truncation
point does not depend on posting-list layout.

**Verification.** Forward and reverse produce identical candidate sets on all
three real pairs — a Jaccard index of 1.0000 with shared-bigram counts agreeing
pair by pair — and the result is a strict **superset** of the frozen engine's
forward direction, with no candidate lost on any of the three.

**Cost.** Between 1.6 and 3 times as many candidates reach the scoring stage.
`max_candidates` continues to bound what reaches alignment, so the ceiling on
running time is unchanged; the additional candidates alter which pairs occupy
that budget rather than how many do.

**Alternatives rejected.** Deriving a single cap from `min(n1, n2)` is likewise
direction-free but removes 44% to 76% of the candidates. Capping the combined
document frequency removes between 926 and 4,786 candidates while recovering
fewer. Neither is preferable to a criterion that loses nothing.

### 2. The score was normalised per call

`flame_pure` derives the subword vocabulary, the polynomial hash base and the
inverse document frequencies from the units of the current call. Since
`base = len(vocab) + 1`, even the hash values differ between calls. In an
all-pairs sweep this yields one scale per work pair: the same unit pair scores
0.3069, 0.3066, 0.3058 and 0.3055 under four different call compositions, and
the per-pair score maxima in the released data range from 0.0000 to 1.0000.

This would be immaterial if the score were only ever compared within a pair. It
was not. `scripts/filter_by_wp.py` applies absolute thresholds across all pairs
— `score ≥ 0.001` for WP1 and WP2, `score ≥ 0.01` for WP3 — and those
thresholds remove 12 of WP1's 19 chain-≥6 candidates and 19 of WP2's 33. The
reported counts of 7 and 14 are therefore determined principally by the score
gate rather than by chain length; for WP3 the gate removes 15 of 693. Two
further sites compare scores across pairs: the "best score" line of the
work-package report, and the optional score thresholds in
`scripts/verify_reuse.py`, which can classify a record as a false positive on
its score alone. `scripts/compute_reported_numbers.py` does not read the score
at any point.

**Remedy.** `flame_pure_v2.build_corpus_index()` derives one vocabulary, hash
base and IDF over the entire corpus, and `compare_iter(corpus_index=…)` uses
them. The vocabulary travels with the IDF because a shared IDF is meaningless
over hashes computed with different bases. Omitting the argument preserves the
per-call behaviour, so the fork remains a drop-in for callers that have not
built an index.

`scripts/filter_by_wp_v2.py` reads the run's provenance sidecar and decides
accordingly: where the scores derive from a corpus-level IDF the absolute gate
is meaningful and is applied; where they are per-call — which is the case for
every existing artefact — the gate is disabled, with a printed note, and
selection falls back to chain length, which is scale-free.

**Verification.** With a corpus index the same unit pair scores 0.3069 under
all four call compositions above, and the unit's underlying TF-IDF vector is
identical between calls.

**Cost.** One additional pass over the corpus before the sweep. The sweep
already re-derives each work's hashes once for every pair in which it appears —
28 times each in the reported run — so the index is cheaper than what it
replaces. The index streams document frequencies rather than materialising a
counter per unit, which would require several gigabytes on a 29-work corpus.

**Consequence for the released data.** Removing the cross-pair gate from the
released match data, which requires no re-run, gives:

| | released | without the cross-pair gate |
|---|---:|---:|
| WP1 (`anc ↔ 7th_8th`, chain ≥ 6) | 7 | 19 |
| WP2 (`anc ↔ 9th_10th`, chain ≥ 6) | 14 | 33 |
| WP3 (`anc ↔ 11th_12th`, chain ≥ 8) | 678 | 693 |

These are not corrections to the paper's figures. They are what the same
criteria select once a quantity that is not comparable across pairs is removed
from them. Which set the paper should report is an argument for §5 rather than
a filtering decision, and the durable answer is a re-run with a corpus-level
IDF, after which the absolute gate becomes meaningful again
(`--score-mode absolute`).

### 3. The Proclus apparatus survived cleaning

`tlg4036.tlg001` (*In Rempublicam*, Kroll) is the only work in the corpus in
which the Teubner critical apparatus is interleaved with the running text
rather than held in a separate field. After the frozen `_clean_text()` has run,
2.4% of the tokens the engine sees are bare numerals and 4.4% are Latin-script;
the cleaning stage removes 87 tokens from the shipped sample and no numerals at
all. This matters because the similarity threshold of 0.75 matches numerals to
one another: `103 ~ 104` and `605 ~ 603` both score 0.833.

**Remedy.** `find_text_reuse_v2.clean_text()` removes bare numerals and
Latin-script tokens, but only from segments that are predominantly Greek, so
that the filter cannot consume a Latin work.

**Verification.** No numeral and no Latin token survives in the sample; the
Proclus unit falls from 95 windows to 92, and the strongest lemmatic record
rises from 90 to 104 matched words, with its score moving from 0.4373 to
0.5708.

**Cost, and it is the significant one.** The word stream shortens, so every
`#k` window label and every `word_range` moves. No positional reference in the
present results survives the change. This is why the filter can be disabled
(`--no-apparatus-strip`) and why enabling it entails repeating the sweep rather
than amending a report. The appropriate place for the correction remains the
corpus builder, where the apparatus column is still separable; that code is not
part of this archive.

### 4. The j-side matched-word count was discarded

`flame_pure` computes `cnt_j` on the line above the record it emits and does
not include it. None of the 35,753 released records carries a j-side count, so
no `gap_j` can be computed for the archive at all.

**Remedy.** `flame_pure_v2` emits it as `matched_words_j`.

### 5. Silent clamping and silent truncation

`ngram`, `n_out`, `min_chain_words` and `fuzz_threshold` are clamped rather
than validated: a request for `ngram=99` silently yields 8. `CAP_WORDS = 400`
truncates over-long units. Neither takes effect under the shipped harness,
whose windows are 140 words, but both are hazards for any other caller, and the
engine emits no diagnostic of any kind.

**Remedy.** The clamping itself is retained, since changing it would change
results; it is now reported. `meta` carries `clamped` — the requested and the
effective value for each overridden parameter — together with `cap_hit`,
`n_candidates_before_cap`, `units_truncated`, `idf_scope` and `bpe_trained`.
`find_text_reuse_v2.py` turns these into warnings and writes a
`text_reuse_matches.meta.json` provenance sidecar recording the effective
parameters, the engine hash and the corpus reference.

The absence of such a sidecar from the reported run is why the value of
`max_candidates` had to be recovered indirectly, from the truncation signature
in the distribution of records per work pair. It was 1,000.

### 6. `tokenize_words()` before `load()`

`bpe_pure.tokenize_words()` evaluates `_RANKS` before calling `load()`, so a
first call on a freshly imported module encodes character by character rather
than into subwords. The defect is latent in the production path only because
`flame_pure._units()` happens to call `is_trained()` first.

**Remedy.** `bpe_pure_v2` reverses the two statements. Nothing else differs.

---

## What was deliberately left unchanged

The Levenshtein predicate, the block builder, the
`core >= ngram and n >= min_chain_words` filter, the emission order and the
140/115 windowing. These produce the matches, and the examination found them
sound: the length prune in `_word_match` never rejects a pair that the unpruned
predicate would accept, verified over 20,000 randomly generated Greek word
pairs at five thresholds with no disagreement; and every block is a strictly
increasing one-to-one pairing on a single diagonal, verified over 78,713 blocks
with no violation.

This is enforced rather than asserted.
`tests/test_flame.py::TestFixedFork::test_matching_stage_is_untouched_by_the_fork`
compares the two engine modules function by function at the level of the
abstract syntax tree and requires exactly one function to differ
(`compare_iter`) and exactly one to be new (`build_corpus_index`).

Also unchanged: the clamping itself, and the default of 4,000 for
`max_candidates`. The reported run used 1,000; the appropriate response is to
state the value in effect, not to substitute a different one silently.

---

## What remains impossible from this archive

**Repeating the sweep.** The corpus is TLG-derived and cannot be
redistributed, and `corpus_manifest.yaml` is not included. Everything above was
verified on the two bundled samples and on three real Greek works — Herodotus
(185,048 words, 1,609 windows), Thucydides (150,165 words, 1,306) and Procopius
(224,518 words, 1,953) — built from PerseusDL TEI as stand-ins for scale. Those
three are not the paper's corpus and support claims about engine behaviour
only.

**Correcting the apparatus at its source.** The corpus-construction scripts are
excluded from the release by policy.

**Subdividing the `ancient_classical` era bucket,** which places Plato and
Proclus, some nine centuries apart, in a single layer. That change touches
`corpus_manifest.yaml`, `ERA_RANK` and `ALL_ERAS`, and every era-pair figure
the paper reports; it must be decided and applied across the pipeline at once.

**Reducing the running time.** Two candidate optimisations were measured and
rejected: precomputing the modular powers outside the inner loop of `_hashes`
yields between 0.92 and 1.15 times the original speed, and memoising
`_word_match` yields 0.95, since `_lev_dist` is already cached and the length
prune is inexpensive. The dominant cost is the construction of the 140 × 140
match matrix itself, at 183 to 237 ms per unit pair, which is intrinsic to the
algorithm as specified.
