"""Name normalization: pure functions, no database.
`stored_form(name)` is what a new or edited name is saved as: NFC, Arabic Yeh/Kaf -> Persian, Arabic-Indic digits -> Persian digits, invisible/bidi controls removed, every whitespace run -> one space (stripped), ZWNJ kept only between two Arabic-script letters.
`name_key(name)` is the comparison key (column `name_key`, unique per table): stored form, then NFKC, ZWNJ removed, digits -> ASCII, casefold. Two names that differ only in spelling variants have the same key.
Existing names are never rewritten; only their key is computed (db/name_keys.py)."""

import unicodedata

ZWNJ = "‌"

# Arabic -> Persian letters; Arabic-Indic (U+0660..) and Persian (U+06F0..) digits.
_LETTERS = {0x064A: 0x06CC, 0x0643: 0x06A9}
_TO_PERSIAN_DIGITS = {0x660 + i: 0x6F0 + i for i in range(10)}
_TO_ASCII_DIGITS = {0x660 + i: 0x30 + i for i in range(10)} | {0x6F0 + i: 0x30 + i for i in range(10)}

# Zero-width space, LRM, RLM, U+202A-202E, U+2066-2069, BOM, soft hyphen, word joiner.
_INVISIBLE = {0x200B, 0x200E, 0x200F, 0xFEFF, 0x00AD, 0x2060, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}
_REMOVE = dict.fromkeys(_INVISIBLE)

_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def _is_arabic_letter(ch: str) -> bool:
    return unicodedata.category(ch).startswith("L") and any(
        low <= ord(ch) <= high for low, high in _ARABIC_RANGES
    )


def _fix_letters(text: str) -> str:
    return text.translate(_LETTERS)


def _keep_zwnj_between_letters(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] != ZWNJ:
            out.append(text[i])
            i += 1
            continue
        while i < len(text) and text[i] == ZWNJ:
            i += 1
        if out and i < len(text) and _is_arabic_letter(out[-1]) and _is_arabic_letter(text[i]):
            out.append(ZWNJ)
    return "".join(out)


def stored_form(name: str) -> str:
    text = unicodedata.normalize("NFC", name)
    text = _fix_letters(text).translate(_TO_PERSIAN_DIGITS).translate(_REMOVE)
    text = " ".join(text.split())
    return unicodedata.normalize("NFC", _keep_zwnj_between_letters(text))


def name_key(name: str) -> str:
    text = unicodedata.normalize("NFKC", stored_form(name))
    # NFKC turns Arabic presentation forms back into Arabic Yeh/Kaf, so map them again.
    text = _fix_letters(text).replace(ZWNJ, "").translate(_TO_ASCII_DIGITS)
    return text.casefold()
