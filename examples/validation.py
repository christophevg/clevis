"""Custom validation in Clevis configurations.

Demonstrates how to validate configuration values using __post_init__
and provide helpful error messages when validation fails.

Features demonstrated:
- URL validation with regex
- Range validation for numeric values
- Required field validation
- Type coercion
- Custom error messages

Run with:
    uv run python validation.py --help
    uv run python validation.py --server-url "http://localhost:8080"

Example TOML file (validation.toml):
    [server]
    url = "https://api.example.com"
    port = 8080
    timeout_seconds = 30

    [features]
    max_connections = 100
    debug = false
"""

import argparse
import re
from dataclasses import dataclass, field

from rich.pretty import pprint

from clevis import ConfigError, SecurityAction, configclass, get_config, get_factory


@dataclass
class ServerConfig:
  """Server configuration with URL and port validation."""

  url: str | None = None
  port: int | None = None
  timeout_seconds: int = 30

  def __post_init__(self) -> None:
    """Validate server configuration after initialization."""
    # Validate URL if provided
    if self.url is not None:
      self._validate_url(self.url)

    # Validate port range
    if self.port is not None:
      self._validate_port_range(self.port)

    # Validate timeout range
    self._validate_timeout_range(self.timeout_seconds)

  def _validate_url(self, url: str) -> None:
    """Validate URL format using regex."""
    # URL pattern: scheme://host[:port][/path][?query][#fragment]
    url_pattern = re.compile(
      r"^https?://"  # http:// or https://
      r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
      r"localhost|"  # localhost
      r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP address
      r"(?::\d+)?"  # optional port
      r"(?:/?|[/?]\S+)$",
      re.IGNORECASE,
    )

    if not url_pattern.match(url):
      raise ConfigError(
        message=f"Invalid URL format: '{url}'. Must be http:// or https:// with valid host.",
        field_path="server.url",
        config_name="validation",
        suggest_cli=True,
      )

  def _validate_port_range(self, port: int) -> None:
    """Validate port is in valid range."""
    if not (1 <= port <= 65535):
      raise ConfigError(
        message=f"Port {port} out of range. Must be between 1 and 65535.",
        field_path="server.port",
        config_name="validation",
        suggest_cli=True,
      )

  def _validate_timeout_range(self, timeout: int) -> None:
    """Validate timeout is positive."""
    if timeout < 1:
      raise ConfigError(
        message=f"Timeout {timeout} must be at least 1 second.",
        field_path="server.timeout_seconds",
        config_name="validation",
        suggest_cli=True,
      )


@dataclass
class FeaturesConfig:
  """Feature flags with validation."""

  max_connections: int = 10
  debug: bool = False

  def __post_init__(self) -> None:
    """Validate features configuration."""
    self._validate_max_connections(self.max_connections)

  def _validate_max_connections(self, max_conn: int) -> None:
    """Validate max_connections is within reasonable bounds."""
    if not (1 <= max_conn <= 10000):
      raise ConfigError(
        message=f"max_connections {max_conn} must be between 1 and 10000.",
        field_path="features.max_connections",
        config_name="validation",
        suggest_cli=True,
      )


@dataclass
class RequiredConfig:
  """Configuration with required fields."""

  api_key: str  # Required - no default
  api_endpoint: str = "https://api.example.com"

  def __post_init__(self) -> None:
    """Validate required fields are present."""
    # Validate API key is not empty
    if not self.api_key or not self.api_key.strip():
      raise ConfigError(
        message="API key cannot be empty.",
        field_path="api_key",
        config_name="validation",
        suggest_cli=True,
      )


@configclass
class AppConfig:
  """Application configuration demonstrating various validation patterns."""

  # Required field - must be provided
  app_name: str

  # Optional nested configurations
  server: ServerConfig = field(default_factory=ServerConfig)
  features: FeaturesConfig = field(default_factory=FeaturesConfig)


def create_parser() -> argparse.ArgumentParser:
  """Create argument parser for the example."""
  parser = argparse.ArgumentParser(
    description="Clevis validation example",
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  return parser


if __name__ == "__main__":
  # Set up parser for all config classes
  parser = create_parser()
  get_factory(AppConfig).parser = parser

  # Load configuration from validation.toml with security checks
  config = get_config(
    AppConfig,
    name="validation",  # Use validation.toml instead of default project.toml
    security={
      "file_permissions": SecurityAction.LOG,
      "directory_permissions": SecurityAction.LOG,
    },
  )

  print("\n✓ Configuration loaded successfully!")
  print("\nConfiguration values:")
  pprint(config)

