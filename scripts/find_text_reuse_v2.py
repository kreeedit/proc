#!/usr/bin/env python3
"""
scripts/find_text_reuse_v2.py
=============================

A javított sweep-harness. Mit és miért javít: `../PIPELINE_V2.md`.

Mit csinál másképp a befagyasztott `scripts/find_text_reuse.py`-hoz képest
--------------------------------------------------------------------------
1. **`flame_pure_v2`-t használ** (szimmetrikus jelöltszűrés + opcionális
   korpuszszintű IDF + `matched_words_j` + diagnosztika), nem a `flame_pure`-t.
2. **Korpuszszintű IDF-et épít** a sweep ELŐTT, és minden párnak azt adja át.
   A `flame_pure` páronként számolja az IDF-et, ezért a `score` művpáronként
   más skálán áll; a `filter_by_wp.py` viszont abszolút küszöbként használja.
   Ezzel a `score` a teljes sweepen belül összehasonlíthatóvá válik.
3. **Apparátus-tokeneket szűr** a `_clean_text`-ben: a csupasz számokat és a
   latin betűs tokeneket a többségében görög szegmensekből. A Proklos
   *In Rempublicam* szövegébe a Teubner-apparátus soron belül van beszőve —
   a mintán a tisztítás UTÁN is 2,4% csupasz szám és 4,4% latin token maradt,
   és a `fuzz=0.75` a számokat egymáshoz illeszti (103~104 = 0,833).
4. **Rögzíti a futás paramétereit** egy `*.meta.json` sidecarba, és
   **figyelmeztet**, ha a motor csendben levágott egy paramétert, ha hiányzik
   a BPE modell, vagy ha a `max_candidates` plafon fogott.

Amit NEM változtat: az ablakozást (140 szó, 115 lépés), a Levenshtein-
predikátumot, a blokk-építést és a `core >= ngram AND n >= min_chain_words`
szűrőt. Az audit ezeket rendben találta.

FONTOS — a cikk számai
----------------------
Ez a szkript egyetlen kiadott artefaktumot sem ír felül. A `--out-dir`
alapértelmezése `logs/v2/`, nem `logs/`. A cikk számai csak akkor változnak,
ha valaki a TLG-alapú korpusszal újrafuttatja a 406 páros sweepet — az a
korpusz nincs ebben a kiadásban.

Használat:
  python3 scripts/find_text_reuse_v2.py                       # teljes sweep
  python3 scripts/find_text_reuse_v2.py --only 9019.001,0732.004
  python3 scripts/find_text_reuse_v2.py --no-corpus-idf       # v1 score-skála
  python3 scripts/find_text_reuse_v2.py --no-apparatus-strip  # v1 tisztítás
  python3 scripts/demo_v2.py                                  # a két mintán
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "engine"
for _p in (str(ENGINE_DIR),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# A befagyasztott harness a windowing, a riport-írók és a zajszűrő regexek
# forrása — azokat nem duplikáljuk, csak azt írjuk újra, ami változik.
import find_text_reuse as H  # noqa: E402
from flame import bpe_pure_v2, flame_pure_v2  # noqa: E402

MANIFEST = H.MANIFEST
CORPUS = H.CORPUS
DEFAULT_OUT_DIR = ROOT / "logs" / "v2"
ERA_RANK = H.ERA_RANK
MAX_UNIT_WORDS = H.MAX_UNIT_WORDS
UNIT_OVERLAP = H.UNIT_OVERLAP


# ---------------------------------------------------------------------------
# (C2) Apparátus-token szűrés
# ---------------------------------------------------------------------------

# Csupasz szám és tisztán latin betűs token. A `(?<!\w)`/`(?!\w)` a `\b`-nél
# szigorúbb: a `12a`-t vagy a `Pl.`-t nem vágja ketté, csak a teljes tokent
# találja el.
_DIGIT_TOKEN_RE = re.compile(r"(?<!\w)\d+(?!\w)")
_LATIN_TOKEN_RE = re.compile(r"(?<!\w)[A-Za-z]+(?!\w)")
_GREEK_CHAR_RE = re.compile(r"[Ͱ-Ͽἀ-῿]")


def is_greek_segment(t: str, min_share: float = 0.5) -> bool:
    """Igaz, ha a tokenek legalább `min_share` hányada tartalmaz görög betűt.

    Ez a kapcsoló teszi biztonságossá a latin tokenek törlését: a korpusz
    latin nyelvű részein (ha lesz ilyen) a szűrő egyszerűen nem fut le."""
    ws = H._MILESTONE_RE.sub(" ", t)
    ws = re.findall(r"\b\w+\b", ws)
    if not ws:
        return False
    return sum(1 for w in ws if _GREEK_CHAR_RE.search(w)) / len(ws) >= min_share


def strip_apparatus_tokens(t: str) -> str:
    """Csupasz számok és latin betűs tokenek eltávolítása görög szövegből.

    A Kroll-féle Teubner-apparátus a `tlg4036.tlg001` (Proklos, *In
    Rempublicam*) futó szövegébe van beszőve, nem külön mezőben áll:
    `… ἦθος [p. 605a], ἀπανοὐδετέρα 3 6 nempe ἄλλῃ 7 ἔχει 11 cf. Δ 104 …`.
    A befagyasztott `_clean_text` ebből a mintán 87 tokent visz el 10 802-ből,
    és a 255 csupasz számból egyet sem."""
    if not is_greek_segment(t):
        return t
    return _LATIN_TOKEN_RE.sub(" ", _DIGIT_TOKEN_RE.sub(" ", t))


def clean_text(t: str, strip_apparatus: bool = True) -> str:
    """A befagyasztott `_clean_text` + (opcionálisan) az apparátus-tokenek."""
    t = H._clean_text(t)
    if strip_apparatus and t:
        t = H._WS.sub(" ", strip_apparatus_tokens(t)).strip()
    return t


# ---------------------------------------------------------------------------
# Unit-építés (a befagyasztott logika, a javított tisztítással)
# ---------------------------------------------------------------------------

def build_units(json_path: Path, tlg_id: str, group_by: str = "page",
                strip_apparatus: bool = True) -> list[dict]:
    """Ugyanaz a csoportosítás és ablakozás, mint `H.build_units`-ban
    (`H._window_units` újrahasznosítva) — csak a tisztítás más.

    FIGYELEM: a tisztítás megrövidíti a szóáramot, ezért MINDEN `#k`
    ablakcímke és minden `word_range` elmozdul az eredeti futáshoz képest.
    A mintán a Proklos-unit 95 ablakról 92-re csökken."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segs = data.get("segments", []) or []

    if group_by == "segment":
        raw = [{"label": s.get("ref", ""),
                "text": clean_text(s.get("text", ""), strip_apparatus)}
               for s in segs if s.get("text")]
    else:
        groups: "OrderedDict[tuple, list[str]]" = OrderedDict()
        for s in segs:
            txt = s.get("text")
            if not txt:
                continue
            ch = s.get("chapter") or ""
            pg = s.get("page") or ""
            groups.setdefault((ch, pg) if pg else (ch, ""), []).append(
                clean_text(txt, strip_apparatus))
        raw = []
        for (ch, pg), texts in groups.items():
            label = f"{ch}/{pg}" if pg else f"{ch}/"
            raw.append({"label": label.strip(), "text": " ".join(texts).strip()})

    raw = [u for u in raw if u["text"]]
    return H._window_units(raw)


# ---------------------------------------------------------------------------
# Futás-diagnosztika és provenance
# ---------------------------------------------------------------------------

def check_run_config(kw: dict, corpus_idf: bool, strip_apparatus: bool) -> dict:
    """A csendes viselkedések kimondása a sweep ELŐTT.

    A `flame_pure` nem naplóz semmit: a határon kívüli paramétereket csendben
    levágja, a hiányzó BPE modellt üres merge-listával helyettesíti. Egyik sem
    változtat a találathalmazon (a BPE csak a `score`-t mozdítja), de mindkettő
    értelmezhetetlenné teszi a riportot, ha észrevétlen marad."""
    warn = []
    trained = bool(bpe_pure_v2.load())
    if not trained:
        warn.append("nincs betöltött BPE modell → a `score` nem a jelentett "
                    "futás skáláján áll (a találathalmaz változatlan)")
    if not corpus_idf:
        warn.append("--no-corpus-idf: az IDF páronként számolódik, a `score` "
                    "MŰVPÁROK KÖZÖTT NEM hasonlítható össze")
    if not strip_apparatus:
        warn.append("--no-apparatus-strip: a Proklos-apparátus bent marad "
                    "(a mintán 2,4% csupasz szám, 4,4% latin token)")
    for w in warn:
        print(f"  [FIGYELEM] {w}")
    return {"bpe_trained": trained,
            "bpe_merges": len(bpe_pure_v2.load()),
            "bpe_stop_subwords": bpe_pure_v2.stop_size(),
            "corpus_idf": corpus_idf,
            "apparatus_strip": strip_apparatus,
            "requested": dict(kw)}


def write_run_meta(meta: dict, works: list[dict], path: Path) -> None:
    """A futás paraméterei a találatok MELLÉ, sidecar fájlba.

    A kiadott `text_reuse_matches.ndjson` egyetlen rekordja sem hordoz
    futás-metaadatot, ezért a `max_candidates` értékét csak közvetve — a
    rekord/pár eloszlás telítési nyomából — lehetett visszanyerni. Ez a
    sidecar additív: a rekordok mezőit nem érinti."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(meta)
    payload["generated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    payload["engine"] = "flame_pure_v2"
    payload["engine_sha256"] = hashlib.sha256(
        (ENGINE_DIR / "flame" / "flame_pure_v2.py").read_bytes()).hexdigest()
    payload["frozen_engine_sha256"] = hashlib.sha256(
        (ENGINE_DIR / "flame" / "flame_pure.py").read_bytes()).hexdigest()
    payload["harness_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()).hexdigest()
    payload["corpus_ref"] = H.corpus_ref()
    payload["works"] = [{"tlg_id": w["tlg_id"], "era": w.get("era", ""),
                         "author": w.get("author", "")} for w in works]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"  provenance → {path}")


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

def run_sweep(works: list[dict], kw: dict, limit_pairs: int | None,
              units_cache: dict, corpus_index: dict | None = None) -> tuple:
    """All-pairs (i<j) összehasonlítás a javított motorral.

    A `corpus_index` minden párnak ugyanazt a szótárat, hash-bázist és IDF-et
    adja, ezért a kimenő `score` a teljes sweepen belül összehasonlítható."""
    compare_iter = flame_pure_v2.compare_iter
    pairs = list(itertools.combinations(range(len(works)), 2))
    if limit_pairs is not None:
        pairs = pairs[:limit_pairs]

    matches: list[dict] = []
    diag = {"cap_hit_pairs": [], "clamped": {}, "units_truncated": 0}
    t0 = time.time()
    for n, (i, j) in enumerate(pairs, 1):
        wi, wj = works[i], works[j]
        ui, uj = units_cache[wi["tlg_id"]], units_cache[wj["tlg_id"]]
        pair_t0 = time.time()
        n_pair = 0
        for ev in compare_iter(ui, uj, corpus_index=corpus_index, **kw):
            if ev.get("t") == "meta":
                if ev.get("cap_hit"):
                    diag["cap_hit_pairs"].append(
                        [wi["tlg_id"], wj["tlg_id"],
                         ev["n_candidates_before_cap"], ev["n_candidates"]])
                if ev.get("clamped"):
                    diag["clamped"] = ev["clamped"]
                diag["units_truncated"] += ev.get("units_truncated", 0)
                continue
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
                # A motor mostantól maga adja — nem a `matched_j` map
                # újraszámolásából jön (a motor korábban eldobta).
                "matched_words_j": p.get("matched_words_j", 0),
                "n_chained": p.get("n_chained", 0),
                "ref_i": p.get("label_i", ""), "ref_j": p.get("label_j", ""),
                "word_range_i": p.get("word_range_i", ""),
                "word_range_j": p.get("word_range_j", ""),
                "snippet_i": p.get("snippet_i", ""),
                "snippet_j": p.get("snippet_j", ""),
            })
            n_pair += 1
        print(f"  [{n}/{len(pairs)}] {wi['tlg_id']} × {wj['tlg_id']}  "
              f"units=({len(ui)},{len(uj)})  matches={n_pair}  "
              f"{time.time()-pair_t0:.1f}s  (elapsed {time.time()-t0:.0f}s)")
    return matches, diag


def report_diagnostics(diag: dict, kw: dict) -> None:
    """Amit a befagyasztott harness sosem mondott el a futásról."""
    if diag["clamped"]:
        for k, v in diag["clamped"].items():
            print(f"  [FIGYELEM] {k}={v['requested']} → a motor "
                  f"{v['used']}-t használt (csendes clamp)")
    if diag["units_truncated"]:
        print(f"  [FIGYELEM] {diag['units_truncated']} unit hosszabb "
              f"{flame_pure_v2.CAP_WORDS} szónál — a motor csonkította")
    hits = diag["cap_hit_pairs"]
    if hits:
        worst = max(hits, key=lambda h: h[2])
        print(f"  [FIGYELEM] a max_candidates={kw['max_candidates']} plafon "
              f"{len(hits)} páron fogott; a legrosszabb {worst[0]}×{worst[1]}: "
              f"{worst[2]} jelöltből {worst[3]} értékelve "
              f"({100*worst[3]/worst[2]:.0f}%). A többi jelölt SOHA nem jutott "
              f"illesztésig — ez recall-veszteség, nem finomhangolás.")
    else:
        print(f"  [ok] a max_candidates={kw['max_candidates']} plafon "
              f"egyetlen páron sem fogott")


# ---------------------------------------------------------------------------
# Fő
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Javított szövegegyezés-keresés (FLAME v2) — l. PIPELINE_V2.md")
    ap.add_argument("--only", help="vesszős tlg_id részhalmaz")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                    help=f"kimeneti könyvtár (default: "
                         f"{DEFAULT_OUT_DIR.relative_to(ROOT)} — a kiadott "
                         f"logs/ NEM íródik felül)")
    ap.add_argument("--group-by", choices=["page", "segment"], default="page")
    ap.add_argument("--ngram", type=int, default=4)
    ap.add_argument("--n-out", type=int, default=1)
    ap.add_argument("--fuzz", type=float, default=0.75)
    ap.add_argument("--min-chain", type=int, default=2)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--limit-pairs", type=int, default=None)
    ap.add_argument("--max-candidates", type=int, default=4000,
                    help="páronkénti jelölt-plafon (default 4000). A jelentett "
                         "futás 1000-rel ment; éles méretű párokon a jelöltszám "
                         "3 617–11 574, tehát 1000 a jelöltek 72–91%%-át elvágja.")
    ap.add_argument("--no-corpus-idf", action="store_true",
                    help="az IDF páronként számolódjon (a v1 viselkedése) — a "
                         "`score` így művpárok között NEM hasonlítható össze")
    ap.add_argument("--no-apparatus-strip", action="store_true",
                    help="a csupasz számok és latin tokenek maradjanak bent "
                         "(a v1 viselkedése)")
    ap.add_argument("--report-min-chain", type=int, default=6)
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    out_dir = Path(args.out_dir).resolve()
    strip_apparatus = not args.no_apparatus_strip
    corpus_idf = not args.no_corpus_idf

    # A kiadás sem a korpuszt, sem a manifestet nem tartalmazza (TLG-alapú,
    # nem redisztributálható) — ezt diagnosztizálható üzenetben mondjuk meg,
    # ne traceback-ben.
    if not MANIFEST.is_file():
        raise SystemExit(
            f"[HIBA] nincs korpusz-manifest: {MANIFEST}\n"
            f"       Ez a kiadás nem tartalmazza a `corpus_manifest.yaml`-t és a\n"
            f"       `data/corpus/`-t (TLG-alapú, nem redisztributálható), ezért a\n"
            f"       teljes sweep innen nem futtatható.\n"
            f"       Amit futtatni tudsz a csomagolt mintákon:\n"
            f"         python3 scripts/demo_v2.py       # a javított pipeline\n"
            f"         python3 engine/demo.py           # a befagyasztott\n"
            f"       Lásd: PIPELINE_V2.md.")
    manifest = H.load_manifest()
    works = H.collect_built_works(manifest, only)
    if len(works) < 2:
        print("Kevesebb mint 2 felépített mű — nincs mit összehasonlítani.")
        return

    kw = {"ngram": args.ngram, "n_out": args.n_out,
          "fuzz_threshold": args.fuzz, "min_chain_words": args.min_chain,
          "max_candidates": args.max_candidates}

    print("=" * 78)
    print(f"FLAME v2 sweep — {len(works)} mű, "
          f"{len(works)*(len(works)-1)//2} pár (all-pairs, i<j)")
    print(f"engine=flame_pure_v2  ngram={args.ngram}  n_out={args.n_out}  "
          f"fuzz={args.fuzz}  min_chain={args.min_chain}  "
          f"max_candidates={args.max_candidates}")
    print(f"corpus_idf={corpus_idf}  apparatus_strip={strip_apparatus}")
    print("=" * 78)
    run_meta = check_run_config(kw, corpus_idf, strip_apparatus)

    print("\n[Unitok] építés ...")
    t0 = time.time()
    units_cache = {w["tlg_id"]: build_units(w["json_path"], w["tlg_id"],
                                            args.group_by, strip_apparatus)
                   for w in works}
    print(f"  {sum(len(u) for u in units_cache.values())} unit, "
          f"{time.time()-t0:.1f}s")

    corpus_index = None
    if corpus_idf:
        print("\n[Korpusz-index] egyszeri IDF a teljes korpuszon ...")
        t0 = time.time()
        corpus_index = flame_pure_v2.build_corpus_index(
            [units_cache[w["tlg_id"]] for w in works],
            ngram=args.ngram, n_out=args.n_out)
        print(f"  {corpus_index['n_works']} mű, {corpus_index['n_units']} unit, "
              f"vocab {len(corpus_index['vocab'])}, "
              f"{len(corpus_index['idf'])} hash, {time.time()-t0:.1f}s")
        run_meta["corpus_index"] = {
            "n_works": corpus_index["n_works"], "n_units": corpus_index["n_units"],
            "vocab_size": len(corpus_index["vocab"]),
            "idf_size": len(corpus_index["idf"])}

    print("\n[Sweep] all-pairs ...")
    t0 = time.time()
    matches, diag = run_sweep(works, kw, args.limit_pairs, units_cache,
                              corpus_index)
    dt = time.time() - t0
    print(f"\n[Sweep] kész: {len(matches)} match, {dt:.1f}s")
    report_diagnostics(diag, kw)

    ndjson_p = out_dir / "text_reuse_matches.ndjson"
    tsv_p = out_dir / "text_reuse_matches.tsv"
    md_p = out_dir / "text_reuse_report.md"
    H.write_ndjson(matches, ndjson_p)
    H.write_tsv(matches, tsv_p)
    H.write_markdown(matches, works, md_p, args.top, kw, args.report_min_chain)
    run_meta["diagnostics"] = {
        "n_matches": len(matches), "elapsed_s": round(dt, 1),
        "cap_hit_pairs": diag["cap_hit_pairs"][:50],
        "n_cap_hit_pairs": len(diag["cap_hit_pairs"]),
        "units_truncated": diag["units_truncated"]}
    write_run_meta(run_meta, works,
                   out_dir / "text_reuse_matches.meta.json")
    print(f"\nKimenetek ({out_dir}):")
    print(f"  {ndjson_p.name}   {len(matches)} sor")
    print(f"  {tsv_p.name}      {len(matches)} sor")
    print(f"  {md_p.name}       Markdown jelentés")


if __name__ == "__main__":
    main()
