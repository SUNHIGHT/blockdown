"""Name normalisation for pg_trgm matching.

The SAME function must be used (a) when inserting rows into `foods`
(name_norm / chain_norm columns) and (b) when querying, otherwise the
trigram similarity is computed over two differently-shaped strings.

What it absorbs:
  - full/half width  (ＡＢＣ / ABC, ｶﾀｶﾅ / カタカナ)          via NFKC
  - upper/lower case                                           via casefold
  - katakana / hiragana                                        folded to hiragana
  - spaces, punctuation, symbols, brackets, middle dots        removed
  - "【店舗限定】" style annotations                            removed
  - a few frequent spelling variants (から揚げ/唐揚げ, 玉子/卵, 並盛り/並盛)

What it does NOT do: kanji <-> kana readings ("牛丼" vs "ぎゅうどん").
That needs a morphological analyser (e.g. pykakasi / fugashi); add it in
`_fold_reading` if the match rate on real data shows it is worth it.
"""
from __future__ import annotations

import re
import unicodedata

# Annotation brackets that carry no dish identity.
_NOTE_WORDS = ("店舗限定", "期間限定", "数量限定", "地域限定", "季節限定", "新発売", "新商品")
_NOTE_BLOCK = re.compile(r"[【\[［]([^】\]］]*)[】\]］]")

# (pattern, replacement) applied AFTER katakana->hiragana folding.
_SYNONYMS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p), r)
    for p, r in (
        (r"から揚げ|唐揚げ|唐揚|唐あげ|からあげ", "からあげ"),
        (r"ご飯|御飯|白飯|ごはん", "ごはん"),
        (r"玉子|卵|たまご", "たまご"),
        (r"(並|大|特|小|中)盛り", r"\1盛"),
        (r"(めん|麺)", "めん"),
    )
)


def _fold_kana(s: str) -> str:
    """Katakana (U+30A1..U+30F6, incl. ヴ) -> hiragana. 'ー' is left alone."""
    out = []
    for ch in s:
        o = ord(ch)
        out.append(chr(o - 0x60) if 0x30A1 <= o <= 0x30F6 else ch)
    return "".join(out)


def _strip_symbols(s: str) -> str:
    """Drop whitespace, punctuation, symbols and control chars; keep letters,
    digits, combining marks and the long-vowel mark 'ー' (category Lm)."""
    return "".join(
        ch for ch in s if unicodedata.category(ch)[0] in ("L", "N", "M")
    )


def normalize_food_name(name: str | None) -> str:
    """Canonical form used for both stored `name_norm` and lookup queries.

    >>> normalize_food_name("ﾗｰﾒﾝ") == normalize_food_name("ラーメン") == normalize_food_name("らーめん")
    True
    >>> normalize_food_name("唐揚げ定食【店舗限定】")
    'からあげ定食'
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).casefold()

    # Remove annotation blocks such as 【店舗限定】; other brackets just lose the
    # bracket characters (their content, e.g. "（6個）", is kept).
    def _drop_note(m: re.Match[str]) -> str:
        return "" if any(w in m.group(1) for w in _NOTE_WORDS) else m.group(0)

    s = _NOTE_BLOCK.sub(_drop_note, s)
    s = _fold_kana(s)
    for pat, rep in _SYNONYMS:
        s = pat.sub(rep, s)
    return _strip_symbols(s)


def normalize_chain_name(chain: str | None) -> str | None:
    """Same folding for chain names; empty -> None so SQL can treat it as 'any'."""
    n = normalize_food_name(chain)
    return n or None
