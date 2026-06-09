"""Plugin registration example for Clevis.

Demonstrates how a plugin module can register its configuration
into an existing application config at runtime.
"""

from dataclasses import dataclass, field

from clevis import SecurityAction, get_config, register_field


# Plugin module defines its configuration
@dataclass
class PkgqToolConfig:
  """Plugin tool configuration for package queries."""

  active: bool = True
  timeout: int = 30


# Built-in tool configuration
@dataclass
class ListToolConfig:
  """Built-in list tool configuration."""

  enabled: bool = True
  format: str = "table"


# Application defines its ToolsConfig (non-frozen for plugin registration)
@dataclass  # NOT frozen - allows dynamic registration
class ToolsConfig:
  """Base tools configuration that plugins can extend."""

  list: ListToolConfig = field(default_factory=ListToolConfig)


# Plugin registers itself into ToolsConfig
# This adds ToolsConfig.pkgq field automatically
register_field(ToolsConfig, "pkgq", PkgqToolConfig)

# Application uses the extended config
# TOML: [tools.list] and [tools.pkgq] work seamlessly
# CLI: --list-enabled and --pkgq-timeout work
tools_config = get_config(
  ToolsConfig,
  name="tools",
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
)

if __name__ == "__main__":
  print("List tool config:", tools_config.list)
  print("Pkgq tool config:", tools_config.pkgq)

  print("ToolsConfig:", get_config(ToolsConfig, name="tools"))

"""

Example TOML file (tools.toml):

[tools.list]
enabled = true
format = "json"

[tools.pkgq]
active = true
timeout = 60

Example CLI usage:

% uv run python plugin.py --help
usage: plugin.py [-h] [--list-enabled] [--list-format LIST.FORMAT]
                 [--pkgq-active] [--pkgq-timeout PKGQ.TIMEOUT]

options:
  -h, --help            show this help message and exit
  --list-enabled        provide list.enabled
  --list-format LIST.FORMAT
                        provide list.format
  --pkgq-active         provide pkgq.active
  --pkgq-timeout PKGQ.TIMEOUT
                        provide pkgq.timeout

% uv run python plugin.py --pkgq-timeout 45
List tool config: ListToolConfig(enabled=True, format='table')
Pkgq tool config: PkgqToolConfig(active=True, timeout=45)

"""
