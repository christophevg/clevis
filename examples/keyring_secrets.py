"""Keyring secret interpolation in Clevis.

Demonstrates ${keyring:service/username} placeholder expansion backed by
the system keyring. Unlike ${VAR} environment interpolation, keyring
placeholders are expanded by clevis itself — no special TOML backend needed.

Features demonstrated:
- ${keyring:service/username} syntax for keyring-backed secrets
- The `clevis keyring set` helper for storing secrets interactively
- Composition with plain values and dataclass validation

Requirements:
    pip install clevis[keyring]  # keyring support

Store the secret (interactive prompt — never in shell history):
    clevis keyring set clevis-example db-password

Run with:
    uv run python keyring_secrets.py

Example TOML file (keyring.toml):
    [database]
    host = "localhost"
    port = 5432
    password = "${keyring:clevis-example/db-password}"

    [app]
    name = "MyApp"

Note: like the ${VAR} syntax, a literal "${keyring:...}" cannot be escaped
in TOML files, and secrets containing "${" should be avoided.
"""

from dataclasses import dataclass
from rich.pretty import pprint
from clevis import get_config, SecurityAction


@dataclass
class DatabaseConfig:
  """Database connection configuration.

  The password is read from the system keyring entry
  service='clevis-example', username='db-password' (stored via
  `clevis keyring set clevis-example db-password`).
  """
  host: str = "localhost"
  port: int = 5432
  password: str | None = None


@dataclass
class AppConfig:
  """Application configuration."""
  name: str = "MyApp"


@dataclass
class Config:
  """Root configuration with nested sections."""
  database: DatabaseConfig
  app: AppConfig


if __name__ == "__main__":
  # Load configuration; keyring placeholders are expanded before parsing.
  # Security checks disabled for this example — in production keep the
  # default (REJECT).
  config = get_config(
    Config,
    name="keyring",
    security={
      "file_permissions": SecurityAction.DONT_CHECK,
      "directory_permissions": SecurityAction.DONT_CHECK,
    },
  )
  print("\n" + "=" * 70)
  print("Configuration loaded from keyring.toml with keyring secret interpolation")
  print("=" * 70 + "\n")
  print("App Configuration:")
  print(f"  Name: {config.app.name}")
  print("\nDatabase Configuration:")
  print(f"  Host: {config.database.host}")
  print(f"  Port: {config.database.port}")
  print(f"  Password: {'***' if config.database.password else 'NOT SET'}")
  print("\n" + "=" * 70)
  print("Full configuration:")
  print("=" * 70 + "\n")
  pprint(config)
