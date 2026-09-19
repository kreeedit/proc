# Measurement scripts behind `../../AUDIT.md`

These are the scripts that produced every number in the audit. They are kept so
the findings can be re-derived rather than trusted. They are **not** tests —
`../test_flame.py` is the part that has to stay green; these are the
instruments.

All of them import the **unmodified** engine and the **release's own** harness
(`engine/flame/flame_pure.py`, `engine/find_text_reuse.py`); none of them
monkeypatches matching logic except `m1_bpe.py`, which flips
`bpe_pure._MERGES` between the trained and the degraded branch on purpose.

## Run without any extra input

| script | produces |
|---|---|
| `m0_d3.py` | finding 12 / D3 — apparatus-token share of the Proclus sample, before and after `_clean_text()` |
| `m2_recover.py` | finding 2 — records-per-work-pair distribution, the `max_candidates = 1000` saturation signature |
| `m4_score.py` | finding 5 — per-pair score ranges in the released NDJSON, and what the absolute WP score gates remove |
| `m5_micro.py`, `m5b.py` | findings 6, 7, 8, 9, 10, 11, 13, 14, 15 — the micro-measurements, plus the IDF-per-call demonstration and the withdrawn `_hashes` optimization |
| `m6_perf.py`, `timing.py` | finding 16 — where the runtime actually goes, and that neither proposed speed-up exists |

## Need the scale corpus

`mk_corpus.py` builds three real Greek works into the Byzantik corpus-JSON
schema from PerseusDL TEI. It reads `/home/kredit/github/KONI/data/texts`
(override with `KONI_TEXTS=...`) and writes `corpus/` next to itself —
git-ignored, ~9 MB.

**This is not the paper's corpus.** The paper's corpus is TLG-derived and
cannot be redistributed; these three works (Herodotus 185,048 w / 1,609
windows, Thucydides 150,165 w / 1,306, Procopius 224,518 w / 1,953) are stand-ins
chosen because they sit at the same scale as the corpus's largest work
(Proclus, *In Rempublicam*, 198,474 w). They support claims about **engine
behaviour at production scale**, never about the paper's content.

```bash
python3 mk_corpus.py          # writes corpus/ (needs the KONI TEI checkout)
python3 verify_cand.py        # asserts cand.py reimplements flame_pure exactly
python3 m2_m3_cand.py         # findings 3, 4 — candidate counts, direction dependence
python3 c1_impact.py          # C1 patch impact at candidate level
python3 m1_bpe.py             # finding 1 — BPE independence, demo pair + real scale
python3 m3_records.py         # finding 4 at record level — ~30 min, writes herothuc.json
python3 m3_analyze.py         # reads herothuc.json, prints the record-level table
```

`cand.py` is an exact reimplementation of the candidate-generation block
(`flame_pure.py:372-393`) used to count candidates without paying for the
Levenshtein stage. `verify_cand.py` asserts it against the engine's own
`meta["n_candidates"]`, and `m3_records.py` re-asserts it at scale by checking
that the engine's emission order equals the reimplementation's rank order.
Do not use it for anything the engine itself can answer.

`m3_records.py` is the slow one: it runs the real engine uncapped in both
directions (565 s + 1,218 s on this machine) and annotates every record with its
candidate rank, which is what makes the `max_candidates = 1000 / 4000` subsets
exact instead of approximate.
