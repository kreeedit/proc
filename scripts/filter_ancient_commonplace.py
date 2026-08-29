#!/usr/bin/env python3
"""
scripts/filter_ancient_commonplace.py
=====================================

I/3 — Kontrollkorpusz-alapú "kivonó" szűrő (overlap filter) a FLAME
text-reuse találatokra.  A Master TO-DO III/3-as prototípusa.

Vezérlő elv (Jonathan levele nyomán, lásd [[byzantik-master-todo]] III/3):
  Ha egy Byz–Byz egyezés (bizánci ↔ bizánci) szöveghelye átfed egy Byz–Ancient
  egyezéssel (bizánci ↔ ókori kontroll, pl. Eustratius ↔ Proklos), akkor a
  Byz–Byz egyezés nagy valószínűséggel nem "valódi bizánci text-reuse", hanem
  egy az ókori forrásra is visszavezethető KÖZHELY (formuláris, oktatási
  hagyományból élő fordulat).  Ezeket a szűrő `tag: ancient_commonplace`
  címkével látja el (és külön tudományos-elemzésre kínálja), a maradék pedig a
  "valódi" Byz–Byz text-reuse marad.

Koordináta-modell
-----------------
A FLAME match-record `word_range_i/j` értékei LOKÁLIS token-indexek a `ref`
által azonosított window-szegmensen belül — két különböző window
(`#1`, `#2`) indexei nem közvetlenül összehasonlíthatók.  Ezért az átfedés-
detektálás HÁROM szintje:

  1. MŰ-egyezés: a Byz–Byz és a Byz–Ancient matchnek közös bizánci művel
     kell rendelkeznie (pl. a 4031.002 = Eustratius a közös).
  2. Citation-page egyezés: a `ref` `#`-előtti része (`ref_prefix`, pl. `/87`)
     mindkét matchben azonos kell legyen — csak akkor értelmezhető a word_range
     metszet.  (Egy citation-page az összes szegmens-szövegből egybefűzött
     hosszú szöveg, amit a build_units átfedő 140-szavas ablakra vág.)
  3. word_range metszet: a bizánci oldalak word_range-jeinek metszete ≥
     OVERLAP_MIN_RATIO (default 0.50) egy bizánci oldal match word_range
     hosszának.

Bemenet
-------
  --byz-ancient PATH : összes Byz–Ancient (kontroll) match NDJSON (pl. a
                       Proklos-pilot: logs/pilot_proclus/text_reuse_matches.ndjson).
                       Ez adja a kontroll-koordinátákat.
  --byz-byz PATH     :a vizsgálandó Byz–Byz match NDJSON (a globális sweep,
                       logs/text_reuse_matches.ndjson).
  --byz-work ID      :a közös bizánci mű tlg_id-ja, amire a szűrés fókuszál
                       (default 4031.002 = Eustratius; ennek mindkét halmazban
                       szerepelnie kell).

Kimenet
-------
  --out-dir DIR :
    byz_byz_tagged.ndjson   — a Byz–Byz matchek 'tag' mezővel kiegészítve
                              (ancient_commonplace vagy NULL).
    byz_byz_tagged.tsv      — ugyanaz flat TSV + tag oszlop.
    filter_report.md        — nyers vs. tisztított összehasonlítás (a pályázat
                              "Nyers adatok vs. Tisztított adatok" demonstrációjának
                              alapja).
  --emit-untagged-only :ha be van kapcsolva, a kimeneti címke csak a VALÓDI
                          maradékot (untagged) írja ki — ez a "tisztított" set.

Használat (pilot prototípus):
  python scripts/filter_ancient_commonplace.py \\
    --byz-ancient logs/pilot_proclus/text_reuse_matches.ndjson \\
    --byz-byz logs/text_reuse_matches.ndjson \\
    --byz-work 4031.002 \\
    --out-dir logs/overlap_filter
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# word_range parse: "98–128" (en-dash, U+2013), "7–10" (ascii kötőjel)
_WR_RE = re.compile(r"\s*(\d+)\s*–-\s*(\d+)\s*|\s*(\d+)\s*-\s*(\d+)\s*")
_WR_RE = re.compile(r"\s*(\d+)\s*[–\-]\s*(\d+)\s*")


def parse_wr(s: str) -> tuple[int, int] | None:
    if not s:
        return None
    m = _WR_RE.match(s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def ref_prefix(r: str) -> str:
    """A `ref` `#`-előtti része = citation-page (windowon belüli index nélkül).
    Pl. 'In Rempublicam/101r#72' -> 'In Rempublicam/101r', '/87#1' -> '/87'."""
    if not r:
        return r
    return r.split("#", 1)[0]


def overlap_ratio(a: tuple[int, int], b: tuple[int, int]) -> float:
    """A SEGEDMÉNY (`a`) word_range-je hányszorosa esik egybe a kontroll (`b`)
    word_range-jának — a javaslat szerint 'a bizánci lánc szavainak hányada'."""
    if a is None or b is None:
        return 0.0
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    if hi < lo:
        return 0.0
    inter = hi - lo + 1
    a_len = a[1] - a[0] + 1
    return inter / a_len if a_len > 0 else 0.0


def load_ndjson(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def collect_ancient_coords(matches: list[dict], byz_work: str
                           ) -> dict[str, list[tuple[int, int]]]:
    """A Byz–Ancient halmazban a közös bizánci mű oldalán lévő koordináták
    (citation-page → [word_range(t)], kontroll-chorgonyokként)."""
    coords: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for m in matches:
        if m["work_i"] == byz_work:
            wr = parse_wr(m["word_range_i"])
            if wr:
                coords[ref_prefix(m["ref_i"])].append(wr)
        elif m["work_j"] == byz_work:
            wr = parse_wr(m["word_range_j"])
            if wr:
                coords[ref_prefix(m["ref_j"])].append(wr)
    return coords


def collect_ancient_coords_by_work(matches: list[dict]
        ) -> dict[str, dict[str, list[tuple[int, int]]]]:
    """Globális (multi-work) koordináta-gyűjtés: minden bizánci műre külön,
    a Byz-Ancient (kontroll) halmazból az 'era' alapján a bizánci oldal
    azonosítva.  Visszatér: {bizánci_tlg_id: {citation_page:
    [word_range(t)]}}.  A kontroll-halmazban az ókori (ancient_classical,
    ERA_RANK 0) a bizánci mellett szerepel — a bizánci oldal koordinátáit
    gyűjtjük, az 'era_i/j' alapján."""
    coords: dict[str, dict[str, list[tuple[int, int]]]] = defaultdict(
        lambda: defaultdict(list))
    for m in matches:
        ei = m.get("era_i", ""); ej = m.get("era_j", "")
        # az ancient_classical oldal a kontroll (ókori); a bizánci a másik
        if ei == "ancient_classical":
            biz_tlg, biz_ref, biz_wr = (m["work_j"], m["ref_j"],
                                        parse_wr(m["word_range_j"]))
        elif ej == "ancient_classical":
            biz_tlg, biz_ref, biz_wr = (m["work_i"], m["ref_i"],
                                        parse_wr(m["word_range_i"]))
        else:
            continue  # Byz-Byz match — itt nem érdekes (csak kontroll-párok kellenek)
        if biz_wr:
            coords[biz_tlg][ref_prefix(biz_ref)].append(biz_wr)
    return coords


def tag_byz_byz_matches(byz_byz: list[dict], byz_work: str,
                         ancient_coords: dict[str, list[tuple[int, int]]],
                         min_ratio: float) -> list[dict]:
    """Minden Byz–Byz match-hez 'tag' mező: 'ancient_commonplace' ha a közös
    bizánci oldal word_range-je elég nagy mértékben átfed egy kontroll-egybeces
    word_range-dzsel ugyanazon citation-page-en; különben NULL ('')."""
    out = []
    for m in byz_byz:
        tag = ""
        # csak a közös bizánci művell érintő Byz–Byz matcheket vizsgáljuk
        if m["work_i"] == byz_work:
            byz_ref = m["ref_i"]
            byz_wr = parse_wr(m["word_range_i"])
        elif m["work_j"] == byz_work:
            byz_ref = m["ref_j"]
            byz_wr = parse_wr(m["word_range_j"])
        else:
            out.append({**m, "tag": ""})
            continue
        pref = ref_prefix(byz_ref)
        # ha van kontroll-koordináta ezen a citation-page-en:
        for cb_wr in ancient_coords.get(pref, []):
            if overlap_ratio(byz_wr, cb_wr) >= min_ratio:
                tag = "ancient_commonplace"
                break
        out.append({**m, "tag": tag})
    return out


def tag_byz_byz_matches_by_work(byz_byz: list[dict],
        coords_by_work: dict[str, dict[str, list[tuple[int, int]]]],
        min_ratio: float) -> list[dict]:
    """Globális multi-work címkézés: minden Byz-Byz matchnél a két műről
    külön-külön megnézzük, hogy bármelyikük oldalán van-e átfedő kontroll-
    koordináta.  Ha mindkét oldal bizánci és egyikük (vagy mindkettő)
    ancient_commonplace overlapot ad, a match címkét kap.  A `tag` elesetén
    a `tag`-boy mellett 'tag_origin' (work_i/work_j) is jelzi, melyik oldal
    az ókori-kontrollba átnyúló."""
    out = []
    for m in byz_byz:
        wi, wj = m["work_i"], m["work_j"]
        # CSAK valódi bizánci ↔ bizánci matcheket vizsgálunk; a kontroll-
        # párokat (amelyben valamelyik fél ancient_classical, ERA_RANK 0) és
        # az ókori↔ókori párokat KIB hagyhagyjuk — ezek nem Byz-Byz állomány.
        ei = m.get("era_i", ""); ej = m.get("era_j", "")
        if ei == "ancient_classical" or ej == "ancient_classical":
            out.append({**m, "tag": "", "tag_origin": ""})
            continue
        tag = ""
        origin = ""
        # i oldal vizsgálata
        cwi = coords_by_work.get(wi, {})
        if cwi:
            wr_i = parse_wr(m["word_range_i"])
            pref_i = ref_prefix(m["ref_i"])
            for cb_wr in cwi.get(pref_i, []):
                if wr_i and overlap_ratio(wr_i, cb_wr) >= min_ratio:
                    tag, origin = "ancient_commonplace", "work_i"
                    break
        # j oldal vizsgálata (ha i nem talált)
        if not tag:
            cwj = coords_by_work.get(wj, {})
            if cwj:
                wr_j = parse_wr(m["word_range_j"])
                pref_j = ref_prefix(m["ref_j"])
                for cb_wr in cwj.get(pref_j, []):
                    if wr_j and overlap_ratio(wr_j, cb_wr) >= min_ratio:
                        tag, origin = "ancient_commonplace", "work_j"
                        break
        out.append({**m, "tag": tag, "tag_origin": origin})
    return out


def write_tagged_ndjson(matches: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for m in matches:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def write_tagged_tsv(matches: list[dict], path: Path) -> None:
    cols = ["work_i", "ref_i", "era_i", "work_j", "ref_j", "era_j",
            "score", "chain_len", "matched_words",
            "snippet_i", "snippet_j", "author_i", "author_j",
            "title_i", "title_j", "tag"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for m in matches:
            f.write("\t".join(str(m.get(c, "")).replace("\t", " ").replace("\n", " ")
                              for c in cols) + "\n")


def write_report(tagged: list[dict], byz_work: str, min_ratio: float,
                 ancient_coords: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_total = len(tagged)
    # csak a közös bizánci művet érintő matchek (a többi érintetlen)
    involved = [m for m in tagged
                if m["work_i"] == byz_work or m["work_j"] == byz_work]
    n_involved = len(involved)
    n_tagged = sum(1 for m in involved if m["tag"] == "ancient_commonplace")
    n_clean = n_involved - n_tagged
    breakdown = defaultdict(lambda: {"total": 0, "tagged": 0})
    for m in involved:
        partner = m["work_j"] if m["work_i"] == byz_work else m["work_i"]
        breakdown[partner]["total"] += 1
        if m["tag"] == "ancient_commonplace":
            breakdown[partner]["tagged"] += 1

    L = []
    L.append("# I/3 Overlap-filter jelentés — ancient_commonplace szűrés\n")
    L.append(f"**Fókusz-bizánci mű:** `{byz_work}` (a Byz–Ancient kontroll és a "
             f"Byz–Byz halmaz közös műve).")
    L.append(f"**Kontroll (Byz–Ancient):** {sum(len(v) for v in ancient_coords.values())} "
             f"koordináta, {len(ancient_coords)} citation-page-en.")
    L.append(f"**Átfedési küszöb:** word_range-metszet ≥ {min_ratio:.0%} a bizánci "
             f"match szavainak.\n")
    L.append(f"## {byz_work}-t érintő Byz–Byz matchek: {n_involved}")
    L.append(f"- **Címkézve ancient_commonplace-ként:** {n_tagged} "
             f"({n_tagged/n_involved:.1%}) — VALÓSZÍNŰLEG ókori kontrollközhely, "
             f"NEM egyedi bizánci átvétel.")
    L.append(f"- **Tiszta maradék (valódi Byz–Byz text-reuse):** {n_clean} "
             f"({n_clean/n_involved:.1%}) — ez a vegyes filológiai elemzésre érdemes.\n")
    L.append("## Bontás bizánci partnerenként\n")
    L.append("| bizánci partner | összes | címkézett (közhely) | tiszta | címkézett % |")
    L.append("|---|---:|---:|---:|---:|")
    for partner, d in sorted(breakdown.items(), key=lambda kv: -kv[1]["tagged"]):
        clean = d["total"] - d["tagged"]
        pct = f"{d['tagged']/d['total']:.0%}" if d["total"] else "0%"
        L.append(f"| {partner} | {d['total']} | {d['tagged']} | {clean} | {pct} |")
    L.append("")
    L.append("## Módszertani megjegyzés")
    L.append("A címkézett sorok azok, amelyek Eustratius (4031.002) egyik "
             "citation-page-én egy Proclus-szal közös szöveghelyre (word_range-"
             "metszet ≥ küszöbre) esnek.  Mivel a Proclus-egybeesés empirikusan "
             "mind neoplatonikus/aristotelészi **közhely** (lásd a pilot 5 cross-"
             "author chain=6 találatát), az ezekkel átfedő Byz–Byz találatok is "
             "ebbe a hagyományba sorolhatók — tehát a szűrés nem elnagyolt "
             "'törlés', hanem kontroll-adatvezérelt **kategorizálás**.")
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="I/3 overlap-filter (ancient_commonplace)")
    ap.add_argument("--byz-ancient", required=True, action="append",
                    help="Byz-Ancient (kontroll) match NDJSON — a kontroll-koordináták "
                         "forrása (többször is megadható több kontroll-mű egyesítéséhez)")
    ap.add_argument("--byz-byz", required=True,
                    help="Byz-Byz (vizsgálandó) match NDJSON")
    ap.add_argument("--byz-work", default="4031.002",
                    help="közös bizánci mű tlg_id-ja, amire a szűrés fókuszál (default "
                         "4031.002); `all` = globális mód, minden bizánci műre (a Byz–"
                         "Ancient kontroll-halmazból, era alapján)")
    ap.add_argument("--min-ratio", type=float, default=0.50,
                    help="word_range-metszet küsz (0-1, default 0.50)")
    ap.add_argument("--out-dir", default="logs/overlap_filter",
                    help="kimeneti könyvtár")
    args = ap.parse_args()

    # --byz-ancient action="append": több kontroll-NDJSON egyesítése (pl. a
    # Proklos-pilot + EN-pilot együtt 2 kontroll-mű koordinátáit adja).
    byz_ancient = []
    for p in args.byz_ancient:
        byz_ancient.extend(load_ndjson(Path(p)))
    byz_byz = load_ndjson(Path(args.byz_byz))
    print(f"Byz-Ancient (kontroll) matchek: {len(byz_ancient)} "
          f"({len(args.byz_ancient)} kontroll-NDJSON)")
    print(f"Byz-Byz (vizsgálandó) matchek: {len(byz_byz)}")
    print(f"Fókusz-bizánci mű: {args.byz_work}")

    out = Path(args.out_dir)
    if args.byz_work == "all":
        # globális mód: minden bizánci mű a kontroll-halmazban
        coords_by_work = collect_ancient_coords_by_work(byz_ancient)
        n_biz = len(coords_by_work)
        n_coords = sum(len(pg) for pg in coords_by_work.values())
        n_pages = sum(len(pages) for pages in coords_by_work.values())
        print(f"  [globális] {n_biz} bizánci mű, {n_coords} koordináta "
              f"{n_pages} citation_page-en")
        tagged = tag_byz_byz_matches_by_work(byz_byz, coords_by_work, args.min_ratio)
        # 'all' capa hebben: a globális járatáshoz a write_report hasonló, de
        # nem egyetlen byz_work-ra bont; itt egyszerű macro-jelentést írunk.
        n_tag_tot = sum(1 for m in tagged if m["tag"] == "ancient_commonplace")
        # clean (tiszta) = érdekes újrás
        write_tagged_ndjson(tagged, out / "byz_byz_tagged.ndjson")
        write_tagged_tsv(tagged, out / "byz_byz_tagged.tsv")
        # globális jelentés
        L = []
        L.append("# I/3 Globális overlap-filter jelentés — `--byz-work all`\n")
        L.append(f"**Byz-Ancient kontroll-matchek:** {len(byz_ancient)} "
                 f"({len(args.byz_ancient)} NDJSON).\n")
        L.append(f"**Byz-Byz vizsgált matchek:** {len(byz_byz)}.\n")
        L.append(f"**Átfedési küszöb:** word_range-metszet ≥ {args.min_ratio:.0%} "
                 f"egyik bizánci oldal match szavainak.\n")
        L.append(f"## Globális eredmény\n")
        L.append(f"- Címkézett ancient_commonplace (ókori kontrollközhely): "
                 f"**{n_tag_tot}** ({n_tag_tot/len(byz_byz):.1%}).")
        L.append(f"- Tiszta maradék (potenciálisan valódi bizánci text-reuse): "
                 f"**{len(byz_byz)-n_tag_tot}** "
                 f"({(len(byz_byz)-n_tag_tot)/len(byz_byz):.1%}).\n")
        L.append(f"## Bontás bizánci művek szerint (címkézési arány)\n")
        L.append("| bizánci mű | összes Byz-Byz | címkézett (közhely) | címkézett % |")
        L.append("|---|---:|---:|---:|")
        per_biz = defaultdict(lambda: {"total": 0, "tagged": 0})
        for m in tagged:
            per_biz[m["work_i"]]["total"] += 1
            per_biz[m["work_j"]]["total"] += 1
            if m["tag"] == "ancient_commonplace":
                per_biz[m["work_i"]]["tagged"] += 1
                per_biz[m["work_j"]]["tagged"] += 1
        # (a per-biz-1 egyszeres — egy mű Byz-Byz-ben kettősen / megkett`
        # Helyesebb: a-tag-pair száma vs. minimize
        # Egyszerűbb: egy matcheczyt --tagged-nél mindkét oldalt számoljuk.
        for b, d in sorted(per_biz.items(), key=lambda kv: -kv[1]["tagged"]):
            if d["total"]:
                L.append(f"| {b} | {d['total']} | {d['tagged']} | "
                         f"{d['tagged']/d['total']:.0%} |")
        L.append("")
        (out / "filter_report.md").write_text("\n".join(L), encoding="utf-8")
        print(f"\nEredmény (globális, {len(byz_byz)} match):")
        print(f"  ancient_commonplace: {n_tag_tot} ({n_tag_tot/len(byz_byz):.1%})"
              f"  |  tiszta: {len(byz_byz)-n_tag_tot}")
        print(f"Kimenetek: {out}/")
        return 0

    ancient_coords = collect_ancient_coords(byz_ancient, args.byz_work)
    print(f"  kontroll-koordináták: {sum(len(v) for v in ancient_coords.values())} "
          f"a {len(ancient_coords)} citation_page-en")

    tagged = tag_byz_byz_matches(byz_byz, args.byz_work, ancient_coords,
                                  args.min_ratio)
    write_tagged_ndjson(tagged, out / "byz_byz_tagged.ndjson")
    write_tagged_tsv(tagged, out / "byz_byz_tagged.tsv")
    write_report(tagged, args.byz_work, args.min_ratio, ancient_coords,
                 out / "filter_report.md")

    involved = [m for m in tagged
                if m["work_i"] == args.byz_work or m["work_j"] == args.byz_work]
    n_tagged = sum(1 for m in involved if m["tag"] == "ancient_commonplace")
    print(f"\nEredmény ({args.byz_work}-t érintő {len(involved)} match):")
    print(f"  ancient_commonplace címkézett: {n_tagged} "
          f"({n_tagged/len(involved):.1%})  |  tiszta: {len(involved)-n_tagged}")
    print(f"Kimenetek: {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())