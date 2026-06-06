"""
Example usage of the clevis configuration module.

Run with:
    uv run python nested.py
    ENV=test uv run python nested.py
"""

from dataclasses import dataclass, field

from rich.pretty import pprint

from clevis import SecurityAction, configclass, get_config


@dataclass
class Settings:
  x : int = 0
  y : int = 0

@dataclass
class Tool:
  settings : Settings = field(default_factory=Settings)

@configclass
class AppConfig:
  name: str | None = None
  tool : Tool = field(default_factory=Tool)

if __name__ == "__main__":
  config = get_config(
    AppConfig,
    security={
      "file_permissions": SecurityAction.DONT_CHECK,
      "directory_permissions": SecurityAction.DONT_CHECK
    },
    name = "nested"
  )
  pprint(config)
