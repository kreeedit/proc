# FLAME engine audit — 2026-09-19

Measured against **`engine/flame/flame_pure.py` exactly as released**
(byte-identical to its KONI source, verified with `cmp` against
`/home/kredit/github/KONI/app/flame_pure.py` and against
`engine/MANIFEST.sha256`) and against the released
`logs/text_reuse_matches.ndjson` (35,753 records, 376 populated work pairs).

Nothing in `engine/flame/flame_pure.py`, `engine/flame/bpe_pure.py`,
`engine/data/bpe_vocab.json` or `engine/LICENSE` was modified; `sha256sum -c
engine/MANIFEST.sha256` still passes on all 12 listed files, and
`tests/test_flame.py::TestDocstringFork::test_frozen_files_are_untouched`
asserts it.

Every finding below is reproduced by `python3 -m unittest discover -s tests`
(47 tests, ~60 s, standard library only).

> **Fix status (added after the first pass).** Findings 1, 4, 5, 11, 12, 14 and
> 15 are now **implemented** in a parallel `_v2` pipeline —
> `engine/flame/flame_pure_v2.py`, `engine/flame/bpe_pure_v2.py`,
> `scripts/find_text_reuse_v2.py`, `scripts/filter_by_wp_v2.py`,
> `scripts/demo_v2.py`. See [`PIPELINE_V2.md`](PIPELINE_V2.md) for how to run it
> and what each fix cost. The frozen pipeline is untouched and still produces
> the reported numbers; the v2 pipeline writes to `logs/v2/` and
> `logs/clean_by_wp_v2/`. The paper's figures move only when the 406-pair sweep
> is re-run with it, which needs the corpus that is not in this release.
>
> **Documentation edited 2026-09-19.** `README.md` and `engine/README.md` carried
> statements this audit falsified (findings 1, 2, 12 and the "single chain of 57"
> figure); they are corrected in place and marked *(corrected 2026-09-19)*. Both
> `MANIFEST.sha256` files were regenerated — same file lists, exactly one changed
> hash each. Pre-edit values, for audit:
>
> | file | before | after |
> |---|---|---|
> | `README.md` | `112f57b696396ada…` | `6830625c9bdeeba4…` |
> | `engine/README.md` | `fa0bdecaf613bf76…` | `823c0e115c8b0496…` |
> | `MANIFEST.sha256` | `7e2dc7ff6db51901…` | regenerated (31 files, 1 hash changed) |
> | `engine/MANIFEST.sha256` | `334f358bab2e103c…` | regenerated (12 files, 1 hash changed) |
>
> No data file, no result file and no paper draft was edited. The replacement §4
> still sits beside the drafts rather than over them.

---

## What was measured on, and what that limits

The paper's corpus is **not in this release** (TLG-derived, not
redistributable), so "live measurement" means three sources:

| source | what it supports |
|---|---|
| the two bundled samples, through the **real** `build_units()` + `compare_iter()` | demo-anchor reproduction, `_clean_text` behaviour, block algebra, fuzzy-match precision |
| the released 35,753-record NDJSON | everything about the reported run's output: score scales, WP gates, record counts per pair, the `max_candidates` recovery |
| three real Greek works at the corpus's own scale, built into corpus-JSON from PerseusDL TEI in `/home/kredit/github/KONI/data/texts` — Herodotus (185,048 w / 1,609 windows), Thucydides (150,165 w / 1,306), Procopius (224,518 w / 1,953) | candidate-set scale, direction dependence, `max_candidates` truncation, BPE independence at scale |

The third source is **not the paper's corpus** and is used only to measure
engine behaviour at production scale. The largest work in the paper's corpus,
Proclus *In Rempublicam*, is 198,474 words — squarely inside that range.

---

## Findings

Class: **A** = documentation only, no semantic effect · **B** = additive, does
not touch existing fields or numbers · **C** = changes reported numbers,
requires a re-run.

| # | Claim | Measurement | Class | Paper number affected |
|---|---|---|---|---|
| **1** | **The BPE model does not affect the match set — only `score`.** Confirms V1. | Structural: `orig`/`norm` word lists identical in both branches (both use `\b\w+\b`), so the candidate dict *and its iteration order* are identical; `similarity_threshold=None`→`0.0` passes every score. Empirical: demo pair 5 vs 5 records identical field-for-field ignoring score; real scale (1,609×1,306, 400 candidates) **56 vs 56 records, 56/56 identical**, 55/56 scores differ, and the **score ranking changes**. | A | none directly; invalidates the *wording* of the README caveat and of `demo.py`'s guard comment |
| **2** | **`max_candidates` IS recoverable from the released artefact, and it was 1000.** Contradicts `engine/README.md` ("no artefact of the run records which value was in effect"). | Records-per-pair is bounded by `max_candidates`. Max over all 376 populated pairs = **exactly 1000**, none above; the pair that reaches it (Arethas, *Scholia in Porphyrii Isagoge* × *Scholia in Categorias*) shows the truncation signature — **its chain lengths start at 19**, while every unsaturated pair is dominated by chain 4–8 (next-largest pair, 965 records, has chain-4 records). Matches the `--max-candidates 1000` in the project log. | A (documentation) | **35,753** raw total, and **6,273** `byz_byz_same_author` — the saturated pair alone is 1,000 records (2.8% of the raw total, 16% of that class) and would have grown under a larger cap |
| **3** | **1000 vs 4000 is not fine-tuning: it is a different match set.** | Candidate counts on three real pairs at corpus scale: **3,617 / 6,707 / 11,574**. A cap of 1000 retains 27.6% / 14.9% / 8.6%; a cap of 4000 retains 100% / 59.6% / 34.6%. On Herodotus × Thucydides, 2,617 candidate pairs exist at 4000 that do not exist at 1000. | — (measurement) | any future re-run; `demo.py` runs at 4000, i.e. **not** the production value |
| **4** | **`compare(A,B) ≠ compare(B,A)`, and severely.** Confirms V8, larger than the reported 61 vs 117. | `df_cap = max(40, int(0.04*n2))` prunes side 2's postings only; side 1 has no cap, and the cap's *value* depends on n2. Herodotus × Thucydides: **3,617 vs 8,402 candidates, Jaccard 0.264**; Herodotus × Procopius 6,707 vs 6,805, Jaccard 0.310; Thucydides × Procopius 11,574 vs 8,642, Jaccard 0.309. The shared-bigram count — which *is* the ordering key — disagrees on 428 / 464 / 961 of the pairs common to both directions. At record level (uncapped, Herodotus × Thucydides): **304 vs 515 records**, Jaccard 0.419, and at the paper's `chain ≥ 6` cut-off **6 vs 12** — reversing the argument order doubles the reportable matches. Where a record exists in both directions its content is identical (242/242, score included), so this is purely a recall effect. See §"Direction dependence at record level". | **C** | every number: `i<j` fixed one direction per pair |
| **5** | **The `score` is per-call normalized and is used as a cross-pair threshold.** Confirms V10 and makes it concrete. | `_idf(counters1 + counters2)` runs once per `compare_iter` call = once per work pair. Same unit pair, different call composition → 0.3069 / 0.3058 / 0.2950. Per-pair score maxima in the released data run from **0.0000 to 1.0000**. Sites that compare scores across pairs: `scripts/filter_by_wp.py:112` (`score >= 0.001` for WP1/WP2, `>= 0.01` for WP3) and `:216` (`nlargest(1,"score")` → the "Legjobb score" line of `logs/clean_by_wp/wp_report.md`, which for WP3 reports a chain-30 record at 0.5370 above the chain-51 records at 0.3357 — from a *different* work pair); and `scripts/verify_reuse.py:211/226/229` (`--fp-score-below` can mark a record `false_positive` on its score alone; `--verify-score-above`, `--unverify-score-above` likewise). **`scripts/compute_reported_numbers.py` does not read `score` at all** — the single-source-of-truth script is clean; the contamination is upstream of it, in the WP candidate sets it counts. | **C** | **WP1 = 7** (the gate drops 12 of 19, 63%), **WP2 = 14** (drops 19 of 33, 58%), **WP3 = 678** (drops 15 of 693, 2%) → the pipeline total **5,260**. Reconstruction from the raw NDJSON reproduces 7 / 14 / 678 and the era-pair denominators 831 / 663 / 4,467 exactly, so the attribution is not an estimate. |
| **6** | `levenshtein_ratio`'s docstring is false. Confirms V2. | Formula is `1 − dist/(|a|+|b|)`, not difflib's `2M/T`: `abc`/`abd` → 0.8333 vs difflib 0.6667. The claimed floor of 0.0 for equal-length strings is **0.5** (measured for L = 1…11). | **A** | none |
| **7** | `fuzz=0.75` admits half the letters differing at equal length, and matches bare numerals. Confirms V3. | `το~τω`, `δε~τε` = 0.7500 (exactly on the threshold); `των~την`, `μεν~μην`, `103~104`, `605~603` = 0.8333; `18~13` = 0.7500. At equal length L the predicate passes while up to `floor(L/2)` letters differ. | **A** (wording) / **C** (if numerals are filtered — see 12) | the §4 phrase "at least 75% character overlap" and "at most one mismatched character" are both wrong |
| **8** | **The precision comes from `core >= ngram`, not from `fuzz`.** Refines V4 and falsifies the module docstring. | Module docstring: "The strict core/chain filters kill short particle matches (τε, καὶ, δὲ)". Measured: `fuzz=0.75` *accepts* those pairs; on 3 Plato × 20 Proclus windows **17,263 raw blocks are generated and 1 survives** the `core>=4 and n>=2` filter. On the demo pair's kept blocks: 213 matched word pairs, **201 string-identical**, 12 fuzzy — `μελλει~μελλοι`, `ταλλα~αλλα`, `εαυτης~αυτης`, `επισκεπτεον~σκεπτεον`, `ποιη~ποι`, `εφη~ιφη` are defensible, `τουτο~ταυτα` and `εαντε~εαν` are not. Practical false-positive rate ≈ 1%. | **A** | none |
| **9** | The length prune in `_word_match` is **sound**. Confirms V5. | 20,000 random Greek pairs × 5 thresholds (0.5/0.6/0.75/0.9/1.0), fixed seed: **0 disagreements** with the unpruned predicate. A genuine guarantee, now regression-tested. | — | none |
| **10** | The block algebra holds. Confirms V6, at larger scale. | **78,713 blocks** over the demo pair: every block is a strictly increasing 1:1 pairing on a single diagonal, **0 violations**. This is why `chain_len` is two-sided and `chain_j` is unnecessary. | — | none |
| **11** | `cnt_j` is computed and discarded; the archive has no j-side count. Confirms V7. | `compare_iter` does `snip_j, rng_j, cnt_j = _snippet(...)` and emits `matched_words` (= cnt_i) only; `matched_words_j` does not occur in `flame_pure.py`. **0 of 35,753** released records carry it. | **B** (already done in `engine/find_text_reuse.py`; not in `scripts/find_text_reuse.py`) | none — but no `gap_j` can be computed for the archive |
| **12** | **The Proclus apparatus is far heavier than the README states.** Confirms V4/D3; the README is internally inconsistent. | `engine/README.md` says "≈0.5% of its 198,474 words are apparatus tokens; 6,618 bare numbers" — but 6,618/198,474 = **3.3%**, so the two figures contradict each other. Measured on the shipped sample, after `_clean_text()`: **255 bare numerals (2.38%)** and **476 Latin-script tokens (4.44%)** of 10,715 tokens; `_clean_text` removes 87 tokens and **none** of the numerals. Top Latin tokens: `Pl`×45, `f`×38, `ex`×29, `cf`×25, `p`×24, `ss`×22. | **C** | recall and `score` on every Proclus pair; §4's claim that apparatus sigla are removed |
| **13** | Emission order is shared-bigram rank, not score, and not chain either. Confirms V9 at scale. | On the released data, **331 of the 359** multi-record work pairs are not score-monotone in file order; only 27 are chain-monotone. `auto_threshold` is computed (`meta["threshold"]`) and never applied (`used_threshold = 0.0`); applying it would drop 3 of the demo pair's 5 records. **Correction to the reported V9:** on the demo pair itself the emitted scores *are* monotone (`0.4373, 0.3069, 0.2209, 0.1624, 0.0381`) — the demo must not be used to illustrate non-monotonicity. | **A** | none |
| **14** | Silent clamping and silent truncation. Confirms V11. | `ngram=99 → 8`, `n_out=99 → 2`, `fuzz=0.1 → 0.5`, `min_chain=0 → 1`, no warning. `CAP_WORDS=400` truncates units silently — inert under this harness (windows are 140 words) but a trap for any other caller. | **B** | none |
| **15** | `bpe_pure.tokenize_words()` before `load()` returns characters. Confirms V12. | Fresh module: `['λ','ο','γ','ο','ς','</w>']`; after `load()`: `['λογος</w>']`. Cause: line 202 evaluates `_RANKS` before line 203 calls `load()`. Latent only because `flame_pure._units()` calls `is_trained()` first. | **B** (or v2 fork) | none |
| **16** | **No free speed-up exists. Refutes the proposed B-class optimization.** | Precomputing `pow(base, power, MOD)` outside `_hashes`' inner loop: **0.92×–1.15×**, i.e. noise (identical output verified). Memoizing `_word_match`: **0.95×** — `_lev_dist` is already `lru_cache`d and the length prune is cheap (676,542 hits / 500,578 misses bought nothing). The real cost is the 140×140 match matrix itself, **183–237 ms per unit pair**, which is intrinsic. | — | the 8,353.9 s figure is not reducible by these changes |

---

## Contradictions resolved (D1/D2/D3)

| | resolution |
|---|---|
| **D1** — "chain of 53" vs the measured 57 | **The README is right; the reconstruction was wrong.** `python3 engine/demo.py` reproduces `chain 53, 53 words` at `598/#3 × In Rempublicam/101r#65`, exit 0. The 57 came from windowing without `_clean_text()`. Note further: applying a *principled* apparatus-token filter (patch C2) does **not** produce 57 either — the `#64`/`#65` records stay separate at 53 and 29. The README's "merge into a single chain of 57" is reproducible only from its own hand-made strip and should be requalified. |
| **D2** — 87 words / 0.4615 vs 90 / 0.4373 | **The README is right.** Measured: `598/#1 × 101r#36` = chain 49, **90 matched words, score 0.4373**, 4 blocks. Exactly the README's figures. |
| **D3** — 2.36% numerals vs "≈0.5% apparatus tokens" | **The measurement is right and the README contradicts itself** (its own "6,618 bare numbers" is 3.3%). See finding 12. |

All three of the reported discrepancies were artefacts of the reconstructed
harness missing `_clean_text()`; the README's demo numbers are current.

## Where the reported measurements were overturned

| reported | measured live |
|---|---|
| V9: "the score is not monotonic" on the demo pair — `[0.2657, 0.3848, 0.1711, …]` | On the demo pair with `_clean_text()`, the emitted scores **are** monotone. The claim holds on the archive (331/359 pairs), not on the demo. |
| V8: "61 vs 117 candidates" on 1,074 Proclus windows | Much larger at true scale: **3,617 vs 8,402** (Jaccard 0.264). The direction dependence is worse than reported. |
| B-class: "`_hashes` precomputed powers — identical output, free speed-up" | **No speed-up (0.92×–1.15×).** Neither does memoizing `_word_match` (0.95×). Finding 16. |
| "no artefact records `max_candidates`" (README) | **It is recoverable, and it is 1000.** Finding 2. |
| V4: 208 matched word pairs, 13 non-identical | 213 / 12 with `_clean_text()` — same conclusion, slightly different counts. |
| Class A: "the `re.findall(r'\b\w+\b')` mention is only true of the non-BPE branch" | **The docstring is correct as written.** `bpe_pure.tokenize_words()` derives `orig_words` from its own `_WORD_RE = re.compile(r"\b\w+\b")` (`bpe_pure.py:20, 204`), the identical pattern `flame_pure._WORD_RE` uses. Both branches produce the same word list — which is *why* finding 1 holds. No correction needed; the v2 docstring says so explicitly instead. |

---

## Direction dependence at record level

Full uncapped run of the shipped engine in **both** directions on Herodotus ×
Thucydides (1,609 × 1,306 windows, `ngram=4 n_out=1 fuzz=0.75 min_chain=2`,
`max_candidates` effectively infinite so the cap is not a confound). 565 s and
1,218 s respectively.

| | forward `A→B` | reverse `B→A` |
|---|---|---|
| candidates | 3,617 | 8,402 |
| **records** | **304** | **515** |
| records with `chain ≥ 5` | 45 | 59 |
| **records with `chain ≥ 6`** (the paper's own BYZ–BYZ cut-off) | **6** | **12** |

* Present in one direction only: **62 forward-only, 273 reverse-only**;
  Jaccard **0.419**.
* At `chain ≥ 6`: **0 forward-only, 6 reverse-only** — reversing the argument
  order *doubles* the reportable matches on this pair, and loses none.
* **Where a record exists in both directions its content is identical** —
  242 of 242, including `chain_len`, both matched-word counts, block count,
  word ranges, **and `score`** (0 of 242 differ; the IDF is built from the
  union of both sides' units, which the swap does not change, and the cosine is
  symmetric). So the asymmetry is purely a **recall** effect: it decides which
  unit pairs are looked at, never what is found in a pair that is looked at.

Combining the two implementation choices on the same pair: the shipped
configuration (forward direction, `max_candidates = 1000`) yields **4** records
at `chain ≥ 6`, where reverse-direction-uncapped yields **12** — a 3×
difference at the paper's own threshold, from parameters no artefact recorded.

Effect of the cap alone, forward direction, at record level:

| `max_candidates` | records | `chain ≥ 5` | `chain ≥ 6` |
|---|---|---|---|
| 1000 | 103 | 21 | 4 |
| 4000 | 304 | 45 | 6 |
| uncapped | 304 | 45 | 6 |

201 of the 304 records (66%) exist only above rank 1000. (This pair is
weak-similarity — its strongest chain is 6 — so no record here would reach
WP3's `chain ≥ 8`; the *proportions* are what transfer, not the absolute
counts.)

Method note: the candidate ranks were obtained from an exact reimplementation
of `flame_pure.py:372-393`, verified against the engine's own
`meta["n_candidates"]` and against the emission order of all 304/515 records
("emitted order == candidate rank order"), so the `max_candidates` subsets
above are exact rather than re-run approximations.

---

## Deliverables and their status

### Implemented (second pass)

The fixed pipeline. Full description, costs and measured verification in
[`PIPELINE_V2.md`](PIPELINE_V2.md).

| finding | fix | verified by |
|---|---|---|
| 4 — direction dependence | `flame_pure_v2`: each side capped by its own unit count, a bigram dropped only when over-frequent on **both**. Candidate ties break on `(i, j)`. | forward == reverse exactly on all three real pairs (Jaccard 1.0000, shared counts agreeing), and a **strict superset** of the frozen engine's forward direction — 0 candidates lost. `test_FIX_candidate_retrieval_is_symmetric` |
| 5 — score not cross-pair comparable | `flame_pure_v2.build_corpus_index()` + `compare_iter(corpus_index=…)`: one vocabulary, hash base and IDF for the whole corpus. `filter_by_wp_v2` reads the run's provenance and refuses an absolute gate on per-call scores. | the same unit pair scores 0.3069 under four different call compositions where the per-call path gives four different values; the unit's TF-IDF vector is identical between calls. `test_FIX_corpus_index_makes_score_call_invariant` |
| 12 — Proclus apparatus | `find_text_reuse_v2.clean_text()` drops bare numerals and Latin-script tokens from **majority-Greek** segments only. | 0 numerals and 0 Latin tokens remain; 95 → 92 windows; the strongest lemmatic record 90 → 104 matched words, 0.4373 → 0.5708. `test_FIX_apparatus_tokens_are_stripped`, `test_FIX_windows_rephase_under_the_strip` |
| 11 — `cnt_j` discarded | emitted as `matched_words_j`. | `test_FIX_matched_words_j_is_emitted` |
| 14 — silent clamping / truncation | `meta.clamped`, `cap_hit`, `n_candidates_before_cap`, `units_truncated`, `idf_scope`, `bpe_trained`; the harness turns them into warnings and writes a `*.meta.json` provenance sidecar. | `test_FIX_silent_behaviour_is_reported`, `test_FIX_cap_hit_is_reported` |
| 15 — `bpe_pure` load order | `bpe_pure_v2` calls `load()` before reading `_RANKS`. | `test_FIX_bpe_load_order` |
| 1, 2 — wrong documentation | corrected in `engine/README.md` and `README.md` in place. | — |

**What was deliberately not changed, and is enforced as such:** the Levenshtein
predicate, the block builder, the `core >= ngram` filter, the emission order and
the windowing. `test_matching_stage_is_untouched_by_the_fork` compares the two
engine modules function by function at AST level and requires **exactly one** to
differ (`compare_iter`) plus exactly one new one (`build_corpus_index`). On the
demo pair the v2 engine reproduces the frozen engine's five records exactly —
same labels, chains, matched words and scores — so `scripts/demo_v2.py`'s
mode-[B] differences are attributable to the cleaning alone.

Also unchanged on purpose: the clamping itself (changing it would change
results) and `max_candidates`' default of 4000 — the production run used 1000,
and the right move is to state the value, not to pick a new one silently.

**Still not possible from this release:** re-running the 406-pair sweep (the
corpus is TLG-derived and absent), fixing the apparatus at its source (the
corpus builder is excluded by policy), and splitting the `ancient_classical` era
bucket (needs `corpus_manifest.yaml`).

### Applied (first pass)

* **`tests/test_flame.py`** — 47 tests, green against the unmodified engine.
  `test_DOC_*` names every test whose recorded behaviour contradicts a
  docstring, the engine README or the paper draft. The two real guarantees
  (length-prune soundness, block algebra) have their own property tests.
* **`engine/flame/flame_pure_v2.py`** — the corrected docstrings that could not
  go into the frozen file: the module docstring (what Phase 1 does and does not
  do, the direction dependence, the `\b\w+\b` branch equivalence, the
  core-vs-fuzz attribution), `levenshtein_ratio` (real formula, 0.5 floor, what
  0.75 admits), `_idf` (per-call normalization), `_units` (`CAP_WORDS`, BPE
  independence) and `compare_iter` (emission order, silent clamping, the unused
  auto-threshold). *In the second pass this file became the fixed engine as
  well — see "Implemented" above. It is still not imported by anything in the
  release: `demo.py` and both harness copies load `flame_pure`.*
* **`docs/Section4_FLAME_rewritten.md`** — §4 rewritten from the measured
  behaviour, placed beside the old text, not over it.

### The first pass's patch set — now superseded

The diffs in `docs/patches/` were written before the fixes were implemented.
They are kept because each is a minimal, reviewable statement of one change, and
because two of them record an option the implementation did **not** take. Where
a patch and the v2 pipeline disagree, the v2 pipeline is the measured answer —
in particular **C1's `min(n1,n2)` symmetrization was rejected**: it is
direction-free but drops 44–76% of candidates, where the implemented
per-side-cap version drops none. See `docs/patches/README.md`.

### Proposed, not applied — class B (additive)

| patch | what it does | impact |
|---|---|---|
| `docs/patches/B2_B3_run_provenance_and_warnings.patch` | (B2) writes a `text_reuse_matches.meta.json` sidecar carrying the effective parameters, `bpe_trained`, `max_candidates`, the engine's sha256 and the corpus ref; (B3) prints a warning when a parameter was silently clamped or the BPE model is missing. Against `engine/find_text_reuse.py`; parses clean. | **zero** on existing records and fields. Would have made finding 2 unnecessary. |
| B1 — backport `matched_words_j` to `scripts/find_text_reuse.py` | The engine already returns `matched_j`; `engine/find_text_reuse.py` already counts it, `scripts/find_text_reuse.py` does not. | zero on existing records; new runs gain a per-side count. **Touches the release-frozen script** (`6556013`) → decision, not a commit. |
| B4 — `bpe_pure` load-order fix (finding 15) | Move `load()` above the `ranks = …` line. | zero in the production path. Must go to a `bpe_pure_v2.py`, since `bpe_pure.py` is byte-frozen. |
| ~~B5 — `_hashes` precomputed powers~~ | **Withdrawn.** Measured at 0.92×–1.15×: there is no speed-up to collect (finding 16). | — |

### Proposed, not applied — class C (changes reported numbers)

| patch | what it does | measured impact |
|---|---|---|
| `docs/patches/C1_df_cap_symmetric.patch` | Caps bigram document frequency on **both** sides and sizes the cap from `min(n1,n2)`, so `compare(A,B) == compare(B,A)`. | **Works**: Jaccard forward↔reverse goes 0.264/0.310/0.309 → **1.0000** on all three real pairs, with shared counts agreeing exactly. **But it costs recall**: candidates drop 3,617→2,013 (−44%), 6,707→2,452 (−63%), 11,574→2,783 (−76%); nothing is gained. The alternative symmetrization — take the **union** of both directions — is also direction-free and goes the other way: 9,506 (+163%), 10,318 (+54%), 15,448 (+33%). Choosing between them is a recall/precision decision, not a bug fix. Either way: **re-run of the full sweep**. |
| `docs/patches/C2_strip_apparatus_tokens.patch` | Drops bare numerals and Latin-script tokens from segments that are majority-Greek, inside `_clean_text()`. | On the demo pair: Proclus windows **95 → 92** (−434 words, −3.3%), records **5 → 6**, and **every `#k` label shifts** (`#65`→`#63`, `#36`→`#35`). `598/#1` rises from **90 → 104 matched words** and **0.4373 → 0.5708** — close to the README's hand-stripped 103 / 0.5684, independently corroborating it. Invalidates every positional reference in the current results. Belongs in the corpus builder if the apparatus column is still separable there. |
| `docs/patches/C5_score_gate_not_cross_pair.patch` | Replaces the absolute `score >= score_min` in `filter_by_wp.py` with a within-work-pair percentile, so the gate is scale-free. Three options are documented in the patch: (1) drop the gate → **WP1 = 19, WP2 = 33, WP3 = 693**; (2) percentile (implemented); (3) recompute `score` with a corpus-level IDF → full re-run. | **WP1 7 → up to 19, WP2 14 → up to 33, WP3 678 → up to 693**, hence the pipeline total **5,260** moves. Option (1) needs no re-run — it is a re-filter of the shipped NDJSON. Options (2)/(3) change the definition and must be argued in §5, not patched in. |
| C3 — apparatus strip in the corpus builder | Not patchable from this release: `build_corpus.py` / `convert_raw_tlg_to_corpus.py` are deliberately excluded. | Superset of C2's effect; the right place for it. |
| C4 — split `ancient_classical` | Not patchable from this release: `corpus_manifest.yaml` is not shipped. Touches the manifest, `ERA_RANK`/`ALL_ERAS` and every era-pair figure in §5. | Every era-layer table. The Plato (4th c. BC) × Proclus (5th c. AD) pair is currently reported as same-layer, ~900 years apart. |

---

## Two things that should not be "fixed"

* **The length prune** (finding 9) and **the block algebra** (finding 10) are
  the engine's two real guarantees. Both are now property-tested. Any change to
  `_word_match` or `_fuzzy_blocks` should keep those tests green.
* **`chain_j`** is genuinely unnecessary: 78,713 blocks, 0 violations of the
  two-sided invariant.

---

## Reproducing this audit

```bash
cd /home/kredit/github/proc
python3 engine/demo.py                          # anchor: chain 53, exit 0
sha256sum -c engine/MANIFEST.sha256             # 12 files, all OK
cmp engine/flame/flame_pure.py /home/kredit/github/KONI/app/flame_pure.py
python3 -m unittest discover -s tests -v        # 33 tests, ~50 s
```

Every measurement is reproducible from `tests/measurements/` — see its
[README](tests/measurements/README.md) for which script produces which finding.
The scale measurements (findings 1, 3, 4, 16 and the C1 impact) first need
`python3 tests/measurements/mk_corpus.py`, which builds three real Greek works
from the PerseusDL TEI in `/home/kredit/github/KONI/data/texts`. Those three
works are **not** the paper's corpus and are used only as production-scale
stand-ins.
