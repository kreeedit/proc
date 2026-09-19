"""Flame text-reuse engine — pure Python, TWO-PHASE, zero dependencies.

DOCSTRING-ONLY FORK of `flame_pure.py` (class A of the 2026-09-19 audit).
========================================================================
Every executable statement is byte-for-byte the statement of
`flame_pure.py`; only docstrings and comments differ.  **No reported metric
changes**: the record sets, `chain_len`, `matched_words`, `score` and the
emission order are identical, and `tests/test_flame.py` asserts that the two
modules compile to the same AST once docstrings are stripped.

`flame_pure.py` is byte-identical to its KONI source and must stay so, which
is why the corrections below could not be applied there.  This file is not
imported by `demo.py`, `find_text_reuse.py` or the reported run — it exists so
the corrected description lives next to the code rather than only in
`AUDIT.md`.

What the engine actually does
-----------------------------
Phase 1 (candidate scoring): BPE subword → leave-n-out rolling hash → TF-IDF →
cosine. The IDF is recomputed **per `compare_iter` call**, from the units of
that call only, so the resulting `score` is comparable *within* one call and
**not** between calls — i.e. not between work pairs of a sweep.  The cosine is
carried on the record but reads nowhere: the candidate order is the shared
word-bigram count, and the similarity gate defaults to `None` → `0.0`, which
every non-negative score passes.  Phase 1 therefore neither ranks nor gates;
without the BPE model the match set is unchanged and only `score` moves.

Phase 2 (local matching): cleaned text → stripGreek-normalized WORD lists →
pure-Python Levenshtein-tolerant matching blocks
(`levenshtein_ratio(w1, w2) >= fuzz_threshold`) → gap-fusing up to `n_out`
non-matching words (n_out=0 = strict contiguous) → STRICT filters (longest
contiguous core >= ngram AND total matched words >= min_chain_words).

The word lists come from `re.findall(r'\\b\\w+\\b')` in **both** branches: with
a trained BPE model via `bpe_pure.tokenize_words()`, without one via the
regex here.  The two branches differ only in `subs` (the cosine's input).

Matching runs DIRECTLY on the word lists, so hit indices ARE real word
indices → the frontend green-verbatim / brown-bridge highlights land on the
actual words with zero visual drift.  Short particle matches (τε, καὶ, δὲ) are
killed by **`core >= ngram` alone**: `fuzz_threshold=0.75` *admits* them
(τε~τε, δε~τε and το~τω all pass), and what removes them is the requirement of
a contiguous run at least `ngram` words long.  Real morphological reuse across
inflections (Ionic ποταμόν ↔ Attic ποταμὸς) survives the same filter because
such runs are long enough.

`compare_iter` is **not symmetric**: `df_cap = max(40, int(0.04 * n2))` prunes
the inverted index built over `sections2` only, and side 1's bigrams carry no
frequency cap, so `compare(A, B)` and `compare(B, A)` return different match
sets.  Measured on real Greek at production scale: 3,617 vs 8,402 candidates
on the same work pair.

NO external deps — Levenshtein is hand-rolled (stdlib only): no rapidfuzz,
no numpy. NO agglomerative chaining. NO hapax/archaism.
"""
from __future__ import annotations

import itertools
import math
import re
import statistics
import unicodedata
from collections import Counter
from functools import lru_cache

from . import bpe_pure

NGRAM = 4
N_OUT = 1
MIN_CHAIN_WORDS = 2
FUZZ_THRESHOLD = 0.75
MOD = (1 << 61) - 1
CAP_WORDS = 400
CAP_SECTIONS = 20000
CHAIN_GAP = 3  # kept for reference but NOT used (chaining removed)

_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)
_WS = re.compile(r"\s+")
_MILESTONE_RE = re.compile(r"[\(\[][0-9]+[\)\]]")


def normalize(text: str) -> str:
    nf = unicodedata.normalize("NFKD", text).lower()
    return "".join(c for c in nf if not unicodedata.combining(c))


def _strip_milestones(text: str) -> str:
    return _WS.sub(" ", _MILESTONE_RE.sub("", text)).strip()


def _units(sections: list[dict]):
    """Per section: (label, orig_words, norm_words, subs, s2w).

    NOTE: `CAP_WORDS` (400) truncates every unit **silently**.  Harmless under
    `find_text_reuse.py`, whose windows are 140 words, but any other caller
    passing longer sections loses their tail without a warning.  Only `subs`
    depends on the BPE model; `orig_words` and `norm_words` — the inputs of
    candidate generation and of Phase-2 matching — are identical either way.

    orig_words:  original accented words (display + snippets, capped CAP_WORDS).
    norm_words:  stripGreek-normalized words (NFKD + drop accents + lower),
                 parallel to orig_words — Phase 2 Levenshtein matching runs on
                 these. Capped identically to orig_words (index-aligned).
    subs:        BPE subwords (stop-words filtered), parallel to s2w (Phase 1).
    s2w:         subword index -> ORIGINAL word index (no remap → zero drift).
    """
    use_bpe = bpe_pure.is_trained()
    out = []
    for s in sections[:CAP_SECTIONS]:
        text = _strip_milestones(s["text"])
        if use_bpe:
            orig, subs, s2w = bpe_pure.tokenize_words(text)
            if bpe_pure.stop_size():
                kept = [(sub, wi) for sub, wi in zip(subs, s2w)
                        if not bpe_pure.is_stop(sub)]
                subs = [k[0] for k in kept]
                s2w = [k[1] for k in kept]
        else:
            orig = _WORD_RE.findall(text)
            subs = [normalize(w) for w in orig]
            s2w = list(range(len(orig)))
        # cap by word count; keep subwords belonging to kept words
        cap = CAP_WORDS
        kept_wi = {wi for wi in range(min(len(orig), cap))}
        orig = orig[:cap]
        norm = [normalize(w) for w in orig]
        subs = [sub for k, sub in enumerate(subs) if s2w[k] in kept_wi]
        s2w = [wi for wi in s2w if wi in kept_wi]
        out.append((s["label"], orig, norm, subs, s2w))
    return out


# ---- leave-n-out rolling hash ----
def _hashes(int_tokens, base, ngram, n_out):
    if len(int_tokens) < ngram:
        return []
    if n_out <= 0:
        hashes = []
        for i in range(len(int_tokens) - ngram + 1):
            window = int_tokens[i:i + ngram]
            h = 0
            for power, val in enumerate(window):
                h = (h + val * pow(base, power, MOD)) % MOD
            hashes.append(h)
        return hashes
    keep = max(1, ngram - n_out)
    hashes = []
    for i in range(len(int_tokens) - ngram + 1):
        window = int_tokens[i:i + ngram]
        for combo in itertools.combinations(window, keep):
            h = 0
            for power, val in enumerate(combo):
                h = (h + val * pow(base, power, MOD)) % MOD
            hashes.append(h)
    return hashes


# ---- TF-IDF + cosine (Phase 1 ranking) ----
def _idf(counters: list[Counter]) -> dict:
    """Document frequencies over **the units of this call only**.

    `compare_iter` calls it as `_idf(counters1 + counters2)`, so in an
    all-pairs sweep the IDF — and therefore every `score` — is renormalized
    per work pair.  The same unit pair scores differently depending on what
    else was in the call (measured: 0.3069 with all 95 j-side units, 0.2950
    with 11 of them).  Any threshold or ranking applied to `score` **across**
    work pairs is therefore comparing quantities on different scales.
    """
    n = len(counters)
    df: Counter = Counter()
    for c in counters:
        for h in c:
            df[h] += 1
    return {h: math.log(1 + n / (1 + d)) + 1.0 for h, d in df.items()}


def _tfidf(counter: Counter, idf: dict) -> dict:
    total = sum(counter.values()) or 1
    return {h: (c / total) * idf.get(h, 0.0) for h, c in counter.items()}


def cosine(v1: dict, v2: dict) -> float:
    if not v1 or not v2:
        return 0.0
    small, large = (v1, v2) if len(v1) <= len(v2) else (v2, v1)
    dot = sum(small[h] * large[h] for h in small if h in large)
    n1 = math.sqrt(sum(x * x for x in v1.values()))
    n2 = math.sqrt(sum(x * x for x in v2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def auto_threshold(scores: list[float]) -> float:
    if len(scores) < 2:
        return 0.0
    return statistics.fmean(scores) + 1.2 * statistics.pstdev(scores)


# ---- Pure-Python Levenshtein (stdlib only: no rapidfuzz / numpy) ----
@lru_cache(maxsize=200000)
def _lev_dist(a: str, b: str) -> int:
    """Levenshtein edit distance between two normalized words (two-row DP)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1,            # deletion
                           cur[j - 1] + 1,         # insertion
                           prev[j - 1] + (ca != cb)))  # substitution
        prev = cur
    return prev[-1]


def levenshtein_ratio(a: str, b: str) -> float:
    """Similarity ratio in [0.0, 1.0]:  ``1 - dist / (len(a) + len(b))``.

    This is **not** the difflib convention (`2*M/T` over matching blocks) and
    must not be read as one: for ``'abc'`` / ``'abd'`` this returns 0.8333
    where ``difflib.SequenceMatcher.ratio()`` returns 0.6667.

    Range in practice:
      * 1.0 — identical (and, by the guard below, for two empty strings);
      * **0.5 is the floor for two strings of equal length**, not 0.0, because
        the edit distance between equal-length strings is at most that length:
        ``1 - L/(2L) = 0.5``.  0.0 is reachable only when one string is empty.

    Consequence for the production threshold ``fuzz_threshold = 0.75``: at
    equal length L the predicate passes while up to ``floor(L/2)`` letters
    differ — half the word for even L (``το ~ τω`` and ``δε ~ τε`` are exactly
    0.75), and it matches bare numerals just as readily (``103 ~ 104`` =
    0.8333), which matters wherever a critical apparatus has been spliced into
    the running text.
    """
    if not a and not b:
        return 1.0
    return 1.0 - _lev_dist(a, b) / (len(a) + len(b))


def _word_match(a: str, b: str, threshold: float) -> bool:
    """Levenshtein-tolerant word equality: True if ratio >= threshold.
    Cheap length-prune first — if the length gap alone makes the threshold
    unreachable, skip the (cached) distance computation."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    tot = la + lb
    if tot == 0:
        return True
    # best possible ratio given the length gap = 1 - |la-lb|/tot
    if abs(la - lb) / tot > (1.0 - threshold):
        return False
    return levenshtein_ratio(a, b) >= threshold


def fuzz_ratio(a: str, b: str) -> float:
    """Bridge-word fuzzy similarity, 0–100 (Levenshtein-based)."""
    if not a and not b:
        return 100.0
    return levenshtein_ratio(a, b) * 100.0


# ---- Levenshtein-tolerant matching blocks (Phase 2, word-level) ----
def _fuzzy_blocks(ni: list[str], nj: list[str],
                  threshold: float, n_out: int) -> list[dict]:
    """Find Levenshtein-tolerant matching blocks on the WORD lists.

    A block is a maximal diagonal run of word pairs (i+k, j+k) whose
    `levenshtein_ratio >= threshold`, with adjacent runs on the SAME
    diagonal fused across a gap of <= `n_out` non-matching words
    (n_out=0 ⇒ strict contiguous — no fusing).

    Because matching runs directly on the word lists, the returned
    indices ARE real word indices (no s2w conversion → zero drift).

    Each block dict:
      a, b    : first matched (i, j) word index
      n       : total matched word pairs in the (possibly fused) block
      core    : longest contiguous matched run within the block
      matches : list of (wi, wj) matched word-index pairs
      gaps    : list of (gi0, gi1, gj0, gj1) half-open internal gap spans
    """
    li, lj = len(ni), len(nj)
    if li == 0 or lj == 0:
        return []
    # match matrix (length-pruned predicate; cached distance underneath)
    M = [[_word_match(ni[i], nj[j], threshold) for j in range(lj)]
         for i in range(li)]
    blocks: list[dict] = []
    for d in range(-li + 1, lj):           # diagonal offset d = j - i
        i0 = max(0, -d)
        i1 = min(li, lj - d)
        # maximal True runs along this diagonal
        runs: list[list[int]] = []          # [start_i, length]
        i = i0
        while i < i1:
            if M[i][i + d]:
                start = i
                while i < i1 and M[i][i + d]:
                    i += 1
                runs.append([start, i - start])
            else:
                i += 1
        if not runs:
            continue
        # fuse adjacent runs on this diagonal across gaps <= n_out
        groups: list[list[list[int]]] = []
        cur = [runs[0]]
        for r in runs[1:]:
            gap = r[0] - (cur[-1][0] + cur[-1][1])
            if 0 < gap <= n_out:
                cur.append(r)
            else:
                groups.append(cur)
                cur = [r]
        groups.append(cur)
        for grp in groups:
            matches = [(s + k, s + k + d) for (s, L) in grp for k in range(L)]
            gaps = []
            for k in range(len(grp) - 1):
                a_run, b_run = grp[k], grp[k + 1]
                gi0, gi1 = a_run[0] + a_run[1], b_run[0]
                gaps.append((gi0, gi1, gi0 + d, gi1 + d))
            blocks.append({
                "a": matches[0][0], "b": matches[0][1],
                "n": len(matches),
                "core": max((L for _, L in grp), default=0),
                "matches": matches, "gaps": gaps,
            })
    return blocks


def _block_word_maps(blocks: list[dict]) -> tuple[dict, dict]:
    """{word_idx -> blockId} for the matched words on each side."""
    mi, mj = {}, {}
    for k, b in enumerate(blocks):
        for wi, wj in b["matches"]:
            mi[wi] = k
            mj[wj] = k
    return mi, mj


def _block_bridge_maps(blocks: list[dict],
                      ni: list[str], nj: list[str]) -> tuple[dict, dict]:
    """Fuzzy similarity (0–100, Levenshtein) of internal gap word spans,
    mapped to the gap word indices on each side."""
    bi, bj = {}, {}
    for b in blocks:
        for gi0, gi1, gj0, gj1 in b["gaps"]:
            gi = ni[gi0:gi1]
            gj = nj[gj0:gj1]
            if not gi and not gj:
                continue
            fuzz = round(fuzz_ratio(" ".join(gi), " ".join(gj)), 1)
            for wi in range(gi0, gi1):
                bi[wi] = fuzz
            for wj in range(gj0, gj1):
                bj[wj] = fuzz
    return bi, bj


def _snippet(words, matched, context=6):
    idxs = sorted(matched.keys())
    if not idxs:
        return "", "", 0
    lo, hi = idxs[0], idxs[-1]
    a = max(0, lo - context)
    b = min(len(words), hi + 1 + context)
    snippet = " ".join(words[a:b]).strip()
    rng = f"{lo + 1}–{hi + 1}" if hi > lo else str(lo + 1)
    return snippet, rng, len(idxs)


def _word_ngrams(words: list[str], n: int):
    """Normalized-word n-grams (tuples) used as the candidate-generation key.
    Sparse and discriminative — this is what makes recall scale to many units."""
    if len(words) < n:
        return []
    return [tuple(words[k:k + n]) for k in range(len(words) - n + 1)]


def compare_iter(sections1: list[dict], sections2: list[dict],
                 ngram: int = NGRAM, n_out: int = N_OUT,
                 min_chain_words: int = MIN_CHAIN_WORDS,
                 fuzz_threshold: float = FUZZ_THRESHOLD,
                 similarity_threshold: float | None = None,
                 min_shared: int = 3, max_candidates: int = 4000,
                 progress_every: int = 150):
    """Streaming Flame: same two-phase algorithm as compare(), but YIELDS
    events so the UI can render incrementally instead of waiting for the whole
    job. Events (dicts):
      {"t":"meta", ...}                      once, after Phase 1 setup
      {"t":"pair", "pair":{...}}             per surviving match (best first)
      {"t":"progress","done","total","found"} periodically
      {"t":"done","found","total"}           at the end

    "Strongest candidates first" means **most shared word bigrams** first, not
    highest cosine: the emission order is `ranked`, and the cosine is computed
    afterwards.  Measured on the released sweep, 331 of the 359 multi-record
    work pairs are not score-monotone in emission order.

    Two silent behaviours a caller has to know about, because the engine emits
    no warning for either:
      * the first four parameters are **clamped**, not validated —
        `ngram` to [2, 8], `n_out` to [0, 2], `min_chain_words` to >= 1,
        `fuzz_threshold` to [0.5, 1.0].  Asking for `ngram=99` silently gets 8.
      * `similarity_threshold=None` becomes **0.0**, which every score passes;
        `meta["threshold"]` reports an `auto_threshold` that is computed and
        then never used (applying it would drop 3 of the demo pair's 5
        records).
    """
    ngram = max(2, min(8, int(ngram)))
    n_out = max(0, min(2, int(n_out)))
    min_chain_words = max(1, int(min_chain_words))
    fuzz_threshold = max(0.5, min(1.0, float(fuzz_threshold)))

    u1 = _units(sections1)
    u2 = _units(sections2)
    n1, n2 = len(u1), len(u2)

    meta = {
        "t": "meta", "n1": n1, "n2": n2, "n_pairs_total": n1 * n2,
        "n_candidates": 0, "n_chosen": 0, "vocab_size": 0, "mean": 0.0,
        "threshold": 0.0, "used_threshold": 0.0, "auto_threshold_disabled": True,
        "ngram": ngram, "n_out": n_out, "min_chain_words": min_chain_words,
        "fuzz_threshold": round(fuzz_threshold, 4),
        "mode": "two-phase (inverted n-gram index -> TF-IDF + Levenshtein word-block, streaming)",
    }
    if not n1 or not n2:
        yield meta
        yield {"t": "done", "found": 0, "total": 0}
        return

    # BPE-subword TF-IDF (scores candidates; does NOT gate recall)
    vocab: dict[str, int] = {}
    for _, _, _, subs, _ in u1 + u2:
        for s in subs:
            if s not in vocab:
                vocab[s] = len(vocab)
    base = len(vocab) + 1
    counters1 = [Counter(_hashes([vocab[s] for s in subs], base, ngram, n_out))
                 for _, _, _, subs, _ in u1]
    counters2 = [Counter(_hashes([vocab[s] for s in subs], base, ngram, n_out))
                 for _, _, _, subs, _ in u2]
    idf = _idf(counters1 + counters2)

    # Phase 1: inverted-index candidate generation on word BIGRAMS (robust to
    # Ionic/Attic spelling drift; trigrams are too brittle for that)
    wn = 2
    grams2 = [_word_ngrams(u[2], wn) for u in u2]
    inv: dict[tuple, list[int]] = {}
    for j, gs in enumerate(grams2):
        for g in set(gs):
            inv.setdefault(g, []).append(j)
    df_cap = max(40, int(0.04 * n2))
    cand: dict[tuple, int] = {}
    for i in range(n1):
        local: dict[int, int] = {}
        for g in set(_word_ngrams(u1[i][2], wn)):
            posting = inv.get(g)
            if not posting or len(posting) > df_cap:
                continue
            for j in posting:
                local[j] = local.get(j, 0) + 1
        for j, shared in local.items():
            if shared >= min_shared:
                cand[(i, j)] = shared
    ranked = sorted(cand.items(), key=lambda kv: kv[1], reverse=True)[:max_candidates]

    vc1: dict[int, dict] = {}
    vc2: dict[int, dict] = {}
    scored = []
    for (i, j), _shared in ranked:
        v1 = vc1.get(i)
        if v1 is None:
            v1 = vc1[i] = _tfidf(counters1[i], idf)
        v2 = vc2.get(j)
        if v2 is None:
            v2 = vc2[j] = _tfidf(counters2[j], idf)
        scored.append((cosine(v1, v2), i, j))

    cand_scores = [s for s, _, _ in scored]
    auto = auto_threshold(cand_scores)
    sel = float(similarity_threshold) if similarity_threshold is not None else 0.0
    chosen = [(s, i, j) for (s, i, j) in scored if s >= sel]

    meta.update({
        "n_candidates": len(ranked), "n_chosen": len(chosen),
        "vocab_size": len(vocab),
        "mean": round(statistics.fmean(cand_scores), 4) if cand_scores else 0.0,
        "threshold": round(auto, 4), "used_threshold": round(sel, 4),
    })
    yield meta

    total = len(chosen)
    found = 0
    for idx, (score, i, j) in enumerate(chosen):
        label_i, orig_i, norm_i, _, _ = u1[i]
        label_j, orig_j, norm_j, _, _ = u2[j]
        raw = _fuzzy_blocks(norm_i, norm_j, fuzz_threshold, n_out)
        kept = [b for b in raw if b["core"] >= ngram and b["n"] >= min_chain_words]
        if kept:
            matched_i, matched_j = _block_word_maps(kept)
            bridges_i, bridges_j = _block_bridge_maps(kept, norm_i, norm_j)
            snip_i, rng_i, cnt_i = _snippet(orig_i, matched_i)
            snip_j, rng_j, cnt_j = _snippet(orig_j, matched_j)
            chain_len = max((b["n"] for b in kept), default=0)
            found += 1
            yield {"t": "pair", "pair": {
                "score": round(score, 4), "i": i, "j": j,
                "label_i": label_i, "label_j": label_j,
                "tokens_i": orig_i, "tokens_j": orig_j,
                "matched_i": matched_i, "matched_j": matched_j,
                "bridges_i": bridges_i, "bridges_j": bridges_j,
                "n_blocks": len(raw), "n_chained": len(kept),
                "matched_words": cnt_i,
                "word_range_i": rng_i, "word_range_j": rng_j,
                "chain_len": chain_len,
                "snippet_i": snip_i, "snippet_j": snip_j,
            }}
        if (idx + 1) % max(1, progress_every) == 0:
            yield {"t": "progress", "done": idx + 1, "total": total, "found": found}
    yield {"t": "done", "found": found, "total": total}


def compare(sections1: list[dict], sections2: list[dict], **kw) -> dict:
    """Backward-compatible wrapper around compare_iter(): collects every event
    and returns the same dict shape as before (sorted pairs + summary), so the
    non-streaming /api/compare endpoint and the tests keep working unchanged."""
    kw.pop("progress_every", None)
    meta = {}
    pairs = []
    for ev in compare_iter(sections1, sections2, progress_every=10**9, **kw):
        t = ev.get("t")
        if t == "meta":
            meta = ev
        elif t == "pair":
            pairs.append(ev["pair"])
    pairs.sort(key=lambda p: p["chain_len"], reverse=True)
    return {
        "threshold": meta.get("threshold", 0.0),
        "used_threshold": meta.get("used_threshold", 0.0),
        "auto_threshold_disabled": True,
        "mean": meta.get("mean", 0.0),
        "n_pairs_total": meta.get("n_pairs_total", 0),
        "n_pairs_shown": len(pairs),
        "n_candidates": meta.get("n_candidates", 0),
        "ngram": meta.get("ngram", None), "n_out": meta.get("n_out", None),
        "min_chain_words": meta.get("min_chain_words", None),
        "fuzz_threshold": meta.get("fuzz_threshold", None),
        "vocab_size": meta.get("vocab_size", 0),
        "mode": meta.get("mode", ""),
        "pairs": pairs,
    }


