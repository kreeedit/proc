# The fixed pipeline (v2)

What the 2026-09-19 audit ([`AUDIT.md`](AUDIT.md)) found broken, implemented and
tested. Read the audit first for the measurements; this file is how to run the
result.

> **The paper's numbers have not changed.** Nothing in the release was rewired:
> `engine/demo.py`, `engine/find_text_reuse.py` and `scripts/find_text_reuse.py`
> all still load the frozen `flame_pure`, and `python3 engine/demo.py` still
> reproduces the chain-53 anchor. The v2 pipeline is a parallel set of files
> that writes to parallel output directories. The figures in the paper move only
> when someone re-runs the 406-pair sweep with it — which needs the TLG-derived
> corpus that is not in this release.

---

## The files

| file | replaces | why it is a separate file |
|---|---|---|
| `engine/flame/flame_pure_v2.py` | `engine/flame/flame_pure.py` | the original is byte-identical to its KONI source and the release advertises that with `cmp` + `MANIFEST.sha256` |
| `engine/flame/bpe_pure_v2.py` | `engine/flame/bpe_pure.py` | same |
| `scripts/find_text_reuse_v2.py` | `scripts/find_text_reuse.py` | the original is covered by the root `MANIFEST.sha256` and the release is frozen at `6556013` |
| `scripts/filter_by_wp_v2.py` | `scripts/filter_by_wp.py` | same |
| `scripts/demo_v2.py` | `engine/demo.py` | the frozen demo verifies the frozen engine; this one verifies the fixed one against it |

## Run it

```bash
python3 engine/demo.py            # frozen pipeline — chain-53 anchor, exit 0
python3 scripts/demo_v2.py        # fixed pipeline on the same two samples
python3 -m unittest discover -s tests    # 47 tests, ~60 s, stdlib only
```

`demo_v2.py` prints two tables. Table **[A]** is the v2 engine with the frozen
cleaning: it reproduces `engine/demo.py`'s five records exactly — same labels,
chains, matched words and scores — which is the point. The engine fixes do not
change what counts as a match. Table **[B]** adds the apparatus strip, and every
difference there is the cleaning's.

The full sweep, when a corpus is available:

```bash
python3 scripts/find_text_reuse_v2.py                    # -> logs/v2/
python3 scripts/filter_by_wp_v2.py                       # -> logs/clean_by_wp_v2/
```

Both default to **new** output directories. `logs/text_reuse_matches.ndjson`,
`logs/clean_by_wp/` and `results/reported_numbers.json` are never written.

---

## What was fixed

### 1. Candidate retrieval is symmetric (audit finding 4)

`flame_pure` drops a bigram when its **side-2** posting list exceeds
`max(40, 0.04 × n2)`. Side 1 is uncapped and the cap's value depends on `n2`, so
`compare(A, B)` and `compare(B, A)` prune different bigrams. Measured on
Herodotus × Thucydides at production scale (1,609 × 1,306 windows): 3,617 vs
8,402 candidates, and run to completion 304 vs 515 records — **6 vs 12 at the
`chain ≥ 6` cut-off the paper uses**.

`flame_pure_v2` gives each side its own cap from its own unit count and drops a
bigram only when it is over-frequent on **both**. That predicate maps to itself
when the arguments are swapped.

Measured result: forward and reverse produce **identical** candidate sets on all
three real pairs (Jaccard 1.0000, shared-bigram counts agreeing pair by pair),
and the result is a **strict superset** of the frozen engine's forward
direction — 0 candidates lost. Two alternatives were measured and rejected:
sizing the cap from `min(n1, n2)` is symmetric but drops 44–76% of candidates,
and capping the union document frequency drops more than it gains.

Candidate ties now break on `(i, j)` as well as on the shared-bigram count, so
the `max_candidates` truncation point is reproducible rather than dependent on
posting-list layout.

**Cost:** roughly 1.6–3× more candidates reach the scoring stage. `max_candidates`
still bounds what reaches alignment, so the runtime ceiling is unchanged — the
extra candidates change *which* pairs fill that budget, not how many.

### 2. `score` is comparable across the whole sweep (audit finding 5)

`flame_pure` builds the vocabulary, the hash base and the IDF from the two works
of the current call. In an all-pairs sweep that is one scale per work pair, and
because `base = len(vocab) + 1` even the hash *values* differ between calls. The
released data shows per-pair score maxima spanning 0.0000 to 1.0000.

That would be harmless if nothing compared scores across pairs. Things do:
`scripts/filter_by_wp.py` applies `score >= 0.001` (WP1/WP2) and `>= 0.01` (WP3)
to every pair alike, and those gates drop **12 of WP1's 19** chain-≥6 candidates
and **19 of WP2's 33** — so the reported 7 and 14 are mostly the gate's doing,
not chain length's.

`flame_pure_v2.build_corpus_index()` builds one vocabulary, base and IDF over the
whole corpus; `compare_iter(corpus_index=…)` uses it. Verified: the same unit
pair scores 0.3069 under four different call compositions where the per-call path
gives four different values, and the unit's underlying TF-IDF vector is
byte-identical between calls.

Without the argument the per-call behaviour is unchanged, so the fork stays a
drop-in for any caller that has not built an index.

**Cost:** one extra pass over the corpus before the sweep. The sweep already
re-derives every work's hashes once per pair it appears in (28 times each in the
reported run), so this is cheaper than what it replaces.

### 3. The Proclus apparatus is removed (audit finding 12)

`tlg4036.tlg001` carries the Teubner apparatus inline in its running text. After
the frozen `_clean_text()`, **2.4% of the tokens the engine sees are bare
numerals and 4.4% are Latin-script** — and `fuzz_threshold = 0.75` matches
numerals to each other (`103 ~ 104` scores 0.833).

`find_text_reuse_v2.clean_text()` drops bare numerals and Latin-script tokens,
but only from segments that are **majority Greek** — so the filter cannot eat a
Latin work. Measured on the sample: 95 → 92 windows, and the strongest lemmatic
record rises from 90 to 104 matched words (score 0.4373 → 0.5708).

**Cost, and it is the serious one:** the word stream shortens, so **every `#k`
window label and every `word_range` moves**. No positional reference in the
current results survives it. This is why the strip is opt-outable
(`--no-apparatus-strip`) and why turning it on means re-running the sweep, not
patching a report. The better place for the fix is still the corpus builder,
where the apparatus column is separable; that code is not in this release.

### 4. Smaller fixes

* **`matched_words_j` is emitted** (finding 11). `flame_pure` computes `cnt_j`
  on the line above the record and throws it away; none of the 35,753 released
  records carries a j-side count, so no `gap_j` can be computed for the archive.
* **Silent behaviour is reported** (finding 14). `meta` now carries `clamped`
  (every parameter the engine overrode — `ngram=99` still silently becomes 8,
  but it says so), `cap_hit` and `n_candidates_before_cap`, `units_truncated`
  for `CAP_WORDS`, `idf_scope` and `bpe_trained`. The harness turns these into
  warnings, and writes a `text_reuse_matches.meta.json` provenance sidecar — the
  absence of which is why `max_candidates` had to be recovered from a truncation
  signature in the first place.
* **`bpe_pure_v2.tokenize_words()` calls `load()` before reading `_RANKS`**
  (finding 15), so a first call on a fresh module returns subwords rather than
  bare characters.

## What was deliberately *not* changed

The Levenshtein predicate, the block builder, the
`core >= ngram and n >= min_chain_words` filter, the emission order, and the
140/115 windowing. Those produce the matches and the audit found them sound:
`_word_match`'s length prune never rejects a pair that would pass (20,000 random
pairs × 5 thresholds, 0 disagreements), and every block is a strictly increasing
1:1 pairing on a single diagonal (78,713 blocks, 0 violations).

`tests/test_flame.py::TestFixedFork::test_matching_stage_is_untouched_by_the_fork`
enforces this: it compares the two modules function by function at AST level and
requires **exactly one** to differ (`compare_iter`) plus exactly one new one
(`build_corpus_index`).

Also unchanged: the clamping itself (changing it would change results), and
`max_candidates`' default of 4000 — the production run used 1000, and the right
move is to state the value, not to pick a new one silently.

---

## The work-package counts

`scripts/filter_by_wp_v2.py` reads the run's provenance sidecar and decides what
the score gate can mean:

* input built with a **corpus-level IDF** → the absolute gate is meaningful and
  is applied;
* input with **per-call** scores, which is every existing artefact → the gate is
  switched off, with a printed note, and selection falls back to chain length,
  which is scale-free.

On the released data that gives, into `logs/clean_by_wp_v2/`:

| | released | v2 (no cross-pair gate) |
|---|---:|---:|
| WP1 (`anc ↔ 7th_8th`, chain ≥ 6) | 7 | **19** |
| WP2 (`anc ↔ 9th_10th`, chain ≥ 6) | 14 | **33** |
| WP3 (`anc ↔ 11th_12th`, chain ≥ 8) | 678 | **693** |

These are **not** a correction of the paper's figures — they are what the same
criteria select once the incomparable quantity is removed from them. Which set
the paper should report is an argument for §5, not a filtering decision, and the
durable answer is a re-run with corpus-level IDF, after which the absolute gate
becomes meaningful again (`--score-mode absolute`).

`logs/clean_by_wp/` and `results/reported_numbers.json` are untouched;
`logs/clean_by_wp_v2/wp_delta_report.md` states the delta.

---

## What still cannot be done from this release

* **Re-run the sweep.** The corpus is TLG-derived and not redistributable, and
  `corpus_manifest.yaml` is not shipped. Everything above is verified on the two
  bundled samples and on three real Greek works (Herodotus, Thucydides,
  Procopius) built from PerseusDL TEI as production-scale stand-ins — not the
  paper's corpus.
* **Fix the apparatus at its source** (`build_corpus.py` and friends are
  excluded from the release by policy).
* **Split the `ancient_classical` era bucket**, which puts Plato and Proclus —
  900 years apart — in one layer. That touches `corpus_manifest.yaml`,
  `ERA_RANK`/`ALL_ERAS` and every era-pair figure in §5, and must be decided
  across the pipeline at once.
