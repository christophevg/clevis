"""
Example usage of the clevis configuration module with subcommands.

Run with:
    uv run python commands.py --help
    uv run python commands.py check --help
    uv run python commands.py c --verbose      # Using alias 'c' for 'check'
    uv run python commands.py chk --verbose    # Using alias 'chk' for 'check'
"""

from dataclasses import dataclass
from rich.pretty import pprint

from clevis import configclass, get_cmd, get_config, SecurityAction

@configclass
class Globals:
  directory : str = "."

@dataclass
class BaseConfig:
  parameter : str = None

@configclass(cmd="print", help="Print configuration", aliases=["p"])
class PrintConfig:
  rich: bool = False

@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig(BaseConfig):
  verbose: bool = False

@configclass(cmd="echo")
class EchoConfig(BaseConfig):
  pass

if __name__ == "__main__":
  security = {
    "file_permissions": SecurityAction.LOG,
    "directory_permissions": SecurityAction.LOG
  }
  cmd = get_cmd()
  config = get_config(Globals)
  if config.directory != ".":
    print(f"changing to directory {config.directory}")
  if cmd == "check":
    config = get_config(CheckConfig, project=False, user=False, security=security)
    print(f"checking verbose={config.verbose}")
  elif cmd == "print":
    config = get_config(PrintConfig, project=False, user=False, security=security)
    if config.rich:
      pprint(config)
    else:
      print(config)
  elif cmd == "echo":
    config = get_config(EchoConfig, project=False, user=False, security=security)
    print(config.parameter)
