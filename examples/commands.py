"""
Example usage of the clevis configuration module with subcommands.

Run with:
    uv run python commands.py --help
    uv run python commands.py check --help
    uv run python commands.py c --verbose      # Using alias 'c' for 'check'
    uv run python commands.py chk --verbose    # Using alias 'chk' for 'check'
"""

from rich.pretty import pprint

from clevis import configclass, get_cmd, get_config, SecurityAction


@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig:
  verbose: bool = False


@configclass(cmd="print", help="Print configuration", aliases=["p"])
class PrintConfig:
  rich: bool = False


if __name__ == "__main__":
  cmd = get_cmd()
  security = {"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG}
  if cmd == "check":
    config = get_config(CheckConfig, project=False, user=False, security=security)
    print(f"checking verbose={config.verbose}")
  elif cmd == "print":
    config = get_config(PrintConfig, project=False, user=False, security=security)
    if config.rich:
      pprint(config)
    else:
      print(config)

