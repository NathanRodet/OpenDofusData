"""Display text of kamas and experience values: pure logic."""

UNKNOWN_TEXT = "Inconnu"
WHOLE_NUMBER_FROM = 10
SINGLE_EXPERIENCE = 1


def _spaced(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_kamas(value: float | None) -> str:
    """A rounded amount with spaces between the thousands."""
    return UNKNOWN_TEXT if value is None else _spaced(round(value))


def format_signed_kamas(value: float | None) -> str:
    """A rounded amount with its sign, like +15 880 or -1 260."""
    if value is None:
        return UNKNOWN_TEXT
    rounded = round(value)
    return ("+" if rounded >= 0 else "-") + _spaced(abs(rounded))


def format_kamas_per_experience(value: float | None) -> str:
    """Whole kamas from 10, one decimal with a comma below."""
    if value is None:
        return UNKNOWN_TEXT
    if value >= WHOLE_NUMBER_FROM:
        return _spaced(round(value))
    return f"{value:.1f}".replace(".", ",")


def format_experience_per_unit(value: float | None) -> str:
    """The experience one resource gives, with at least the tenth: +7,3 or +0,111 (a comma, as in French)."""
    if value is None or value <= 0:
        return UNKNOWN_TEXT
    text = f"{value:.1f}" if value >= SINGLE_EXPERIENCE else f"{value:.3g}"
    if "e" in text:  # a tiny figure: fixed decimals instead of an exponent
        text = f"{value:.6f}".rstrip("0")
    if text == "1" or "." not in text:
        text += ".0"
    return "+" + text.replace(".", ",")
