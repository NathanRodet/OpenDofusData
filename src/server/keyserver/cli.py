"""The only command line of the server: generate the master secret."""

import argparse
import sys
from typing import TextIO

from keyserver.settings import SECRET_VARIABLE
from keyserver.signed_keys import generate_secret

NEW_SECRET_COMMAND = "new-secret"
ADMIN_VARIABLE = "ADMIN_SECRET"


def build_parser() -> argparse.ArgumentParser:
    """The parser with its single `new-secret` subcommand."""
    parser = argparse.ArgumentParser(prog="keyserver")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(NEW_SECRET_COMMAND, help="génère le secret maître (à copier dans les deux .env)")
    return parser


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    """Run the command; `new-secret` prints the secret once, for the server and the admin .env files."""
    build_parser().parse_args(argv)
    secret = generate_secret()
    out.write(f"{SECRET_VARIABLE}={secret}\n{ADMIN_VARIABLE}={secret}\n")
    return 0
