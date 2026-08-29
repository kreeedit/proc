# WP-specifikus szűrési jelentés

Alapszűrt halmaz: 20228 sor (cross-author, tag=NaN — self-matchek és közhelyek nélkül)

## WP1: Implicit ókori tekintélyek (7–8. sz.)
  - Korszakpár: ancient_classical ↔ 7th_8th
  - Nyers (alapszűrt) találat: 831
  - Küszöbök: chain_len ≥ 6, score ≥ 0.001
  - Tisztított (valódi) találat: **7** (0.8% a korszakpár alapszűrt halmazán belül)
  - Ezen belül chain_len 4-5 (FP nyomok): 0 sor

  **Top 3 valódi átvétel (leghosszabb chain_len)::**
    1. Aristotle (tlg0086.tlg010, 1/#13) → John of Damascus (2934.004, 38/#3) | chain_len=7, score=0.0444
    1. Aristotle (tlg0086.tlg010, 3/#8) → John of Damascus (2934.004, 12b/#3) | chain_len=7, score=0.0022
    1. Aristotle (tlg0086.tlg010, 3/#9) → John of Damascus (2934.004, 12b/#3) | chain_len=7, score=0.0044

  **Legjobb score: 7 szavas lánc, score=0.0444 — Aristotle ↔ John of Damascus**

## WP2: Kánonformálás és kéziratos másolás (9–10. sz.)
  - Korszakpár: ancient_classical ↔ 9th_10th
  - Nyers (alapszűrt) találat: 663
  - Küszöbök: chain_len ≥ 6, score ≥ 0.001
  - Tisztított (valódi) találat: **14** (2.1% a korszakpár alapszűrt halmazán belül)
  - Ezen belül chain_len 4-5 (FP nyomok): 0 sor

  **Top 3 valódi átvétel (leghosszabb chain_len)::**
    1. Plato (tlg0059.tlg030, 501/#1) → Photius I of Constantinople (4040.001, 464b/#2) | chain_len=14, score=0.1599
    1. Plato (tlg0059.tlg030, 469/#1) → Photius I of Constantinople (4040.001, 427a/#2) | chain_len=9, score=0.0319
    1. Plato (tlg0059.tlg030, 501/#1) → Photius I of Constantinople (4040.001, 464b/#1) | chain_len=8, score=0.0641

  **Legjobb score: 14 szavas lánc, score=0.1599 — Plato ↔ Photius I of Constantinople**

  **Leghosszabb lánc (chain_len=14)::**
    snippet_i: λαβόντες ἦν δ ἐγώ ὥσπερ πίνακα πόλιν τε καὶ ἤθη ἀνθρώπων πρῶτον μὲν καθαρὰν ποιήσειαν ἄν ὃ οὐ πάνυ ῥᾴδιον ἀλλ οὖν οἶσθ ὅ…
    snippet_j: πόλιν τε καὶ ἤθη ἀνθρώπων πρῶτον μὲν κα θαρὰν ποιήσειαν καὶ μετὰ τοῦτο ὑπογράψαιντο ἂν τὸ σχῆμα τῆς πολιτείας ἔπειτα οἶμ…

## WP3: Explicit kommentárok (11–12. sz.)
  - Korszakpár: ancient_classical ↔ 11th_12th
  - Nyers (alapszűrt) találat: 4467
  - Küszöbök: chain_len ≥ 8, score ≥ 0.01
  - Tisztított (valódi) találat: **678** (15.2% a korszakpár alapszűrt halmazán belül)
  - Ezen belül chain_len 4-5 (FP nyomok): 0 sor

  **Top 3 valódi átvétel (leghosszabb chain_len)::**
    1. Aristotle (tlg0086.tlg010, 9/#20) → Eustratius of Nicaea (4031.003, /356#1) | chain_len=51, score=0.3357
    1. Aristotle (tlg0086.tlg010, 8/#28) → Eustratius of Nicaea (4031.003, /350#2) | chain_len=51, score=0.3010
    1. Aristotle (tlg0086.tlg010, 12/#7) → Eustratius of Nicaea (4031.003, /384#1) | chain_len=45, score=0.1995

  **Legjobb score: 30 szavas lánc, score=0.5370 — Aristotle ↔ Eustratius of Nicaea**

  **Leghosszabb lánc (chain_len=51)::**
    snippet_i: τις ἡ ἀγχίνοια οὐδὲ δὴ δόξα ἡ εὐβουλία οὐδεμία ἀλλ ἐπεὶ ὁ μὲν κακῶς βουλευόμενος ἁμαρτάνει ὁ δ εὖ ὀρθῶς βουλεύεται δῆλον…
    snippet_j: Οὐδὲ δὴ δόξα ἡ εὐβουλία οὐδεμία ἀλλ ἐπεὶ ὁ μὲν κακῶς βουλευόμενος ἁμαρτάνει ὁ δὲ εὖ ὀρθῶς βουλευέται δῆλον ὅτι ὀρθότης τ…

---

## Összesítő tábla

| WP | Korszak | Nyers | Küszöbök | Tisztított | Hatékonyság |
|----|---------|-------|----------|------------|-------------|
| wp1_implicit | ancient_classical↔7th_8th | 831 | chain≥6, score≥0.001 | **7** | 0.8% |
| wp2_canon | ancient_classical↔9th_10th | 663 | chain≥6, score≥0.001 | **14** | 2.1% |
| wp3_explicit | ancient_classical↔11th_12th | 4467 | chain≥8, score≥0.01 | **678** | 15.2% |

---
## Demonstráció: a nyers adatok 80%+ FP-zaja

Alapszűrt halmaz: 20228 sor
Ebből chain_len < 6 (véletlenszerű egyezés, szinte biztos FP): 16544 sor (81.8%)
Ebből chain_len ≥ 6 (valószínű TP): 3684 sor (18.2%)