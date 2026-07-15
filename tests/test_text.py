"""normalize_ascii folds typographic characters to ASCII, idempotently."""

from smart_insights.text import normalize_ascii

CURLY_SINGLE_OPEN = chr(0x2018)
CURLY_SINGLE_CLOSE = chr(0x2019)
CURLY_DOUBLE_OPEN = chr(0x201C)
CURLY_DOUBLE_CLOSE = chr(0x201D)
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
ELLIPSIS = chr(0x2026)
NO_BREAK_SPACE = chr(0x00A0)
E_ACUTE = chr(0x00E9)


def test_curly_quotes_become_straight():
    text = f"{CURLY_DOUBLE_OPEN}exit{CURLY_SINGLE_CLOSE}intent{CURLY_DOUBLE_CLOSE}"
    assert normalize_ascii(text) == '"exit\'intent"'


def test_dashes_and_ellipsis_become_ascii():
    text = f"5{EN_DASH}second delay{EM_DASH}try it{ELLIPSIS}"
    assert normalize_ascii(text) == "5-second delay-try it..."


def test_no_break_space_becomes_plain_space():
    assert normalize_ascii(f"2.4%{NO_BREAK_SPACE}median") == "2.4% median"


def test_accented_letter_folds_to_base():
    assert normalize_ascii(f"caf{E_ACUTE}") == "cafe"


def test_result_always_encodes_as_ascii():
    text = f"{CURLY_DOUBLE_OPEN}{E_ACUTE}{EM_DASH}{ELLIPSIS}"
    normalize_ascii(text).encode("ascii")  # raises if any non-ASCII survives


def test_plain_ascii_is_unchanged():
    text = "Add an exit-intent trigger; your rate is 2.4% vs median 3.1%."
    assert normalize_ascii(text) == text


def test_idempotent():
    text = f"{CURLY_DOUBLE_OPEN}exit{EM_DASH}intent{CURLY_DOUBLE_CLOSE}{ELLIPSIS}"
    once = normalize_ascii(text)
    assert normalize_ascii(once) == once
