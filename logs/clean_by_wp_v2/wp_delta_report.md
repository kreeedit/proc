# WP-szűrés v2 — delta a kiadott futáshoz képest

Bemenet: `logs/overlap_filter_global/byz_byz_tagged.tsv` — score-skála **call** (nincs futás-provenance a bemenet mellett (a kiadott sweep ilyen)); score-mód **none**.

A kiadott `logs/clean_by_wp/` és a `results/reported_numbers.json` **érintetlen**; ez a futás a `logs/clean_by_wp_v2/`-be ír.

| munkacsomag | era-pár + chain | score-kapu után | kiadott | delta |
|---|---:|---:|---:|---:|
| wp1_implicit (chain≥6) | 19 | 19 | 7 | +12 |
| wp2_canon (chain≥6) | 33 | 33 | 14 | +19 |
| wp3_explicit (chain≥8) | 693 | 693 | 678 | +15 |

**WP1–3 összesen:** 745 (kiadott: 699, delta +46).

## Miért tér el

A kiadott futás a `score >= 0.001` (WP1/WP2) és `>= 0.01` (WP3) abszolút küszöböt alkalmazta minden művpáron át. A `score` viszont hívásonként normalizált: a `flame_pure.compare_iter` a szótárat, a hash-bázist és az IDF-et a hívás két művéből építi, a sweep pedig művpáronként hív. A kiadott adatban a páronkénti score-maximum 0,0000 és 1,0000 között szór, tehát ugyanaz a küszöb páronként mást jelent.

A tartós megoldás nem ez a szűrő, hanem a sweep újrafuttatása `scripts/find_text_reuse_v2.py`-vel: az korpuszszintű IDF-et épít, és akkor az abszolút küszöb újra értelmes lesz (`--score-mode absolute`). Addig a chain-hossz az egyetlen skálafüggetlen kritérium a kiadott adaton.

Mérve: `score >= 0.001` a WP1 19 chain≥6 jelöltjéből 12-t, a WP2 33-ból 19-et dob el; `score >= 0.01` a WP3 693-ból 15-öt.