"""Style rules for what the player reads: no dash look-alikes and no middle dot used as a separator."""

import pathlib
import re

FORBIDDEN = re.compile("[\u2014\u2013\u2212\u2010\u2011\u2012\u2015\u00b7\u2022\u22c5\u2219]")
ROOTS = ("src/opendofusdata", "src/server", "tests", "README.md", "docs/developpement.md")


def test_no_dash_look_alike_nor_middle_dot_in_code_tests_and_readme() -> None:
    offenders = []
    for root in ROOTS:
        base = pathlib.Path(root)
        for path in ([base] if base.is_file() else base.rglob("*.py")):
            if path.name == "test_text_style.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if FORBIDDEN.search(line):
                    offenders.append(f"{path}:{number}")
    assert not offenders, offenders
