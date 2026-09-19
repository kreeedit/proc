"""TEI (PerseusDL) -> Byzantik corpus-JSON schema, so the REAL harness
build_units()/run_sweep() can run at production scale on real Greek.

NOT the paper's corpus (that is TLG-derived and absent from the release).
Used only to measure engine behaviour at scale.
"""
import json, os, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path

TEI = "{http://www.tei-c.org/ns/1.0}"
OUT = Path(__file__).resolve().parent / "corpus"
OUT.mkdir(parents=True, exist_ok=True)
SRC = Path(os.environ.get("KONI_TEXTS", "/home/kredit/github/KONI/data/texts"))

WORKS = [("tlg0016.tlg001", "Herodotus", "Historiae", "tlg0016/tlg001.xml"),
         ("tlg0003.tlg001", "Thucydides", "Historiae", "tlg0003/tlg001.xml"),
         ("tlg4029.tlg001", "Procopius", "De bellis", "tlg4029/tlg001.xml")]

def text_of(el):
    return " ".join(t for t in el.itertext())

def leaf_divs(root):
    body = root.find(f".//{TEI}text/{TEI}body")
    out = []
    def walk(el, path):
        kids = [c for c in el if c.tag == f"{TEI}div"]
        if not kids:
            out.append((".".join(path), el))
            return
        for c in kids:
            walk(c, path + [c.get("n") or "?"])
    for c in body:
        if c.tag == f"{TEI}div":
            walk(c, [c.get("n") or "?"])
        else:
            out.append(("", c))
    return out

for tlg, author, title, rel in WORKS:
    root = ET.parse(SRC/rel).getroot()
    segs = []
    for ref, el in leaf_divs(root):
        txt = re.sub(r"\s+", " ", text_of(el)).strip()
        if not txt:
            continue
        # chapter = top-level book, so build_units groups into book-sized units
        book = ref.split(".")[0] if ref else ""
        segs.append({"chapter": book, "page": "", "role": "body",
                     "text": txt, "ref": ref})
    words = sum(len(s["text"].split()) for s in segs)
    doc = {"meta": {"tlg_id": tlg, "author": author, "title": title,
                    "lang": "grc", "source_type": "open_tei",
                    "licence": "CC BY-SA 4.0 PerseusDL"},
           "stats": {"segments": len(segs), "words": words},
           "segments": segs, "notes": []}
    p = OUT / f"{tlg}__{title.lower()}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"{tlg:16s} {author:12s} segs={len(segs):5d} words={words:7d}  -> {p.name}")
