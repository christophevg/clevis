"""
Nested configuration objects with clevis.

This example demonstrates how to create configuration hierarchies using
nested dataclasses. Nested configs allow you to organize related settings
into logical groups, with automatic TOML section mapping and CLI argument
namespacing.

The @configclass decorator is only applied to the top-level configuration,
while nested classes are plain dataclasses. Clevis automatically discovers
and processes nested configuration fields.

Features demonstrated:
- Nested configuration dataclasses (AppConfig contains Tool, Tool contains Settings)
- Using @configclass decorator only on top-level config
- field(default_factory=...) for mutable nested defaults
- TOML section nesting ([tool.settings])
- CLI argument nesting (--tool-settings-x)
- Custom configuration name (name="nested")

Run with:
    uv run python nested.py
    uv run python nested.py --help
    uv run python nested.py --tool-settings-x 10 --tool-settings-y 20
    ENV=test uv run python nested.py

Example TOML file (nested.toml or .nested.toml):
    name = "MyApp"

    [tool]
    # Tool-level settings

    [tool.settings]
    # Nested settings at arbitrary depth
    x = 42
    y = 100
"""

from dataclasses import dataclass, field

from rich.pretty import pprint

from clevis import SecurityAction, configclass, get_config


@dataclass
class Settings:
  """Deeply nested configuration for tool settings.

  This demonstrates that nesting can go multiple levels deep.
  """
  x: int = 0
  y: int = 0


@dataclass
class Tool:
  """Middle-level configuration containing another nested config.

  Note: This is a plain @dataclass, not @configclass.
  Only the top-level config needs @configclass.
  """
  settings: Settings = field(default_factory=Settings)


@configclass
class AppConfig:
  """Top-level application configuration.

  The @configclass decorator enables:
  - CLI argument generation
  - TOML file loading
  - Environment variable mapping

  Only the top-level config needs this decorator.
  """
  name: str | None = None
  tool: Tool = field(default_factory=Tool)


if __name__ == "__main__":
  # Load configuration with custom name
  # This looks for nested.toml or .nested.toml instead of appconfig.toml
  config = get_config(
    AppConfig,
    security={
      "file_permissions": SecurityAction.DONT_CHECK,
      "directory_permissions": SecurityAction.DONT_CHECK
    },
    name="nested"
  )

  # Display the loaded configuration
  # Shows how nested values are accessible through the hierarchy
  pprint(config)