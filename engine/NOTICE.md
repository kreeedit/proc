# engine/ — provenance, licensing and attribution

## 1. Engine code — MIT License (KONI)

`flame/flame_pure.py` and `flame/bpe_pure.py` are verbatim copies of the KONI
project's engine (`KONI/app/*.py`), released under the **MIT License** — see
`LICENSE` in this directory (Copyright (c) 2026 Tamás Kovács).

`find_text_reuse.py` is a copy of the paper's sweep harness
(`Byzantik/scripts/find_text_reuse.py`), same licence.

**Upstream method — please cite.** KONI's `flame_pure.py` is an *independent,
pure-Python (standard-library-only) reimplementation of the Leave-N-Out (LNO)
n-gram text-reuse method of FLAME*, by the same author. The original FLAME tool
remains available under the Apache License 2.0:

> FLAME — Formulaic Language Analysis in Medieval Expressions
> Tamás Kovács (kreeedit) — Apache License 2.0
> https://github.com/kreeedit/FLAME — DOI: 10.5281/zenodo.15805449

> Kovács, T. (2025). *FLAME: Formulaic Language Analysis in Medieval Expressions*
> (Version 1.0.0) [Computer software].
> https://github.com/kreeedit/FLAME — doi:10.5281/zenodo.15805449

The **public FLAME repository is not the software that produced this paper's
results** (see `README.md`, "Relationship to the public FLAME tool").

## 2. Sample texts — CC BY-SA 4.0 (PerseusDL / Open Greek and Latin)

The two files under `samples/` are excerpts of digital editions from the Perseus
Digital Library and the Open Greek and Latin project, licensed under
**Creative Commons Attribution-ShareAlike 4.0 International**:

> Greek text and editorial matter from the Perseus Digital Library and the Open
> Greek and Latin project, licensed under CC BY-SA 4.0 —
> https://creativecommons.org/licenses/by-sa/4.0/

| sample | work | edition | source |
|---|---|---|---|
| `plato_respublica_598.json` | Plato, *Respublica* 598 | Burnet, `perseus-grc2` | [PerseusDL/canonical-greekLit](https://github.com/PerseusDL/canonical-greekLit) |
| `proclus_in_rem_publicam_101r.json` | Proclus, *In Platonis Rem publicam commentarii* — the corpus unit keyed `In Rempublicam/101r`, which in this edition spans **fols. 101r–121r** (the demo's matched window lies just after the `f. 115r.` running head) | Kroll 1899–1901, `opp-grc1` | [Scaife Viewer / Open Greek and Latin](https://scaife.perseus.org/) |

The Proclus file is named after its corpus unit key, not after a single folio: it
is one citation-page unit of 10,878 words, whose printed running heads run
monotonically from `f. 101v.` to `f. 121r.` — 31 anchors, of which two are
digit transpositions in the printed running heads (`170r` between `106v` and
`107v`; `199r` between `118v` and `119v`). The `#NN` suffix in a match
reference such as `In Rempublicam/101r#65` is the ordinal of a 140-word window
inside that unit.

The underlying ancient works are in the public domain; CC BY-SA 4.0 covers these
particular digital editions. **Share-alike:** redistributed or derivative
versions of these texts must remain under CC BY-SA 4.0.

The one citation unit `demo.py` needs is included in full — 95 windows, of which
the demo matches 5. The full corpus is not redistributed here.

## 3. Restricted sources — NOT redistributed

The paper's Byzantine corpus is TLG-derived (and partly OCR from CAG /
Patrologia Graeca scans) and is **not** included in this release. TLG materials
are copyrighted; short quotations for research are permitted, wholesale
downloading and redistribution are not. See the paper's §3 and
`../README.md` ("Reproducibility").

Two consequences worth stating plainly: the shipped `../logs/text_reuse_matches.ndjson`
contains short matched snippets (quotations in the research sense); and the full
sweep **cannot** be re-run from this archive, because its input corpus cannot be
redistributed.
