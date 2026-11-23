"""Command-line interface for Clevis.

A small convenience tool with two commands:

- ``clevis cat <file>`` — load a TOML file through the full Clevis
  pipeline (keyring pre-pass + backend env-var interpolation) and dump
  the interpreted configuration to stdout as JSON. Handy for debugging
  config loading.
- ``clevis keyring set <service> <username>`` — add secrets to the
  system keyring interactively (no secrets in shell history). Requires
  the ``keyring`` extra (``pip install clevis[keyring]``).
"""

import argparse
import getpass
import json
import sys

from clevis import __version__, load
from clevis.keyring import KeyringError, _get_keyring


def _cmd_cat(args: argparse.Namespace) -> int:
  """Dump a TOML file as interpreted by the full Clevis pipeline (JSON)."""
  try:
    with open(args.file, "rb") as f:
      data = load(f)
  except OSError as exc:
    reason = exc.strerror or str(exc)
    print(f"Error: cannot read {args.file}: {reason}", file=sys.stderr)
    return 1
  except Exception as exc:  # noqa: BLE001 - CLI reports any load failure as a one-liner
    print(f"Error: {exc}", file=sys.stderr)
    return 1
  print(json.dumps(data, indent=2))
  return 0


def _cmd_keyring_set(args: argparse.Namespace) -> int:
  """Store a secret in the system keyring, prompting without echo."""
  try:
    keyring = _get_keyring(
      "The 'keyring' package is required by 'clevis keyring set' but is not available."
    )
  except KeyringError as exc:
    print(str(exc), file=sys.stderr)
    return 1
  password = getpass.getpass(f"Password for {args.service}/{args.username}: ")
  if password != getpass.getpass("Repeat: "):
    print("Error: passwords do not match.", file=sys.stderr)
    return 2
  keyring.set_password(args.service, args.username, password)
  print(f"Stored secret for {args.service}/{args.username}.")
  return 0


def _build_parser() -> argparse.ArgumentParser:
  """Build the clevis argument parser (cat > keyring > set)."""
  parser = argparse.ArgumentParser(
    prog="clevis",
    description="Clevis configuration helper.",
  )
  parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
  subcommands = parser.add_subparsers(dest="command", required=True)
  cat_parser = subcommands.add_parser("cat", help="Dump a TOML file as Clevis interprets it (JSON)")
  cat_parser.add_argument(
    "file", help="TOML file to load (keyring and env-var interpolation applied)"
  )
  cat_parser.set_defaults(func=_cmd_cat)
  keyring_parser = subcommands.add_parser(
    "keyring", help="Manage keyring-backed configuration secrets"
  )
  keyring_sub = keyring_parser.add_subparsers(dest="subcommand", required=True)
  set_parser = keyring_sub.add_parser(
    "set", help="Interactively store a secret for a service/username pair"
  )
  set_parser.add_argument("service", help="Service name, e.g. 'myapp'")
  set_parser.add_argument("username", help="Username or account identifier")
  set_parser.set_defaults(func=_cmd_keyring_set)
  return parser


def main(argv: list[str] | None = None) -> int:
  """Entry point for the clevis console command.

  Args:
    argv: Optional argument list (defaults to sys.argv[1:]).

  Returns:
    Process exit code (0 success; 1 unreadable/invalid file or keyring
    unavailable; 2 password mismatch or invalid usage).
  """
  args = _build_parser().parse_args(argv)
  exit_code: int = args.func(args)
  return exit_code
