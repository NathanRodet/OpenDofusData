"""Tests for the server resolution precedence and the numbered prompt (no console)."""

from dofus_prices.game_servers import GameServer
from dofus_prices.server_choice import ServerResolution, resolve_server

SERVERS = [
    GameServer(295, "Draconiros", 0, "Classique", 0),
    GameServer(294, "Hell Mina", 0, "Classique", 0),
    GameServer(900, "Speed Rush", 3, "Tournoi", 1),
    GameServer(9, "Zed", 77, "", 1),
]


class Script:
    """Scripted answers; raises EOFError once exhausted. Records prompts and messages."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.said: list[str] = []

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)

    def say(self, text: str) -> None:
        self.said.append(text)


def resolve(script: Script, explicit=None, servers=SERVERS, config=None,
            interactive=True, force_choice=False) -> ServerResolution:
    return resolve_server(explicit, servers, config or {}, interactive, force_choice,
                          script.ask, script.say)


def test_option_uses_canonical_spelling_and_is_not_saved() -> None:
    script = Script()
    result = resolve(script, explicit="draconiros", config={"server": "Zed"})
    assert result == ServerResolution("Draconiros", "option", False)
    assert script.prompts == [] and script.said == []


def test_option_not_in_list_is_kept_with_french_warning() -> None:
    script = Script()
    result = resolve(script, explicit="Inconnu")
    assert (result.name, result.source, result.save) == ("Inconnu", "option", False)
    assert script.said == ["serveur « Inconnu » absent de la liste "
                           "(servers-update pour la mettre à jour)"]


def test_option_without_servers_or_unknown_does_not_warn() -> None:
    script = Script()
    assert resolve(script, explicit="X", servers=[]).name == "X"
    assert resolve(script, explicit="unknown").name == "unknown"
    assert script.said == []


def test_config_server_is_used_silently() -> None:
    script = Script()
    result = resolve(script, config={"server": "Zed"})
    assert result == ServerResolution("Zed", "config", False)
    assert script.prompts == [] and script.said == []


def test_config_server_not_in_list_warns_once_and_is_still_used() -> None:
    script = Script()
    result = resolve(script, config={"server": "Fantome"})
    assert result == ServerResolution("Fantome", "config", False)
    assert script.said == ["serveur « Fantome » absent de la liste "
                           "(servers-update pour la mettre à jour)"]
    assert resolve(Script(), config={"server": "ZED"}).name == "ZED"


def test_blank_option_is_ignored_with_one_warning_and_resolution_continues() -> None:
    for blank in ("", "   "):
        script = Script()
        result = resolve(script, explicit=blank, config={"server": "Zed"})
        assert result == ServerResolution("Zed", "config", False)
        assert script.said == ["--server vide ignoré"]
    prompted = Script("1")
    assert resolve(prompted, explicit=" ").source == "prompt"
    assert prompted.said.count("--server vide ignoré") == 1


def test_option_and_config_names_are_stripped() -> None:
    assert resolve(Script(), explicit="  hell mina ").name == "Hell Mina"
    assert resolve(Script(), config={"server": "  Zed  "}).name == "Zed"


def test_config_server_ignored_when_not_a_non_empty_string() -> None:
    for bad in (None, 3, "", "  ", ["x"]):
        script = Script("1")
        assert resolve(script, config={"server": bad}).source == "prompt"


def test_force_choice_asks_even_with_saved_server() -> None:
    result = resolve(Script("2"), config={"server": "Brial"}, force_choice=True)
    assert result == ServerResolution("Hell Mina", "prompt", True)


def test_option_wins_over_force_choice() -> None:
    script = Script()
    assert resolve(script, explicit="Zed", force_choice=True).source == "option"
    assert script.prompts == []


def test_prompt_lists_numbered_servers_grouped_by_type() -> None:
    script = Script("1")
    resolve(script)
    listing = "\n".join(script.said)
    assert listing.index("Classique") < listing.index("  1. Draconiros")
    assert listing.index("  2. Hell Mina") < listing.index("Tournoi")
    assert listing.index("Tournoi") < listing.index("  3. Speed Rush")
    assert "  4. Zed" in listing


def test_prompt_accepts_number_and_exact_name_case_insensitive() -> None:
    assert resolve(Script("3")).name == "Speed Rush"
    assert resolve(Script("hell mina")).name == "Hell Mina"
    assert resolve(Script("  ZED ")).name == "Zed"


def test_prompt_choice_is_saved() -> None:
    assert resolve(Script("1")) == ServerResolution("Draconiros", "prompt", True)


def test_invalid_then_valid() -> None:
    script = Script("99", "nope", "2")
    result = resolve(script)
    assert result.name == "Hell Mina" and result.save
    assert len(script.prompts) == 3
    assert sum("invalide" in line for line in script.said) == 2


def test_three_invalid_answers_skip_without_saving() -> None:
    script = Script("0", "99", "abc", "1")
    result = resolve(script)
    assert result == ServerResolution("unknown", "default", False)
    assert len(script.prompts) == 3


def test_empty_answer_and_eof_skip_without_saving() -> None:
    assert resolve(Script("")) == ServerResolution("unknown", "default", False)
    assert resolve(Script()) == ServerResolution("unknown", "default", False)


def test_empty_list_never_asks_and_never_saves_free_text() -> None:
    script = Script("Mon Serveur")
    assert resolve(script, servers=[]) == ServerResolution("unknown", "default", False)
    assert script.prompts == []


def test_non_interactive_gives_unknown_with_one_line_hint() -> None:
    script = Script()
    result = resolve(script, interactive=False)
    assert result == ServerResolution("unknown", "default", False)
    assert script.prompts == [] and len(script.said) == 1
    assert "--server" in script.said[0] and "server --set" in script.said[0]


def test_non_interactive_still_uses_saved_server() -> None:
    result = resolve(Script(), config={"server": "Brial"}, interactive=False)
    assert result.source == "config"


def test_unknown_is_never_saved_in_any_path() -> None:
    cases = [resolve(Script(), interactive=False), resolve(Script("")), resolve(Script(), servers=[]),
             resolve(Script("x", "y", "z"))]
    assert all(case.name == "unknown" and not case.save for case in cases)
