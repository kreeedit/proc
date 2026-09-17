# The text-reuse engine used for this paper

**Short answer to "which software did you use?"** — The matches reported in this
paper were produced by the **FLAME text-reuse engine as implemented in
`flame/flame_pure.py`** (a pure-Python, standard-library-only reimplementation of
FLAME's Leave-N-Out n-gram method), driven by the sweep harness
`find_text_reuse.py`. Both are included here in full; `flame/flame_pure.py` is the
exact file that ran, byte-for-byte.

This is **not** the public [`github.com/kreeedit/FLAME`](https://github.com/kreeedit/FLAME)
tool — see [Relationship to the public FLAME tool](#relationship-to-the-public-flame-tool).

> **Note for anyone reading the manuscript alongside this code.** The three
> phases described in §4 of the shipped draft
> (`../docs/Eustratius_Implicit_Authority_Paper_Draft.md:125-131`, repeated in
> `../docs/Methodology_Section_Pilot.md:63-69`) are **not** what this code does:
>
> | §4 says | the shipped engine does |
> |---|---|
> | Phase 1: character-level **quadrigrams** | BPE **subword** 4-grams (`bpe_pure`) |
> | Phase 2: **n-gram hash collisions clustered** | **word-bigram inverted index** |
> | Phase 3: **character-level** Levenshtein, chains of consecutive words | **word-level** Levenshtein, fusing up to `n_out` intervening words |
> | "No orthographic normalisation … surface forms throughout" | accents **stripped** (NFKD + drop combining marks) and lowercased before matching — more than the "Unicode standardisation" §4 allows for |
> | "deliberately excludes gapped (non-adjacent) alignment" | gaps of up to `n_out` (production: 1) word **are** fused |
>
> The authoritative description of the engine that produced the reported numbers
> is [What the engine actually does](#what-the-engine-actually-does) below. §4
> should be rewritten from it — do not treat §4 as a specification of this
> package. A *later*, unshipped draft
> (`../../pilot_cases_for_jonathan/Eustratius_Implicit_Authority_Paper_Draft_v0.4.md:118`)
> adds a fork disclaimer, but its specifics are inverted too: it says the fork's
> Phase 2 "uses hash-collision clustering rather than the TF-IDF/cosine-similarity
> approach documented in the public repo's README", when in fact neither phase is
> hash-collision clustering and the code does compute a TF-IDF cosine.

---

## Layout

```
engine/
├── README.md                     this file
├── NOTICE.md                     provenance, licensing, attribution  ← read with LICENSE
├── LICENSE                       MIT (the engine code)
├── demo.py                       runnable, self-contained demonstration  ← start here
├── find_text_reuse.py            the sweep harness (drives the engine over a corpus)
├── flame/
│   ├── __init__.py               package marker (docstring rewritten for the
│   │                             standalone package — the one non-identical
│   │                             file in this directory)
│   ├── flame_pure.py             THE ENGINE  (compare_iter is the entry point)
│   └── bpe_pure.py               BPE subword tokenizer (loads ../data/bpe_vocab.json)
├── data/
│   └── bpe_vocab.json            trained BPE model (3,000 merges + 50 stop-subwords)
└── samples/
    ├── plato_respublica_598.json
    └── proclus_in_rem_publicam_101r.json   ← the two corpus units the demo compares
```

## Run it

```bash
python3 engine/demo.py                # no packages to install; writes engine/demo_out/
```

Expected: five matches between the two samples, the largest being a **chain of 53
words** at `598/#3` × `In Rempublicam/101r#65`. That is the strongest
cross-author correspondence in the released match data — Plato × Proclus, chain
53, against a next-best cross-author chain of 51 (`logs/text_reuse_matches.ndjson`,
all 35,753 rows scanned) — so the demo is a verification of the shipped engine
rather than an illustration. Note that the manuscript itself does not cite this
pair (§6 cites Proclus `101r#72`, `121v#138`, `18r#11`), so "strongest in the
data" is not the same as "most significant in the argument". It exits non-zero if
the anchor is not reproduced, and also if the BPE model is missing (the engine
degrades *silently* without it — see [Known caveats](#known-caveats)).

The demo uses only redistributable PerseusDL / Open Greek and Latin text and runs
in under a second.

## Verify this package

```bash
cd engine && sha256sum -c MANIFEST.sha256      # 12 files
diff -u ../scripts/find_text_reuse.py find_text_reuse.py   # the release edits
# (identical to the working copy Byzantik/scripts/find_text_reuse.py, so either
#  path gives the same 14 hunks)
cmp flame/flame_pure.py <KONI>/app/flame_pure.py           # if you have KONI
```

## What the engine actually does

Three stages, in `flame/flame_pure.py`:

1. **Ranking (Phase 1).** Text is tokenized into **BPE subwords** (`bpe_pure`;
   3,000 learned merges, the 50 most frequent purely-grammatical endings
   suppressed as noise). Subword n-grams (`ngram=4`) are turned into
   **leave-n-out (LNO) rolling hashes** (`n_out=1`: each window hashed with one
   subword omitted) modulo 2⁶¹−1. This stage builds a feature vector per unit.
2. **Candidate retrieval.** An **inverted index over normalized word bigrams**
   proposes unit pairs (`min_shared=3` shared bigrams; bigrams present in more
   than `max(40, 4%)` of units are skipped as too common). Each proposed pair is
   then given a **TF-IDF cosine** score over the stage-1 hashes (IDF down-weights
   ultra-frequent morphemes). That cosine is reported on the match record as its
   `score`, but it **neither orders nor gates** anything: the pair order — and
   therefore which pairs `max_candidates` truncates — comes from the
   **shared-bigram count** (`flame_pure.py:393`), and the similarity cut-off is
   the module default `similarity_threshold=None` → `0.0`, which every pair
   passes. The harness exposes no flag to change it. So no match is decided here.
3. **Matching (Phase 2).** On **word lists** (NFKD-normalized, accents dropped,
   lowercase — no lemmatization), a hand-rolled **Levenshtein ratio ≥
   `fuzz_threshold`** (0.75) marks matching words; runs are fused across up to
   `n_out` intervening non-matching words. Strict filters then apply: the longest
   contiguous matched core must be ≥ `ngram` **and** total matched words ≥
   `min_chain_words`. Levenshtein is pure Python (two-row DP, `lru_cache`) — no
   `rapidfuzz`, no NumPy, no SciPy. There is **no agglomerative chaining**
   (`CHAIN_GAP` is kept in the source for reference only), and emitted matches
   are ordered by `chain_len`, never by score.

   *Note on the cosine:* it is computed, carried and reported, but nothing reads
   it. If you sort the released match data by `score` within a work pair you will
   see the scores are not monotonic — the ordering is by shared-bigram count, then
   by chain length. Anyone describing this engine as "ranking pairs by TF-IDF
   cosine" is describing the public tool's documented behaviour, not this code's.

Unit segmentation is the harness's job (`find_text_reuse.py`): segments are
grouped into **citation-page units**, cleaned (`_clean_text`: modern header and
licence lines, EpiDoc/TEI markup, critical-apparatus sigla, scholastic transition
formulas, milestone references), then split into **140-word windows with 25 words
of overlap** (step 115). That windowing is why units carry labels like
`In Rempublicam/101r#65` — page plus window ordinal.

## The production run

Recorded parameters of the sweep that produced the paper's numbers:

| | |
|---|---|
| corpus | 29 built works, 406 pairs (exhaustive all-pairs, i<j) |
| thresholds | `ngram=4`, `n_out=1`, `fuzz=0.75`, `min_chain=2` |
| output | **35,753 raw matches**, ≈140 min on one workstation, no GPU (`8353.9 s` logged) |
| match data | `../logs/text_reuse_matches.ndjson` (shipped in this release) |
| numbers in the paper | `../scripts/compute_reported_numbers.py` → `../logs/reported_numbers.json`; the copy shipped in this release sits at `../results/reported_numbers.json` (the script's output path is hard-coded to `logs/`, so a re-run will not overwrite it in place) |

Command as recorded in the project log (not a claim about which value was in
effect — see the note below):

```bash
python scripts/find_text_reuse.py --max-candidates 1000
```

> **One parameter is not pinned down.** The code default is `max_candidates=4000`
> and the paper draft states "default 4,000", but the sweep commands recorded in
> the project log carry `--max-candidates 1000`, and **no artefact of the run
> records which value was in effect**: the report header logged `ngram`, `n_out`,
> `fuzz`, `min_chain` only, and `logs/text_reuse_matches.ndjson` carries no
> run-parameter metadata. Before this parameter is cited, it should either be
> recovered from the run environment or the sweep re-run with an explicit value.
> A fresh sweep with the shipped harness now writes `max_candidates` into the
> report header, so the ambiguity cannot recur *for new runs*.
>
> `demo.py` runs with the code default, `max_candidates=4000` — that is the
> default, not a recovered production value.

## Reproducibility: what you can and cannot do from here

- **You can** re-run the engine itself, and verify it reproduces the strongest
  cross-author match in the released data — `python3 engine/demo.py`.
- **You can** recompute every number in the paper from the shipped match data —
  `python3 scripts/compute_reported_numbers.py` (standard library only,
  self-contained).
- **You cannot** re-run the full 29-work sweep from this archive. Its input
  corpus is TLG-derived (and partly OCR of CAG / Patrologia Graeca scans) and
  **cannot be redistributed**; only the three ancient controls used in the paper
  are freely available (PerseusDL / Open Greek and Latin). The corpus metadata
  that would let you rebuild it under an institutional TLG subscription —
  `corpus_manifest.yaml` — is *not* in this release, although the paper's §3
  states that it is.

The demo is deliberately built the other way round: it takes the two corpus units
of a match recorded in the released data, so a reader can watch the shipped engine
reproduce a reported result without any licensed input.

## Relationship to the public FLAME tool

[`kreeedit/FLAME`](https://github.com/kreeedit/FLAME) (Apache-2.0) is the original
tool, aimed at medieval charters. Its documented pipeline is the same method
family: **LNO n-grams** (`ngram` default 6, `n_out` default 1) over **BPE
subword** tokens with an automatically suggested vocabulary size, hashed with a
*vectorised* polynomial rolling hash, and compared by **TF-IDF-scaled cosine**
over shared sparse feature hashes, with an automatic (`Otsu`) or fixed similarity
threshold. It ships a GUI (`flame_gui.py`), *Autonomous Parameter Auto-Tuning*,
and interactive HTML reports (`text_comparisons_XX.html`,
`similarity_heatmap.html`).

The engine shipped here is an independent pure-Python reimplementation of that
LNO method by the same author — the KONI `NOTICE` states this explicitly — and it
is the version that actually ran for this paper. The differences that matter when
reading the code:

| | public FLAME | this engine |
|---|---|---|
| n-gram window | 6 (default) | **4** |
| rolling hash | vectorised (NumPy) | plain Python, mod 2⁶¹−1 |
| BPE vocabulary | auto-sized per corpus | **fixed** 3,000 merges + 50 stop-subwords |
| similarity | cosine decides | cosine **scores only** — never used to order or gate; matching is separate |
| candidate retrieval | sparse feature matrix | **word-bigram inverted index** |
| alignment | — | **word-level Levenshtein**, `n_out` gap fusing |
| GUI / auto-tune / HTML reports | yes | none |
| licence | Apache-2.0 | MIT (see `LICENSE`, `NOTICE.md`) |

Two things follow from the table. First, the public tool's documentation contains
no *hash-collision clustering* and no *agglomerative chaining* either, so the
mechanism §4 attributes to "FLAME" is documented nowhere — it is not a
description of the public tool, and it is not a description of this one. Second,
the retrieval and alignment stages above are specific to this engine and are
where the reported behaviour actually comes from; §4 should be rewritten from the
[section above](#what-the-engine-actually-does), not from the public tool's
documentation.

## How to read a match record

The fields that look interchangeable are not, and reading them as if they were
is what makes the released tables look internally inconsistent:

| field | meaning |
|---|---|
| `chain_len` | matched word **pairs** in the single longest kept block — the same number on both sides, because a block is a strictly monotone diagonal pairing (`matches` is built as `(s+k, s+k+d)`, so each side contributes exactly `n` distinct, increasing indices). *Not* an n-gram chain length, despite the name. |
| `matched_words` | **total** matched words on the **i side** across **every** kept block of that record. Not a symmetric count — see below. |
| `matched_words_j` | the same for the **j side**. Added by this release; the archived full sweep predates it, so there it is absent and the report prints `–` rather than a fabricated `0`. |
| `n_chained` | how many blocks survived the filter (`core >= ngram` **and** `n >= min_chain_words`). |
| `word_range_i/j` | full extent of the match on each side — first→last matched word, **internal gaps included**. |
| `score` | TF-IDF cosine of the unit pair. Candidate selection only; it never orders or gates. |
| `snippet_i/j` | the matched span **plus 6 words of context on each side**, so a snippet is always wider than the match it describes. |

The two sides are counted **independently**: `_block_word_maps` de-duplicates
word indices per side, and blocks sit on **different diagonals** (`d = j − i`),
so one word can pair with several partners across blocks and the de-duplication
then removes it from one side only. Measured example:
`616/#3 × In Rempublicam/4v#181` has 31 matched words on the i side but 19 on
the j side, over extents of 49 and 21 words. Replaying 295 of the archived
records against the engine: 274 have equal counts, 21 differ (16 with the j side
larger, 5 with the i side larger). Comparing one side's count against the *other*
side's span is therefore meaningless — an earlier draft of the demo report did
exactly that and produced negative "gaps", which is why the report now carries a
count per side.

`chain_len` is **not** affected by this asymmetry: it counts pairs in the longest
block, and 379 blocks replayed from the archive satisfy
`len(set(i-indices)) == len(set(j-indices)) == n` with both sides strictly
increasing — 0 violations. The `chain` ordering is therefore two-sided, and no
`chain_j` is needed.

So with one block `chain_len = matched_words` (= i-side count) and
`span_i = matched_words + gap_i`. In the demo, `598/#3 × 101r#65` is
53/53/53 **because it is a single block**, while `598/#1 × 101r#36` is
49/90/95 **because it is four** (95 = 90 + 5 on the i side, 98 = 90 + 8 on the
j side). Ordering by `chain_len` — which is what the
sweep does — therefore ranks a fragmented record *below* a compact one even when
the fragmented record carries more evidence and a higher cosine; the report
prints all of these plus `blocks` so the ordering is visible rather than implied.

## Known caveats

- **Silent degradation without the BPE model.** If `data/bpe_vocab.json` is
  missing or unreadable, `bpe_pure.load()` falls back to empty merges and the
  engine switches to plain normalized-word hashing — no subword tokenization, no
  stop-word filtering — while still returning plausible matches and printing
  nothing. `demo.py` checks for this and refuses to run; any other caller should
  too.
- **`bpe_pure.tokenize_words()` before `load()`** returns character-level symbols
  instead of subword symbols (a latent ordering bug in `bpe_pure.py`, harmless in
  the production path because `flame_pure._units()` calls `is_trained()` first).
- **No internal logging.** The engine emits no warnings or diagnostics; a
  misconfiguration is visible only in its output.
- **Nothing pins the corpus version in the artefacts themselves.** The era labels
  and every `word_range` come from the corpus build, so a corpus fix (such as the
  apparatus strip below) moves the `#k` labels *and* the word offsets without
  touching a single matching parameter — old and new reports then agree on nothing
  positional. The report header now carries `Corpus: … — <manifest sha256>` as the
  reference point (`corpus_ref()`); the hash of the manifest used for the reported
  run is recorded in [`../README.md`](../README.md).
- **One continuous parallel can be recorded several times.** Units are 140-word
  windows with a 25-word step, so *adjacent windows overlap by 25 words on both
  sides*, and the same alignment can produce more than one `(unit_i, unit_j)`
  record. In the released sweep this is not marginal: **6,667 of the 35,753
  records (18.6%) re-report a passage already listed**, i.e. there are 29,086
  distinct passages behind them. The demo shows the same effect at small scale —
  its 5 matches are 3 distinct passages, and the two pairs involved cover *one*
  continuous Plato×Proclus parallel each, split across Proclus windows #36/#37
  and #64/#65. **Nothing here changes the matching logic**; it is a property of
  the windowing. The report now states the distinct count and groups the
  duplicates (`[dup n]`), but a count of "matches" quoted from the raw NDJSON is a
  count of *records*, not of passages. Which side of a group differs is not
  fixed: measured over the released sweep, the i-extent is identical in 2,754 of
  the 4,925 groups and the j-extent in 2,633 — so "the j side overlaps" is true of
  the demo, not a law. Collapsing the groups in the pipeline
  instead would change every count the paper reports and is left as a decision
  (see below).
- **The Proclus text has the Teubner apparatus spliced into its running text.**
  `tlg4036.tlg001` (*In Rempublicam*, Kroll) is the one work in the corpus with
  `source_type: scaife_text`, and in it the critical apparatus sits **inline in
  the body text**, not in a separate field: `… ἦθος [p. 605a], ἀπανοὐδετέρα
  3 6 nempe ἄλλῃ 7 ἔχει 11 cf. Δ 104 16 etc. ξ 421 π 898 13 ἀφορί 603e sqq.
  18 possis 〈κατὰ〉 τὸ γ 146 etc. … τησόμεθα …`. That injects Latin apparatus
  words, manuscript sigla and bare line numbers into the Greek word stream
  (≈0.5% of its 198,474 words are apparatus tokens; 6,618 bare numbers). It is a
  corpus-construction defect upstream of FLAME, and it costs both recall and
  score. Measured on the demo by stripping the apparatus runs (137 tokens, 1.3%
  of the text): the `#64`/`#65` records **merge into a single chain of 57** (was
  29 and 53), and the `#36` record rises from 90 to **103** matched words and
  from 0.4373 to **0.5684** score. Only 1 of the 36 corpus works is affected, but
  it is the largest, and the fix belongs in the corpus builder (where the
  apparatus column is still identifiable), not in a regex over the finished
  text: a stripper clean enough to be safe here also removed a handful of
  genuine Greek words (≈8–10 per 10,878). Note also that **any change to this
  text re-phases the windows**, so it invalidates every `#k` reference and the
  anchor asserted below — it is a re-run of the sweep, not a patch.
- **`engine/` and `scripts/find_text_reuse.py` both resolve `ROOT` to the release
  root**, so both would write to the same `logs/` paths. `engine/find_text_reuse.py`
  is the localized copy (bundled engine, no KONI checkout needed); treat it as the
  authoritative one for reading and running.
- **The era taxonomy is coarse by design, and it is not a substitute for
  chronology.** The corpus uses four `era` values — `7th_8th`, `9th_10th`,
  `11th_12th` and `ancient_classical` — and `ancient_classical` is a *single*
  control layer for everything pre-Byzantine (`corpus_manifest.yaml`, header
  comment: "ókori/későantik kontrollkorpusz … az ókori a 'forrás', a bizánci a
  'fogadó'"). So the demo's Plato (4th c. BC) × Proclus (5th c. AD) pair is
  reported as a same-layer match, ~900 years apart. Splitting that bucket into
  Classical / Hellenistic / Roman / Late Antique would be a real gain for the
  era-layer tables in §5, but it is a **taxonomy change**: it touches the
  manifest, `ERA_RANK`/`ALL_ERAS`, and every era-pair figure the paper reports.
  It must therefore be decided and applied across the pipeline at once, not
  patched into the reporting layer — which is why only the misleading label was
  fixed here.

## Deviations from the production files

`flame/flame_pure.py`, `flame/bpe_pure.py`, `data/bpe_vocab.json` and `LICENSE`
are **byte-identical** to their sources in KONI (verified with `cmp`, in addition
to the sha256 in `MANIFEST.sha256`). The only file edited for the release is the
harness — **fourteen hunks** in three groups, none of which touch the matching
logic (candidate generation, Levenshtein alignment, filters are byte-identical):

**(a) Packaging — so the engine loads from this directory** (hunks 1–6)

1. module docstring — describes the bundled layout instead of the KONI checkout;
2. `import yaml` removed from the top level, replaced by a comment explaining why;
3. `BUNDLED_FLAME_DIR` added; `DEFAULT_KONI_ROOT` default changed to `None`;
4. `load_flame()` — `None` loads the bundled `flame/` package; an explicit path
   still takes the original cross-repo route *unchanged*;
5. lazy `import yaml` inside `load_manifest()` (the only PyYAML user);
6. `--koni-root` default and help text changed accordingly.

**(b) Run-parameter provenance** (hunks 7–8)

7. the report header now records `max_candidates` alongside the other thresholds;
8. the `--report-only` branch passes `max_candidates` too, so the header is
   self-consistent on both paths (it previously rendered `max_candidates=None`).

**(c) Report rendering and this release's own output layer** (hunks 9–14) — `demo_out/demo_report.md` is where you see
these, and they fix defects that made the report read as if it contained an
aggregation error:

9. **the breakdown now reconciles.** The cross-author / intra-author counts are
   computed *after* the `chain >= min_chain` display filter, but were printed
   without saying so — so a report could show "Total matches: 5" above
   "Cross-author: 4, Intra-author: 0", i.e. 4 ≠ 5, which looks like a lost match
   or a grouping bug. It is neither: the fifth match has `chain_len=5` and is
   below the threshold. The header now prints the full-partition breakdown, the
   shown-vs-total counts, and an explicit note of how many fall below.
10. **snippets are clipped at word boundaries** (`_clip()`), not at a raw
    character offset. The old `snippet[:70]` cut mid-word — `τραγῳ` for
    `τραγῳδίαν` — which is not publication-ready output. The function clips at
    the last space at or before the limit, and when the limit falls *inside the
    first word* it emits the whole word instead of a fragment; only a single
    unbreakable token is returned unchanged. (Verified by a property test over
    the demo snippets plus adversarial inputs — 70 texts × 5 limits, no
    mid-word cut, output always a prefix of the source or the source itself.)
11. **the `ancient_classical → ancient_classical` era label.** It used to read
    "(intra-era)", which is misleading: `ancient_classical` is a single control
    layer spanning antiquity to late antiquity, so it puts Plato (4th c. BC) and
    Proclus (5th c. AD) in one bucket. The label now says so. Byzantine buckets
    (`11th_12th` etc.) keep "(intra-era)", where it is accurate. **This is a
    label fix only — the era taxonomy itself is a design decision, not a bug;
    see the note below.**
12. pluralisation in the header (`1 pair`, `1 match`, not `1 pairs`).
13. **the header threshold and the filter now agree.** The header printed
    `report threshold: chain >= min_chain` while the filter used
    `max(min_chain, 1)`, so a run with `min_chain=0` said `chain >= 0` and then
    applied `chain >= 1`. The effective threshold is now computed once as `thr`
    and both places use it. (With the shipped demo parameters, `min_chain=2`,
    the two were already identical — the demo output is unchanged.)
14. **the reporting layer now separates records from passages, and names the
    metrics it prints.** Three additions, none of them touching matching: (i) the
    tables carry `blocks`, `score` and `span_i`/`span_j`, and a legend defines
    `chain_len` vs `matched_words` vs span — the fields that made the tables look
    self-contradictory; (ii) `_overlap_groups()` clusters records whose spans
    overlap within a work-pair (undone by the `#k` window label, so the *absolute*
    word position is recomputed via `_abs_span()`), the header states
    "Distinct passages: N", and the groups are listed with their merged extent;
    (iii) when the first row is not the strongest by `words` or `score`, a note
    says so explicitly. Wording fixes in the same hunk: the intra-author line
    reads "not applicable" instead of `0 of 0` when no two works share an author,
    both category lines now print a consistent denominator (threshold set, with
    the all-matches figure alongside), and "the philologically interesting reuse"
    — an overstatement for a commentary quoting its own lemma — is gone.
    `n_chained` and `word_range_i/j` were also added to the TSV columns. A fourth
    addition is a **correctness fix to this release's own draft**, not to the
    production code: the demo report's `gap_j` column first compared the j-side
    span against `matched_words`, which counts the **i** side, and clamped the
    resulting negative to zero — so 1,985 of the 35,753 archived records (all on
    the Plato × Proclus pair) would have shown a fabricated "no gap". The
    per-side count `matched_words_j` now exists in the record (taken from the
    `matched_j` map `flame_pure` already returns, so the engine file stays
    byte-identical), `gap_i`/`gap_j` are computed from their own side's count,
    and a record that predates the field prints `–` instead of `0`.
15. **the report can no longer be silently stale or malformed.** Three guards,
    all in the reporting layer: (i) `write_markdown()` used to *drop the report*
    when exactly one era pair is populated — the collapse branch returned before
    the final `path.write_text()`; (ii) `demo.py` now requires every output to be
    **fresh** (mtime recorded before the run, so a file left over from an earlier
    run cannot pass — the profile of the original bug), non-empty, and present,
    and the main audience-facing table is routed through the same checked emitter
    as the era tables instead of being appended directly; (iii) `_assert_table_shape()`
    verifies header, separator and every data row have the same cell count, because
    a separator with one cell too many turns the whole table into raw text in
    strict Markdown renderers — the shipped demo had exactly this defect (14 cells
    vs 13). The tables also gained `Corpus: … — <manifest sha256>` provenance (see
    item (i) below), so two reports made from different corpus builds are
    distinguishable even when the matching parameters are identical (see
    "Corpus version" in [`../README.md`](../README.md)).

The original production files are unchanged in the working project, so the
reported run remains reproducible from those. Notes:

- The comments and docstrings in the harness are in Hungarian, as in the original.
- **No shipped artefact is affected by group (c).** None of the `.md` files in
  `../logs/` or `../results/` is `write_markdown` output (verified: none contains
  the `# Byzantik — Text-reuse report (FLAME)` header), so the released reports
  remain exactly as generated. Group (c) only changes what a *new* run prints.
- The production `../scripts/find_text_reuse.py` still has the group (c)
  behaviour. Backporting it is a separate decision — it would change the
  release's own script, and the release is frozen at `6556013`.

Diff the two copies yourself:

```bash
diff -u scripts/find_text_reuse.py engine/find_text_reuse.py
```

## Dependencies

| component | requires |
|---|---|
| engine (`flame_pure`, `bpe_pure`) | Python 3.8+ standard library only |
| `demo.py` | standard library only |
| `find_text_reuse.py` (full sweep) | PyYAML (for the manifest), plus the corpus |

## Citing the software

Please cite the paper for the corpus and findings, and FLAME for the method — the
citation is in `NOTICE.md`, along with the licensing of the engine (MIT) and of
the bundled samples (CC BY-SA 4.0, PerseusDL / Open Greek and Latin).

---

*Prepared 2026-09-16. Engine and model copied from the KONI working tree as of
that date; sample texts extracted from the paper's corpus with the citation unit
and window numbering preserved.*
