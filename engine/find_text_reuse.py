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

A FLAME motor alapból a kiadásba csomagolt `engine/flame/` csomagból töltődik:
  sys.path.insert(0, <engine>); from flame import flame_pure
A BPE modell (`engine/data/bpe_vocab.json`) automatikusan betöltődik. Az
app.texts modul NEM importálható (canon.py → scripts/common.py függőség), de
nem is kell — a unitokat a korpusz JSON-ekből építjük, a motor csak a
flame_pure.compare_iter függvényt adja.

A `--koni-root` opcionális: ha megadod, a produkciós cross-repo kódút fut
(sys.path.insert + from app import flame_pure), egy szomszédos KONI checkoutból.

Függőségek: a motor stdlib-only; ez a szkript a manifesthez PyYAML-t igényel
(és a teljes sweephez a nem-redisztributálható korpuszt — lásd README).

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
import hashlib
import itertools
import json
import re
import sys
import time
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

# A PyYAML szándékosan lusta import (a load_manifest() belsejében): a modul
# importálása így stdlib-only marad, a demo nem igényel harmadik féltől származó
# csomagot.  Csak a manifestet olvasó belépési pontok (main(), load_manifest())
# igényelnek PyYAML-t.

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "corpus_manifest.yaml"
CORPUS = ROOT / "data" / "corpus"
# A kiadásba csomagolt Flame motor (engine/flame/) — ez az elsődleges.
# A --koni-root csak visszafelé-kompatibilitási override (produkciós kódút).
BUNDLED_FLAME_DIR = Path(__file__).resolve().parent
DEFAULT_KONI_ROOT = None  # None -> a csomagolt engine/flame/ csomag
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
# A „same work pair, different passage" listában ennyi rekordot írunk ki NÉVVEL
# (a közelieket és a távoliakat együtt, a legközelebbivel kezdve); afelett csak a
# maradék darabszámot.  Korábban itt egy NEAR_WORDS-küszöb osztotta két csoportra
# a rekordokat, amitől ugyanaz a rekord az egyik dup-csoport alatt névvel, a
# másik alatt névtelen darabszámként jelent meg — ellenőrizhetetlenül.
MAX_NAMED_OTHERS = 6

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
# FLAME motor betöltése
# ---------------------------------------------------------------------------

def load_flame(koni_root: "Path | None" = None):
    """A flame_pure modul betöltése (BPE auto-load).
    Visszatér: a flame_pure module.  A hívó a flame_pure.compare_iter-t használja.

    koni_root=None  -> a kiadásba csomagolt `engine/flame/` csomag
                       (BPE: engine/data/bpe_vocab.json).
    koni_root=<path> -> szomszédos KONI checkout (from app import flame_pure):
                       a produkciós cross-repo kódút változatlan rekonstrukciója."""
    if koni_root is None:
        if str(BUNDLED_FLAME_DIR) not in sys.path:
            sys.path.insert(0, str(BUNDLED_FLAME_DIR))
        from flame import flame_pure  # noqa: E402 — BPE auto-load az engine/data-ból
        return flame_pure
    koni_root = Path(koni_root)
    if not koni_root.is_dir():
        raise FileNotFoundError(
            f"A KONI repo nem található: {koni_root} (--koni-root)")
    sys.path.insert(0, str(koni_root))
    from app import flame_pure  # noqa: E402 — BPE auto-load a KONI/data-ból
    return flame_pure


# ---------------------------------------------------------------------------
# Művek + meta betöltése, kronológiai rendezés
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    import yaml  # lusta import — csak ez a függvény igényli (PyYAML)
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
                # A `matched_words` (=cnt_i) KIZÁRÓLAG az i-oldal illesztett
                # szavait számolja; a két oldal darabszáma nem feltétlenül
                # egyezik (a `_block_word_maps` oldalanként dedupál, és az
                # `n_out`-tal összevont blokkok kiterjedése átfedhet), ezért a
                # j-oldali számot külön vesszük. Élő példa: `616/#3 ×
                # In Rempublicam/4v#181` → cnt_i=31, cnt_j=19, span_j=21.
                "matched_words_j": len(p.get("matched_j") or {}),
                # Hány blokk maradt fenn a szűrő után. Ez magyarázza, miért lehet
                # chain_len < matched_words: a chain_len a LEGHOSSZABB blokk
                # illesztett szópárjainak száma, a matched_words pedig az ÖSSZES
                # fennmaradt blokk i-oldali illesztett szavai — egy rekordon belül.
                "n_chained": p.get("n_chained", 0),
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
            "score", "chain_len", "matched_words", "matched_words_j", "n_chained",
            "word_range_i", "word_range_j",
            "snippet_i", "snippet_j", "author_i", "author_j",
            "title_i", "title_j"]
    with path.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for m in matches:
            f.write("\t".join(str(m.get(c, "")).replace("\t", " ")
                              for c in cols) + "\n")


def _clip(text: str, limit: int) -> str:
    """Szóhatár-alapú csonkítás a táblázatokhoz.

    A nyers `text[:limit]` szó közepén vágott (pl. „τραγῳ" a „τραγῳδίαν"
    helyett), ami a riportot publikálhatatlanná tette. Itt a levágást az utolsó
    szóhatárra toljuk, és `…`-tal jelöljük. A `|` escape-elése megmarad, mert
    a szöveg Markdown-táblacellába kerül."""
    t = " ".join(text.split()).replace("|", "/")
    if len(t) <= limit:
        return t
    cut = t[:limit]
    sp = cut.rfind(" ")
    if sp > 0:
        return cut[:sp].rstrip() + " …"
    # Nincs szóköz a limitig: a vágás az első szó belsejébe esne. Ilyenkor a
    # teljes első szót adjuk vissza (a limit fölé nyúlva), mert a szó közepén
    # elvágott töredék („τραγῳ" a „τραγῳδίαν" helyett) nem publikálható.
    nxt = t.find(" ", limit)
    if nxt == -1:
        return t  # egyetlen, törhetetlen token — nincs szóhatár, ahol vághatnánk
    return t[:nxt].rstrip() + " …"


def _abs_span(ref: str, rng: str) -> tuple[str, int, int]:
    """`ref` ('unit' vagy 'unit#k') + `rng` ('12–34') → (unit, abs_lo, abs_hi).

    A `#k` ablak-suffixet visszaszámolja a uniton belüli abszolút szó-indexre
    (window: MAX_UNIT_WORDS szó, lépés MAX_UNIT_WORDS - UNIT_OVERLAP), különben
    a koordináta már abszolút.  Így két különböző ablakból származó rekord
    összehasonlítható: enélkül nem látszik, hogy ugyanazt a szövegpárhuzamot
    írják le."""
    unit, sep, win = ref.rpartition("#")
    if not sep or not win.isdigit():
        unit, win = ref, "1"
    lo, dash, hi = rng.partition("\u2013")
    base = (int(win) - 1) * (MAX_UNIT_WORDS - UNIT_OVERLAP)
    lo_i = int(lo) if lo.strip().isdigit() else 0
    hi_i = int(hi) if hi.strip().isdigit() else lo_i
    return unit, base + lo_i, base + hi_i


def _overlap_groups(matches: list[dict]) -> list[dict]:
    """Ugyanazt a szövegpárhuzamot leíró, átfedő rekordok klaszterei.

    A 140-szavas ablakok 25 szón átfednek MINDKÉT oldalon, ezért egy összefüggő
    párhuzam két (ablak_i, ablak_j) rekordként is megjelenhet.  Egy klaszter:
    azonos (work_i, unit_i, work_j, unit_j) kulcson belül az i-oldali
    szóintervallumukban átfedő rekordok, az egyesített kiterjedéssel."""
    groups: dict = defaultdict(list)
    for m in matches:
        ui, lo, hi = _abs_span(m["ref_i"], m["word_range_i"])
        uj, lo2, hi2 = _abs_span(m["ref_j"], m["word_range_j"])
        groups[(m["work_i"], ui, m["work_j"], uj)].append((m, (lo, hi), (lo2, hi2)))
    out = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        clusters: list[list] = []
        for it in sorted(items, key=lambda x: x[1]):
            if clusters and it[1][0] <= clusters[-1][-1][1][1]:
                clusters[-1].append(it)
            else:
                clusters.append([it])
        for cl in clusters:
            if len(cl) < 2:
                continue
            out.append({
                "key": key,
                "items": [x[0] for x in cl],
                "i": (min(x[1][0] for x in cl), max(x[1][1] for x in cl)),
                "j": (min(x[2][0] for x in cl), max(x[2][1] for x in cl)),
            })
    return out


_TABLE_HEAD = ("| chain | words_i | words_j | gap_i | gap_j | blocks | score | span_i | span_j | "
               "work_i · ref_i | work_j · ref_j | snippet_i | snippet_j |")
# PONTOSAN annyi cella, mint a fejlécben (13).  Egy korábbi szerkesztés itt
# 14-et hagyott; a laza renderelők elnyelik, a szigorúbbak (GitHub egyes
# útvonalai, pandoc) viszont az EGÉSZ táblát nyers szövegként dobják ki.
_TABLE_RULE = "|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|"


def _assert_table_shape(header: str, rule: str, rows: list[str], where: str) -> None:
    """A generált tábla minden sora ugyanannyi cellából álljon.

    A hibaosztály, amit kizár: a fejléc/oszlopok szerkesztésekor az elválasztó
    sor vagy egy adatsor lemarad.  Ez csendben rossz Markdown-t ad, amit csak a
    renderelő bukása mutat meg — ezért itt, a writerben derüljön ki."""
    def ncell(line: str) -> int:
        return len(line.strip().strip("|").split("|"))
    n = ncell(header)
    for label, line in [("separator", rule)] + [(f"row {i}", r) for i, r in enumerate(rows, 1)]:
        if ncell(line) != n:
            raise ValueError(
                f"{where}: {label} has {ncell(line)} cells, header has {n}. "
                f"Strict Markdown renderers would not treat this as a table.")


def _span_width(rng: str) -> int:
    """`'23–52'` → 30 (a `word_range` szélessége, 1-alapú inkluzív)."""
    lo, dash, hi = rng.partition("\u2013")
    if not lo.strip().isdigit():
        return 0
    hi = hi if hi.strip().isdigit() else lo
    return int(hi) - int(lo) + 1


def _gap_words(m: dict, side: str):
    """A `word_range_*` kiterjedésén belül NEM illeszkedő szavak száma.

    A `word_range` az első és az utolsó illesztett szó közötti teljes
    intervallum, ezért `gap = span - (az adott oldal illesztett szavai)`
    pontosan a kihagyott (illesztetlen) szavakat adja — a blokkon BELÜLI,
    `n_out`-tal összevont réseket és a blokkok KÖZÖTTI réseket együtt.  Ez az a
    szám, ami megmagyarázza, miért lehet egy blokk mellett is `span > matched`.

    FONTOS: oldalanként a SAJÁT darabszámot kell használni.  A `matched_words`
    csak az i-oldalt számolja, a j-oldalé a `matched_words_j`; a kettő
    érdemben eltérhet (mért példa: cnt_i=31, cnt_j=19), és ha a j-oldali
    szélességhez az i-oldali darabszámot vonnánk, negatív „rés" adódna, amit
    nullázva a jelentés hamis nullát közölne.

    Visszatér: int, vagy None, ha a rekord nem tartalmazza a szükséges mezőt
    (a kiadott teljes sweep ilyen: nincs benne `matched_words_j`)."""
    span = _span_width(m.get("word_range_" + side) or "")
    if not span:
        return None
    cnt = m.get("matched_words") if side == "i" else m.get("matched_words_j")
    if cnt is None:
        return None
    return max(0, span - int(cnt))


def _cell(v) -> str:
    """Táblacella: a `None` (nincs adat) jele `–`, nem `0`."""
    return "–" if v is None else str(v)


def _md_row(m: dict, snip_len: int = 70, mark: str = "") -> str:
    si = _clip(m["snippet_i"], snip_len)
    sj = _clip(m["snippet_j"], snip_len)
    return (f"| {m['chain_len']} | {m['matched_words']} | "
            f"{_cell(m.get('matched_words_j'))} | "
            f"{_cell(_gap_words(m, 'i'))} | {_cell(_gap_words(m, 'j'))} | "
            f"{m.get('n_chained') or 'n/a'} | "
            f"{m['score']:.4f} | {m['word_range_i']} | {m['word_range_j']} | "
            f"{m['work_i']} · {m['ref_i']}{mark} | {m['work_j']} · {m['ref_j']}{mark} | "
            f"{si} | {sj} |")


def corpus_ref(manifest_path: Path | None = None) -> str:
    """A korpusz-verzió hivatkozási pontja a riport fejlécéhez.

    Az era-címkék a `corpus_manifest.yaml`-ból jönnek, és egy korpusz-javítás
    (pl. apparátus-szűrés) az offszeteket is elmozdítja — a manifeszt hash-e az
    egyetlen pont, ahol két riport összehasonlítható marad."""
    mp = manifest_path or MANIFEST
    if mp.is_file():
        h = hashlib.sha256(mp.read_bytes()).hexdigest()
        return f"{mp.name} sha256 {h[:16]}…"
    return ("no corpus_manifest.yaml in this package — bundled samples only, "
            "see the file hashes in engine/MANIFEST.sha256")


# A demó keretező bekezdése.  FONTOS: ez NEM a sweep riportjáé — a
# `write_markdown`-t a teljes sweep is hívja (l. a két `run_sweep`-hívást), és
# ott ez a szöveg egyszerűen hamis lenne: a sweep 38 mű minden párját dolgozza
# fel, nem egyetlen ismert kontrollpárt.  Ezért a riport-író csak akkor fűzi be,
# ha a hívó kifejezetten kéri (`scope=`), ugyanúgy, ahogy a `manifest_ref`-et is.
DEMO_SCOPE = (
    "Scope: this is an engine demonstration, not a sample of the paper's "
    "results. The pair is control × control (Plato, *Respublica* × Proclus, "
    "*In Rempublicam*), a known lemmatic-quotation relation: Proclus cites "
    "Plato's text as the lemma of his commentary. Long verbatim chains are "
    "therefore expected here, and are the phenomenon the Topos Exclusion "
    "Matrix is designed to remove — not the covert borrowing the case "
    "studies argue for.")


def write_markdown(matches: list[dict], works: list[dict], path: Path,
                   top: int, kw: dict, min_chain: int = 0,
                   manifest_ref: str | None = None,
                   scope: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Korszak-párok kronológiai sorrendje (az `ancient_classical` ókori
    # kontrollkorpusz réteget is tartalmazza — rangja 0, így minden bizánci
    # réteg előtt jön; e nélkül a by_era ciklus `KeyError`-t dobna és a
    # Proklos↔bizánci egyezések kimaradnának a jelentésből).
    # A tényleges riport-küszöb (a szűrő max(min_chain, 1)-et használ) — egyszer
    # számoljuk, hogy a fejléc és a szűrés ne mondhasson mást.
    thr = max(min_chain, 1)
    ALL_ERAS = ("ancient_classical", "7th_8th", "9th_10th", "11th_12th")
    era_pairs = []
    for a in ALL_ERAS:
        for b in ALL_ERAS:
            if ERA_RANK[a] <= ERA_RANK[b] and (a, b) not in era_pairs:
                era_pairs.append((a, b))

    lines = []
    lines.append("# Byzantik — Text-reuse report (FLAME)\n")
    n_pairs = len(works) * (len(works) - 1) // 2
    lines.append(f"Corpus: {len(works)} built works, {n_pairs} "
                 f"{('pair' if n_pairs == 1 else 'pairs')} (all-pairs, i<j) — "
                 f"{manifest_ref or corpus_ref()}.")
    # Keretező bekezdés, de CSAK a demó riportjában (`scope=DEMO_SCOPE`).  A sweep
    # riportja a cikk saját eredménye, ott ez a mondat önmagát cáfolná.
    if scope:
        lines.append(scope + "\n")
    lines.append(f"Thresholds: ngram={kw.get('ngram')}, n_out={kw.get('n_out')}, "
                 f"fuzz={kw.get('fuzz_threshold')}, "
                 f"min_chain={kw.get('min_chain_words')}, "
                 f"max_candidates={kw.get('max_candidates')}.")
    lines.append(f"Total matches: {len(matches)}; report threshold: chain >= {thr}.")

    # A 140-szavas ablakok 25 szón átfednek mindkét oldalon, ezért egy összefüggő
    # párhuzam több rekordként is megjelenhet — a nyers darabszám felfelé torzít.
    # A „rekord" és a „szövegpárhuzam" szétválasztása nélkül a fejléc félrevezet.
    ovl = _overlap_groups(matches)
    marks: dict[int, str] = {}
    for gi, g in enumerate(ovl, 1):
        for m in g["items"]:
            marks[id(m)] = f" [dup {gi}]"
    n_redundant = sum(len(g["items"]) - 1 for g in ovl)
    if ovl:
        lines.append(
            f"Distinct passages: {len(matches) - n_redundant} — {n_redundant} of the "
            f"{len(matches)} records re-report a passage already listed: the units are "
            f"{MAX_UNIT_WORDS}-word windows stepping by {MAX_UNIT_WORDS - UNIT_OVERLAP} "
            f"words, so the same alignment is seen again in a neighbouring window. The "
            f"records of a group differ only in which window pair they came from — on the "
            f"i side, the j side, or both. Grouped by [dup n] below.")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}.\n")
    lines.append(
        "Columns: `chain` = matched word pairs in the single **longest** block; "
        "`words_i`/`words_j` = matched words on each side, summed over every kept block; "
        "the two are counted independently and **can differ** (blocks sit on different "
        "diagonals, so a word may pair with several partners across blocks and be "
        "de-duplicated on one side only — measured on the full sweep, not on this corpus: "
        "21 of 295 replayed records, 7%); `chain` counts matched **pairs** in the "
        "longest block, so unlike those two it is **the same on both sides** (a block is a "
        "strictly monotone diagonal pairing) — ordering by `chain` is not one-sided; "
        "`gap_i`/`gap_j` = non-matching words inside the reported extent on "
        "that side (`span − words` for that side; `–` means the record predates the "
        "`matched_words_j` field, which is the case for the released full sweep); "
        "`blocks` = how many "
        "blocks survived the filter; `score` = TF-IDF cosine of the unit pair (candidate "
        "selection only — it does **not** rank these tables); `span_i`/`span_j` = the full "
        "extent of the match on each side (first→last matched word), in **unit-local** word "
        "positions — the `[dup n]` section below uses absolute work positions instead.\n")
    lines.append(
        "The invariants, so the columns can be checked against each other: "
        "`span_i = words_i + gap_i` and `span_j = words_j + gap_j`; `words_i <= span_i` and "
        "`words_j <= span_j` always; and `chain = words_i = words_j` only when there is "
        "**exactly one** block (with several, `chain <= words_i` and `chain <= words_j`). A block is *not* necessarily contiguous — "
        "adjacent runs are fused across gaps of up to `n_out` words — so a single block can "
        "still have `gap > 0`, which is why `span > words` on a `blocks = 1` row is not an "
        "error. The tables are ordered by `chain`, as in the production sweep, so a record "
        "leading on `words_i` or `score` need not be first.\n")

    # Szűrés a report-küszöbre + szerző-közi/intra-szerző szétválasztás.
    # A bontás a SZŰRT halmazon készül, ezért a darabszámoknak a küször feletti
    # részhalmazt kell összeadniuk — ezt a kiírás mostantól explicit módon
    # megadja (korábban a nyers „5 total" mellett „4 + 0" szerepelt, ami
    # aggregációs hibának látszott, holott a `chain >= min_chain` szűrő működött).
    filt = [m for m in matches if m["chain_len"] >= thr]
    cross = [m for m in filt if m["author_i"] != m["author_j"]]
    intra = [m for m in filt if m["author_i"] == m["author_j"]]
    n_cross_all = sum(1 for m in matches if m["author_i"] != m["author_j"])
    n_intra_all = len(matches) - n_cross_all
    cross.sort(key=lambda m: m["chain_len"], reverse=True)
    intra.sort(key=lambda m: m["chain_len"], reverse=True)

    if not filt:
        lines.append("_No matches above the report threshold._")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    n_below = len(matches) - len(filt)
    lines.append(
        f"Breakdown (all {len(matches)} matches): "
        f"{n_cross_all} cross-author + {n_intra_all} intra-author = {len(matches)}.")
    mw = "match" if len(filt) == 1 else "matches"
    lines.append(
        f"Shown in the tables below: the **{len(filt)}** {mw} with chain >= "
        f"{thr} — {len(cross)} cross-author, {len(intra)} intra-author"
        + (f"; {n_below} {'match falls' if n_below == 1 else 'matches fall'} "
           f"below the threshold and {'is' if n_below == 1 else 'are'} not listed.\n"
           if n_below else ".\n"))
    # Nevezők: mindkét sor ugyanarra a halmazra vonatkozik (a küszöb feletti
    # rekordok), és mellette áll a teljes halmazé — korábban az egyik a
    # szűrtre, a másik a nullára hivatkozott, ami olvasáskor félrevezetett.
    lines.append(f"**Cross-author:** {len(cross)} of the {len(filt)} records at or above "
                 f"the threshold ({n_cross_all} of {len(matches)} overall) — different "
                 f"authors.  ")
    n_auth = Counter(w.get("author") for w in works)
    if n_intra_all == 0 and max(n_auth.values(), default=0) < 2:
        lines.append(f"**Intra-author:** not applicable — each author contributes one "
                     f"built work, so no same-author pair exists in this corpus.\n")
    else:
        lines.append(f"**Intra-author:** {len(intra)} of the {len(filt)} records at or "
                     f"above the threshold ({n_intra_all} of {len(matches)} overall) — "
                     f"same author, two works: the author's own reused material or "
                     f"shared apparatus.\n")

    def _emit_table(ms: list[dict], n: int) -> None:
        """Egy MD-tábla (fejléc + n sor) a `lines`-ba."""
        rows = [_md_row(m, 70, marks.get(id(m), "")) for m in ms[:n]]
        _assert_table_shape(_TABLE_HEAD, _TABLE_RULE, rows, "correspondence table")
        lines.append(_TABLE_HEAD)
        lines.append(_TABLE_RULE)
        for r in rows:
            lines.append(r)
        lines.append("")

    # --- Szerző-közi: globális top + kronológiai era-pair bontás ---
    if cross:
        lines.append(f"## Cross-author top correspondences (ordered by chain, top {top})\n")
        # A rendezés `chain_len` szerinti (mint a produkciós sweepben), de a
        # `chain_len` csak a leghosszabb blokk szószáma — egy több blokkból álló
        # rekord lehet összesítésben erősebb.  Ha az élen álló nem az élen áll a
        # `words`/`score` szerint sem, azt itt kimondjuk, hogy a tábla ne
        # sugalljon olyan rangsort, amit az adat nem támaszt alá.
        head = cross[0]
        by_words = max(cross, key=lambda m: m["matched_words"])
        by_score = max(cross, key=lambda m: m["score"])
        # A címkék a tábla tényleges oszlopnevei (`words_i`), különben a
        # szöveg olyan oszlopra hivatkozna, ami a fejlécben nem szerepel.
        diff = [n for n, c in (("words_i", by_words), ("score", by_score))
                if c is not head]
        if diff:
            champs = {id(c) for c in (by_words, by_score) if c is not head}
            def _blk(m):
                n = m.get("n_chained")
                return (f"{n} block" + ("" if n == 1 else "s")) if n else "blocks n/a"
            lines.append(
                f"Note: the first row is **not** the strongest record by "
                f"{' or '.join('`' + d + '`' for d in diff)}. The sweep orders by `chain` "
                f"(the longest single block), which is not the same as total evidence: ")
            seen: set = set()
            for m in (by_words, by_score):
                if m is head or id(m) in seen:
                    continue
                seen.add(id(m))
                lines.append(
                    f"`{m['ref_i']}` × `{m['ref_j']}` — {m['matched_words']} matched words, "
                    f"{_blk(m)}, score {m['score']:.4f} — against the first row's "
                    f"{head['matched_words']} words, {_blk(head)}, score {head['score']:.4f}.  ")
            if len(champs) == 2:
                lines.append("(Two different records hold those two leads.)  ")
            lines.append("Both orders are defensible; the tables show every metric so the "
                         "reader can re-rank.\n")
        else:
            lines.append("")
        # A fő tábla is a `_emit_table`-en menjen át: korábban ez a hely
        # közvetlenül fűzte be a fejlécet és az elválasztót, így pont az a
        # tábla maradt ellenőrzés nélkül, amit a bíráló olvas.
        _emit_table(cross, top)

        if ovl:
            # Egyszeri indexelés: kulcs -> rekordok, és a csoportokban szereplő
            # rekordok azonosítói (hogy a „separate passage" lista ne ismételje
            # meg a többi csoport tagjait, és ne legyen O(csoport x rekord)).
            by_key: dict = defaultdict(list)
            for m in matches:
                by_key[(m["work_i"], _abs_span(m["ref_i"], m["word_range_i"])[0],
                        m["work_j"], _abs_span(m["ref_j"], m["word_range_j"])[0])].append(m)
            grouped_ids = {id(m) for g in ovl for m in g["items"]}
            lines.append("### Records that re-report the same passage ([dup n] groups)\n")
            lines.append(
                "One continuous parallel recorded once per overlapping window pair. "
                "Ranges below are in **absolute** word positions within the work (unlike "
                "the `span_*` columns above, which are unit-local), so the overlap is "
                "visible directly.\n")
            for gi, g in enumerate(ovl, 1):
                wi, ui, wj, uj = g["key"]
                lines.append(f"**[dup {gi}]** — `{wi}` {ui} × `{wj}` {uj}\n")
                # Melyik oldal ablaka tér el a csoporton belül? (A demóban mindkét
                # csoportnál a j-oldali; általában bármelyik lehet.)
                sides = []
                if len({m["ref_i"] for m in g["items"]}) > 1:
                    sides.append("i")
                if len({m["ref_j"] for m in g["items"]}) > 1:
                    sides.append("j")
                if sides:
                    lines.append(f"Differing window: **{' and '.join(sides)} side**\n")
                # Csökkenő chain — ugyanaz a sorrend, mint a táblákban.
                for m in sorted(g["items"], key=lambda m: -m["chain_len"]):
                    # `n_chained` csak az újabb rekordokban van; a régi (kiadott)
                    # NDJSON-ból hiányzik — ilyenkor `n/a`, nem tippelünk.
                    nb = m.get("n_chained")
                    blk = f"{nb} block" + ("" if nb == 1 else "s") if nb else "blocks n/a"
                    lines.append(
                        f"- `{m['ref_i']}` × `{m['ref_j']}` — chain {m['chain_len']}, "
                        f"{m['matched_words']} words, {blk}, "
                        f"gap {_gap_words(m, 'i')}/{_gap_words(m, 'j')}, "
                        f"score {m['score']:.4f}")
                lines.append(
                    f"- merged extent: i {g['i'][0]}–{g['i'][1]} ({g['i'][1]-g['i'][0]+1} "
                    f"words), j {g['j'][0]}–{g['j'][1]} ({g['j'][1]-g['j'][0]+1} words) — "
                    f"one passage, {len(g['items'])} records.")
                # Ugyanazon a unit-páron, de a csoporton KÍVÜL eső rekordok: ezek
                # külön passzusok, és eddig egyáltalán nem jelentek meg a
                # jelentésben (ha a küszöb alatt maradtak).  A szomszédosságuk
                # filológiailag informatív: ugyanaz a forrás-hely tér vissza
                # később a kommentárban.
                # Ugyanazon a unit-páron álló, de egyik csoportba sem tartozó
                # rekordok.  A KÖZELIEKET kiírjuk (a Plató-oldal szinte folytonos,
                # és a visszatérés ugyanahhoz a lemmához filológiailag informatív);
                # a távoliakat csak megszámoljuk, különben a jelentés szétesik.
                in_any = grouped_ids
                others = []
                for m in by_key.get(g["key"], ()):
                    if id(m) in in_any:
                        continue
                    ilo, ihi = _abs_span(m["ref_i"], m["word_range_i"])[1:]
                    jlo, jhi = _abs_span(m["ref_j"], m["word_range_j"])[1:]
                    # A KÖZTES szavak száma (nem indexkülönbség): a 109 → 113
                    # három szót (110, 111, 112) hagy ki, nem négyet — a `gap_*`
                    # oszlopok is darabszámot adnak, így ez konzisztens.
                    between = max(0, max(g["i"][0] - ihi - 1, ilo - g["i"][1] - 1))
                    others.append((between, -m["chain_len"], m, ilo, ihi, jlo, jhi))
                # MINDEN ugyanide tartozó rekordot NÉVVEL írunk ki, a közelieket
                # is és a távoliakat is: ugyanaz a rekord két csoport alatt is
                # szerepelhet, és a névtelen „N further passages" alak nem
                # ellenőrizhető vissza.  Darabszám-plafon csak a nagyon termékeny
                # unit-párok ellen.
                # Kulcs szerint rendezünk: a tuple-összehasonlítás azonos
                # `between`/`chain` esetén a dict-eket hasonlítaná (TypeError).
                others.sort(key=lambda x: (x[0], x[1]))
                for between, _n, m, ilo, ihi, jlo, jhi in others[:MAX_NAMED_OTHERS]:
                    below = "" if m["chain_len"] >= thr else " (below the report threshold)"
                    lines.append(
                        f"- *separate passage on the same work pair:* `{m['ref_i']}` × "
                        f"`{m['ref_j']}` — chain {m['chain_len']}, {m['matched_words']} "
                        f"words, i {ilo}–{ihi} / j {jlo}–{jhi}{below}; {between} "
                        f"{'word' if between == 1 else 'words'} between this group's "
                        f"i-extent and this record")
                if len(others) > MAX_NAMED_OTHERS:
                    rest = len(others) - MAX_NAMED_OTHERS
                    lines.append(
                        f"- and {rest} further "
                        f"{'passage' if rest == 1 else 'passages'} on this work pair, "
                        f"each at least {others[MAX_NAMED_OTHERS][0]} words away on the "
                        f"i side (nearest first, listed up to {MAX_NAMED_OTHERS}).")
                lines.append("")

        by_era = defaultdict(list)
        for m in cross:
            key = (m["era_i"], m["era_j"])
            if ERA_RANK.get(m["era_i"], 9) > ERA_RANK.get(m["era_j"], 9):
                key = (m["era_j"], m["era_i"])
            by_era[key].append(m)

        lines.append("## Cross-author by chronological layer (era-pair)\n")
        # FONTOS: itt nem `return`-nel lépünk ki — a függvény végén van a
        # `path.write_text()`, és egy korai `return` némán elhagyta volna a
        # fájlt (a hívó pedig sikeresnek hitte a futást).
        populated = [(ea, eb) for ea, eb in era_pairs if by_era.get((ea, eb))]
        if len(populated) == 1:
            # Egyetlen feltöltött réteg-pár mellett a tábla szó szerint
            # megismételné a fenti top-táblát — ilyenkor csak a tényt közöljük.
            ea, eb = populated[0]
            n = len(by_era[(ea, eb)])
            lines.append(
                f"Only one era pair is populated in this corpus: **{ea} → {eb}** — "
                f"{n} {'match' if n == 1 else 'matches'}, all of them listed in the table "
                f"above, so no separate layer breakdown is printed.\n")
        else:
            for ea, eb in era_pairs:
                ms = by_era.get((ea, eb), [])
                if not ms:
                    continue
                ms_sorted = sorted(ms, key=lambda m: m["chain_len"], reverse=True)[:top]
                if ea != eb:
                    label = f"{ea} → {eb}"
                elif ea == "ancient_classical":
                    # Az `ancient_classical` EGY gyűjtőréteg (ókortól a későantikig,
                    # vö. corpus_manifest.yaml): a Platónt (i. e. 4. sz.) és Prokloszt
                    # (i. sz. 5. sz.) is ide sorolja, ezért a „(intra-era)" címke
                    # félrevezető — a két oldal ~900 évre van egymástól.
                    label = (f"{ea} (control-corpus layer, both sides — "
                             f"antiquity to late antiquity)")
                else:
                    label = f"{ea} (intra-era)"
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
    ap.add_argument("--koni-root", default=DEFAULT_KONI_ROOT,
                    help="opcionális: szomszédos KONI checkout (from app import "
                         "flame_pure). Alapból a csomagolt engine/flame/ töltődik.")
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
        # Ugyanaz az öt kulcs, mint a sweep-ágban: a riport fejléc így mindkét
        # úton önkonzisztens. FIGYELEM: ezek a CLI-defaultok, nem a hajdani
        # sweep tényleges értékei (a max_candidates default 4000, a naplózott
        # sweep viszont 1000-rel futott) — a fejléc csak azt rögzíti, ami a
        # jelenlegi rendereléshez tartozik.
        kw = {"ngram": args.ngram, "n_out": args.n_out,
              "fuzz_threshold": args.fuzz, "min_chain_words": args.min_chain,
              "max_candidates": args.max_candidates}
        write_markdown(matches, works, md_p, args.top, kw, args.report_min_chain)
        print(f"[REPORT-ONLY] {md_p} újragenerálva "
              f"({len(matches)} match, küsz chain>={args.report_min_chain}).")
        return

    # --- Motor ---
    try:
        flame = load_flame(args.koni_root)  # None -> csomagolt engine/flame/
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