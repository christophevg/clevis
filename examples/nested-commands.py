"""
Example usage of the clevis configuration module with subcommands.

Run with:
    uv run python commands.py --help
    uv run python commands.py check --help
    uv run python commands.py c --verbose      # Using alias 'c' for 'check'
    uv run python commands.py chk --verbose    # Using alias 'chk' for 'check'
"""

from dataclasses import dataclass, field
from rich.pretty import pprint

from clevis import configclass, get_cmd, get_config, SecurityAction

# module level

@dataclass
class PrintConfig:
  rich: bool = False

@configclass
class RootConfig:
  print : PrintConfig = field(default_factory=PrintConfig)

# cli level

@configclass(cmd="print")
class PrintCmd(PrintConfig):
  pass

if __name__ == "__main__":
  security = {
    "file_permissions": SecurityAction.LOG,
    "directory_permissions": SecurityAction.LOG
  }
  cmd = get_cmd()

  if cmd == "print":
    config = get_config(PrintCmd, security=security, name="nested-commands")
    if config.rich:
      pprint(config)
    else:
      print(config)
