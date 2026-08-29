# WP-Specific Filtering Report

Base-filtered set: 20228 rows (cross-author, tag=NaN — excluding self-matches and commonplaces)

## WP1: Implicit ókori tekintélyek (7–8. sz.)
  - Era pair: ancient_classical ↔ 7th_8th
  - Raw (base-filtered) matches: 831
  - Thresholds: chain_len ≥ 6, score ≥ 0.001
  - Cleaned (true positive) matches: **7** (0.8% of the era pair's base-filtered set)
  - Of which chain_len 4-5 (FP traces): 0 rows

  **Top 3 true borrowings (longest chain_len)::**
    1. Aristotle (tlg0086.tlg010, 1/#13) → John of Damascus (2934.004, 38/#3) | chain_len=7, score=0.0444
    1. Aristotle (tlg0086.tlg010, 3/#8) → John of Damascus (2934.004, 12b/#3) | chain_len=7, score=0.0022
    1. Aristotle (tlg0086.tlg010, 3/#9) → John of Damascus (2934.004, 12b/#3) | chain_len=7, score=0.0044

  **Best score: 7-word chain, score=0.0444 — Aristotle ↔ John of Damascus**

## WP2: Kánonformálás és kéziratos másolás (9–10. sz.)
  - Era pair: ancient_classical ↔ 9th_10th
  - Raw (base-filtered) matches: 663
  - Thresholds: chain_len ≥ 6, score ≥ 0.001
  - Cleaned (true positive) matches: **14** (2.1% of the era pair's base-filtered set)
  - Of which chain_len 4-5 (FP traces): 0 rows

  **Top 3 true borrowings (longest chain_len)::**
    1. Plato (tlg0059.tlg030, 501/#1) → Photius I of Constantinople (4040.001, 464b/#2) | chain_len=14, score=0.1599
    1. Plato (tlg0059.tlg030, 469/#1) → Photius I of Constantinople (4040.001, 427a/#2) | chain_len=9, score=0.0319
    1. Plato (tlg0059.tlg030, 501/#1) → Photius I of Constantinople (4040.001, 464b/#1) | chain_len=8, score=0.0641

  **Best score: 14-word chain, score=0.1599 — Plato ↔ Photius I of Constantinople**

  **Longest chain (chain_len=14)::**
    snippet_i: λαβόντες ἦν δ ἐγώ ὥσπερ πίνακα πόλιν τε καὶ ἤθη ἀνθρώπων πρῶτον μὲν καθαρὰν ποιήσειαν ἄν ὃ οὐ πάνυ ῥᾴδιον ἀλλ οὖν οἶσθ ὅ…
    snippet_j: πόλιν τε καὶ ἤθη ἀνθρώπων πρῶτον μὲν κα θαρὰν ποιήσειαν καὶ μετὰ τοῦτο ὑπογράψαιντο ἂν τὸ σχῆμα τῆς πολιτείας ἔπειτα οἶμ…

## WP3: Explicit kommentárok (11–12. sz.)
  - Era pair: ancient_classical ↔ 11th_12th
  - Raw (base-filtered) matches: 4467
  - Thresholds: chain_len ≥ 8, score ≥ 0.01
  - Cleaned (true positive) matches: **678** (15.2% of the era pair's base-filtered set)
  - Of which chain_len 4-5 (FP traces): 0 rows

  **Top 3 true borrowings (longest chain_len)::**
    1. Aristotle (tlg0086.tlg010, 9/#20) → Eustratius of Nicaea (4031.003, /356#1) | chain_len=51, score=0.3357
    1. Aristotle (tlg0086.tlg010, 8/#28) → Eustratius of Nicaea (4031.003, /350#2) | chain_len=51, score=0.3010
    1. Aristotle (tlg0086.tlg010, 12/#7) → Eustratius of Nicaea (4031.003, /384#1) | chain_len=45, score=0.1995

  **Best score: 30-word chain, score=0.5370 — Aristotle ↔ Eustratius of Nicaea**

  **Longest chain (chain_len=51)::**
    snippet_i: τις ἡ ἀγχίνοια οὐδὲ δὴ δόξα ἡ εὐβουλία οὐδεμία ἀλλ ἐπεὶ ὁ μὲν κακῶς βουλευόμενος ἁμαρτάνει ὁ δ εὖ ὀρθῶς βουλεύεται δῆλον…
    snippet_j: Οὐδὲ δὴ δόξα ἡ εὐβουλία οὐδεμία ἀλλ ἐπεὶ ὁ μὲν κακῶς βουλευόμενος ἁμαρτάνει ὁ δὲ εὖ ὀρθῶς βουλευέται δῆλον ὅτι ὀρθότης τ…

---

## Summary table

| WP | Era | Raw | Thresholds | Cleaned | Efficiency |
|----|---------|-------|----------|------------|-------------|
| wp1_implicit | ancient_classical↔7th_8th | 831 | chain≥6, score≥0.001 | **7** | 0.8% |
| wp2_canon | ancient_classical↔9th_10th | 663 | chain≥6, score≥0.001 | **14** | 2.1% |
| wp3_explicit | ancient_classical↔11th_12th | 4467 | chain≥8, score≥0.01 | **678** | 15.2% |

---
## Demonstration: 80%+ FP noise in the raw data

Base-filtered set: 20228 rows
Of which chain_len < 6 (coincidental matches, near-certain FP): 16544 rows (81.8%)
Of which chain_len ≥ 6 (probable TP): 3684 rows (18.2%)