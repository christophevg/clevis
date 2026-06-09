"""Environment variable interpolation in Clevis.

Demonstrates how to use environment variables in TOML configuration
files with the envtoml parser.

Features demonstrated:
- ${VAR} syntax for environment variable expansion
- Environment-specific configuration
- Secure credential handling
- Type conversion from string environment variables

Requirements:
    pip install clevis[envtoml]  # Required for ${VAR} syntax

Run with:
    export DB_HOST=localhost
    export DB_PORT=5432
    export API_KEY=secret123
    export ENV=production
    uv run python environment.py

Example TOML file (environment.toml):
    [database]
    host = "${DB_HOST}"
    port = "${DB_PORT}"
    url = "${DB_HOST}:${DB_PORT}"
    api_key = "${API_KEY}"

    [app]
    name = "MyApp"
    environment = "${ENV}"

Note: For optional values with defaults, use dataclass defaults
instead of ${VAR|default} syntax, as this is not currently supported.
"""

from dataclasses import dataclass

from rich.pretty import pprint

from clevis import get_config, SecurityAction


@dataclass
class DatabaseConfig:
  """Database connection configuration.

  Environment variables:
      DB_HOST: Database host (required)
      DB_PORT: Database port (required, will be converted to int)
      API_KEY: API key for authentication (required)
  """

  host: str | None = None
  port: int | None = None
  url: str | None = None
  api_key: str | None = None


@dataclass
class AppConfig:
  """Application configuration.

  Environment variables:
      ENV: Environment name (required)
  """

  name: str | None = None
  environment: str | None = None


@dataclass
class Config:
  """Root configuration with nested sections."""

  database: DatabaseConfig
  app: AppConfig


if __name__ == "__main__":
  # Load configuration with security checks disabled for this example
  # In production, use SecurityAction.REJECT (default) for strict security
  config = get_config(
    Config,
    name="environment",
    security={
      "file_permissions": SecurityAction.DONT_CHECK,
      "directory_permissions": SecurityAction.DONT_CHECK,
    },
  )

  print("\n" + "=" * 70)
  print("Configuration loaded from environment.toml with env var interpolation")
  print("=" * 70 + "\n")

  print("Database Configuration:")
  print(f"  Host: {config.database.host}")
  print(f"  Port: {config.database.port}")
  print(f"  URL: {config.database.url}")
  print(f"  API Key: {'***' if config.database.api_key else 'NOT SET'}")

  print("\nApp Configuration:")
  print(f"  Name: {config.app.name}")
  print(f"  Environment: {config.app.environment}")

  print("\n" + "=" * 70)
  print("Full configuration:")
  print("=" * 70 + "\n")
  pprint(config)
