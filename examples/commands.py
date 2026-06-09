"""
Subcommand-based configuration with clevis.

This example demonstrates how to use the @configclass decorator to create
CLI applications with multiple subcommands. Each subcommand has its own
configuration class, aliases, and help text, making it easy to build
complex command-line tools with clean separation of concerns.

Features demonstrated:
- @configclass decorator for automatic CLI argument generation
- Subcommand definitions with cmd parameter
- Command aliases for shortcuts (c, chk for check)
- Global configuration shared across commands
- Per-command configuration classes
- Help text for commands (--help)
- Configuration source filtering (project=False, user=False)

Run with:
    uv run python commands.py --help
    uv run python commands.py check --help
    uv run python commands.py c --verbose      # Using alias 'c' for 'check'
    uv run python commands.py chk --verbose    # Using alias 'chk' for 'check'
    uv run python commands.py print --rich
    uv run python commands.py echo --parameter "hello"

Example TOML file (commands.toml or .commands.toml):
    directory = "/path/to/project"

    [check]
    verbose = true
    parameter = "default-value"

    [print]
    rich = true

    [echo]
    parameter = "echo-value"
"""

from dataclasses import dataclass
from rich.pretty import pprint

from clevis import configclass, get_cmd, get_config, SecurityAction


@configclass
class Globals:
  """Global configuration shared across all commands."""
  directory: str = "."


@dataclass
class BaseConfig:
  """Base configuration with common fields."""
  parameter: str = None


@configclass(cmd="print", help="Print configuration", aliases=["p"])
class PrintConfig:
  """Configuration for the print command.

  Demonstrates a simple command with a boolean flag.
  """
  rich: bool = False


@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig(BaseConfig):
  """Configuration for the check command.

  Demonstrates command with aliases and inherited fields.
  """
  verbose: bool = False


@configclass(cmd="echo")
class EchoConfig(BaseConfig):
  """Configuration for the echo command.

  Demonstrates command without aliases, using inherited parameter.
  """
  pass


if __name__ == "__main__":
  # Security configuration for file permission checks
  security = {
    "file_permissions": SecurityAction.LOG,
    "directory_permissions": SecurityAction.LOG
  }

  # Get the requested subcommand
  cmd = get_cmd()

  # Load global configuration (can be used by all commands)
  config = get_config(Globals)

  # Handle directory change if specified
  if config.directory != ".":
    print(f"changing to directory {config.directory}")

  # Load and process command-specific configuration
  if cmd == "check":
    # Load check config with custom sources
    config = get_config(CheckConfig, project=False, user=False, security=security)
    print(f"checking verbose={config.verbose}")
  elif cmd == "print":
    # Load print config and display
    config = get_config(PrintConfig, project=False, user=False, security=security)
    if config.rich:
      pprint(config)
    else:
      print(config)
  elif cmd == "echo":
    # Load echo config and print parameter
    config = get_config(EchoConfig, project=False, user=False, security=security)
    print(config.parameter)