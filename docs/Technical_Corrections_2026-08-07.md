# Technical Corrections to the Eustratius Draft — 2026-08-07

## 0. Confirmed correct (no change made)

- **Corpus:** 29 works, 406 pairs (C(29,2)), 35,753 raw matches, sweep ≈140 min.
- **Word total 2,371,796** — re-summed from Table 1 by hand; it matches.
- **§5.1 partition:** BYZ–ANC 6,426 · same-author 6,273 · different-author 23,054.
- **§5.2 Topos Exclusion:** 29,327 BYZ–BYZ → 11,487 tagged (39.2%) → 17,840 clean.
- **§5.3 thresholds:** WP1 = 7 · WP2 = 14 · WP3 = 678 · WP4 = 4,561 (1,405 ANC + 163 A/A
  + 2,279 clean + 877 restored) · pipeline total 5,260 = 7+14+678+4561 · chain<6 share 86.3%.
- **Case Study A:** 94 raw Proclus × Eustratius (*In EN* I) matches; exactly **five**
  chain-≥6 matches — the five discussed (§6.1). The quoted Greek for Matches 1–3 and the
  cited coordinates (101r#72, 121v#138, 18r#11 ↔ /87#1, /34#1) reproduce the data exactly.

---

## 1. Case B anchor was misnumbered (§6.2)

**Draft said:** "anchored on Match ID **28635** (chain length 6; score 0.0444)".
**Actual data:** the match with score 0.0444 / chain 6 / Psellos *Theol.* I 3/#4 ×
Eustratius *In APo* II /82#3 is the **28636th** record of `text_reuse_matches.ndjson`.
Record 28635 is an unrelated match (Psellos × Nicholas of Methone, score 0.0008).
**Fix:** anchor is `28636`. The same-locus recurrences are `28637` (*Theol.* I 3/#1)
and `28638` (*Theol.* I 3/#5 — this is the record that carries the *οὐ τοίνυν ὅσα κατά
τινος…* variant previously attributed to 28637).

This also required stating the ID convention explicitly: **Match IDs are the 1-based
positions of records in `text_reuse_matches.ndjson`** (added to §4), so they are
reproducibly recoverable from the archive.

## 2. The §5.4 / §6.2 tag claim was the opposite of the output

**Draft said (twice):** the shared predication-rule string "is correctly tagged
`ancient_commonplace` at the level of raw string identity", and that Case Study B is a
"restored [tagged] match" — the architecture's flagship illustration of §5.4.

**Actual data:** the three Psellos × Eustratius /82#3 matches (28636–28638) are all
**untagged** (`tag=''`) in the filter output that `compute_reported_numbers.py` uses
(`overlap_filter_global`, hash matches the manuscript). They pass as **clean** candidates;
they are not among the 877 restored commonplaces. The Topos Exclusion Matrix did *not*
catch them.

**Why this matters:** §5.4's central example claimed the *restore* mechanism caught Case B;
in fact Case B never went through the restore path. §5.4 and §6.2 have been corrected to
state that the filter does **not** tag it — and this is turned to the argument's advantage: a filter
built on the ancient core alone discards precisely the frame-bearing signal it should keep,
which is direct empirical evidence for §5.4's "exclusion cannot be absolute" thesis and for
the planned bidirectional refinement.

## 3. The "Recurrence across works" claim (28815 / 28824) did not hold as written (§6.2)

**Draft said:** IDs 28815 and 28824 "place the same Psellan framework, keyed to the same
Eunomius reference (ἐπεὶ δὲ ὁ Εὐνόμιος), in Eustratius' *Ethics* commentary (*In EN VI*
/258#2–3)".

**Actual data:**
- Both are **chain 4** — below the WP4 ≥ 6 threshold used to build the reported
  5,260-candidate set, so neither is in it.
- Their page references are **/268#2** (28815) and **/356#2** (28824), not /258#2–3, and
  the two are at *different* loci (and anyway from different *Theologica* sections, 3/#10
  and 24/#2).
- On the aligned strings they do **not** reproduce the predication-rule frame: 28815 aligns
  on a passage about being and non-being (τὸ μὴ ὂν δοξαστόν), 28824 on the ἢ εἴδει ἢ γένει
  differentia. The lifted "ἐπεὶ δὲ ὁ Εὐνόμιος" tag did not match either record.

**Fix:** the bullet is rewritten as *"sub-threshold alignments … not claimed as evidence"*:
the alignment is reported, the page refs corrected, and the question whether anything beyond
the anchor locus is at stake is explicitly left to philological adjudication on the full text.
The closing sentence now rests on "repeated-locus" rather than "cross-locus" evidence.
28815/28824 should **not** be cited as evidence of the framework migrating into the ethical
work without a fresh look at the full passages.

---

## 4. Small copy-edits made

- §2b: "Trizio's establishes" → "Trizio establishes"; "the cases whe Proclus" → "where".
- §6.2: "harde to notice" → "harder to notice".

---

## 5. Left open (TODO items in the draft, and one provenance gap that cannot be closed from data)

1. **Match 4 & Match 5 (§6.1)** still need their precise Kroll / Heylbut *line* references.
2. **Psellos *Theologica* I, %3/#4** still needs its Gautier 1989 edition/page reference.
3. **Case A "residual ancient-commonplace rate of 12%"** is not computed by
   `compute_reported_numbers.py` (and is conceptually different from the §5.2 BYZ–BYZ tag
   rate, since Proclus×Eustratius is a BYZ–ANC pair). If the number is kept, it needs a
   reproducible definition; otherwise the manuscript's "all numerical claims … by a single
   script" promise does not cover it.


