"""
Example usage of the clevis configuration module.

Run with:
    uv run python commands.py
    uv run python commands.py check
"""

from rich.pretty import pprint

from clevis import configclass, get_cmd, get_config


@configclass(cmd="check")
class CheckConfig:
  verbose : bool = False

@configclass(cmd="print")
class PrintConfig:
  rich : bool = False

if __name__ == "__main__":
  cmd = get_cmd()
  if cmd == "check":
    config = get_config(CheckConfig, project=False, user=False)
    print(f"checking verbose={config.verbose}")
  elif cmd == "print":
    config = get_config(PrintConfig, project=False, user=False)
    if config.rich:
      pprint(config)
    else:
      print(config)
