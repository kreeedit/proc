"""FLAME text-reuse engine (fork used for the Eustratius paper).

This package holds the engine exactly as it ran for the paper's sweep:

    flame_pure.py   the matching engine (``compare_iter`` is the entry point)
    bpe_pure.py     pure-Python BPE subword tokenizer (loads ``../data/bpe_vocab.json``)

Upstream project: https://github.com/kreeedit/FLAME (Apache-2.0).
This fork is maintained separately; see ../README.md for what differs and why.
"""
