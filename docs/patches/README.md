# Unapplied patches from the 2026-09-19 engine audit

**None of these is applied.** Each one either changes a number the paper
reports (class C) or touches a file that the release freezes (class B against
`scripts/find_text_reuse.py`). They are kept here so the decision is about a
concrete diff rather than a description. Findings, measurements and impact
estimates: [`../../AUDIT.md`](../../AUDIT.md).

All four apply cleanly from the repository root:

```bash
cd /home/kredit/github/proc
git apply --check docs/patches/<name>.patch     # verified: all four pass
```

| patch | target | class | consequence |
|---|---|---|---|
| `B2_B3_run_provenance_and_warnings.patch` | `engine/find_text_reuse.py` | **B** | Additive. Writes a `logs/text_reuse_matches.meta.json` sidecar (effective parameters after clamping, `bpe_trained`, `max_candidates`, engine sha256, corpus ref, work list) and warns when a parameter was silently clamped or the BPE model is absent. Changes no record and no existing field. |
| `C1_df_cap_symmetric.patch` | `engine/flame/flame_pure.py` | **C** | Makes `compare()` direction-free. **Do not apply to `flame_pure.py` itself** — that file is byte-frozen against its KONI source and the manifest check. Apply to a new `flame_pure_v3.py` fork, as `flame_pure_v2.py` was created for the docstring class. Requires a full re-run and costs 44–76% of candidates; the union-of-both-directions alternative is discussed in `AUDIT.md`. |
| `C2_strip_apparatus_tokens.patch` | `engine/find_text_reuse.py` | **C** | Removes bare numerals and Latin-script tokens from majority-Greek segments inside `_clean_text()`. Re-phases every window: `#k` labels and `word_range` values all move. Requires a full re-run. The proper home for this fix is the corpus builder, which is not in this release. |
| `C5_score_gate_not_cross_pair.patch` | `scripts/filter_by_wp.py` | **C** | Replaces the absolute `score >= score_min` gate — which compares a per-work-pair-normalized cosine across work pairs — with a within-pair percentile. Moves WP1/WP2/WP3 and the 5,260 total. The patch documents two alternatives, one of which (dropping the gate) needs no re-run, only a re-filter of the shipped NDJSON. |

## Withdrawn

* **`_hashes` with precomputed powers.** Proposed as a free speed-up; measured
  at 0.92×–1.15× (identical output verified). Memoizing `_word_match` measures
  0.95×. The cost is the 140×140 match matrix itself, 183–237 ms per unit pair.
  No patch is offered because there is nothing to gain. See `AUDIT.md` finding 16.
