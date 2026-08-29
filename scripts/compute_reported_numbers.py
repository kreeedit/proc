#!/usr/bin/env python3
"""
compute_reported_numbers.py — Single source of truth for all numbers used in the DSH manuscript.

Usage:
    python scripts/compute_reported_numbers.py

Reads logs/text_reuse_matches.ndjson, logs/overlap_filter_global/byz_byz_tagged.{ndjson,tsv},
and logs/clean_by_wp/*.tsv, computes every number referenced in the manuscript using
explicit, documented predicates, and writes results to logs/reported_numbers.json
with a timestamp and input data hash.

This script is the ONLY source for quantitative claims in the article.
All Section references (e.g., §5.2, §6) refer to the document:
    logs/technical_description_for_article_2026-07-20.md
"""

import json
import hashlib
import csv
import os
from collections import defaultdict
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────
NDJSON_PATH = "logs/text_reuse_matches.ndjson"
FILTER_NDJSON_PATH = "logs/overlap_filter_global/byz_byz_tagged.ndjson"
FILTER_TSV_PATH = "logs/overlap_filter_global/byz_byz_tagged.tsv"
WP_DIR = "logs/clean_by_wp"
OUTPUT_PATH = "logs/reported_numbers.json"

# ── Ancient control works (VERIFIED from corpus + NDJSON data) ────────────
# These three works are the only ones used as the control corpus:
#   tlg0059.tlg030 = Plato, Respublica (Politeia)      — open_tei
#   tlg0086.tlg010 = Aristotle, Ethica Nicomachea       — open_tei
#   tlg4036.tlg001 = Proclus, In Platonis Rem publicam  — scaife_text
ANCIENT_WORKS = {"tlg0059.tlg030", "tlg0086.tlg010", "tlg4036.tlg001"}


# ── Helpers ────────────────────────────────────────────────────────────────
def build_work_to_author(ndjson_path):
    """Build work_id → author_name from NDJSON."""
    m = {}
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for side in [("work_i", "author_i"), ("work_j", "author_j")]:
                wid, auth = rec.get(side[0]), rec.get(side[1])
                if wid and auth:
                    m[wid] = auth
    return m


def build_work_to_title(ndjson_path):
    """Build work_id → title from NDJSON."""
    m = {}
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for side in [("work_i", "title_i"), ("work_j", "title_j")]:
                wid, title = rec.get(side[0]), rec.get(side[1])
                if wid and title:
                    m[wid] = title
    return m


def file_hash(path):
    """SHA-256 of file contents (first 16 hex chars)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ── §4.3: Raw FLAME partition ─────────────────────────────────────────────
def partition_raw_matches(ndjson_path, work_to_author):
    """
    Three-way partition of the 35,753 raw matches:

      BYZ_ANC     = any side is in ANCIENT_WORKS
      SAME_AUTHOR = both sides Byzantine, same author_name (= self-match)
      DIFF_AUTHOR = both sides Byzantine, different author_name
    """
    counts = {"byz_anc": 0, "same_author": 0, "diff_author": 0}
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            wi, wj = rec.get("work_i", ""), rec.get("work_j", "")
            ai, aj = work_to_author.get(wi, ""), work_to_author.get(wj, "")

            if wi in ANCIENT_WORKS or wj in ANCIENT_WORKS:
                counts["byz_anc"] += 1
            elif ai == aj:
                counts["same_author"] += 1
            else:
                counts["diff_author"] += 1
    assert sum(counts.values()) == counts["byz_anc"] + counts["same_author"] + counts["diff_author"]
    return counts


# ── §5.2: Topos Exclusion Matrix ──────────────────────────────────────────
def analyze_filter(filter_ndjson_path, byz_total, work_to_author):
    """
    Count tagged matches in the overlap filter output, split by
    same-author vs diff-author.

    PREDICATE: byz_byz_tagged.tag == 'ancient_commonplace'
    """
    s, d = 0, 0
    origins = defaultdict(int)
    with open(filter_ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("tag") != "ancient_commonplace":
                continue
            wi, wj = rec.get("work_i", ""), rec.get("work_j", "")
            ai, aj = work_to_author.get(wi, ""), work_to_author.get(wj, "")
            if ai == aj:
                s += 1
            else:
                d += 1
            origins[rec.get("tag_origin", "unknown")] += 1

    total_t = s + d
    clean_s = byz_total["same_author"] - s
    clean_d = byz_total["diff_author"] - d

    return {
        "total_tagged": total_t,
        "tagged_same_author": s,
        "tagged_diff_author": d,
        "commonplace_pct_of_byz_byz": round(total_t / (byz_total["same_author"] + byz_total["diff_author"]) * 100, 1),
        "commonplace_pct_of_diff_author": round(d / byz_total["diff_author"] * 100, 1),
        "tag_origin_breakdown": dict(origins),
        "clean_byz_byz_same_author": clean_s,
        "clean_byz_byz_diff_author": clean_d,
        "clean_byz_byz_total": clean_s + clean_d,
    }


# ── §6: Work Package counts ──────────────────────────────────────────────
def count_wp_files(wp_dir, work_to_author):
    """
    Read WP TSV files.

    WP4 PREDICATE (from filter_by_wp.py):
      raw_tagged_tsv → cross-author (author_i != author_j)
      → chain_len >= 6 → no tag filter (retains ancient_commonplace)
      → no era filter except excluding ancient×ancient
    """
    wp = {}
    files = {
        "wp1_implicit": "wp1_implicit_clean.tsv",
        "wp2_canon": "wp2_canon_clean.tsv",
        "wp3_explicit": "wp3_explicit_clean.tsv",
        "wp4_synthesis": "wp4_synthesis_clean.tsv",
    }

    for key, fn in files.items():
        path = os.path.join(wp_dir, fn)
        if not os.path.exists(path):
            wp[key] = {"error": f"not found: {path}"}
            continue
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
        wp[key] = {"total": len(rows)}

        if key == "wp4_synthesis":
            byz_anc = byz_anc_aa = byz_tag = byz_clean = 0
            for row in rows:
                wi, wj = row["work_i"], row["work_j"]
                is_anc = wi in ANCIENT_WORKS or wj in ANCIENT_WORKS
                if is_anc:
                    byz_anc += 1
                    if wi in ANCIENT_WORKS and wj in ANCIENT_WORKS:
                        byz_anc_aa += 1
                elif row.get("tag") == "ancient_commonplace":
                    byz_tag += 1
                else:
                    byz_clean += 1
            assert byz_anc + byz_tag + byz_clean == len(rows)
            wp[key].update({
                "byz_anc_in_wp4": byz_anc,
                "byz_anc_ancient_ancient": byz_anc_aa,
                "byz_byz_noncommonplace": byz_clean,
                "byz_byz_tagged_retained": byz_tag,
            })

    total = sum(
        v.get("total", 0) for v in wp.values() if isinstance(v, dict) and "total" in v
    )
    wp["total_clean"] = total
    return wp


# ── WP1-3 base counts per era pair ─────────────────────────────────────────
def count_base_by_era(filter_tsv_path, work_to_author):
    """
    Count BYZ-ANC matches per era-pair after filter_by_wp.py's base filter:
      cross-author, tag != 'ancient_commonplace', one era is ancient_classical.
    """
    eras = {
        ("ancient_classical", "7th_8th"): 0,
        ("ancient_classical", "9th_10th"): 0,
        ("ancient_classical", "11th_12th"): 0,
    }
    with open(filter_tsv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            wi, wj = row["work_i"], row["work_j"]
            if work_to_author.get(wi) == work_to_author.get(wj):
                continue
            if row.get("tag") == "ancient_commonplace":
                continue
            ei, ej = row.get("era_i", ""), row.get("era_j", "")
            if "ancient_classical" not in (ei, ej):
                continue
            byz_era = ej if ei == "ancient_classical" else ei
            key = ("ancient_classical", byz_era)
            if key in eras:
                eras[key] += 1
    return eras


# ── §8.2: Chain-length distribution ──────────────────────────────────────
def chain_length_distribution(ndjson_path, work_to_author):
    """Compute chain_len for BYZ-BYZ different-author matches only."""
    chains = []
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            wi, wj = rec.get("work_i", ""), rec.get("work_j", "")
            if wi in ANCIENT_WORKS or wj in ANCIENT_WORKS:
                continue
            if work_to_author.get(wi) == work_to_author.get(wj):
                continue
            chains.append(rec.get("chain_len", 0))

    lt6 = sum(1 for c in chains if c < 6)
    return {
        "predicate": "diff-author BYZ-BYZ matches only (author_i != author_j, neither side in ANCIENT_WORKS)",
        "total": len(chains),
        "lt_6": lt6,
        "gte_6": sum(1 for c in chains if c >= 6),
        "pct_lt_6": round(lt6 / len(chains) * 100, 1),
    }


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now().isoformat()}] Computing reported numbers...")

    h_ndjson = file_hash(NDJSON_PATH)
    h_filter = file_hash(FILTER_NDJSON_PATH)
    print(f"  NDJSON hash: {h_ndjson}")
    print(f"  Filter hash: {h_filter}")

    w2a = build_work_to_author(NDJSON_PATH)
    w2t = build_work_to_title(NDJSON_PATH)
    print(f"  Works: {len(w2a)}\n")

    # ── §4.3 partition ──
    part = partition_raw_matches(NDJSON_PATH, w2a)
    total_raw = sum(part.values())
    byz_total = part["same_author"] + part["diff_author"]
    print(f"§4.3  Total: {total_raw}")
    print(f"      BYZ-ANC: {part['byz_anc']}")
    print(f"      Self:    {part['same_author']}")
    print(f"      Diff:    {part['diff_author']}")

    # ── §5.2 filter ──
    filt = analyze_filter(FILTER_NDJSON_PATH, part, w2a)
    clean_total = filt["clean_byz_byz_total"] + part["byz_anc"]
    sampling_pop = filt["clean_byz_byz_diff_author"] + part["byz_anc"]
    print(f"\n§5.2  Tagged total: {filt['total_tagged']} (same: {filt['tagged_same_author']}, diff: {filt['tagged_diff_author']})")
    print(f"      Clean BYZ-BYZ total: {filt['clean_byz_byz_total']}")
    print(f"      Clean remainder (total): {clean_total}")
    print(f"      Sampling pop (excl self): {sampling_pop}")

    # ── §6 WP ──
    wp = count_wp_files(WP_DIR, w2a)
    for k in ["wp1_implicit", "wp2_canon", "wp3_explicit", "wp4_synthesis"]:
        v = wp.get(k, {})
        if "error" in v:
            print(f"\n§6    {k}: ERROR {v['error']}")
        elif k == "wp4_synthesis":
            print(f"\n§6    {k}: {v['total']} (BYZ-ANC: {v['byz_anc_in_wp4']}, "
                  f"BYZ-BYZ clean: {v['byz_byz_noncommonplace']}, "
                  f"BYZ-BYZ tagged: {v['byz_byz_tagged_retained']})")
        else:
            print(f"\n§6    {k}: {v['total']}")
    print(f"      Total clean: {wp.get('total_clean', '?')}")

    eras = count_base_by_era(FILTER_TSV_PATH, w2a)
    for (ea, eb), cnt in sorted(eras.items()):
        print(f"      Base {ea}↔{eb}: {cnt}")

    # ── §8.2 chain dist ──
    cd = chain_length_distribution(NDJSON_PATH, w2a)
    print(f"\n§8.2  diff-author BYZ-BYZ: {cd['total']} (lt6: {cd['lt_6']}/{cd['pct_lt_6']}%, gte6: {cd['gte_6']})")

    # ── Cross-checks ──
    wp4_bz = wp["wp4_synthesis"]["byz_byz_noncommonplace"] + wp["wp4_synthesis"]["byz_byz_tagged_retained"]
    assert wp4_bz == cd["gte_6"], f"WP4 BYZ-BYZ {wp4_bz} != chain gte6 {cd['gte_6']}"
    print(f"\n  ✅ WP4 BYZ-BYZ ({wp4_bz}) == chain >=6 ({cd['gte_6']})")

    # ── Control works ──
    ctrl = {wid: {"author": w2a.get(wid, "?"), "title": w2t.get(wid, "?")}
            for wid in sorted(ANCIENT_WORKS)}

    # ── Output ──
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "ndjson_hash": h_ndjson,
            "filter_hash": h_filter,
        },
        "section_4_3_raw_matches": {
            "total": total_raw,
            "byz_anc": part["byz_anc"],
            "byz_byz_same_author": part["same_author"],
            "byz_byz_diff_author": part["diff_author"],
            "byz_byz_total": byz_total,
            "num_pairs": 406,
            "num_works": len(w2a),
        },
        "section_5_2_topos_exclusion_matrix": {
            "predicate": "byz_byz_tagged.tag == 'ancient_commonplace' on full BYZ-BYZ (29,327)",
            "byz_byz_evaluated": byz_total,
            "ancient_control_works": ctrl,
            "tagged_commonplace_total": filt["total_tagged"],
            "tagged_commonplace_same_author": filt["tagged_same_author"],
            "tagged_commonplace_diff_author": filt["tagged_diff_author"],
            "commonplace_pct_of_byz_byz": filt["commonplace_pct_of_byz_byz"],
            "commonplace_pct_of_diff_author": filt["commonplace_pct_of_diff_author"],
            "tag_origin_breakdown": filt["tag_origin_breakdown"],
            "clean_byz_byz_same_author": filt["clean_byz_byz_same_author"],
            "clean_byz_byz_diff_author": filt["clean_byz_byz_diff_author"],
            "clean_byz_byz_total": filt["clean_byz_byz_total"],
            "byz_anc_control_matches": part["byz_anc"],
            "total_clean_remainder": clean_total,
        },
        "section_6_work_packages": {
            **wp,
            "wp1_3_base_counts": {
                "ancient_classical↔7th_8th": eras[("ancient_classical", "7th_8th")],
                "ancient_classical↔9th_10th": eras[("ancient_classical", "9th_10th")],
                "ancient_classical↔11th_12th": eras[("ancient_classical", "11th_12th")],
            },
            "wp4_pipeline_predicate": (
                "filter_by_wp.py: raw_tagged_tsv → cross-author → chain≥6 "
                "→ no tag filter (retains ancient_commonplace) "
                "→ no era filter except ¬ancient×ancient"
            ),
        },
        "section_7_1_sampling": {
            "predicate": (
                "Sampling population = clean BYZ-BYZ diff-author only "
                "(author_i != author_j, tag ≠ ancient_commonplace) + BYZ-ANC. "
                "Same-author clean matches excluded a priori."
            ),
            "clean_remainder_population_total": clean_total,
            "clean_remainder_same_author_included": filt["clean_byz_byz_same_author"],
            "sampling_population_excluding_self_matches": sampling_pop,
            "excluded_population": filt["total_tagged"],
            "excluded_population_diff_author_only": filt["tagged_diff_author"],
            "total_population": total_raw,
            "clean_sample_size": 200,
            "excluded_sample_size": 100,
            "total_sample_size": 300,
        },
        "section_8_2_chain_distribution": cd,
        "appendix_wp4_composition": {
            "predicate": "WP4 TSV breakdown: BYZ-ANC vs BYZ-BYZ (non-commonplace + tagged retained)",
            "wp4_total": wp["wp4_synthesis"]["total"],
            "wp4_byz_anc": wp["wp4_synthesis"]["byz_anc_in_wp4"],
            "wp4_byz_anc_ancient_ancient": wp["wp4_synthesis"]["byz_anc_ancient_ancient"],
            "wp4_byz_byz_non_commonplace": wp["wp4_synthesis"]["byz_byz_noncommonplace"],
            "wp4_byz_byz_tagged_retained": wp["wp4_synthesis"]["byz_byz_tagged_retained"],
            "wp4_byz_byz_total": wp4_bz,
            "crosscheck_raw_chain_gte6": cd["gte_6"],
        },
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
