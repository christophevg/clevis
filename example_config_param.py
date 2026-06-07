"""Example demonstrating the config= parameter for @configclass.

This example shows how to use the config parameter to specify a TOML extraction
key that's different from the CLI command name.
"""

from clevis import configclass, get_config


# Example 1: Different names for CLI and TOML
@configclass(cmd="print", config="output")
class PrintConfig:
  """Print command with TOML section [output], not [print]."""
  rich: bool = False
  verbose: bool = False


# Example 2: Config extraction without CLI subcommand
@configclass(config="settings")
class SettingsConfig:
  """Settings extracted from [settings] section, no CLI subcommand."""
  debug: bool = False
  log_level: str = "INFO"


# Example 3: Backward compatible - uses cmd for both CLI and TOML
@configclass(cmd="check")
class CheckConfig:
  """Check command uses [check] for TOML (backward compatible)."""
  verbose: bool = False


if __name__ == "__main__":
  # This would load from a TOML file like:
  # [output]
  # rich = true
  # [settings]
  # debug = true
  # [check]
  # verbose = true

  print("Example config= parameter usage:")
  print("  @configclass(cmd='print', config='output')")
  print("    - CLI uses 'print' subcommand")
  print("    - TOML uses [output] section")
  print()
  print("  @configclass(config='settings')")
  print("    - No CLI subcommand")
  print("    - TOML uses [settings] section")
  print()
  print("  @configclass(cmd='check')")
  print("    - CLI uses 'check' subcommand")
  print("    - TOML uses [check] section (backward compatible)")