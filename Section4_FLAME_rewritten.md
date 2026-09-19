# §4 — FLAME: The Matching Engine (rewritten from the measured behaviour)

> **Status.** This is a *replacement draft* for §4 of
> `Eustratius_Implicit_Authority_Paper_Draft.md:125-131` and for the identical
> §3 of `Methodology_Section_Pilot.md:63-69`. It is placed **beside** those
> files, not over them: swapping it in is an editorial decision, and two of the
> corrections below (the candidate cap, the score gates) reach into §5, so the
> two sections have to move together.
>
> Every claim here is measured against `engine/flame/flame_pure.py` as shipped
> and against `logs/text_reuse_matches.ndjson` as released; the measurements are
> listed in [`AUDIT.md`](AUDIT.md) and locked by `tests/test_flame.py`.
>
> The later, unshipped `..._v0.4.md:118` fork disclaimer is **inverted** and
> should be deleted rather than edited: it says the fork's Phase 2 "uses
> hash-collision clustering rather than the TF-IDF/cosine-similarity approach
> documented in the public repo's README", whereas the fork uses neither
> hash-collision clustering (it uses a word-bigram inverted index) nor
> cosine-based selection (it computes a cosine and never reads it). That file is
> not part of this release and could not be inspected directly.

---

## 4. FLAME: The Matching Engine

Text reuse is detected by FLAME (Fuzzy Levenshtein-tolerant Ancient Matching
Engine), a word-level alignment engine for morphologically rich historical
languages. The implementation that produced the numbers reported here is the
pure-Python, standard-library-only reimplementation shipped as
`engine/flame/flame_pure.py`; it is a sibling of, and not identical to, the
public `kreeedit/FLAME` tool, whose documented pipeline differs in the
particulars set out at the end of this section. FLAME performs an exhaustive
all-pairs sweep: every comparison unit of every work is matched against every
unit of every other work.

### Segmentation

Each work is first passed through a cleaning stage that removes modern
editorial metadata (CTS URNs, EpiDoc/TEI markup, Creative Commons licence
lines), a conservative list of critical-apparatus notations (`om.` with its
period, marginal line marks of the form `4a`, `q38`), and four fixed scholastic
transition formulas. The cleaned text is grouped into citation-page units and
then cut into **sliding windows of 140 words stepping by 115** (a 25-word
overlap); windows are *not* aligned to sentence boundaries. Window labels carry
the page and the window ordinal, which is why a match reference reads
`In Rempublicam/101r#65`.

Two properties of this stage bear directly on how the match counts should be
read.

First, **the cleaning is not exhaustive on one work, and that work is the
largest in the corpus.** Proclus, *In Rempublicam* (`tlg4036.tlg001`) is the
only work drawn from a Scaife running text in which the Teubner critical
apparatus sits inline in the body rather than in a separate field. On the
released sample of that work, after cleaning, **2.4% of the tokens the engine
sees are bare numerals and a further 4.4% are Latin-script apparatus words**
(`Pl`, `f`, `ex`, `cf`, `p`, `ss`, `corr`). The cleaning stage removes 87 of
10,802 tokens there and none of the numerals. This is a corpus-construction
defect upstream of the engine; it costs both recall and score, and it interacts
with the matching threshold described below, which admits numeral-to-numeral
matches. Repairing it belongs in the corpus builder, and because any change to
that text re-phases its windows, it invalidates every `#k` reference in the
present results — it is a re-run, not a patch.

Second, **overlapping windows re-report the same passage.** Because adjacent
windows share 25 words on both sides, one continuous parallel can surface as
several `(unit_i, unit_j)` records: 6,667 of the 35,753 released records
(18.6%) re-report a passage already listed, leaving 29,086 distinct passages.
A count of "matches" taken from the raw NDJSON is a count of *records*, not of
passages.

### Phase 1 — Candidate retrieval

Candidate unit pairs are proposed by an **inverted index over normalized word
bigrams**, not by character n-grams and not by hash collisions. A pair is
retained when it shares at least three bigrams; bigrams occurring in more than
`max(40, 4% of the units on the second side)` units are skipped as too common.
The retained pairs are ordered by **shared-bigram count**, and the first
`max_candidates` of them go forward to alignment. The production sweep ran with
`max_candidates = 1000`.[^mc]

This stage is **directional**. The frequency cap is computed from, and applied
to, the second argument only; the first side's bigrams carry no cap at all.
Swapping the two arguments therefore changes which bigrams are pruned, hence
the candidate set. Measured on a real Greek pair at the corpus's own scale
(1,609 × 1,306 windows), the two directions produce **3,617 and 8,402
candidates** with a Jaccard overlap of 0.26, and the shared-bigram count itself
differs on 428 of the 2,513 pairs common to both. Run to completion in both
directions, that becomes **304 against 515 match records**, and at a chain
threshold of 6 — the cut-off §5 applies to the intra-Byzantine set — **6
against 12**: reversing the argument order doubles the reportable matches on
that pair and loses none of them. What the direction does *not* affect is the
content of a record that both directions find: on all 242 such records every
field agrees, `score` included. The asymmetry is therefore a recall effect
only. The sweep's `i < j`
enumeration fixes one direction per work pair by the corpus's chronological
sort order; the results reported here are the results of that direction. This
is a property of the implementation, not a design choice, and it should be
removed before the engine is reused.

### Phase 2 — Scoring (reported, but inert)

Each candidate pair is given a TF-IDF cosine over leave-n-out rolling hashes of
its BPE subword 4-grams (3,000 learned merges, the 50 most frequent
purely-grammatical endings suppressed). This is the `score` field on every
match record.

**The cosine neither orders nor gates anything.** The order in which matches
are emitted is the shared-bigram order of Phase 1; the similarity cut-off is
the module default `None` → `0.0`, which every non-negative score passes, and
the harness exposes no flag to change it. An automatic threshold is computed
and then never applied. On the released data, 331 of the 359 work pairs with
more than one record are **not** score-monotone in file order.

Two consequences follow, and both are load-bearing for §5.

1. **`score` is not comparable between work pairs.** The inverse document
   frequencies are recomputed inside each `compare` call, from the units of
   that call alone; in an all-pairs sweep that means once per work pair. The
   same unit pair scores differently depending on which other units shared its
   call, and the per-pair score ranges in the released data run from a maximum
   of 0.0000 on some pairs to 1.0000 on others. Any absolute threshold on
   `score` is therefore applied to quantities on different scales. The
   work-package gates in §5 are exactly such thresholds, and they are not
   marginal: `score ≥ 0.001` removes 12 of the 19 chain-≥6 candidates in WP1
   and 19 of the 33 in WP2, i.e. it, rather than the chain-length criterion,
   determines the reported counts of 7 and 14. In WP3 (`score ≥ 0.01`) it
   removes 15 of 693.
2. **The BPE model affects the score and nothing else.** With the model absent
   the engine falls back to plain normalized-word hashing. Measured on the demo
   pair and on a real 1,609 × 1,306-window pair, the record sets are identical
   field for field — labels, `chain_len`, `matched_words`, block counts, word
   ranges, snippets — and only `score` moves; at scale the score *ranking* moves
   too. The reason is structural: both branches tokenize words with the same
   `\b\w+\b` regular expression, so candidate retrieval and alignment receive
   identical input either way, and the only BPE-dependent quantity is the one
   nothing reads.

### Phase 3 — Alignment

Alignment runs on **word lists**, not on character n-grams. The words are
NFKD-normalized, combining marks dropped and lowercased — that is, **accents
and breathings are stripped before matching**, which is more normalisation than
"Unicode standardisation of the source texts". No lemmatization is performed.

Two words are treated as matching when

$$\text{ratio}(a,b) \;=\; 1 - \frac{\mathrm{lev}(a,b)}{|a| + |b|} \;\ge\; 0.75 .$$

This is a length-normalized edit distance, and it should not be paraphrased as
"at least 75% character overlap" or as "each n-gram tolerates at most one
mismatched character". Because the denominator is the *sum* of the two lengths,
the ratio of two strings of equal length can never fall below 0.5, and a
threshold of 0.75 therefore admits any equal-length pair in which **up to half
the letters differ**: `το ~ τω` and `δε ~ τε` sit exactly on the threshold,
`των ~ την` and `μεν ~ μην` pass comfortably at 0.833, and so do bare numerals
— `103 ~ 104`, `605 ~ 603`, `18 ~ 13` — which is what makes the inline
apparatus of the Proclus text a matching problem and not merely a cosmetic one.

What keeps this from flooding the output is not the similarity threshold but
the **structural filter applied afterwards**: a run of matched words is kept
only if its longest contiguous core is at least `ngram` (4) words long *and*
the run totals at least `min_chain_words` (2) matched words. On three Plato
windows against twenty Proclus windows, 17,263 candidate blocks are generated
and 1 survives. Measured on the demo pair's surviving blocks, 213 word pairs
are matched of which 201 are string-identical; of the 12 fuzzy matches most are
genuine morphological variants (`μελλει ~ μελλοι`, `ταλλα ~ ἄλλα`,
`εαυτης ~ αυτης`, `επισκεπτεον ~ σκεπτεον`) and one or two are not
(`τουτο ~ ταυτα`). The precision of the reported matches is thus a property of
the core-length filter; the similarity threshold on its own is permissive.

**Gapped alignment is used, not excluded.** Adjacent matched runs on the same
diagonal are fused across up to `n_out` intervening non-matching words, and the
production value is `n_out = 1`. A block is therefore not necessarily
contiguous, which is why a record can show a span wider than its matched-word
count even when it consists of a single block. Alignment is nonetheless strictly
monotone and one-to-one: every block pairs words `(s+k, s+k+d)` on a single
diagonal, so both sides contribute exactly the same number of distinct,
increasing indices. Verified over 78,713 blocks of the demo pair with zero
violations.

### What a match record contains

For each surviving pair FLAME records the work identifiers, the citation-page
and window references, the TF-IDF cosine (`score`), the number of matched word
pairs in the single longest kept block (`chain_len`), the total matched words
on the first side across all kept blocks (`matched_words`), the first-to-last
extent of the match on each side (`word_range_i/j`, internal gaps included),
the matched snippets with six words of context on each side, and the
chronological era of each side. Output is written to NDJSON and flat TSV.

Three of these are routinely misread and the tables should name them
explicitly. `chain_len` is a count of matched *pairs* in one block, not an
n-gram chain length, and it is the same number on both sides. `matched_words`
counts the **first side only**; the second side's count is not in the released
records at all, so it cannot be recovered from the archive. `word_range` is an
extent, not a count. Comparing one side's count against the other side's extent
is meaningless.

The Match IDs cited in §6 are the 1-based positions of their records in
`text_reuse_matches.ndjson`. On the 29-work corpus the sweep evaluated 406 work
pairs in approximately 140 minutes on a standard workstation without GPU
acceleration, and produced **35,753 raw matches** across 376 populated pairs.
All numerical claims in this paper are computed from that raw set by a single
script (`compute_reported_numbers.py`), released with the archive together with
its output (`reported_numbers.json`), which records input hashes and run date.

### Relation to the public FLAME tool

The public `kreeedit/FLAME` (Apache-2.0) implements the same method family —
leave-n-out n-grams over BPE subwords, hashed and compared by a TF-IDF-scaled
cosine, with an automatic or fixed similarity threshold — but it lets the
cosine decide, retrieves candidates from a sparse feature matrix, defaults to
`ngram = 6`, auto-sizes its BPE vocabulary, and ships a GUI and interactive
HTML reports. The engine used here fixes `ngram = 4` and a 3,000-merge
vocabulary, retrieves candidates from a word-bigram inverted index, scores with
a cosine it does not act on, and aligns with word-level Levenshtein and gap
fusing — a stage the public tool does not have. Neither tool performs
hash-collision clustering or agglomerative chaining; a description of FLAME in
those terms describes neither implementation.

[^mc]: The value was previously recorded as unrecoverable. It is recoverable
    from the released data: a record can exist only for a candidate that was
    actually evaluated, so records-per-work-pair is bounded above by
    `max_candidates`. Across all 376 populated pairs the maximum is exactly
    1,000, no pair exceeds it, and the pair that reaches it (Arethas, *Scholia
    in Porphyrii Isagoge* × *Scholia in Categorias*, a near-duplicate pair whose
    scores reach 1.0) shows the truncation signature: its chain lengths begin at
    19, whereas every unsaturated pair is dominated by chains of 4 to 8. That is
    rank truncation at 1,000, matching the `--max-candidates 1000` recorded in
    the project log. The cap is not a fine-tuning parameter at this scale:
    measured on three real Greek work pairs of comparable size, the candidate
    sets run to 3,617 / 6,707 / 11,574 pairs, so 1,000 retains 28%, 15% and 9%
    of them. At record level on Herodotus × Thucydides, a cap of 1,000 yields
    103 records where 4,000 yields 304 — 66% of the records lie above rank
    1,000 — and 4 against 6 at a chain threshold of 6. Any future run must
    state the value explicitly.
