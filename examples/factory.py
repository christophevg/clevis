"""
Shared configuration parser with factory pattern.

This example demonstrates how to use clevis factories to share a single
argument parser across multiple configuration classes. This is essential when
building applications with multiple components that each need their own
configuration, but you want a unified command-line interface with --help
showing all options at once.

The factory pattern allows:
- Prefixing configuration fields to avoid name collisions
- Sharing a single parser across multiple config classes
- Configuring external packages that use clevis internally

Features demonstrated:
- get_factory() to access configuration factories
- Setting field prefixes for namespace isolation
- Sharing argparse.ArgumentParser across configs
- Configuration loading order (app1 before app2)
- Multi-package configuration coordination

Run with:
    uv run python factory.py --help
    uv run python factory.py --app1-name "custom name" --app2-name "other" --verbose

Example TOML file (factory.toml or .factory.toml):
    verbose = true

    [app1]
    name = "app1 from toml"

    [app2]
    name = "app2 from toml"

Example output:
    % uv run python factory.py --app2-name "cli > name" --verbose
    App1Config(name='app1.toml > name')
    App2Config(name='cli > name')
"""

import argparse

from clevis import configclass, get_config, get_factory, SecurityAction


# Our own configuration (no prefix needed)
@configclass
class MyConfig:
  """Application-wide configuration."""
  verbose: bool = False


# External packages providing App1 and App2 classes, each with clevis config

@configclass
class App1Config:
  """Configuration for App1 package."""
  name: str | None = None


@configclass
class App2Config:
  """Configuration for App2 package."""
  name: str | None = None


class App1:
  """Example application component with its own configuration.

  This demonstrates how an external package would use clevis
  to load its configuration independently.
  """

  def __init__(self):
    # Load configuration with package-specific name
    # This creates a factory if it doesn't exist
    self.config: App1Config = get_config(
      App1Config,
      name="app1",
      security={
        "file_permissions": SecurityAction.LOG,
        "directory_permissions": SecurityAction.LOG,
      },
    )

  def __str__(self):
    return str(self.config)


class App2:
  """Another application component with its own configuration."""

  def __init__(self):
    self.config: App2Config = get_config(
      App2Config,
      security={
        "file_permissions": SecurityAction.LOG,
        "directory_permissions": SecurityAction.LOG,
      },
    )

  def __str__(self):
    return str(self.config)


# Configure factories for App1Config and App2Config
# Apply prefixes to avoid config argument collisions between the two apps
# This ensures CLI args become --app1-name and --app2-name instead of ambiguous --name
get_factory(App1Config).prefix = "app1"
get_factory(App2Config).prefix = "app2"

# Create a shared parser for all configurations
# This ensures --help shows all options from all configs
parser = argparse.ArgumentParser(description="My Factory Parser")
get_factory(App1Config).parser = parser
get_factory(App2Config).parser = parser
get_factory(MyConfig).parser = parser

# Initialize both applications
# - Each loads its configuration using auto-discovery (user/project)
# - Since we created a factory for their configuration, they use it
# - The first get_config() call resolves CLI args
app1 = App1()  # Would stop here on --help
app2 = App2()

# Display configurations if verbose mode is enabled
if get_config(
  MyConfig,
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
).verbose:
  print(app1)
  print(app2)