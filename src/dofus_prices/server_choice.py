"""Which game server the records belong to: pure precedence and prompt logic (no console)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from dofus_prices.game_servers import UNKNOWN_SERVER, GameServer, canonical_name

Ask = Callable[[str], str]
Say = Callable[[str], None]
Source = Literal["option", "config", "prompt", "default"]

SERVER_KEY = "server"
MAX_INVALID_ATTEMPTS = 3
OTHER_TYPE_LABEL = "Autres"
UNLISTED_WARNING = ("serveur « {name} » absent de la liste "
                    "(servers-update pour la mettre à jour)")
PROMPT_TEXT = "Numéro ou nom du serveur (Entrée pour passer) : "
FREE_TEXT_PROMPT = "Nom du serveur (Entrée pour passer) : "
INVALID_CHOICE = "Choix invalide : tape un numéro de la liste ou le nom exact du serveur."
SKIPPED_MESSAGE = "Aucun serveur choisi : les prix seront enregistrés avec « unknown »."
NO_LIST_MESSAGE = (r"Liste des serveurs absente : télécharge-la avec .\dev.ps1 run servers-update. "
                   "Tu peux aussi saisir le nom du serveur à la main.")
NON_INTERACTIVE_HINT = ("Serveur inconnu : indique-le avec --server NOM ou mémorise-le avec "
                        "« server --set NOM » (voir le README).")


@dataclass(frozen=True)
class ServerResolution:
    """The chosen server name, where it came from, and whether to remember it."""

    name: str
    source: Source
    save: bool


def _default_resolution() -> ServerResolution:
    return ServerResolution(UNKNOWN_SERVER, "default", False)


def normalise_server_name(name: str, servers: Sequence[GameServer], say: Say) -> str:
    """Return the listed spelling of a name; warn if a non-empty list lacks it."""
    if not servers or name == UNKNOWN_SERVER:
        return name
    canonical = canonical_name(servers, name)
    if canonical is None:
        say(UNLISTED_WARNING.format(name=name))
        return name
    return canonical


def _display_order(servers: Sequence[GameServer]) -> list[GameServer]:
    return sorted(servers, key=lambda server: (not server.game_type, server.game_type.casefold(),
                                               server.name.casefold()))


def _print_numbered_list(ordered: Sequence[GameServer], say: Say) -> None:
    current_type: str | None = None
    for number, server in enumerate(ordered, start=1):
        label = server.game_type or OTHER_TYPE_LABEL
        if label != current_type:
            say(f"{label} :")
            current_type = label
        say(f"  {number}. {server.name}")


def _match_answer(answer: str, ordered: Sequence[GameServer]) -> str | None:
    if answer.isascii() and answer.isdigit():
        index = int(answer)
        return ordered[index - 1].name if 1 <= index <= len(ordered) else None
    return canonical_name(ordered, answer)


def _ask_or_none(ask: Ask, prompt: str) -> str | None:
    """Return the stripped answer; None at end of input."""
    try:
        return ask(prompt).strip()
    except EOFError:
        return None


def _prompt_for_listed_server(ordered: Sequence[GameServer], ask: Ask, say: Say) -> str | None:
    _print_numbered_list(ordered, say)
    for _ in range(MAX_INVALID_ATTEMPTS):
        answer = _ask_or_none(ask, PROMPT_TEXT)
        if not answer:
            return None
        chosen = _match_answer(answer, ordered)
        if chosen is not None:
            return chosen
        say(INVALID_CHOICE)
    return None


def _prompt_for_free_text(ask: Ask, say: Say) -> str | None:
    say(NO_LIST_MESSAGE)
    return _ask_or_none(ask, FREE_TEXT_PROMPT) or None


def _from_prompt(servers: Sequence[GameServer], ask: Ask, say: Say) -> ServerResolution:
    if servers:
        name = _prompt_for_listed_server(_display_order(servers), ask, say)
    else:
        name = _prompt_for_free_text(ask, say)
    if name is None:
        say(SKIPPED_MESSAGE)
        return _default_resolution()
    return ServerResolution(name, "prompt", True)


def resolve_server(
    explicit: str | None, servers: Sequence[GameServer], config: Mapping[str, object],
    interactive: bool, force_choice: bool, ask: Ask, say: Say,
) -> ServerResolution:
    """Pick the server: option, saved choice, prompt, else unknown (never saved)."""
    if explicit is not None:
        return ServerResolution(normalise_server_name(explicit, servers, say), "option", False)
    saved = config.get(SERVER_KEY)
    if not force_choice and isinstance(saved, str) and saved:
        return ServerResolution(saved, "config", False)
    if interactive:
        return _from_prompt(servers, ask, say)
    say(NON_INTERACTIVE_HINT)
    return _default_resolution()
