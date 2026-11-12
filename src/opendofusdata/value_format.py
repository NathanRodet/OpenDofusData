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
    """+N when one resource gives at least one XP, `1 XP pour N` otherwise."""
    if value is None or value <= 0:
        return UNKNOWN_TEXT
    if value >= SINGLE_EXPERIENCE:
        return f"+{round(value)}"
    return f"1 XP pour {round(1 / value)}"
