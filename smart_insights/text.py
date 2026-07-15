"""Deterministic ASCII folding for LLM-authored prose.

Stage 2 and stage 5 both instruct the model to write plain ASCII -- straight
quotes, ordinary hyphens, no typographic dashes -- but a prompt is a request,
not a guarantee: gpt-5 still slips in a curly quote or an em dash. This folds
the output down to ASCII deterministically, so the committed artifacts and the
cp1252 Windows console never meet a character they cannot encode. It is the
enforcement behind the prompts' "plain ASCII only" rule, applied on the LLM
response models in models.py.
"""

from __future__ import annotations

import unicodedata

# Characters that carry a deliberate ASCII spelling, keyed by code point so
# this source stays pure ASCII (ruff RUF001 flags ambiguous literals). Mapped
# by intent rather than left to the lossy NFKD pass below, which would drop an
# em dash entirely and turn an ellipsis into nothing.
_REPLACEMENTS = {
    0x2018: "'",  # left single quote
    0x2019: "'",  # right single quote / apostrophe
    0x201A: "'",  # single low-9 quote
    0x201C: '"',  # left double quote
    0x201D: '"',  # right double quote
    0x201E: '"',  # double low-9 quote
    0x2032: "'",  # prime
    0x2033: '"',  # double prime
    0x2012: "-",  # figure dash
    0x2013: "-",  # en dash
    0x2014: "-",  # em dash
    0x2015: "-",  # horizontal bar
    0x2212: "-",  # minus sign
    0x2026: "...",  # ellipsis
    0x2022: "*",  # bullet
    0x00A0: " ",  # no-break space
    0x2009: " ",  # thin space
    0x202F: " ",  # narrow no-break space
}


def normalize_ascii(text: str) -> str:
    """Fold `text` to pure ASCII, deterministically and idempotently.

    Known typographic characters become their intended ASCII spelling; anything
    else is decomposed (an accented letter to its base) and any residual
    non-ASCII dropped, so the result always encodes as ASCII.
    """
    mapped = text.translate(_REPLACEMENTS)
    decomposed = unicodedata.normalize("NFKD", mapped)
    return decomposed.encode("ascii", "ignore").decode("ascii")
