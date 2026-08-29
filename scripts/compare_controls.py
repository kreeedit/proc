#!/usr/bin/env python3
"""
scripts/compare_controls.py
============================

III/6 demonstrációs kiegészítő: a két I.3 overlap-filter eredmény (Proklos
kontroll vs. Aristotle EN kontroll) egyetlen összehasonlító táblázatba ötvé-
se, partnerenkénti címkézési rátával.  Ez adja Jonathan módszertani cikk-
tervezetének empirikus "nyers vs. tisztított" demonstrációját.

A Proklos és az EN kontroll **eltérő kontroll-ereje** filológiai releváns:
  - Proklos: neoplatonikus HÁTTÉRKÖZHELY — kevés egybeesés Eustratiussal
    átfed (12% címkézés).
  - Arisztotelész EN: Eustratius KÖZVETLEN FORRÁSA — a Byz–Byz egyezések
    többsége az EN-re vezethető vissza (61% címkézés).
A kettő kontrasztja mutatja, hogy a kontrollkorpusz-választás határozza meg
a szűrés erejét — és a 4034.001 (Michael of Ephesus In EN) 67%-os címkézése
(Proklos kontrollal 11%) visszamenőlegesen is bizonyítja, hogy Michael
anyaga jelentősen az EN-re épül.

Használat:
  python scripts/compare_controls.py
  python scripts/compare_controls.py --proclus logs/overlap_filter
                                     --en logs/overlap_filter_en
                                     --out logs/compare_controls.md
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROCLUS = ROOT / "logs" / "overlap_filter"
DEFAULT_EN = ROOT / "logs" / "overlap_filter_en"
DEFAULT_OUT = ROOT / "logs" / "compare_controls.md"

# A manifestből partner-azonosító → szerző+cím (emberi olvashatóság a táblázatban)
PARTNERS = {
    "0732.004": "Michael of Ephesus — In Metaphysica",
    "2130.038": "Arethas — Scholia in Porphyrii Isagoge",
    "2130.039": "Arethas — Scholia in Categorias",
    "2702.010": "Psellos — Philosophica minora I",
    "2702.011": "Psellos — Philosophica minora II",
    "2702.012": "Psellos — Theologica I",
    "2702.028": "Psellos — De omnifaria doctrina",
    "2702.051": "Psellos — Epistulae",
    "2892.001": "Maximus Confessor — Quaestiones ad Thalassium",
    "2892.044": "Maximus Confessor — Epistulae",
    "2892.050": "Maximus Confessor — Ambigua ad Thomam",
    "2892.051": "Maximus Confessor — Ambigua ad Ioannem",
    "2934.002": "John of Damascus — Dialectica",
    "2934.004": "John of Damascus — Expositio fidei",
    "3062.002": "John Italos — Quaestiones quodlibetales",
    "3062.005": "John Italos — Commentaria Topicorum",
    "3062.ket": "John Italos — Logical treatises",
    "3104.004": "Nicholas of Methone — Refutatio",
    "3104.005": "Nicholas of Methone — Adv. Latinos de spiritu sancto",
    "3104.006": "Nicholas of Methone — Adv. Latinos de azymis",
    "4031.001": "Eustratius — In Analytica Posteriora II",
    "4031.002": "Eustratius — In Ethica Nicomachea I  (fókusz)",
    "4031.003": "Eustratius — In Ethica Nicomachea VI",
    "4034.001": "Michael of Ephesus — In EN IX-X",
    "4034.002": "Michael of Ephesus — In parva naturalia",
    "4034.003": "Michael of Ephesus — In de partibus animalium",
    "4034.004": "Michael of Ephesus — In de animalium motione",
    "4034.005": "Michael of Ephesus — In de animalium incessu",
    "4034.006": "Michael of Ephesus — In EN V",
    "4040.001": "Photius — Bibliotheca",
    "4040.009": "Photius — Epistulae et Amphilochia",
    "7051.001": "Doctrina patrum de incarnatione",
    "9019.001": "Stephanus Alex. — In De interpretatione",
    "non-tlg.furrer": "Horoi kai hypographai",
}


def parse_partner_table(report_text: str) -> dict[str, dict]:
    """A filter_report.md 'Bontás bizánci partnerenként' táblázatának olvasása.
    Visszatér: {tlg_id: {'total', 'tagged', 'clean', 'pct'}}"""
    out = {}
    # a tábla után | bizánci partner | ... sorok
    rows = re.findall(
        r"^\|\s*([0-9A-Za-z.\-]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)%\s*\|",
        report_text, re.MULTILINE)
    for pid, total, tagged, clean, pct in rows:
        if pid in ("bizánci partner",):
            continue
        out[pid] = {"total": int(total), "tagged": int(tagged),
                    "clean": int(clean), "pct": int(pct)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Kontroll-összehasonlító tábla")
    ap.add_argument("--proclus", default=str(DEFAULT_PROCLUS),
                    help="Proklos-kontrollú filter kimeneti könyvtár (default logs/overlap_filter)")
    ap.add_argument("--en", default=str(DEFAULT_EN),
                    help="EN-kontrollú filter kimeneti könyvtár (default logs/overlap_filter_en)")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="kimeneti Markdown (default logs/compare_controls.md)")
    args = ap.parse_args()

    pc_text = (Path(args.proclus) / "filter_report.md").read_text(encoding="utf-8")
    en_text = (Path(args.en) / "filter_report.md").read_text(encoding="utf-8")
    pc = parse_partner_table(pc_text)
    en = parse_partner_table(en_text)

    # toplines: a két kontroll összesített száma (a report fejlécből)
    pc_hdr = re.search(r"Címkézve ancient_commonplace-ként:\*\*\s*(\d+)\s*\(([\d.]+)%\)", pc_text)
    en_hdr = re.search(r"Címkézve ancient_commonplace-ként:\*\*\s*(\d+)\s*\(([\d.]+)%\)", en_text)
    pc_total = int(pc_hdr.group(1)) if pc_hdr else sum(d["tagged"] for d in pc.values())
    pc_pct = float(pc_hdr.group(2)) if pc_hdr else 0
    en_total = int(en_hdr.group(1)) if en_hdr else sum(d["tagged"] for d in en.values())
    en_pct = float(en_hdr.group(2)) if en_hdr else 0
    byz_total = pc_hdr and re.search(r"Byz–Byz matchek:\s*(\d+)", pc_text)
    byz_n = int(byz_total.group(1)) if byz_total else sum(d["total"] for d in pc.values())

    partners = sorted(set(pc) | set(en), key=lambda p: -en.get(p, {}).get("tagged", 0))
    L = []
    L.append("# III/6 demonstráció — kontrollkorpusz-választás hatása a Byz–Byz szűrésre\n")
    L.append(f"**Fókusz-bizánci mű:** Eustratius In EN I (`4031.002`), {byz_n} Byz–Byz "
             f"match összesen.  **Átfedési küszöb:** word_range-metszet ≥ 50%.\n")
    L.append("## Összesítő — a kontroll-választás drasztikus hatása\n")
    L.append("| kontroll-mű (ókori) | kontroll típus | címkézett (ancient_commonplace) | arány |")
    L.append("|---|---|---:|---:|")
    L.append(f"| Proclus In Remp. (`tlg4036.tlg001`) | neoplatonikus HÁTTÉRKÖZHELY |"
             f" {pc_total} | **{pc_pct}%** |")
    L.append(f"| Aristotle EN (`tlg0086.tlg010`)     | Eustratius KÖZVETLEN FORRÁSA |"
             f" {en_total} | **{en_pct}%** |")
    L.append("")
    L.append("**Filológiai kontraszt:** Proklos csak neoplatonikus háttérközhelyeket ad "
             "Eustratius kommentárjához (12%); Arisztotelész EN — amit Eustratius "
             "*kommentál* — a Byz–Byz egyezések 61%-át magyarázza.  A kettő különbsége "
             "*pontosan* méri, mennyi bizánci egyezés vezes vissza az ókori forrásra "
             "vs. csupán common scholastic backgroundra.\n")
    L.append("## Partnerenkénti bontás — mindkét kontrollal\n")
    L.append("| bizánci partner (Eustratius ↔ X) | Proklos kontroll % | EN kontroll % | "
             "függetlenedés az EN-től |")
    L.append("|---|---:|---:|---:|")
    for pid in partners:
        label = PARTNERS.get(pid, pid)
        pcp = pc.get(pid, {}).get("pct", 0)
        enp = en.get(pid, {}).get("pct", 0)
        # 'függetlenedés' = 100 - EN%-os címkézés (minél nagyobb, annál több valós egyedi
        # bizánci text-reuse, ami nem az EN-re vezethető vissza)
        indep = 100 - enp
        L.append(f"| {label} | {pcp}% | {enp}% | **{indep}%** |")
    L.append("")
    L.append("## Módszertani megjegyzés a bírálóknak\n")
    L.append("A 'függetlenedés az EN-től' oszlop mutatja, hogy egy bizánci szerző "
             "Eustratiussal való egyezéseinek hány százaléka **NEM** az Arisztotelész "
             "EN-re rärí vissza — tehát potenciálisan valódi bizánci text-reuse, "
             "amely további filológiai elemzést érdemel.  Ez a szűrés nem *töröl*, "
             "hanem **kategorizál**: a 'ancient_commonplace' címkéjű találatok "
             "valószínűleg közvetett hagyományközhelyek, a címke nélküliek a "
             "genuin bizánci intertextualitás jelöltjei.")
    Path(args.out).write_text("\n".join(L), encoding="utf-8")
    print(f"Összehasonlító tábla írva: {args.out}")
    print(f"  Proklos kontroll: {pc_total} címkézett ({pc_pct}%)")
    print(f"  EN kontroll:      {en_total} címkézett ({en_pct}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())