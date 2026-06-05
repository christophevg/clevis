"""
Example usage of the clevis configuration module.

Run with:
    uv run python main.py
    ENV=test uv run python main.py --database-host localhost --features-enabled
"""

from dataclasses import dataclass, field

from rich.pretty import pprint

from clevis import get_config


@dataclass
class DatabaseConfig:
  host: str
  port: int | None = None
  user: str | None = None
  password: str | None = None
  name: str | None = None


@dataclass
class RedisConfig:
  host: str | None = None
  port: int | None = None


@dataclass
class FeaturesConfig:
  enabled: bool = False
  name: str | None = None

from urllib.parse import urlparse

@dataclass
class AppConfig:
  app_name: str | None = None
  debug: bool = True
  environment: str | None = None
  server_url: str | None = None

  database: DatabaseConfig = field(default_factory=DatabaseConfig)
  redis: RedisConfig = field(default_factory=RedisConfig)
  features: FeaturesConfig = field(default_factory=FeaturesConfig)

  def __post_init__(self):
    if self.server_url:
      parsed = urlparse(self.server_url)
      if parsed.scheme not in ('http', 'https'):
        raise ValueError(
          f"Invalid server URL: scheme must be http or https, got {parsed.scheme}"
        )

if __name__ == "__main__":
  config = get_config(AppConfig)
  pprint(config)
