"""
Subcommands with TOML override example for Clevis.

This example demonstrates the `config` parameter which allows a subcommand
to read from a different TOML section than the command name.

Use case: When you have a base configuration class used by multiple
subcommands, but each subcommand reads from its own TOML section.

Run with:
    uv run python subcommands.py --help
    uv run python subcommands.py cli --server-url "https://api.example.com"
    uv run python subcommands.py tui --server-url "https://api.example.com"

Example TOML file (subcommands.toml):
    [client]
    server_url = "https://default.example.com"
    timeout = 30

    # Both cli and tui subcommands read from [client] section
    # because they use config="client" parameter
"""

from dataclasses import dataclass

from clevis import configclass, get_cmd, get_config, SecurityAction


# Base configuration shared by multiple subcommands
@dataclass
class ClientConfig:
  """Base configuration for client connections."""

  server_url: str = "http://localhost:8000"
  timeout: int = 30


# Subcommand reads from [client] section (not [cli])
@configclass(cmd="cli", config="client", help="Run CLI client")
class CliConfig(ClientConfig):
  """CLI client configuration.

  Inherits all fields from ClientConfig.
  Reads from [client] TOML section (config="client").
  """

  pass


# Subcommand reads from [client] section (not [tui])
@configclass(cmd="tui", config="client", help="Run TUI client")
class TUIConfig(ClientConfig):
  """TUI client configuration.

  Inherits all fields from ClientConfig.
  Reads from [client] TOML section (config="client").
  """

  pass


if __name__ == "__main__":
  # Security configuration for development
  security = {
    "file_permissions": SecurityAction.LOG,
    "directory_permissions": SecurityAction.LOG,
  }

  # Get the requested subcommand
  cmd = get_cmd()

  # Both 'cli' and 'tui' subcommands read from [client] TOML section
  # This allows sharing configuration across different interfaces
  if cmd == "cli":
    config = get_config(CliConfig, security=security)
    print(f"CLI client connecting to {config.server_url}")
    print(f"Timeout: {config.timeout}s")
  elif cmd == "tui":
    config = get_config(TUIConfig, security=security)
    print(f"TUI client connecting to {config.server_url}")
    print(f"Timeout: {config.timeout}s")
  else:
    # No subcommand or unknown command
    print("Usage: subcommands.py {cli|tui} [--server-url URL] [--timeout N]")