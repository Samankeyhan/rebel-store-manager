"""db/names.py: the stored form and the comparison key of a name (Persian/Arabic spelling variants)."""

import pytest

from db.names import name_key, stored_form

ZWNJ = "‌"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("كتاب", "کتاب"),  # Arabic Kaf -> Persian Kaf
        ("علي", "علی"),  # Arabic Yeh -> Persian Yeh
        ("نسخه ٣", "نسخه ۳"),  # Arabic-Indic digit -> Persian digit
        ("نسخه ۳", "نسخه ۳"),  # already Persian: unchanged
        ("  تی‌شرت  ", "تی‌شرت"),  # strip, ZWNJ between letters kept
        ("آلبوم  جدید", "آلبوم جدید"),  # NBSP run
        ("آلبوم\t\n جدید", "آلبوم جدید"),  # tab / newline run
        ("آل​بوم", "آلبوم"),  # zero-width space removed (never a space)
        ("آل‎بوم‏", "آلبوم"),  # LRM / RLM
        ("‪آلبوم‬ ⁦جدید⁩", "آلبوم جدید"),  # bidi embeddings / isolates
        ("﻿آلبوم­⁠", "آلبوم"),  # BOM, soft hyphen, word joiner
        ("می‌‌‌خواهم", "می‌خواهم"),  # ZWNJ run collapses to one
        ("می‌ خواهم", "می خواهم"),  # ZWNJ next to a space removed
        ("‌می", "می"),  # ZWNJ at the edge removed
        ("می‌", "می"),
        ("می‌۲", "می۲"),  # ZWNJ before a digit removed
        ("a‌b", "ab"),  # ZWNJ between Latin letters removed
        ("می‌A", "میA"),  # ZWNJ between Persian and Latin removed
        ("آ", "آ"),  # NFC: alef + madda -> alef with madda
        ("", ""),
        ("​ ‎", ""),  # nothing but invisibles
    ],
)
def test_stored_form(raw, expected):
    assert stored_form(raw) == expected


def test_stored_form_is_idempotent():
    for raw in ("  كتاب‏  ٣  ", "می‌‌خواهم", "Ab‌C", ""):
        once = stored_form(raw)
        assert stored_form(once) == once


@pytest.mark.parametrize(
    "a, b",
    [
        ("كتاب", "کتاب"),
        ("علي", "علی"),
        ("تی‌شرت", "تیشرت"),  # ZWNJ ignored by the key
        ("تی شرت", "تی  شرت"),
        ("نسخه ٣", "نسخه 3"),  # every digit set -> ASCII
        ("نسخه ۳", "نسخه 3"),
        ("Rebel LP", "REBEL lp"),  # casefold
        ("ﻙتاب", "کتاب"),  # Arabic presentation form -> NFKC -> Arabic Kaf -> Persian
        ("ＡＢＣ", "abc"),  # full-width Latin
        ("ﬁle", "file"),  # ligature
        ("آلبوم‏", "آلبوم"),
        ("Straße", "STRASSE"),  # casefold, not lower
    ],
)
def test_same_key(a, b):
    assert name_key(a) == name_key(b)


@pytest.mark.parametrize(
    "a, b",
    [
        ("آلبوم", "البوم"),  # different letters stay different
        ("نسخه 1", "نسخه 2"),
        ("تی شرت", "تیشرت"),  # a real space is not a ZWNJ
        ("ab", "a b"),
    ],
)
def test_different_key(a, b):
    assert name_key(a) != name_key(b)


def test_key_of_stored_form_equals_key_of_raw_name():
    for raw in ("  كتاب‏  ٣  ", "می‌‌خواهم", "ﻙتاب", "Ab‌C"):
        assert name_key(stored_form(raw)) == name_key(raw)


def test_key_has_no_arabic_variants_digits_or_zwnj():
    key = name_key("كيك‌٣۴")
    assert "ك" not in key and "ي" not in key and ZWNJ not in key
    assert key.endswith("34")
