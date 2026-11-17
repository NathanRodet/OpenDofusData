"""Tests of the kamas and experience display text."""

from opendofusdata.value_format import (
    UNKNOWN_TEXT, format_experience_per_unit, format_kamas, format_kamas_per_experience, format_signed_kamas,
)


def test_kamas_use_spaces_between_thousands() -> None:
    assert format_kamas(21_550_920.0) == "21 550 920"
    assert format_kamas(0.0) == "0"


def test_signed_kamas() -> None:
    assert format_signed_kamas(15880.0) == "+15 880"
    assert format_signed_kamas(-1260.0) == "-1 260"
    assert format_signed_kamas(0.0) == "+0"


def test_kamas_per_experience() -> None:
    assert format_kamas_per_experience(7.5) == "7,5"
    assert format_kamas_per_experience(120.0) == "120"


def test_experience_per_unit() -> None:
    assert format_experience_per_unit(2.0) == "+2,0"  # always at least the tenth
    assert format_experience_per_unit(7.333) == "+7,3"
    assert format_experience_per_unit(640.44) == "+640,4"
    assert format_experience_per_unit(1 / 9) == "+0,111"  # a small figure keeps its significant digits
    assert format_experience_per_unit(0.5) == "+0,5"
    assert format_experience_per_unit(0.9999) == "+1,0"
    assert format_experience_per_unit(0.0004) == "+0,0004"


def test_unknown_values() -> None:
    for formatter in (format_kamas, format_signed_kamas, format_kamas_per_experience, format_experience_per_unit):
        assert formatter(None) == UNKNOWN_TEXT == "Inconnu"
