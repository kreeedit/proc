#!/usr/bin/env python3
"""
scripts/filter_by_wp_v2.py
==========================

A javított munkacsomag-szűrő — a 2026-09-19-i audit (`../AUDIT.md`) 5.
megállapításának implementációja.

A probléma
----------
A `scripts/filter_by_wp.py` abszolút `score` küszöböt alkalmaz
(`score >= 0.001` a WP1/WP2-re, `>= 0.01` a WP3-ra) MINDEN művpáron át. A
`flame_pure.compare_iter` viszont az IDF-et hívásonként számolja
(`_idf(counters1 + counters2)`), a sweep pedig művpáronként hív — sőt a
szótár és a hash-bázis is páronként épül, ezért még a hash-ÉRTÉKEK is mások.
A `score` tehát művpáronként más skálán áll: a kiadott adatban a páronkénti
maximum 0,0000 és 1,0000 között szór.

Ez nem elhanyagolható részlet: a küszöb a WP1 19 jelöltjéből 12-t, a WP2 33
jelöltjéből 19-et dob el — vagyis a jelentett **7** és **14** döntő részben
ennek a küszöbnek az eredménye, nem a chain-hosszé. (WP3-nál 693-ból 15.)

A megoldás
----------
`--score-mode auto` (alapértelmezés): a futás provenance-fájlja dönt.

* Ha a bemenet **korpuszszintű IDF-fel** készült (`find_text_reuse_v2.py`,
  `corpus_idf: true` a `*.meta.json`-ban), a `score` a teljes sweepen belül
  összehasonlítható → az abszolút küszöb értelmes, és alkalmazzuk.
* Ha nem (a kiadott futás ilyen), az abszolút küszöb összehasonlíthatatlan
  mennyiségeket hasonlít → **nem alkalmazzuk**, és ezt kiírjuk. A szűrés a
  chain-hosszra marad, ami skálafüggetlen.

`--score-mode percentile` a köztes út: a küszöböt a SAJÁT művpárján belüli
percentilisre fordítjuk, így skálafüggetlen marad. Ez megtartja a küszöb
„vágjuk le a pár leggyengébb találatait" szándékát, de más halmazt ad, mint az
eredeti — ez interpretációs döntés, nem hibajavítás.

FONTOS
------
Ez a szkript egyetlen kiadott artefaktumot sem ír felül: a `--out-dir`
alapértelmezése `logs/clean_by_wp_v2/`. A `logs/clean_by_wp/` és a
`results/reported_numbers.json` érintetlen marad.

Használat:
  python3 scripts/filter_by_wp_v2.py                      # auto + delta-jelentés
  python3 scripts/filter_by_wp_v2.py --score-mode percentile --score-pct 0.25
  python3 scripts/filter_by_wp_v2.py --score-mode absolute # csak v2 sweepre
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TSV = ROOT / "logs" / "overlap_filter_global" / "byz_byz_tagged.tsv"
DEFAULT_OUT = ROOT / "logs" / "clean_by_wp_v2"
SHIPPED_OUT = ROOT / "logs" / "clean_by_wp"

# Ugyanazok a munkacsomagok és küszöbök, mint a befagyasztott szkriptben —
# csak a score-kapu kezelése más.
WP = {
    "wp1_implicit": {"label": "WP1: Implicit ókori tekintélyek (7–8. sz.)",
                     "era_a": "ancient_classical", "era_b": "7th_8th",
                     "chain_len_min": 6, "score_min": 0.001},
    "wp2_canon": {"label": "WP2: Kánonformálás és kéziratos másolás (9–10. sz.)",
                  "era_a": "ancient_classical", "era_b": "9th_10th",
                  "chain_len_min": 6, "score_min": 0.001},
    "wp3_explicit": {"label": "WP3: Explicit kommentárok (11–12. sz.)",
                     "era_a": "ancient_classical", "era_b": "11th_12th",
                     "chain_len_min": 8, "score_min": 0.01},
}


def detect_score_scope(tsv: Path) -> tuple[str, str]:
    """A bemenet mellé tett `*.meta.json` alapján: 'corpus' vagy 'call'.

    A kiadott sweep semmilyen futás-metaadatot nem hordoz (ezért kellett a
    `max_candidates` értékét a rekord/pár eloszlás telítési nyomából
    visszanyerni), tehát sidecar hiányában 'call'-t feltételezünk — ez a
    konzervatív irány: a score-kaput nem alkalmazzuk."""
    for cand in (tsv.with_suffix(".meta.json"),
                 tsv.parent / "text_reuse_matches.meta.json",
                 tsv.parent.parent / "text_reuse_matches.meta.json"):
        if cand.is_file():
            try:
                meta = json.loads(cand.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("corpus_idf"):
                return "corpus", f"{cand.name}: corpus_idf=true"
            return "call", f"{cand.name}: corpus_idf=false"
    return "call", "nincs futás-provenance a bemenet mellett (a kiadott sweep ilyen)"


def load_base(tsv: Path) -> pd.DataFrame:
    """Alapszűrés, változatlanul: self-match és `ancient_commonplace` ki."""
    df = pd.read_csv(tsv, sep="\t", low_memory=False)
    n_raw = len(df)
    df = df[(df["author_i"] != df["author_j"]) & (df["tag"].isna())].copy()
    print(f"  Bemenet: {n_raw} sor → alapszűrt: {len(df)} sor "
          f"({n_raw - len(df)} eltávolítva: self-match + ancient_commonplace)")
    return df


def era_mask(df: pd.DataFrame, a: str, b: str) -> pd.Series:
    return (((df["era_i"] == a) & (df["era_j"] == b))
            | ((df["era_i"] == b) & (df["era_j"] == a)))


def filter_wp(df: pd.DataFrame, cfg: dict, mode: str,
              score_pct: float) -> tuple[pd.DataFrame, dict]:
    """Az era + chain szűrés, majd a választott score-kezelés."""
    pre = df[era_mask(df, cfg["era_a"], cfg["era_b"])
             & (df["chain_len"] >= cfg["chain_len_min"])].copy()
    info = {"after_era_and_chain": len(pre), "mode": mode}
    if pre.empty or mode == "none":
        info["after_score"] = len(pre)
        return pre, info
    if mode == "absolute":
        out = pre[pre["score"] >= cfg["score_min"]].copy()
    elif mode == "percentile":
        # Páron belüli rang: skálafüggetlen, mert csak az azonos hívásban
        # keletkezett score-okat hasonlítja egymáshoz.
        rank = pre.groupby(["work_i", "work_j"])["score"].rank(pct=True)
        out = pre[rank >= score_pct].copy()
    else:
        raise ValueError(mode)
    info["after_score"] = len(out)
    return out, info


def shipped_counts() -> dict:
    """A kiadott WP-kimenetek sorszámai — a delta-jelentéshez."""
    out = {}
    for key, fn in (("wp1_implicit", "wp1_implicit_clean.tsv"),
                    ("wp2_canon", "wp2_canon_clean.tsv"),
                    ("wp3_explicit", "wp3_explicit_clean.tsv")):
        p = SHIPPED_OUT / fn
        out[key] = (sum(1 for _ in p.open(encoding="utf-8")) - 1
                    if p.is_file() else None)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Javított WP-szűrő — l. AUDIT.md")
    ap.add_argument("--input", default=str(DEFAULT_TSV))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT),
                    help=f"default {DEFAULT_OUT.relative_to(ROOT)} — a kiadott "
                         f"logs/clean_by_wp/ NEM íródik felül")
    ap.add_argument("--score-mode", choices=["auto", "none", "percentile",
                                             "absolute"], default="auto")
    ap.add_argument("--score-pct", type=float, default=0.25,
                    help="percentile módban a páron belüli alsó vágás (0.25 = "
                         "a pár leggyengébb negyede esik ki)")
    args = ap.parse_args()

    tsv = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    scope, why = detect_score_scope(tsv)
    mode = args.score_mode
    if mode == "auto":
        mode = "absolute" if scope == "corpus" else "none"

    print("=" * 78)
    print(f"WP-szűrés v2 — {tsv.name}")
    print(f"  score-skála: {scope}  ({why})")
    print(f"  score-mód  : {mode}"
          + (f"  (pct={args.score_pct})" if mode == "percentile" else ""))
    if scope == "call" and mode == "absolute":
        print("  [FIGYELEM] abszolút score-küszöb per-hívás normalizált "
              "score-on: művpárok között összehasonlíthatatlan mennyiségeket "
              "hasonlít. Csak akkor használd, ha tudod, miért.")
    if scope == "call" and mode == "none":
        print("  [MEGJEGYZÉS] a score-kapu KI van kapcsolva, mert a bemenet "
              "per-hívás normalizált score-t hordoz. A szűrés a chain-hosszra "
              "marad, ami skálafüggetlen.")
    print("=" * 78)

    df = load_base(tsv)
    shipped = shipped_counts()
    rows = []
    for key, cfg in WP.items():
        wp_df, info = filter_wp(df, cfg, mode, args.score_pct)
        path = out_dir / f"{key}_clean.tsv"
        wp_df.to_csv(path, sep="\t", index=False)
        rows.append((key, cfg, info, len(wp_df), shipped.get(key)))
        print(f"\n{cfg['label']}")
        print(f"  era-pár + chain>={cfg['chain_len_min']}: "
              f"{info['after_era_and_chain']}")
        print(f"  score-kapu után                 : {info['after_score']}"
              + ("" if mode == "none" else
                 f"  (elvesz {info['after_era_and_chain'] - info['after_score']})"))
        print(f"  kiadott futás                   : {shipped.get(key)}")
        print(f"  → {path.relative_to(ROOT)}")

    # --- delta-jelentés ---
    md = [f"# WP-szűrés v2 — delta a kiadott futáshoz képest\n",
          f"Bemenet: `{tsv.relative_to(ROOT)}` — score-skála **{scope}** "
          f"({why}); score-mód **{mode}**"
          + (f", pct={args.score_pct}" if mode == "percentile" else "") + ".\n",
          "A kiadott `logs/clean_by_wp/` és a `results/reported_numbers.json` "
          "**érintetlen**; ez a futás a `logs/clean_by_wp_v2/`-be ír.\n",
          "| munkacsomag | era-pár + chain | score-kapu után | kiadott | delta |",
          "|---|---:|---:|---:|---:|"]
    total_new = total_old = 0
    for key, cfg, info, n, old in rows:
        delta = "—" if old is None else f"{n - old:+d}"
        md.append(f"| {key} (chain≥{cfg['chain_len_min']}) | "
                  f"{info['after_era_and_chain']} | {n} | {old} | {delta} |")
        total_new += n
        total_old += old or 0
    md += ["", f"**WP1–3 összesen:** {total_new} (kiadott: {total_old}, "
               f"delta {total_new - total_old:+d}).", "",
           "## Miért tér el",
           "",
           "A kiadott futás a `score >= 0.001` (WP1/WP2) és `>= 0.01` (WP3) "
           "abszolút küszöböt alkalmazta minden művpáron át. A `score` viszont "
           "hívásonként normalizált: a `flame_pure.compare_iter` a szótárat, a "
           "hash-bázist és az IDF-et a hívás két művéből építi, a sweep pedig "
           "művpáronként hív. A kiadott adatban a páronkénti score-maximum "
           "0,0000 és 1,0000 között szór, tehát ugyanaz a küszöb páronként mást "
           "jelent.",
           "",
           "A tartós megoldás nem ez a szűrő, hanem a sweep újrafuttatása "
           "`scripts/find_text_reuse_v2.py`-vel: az korpuszszintű IDF-et épít, "
           "és akkor az abszolút küszöb újra értelmes lesz (`--score-mode "
           "absolute`). Addig a chain-hossz az egyetlen skálafüggetlen "
           "kritérium a kiadott adaton.",
           "",
           "Mérve: `score >= 0.001` a WP1 19 chain≥6 jelöltjéből 12-t, a WP2 "
           "33-ból 19-et dob el; `score >= 0.01` a WP3 693-ból 15-öt.",
           ]
    (out_dir / "wp_delta_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\ndelta-jelentés → {(out_dir / 'wp_delta_report.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
