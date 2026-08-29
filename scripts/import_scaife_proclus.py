#!/usr/bin/env python3
"""
scripts/import_scaife_proclus.py
=================================

Célzott importőr a Proklos *In Platonis Rem publicam commentarii* szövegéhez a
Scaife Viewer / OpenGreek projekttől.  Ez a mű NEM a `PerseusDL/canonical-
greekLit` GitHub repo-ban elérhető TEI formában van (a `tlg4036` könyvtárban
ott csak egy téves "Chrestomathy" `tlg023` van), hanem a Scaife Viewer egy
speciális "nyers szöveg" végpontján — HTML/TEI/SPA-hackelés nélkül, egyszerű
HTTP GET-tel letölthető tiszta görög szöveg folio-horgonyokkal.

Miért önálló szkript (és nem a fő pipeline része)?
-------------------------------------------------
A fő pipeline-nak két parser-e van: `fetch_and_parse.py` (TEI XML → JSON) és
`build_from_tlg_html.py` (TLG-tükör HTML → JSON).  A Scaife nyers plain-text
formátuma egyikbe sem illik bele, és ez az egyetlen mű ebben a formátumban —
így egy új `source_type: scaife_text` bevezetése és a `build_corpus.py`
dispatch-tábla bővítése aránytalanul nagy kód lenne egyetlen célponthoz.
Ezért a "Tiszta B" megoldást követjük (lásd a projekt memóriáját,
[[byzantik-master-todo]] I/1): egy pici, célzott, dokumentált importőr, ami
reprodukválható módon letölti, megtisztítja, szegmentálja és kimenti a JSON-t.
A `corpus_manifest.yaml` egy `status: prebuilt` bejegyzéssel és egy kötelező
kommenttel hivatkozik erre a szkriptre — így a manifest továbbra is a projekt
térképe, a build reprodukálható, de a fő pipeline szétgányolása nélkül.

Letöltési végpont
-----------------
  https://scaife.perseus.org/library/passage/<URN>/text/
ahol <URN> = urn:cts:greekLit:tlg4036.tlg001.opp-grc1:1-9999
  (az `:1-9999` passzázs-tartomány a teljes Kroll-kiadást kiadja; ha
  nyitva hagyjuk az `:1-` -t, a szerver 500-at ad, ezért egy nagy felső
  határt használunk, amit a vágási logika úgyis szűkít).

A szöveg folio-horgonyokkal van címsorozva (pl. `f 3r`, `f 5r`, ... `f 200r`),
amelyek a Kroll Teubner-kiadás (1899-1901) kézirat-foliumaira utalnak.  A
letöltés végén NÉMET nyelvű kritikai/marginális apparatus van (a `:1-9999`
túllép a görög szövegen) — ezt az importőr a görög-karakterarány alapján
lenyisszantja, mielőtt a korpuszba kerülne.

Kimenet
-------
  data/corpus/ancient_classical/tlg4036.tlg001__in_rem_publicam.json
  (+ .txt a tokenizálónak)

A JSON a `find_text_reuse.py` által várt sémát követi: `meta` + `segments[]`,
ahol minden szegmens `{chapter, page, role, text, ref}` — a `page` a folió
(pl. "3r"), a `ref` a CTS-URN + folió.

Használat:
  python scripts/import_scaife_proclus.py            # letölt + ír
  python scripts/import_scaife_proclus.py --no-fetch  # a /tmp-ben lévő cache-ből
  python scripts/import_scaife_proclus.py --dry-run   # csak tervezi, nem ír
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus" / "ancient_classical"
CACHE = Path("/tmp/proclus_full.txt")  # a fejlesztés közbeni letöltés cache-e

# --- Proklos In Remp. konstansok ---
TLG_ID = "tlg4036.tlg001"
URN = "urn:cts:greekLit:tlg4036.tlg001.opp-grc1"
PASSAGE_URN = f"{URN}:1-9999"  # teljes Kroll-kiadás
URL = f"https://scaife.perseus.org/library/passage/{PASSAGE_URN}/text/"
OUT_JSON = CORPUS / "tlg4036.tlg001__in_rem_publicam.json"
OUT_TXT = CORPUS / "tlg4036.tlg001__in_rem_publicam.txt"
SAFE_NAME = "tlg4036.tlg001__in_rem_publicam"

# Folio-horgony: `f 3r`, `f 46v` formátum (Kroll Teubner foliójelek).
FOLIO_RE = re.compile(r"f\s+(\d+[rv]+)\b")
# Görög karakter (politonos görög small letters).
_GREEK = re.compile(r"[α-ωίϊϋόύώάέή]")
_WS = re.compile(r"\s+")

# A görög-arány ablak-mérete és küszöbe a német farok levágásához.
TAIL_WINDOW = 500      # karakterek/csomópont
TAIL_MIN_GREEK_RATIO = 0.10  # < 10% görög → latin-domináns (apparátus/német)
# A 'tartós alacsony sáv' küszöbe: egy ablakot még 'alacsonynak' tekintünk, ha
# görög-aránya ez alatt van.  Szigorú (0.20): a német apparatus-beli
# interlineánus görög töredékek (röviden kiugró ablakok) nem számítanak — csak a
# tartósan görög-szegény szakasz aktywálja a vágást.
TAIL_LOW_RATIO_MAX = 0.20
TAIL_LOW_RUN = 3000       # ekkora folytonos alacsony sáv (charban) kell a vágáshoz


def fetch_text() -> str:
    """Letölti a Scaife nyers szöveget.  Udvarias User-Agent."""
    print(f"  [LETÖLTÉS] {URL}")
    req = urllib.request.Request(
        URL, headers={"User-Agent": "Byzantik-Corpus-Build/1.0 (DH-research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode("utf-8", "replace")
    print(f"  letöltve: {len(t)} karakter")
    return t


def trim_german_tail(text: str) -> str:
    """Lenyisszantja a német/latin apparatus-farkot a szöveg végéről.

    A német kritikai apparatus (a `:1-9999` túllépésének következménye)
    interlineánus GÖRÖG szavakat is tartalmaz (pl. "die als ἴτη bezeichnet
    sind"), tehát egyetlen görög-ablak még a német szakaszban is előfordul —
    az "utolsó görög ablak" módszer nem megbízható.  Helyette:

      Előrefelé haladva csúszóablakok görög-arányát mérjük.  A görög szöveg
      tartósan görög-domináns; a farok elején az arány ÖSSZEOMLIK: több
      egymást követő ablak is TAIL_MIN_GREEK_RATIO alá esik és nem
      regenerálódik.  Az első olyan ablak, amelynek utána N egymást követő
      ablak is alacsony marad, a farok kezdete; itt vágunk.
    """
    n = len(text)
    if n < TAIL_WINDOW:
        return text
    # Görög-arány görbe mérése (elég sűrűn: step 100), majd egy egyszerű
    # simított (gördülő, szélesség W) görög-arány alapján detektáljuk az
    # összeomlást.  Ez robusztus a német apparatus-ban előforduló ritka
    # interlineánus görög töredékekkel szemben (amik egy-egy pillanatnyi
    # kiugrást okoznak, de az átlag alacsony marad).
    step = 100
    W = TAIL_WINDOW
    # ratio[i] = az [i, i+W) ablak görög-aránya
    pts = []  # (pos, ratio)
    i = 0
    while i < n - W:
        w = text[i:i + W]
        gk = len(_GREEK.findall(w))
        lat = len(re.findall(r"[a-zA-Z]", w))
        pts.append((i, gk / (gk + lat + 1)))
        i += step
    # simítás: gördülő átlag 3 szomszéd ablakon (magasabb robusztuság)
    smooth = []
    for k in range(len(pts)):
        lo = max(0, k - 1); hi = min(len(pts), k + 2)
        avg = sum(p[1] for p in pts[lo:hi]) / (hi - lo)
        smooth.append((pts[k][0], avg))
    # Első simított pont, ahol az átlag TAIL_MIN_GREEK_RATIO alá esik ÉS
    # az utána lévő H AllowsOPT-length szakaszban a görög-arány tartósan alacsony
    # marad (egy meghatározott szélességű low-sáv).  Az interlineánus görög
    # jegyzet-töredékek (amelyek a német apparatus-ban ritkán előfordulnak) nem
    # szakíthatják meg ezt: egészen egy TAIL_LOW_RUN hosszan kell maradnia
    # alacsonynak ahhoz, hogy vágjunk.  Ha utána újra magas lenne (még nagyobb
    # görög》, az visszakapcsolja a főszöveget — de a Kroll-farok nem ilyen,
    # csak töredékek szakaszokká.
    cut = n
    k = 0
    while k < len(smooth):
        if smooth[k][1] < TAIL_LOW_RATIO_MAX:
            # megmérjük: a k-tól lévő lépéseket TAIL_LOW_RUN char-on át
            low_span = 0
            j = k
            while j < len(smooth) and smooth[j][1] < TAIL_LOW_RATIO_MAX:
                low_span += step
                j += 1
            if low_span >= TAIL_LOW_RUN:
                cut = smooth[k][0]
                break
            k = j
        k += 1
    if cut >= n:
        return text  # nem találtunk tartós összeomlást -> ne vágj (óvatos)
    # A vágási pontnál a farok KEZDETE előtti utolsó görög mondatvéggel
    # igazodunk (a simaság kedvéért — a görög szöveg mondatvéggel zárul).
    head = text[:cut]
    last_gr = max(head.rfind("·"), head.rfind("."), head.rfind(";"))
    if last_gr > cut - 1500:
        cut = last_gr + 1
    # Másodlagos finomítás: a német kritikai apparatus gyakran a görög
    # mondat végén indul egy lapszám-jelöléssel (pl. " 1 ante ...") vagy
    # egy "Drei Exkurse" / "Zwei Exkurse" címszóval.  Ilyen előfordulásnál
    # a szöveget az utolsó görög szó/Kroll-scholion után metsszük.
    head = text[:cut]
    m = re.search(r"\s+\d+\s+(?:ante|cf\.|cf|Vgl|vgl)|\s+(?:Drei|Zwei|Ein)\s+Exkurse",
                  head)
    if m and m.start() > cut - 1500:
        cut = m.start()
    return text[:cut].rstrip()


def segment_by_folio(text: str) -> list[dict]:
    """Folio-horgonyok ('f 3r') szerinti szegmentálás.

    Minden folio egy szegmens: `page` = folió (pl. "3r"), a szöveg a következő
    folióig (vagy a szöveg végéig).  Az első szegmens a címsor-szekció lehet
    (előtte folio nélkül).
    """
    segs = []
    matches = list(FOLIO_RE.finditer(text))
    if not matches:
        return [{"chapter": "In Rempublicam", "page": "",
                 "role": "text", "ref": URN,
                 "text": _WS.sub(" ", text).strip()}]
    # Ha van szöveg az első folio előtt (címsor/kapitulumjegyzék) -> 1. szegmens
    pre = text[:matches[0].start()].strip()
    if pre:
        segs.append({"chapter": "In Rempublicam", "page": "prefatio",
                     "role": "text",
                     "ref": f"{URN}:prefatio",
                     "text": _WS.sub(" ", pre).strip()})
    # Folio-szegmentumok
    for i, m in enumerate(matches):
        folio = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        # A folio-jelzőt magát is levedjük (nem tartozik a főszövegbe már).
        # A chunk gyakran újsorral kezd a folio után.
        if chunk:
            segs.append({"chapter": "In Rempublicam", "page": folio,
                          "role": "text",
                          "ref": f"{URN}:f{folio}",
                          "text": _WS.sub(" ", chunk).strip()})
    return segs


def build_json(segments: list[dict]) -> dict:
    """A `find_text_reuse.py` által várt JSON-szerkezet (meta + segments + stats)."""
    total_chars = sum(len(s["text"]) for s in segments)
    total_words = sum(len(s["text"].split()) for s in segments)
    meta = {
        "tlg_id": TLG_ID,
        "title": "In Platonis Rem publicam commentarii",
        "author": "PROCLUS",
        "editor": "Kroll 1899-1901 (Teubner); Scaife/OGL opp-grc1 edition",
        "publisher": "Scaife Viewer / OpenGreek project (PerseusDL)",
        "pub_place": "",
        "date": "",
        "source_url": URL,
        "lang": "grc",
        "licence": "Open Greek Project — nyílt hozzáférésű",
        "source_type": "scaife_text",
        "line_scheme": "folio",
    }
    stats = {"segments": len(segments), "chars": total_chars, "words": total_words}
    return {"meta": meta, "stats": stats, "segments": segments, "notes": []}


def write_outputs(data: dict, text: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [DRY-RUN] JSON -> {OUT_JSON} ({len(data['segments'])} szegmens)")
        print(f"  [DRY-RUN] TXT  -> {OUT_TXT}")
        return
    CORPUS.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    OUT_TXT.write_text(text, encoding="utf-8")
    print(f"  [OK] {OUT_JSON}  ({len(data['segments'])} szegmens, "
          f"{data['stats']['chars']} char, {data['stats']['words']} szó)")
    print(f"  [OK] {OUT_TXT}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Proklos In Remp. importőre a Scaife-ről")
    ap.add_argument("--no-fetch", action="store_true",
                    help="nem tölt le, a /tmp/proclus_full.txt cache-ből dolgozik")
    ap.add_argument("--dry-run", action="store_true",
                    help="nem ír fájlt, csak a tervet írja ki")
    args = ap.parse_args()

    print(f"Proklos In Remp. importőr — URN: {URN}")
    if args.no_fetch and CACHE.exists():
        print(f"  [CACHE] {CACHE} ({CACHE.stat().st_size} bájt)")
        text = CACHE.read_text(encoding="utf-8", errors="replace")
    else:
        text = fetch_text()
        CACHE.write_text(text, encoding="utf-8")  # cache a fejlesztéshez

    print("  [VÁGÁS] német farok lenyisszantása…")
    before = len(text)
    text = trim_german_tail(text)
    print(f"  vágva: {before} -> {len(text)} char (-{before - len(text)})")

    print("  [SZEGMENS] folio-horgonyok szerinti bontás…")
    segments = segment_by_folio(text)
    print(f"  szegmensek: {len(segments)}; foliók: "
          f"{[s['page'] for s in segments if s['page']!='prefatio'][:3]}…"
          f"{[s['page'] for s in segments if s['page']!='prefatio'][-3:]}")

    data = build_json(segments)
    write_outputs(data, text, args.dry_run)
    print("  kész.")
    return 0


if __name__ == "__main__":
    sys.exit(main())