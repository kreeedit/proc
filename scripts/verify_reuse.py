#!/usr/bin/env python3
"""
scripts/verify_reuse.py
=======================

Humán validációs réteg a byzantiq text-reuse eredményekhez.

Két üzemmód:

**Batch mód (--apply-rules):** Automatikus szabályalapú ítéletek.
  Pl. "minden WP1 match → verified; chain_len < 6 → false_positive"

**JSON kimenet (default):** Kiírja az aktuális státuszokat JSON-ba,
  ami kézzel szerkeszthető, majd a ``--verdicts`` flag-gel visszatölthető
  a ``convert_to_dh_standards.py``-ba.

Használat::

    source /home/tamask/environments/python3/bin/activate

    # 1) Aktuális státuszok exportja (szerkeszthető JSON)
    python scripts/verify_reuse.py --export > logs/verdicts.json

    # 2) Batch alkalmazás: chain < 6 → false_positive
    python scripts/verify_reuse.py --apply-rules \\
        --fp-chain-below 6 \\
        --out logs/verdicts_auto.json

    # 3) Batch alkalmazás: WP1 → verified (ha chain >= 6)
    python scripts/verify_reuse.py --apply-rules \\
        --verify-wp 1 \\
        --out logs/verdicts_wp1.json

    # 4) Verdict-ek visszatöltése a DH konverterbe
    python scripts/convert_to_dh_standards.py --verdicts logs/verdicts.json

    # 5) Statisztika
    python scripts/verify_reuse.py --stats
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ─── Konstansok ───────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "logs" / "dh_standards"
TSV_DIR = PROJECT_ROOT / "logs" / "clean_by_wp"

WP_GROUPS = [
    ("wp1_implicit", "7th–8th c. (Implicit Reception)"),
    ("wp2_canon", "9th–10th c. (Canon Formation)"),
    ("wp3_explicit", "11th–12th c. (Explicit Commentary)"),
    ("wp4_synthesis", "13th–15th c. (Synthesis / commonplaces)"),
]


# ─── Adatmodell ──────────────────────────────────────────────────────────────


@dataclass
class ReuseRecord:
    """Egy text-reuse sor adatai — elég a verifikációhoz és a szűréshez."""

    rel_id: str
    wp_key: str
    source_wp: str
    work_i: str
    author_i: str
    title_i: str
    ref_i: str
    snippet_i: str
    work_j: str
    author_j: str
    title_j: str
    ref_j: str
    snippet_j: str
    era_i: str
    era_j: str
    score: float
    chain_len: int
    matched_words: int
    tag: str
    gloss_tags_i: list[str] = field(default_factory=list)
    gloss_tags_j: list[str] = field(default_factory=list)
    verification_status: str = "unverified"


# ─── TSV olvasás ─────────────────────────────────────────────────────────────


def parse_gloss_tags(raw: str) -> list[str]:
    """Parsolja a TSV gloss_tags_i/j oszlopot."""
    raw = raw.strip()
    if not raw or raw == "nan":
        return []
    try:
        val = eval(raw, {"__builtins__": {}}, {})
        if isinstance(val, list):
            return [str(v) for v in val]
    except Exception:
        pass
    raw = raw.strip("[]'\" ")
    return [t.strip() for t in raw.split(",") if t.strip()]


def load_wp_tsv(wp_key: str) -> list[ReuseRecord]:
    """Betölti egy WP csoport TSV-jét (preferálja a *_tagged.tsv-t)."""
    tagged = TSV_DIR / f"{wp_key}_tagged.tsv"
    clean = TSV_DIR / f"{wp_key}_clean.tsv"
    path = tagged if tagged.exists() else clean
    if not path.exists():
        return []

    records: list[ReuseRecord] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for idx, row in enumerate(reader, start=1):
            rel_id = f"rel-{wp_key}-{idx:05d}"
            has_gloss = "gloss_tags_i" in row
            records.append(
                ReuseRecord(
                    rel_id=rel_id,
                    wp_key=wp_key,
                    source_wp=wp_key,
                    work_i=row.get("work_i", ""),
                    author_i=row.get("author_i", ""),
                    title_i=row.get("title_i", ""),
                    ref_i=row.get("ref_i", ""),
                    snippet_i=row.get("snippet_i", ""),
                    work_j=row.get("work_j", ""),
                    author_j=row.get("author_j", ""),
                    title_j=row.get("title_j", ""),
                    ref_j=row.get("ref_j", ""),
                    snippet_j=row.get("snippet_j", ""),
                    era_i=row.get("era_i", ""),
                    era_j=row.get("era_j", ""),
                    score=float(row.get("score", 0)),
                    chain_len=int(row.get("chain_len", 0)),
                    matched_words=int(row.get("matched_words", 0)),
                    tag=row.get("tag", ""),
                    gloss_tags_i=(
                        parse_gloss_tags(row["gloss_tags_i"])
                        if has_gloss and row.get("gloss_tags_i")
                        else []
                    ),
                    gloss_tags_j=(
                        parse_gloss_tags(row["gloss_tags_j"])
                        if has_gloss and row.get("gloss_tags_j")
                        else []
                    ),
                )
            )
    return records


def load_all() -> dict[str, list[ReuseRecord]]:
    """Összes WP csoport betöltése."""
    per_wp: dict[str, list[ReuseRecord]] = {}
    for wp_key, _ in WP_GROUPS:
        records = load_wp_tsv(wp_key)
        if records:
            per_wp[wp_key] = records
    return per_wp


# ─── Verifikációs logika ─────────────────────────────────────────────────────


def apply_rules(
    per_wp: dict[str, list[ReuseRecord]],
    *,
    fp_chain_below: int | None = None,
    fp_score_below: float | None = None,
    verify_wp: list[str] | None = None,
    verify_chain_above: int | None = None,
    verify_score_above: float | None = None,
    unverify_chain_above: int | None = None,
    unverify_score_above: float | None = None,
) -> dict[str, str]:
    """
    Szabályalapú verifikáció.

    Szabályok sorrendben (későbbi felülírhat korábbit):
    1. Ha chain_len < fp_chain_below → "false_positive"
    2. Ha score < fp_score_below → "false_positive"
    3. Ha wp_key a verify_wp-ban van → "verified"
       (csak ha chain_len >= verify_chain_above, ha meg van adva)
    4. Speciális: chain_len < 6 → "false_positive" (OCR-zaj / FP)

    Visszaad: {rel_id → status}
    """
    verdicts: dict[str, str] = {}

    for wp_key, records in per_wp.items():
        for rec in records:
            status = rec.verification_status  # start from default

            # FP szabályok
            if fp_chain_below is not None and rec.chain_len < fp_chain_below:
                status = "false_positive"
            if fp_score_below is not None and rec.score < fp_score_below:
                status = "false_positive"

            # Verified szabályok
            if verify_wp and any(wp_key.startswith(w) for w in verify_wp):
                chain_ok = (
                    verify_chain_above is None
                    or rec.chain_len >= verify_chain_above
                )
                score_ok = (
                    verify_score_above is None
                    or rec.score >= verify_score_above
                )
                if chain_ok and score_ok:
                    status = "verified"

            # Unverify szabályok
            if unverify_chain_above is not None and rec.chain_len >= unverify_chain_above:
                status = "unverified"
            if unverify_score_above is not None and rec.score >= unverify_score_above:
                status = "unverified"

            verdicts[rec.rel_id] = status

    return verdicts


def compute_stats(per_wp: dict[str, list[ReuseRecord]]) -> str:
    """Statisztika az aktuális verifikációs állapotról."""
    total = 0
    status_counts: Counter = Counter()
    wp_counts: Counter = Counter()
    chain_buckets: Counter = Counter()
    score_buckets: Counter = Counter()

    for wp_key, records in per_wp.items():
        for rec in records:
            total += 1
            status_counts[rec.verification_status] += 1
            wp_counts[wp_key] += 1
            # chain_len bucket
            if rec.chain_len < 6:
                chain_buckets["<6"] += 1
            elif rec.chain_len < 10:
                chain_buckets["6–9"] += 1
            elif rec.chain_len < 20:
                chain_buckets["10–19"] += 1
            else:
                chain_buckets["20+"] += 1
            # score bucket
            if rec.score < 0.001:
                score_buckets["<0.001"] += 1
            elif rec.score < 0.01:
                score_buckets["0.001–0.01"] += 1
            elif rec.score < 0.05:
                score_buckets["0.01–0.05"] += 1
            else:
                score_buckets["0.05+"] += 1

    lines = [
        "# Verification Status Report",
        "",
        f"Total records: {total}",
        "",
        "## Status distribution",
        "| Status | Count | Percentage |",
        "|---|---|---|",
    ]
    for status in ["unverified", "verified", "false_positive"]:
        c = status_counts.get(status, 0)
        pct = c / total * 100 if total else 0
        lines.append(f"| {status} | {c} | {pct:.1f}% |")

    lines.extend([
        "",
        "## Per WP",
        "| WP | Count |",
        "|---|---|",
    ])
    for wp_key, label in WP_GROUPS:
        c = wp_counts.get(wp_key, 0)
        lines.append(f"| {wp_key} ({label}) | {c} |")

    lines.extend([
        "",
        "## Chain length distribution",
        "| Bucket | Count |",
        "|---|---|",
    ])
    for bucket in ["<6", "6–9", "10–19", "20+"]:
        lines.append(f"| {bucket} | {chain_buckets.get(bucket, 0)} |")

    lines.extend([
        "",
        "## Score distribution",
        "| Bucket | Count |",
        "|---|---|",
    ])
    for bucket in ["<0.001", "0.001–0.01", "0.01–0.05", "0.05+"]:
        lines.append(f"| {bucket} | {score_buckets.get(bucket, 0)} |")

    return "\n".join(lines)


# ─── Interactive review ──────────────────────────────────────────────────────


def format_record(rec: ReuseRecord, idx: int = 0) -> str:
    """Emberi olvasású formátum egy rekordhoz."""
    fmt = (
        f"[{idx}] ── {rec.rel_id} ──\n"
        f"  Source:   {rec.author_i} — {rec.title_i} ({rec.ref_i})\n"
        f"  Target:   {rec.author_j} — {rec.title_j} ({rec.ref_j})\n"
        f"  Era:      {rec.era_i} → {rec.era_j}\n"
        f"  Score:    {rec.score:.4f} | Chain: {rec.chain_len} | Words: {rec.matched_words}\n"
        f"  Tag:      {rec.tag or '—'}\n"
        f"  Snippet i: {rec.snippet_i[:120]}...\n"
        f"  Snippet j: {rec.snippet_j[:120]}...\n"
        f"  Gloss i:   {'; '.join(rec.gloss_tags_i) if rec.gloss_tags_i else '—'}\n"
        f"  Gloss j:   {'; '.join(rec.gloss_tags_j) if rec.gloss_tags_j else '—'}\n"
        f"  Status:    {rec.verification_status}\n"
    )
    return fmt


def run_interactive(
    per_wp: dict[str, list[ReuseRecord]],
    *,
    min_chain: int = 0,
    max_chain: int = 999,
    min_score: float = 0.0,
    wp_filter: str | None = None,
    author_filter: str | None = None,
) -> dict[str, str]:
    """
    Interaktív felülvizsgálat: iterál a kiválasztott rekordokon,
    minden lépésnél kéri a besorolást.

    Visszaad: {rel_id → status}
    """
    filtered: list[ReuseRecord] = []
    for wp_key, records in per_wp.items():
        if wp_filter and wp_filter not in wp_key:
            continue
        for rec in records:
            if rec.chain_len < min_chain or rec.chain_len > max_chain:
                continue
            if rec.score < min_score:
                continue
            if author_filter and author_filter.lower() not in rec.author_i.lower() and author_filter.lower() not in rec.author_j.lower():
                continue
            filtered.append(rec)

    print(f"\n  {len(filtered)} rekord a szűrők után (interaktív mód)", file=sys.stderr)

    verdicts: dict[str, str] = {}
    for idx, rec in enumerate(filtered, start=1):
        print("\n" + format_record(rec, idx), file=sys.stderr)

        while True:
            prompt = "Besorolás [v=verified/f=false_positive/u=unverified/n=skip/q=quit]: "
            try:
                ans = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n", file=sys.stderr)
                return verdicts

            if ans in ("v", "verified"):
                verdicts[rec.rel_id] = "verified"
                break
            elif ans in ("f", "false_positive", "fp"):
                verdicts[rec.rel_id] = "false_positive"
                break
            elif ans in ("u", "unverified"):
                verdicts[rec.rel_id] = "unverified"
                break
            elif ans in ("n", "skip", ""):
                break
            elif ans in ("q", "quit"):
                print("  Kilépés.", file=sys.stderr)
                return verdicts
            else:
                print(f"  Ismeretlen parancs: {ans}", file=sys.stderr)

    return verdicts


# ─── CLI ─────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ByzAntiq — Humán verifikációs eszköz a text-reuse találatokhoz.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Export
    parser.add_argument(
        "--export",
        action="store_true",
        default=False,
        help="Aktuális státuszok exportja JSON-ba (stdout)",
    )

    # Stats
    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Statisztika a verifikációs állapotról",
    )

    # Batch rules
    parser.add_argument(
        "--apply-rules",
        action="store_true",
        default=False,
        help="Szabályalapú batch verifikáció",
    )
    parser.add_argument(
        "--fp-chain-below",
        type=int,
        default=None,
        help="false_positive ha chain_len < N",
    )
    parser.add_argument(
        "--fp-score-below",
        type=float,
        default=None,
        help="false_positive ha score < N",
    )
    parser.add_argument(
        "--verify-wp",
        type=str,
        default=None,
        help="WP-k verified státuszra (vesszővel elválasztva: 1,2,3)",
    )
    parser.add_argument(
        "--verify-chain-above",
        type=int,
        default=None,
        help="Csak verified ha chain >= N (--verify-wp-pel együtt)",
    )
    parser.add_argument(
        "--verify-score-above",
        type=float,
        default=None,
        help="Csak verified ha score >= N (--verify-wp-pel együtt)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="logs/verdicts.json",
        help="Kimeneti JSON fájl a verdict-eknek",
    )

    # Interactive
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Interaktív mód: rekordonkénti besorolás",
    )
    parser.add_argument(
        "--min-chain",
        type=int,
        default=0,
        help="Minimális chain_len a szűréshez (interactive)",
    )
    parser.add_argument(
        "--max-chain",
        type=int,
        default=999,
        help="Maximális chain_len a szűréshez (interactive)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Minimális score a szűréshez (interactive)",
    )
    parser.add_argument(
        "--wp-filter",
        type=str,
        default=None,
        help="WP szűrő (interactive, pl. wp3 vagy 3)",
    )
    parser.add_argument(
        "--author-filter",
        type=str,
        default=None,
        help="Szerző szűrő (interactive, pl. Eustratius vagy Photios)",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    per_wp = load_all()

    if not per_wp:
        print("Nincs betölthető adat.", file=sys.stderr)
        return 1

    total = sum(len(v) for v in per_wp.values())
    print(f"  ✓ {total} rekord betöltve ({len(per_wp)} WP csoport)", file=sys.stderr)

    # ── Statisztika ──
    if args.stats:
        print(compute_stats(per_wp))
        return 0

    # ── Export ──
    if args.export:
        verdicts: dict[str, str] = {}
        for wp_key, records in per_wp.items():
            for idx, rec in enumerate(records, start=1):
                rel_id = f"rel-{wp_key}-{idx:05d}" if not hasattr(rec, 'rel_id') or not rec.rel_id else rec.rel_id
                verdicts[rel_id] = rec.verification_status
        print(json.dumps(verdicts, indent=2, ensure_ascii=False))
        return 0

    # ── Batch szabályok ──
    if args.apply_rules:
        # WP lista feloldása
        verify_wp_list: list[str] | None = None
        if args.verify_wp:
            verify_wp_list = []
            for part in args.verify_wp.split(","):
                part = part.strip()
                if part.isdigit():
                    verify_wp_list.append(f"wp{part}")
                else:
                    # Lehet wp1_implicit formátum is
                    if "_" not in part and not part.startswith("wp"):
                        verify_wp_list.append(f"wp{part}")
                    else:
                        verify_wp_list.append(part)

        verdicts = apply_rules(
            per_wp,
            fp_chain_below=args.fp_chain_below,
            fp_score_below=args.fp_score_below,
            verify_wp=verify_wp_list,
            verify_chain_above=args.verify_chain_above,
            verify_score_above=args.verify_score_above,
        )

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(verdicts, f, indent=2, ensure_ascii=False)

        # Statisztika
        statuses = Counter(verdicts.values())
        print(f"\n  ✓ Verdicts mentve: {out_path}", file=sys.stderr)
        print(f"    {dict(statuses)}", file=sys.stderr)

        # Használati útmutató
        print(
            "\n  Következő lépés: python scripts/convert_to_dh_standards.py"
            f" --verdicts {args.out}",
            file=sys.stderr,
        )
        return 0

    # ── Interaktív mód ──
    if args.interactive:
        verdicts = run_interactive(
            per_wp,
            min_chain=args.min_chain,
            max_chain=args.max_chain,
            min_score=args.min_score,
            wp_filter=args.wp_filter,
            author_filter=args.author_filter,
        )
        if verdicts:
            out_path = Path(args.out if args.out else "logs/verdicts.json")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(verdicts, f, indent=2, ensure_ascii=False)
            print(f"\n  ✓ {len(verdicts)} verdict mentve: {out_path}", file=sys.stderr)
        else:
            print("  Nincs mentendő verdict.", file=sys.stderr)
        return 0

    # Default: help
    print("Használat: python scripts/verify_reuse.py --help", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
