#!/usr/bin/env python3
"""
scripts/find_text_reuse.py
==========================

Szisztematikus szövegegyezés-keresés a Byzantik korpuszban a KONI FLAME
motorjával, kronológiai sorrendben.

A felépített korpusz (data/corpus/<era>/*.json — citation-line szegmensek)
minden művét Flame comparison-unitokká alakítja (citation-page szerint
csoportosítva + 140-szavas átfedő windowing, a KONI app/texts.py konvenciója
szerint), majd all-pairs (i<j, irányítatlan) Levenshtein-toleráns
szövegegyeztetést fut rajtuk. A matcheket (idézetek, imitációk, formula-szerű
ismétlések) citation-ref-fel együtt kimenti NDJSON + TSV + Markdown
jelentésbe, utóbbit kronológiai bontásban (korszak-páronként a legerősebb
egybeesések).

A FLAME motor a szomszédos KONI repo-ból kerül importálra (cross-repo):
  sys.path.insert(0, KONI_ROOT); from app import flame_pure
A BPE modell (KONI/data/bpe_vocab.json) automatikusan betöltődik. Az
app.texts modul NEM importálható cross-repo (canon.py → scripts/common.py
függőség), de nem is kell — a unitokat a Byzantik JSON-ekből építjük, a
motor csak a flame_pure.compare_iter függvényt adja.

Függőség: a KONI repo elérhetősége (default /home/tamask/github/KONI).

Használat:
  python scripts/find_text_reuse.py                         # teljes 325 pár sweep
  python scripts/find_text_reuse.py --only 9019.001,0732.004  # 1 pár (próba)
  python scripts/find_text_reuse.py --limit-pairs 5          # első 5 pár (skála-mérés)
  python scripts/find_text_reuse.py --group-by segment       # finomabb citation-horgony
  python scripts/find_text_reuse.py --fuzz 0.70 --ngram 5    # küszöb-override
  python scripts/find_text_reuse.py --koni-root /path/to/KONI --out-dir logs --top 10
"""

from __future__ import annotations

import argparse
import glob
import itertools
import json
import re
import sys
import time
from collections import OrderedDict, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "corpus_manifest.yaml"
CORPUS = ROOT / "data" / "corpus"
DEFAULT_KONI_ROOT = Path("/home/tamask/github/KONI")
DEFAULT_OUT_DIR = ROOT / "logs"

# Korszak → kronológiai rendezési rang (a manifest era-mezője alapján).
# Az `ancient_classical` (ókori/későantik kontrollkorpusz — pl. Proklos In Remp.)
# a rang 0, hogy a kronológiai jelentésben MINDEN bizánci (≥1) réteg előtt
# jelenjen meg: a cross-author egyezésekben az ókori a "forrás", a bizánci a
# "fogadó" — így a I/3 kontrollkorpusz-szűrő (Byz–Byz vs Byz–Ókor) olvasható.
ERA_RANK = {"ancient_classical": 0, "7th_8th": 1, "9th_10th": 2, "11th_12th": 3}

# KONI app/texts.py konstansok (a windowing-hez — ott is így).
MAX_UNIT_WORDS = 140
UNIT_OVERLAP = 25

# Milestone-refek (pl. (15), [2]) eltávolítása, hogy ne törjék az n-gramokat.
_MILESTONE_RE = re.compile(r"[\(\[][0-9]+[\)\]]")
_WS = re.compile(r"\s+")

# --- Zajszűrés (I/2 surgical edit): apparátus, markup, átvezető-sablonok,
#     modern fejlécek.  Konvenció: CSAK stabil formulák, sosem egyedi szavak
#     (pl. \bom\b tilos — a latin 'omni/omnem' igazi szó; csak az 'om.'
#     omissit-jelölés).  A `_clean_text` alkalmazza őket a FLAME unit-építés
#     ELŐTT, így a markup/apparátus nem jut el a Phase-2 \b\w+\b tokenizálásig. ---

# EpiDoc/TEI/XML markup-tagek: <i>...</i>, <gap/>, <lb n=".."/> stb. A FLAME
# Phase-2 \b\w+\b különben "i"/"gap" szóként találná meg őket → hamis egyezés.
_TAG_RE = re.compile(r"</?[a-zA-Z][^<>]*>")

# Kritikai apparátus-jelölések (stabil formulák):
#   - 'om.' omissit                (csak ponttal — nem \bom\b, az latin 'omni')
#   - '(24) a: om.'                (zárójeles elhagyás lemma+jelölés)
#   - '4a', '12b'                  (\b\d+[a-z]\b — margó-linajelek)
#   - 'q4', 'c3', 'q38'            (\b[cq]\d+\b — apparatus-linajelek)
_APPARATUS_RE = re.compile(
    r"\bom\."
    r"|\(\d+\)\s*[a-z]:\s*om\."
    r"|\b\d+[a-z]\b"
    r"|\b[cq]\d+\b"
)

# Modern metaadat- és licenc-sorok: a teljes SOR eldobása, ha ezeket tartalmazza
# (a fejléc tipikusan önálló sor a JSON szegmensben, nem kevert).
_HEADER_KEYS = re.compile(
    r"Gregory R\. Crane"
    r"|Editor-in-Chief, Perseus"
    r"|Creative Commons"
    r"|Attribution-ShareAlike"
    r"|University of Leipzig"
    r"|urn:cts:"
    r"|This work is licensed"
    r"|Digital Library"
    r"|National Endowment"
)

# Bizánci/későantik schola-átvezető SABLONOK — csak a teljes, stabil formula
# (Jonathan által idézett minták).  Konzervatív: nem egyedi szavakat töröl,
# hanem a kész formula-szöveget üres ACT-re helyettesíti, megszakítva a hamis
# n-gram-láncot.  A pilot (I/3) után finomítható.
_STOP_PHRASES = [
    "δὲ τὰ ἑξῆς",
    "τοῦτο δὲ ταὐτὸν ἐστι τῷ",
    "ἐν δὲ τῇ λέξει τῇ",
    "ἐν δὲ τῇ λεξεί τῇ",
]
_STOP_PHRASE_RE = re.compile("|".join(re.escape(p) for p in _STOP_PHRASES))


# ---------------------------------------------------------------------------
# FLAME motor cross-repo betöltése
# ---------------------------------------------------------------------------

def load_flame(koni_root: Path):
    """A KONI repo-ból importálja a flame_pure modult (BPE auto-load).
    Visszatér: a flame_pure module.  A hívó a flame_pure.compare_iter-t használja."""
    koni_root = Path(koni_root)
    if not koni_root.is_dir():
        raise FileNotFoundError(
            f"A KONI repo nem található: {koni_root} (--koni-root)")
    sys.path.insert(0, str(koni_root))
    from app import flame_pure  # noqa: E402 — BPE auto-load a KONI/data-ből
    return flame_pure


# ---------------------------------------------------------------------------
# Művek + meta betöltése, kronológiai rendezés
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}


def find_work_json(work: dict) -> Path | None:
    """A manifest műhöz a felépített JSON útvonala:
    data/corpus/<era>/<tlg_id>__*.json (a fetch_and_parse/build_from_tlg_html
    konvenció: <tlg_id>__<slug>.json)."""
    era = work.get("era")
    if not era:
        return None
    matches = sorted(glob.glob(str(CORPUS / era / f"{work['tlg_id']}__*.json")))
    return Path(matches[0]) if matches else None


def collect_built_works(manifest: dict, only: set | None) -> list[dict]:
    """Csak a felépített (van JSON) művek, kronológiai sorrendben
    (era-rank, majd tlg_id).  Visszatér: [{tlg_id, era, author, title,
    json_path, era_rank}]."""
    out = []
    for w in manifest.get("works", []) or []:
        if only and w["tlg_id"] not in only:
            continue
        jp = find_work_json(w)
        if jp is None:
            continue
        out.append({
            "tlg_id": w["tlg_id"], "era": w.get("era", ""),
            "author": w.get("author", ""), "title": w.get("title_latin", ""),
            "json_path": jp,
            "era_rank": ERA_RANK.get(w.get("era", ""), 9),
        })
    out.sort(key=lambda r: (r["era_rank"], r["tlg_id"]))
    return out


# ---------------------------------------------------------------------------
# Section-ök építése művenként (Byzantik JSON → Flame comparison-unitok)
# ---------------------------------------------------------------------------

def _clean_text(t: str) -> str:
    r"""Szövegtisztítás a FLAME unit-építés ELŐTT.

    Sorrend: modern fejléc/licenc-sorok eldobása → EpiDoc/TEI markup-tagek →
    kritikai apparátus (om./a: om./margó-linajelek) → schola-átvezető sablonok
    → milestone-refek (pl. (15), [2]) → maradék whitespace összevonása.

    A tisztítás HERE fut (a build_units citation-page csoportosítás + 140-szavas
    windowing előtt), így a markup/apparátus nem is jut el a FLAME Phase-2
    \b\w+\b tokenizálásáig — az n-gramok tiszták maradnak.  A Byzantik JSON-szöveg
    nagy része már tiszta, de a tlg_html/raw_pdf forrásokból (pl. 2892.044 EpiDoc
    <i>-tagek, 2892.050 'om.'-apparátus) becsúszhat zaj.

    Szándékosan konzervatív: sosem \bom\b (latin 'omni/omnem'), csak stabil
    formulák.  Lásd a modul-szintű `_TAG_RE/_APPARATUS_RE/_HEADER_KEYS/
    _STOP_PHRASE_RE` konstansokat a feljegyzett I/2 indoklással."""
    if not t:
        return ""
    # (a) Modern fejléc/licenc-sorok eldobása — szegenms-szintű (pe. a fejléc
    #     önálló sor; ha kevert lenne, a sor-törlés túl vág, de mérés szerint ritka).
    lines = [ln for ln in t.splitlines() if not _HEADER_KEYS.search(ln)]
    t = " ".join(lines)
    # (b)–(e) Sorrend fix: tag → apparátus → stop-phrase → milestone.
    t = _TAG_RE.sub(" ", t)
    t = _APPARATUS_RE.sub(" ", t)
    t = _STOP_PHRASE_RE.sub(" ", t)
    t = _MILESTONE_RE.sub("", t)
    return _WS.sub(" ", t).strip()


def _window_units(units: list[dict]) -> list[dict]:
    """Túl hosszú unitok (>MAX_UNIT_WORDS szó) átfedő word-windowokra bontása;
    rövid unitok átengedése.  A window-label #k suffixet kap (pl. '1.2#3').
    (A KONI app/texts.py._window_units logikájának másolata.)"""
    out = []
    step = max(1, MAX_UNIT_WORDS - UNIT_OVERLAP)
    for u in units:
        words = u["text"].split()
        if len(words) <= MAX_UNIT_WORDS:
            out.append(u)
            continue
        part = 1
        for k in range(0, len(words), step):
            chunk = words[k:k + MAX_UNIT_WORDS]
            if not chunk:
                break
            out.append({"label": f'{u["label"]}#{part}',
                        "text": " ".join(chunk)})
            part += 1
            if k + MAX_UNIT_WORDS >= len(words):
                break
    return out


def build_units(json_path: Path, tlg_id: str,
                 group_by: str = "page") -> list[dict]:
    """Egy mű szegmenseiből Flame comparison-unitok: [{'label', 'text'}].

    group_by='page': szegmensek (chapter,page) szerinti csoportosítása egy-egy
      citation-page unitba (szöveg = a csoport szegmens-szövegei olvasási
      sorrendben; label = '{tlg_id} {ch}/{p}'). Ha page None, chapter szerint.
    group_by='segment': minden szegmens külön unit (finomabb citation-horgony).

    Ezután milestone-strip + 140-szavas átfedő windowing."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segs = data.get("segments", []) or []

    if group_by == "segment":
        raw = [{"label": s.get("ref", ""),
                "text": _clean_text(s.get("text", ""))}
               for s in segs if s.get("text")]
    else:  # 'page' — citation-page csoportosítás
        groups: "OrderedDict[tuple, list[str]]" = OrderedDict()
        for s in segs:
            txt = s.get("text")
            if not txt:
                continue
            ch = s.get("chapter") or ""
            pg = s.get("page") or ""
            # Ha van page, (ch,pg) a kulcs; ha nincs, (ch,'') — chapter-szerint.
            key = (ch, pg) if pg else (ch, "")
            groups.setdefault(key, []).append(_clean_text(txt))
        raw = []
        for (ch, pg), texts in groups.items():
            label = f"{ch}/{pg}" if pg else f"{ch}/"
            raw.append({"label": label.strip(), "text": " ".join(texts).strip()})

    # Üres unitok kiszűrése + windowing.
    raw = [u for u in raw if u["text"]]
    return _window_units(raw)


# ---------------------------------------------------------------------------
# All-pairs sweep
# ---------------------------------------------------------------------------

def run_sweep(works: list[dict], flame, kw: dict, limit_pairs: int | None
              ) -> list[dict]:
    """All-pairs (i<j) Flame összehasonlítás.  Visszatér: match-rekord listája.
    Minden mű unitjai egyszer épülnek (cache), és újrahasználódnak a párokhoz."""
    compare_iter = flame.compare_iter
    units_cache: dict[str, list[dict]] = {}
    n_pairs_total = len(works) * (len(works) - 1) // 2
    pairs = list(itertools.combinations(range(len(works)), 2))
    if limit_pairs is not None:
        pairs = pairs[:limit_pairs]

    matches: list[dict] = []
    t0 = time.time()
    for n, (i, j) in enumerate(pairs, 1):
        wi, wj = works[i], works[j]
        # Unitok cache-lése művenként.
        if wi["tlg_id"] not in units_cache:
            units_cache[wi["tlg_id"]] = build_units(
                wi["json_path"], wi["tlg_id"])
        if wj["tlg_id"] not in units_cache:
            units_cache[wj["tlg_id"]] = build_units(
                wj["json_path"], wj["tlg_id"])
        ui, uj = units_cache[wi["tlg_id"]], units_cache[wj["tlg_id"]]

        pair_t0 = time.time()
        n_pair_matches = 0
        for ev in compare_iter(ui, uj, **kw):
            if ev.get("t") != "pair":
                continue
            p = ev["pair"]
            matches.append({
                "work_i": wi["tlg_id"], "work_j": wj["tlg_id"],
                "era_i": wi["era"], "era_j": wj["era"],
                "author_i": wi["author"], "author_j": wj["author"],
                "title_i": wi["title"], "title_j": wj["title"],
                "score": p.get("score", 0.0),
                "chain_len": p.get("chain_len", 0),
                "matched_words": p.get("matched_words", 0),
                "ref_i": p.get("label_i", ""), "ref_j": p.get("label_j", ""),
                "word_range_i": p.get("word_range_i", ""),
                "word_range_j": p.get("word_range_j", ""),
                "snippet_i": p.get("snippet_i", ""),
                "snippet_j": p.get("snippet_j", ""),
            })
            n_pair_matches += 1
        dt = time.time() - pair_t0
        print(f"  [{n}/{len(pairs)}] {wi['tlg_id']} × {wj['tlg_id']}  "
              f"units=({len(ui)},{len(uj)})  matches={n_pair_matches}  "
              f"{dt:.1f}s  (elapsed {time.time()-t0:.0f}s)")
    return matches


# ---------------------------------------------------------------------------
# Kimenetek: NDJSON + TSV + Markdown
# ---------------------------------------------------------------------------

def write_ndjson(matches: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for m in matches:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def write_tsv(matches: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["work_i", "ref_i", "era_i", "work_j", "ref_j", "era_j",
            "score", "chain_len", "matched_words",
            "snippet_i", "snippet_j", "author_i", "author_j",
            "title_i", "title_j"]
    with path.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for m in matches:
            f.write("\t".join(str(m.get(c, "")).replace("\t", " ")
                              for c in cols) + "\n")


def _md_row(m: dict, snip_len: int = 70) -> str:
    si = m["snippet_i"][:snip_len].replace("|", "/").replace("\n", " ")
    sj = m["snippet_j"][:snip_len].replace("|", "/").replace("\n", " ")
    return (f"| {m['chain_len']} | {m['matched_words']} | "
            f"{m['work_i']} · {m['ref_i']} | {m['work_j']} · {m['ref_j']} | "
            f"{si} | {sj} |")


def write_markdown(matches: list[dict], works: list[dict], path: Path,
                   top: int, kw: dict, min_chain: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Korszak-párok kronológiai sorrendje (az `ancient_classical` ókori
    # kontrollkorpusz réteget is tartalmazza — rangja 0, így minden bizánci
    # réteg előtt jön; e nélkül a by_era ciklus `KeyError`-t dobna és a
    # Proklos↔bizánci egyezések kimaradnának a jelentésből).
    ALL_ERAS = ("ancient_classical", "7th_8th", "9th_10th", "11th_12th")
    era_pairs = []
    for a in ALL_ERAS:
        for b in ALL_ERAS:
            if ERA_RANK[a] <= ERA_RANK[b] and (a, b) not in era_pairs:
                era_pairs.append((a, b))

    lines = []
    lines.append("# Byzantik — Text-reuse report (FLAME)\n")
    lines.append(f"Corpus: {len(works)} built works, "
                 f"{len(works)*(len(works)-1)//2} pairs (all-pairs, i<j).")
    lines.append(f"Thresholds: ngram={kw.get('ngram')}, n_out={kw.get('n_out')}, "
                 f"fuzz={kw.get('fuzz_threshold')}, "
                 f"min_chain={kw.get('min_chain_words')}.")
    lines.append(f"Total matches: {len(matches)}; report threshold: chain >= {min_chain}.\n")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}.\n")

    # Szűrés a report-küszöbre + szerző-közi/intra-szerző szétválasztás.
    filt = [m for m in matches if m["chain_len"] >= max(min_chain, 1)]
    cross = [m for m in filt if m["author_i"] != m["author_j"]]
    intra = [m for m in filt if m["author_i"] == m["author_j"]]
    cross.sort(key=lambda m: m["chain_len"], reverse=True)
    intra.sort(key=lambda m: m["chain_len"], reverse=True)

    if not filt:
        lines.append("_No matches above the report threshold._")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    lines.append(f"**Cross-author correspondences:** {len(cross)}  "
                 f"(different authors — the philologically interesting reuse).  ")
    lines.append(f"**Intra-author:** {len(intra)}  "
                 f"(same author, two works — shared material/apparatus).\n")

    def _emit_table(ms: list[dict], n: int) -> None:
        """Egy MD-tábla (fejléc + n sor) a `lines`-ba."""
        lines.append("| chain | words | work_i · ref_i | work_j · ref_j | snippet_i | snippet_j |")
        lines.append("|---:|---:|---|---|---|---|")
        for m in ms[:n]:
            lines.append(_md_row(m, 70))
        lines.append("")

    # --- Szerző-közi: globális top + kronológiai era-pair bontás ---
    if cross:
        lines.append(f"## Cross-author top correspondences (by chain_len, top {top})\n")
        lines.append("| # | chain | words | work_i · ref_i | work_j · ref_j | snippet_i / snippet_j |")
        lines.append("|--:|---:|---:|---|---|---|")
        for k, m in enumerate(cross[:top], 1):
            si = m["snippet_i"][:55].replace("|", "/").replace("\n", " ")
            sj = m["snippet_j"][:55].replace("|", "/").replace("\n", " ")
            lines.append(f"| {k} | {m['chain_len']} | {m['matched_words']} | "
                         f"{m['work_i']} · {m['ref_i']} | {m['work_j']} · {m['ref_j']} | "
                         f"{si} / {sj} |")
        lines.append("")

        by_era = defaultdict(list)
        for m in cross:
            key = (m["era_i"], m["era_j"])
            if ERA_RANK.get(m["era_i"], 9) > ERA_RANK.get(m["era_j"], 9):
                key = (m["era_j"], m["era_i"])
            by_era[key].append(m)

        lines.append("## Cross-author by chronological layer (era-pair)\n")
        for ea, eb in era_pairs:
            ms = by_era.get((ea, eb), [])
            if not ms:
                continue
            ms_sorted = sorted(ms, key=lambda m: m["chain_len"], reverse=True)[:top]
            label = f"{ea} → {eb}" if ea != eb else f"{ea} (intra-era)"
            lines.append(f"### {label}  ({len(ms)} matches; top {len(ms_sorted)})\n")
            _emit_table(ms_sorted, top)

    # --- Intra-szerző (egy szerző két műve — közös anyag/apparatus) ---
    if intra:
        lines.append(f"## Intra-author correspondences (same author, two works; top {top})\n")
        _emit_table(intra, top)

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fő
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Szövegegyezés-keresés a Byzantik korpuszban (KONI FLAME).")
    ap.add_argument("--only", help="vesszős tlg_id részhalmaz (pl. 9019.001,0732.004)")
    ap.add_argument("--koni-root", default=str(DEFAULT_KONI_ROOT),
                    help=f"KONI repo gyökér (default: {DEFAULT_KONI_ROOT})")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                    help=f"kimeneti könyvtár (default: {DEFAULT_OUT_DIR.relative_to(ROOT)})")
    ap.add_argument("--group-by", choices=["page", "segment"], default="page",
                    help="comparison-unitok: 'page' (citation-page csoportosítás, "
                         "default) vagy 'segment' (finomabb, minden szegmens)")
    ap.add_argument("--ngram", type=int, default=4, help="Flame ngram (default 4)")
    ap.add_argument("--n-out", type=int, default=1, help="Flame n_out (default 1)")
    ap.add_argument("--fuzz", type=float, default=0.75,
                    help="Flame fuzz_threshold (default 0.75)")
    ap.add_argument("--min-chain", type=int, default=2,
                    help="Flame min_chain_words (default 2)")
    ap.add_argument("--top", type=int, default=10,
                    help="N match/réteg a Markdown jelentésben (default 10)")
    ap.add_argument("--limit-pairs", type=int, default=None,
                    help="csak az első N pár (debug/skála-mérés)")
    ap.add_argument("--max-candidates", type=int, default=4000,
                    help="Flame Phase-2 candidate-cap páronként (default 4000; "
                         "alacsonyabb = gyorsabb, kevesebb recall a zajosabb "
                         "pároknál)")
    ap.add_argument("--report-only", action="store_true",
                    help="csak a Markdown jelentés újragenerálása a cache-elt "
                         "NDJSON-ból (Flame újrafutása nélkül)")
    ap.add_argument("--report-min-chain", type=int, default=6,
                    help="MD-jelentés küszöbe: csak chain >= ennyi matchek "
                         "kerülnek a jelentésbe (default 6; a zajos rövid "
                         "matcheket kiszűri). A teljes NDJSON/TSV nem szűrt.")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    out_dir = Path(args.out_dir).resolve()

    # --- Művek (a report-onlyhoz is kell a manifest-meta) ---
    manifest = load_manifest()
    works = collect_built_works(manifest, only)
    if len(works) < 2 and not args.report_only:
        print("Kevesebb mint 2 felépített mű a kiválasztásban — nincs mit összehasonlítani.")
        return

    # --- Report-only: NDJSON-ból újra-renderelés, Flame nélkül ---
    ndjson_p = out_dir / "text_reuse_matches.ndjson"
    md_p = out_dir / "text_reuse_report.md"
    if args.report_only:
        if not ndjson_p.exists():
            print(f"[HIBA] nincs cache-elt NDJSON: {ndjson_p} "
                  f"(előbb futtass sweep-et nélküle)")
            return
        matches = [json.loads(l) for l in ndjson_p.read_text(encoding="utf-8").splitlines() if l]
        if only:
            only_ids = only
            matches = [m for m in matches
                       if m["work_i"] in only_ids and m["work_j"] in only_ids]
        kw = {"ngram": args.ngram, "n_out": args.n_out,
              "fuzz_threshold": args.fuzz, "min_chain_words": args.min_chain}
        write_markdown(matches, works, md_p, args.top, kw, args.report_min_chain)
        print(f"[REPORT-ONLY] {md_p} újragenerálva "
              f"({len(matches)} match, küsz chain>={args.report_min_chain}).")
        return

    # --- Motor ---
    try:
        flame = load_flame(Path(args.koni_root))
    except FileNotFoundError as e:
        print(f"[HIBA] {e}")
        return


    print("=" * 78)
    print(f"BYZANTIK szövegegyezés-keresés (FLAME) — {len(works)} mű, "
          f"{len(works)*(len(works)-1)//2} pár (all-pairs)")
    print(f"group_by={args.group_by}  ngram={args.ngram}  n_out={args.n_out}  "
          f"fuzz={args.fuzz}  min_chain={args.min_chain}")
    if args.limit_pairs is not None:
        print(f"[LIMIT] csak az első {args.limit_pairs} pár")
    print("=" * 78)
    for w in works:
        print(f"  {w['tlg_id']:<11} {w['era']:<10} {w['author'][:30]:<30} {w['title'][:40]}")

    kw = {
        "ngram": args.ngram, "n_out": args.n_out,
        "fuzz_threshold": args.fuzz, "min_chain_words": args.min_chain,
        "max_candidates": args.max_candidates,
    }

    # --- Sweep ---
    print("\n[Sweep] all-pairs ...")
    t0 = time.time()
    matches = run_sweep(works, flame, kw, args.limit_pairs)
    dt = time.time() - t0
    print(f"\n[Sweep] kész: {len(matches)} match, {dt:.1f}s")

    # --- Kimenetek ---
    tsv_p = out_dir / "text_reuse_matches.tsv"
    write_ndjson(matches, ndjson_p)
    write_tsv(matches, tsv_p)
    write_markdown(matches, works, md_p, args.top, kw, args.report_min_chain)
    print(f"\nKimenetek ({out_dir.relative_to(ROOT)}/):")
    print(f"  {ndjson_p.name}   {len(matches)} sor (gépi, match-enként JSON)")
    print(f"  {tsv_p.name}      {len(matches)} sor (flat TSV)")
    print(f"  {md_p.name}      Markdown jelentés (kronológiai bontás, "
          f"chain>={args.report_min_chain})")


if __name__ == "__main__":
    main()