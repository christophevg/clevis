"""
Basic configuration loading with clevis.

This example demonstrates the core functionality of clevis: loading configuration
from multiple sources with automatic type conversion and validation. Configuration
is loaded from environment variables, command-line arguments, and TOML files with
a clear priority order (CLI > environment > TOML > defaults).

Features demonstrated:
- Defining configuration dataclasses with type hints
- Nested configuration objects (database, redis, features)
- Automatic configuration discovery (user/project directories)
- Environment variable support (ENV=test sets environment field)
- Command-line argument parsing (--database-host localhost)
- Security validation for file permissions
- Post-initialization validation with __post_init__

Run with:
    uv run python main.py
    uv run python main.py --help
    ENV=test uv run python main.py --database-host localhost --features-enabled

Example TOML file (app.toml or .app.toml):
    app_name = "MyApp"
    debug = false
    environment = "production"
    server_url = "https://api.example.com"

    [database]
    host = "localhost"
    port = 5432
    user = "admin"
    password = "secret"
    name = "mydb"

    [redis]
    host = "localhost"
    port = 6379

    [features]
    enabled = true
    name = "new-feature"
"""

from dataclasses import dataclass, field

from rich.pretty import pprint

from clevis import get_config, SecurityAction


@dataclass
class DatabaseConfig:
  """Database connection configuration."""
  host: str
  port: int | None = None
  user: str | None = None
  password: str | None = None
  name: str | None = None


@dataclass
class RedisConfig:
  """Redis cache configuration."""
  host: str | None = None
  port: int | None = None


@dataclass
class FeaturesConfig:
  """Feature flags configuration."""
  enabled: bool = False
  name: str | None = None


from urllib.parse import urlparse


@dataclass
class AppConfig:
  """Main application configuration.

  Demonstrates nested configuration objects and post-init validation.
  The __post_init__ method validates server_url format.
  """
  app_name: str | None = None
  debug: bool = True
  environment: str | None = None
  server_url: str | None = None

  database: DatabaseConfig = field(default_factory=DatabaseConfig)
  redis: RedisConfig = field(default_factory=RedisConfig)
  features: FeaturesConfig = field(default_factory=FeaturesConfig)

  def __post_init__(self):
    """Validate configuration after initialization."""
    if self.server_url:
      parsed = urlparse(self.server_url)
      if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid server URL: scheme must be http or https, got {parsed.scheme}")


if __name__ == "__main__":
  # Load configuration with security checks enabled
  # Logs warnings for files with insecure permissions
  config = get_config(
    AppConfig,
    security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
  )
  pprint(config)