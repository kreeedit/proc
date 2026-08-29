#!/usr/bin/env python3
"""
scripts/filter_by_wp.py
=======================

WP-specifikus zajszűrés a FLAME text-reuse találatokra — a "Python-recept"
alapján.  A bemenet a globális overlap-filtrált TSV
(logs/overlap_filter_global/byz_byz_tagged.tsv).

Művelet
-------
1. Alapszűrés: self-matchek (author_i == author_j) kidobása; tag != NaN
   (ancient_commonplace) kiszűrése → a maradék a "valódi" cross-author,
   nem-közhely halmaz.
2. Munkacsomag-szűrés a megfelelő korszak-párokra + chain_len + score
   küszöbök alapján.
3. Minden WP eredményét külön fájlba menti.
4. Összehasonlító riportot generál stdout-ra és fájlba.

Bemenet
-------
  --input PATH   : a tagged TSV (default logs/overlap_filter_global/byz_byz_tagged.tsv)
  --out-dir DIR  : kimeneti mappa (default logs/clean_by_wp/)

Kimenet
-------
  --out-dir/:
    wp1_implicit_clean.tsv    — ancient_classical ↔ 7th_8th, chain≥6, score≥0.001
    wp2_canon_clean.tsv       — ancient_classical ↔ 9th_10th, chain≥6, score≥0.001
    wp3_explicit_clean.tsv    — ancient_classical ↔ 11th_12th, chain≥8, score≥0.01
    wp_report.md             — összehasonlító riport (nyers vs. tisztított)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "logs" / "overlap_filter_global" / "byz_byz_tagged.tsv"
DEFAULT_OUT_DIR = ROOT / "logs" / "clean_by_wp"

# WP-küszöbök (a recept alapján)
WP_THRESHOLDS = {
    "wp1_implicit": {
        "label": "WP1: Implicit ókori tekintélyek (7–8. sz.)",
        "en_label": "WP1: Implicit Ancient Authorities (7th–8th c.)",
        "era_a": "ancient_classical",
        "era_b": "7th_8th",
        "chain_len_min": 6,
        "score_min": 0.001,
    },
    "wp2_canon": {
        "label": "WP2: Kánonformálás és kéziratos másolás (9–10. sz.)",
        "en_label": "WP2: Canon Formation and Manuscript Copying (9th–10th c.)",
        "era_a": "ancient_classical",
        "era_b": "9th_10th",
        "chain_len_min": 6,
        "score_min": 0.001,
    },
    "wp3_explicit": {
        "label": "WP3: Explicit kommentárok (11–12. sz.)",
        "en_label": "WP3: Explicit Commentaries (11th–12th c.)",
        "era_a": "ancient_classical",
        "era_b": "11th_12th",
        "chain_len_min": 8,
        "score_min": 0.01,
    },
}


def _era_pair_filter(
    df: pd.DataFrame,
    era_a: str,
    era_b: str,
) -> pd.Series:
    """Visszaad egy boolean Series-t: igaz, ha a sor era_i/era_j éppen a
    (era_a, era_b) vagy (era_b, era_a) párt alkotja."""
    return ((df["era_i"] == era_a) & (df["era_j"] == era_b)) | (
        (df["era_i"] == era_b) & (df["era_j"] == era_a)
    )


def load_and_filter(input_path: Path) -> pd.DataFrame:
    """Betölti a tagged TSV-t és alkalmazza az alapszűrést.

    - Self-matchek (author_i == author_j) kizárva
    - ancient_commonplace (tag == 'ancient_commonplace') kizárva
    """
    df = pd.read_csv(input_path, sep="\t", low_memory=False)
    n_raw = len(df)
    df = df[(df["author_i"] != df["author_j"]) & (df["tag"].isna())].copy()
    n_base = len(df)
    print(f"  Bemenet: {n_raw} sor → alapszűrt: {n_base} sor "
          f"({n_raw - n_base} eltávolítva: self-match + ancient_commonplace)")
    return df


def filter_wp(
    df: pd.DataFrame,
    era_a: str,
    era_b: str,
    chain_len_min: int,
    score_min: float,
) -> pd.DataFrame:
    """Alkalmazza a WP-specifikus szűrőket és visszaadja a tiszta DataFrame-et."""
    era_mask = _era_pair_filter(df, era_a, era_b)
    chain_mask = df["chain_len"] >= chain_len_min
    score_mask = df["score"] >= score_min
    wp_df = df[era_mask & chain_mask & score_mask].copy()
    return wp_df


def build_report(
    df_base: pd.DataFrame,
    wp_results: dict[str, pd.DataFrame],
    lang: str = "hu",
) -> str:
    """Összehasonlító riport készítése a WP-nkénti szűrési hatékonyságról.

    lang="hu" → magyar szöveg (alapértelmezett)
    lang="en" → angol szöveg

    Visszaadja a riport szövegét (Markdown).
    """
    # Nyelvfüggő szövegek
    TXT = {
        "hu": {
            "title": "WP-specifikus szűrési jelentés",
            "base_desc": "Alapszűrt halmaz: {n} sor (cross-author, tag=NaN — self-matchek és közhelyek nélkül)",
            "era": "Korszakpár",
            "raw": "Nyers (alapszűrt) találat",
            "thresholds": "Küszöbök",
            "cleaned": "Tisztított (valódi) találat",
            "pct": "{pct:.1f}% a korszakpár alapszűrt halmazán belül",
            "fp_traces": "Ezen belül chain_len 4-5 (FP nyomok): {n} sor",
            "top_borrowings": "Top {n} valódi átvétel (leghosszabb chain_len):",
            "best_score": "Legjobb score: {cl} szavas lánc, score={sc:.4f} — {a} ↔ {b}",
            "longest_chain": "Leghosszabb lánc (chain_len={cl}):",
            "summary_table": "Összesítő tábla",
            "tbl_wp": "WP",
            "tbl_era": "Korszak",
            "tbl_raw": "Nyers",
            "tbl_thr": "Küszöbök",
            "tbl_clean": "Tisztított",
            "tbl_eff": "Hatékonyság",
            "demo_title": "Demonstráció: a nyers adatok 80%+ FP-zaja",
            "demo_base": "Alapszűrt halmaz: {n} sor",
            "demo_fp": "Ebből chain_len < 6 (véletlenszerű egyezés, szinte biztos FP): {n} sor ({pct:.1f}%)",
            "demo_tp": "Ebből chain_len ≥ 6 (valószínű TP): {n} sor ({pct:.1f}%)",
        },
        "en": {
            "title": "WP-Specific Filtering Report",
            "base_desc": "Base-filtered set: {n} rows (cross-author, tag=NaN — excluding self-matches and commonplaces)",
            "era": "Era pair",
            "raw": "Raw (base-filtered) matches",
            "thresholds": "Thresholds",
            "cleaned": "Cleaned (true positive) matches",
            "pct": "{pct:.1f}% of the era pair's base-filtered set",
            "fp_traces": "Of which chain_len 4-5 (FP traces): {n} rows",
            "top_borrowings": "Top {n} true borrowings (longest chain_len):",
            "best_score": "Best score: {cl}-word chain, score={sc:.4f} — {a} ↔ {b}",
            "longest_chain": "Longest chain (chain_len={cl}):",
            "summary_table": "Summary table",
            "tbl_wp": "WP",
            "tbl_era": "Era",
            "tbl_raw": "Raw",
            "tbl_thr": "Thresholds",
            "tbl_clean": "Cleaned",
            "tbl_eff": "Efficiency",
            "demo_title": "Demonstration: 80%+ FP noise in the raw data",
            "demo_base": "Base-filtered set: {n} rows",
            "demo_fp": "Of which chain_len < 6 (coincidental matches, near-certain FP): {n} rows ({pct:.1f}%)",
            "demo_tp": "Of which chain_len ≥ 6 (probable TP): {n} rows ({pct:.1f}%)",
        },
    }
    t = TXT.get(lang, TXT["hu"])
    lines: list[str] = []
    lines.append(f"# {t['title']}\n")
    lines.append(t["base_desc"].format(n=len(df_base)) + "\n")

    for wp_key, wp_df in wp_results.items():
        cfg = WP_THRESHOLDS[wp_key]
        label = cfg["en_label"] if lang == "en" else cfg["label"]
        era_a, era_b = cfg["era_a"], cfg["era_b"]

        # Hány sor van ebben a korszak-párban az alapszűrt halmazban?
        era_mask = _era_pair_filter(df_base, era_a, era_b)
        n_era = era_mask.sum()
        n_wp = len(wp_df)
        pct = (n_wp / n_era * 100) if n_era else 0.0

        lines.append(f"## {label}")
        lines.append(f"  - {t['era']}: {era_a} ↔ {era_b}")
        lines.append(f"  - {t['raw']}: {n_era}")
        lines.append(f"  - {t['thresholds']}: chain_len ≥ {cfg['chain_len_min']}, "
                     f"score ≥ {cfg['score_min']}")
        lines.append(f"  - {t['cleaned']}: **{n_wp}** "
                     f"({t['pct'].format(pct=pct)})")
        lines.append(f"  - {t['fp_traces'].format(n=(wp_df['chain_len'] < 6).sum())}")

        # Legjobb példák
        if len(wp_df) > 0:
            top = wp_df.nlargest(min(3, len(wp_df)), "chain_len")
            lines.append(f"\n  **{t['top_borrowings'].format(n=len(top))}:**")
            for _, row in top.iterrows():
                lines.append(
                    f"    1. {row['author_i']} ({row['work_i']}, {row['ref_i']}) → "
                    f"{row['author_j']} ({row['work_j']}, {row['ref_j']}) | "
                    f"chain_len={row['chain_len']}, score={row['score']:.4f}"
                )
            # Legjobb score
            best = wp_df.nlargest(1, "score").iloc[0]
            lines.append(f"\n  **{t['best_score'].format(cl=best['chain_len'], sc=best['score'], a=best['author_i'], b=best['author_j'])}**")

            # Snippet (ha chain_len ≥ 8)
            long = wp_df[wp_df["chain_len"] >= 8]
            if len(long) > 0:
                best_long = long.nlargest(1, "chain_len").iloc[0]
                lines.append(f"\n  **{t['longest_chain'].format(cl=best_long['chain_len'])}:**")
                lines.append(f"    snippet_i: {best_long['snippet_i'][:120]}…")
                lines.append(f"    snippet_j: {best_long['snippet_j'][:120]}…")

        lines.append("")

    # Összesítő tábla
    lines.append("---\n")
    lines.append(f"## {t['summary_table']}\n")
    lines.append(f"| {t['tbl_wp']} | {t['tbl_era']} | {t['tbl_raw']} | {t['tbl_thr']} | {t['tbl_clean']} | {t['tbl_eff']} |")
    lines.append("|----|---------|-------|----------|------------|-------------|")
    for wp_key, wp_df in wp_results.items():
        cfg = WP_THRESHOLDS[wp_key]
        era_mask = _era_pair_filter(df_base, cfg["era_a"], cfg["era_b"])
        n_era = era_mask.sum()
        n_wp = len(wp_df)
        pct = (n_wp / n_era * 100) if n_era else 0.0
        lines.append(
            f"| {wp_key} | {cfg['era_a']}↔{cfg['era_b']} | "
            f"{n_era} | chain≥{cfg['chain_len_min']}, score≥{cfg['score_min']} | "
            f"**{n_wp}** | {pct:.1f}% |"
        )

    # Nyers 80%+ FP demonstráció
    lines.append(f"\n---\n## {t['demo_title']}\n")
    short = df_base[df_base["chain_len"] < 6]
    long_chain = df_base[df_base["chain_len"] >= 6]
    lines.append(t["demo_base"].format(n=len(df_base)))
    lines.append(t["demo_fp"].format(n=len(short), pct=len(short)/len(df_base)*100))
    lines.append(t["demo_tp"].format(n=len(long_chain), pct=len(long_chain)/len(df_base)*100))

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WP-specifikus zajszűrés a FLAME text-reuse találatokra"
    )
    parser.add_argument(
        "--input", type=Path, default=TSV,
        help=f"Tagged TSV elérési útja (default: {TSV})",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT_DIR,
        help=f"Kimeneti mappa (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ByzAntiq — WP-specifikus text-reuse szűrés")
    print("=" * 60)
    print()

    # 1. Betöltés + alapszűrés
    print("[1/3] Betöltés és alapszűrés...")
    df_base = load_and_filter(args.input)
    print()

    # 2. WP-nkénti szűrés
    print("[2/3] WP-specifikus szűrés...")
    wp_results: dict[str, pd.DataFrame] = {}
    for wp_key, cfg in WP_THRESHOLDS.items():
        wp_df = filter_wp(
            df_base,
            era_a=cfg["era_a"],
            era_b=cfg["era_b"],
            chain_len_min=cfg["chain_len_min"],
            score_min=cfg["score_min"],
        )
        wp_results[wp_key] = wp_df
        print(f"  {cfg['label']}: {len(wp_df)} tiszta találat")

        # Mentés
        out_path = out_dir / f"{wp_key}_clean.tsv"
        wp_df.to_csv(out_path, sep="\t", index=False)
        print(f"    → {out_path}")
    print()

    # 2b. WP4 (opcionális: transzmisszió ancient_commonplace MEGTARTÁSÁVAL)
    print("  WP4 (opcionális): transzmisszió/szintézis (ancient_commonplace megtartva)...")
    wp4_df = df_base[
        ~_era_pair_filter(df_base, "ancient_classical", "ancient_classical")
    ]  # kizárjuk az ókori-ókori ókori egyezéseket
    # Visszahozzuk az ancient_commonplace-t is
    wp4_df_raw = pd.read_csv(args.input, sep="\t", low_memory=False)
    wp4_full = wp4_df_raw[
        (wp4_df_raw["author_i"] != wp4_df_raw["author_j"])
        & (wp4_df_raw["chain_len"] >= 6)
    ].copy()

    # Két változat: ancient_commonplace megtartva
    out_path_wp4 = out_dir / "wp4_synthesis_clean.tsv"
    wp4_full.to_csv(out_path_wp4, sep="\t", index=False)
    print(f"    → {out_path_wp4} ({len(wp4_full)} sor, ancient_commonplace megtartva)")
    print()

    # 2c. Külön fájl: a nyers ókori–bizánci találatok küszöb nélkül
    print("  Nyers ókori–bizánci kereszt-találatok (küszöb nélkül, cross-author)...")
    ancient_byz = df_base[
        ((df_base["era_i"] == "ancient_classical") |
         (df_base["era_j"] == "ancient_classical"))
    ].copy()
    out_path_ab = out_dir / "ancient_byz_raw_clean.tsv"
    ancient_byz.to_csv(out_path_ab, sep="\t", index=False)
    print(f"    → {out_path_ab} ({len(ancient_byz)} sor)")
    print()

    # 3. Riport (magyar + angol)
    print("[3/3] Riport generálása...")
    for lang, suffix in [("hu", ""), ("en", ".en")]:
        report = build_report(df_base, wp_results, lang=lang)
        report_path = out_dir / f"wp_report{suffix}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"    → {report_path}")
        if lang == "hu":
            print()
            print(report)
    print("=" * 60)


if __name__ == "__main__":
    main()
