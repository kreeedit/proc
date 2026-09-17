"""Pure-Python BPE subword tokenizer (stdlib only: collections, re, json).

Trains a Byte Pair Encoding vocabulary on the cached Greek texts so that
inflectional endings (-ος, -ου, -ων, -οις, …) and stems split into separate
subword units — letting the Flame engine match a stem even when the ending
differs. The trained merges are cached at data/bpe_vocab.json.

Normalization mirrors the Flame engine (NFKD + drop combining marks + lower),
so matching is accent-insensitive; the *original* words are kept for display.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

END = "</w>"
_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)

# Module state
_MERGES: list[tuple[str, str]] | None = None
_RANKS: dict[tuple[str, str], int] | None = None
_STOP: set[str] | None = None
STOP_SIZE = 50            # top-N most frequent pure-grammatical endings -> noise
VOCAB_PATH = Path(__file__).resolve().parent.parent / "data" / "bpe_vocab.json"


def normalize(text: str) -> str:
    nf = unicodedata.normalize("NFKD", text).lower()
    return "".join(c for c in nf if not unicodedata.combining(c))


def _word_freqs_from_corpus(texts: list[str]) -> Counter:
    freqs: Counter = Counter()
    for t in texts:
        for w in _WORD_RE.findall(normalize(t)):
            freqs[w] += 1
    return freqs


def train(word_freqs: Counter, num_merges: int = 4000, min_freq: int = 2):
    """Efficient incremental BPE. Returns a list of (a, b) merges."""
    # working representation: list of [symbols(list), freq]
    words = [[list(w) + [END], f] for w, f in word_freqs.items() if w]
    pair_counts: Counter = Counter()
    pair_words: dict = {}  # pair -> set of word indices containing it
    for wi, (syms, f) in enumerate(words):
        for i in range(len(syms) - 1):
            p = (syms[i], syms[i + 1])
            pair_counts[p] += f
            pair_words.setdefault(p, set()).add(wi)
    merges: list[tuple[str, str]] = []
    for _ in range(num_merges):
        if not pair_counts:
            break
        best, f = max(pair_counts.items(), key=lambda kv: (kv[1], kv[0]))
        if f < min_freq:
            break
        merges.append(best)
        new_sym = best[0] + best[1]
        affected = list(pair_words.get(best, ()))
        for wi in affected:
            syms, wf = words[wi]
            # subtract this word's old pair contributions
            for i in range(len(syms) - 1):
                p = (syms[i], syms[i + 1])
                pair_counts[p] -= wf
                if pair_counts[p] <= 0:
                    del pair_counts[p]
                s = pair_words.get(p)
                if s is not None:
                    s.discard(wi)
                    if not s:
                        del pair_words[p]
            # merge the chosen pair (may occur multiple times)
            merged: list[str] = []
            i = 0
            while i < len(syms):
                if i < len(syms) - 1 and (syms[i], syms[i + 1]) == best:
                    merged.append(new_sym)
                    i += 2
                else:
                    merged.append(syms[i])
                    i += 1
            words[wi][0] = merged
            syms = merged
            # add new pair contributions
            for i in range(len(syms) - 1):
                p = (syms[i], syms[i + 1])
                pair_counts[p] += wf
                pair_words.setdefault(p, set()).add(wi)
    return merges


def save(merges, stop=None) -> None:
    VOCAB_PATH.parent.mkdir(parents=True, exist_ok=True)
    VOCAB_PATH.write_text(
        json.dumps({"merges": merges, "stop": stop or []}, ensure_ascii=False),
        encoding="utf-8")


def compute_stop(word_freqs, n=STOP_SIZE):
    """Top-N most frequent purely-grammatical subwords (word-final endings,
    i.e. subwords carrying </w>) — treated as noise and filtered from matching."""
    load()
    if not _MERGES:
        return []
    counts: Counter = Counter()
    for w, f in word_freqs.items():
        for sw in _encode_word(normalize(w)):
            counts[sw] += f
    # only word-final ending subwords (carry </w>), ranked by frequency
    ending_counts = [(c, sw) for sw, c in counts.items() if END in sw]
    ending_counts.sort(reverse=True)
    return [sw for _, sw in ending_counts[:n]]


def load(force=False):
    """Load cached merges + stop-words; return the merges list (empty if absent)."""
    global _MERGES, _RANKS, _STOP
    if _MERGES is not None and not force:
        return _MERGES
    if VOCAB_PATH.exists():
        try:
            data = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
            _MERGES = [tuple(m) for m in data.get("merges", [])]
            _STOP = set(data.get("stop", []))
        except Exception:
            _MERGES = []
            _STOP = set()
    else:
        _MERGES = []
        _STOP = set()
    _RANKS = {m: i for i, m in enumerate(_MERGES)}
    return _MERGES


def is_trained() -> bool:
    return bool(load())


def is_stop(sub: str) -> bool:
    if _STOP is None:
        load()
    return sub in (_STOP or set())


def stop_size() -> int:
    if _STOP is None:
        load()
    return len(_STOP or set())


def merge_ranks(limit=None) -> dict:
    """Rank map for the first `limit` merges (merge truncation). limit=None or
    >= len(merges) -> full. limit=0 -> empty -> no merges -> pure characters."""
    load()
    if not _MERGES:
        return {}
    if limit is None or limit >= len(_MERGES):
        return _RANKS or {}
    return {m: i for i, m in enumerate(_MERGES[:max(0, int(limit))])}


def _encode_word(word: str, ranks=None) -> list[str]:
    """Apply merges (lowest rank first) to a normalized word. `ranks` is a
    pair->rank dict; passing a truncated map limits how far merging goes
    (merge truncation / character-level at limit=0)."""
    if ranks is None:
        load()
        ranks = _RANKS or {}
    syms = list(word) + [END]
    if not ranks:
        return syms
    while len(syms) > 1:
        best_rank = None
        best_i = -1
        for i in range(len(syms) - 1):
            r = ranks.get((syms[i], syms[i + 1]))
            if r is not None and (best_rank is None or r < best_rank):
                best_rank = r
                best_i = i
        if best_rank is None:
            break
        a, b = syms[best_i], syms[best_i + 1]
        syms[best_i:best_i + 2] = [a + b]
    return syms


def tokenize_words(text: str, merge_limit=None):
    """Return (orig_words, subwords, sub_to_word).

    merge_limit: apply only the first N BPE merges (None=all). At 0 the encoder
    returns pure characters -> the Flame engine becomes a character n-grammer.

    orig_words : original (accented) word strings — for display
    subwords   : normalized subword strings (last one carries </w>)
    sub_to_word: subwords[i] belongs to orig_words[sub_to_word[i]]
    """
    ranks = merge_ranks(merge_limit) if merge_limit is not None else (_RANKS or {})
    load()
    orig_words = _WORD_RE.findall(text)
    subwords: list[str] = []
    sub_to_word: list[int] = []
    for wi, w in enumerate(orig_words):
        for sw in _encode_word(normalize(w), ranks):
            subwords.append(sw)
            sub_to_word.append(wi)
    return orig_words, subwords, sub_to_word


def tokenize(text: str) -> list[str]:
    return tokenize_words(text)[1]