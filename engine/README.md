# The text-reuse engine

The matches reported in the accompanying paper were produced by the FLAME
text-reuse engine as implemented in `flame/flame_pure.py`, a pure-Python,
standard-library-only implementation of a leave-*n*-out *n*-gram method,
driven by the sweep harness `find_text_reuse.py`. Both are included here in
full, and `flame/flame_pure.py` is the exact file that ran, byte for byte.

This document is the authoritative description of that engine. It supersedes
the account of the matching procedure given in §4 of the manuscript, which
describes a different algorithm; a replacement for that section, written from
the behaviour documented here, is provided as
[`../Section4_FLAME_rewritten.md`](../Section4_FLAME_rewritten.md).

The engine is not the public
[`kreeedit/FLAME`](https://github.com/kreeedit/FLAME) tool. The two implement
the same method family but differ in every stage that determines what is
reported; see [Relation to the public FLAME tool](#relation-to-the-public-flame-tool).

Every quantitative statement below was verified against the shipped code and
the shipped match data in an audit conducted on 19 September 2026. The finding
list and the measurements are in [`../AUDIT.md`](../AUDIT.md); the assertions
are held by `../tests/test_flame.py`, and the scripts that produced the
measurements are in `../tests/measurements/`. Where a defect admits a remedy,
that remedy is implemented in a parallel pipeline described in
[`../PIPELINE_V2.md`](../PIPELINE_V2.md). The present package is unaffected by
it: `flame/flame_pure.py`, `flame/bpe_pure.py`, `data/bpe_vocab.json` and
`LICENSE` remain byte-identical to their sources, and the reported figures are
reproducible from them.

---

## Contents

```
engine/
├── README.md                     this file
├── NOTICE.md                     provenance, licensing, attribution (read with LICENSE)
├── LICENSE                       MIT (the engine code)
├── demo.py                       a runnable, self-contained demonstration
├── find_text_reuse.py            the sweep harness, localised for this package
├── flame/
│   ├── __init__.py               package marker (the one non-identical file here)
│   ├── flame_pure.py             the engine; `compare_iter` is the entry point
│   ├── flame_pure_v2.py          the corrected engine (see ../PIPELINE_V2.md)
│   ├── bpe_pure.py               BPE subword tokenizer
│   └── bpe_pure_v2.py            the same, with an ordering defect repaired
├── data/
│   └── bpe_vocab.json            the trained BPE model (3,000 merges, 50 stop-subwords)
└── samples/
    ├── plato_respublica_598.json
    └── proclus_in_rem_publicam_101r.json
```

## Demonstration

```bash
python3 engine/demo.py            # no dependencies; writes engine/demo_out/
```

The demonstration compares the two bundled corpus units and produces five
matches, the largest being a chain of 53 words at `598/#3` ×
`In Rempublicam/101r#65`. That is the strongest cross-author correspondence in
the released match data — Plato × Proclus, against a next-best cross-author
chain of 51, over all 35,753 records — so the run constitutes a verification of
the shipped engine rather than an illustration of it. The process exits
non-zero if the anchor is not reproduced, and refuses to run if the BPE model
is absent.

The manuscript does not itself cite this pair; §6 cites Proclus `101r#72`,
`121v#138` and `18r#11`. "Strongest in the data" is therefore not a claim about
evidential weight in the argument.

The bundled texts are redistributable PerseusDL / Open Greek and Latin
editions, and the run completes in under a second.

To observe the corrected pipeline on the same material:

```bash
python3 scripts/demo_v2.py        # see ../PIPELINE_V2.md
```

## Verification of this package

```bash
cd engine && sha256sum -c MANIFEST.sha256          # 12 files
cmp flame/flame_pure.py <KONI>/app/flame_pure.py   # if the source tree is available
diff -u ../scripts/find_text_reuse.py find_text_reuse.py
```

## What the engine does

Unit segmentation is the harness's responsibility (`find_text_reuse.py`).
Segments are grouped into citation-page units, cleaned — modern header and
licence lines, EpiDoc/TEI markup, a conservative list of critical-apparatus
sigla, four scholastic transition formulas, milestone references — and then
divided into **windows of 140 words at a step of 115**, that is, with an
overlap of 25 words. Windows are not aligned to sentence boundaries. The
windowing is why units carry labels of the form `In Rempublicam/101r#65`: page
followed by window ordinal.

The engine proper operates in three stages, all in `flame/flame_pure.py`.

### Stage 1: candidate retrieval

An inverted index over normalised word **bigrams** proposes unit pairs. A pair
is retained when it shares at least `min_shared` (3) bigrams. Bigrams whose
posting list exceeds `max(40, 4% of the units on the second side)` are treated
as too common and skipped. The surviving pairs are ordered by shared-bigram
count, and the first `max_candidates` of them proceed to alignment.

This stage determines recall, and it has two properties that bear on the
interpretation of any figure derived from the sweep.

First, **retrieval is directional**. The frequency cap is computed from, and
applied to, the second argument alone; the first argument's bigrams are subject
to no cap. Exchanging the arguments therefore alters which bigrams are pruned
and hence the candidate set. Measured on a pair of real Greek works at a scale
comparable to the corpus's largest (1,609 × 1,306 windows), the two directions
yield 3,617 and 8,402 candidates, a Jaccard overlap of 0.264; two further pairs
give 6,707 against 6,805 and 11,574 against 8,642. Carried through to
completion, the same pair yields 304 records in one direction and 515 in the
other, and at a chain threshold of 6 — the criterion §5 applies to the
intra-Byzantine set — 6 against 12. Where a record is found in both directions
its content is identical in every field, so the asymmetry is a matter of
recall alone: it governs which unit pairs are examined, never what is found
within a pair that is examined. The sweep's `i < j` enumeration fixes one
direction per work pair according to the corpus's chronological sort order.

Second, **`max_candidates` is a recall parameter, not a refinement**. On the
three real pairs above, a cap of 1,000 retains 27.6%, 14.9% and 8.6% of the
candidates respectively. At record level a cap of 1,000 yields 103 records
where 4,000 yields 304. The value in effect for the reported run was 1,000; see
[The reported run](#the-reported-run).

### Stage 2: scoring

Each candidate pair receives a TF-IDF cosine computed over leave-*n*-out
rolling hashes of its BPE subword *n*-grams (`ngram = 4`, `n_out = 1`, modulo
2⁶¹−1; 3,000 learned merges with the fifty most frequent purely grammatical
endings suppressed as noise). This quantity is reported on every match record
as `score`.

**The cosine neither orders nor gates any part of the procedure.** The order in
which matches are emitted is the shared-bigram order established in stage 1;
the similarity cut-off is the module default `similarity_threshold=None`,
which resolves to 0.0 and admits every non-negative score, and the harness
exposes no option to alter it. An automatic threshold is computed and placed in
the metadata, and is never applied. Over the released data, 331 of the 359 work
pairs carrying more than one record are not score-monotone in file order, and
only 27 are chain-monotone.

Two consequences follow, and both bear on figures reported in the paper.

**The score is normalised per call and is not comparable between work pairs.**
The vocabulary, the hash base and the inverse document frequencies are all
derived from the units of the current call; since `base = len(vocab) + 1`, even
the hash values differ between calls. In an all-pairs sweep this amounts to one
scale per work pair. The same unit pair scores 0.3069, 0.3066, 0.3058 and
0.3055 under four different call compositions, and the per-pair score maxima in
the released data range from 0.0000 to 1.0000. This would be immaterial were
the score used only within a pair; it is not. `scripts/filter_by_wp.py` applies
absolute thresholds across all pairs (`score ≥ 0.001` for WP1 and WP2,
`score ≥ 0.01` for WP3), and those thresholds remove 12 of WP1's 19 chain-≥6
candidates and 19 of WP2's 33. The reported counts of 7 and 14 are therefore
determined principally by the score gate rather than by chain length; for WP3
the gate removes 15 of 693. The script that computes the paper's figures,
`compute_reported_numbers.py`, does not read `score` at all.

**The BPE model governs the score and nothing else.** When
`data/bpe_vocab.json` is absent or unreadable, `bpe_pure.load()` falls back to
empty merges and the engine reverts to plain normalised-word hashing. Both
branches tokenise words with the same `\b\w+\b` pattern, so candidate retrieval
and alignment receive identical input; the cosine is the only BPE-dependent
quantity, and nothing reads it. Trained and untrained runs were compared on the
demonstration pair and on a real 1,609 × 1,306-window pair: the record sets are
identical field for field — labels, `chain_len`, `matched_words`, block counts,
word ranges and snippets — and only `score` differs, with the score *ranking*
also differing at scale. A missing model therefore invalidates every
score-derived claim while leaving recall intact. `demo.py` refuses to run
without the model, which remains the correct behaviour for this reason rather
than for the loss of recall previously supposed.

### Stage 3: alignment

Alignment proceeds over **word lists**, not character *n*-grams. The words are
NFKD-normalised, combining marks are discarded and case is folded: accents and
breathings are removed before matching, which is a greater degree of
normalisation than "Unicode standardisation of the source texts". No
lemmatisation is performed.

Two words are treated as equivalent when

&nbsp;&nbsp;&nbsp;&nbsp;`ratio(a, b) = 1 − lev(a, b) / (|a| + |b|) ≥ fuzz_threshold` (0.75)

This is a length-normalised edit distance. It should not be paraphrased as "at
least 75% character overlap", nor as a tolerance of "one mismatched character
per *n*-gram". Because the denominator is the sum of the two lengths, the ratio
between two strings of equal length cannot fall below 0.5, and a threshold of
0.75 consequently admits any equal-length pair in which up to half the letters
differ: `το ~ τω` and `δε ~ τε` fall exactly on the threshold, `των ~ την` and
`μεν ~ μην` pass at 0.833, and bare numerals match one another on the same
terms — `103 ~ 104` and `605 ~ 603` at 0.833, `18 ~ 13` at 0.75.

Matching runs of equivalent words are assembled into blocks along a single
diagonal, with adjacent runs fused across up to `n_out` intervening
non-matching words. The production value is `n_out = 1`, so **gapped alignment
is employed, not excluded**, and a block is not necessarily contiguous.

Precision is supplied not by the similarity threshold but by the structural
filter applied afterwards: a block is retained only if its longest contiguous
core is at least `ngram` (4) words and the block totals at least
`min_chain_words` (2) matched words. Over three Plato windows against twenty
Proclus windows, 17,263 candidate blocks are generated and one survives. Within
the demonstration pair's surviving blocks, 213 word pairs are matched, of which
201 are string-identical; of the twelve fuzzy matches, most are genuine
morphological variants (`μελλει ~ μελλοι`, `ταλλα ~ ἄλλα`, `εαυτης ~ αυτης`,
`επισκεπτεον ~ σκεπτεον`) and one or two are not (`τουτο ~ ταυτα`). The
frequently repeated claim that the filters "kill short particle matches" should
therefore be attributed to the core-length criterion alone; the similarity
threshold admits those matches.

Levenshtein distance is computed in pure Python by a two-row dynamic program
with an `lru_cache`. There is no agglomerative chaining; `CHAIN_GAP` is
retained in the source for reference only.

### Properties that hold

Two properties of the alignment stage were verified and are protected by
regression tests.

The cheap length prune in `_word_match` is **sound**: it never rejects a pair
that the unpruned predicate would accept. Verified over 20,000 randomly
generated Greek word pairs at five thresholds, with no disagreement.

Every block is a **strictly increasing one-to-one pairing on a single
diagonal**: both sides contribute exactly the same number of distinct,
increasing indices. Verified over 78,713 blocks of the demonstration pair, with
no violation. It is this property that makes `chain_len` a two-sided quantity
and renders a separate `chain_j` unnecessary.

## Interpreting a match record

Fields that appear interchangeable are not, and reading them as though they
were is what makes the released tables appear internally inconsistent.

| field | meaning |
|---|---|
| `chain_len` | matched word **pairs** in the single longest retained block. The same number on both sides, because a block is a strictly monotone diagonal pairing. Despite the name, not an *n*-gram chain length. |
| `matched_words` | the **total** matched words on the **i** side across every retained block of the record. Not a symmetric count. |
| `matched_words_j` | the corresponding count for the **j** side. The engine computes this quantity and discards it; this package's harness re-derives it from the `matched_j` map, and `flame_pure_v2` emits it directly. The archived sweep predates the field: none of its 35,753 records carries it, and the report prints `–` rather than a fabricated `0`. |
| `n_chained` | the number of blocks that survived the filter. |
| `word_range_i/j` | the full extent of the match on each side, first to last matched word, internal gaps included. An extent, not a count. |
| `score` | the TF-IDF cosine of the unit pair. Candidate scoring only; it neither orders nor gates, and it is not comparable between work pairs. |
| `snippet_i/j` | the matched span with six words of context on each side, hence always wider than the match it describes. |

The two sides are counted independently: `_block_word_maps` de-duplicates word
indices per side, and blocks occupy different diagonals (`d = j − i`), so a
word may pair with several partners across blocks and be removed from one side
only. A measured instance: `616/#3 × In Rempublicam/4v#181` carries 31 matched
words on the i side and 19 on the j side, over extents of 49 and 21 words.
Replaying 295 archived records against the engine, 274 show equal counts and 21
differ. Comparing one side's count against the other side's extent is therefore
meaningless.

Because ordering is by `chain_len`, a fragmented record is ranked below a
compact one even when it carries more evidence in aggregate. In the
demonstration, `598/#3 × 101r#65` gives 53/53/53 because it consists of a
single block, whereas `598/#1 × 101r#36` gives 49/90/95 because it consists of
four.

## The reported run

| | |
|---|---|
| corpus | 29 built works, 406 pairs, exhaustive all-pairs with `i < j` |
| thresholds | `ngram=4`, `n_out=1`, `fuzz=0.75`, `min_chain=2`, `max_candidates=1000` |
| output | 35,753 raw matches over 376 populated pairs; 8,353.9 s on one workstation, no GPU |
| match data | `../logs/text_reuse_matches.ndjson` |
| derived figures | `../scripts/compute_reported_numbers.py` → `../results/reported_numbers.json` |

The value of `max_candidates` is recoverable from the released data, although
no field records it directly. A record can exist only for a candidate that was
actually evaluated, so the number of records per work pair is bounded above by
the cap. Across all 376 populated pairs the maximum is exactly 1,000, none
exceeds it, and the pair that attains it — Arethas, *Scholia in Porphyrii
Isagoge* × *Scholia in Categorias*, a near-duplicate pair whose scores reach
1.0 — exhibits the signature of rank truncation: its chain lengths begin at 19,
whereas every unsaturated pair is dominated by chains of 4 to 8. The
next-largest pair, with 965 records, carries 99 records at chain 4. This is
consistent with the `--max-candidates 1000` recorded in the project log, and
inconsistent with the code default of 4,000.

Note that `demo.py` runs at the code default. On the demonstration pair only
ten candidates exist, so the difference is inert there, but the demonstration
does not exercise the production value.

## Reproducibility

The engine itself may be re-run, and may be verified to reproduce the strongest
cross-author match in the released data, by `python3 engine/demo.py`. Every
figure in the paper may be recomputed from the shipped match data by
`python3 scripts/compute_reported_numbers.py`, which depends on the standard
library alone.

The full 29-work sweep cannot be re-run from this archive. Its input corpus is
TLG-derived, in part produced by OCR of CAG and Patrologia Graeca scans, and
cannot be redistributed; only the three ancient controls used in the paper are
freely available. The corpus metadata that would permit reconstruction under an
institutional TLG subscription, `corpus_manifest.yaml`, is not included in this
release, although §3 of the manuscript states that it is.

The demonstration is constructed in the opposite direction for this reason: it
takes the two corpus units of a match recorded in the released data, so that a
reader may observe the shipped engine reproduce a reported result without
licensed input.

## Limitations of the reported run

The items below are properties of the code and of the corpus as they stood for
the reported run. Each was measured; none is a conjecture. Where a remedy
exists it is identified, and the remedies are implemented in the parallel
pipeline documented in [`../PIPELINE_V2.md`](../PIPELINE_V2.md), not here.

**Retrieval is directional.** Described under
[Stage 1](#stage-1-candidate-retrieval). Remedied in `flame/flame_pure_v2.py`
by capping each side against its own unit count and pruning a bigram only when
it is over-frequent on both, a predicate invariant under exchange of the
arguments. Measured outcome: the two directions become identical, and the
result is a strict superset of the frozen engine's forward direction.

**The score is not comparable between work pairs.** Described under
[Stage 2](#stage-2-scoring). Remedied by
`flame_pure_v2.build_corpus_index()`, which derives one vocabulary, hash base
and IDF for the entire corpus.

**One continuous parallel may be recorded several times.** Units are 140-word
windows at a step of 115, so adjacent windows overlap by 25 words on both
sides, and a single alignment may yield more than one `(unit_i, unit_j)`
record. In the released sweep this is not marginal: 6,667 of the 35,753 records
(18.6%) re-report a passage already listed, leaving 29,086 distinct passages in
4,925 groups. A count of matches taken from the raw NDJSON is a count of
records, not of passages. Which side of a group varies is not fixed. Collapsing
the groups within the pipeline would alter every count the paper reports and is
left as an editorial decision.

**The Proclus text carries its critical apparatus inline.**
`tlg4036.tlg001` (*In Rempublicam*, Kroll) is the only work in the corpus with
`source_type: scaife_text`, and in it the apparatus is interleaved with the
body text rather than held in a separate field: `… ἦθος [p. 605a],
ἀπανοὐδετέρα 3 6 nempe ἄλλῃ 7 ἔχει 11 cf. Δ 104 16 etc. ξ 421 π 898 13 ἀφορί
603e sqq. 18 possis 〈κατὰ〉 τὸ γ 146 etc. … τησόμεθα …`. Latin apparatus words,
manuscript sigla and bare line numbers thus enter the Greek word stream.
Measured on the shipped sample *after* `_clean_text()` has run: of 10,715
tokens, 255 are bare numerals (2.4%) and 476 are Latin-script (4.4%) — `Pl`×45,
`f`×38, `ex`×29, `cf`×25, `p`×24, `ss`×22. The cleaning stage removes 87 tokens
and no numerals at all. The contamination is consequential because the
similarity threshold matches numerals to one another, as noted under
[Stage 3](#stage-3-alignment).

Applying a principled token filter — removing bare numerals and Latin-script
tokens from segments that are predominantly Greek, as implemented in
`scripts/find_text_reuse_v2.py` and observable through `scripts/demo_v2.py` —
reduces the Proclus unit from 95 windows to 92 (−434 words, −3.3%) and raises
the `#36` record from 90 to 104 matched words and from 0.4373 to 0.5708. The
`#64` and `#65` records do **not** merge under such a filter; they remain
separate at 29 and 53. The defect is one of corpus construction, upstream of
the engine, and the appropriate remedy belongs in the corpus builder, where the
apparatus column remains identifiable. Any change to this text re-phases the
windows and therefore invalidates every `#k` reference and the anchor asserted
by the demonstration: it constitutes a re-run of the sweep, not a patch.

**The era taxonomy is coarse by design and is not a substitute for
chronology.** The corpus employs four `era` values — `7th_8th`, `9th_10th`,
`11th_12th` and `ancient_classical` — of which the last is a single control
layer for everything pre-Byzantine. The demonstration's Plato (4th c. BC) ×
Proclus (5th c. AD) pair is consequently reported as a same-layer match across
some nine centuries. Subdividing that bucket into Classical, Hellenistic, Roman
and Late Antique would materially improve the era-layer tables of §5, but it is
a taxonomy change: it touches the manifest, `ERA_RANK` and `ALL_ERAS`, and
every era-pair figure the paper reports. It must therefore be decided and
applied across the pipeline at once, which is why only the misleading label was
corrected in the reporting layer.

**The engine emits no diagnostics.** A misconfiguration is visible only in the
output. In particular `ngram`, `n_out`, `min_chain_words` and `fuzz_threshold`
are clamped rather than validated — a request for `ngram=99` silently yields 8
— and `CAP_WORDS = 400` truncates over-long units. Neither takes effect under
this harness, whose windows are 140 words, but both are hazards for any other
caller. `flame_pure_v2` reports all of them in its metadata.

**`bpe_pure.tokenize_words()` called before `load()`** returns character-level
symbols rather than subword symbols, an ordering defect that is latent in the
production path only because `flame_pure._units()` calls `is_trained()` first.
Repaired in `flame/bpe_pure_v2.py`.

**Nothing in the artefacts pins the corpus version.** The era labels and every
`word_range` derive from the corpus build, so a corpus correction moves the
`#k` labels and the word offsets without any matching parameter changing; old
and new reports then agree on nothing positional. The report header carries
`Corpus: … — <manifest sha256>` as a reference point, and `find_text_reuse_v2.py`
additionally writes a `text_reuse_matches.meta.json` provenance sidecar. Its
absence from the reported run is why `max_candidates` had to be recovered
indirectly.

**`engine/` and `scripts/find_text_reuse.py` both resolve `ROOT` to the release
root** and would therefore write to the same `logs/` paths.
`engine/find_text_reuse.py` is the localised copy, requiring no external
checkout, and should be treated as authoritative for reading and running.

**No profitable optimisation was identified.** Two candidate improvements were
measured and rejected: precomputing the modular powers outside the inner loop
of `_hashes` yields 0.92–1.15×, and memoising `_word_match` yields 0.95×, since
`_lev_dist` is already cached and the length prune is inexpensive. The dominant
cost is the construction of the 140 × 140 match matrix itself, at 183–237 ms
per unit pair, which is intrinsic to the algorithm as specified.

## Relation to the public FLAME tool

[`kreeedit/FLAME`](https://github.com/kreeedit/FLAME) (Apache-2.0) is the
original tool, developed for medieval charters. Its documented pipeline belongs
to the same method family: leave-*n*-out *n*-grams over BPE subword tokens with
an automatically suggested vocabulary size, hashed with a vectorised polynomial
rolling hash and compared by a TF-IDF-scaled cosine, with an automatic (Otsu)
or fixed similarity threshold. It ships a graphical interface, autonomous
parameter tuning, and interactive HTML reports.

The engine used here is an independent pure-Python reimplementation of that
method by the same author, and it is the version that ran for this paper.

| | public FLAME | this engine |
|---|---|---|
| *n*-gram window | 6 (default) | 4 |
| rolling hash | vectorised (NumPy) | plain Python, modulo 2⁶¹−1 |
| BPE vocabulary | auto-sized per corpus | fixed: 3,000 merges, 50 stop-subwords |
| similarity | the cosine decides | the cosine scores only; it never orders or gates |
| candidate retrieval | sparse feature matrix | word-bigram inverted index |
| alignment | — | word-level Levenshtein with `n_out` gap fusion |
| interface, tuning, HTML reports | yes | none |
| licence | Apache-2.0 | MIT |

Two points follow. Neither tool performs hash-collision clustering or
agglomerative chaining, so the mechanism attributed to FLAME in §4 of the
manuscript describes neither implementation. And the retrieval and alignment
stages are specific to this engine and are where the reported behaviour
originates, which is why §4 should be rewritten from the present document
rather than from the public tool's documentation.

## Deviations from the production files

`flame/flame_pure.py`, `flame/bpe_pure.py`, `data/bpe_vocab.json` and `LICENSE`
are byte-identical to their sources in the working tree, verified by `cmp` in
addition to the checksums in `MANIFEST.sha256`. The only file edited for the
release is the harness — fourteen hunks in three groups, none of which touches
the matching logic; candidate generation, Levenshtein alignment and the filters
are byte-identical.

**(a) Packaging, so that the engine loads from this directory** (hunks 1–6):
the module docstring describes the bundled layout; `import yaml` is removed
from the top level and made lazy inside `load_manifest()`; `BUNDLED_FLAME_DIR`
is added and `DEFAULT_KONI_ROOT` defaults to `None`, in which case `load_flame()`
loads the bundled `flame/` package while an explicit path takes the original
cross-repository route unchanged; the corresponding option default and help text
are adjusted.

**(b) Run-parameter provenance** (hunks 7–8): the report header records
`max_candidates` alongside the other thresholds, and the `--report-only` branch
passes it too, so the header is self-consistent on both paths.

**(c) Report rendering** (hunks 9–15): the cross-author and intra-author
breakdown is reconciled with the display threshold it is computed under;
snippets are clipped at word boundaries rather than at a raw character offset;
the `ancient_classical → ancient_classical` label states that it is a single
control layer rather than an intra-era match; header pluralisation is
corrected; the header threshold and the filter are computed once so they cannot
disagree; the tables carry `blocks`, `score` and the per-side spans with a
legend defining them, records that re-report the same passage are grouped, and
a note is emitted when the leading row is not the strongest by matched words or
by score; `matched_words_j` is added so that `gap_j` is computed from its own
side's count rather than from the i side's; and three guards prevent the report
from being silently stale, empty or malformed.

The original production files are unchanged in the working project, so the
reported run remains reproducible from them. Comments and docstrings in the
harness are in Hungarian, as in the original. No shipped artefact is affected by
group (c): none of the Markdown files under `../logs/` or `../results/` is
`write_markdown` output. The production copy at `../scripts/find_text_reuse.py`
retains the group (c) behaviour; backporting is a separate decision, since the
release is frozen.

## Dependencies

| component | requires |
|---|---|
| `flame_pure`, `bpe_pure` and their v2 forks | Python 3.8+, standard library only |
| `demo.py`, `scripts/demo_v2.py` | standard library only |
| `find_text_reuse.py`, `find_text_reuse_v2.py` (full sweep) | PyYAML for the manifest, plus the corpus |
| `scripts/filter_by_wp_v2.py` | pandas |

## Citation

Please cite the paper for the corpus and the findings, and FLAME for the
method. The citation is given in `NOTICE.md`, together with the licensing of
the engine (MIT) and of the bundled samples (CC BY-SA 4.0, PerseusDL / Open
Greek and Latin).

---

*Prepared 16 September 2026; revised 19 September 2026 following the audit
recorded in [`../AUDIT.md`](../AUDIT.md). Engine and model copied from the
working tree as of the earlier date; sample texts extracted from the paper's
corpus with the citation unit and window numbering preserved.*
