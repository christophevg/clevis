"""
Example demonstrating dynamic field registration for plugin architectures.

This example shows how to use register_field() to add configuration fields
to dataclasses at runtime, enabling plugin systems to inject their own
configuration sections.

Run with:
    uv run python dynamic.py
    uv run python dynamic.py --help
    uv run python dynamic.py --tools-pkgq-enabled --tools-pkgq-timeout 60
"""

from dataclasses import dataclass, field
from pathlib import Path
import tempfile

from clevis import (
  configclass,
  get_config,
  register_field,
  _reset_factories,
  SecurityAction,
)


def example_basic_registration():
  """Demonstrate basic dynamic field registration.

  This shows the simplest use case: adding a field to a parent config.
  """
  print("=" * 70)
  print("Example 1: Basic Dynamic Field Registration")
  print("=" * 70)

  # Reset factories to ensure clean state
  _reset_factories()

  # Parent config (must NOT be frozen)
  @dataclass
  class ToolsConfig:
    """Container for tool configurations."""
    list: str = "default"

  # Plugin config to be registered
  @dataclass
  class PkgqToolConfig:
    """Configuration for pkgq tool plugin."""
    enabled: bool = True
    cache_directory: str = "~/.cache/pkgq"
    timeout: int = 30

  # Register the plugin's config as a field
  print("\nRegistering pkgq field...")
  register_field(ToolsConfig, "pkgq", PkgqToolConfig)

  # Create an instance - the field is now available
  config = ToolsConfig()
  print(f"✓ ToolsConfig now has pkgq field: {config.pkgq}")
  print(f"  - enabled: {config.pkgq.enabled}")
  print(f"  - cache_directory: {config.pkgq.cache_directory}")
  print(f"  - timeout: {config.pkgq.timeout}")

  print("\n✓ Basic registration complete\n")


def example_toml_loading():
  """Demonstrate TOML configuration loading for registered fields.

  This shows how registered fields integrate with TOML file loading.
  """
  print("=" * 70)
  print("Example 2: TOML Configuration Loading")
  print("=" * 70)

  _reset_factories()

  # Define configs
  @dataclass
  class ToolsConfig:
    list: str = "default"

  @dataclass
  class PkgqToolConfig:
    enabled: bool = True
    cache_directory: str = "~/.cache/pkgq"

  @dataclass
  class Config:
    name: str = "myapp"
    tools: ToolsConfig = field(default_factory=ToolsConfig)

  # Register before loading
  register_field(ToolsConfig, "pkgq", PkgqToolConfig)

  # Create a temporary TOML file
  with tempfile.TemporaryDirectory() as tmpdir:
    config_file = Path(tmpdir) / "test.toml"
    config_file.write_text(
      """
# Application configuration
name = "TestApp"

[tools]
list = "custom-value"

# Plugin configuration - this section is now recognized
[tools.pkgq]
enabled = false
cache_directory = "/custom/cache"
"""
    )

    print(f"\nCreated TOML file at: {config_file}")
    print(f"Content:\n{config_file.read_text()}")

    # Load configuration from TOML
    import os

    original_dir = os.getcwd()
    try:
      os.chdir(tmpdir)
      config = get_config(
        Config,
        name="test",
        user=False,
        project=True,
        cli=False,
        security={
          "file_permissions": SecurityAction.DONT_CHECK,
          "directory_permissions": SecurityAction.DONT_CHECK,
        },
      )

      print("\n✓ Configuration loaded from TOML:")
      print(f"  - name: {config.name}")
      print(f"  - tools.list: {config.tools.list}")
      print(f"  - tools.pkgq.enabled: {config.tools.pkgq.enabled}")
      print(f"  - tools.pkgq.cache_directory: {config.tools.pkgq.cache_directory}")

    finally:
      os.chdir(original_dir)

  print("\n✓ TOML loading complete\n")


def example_cli_arguments():
  """Demonstrate CLI argument generation for registered fields.

  This shows how registered fields generate CLI arguments.
  """
  print("=" * 70)
  print("Example 3: CLI Argument Generation")
  print("=" * 70)

  _reset_factories()

  # Define configs
  @dataclass
  class ToolsConfig:
    list: str = "default"

  @dataclass
  class PkgqToolConfig:
    enabled: bool = False
    timeout: int = 30
    cache_directory: str = "~/.cache"

  @dataclass
  class Config:
    name: str = "myapp"
    tools: ToolsConfig = field(default_factory=ToolsConfig)

  # Register before loading
  register_field(ToolsConfig, "pkgq", PkgqToolConfig)

  print("\nRegistered fields generate CLI arguments with nested names:")
  print("  --tools-pkgq-enabled")
  print("  --tools-pkgq-timeout")
  print("  --tools-pkgq-cache-directory")

  # Load config with CLI args
  config = get_config(
    Config,
    name="test",
    user=False,
    project=False,
    cli=True,
    args=["--tools-pkgq-enabled", "--tools-pkgq-timeout", "60"],
    security={
      "file_permissions": SecurityAction.DONT_CHECK,
      "directory_permissions": SecurityAction.DONT_CHECK,
    },
  )

  print("\n✓ Configuration loaded with CLI args:")
  print(f"  - tools.pkgq.enabled: {config.tools.pkgq.enabled}")
  print(f"  - tools.pkgq.timeout: {config.tools.pkgq.timeout}")
  print(f"  - tools.pkgq.cache_directory: {config.tools.pkgq.cache_directory}")

  print("\n✓ CLI argument generation complete\n")


def example_error_handling():
  """Demonstrate error handling for registration failures.

  This shows the three main error cases.
  """
  print("=" * 70)
  print("Example 4: Error Handling")
  print("=" * 70)

  _reset_factories()

  # Error 1: Frozen parent
  print("\nError 1: Frozen Parent")
  print("-" * 70)

  @dataclass(frozen=True)
  class FrozenConfig:
    name: str = "default"

  @dataclass
  class PluginConfig:
    enabled: bool = True

  try:
    register_field(FrozenConfig, "plugin", PluginConfig)
    print("ERROR: Should have raised TypeError!")
  except TypeError as e:
    print(f"✓ Caught TypeError: {e}")

  # Error 2: Duplicate field name
  print("\nError 2: Duplicate Field Name")
  print("-" * 70)

  @dataclass
  class ConfigWithFields:
    existing_field: str = "value"

  @dataclass
  class NewConfig:
    value: int = 10

  register_field(ConfigWithFields, "new_field", NewConfig)

  try:
    register_field(ConfigWithFields, "new_field", NewConfig)
    print("ERROR: Should have raised ValueError!")
  except ValueError as e:
    print(f"✓ Caught ValueError: {e}")

  # Error 3: Late registration
  print("\nError 3: Late Registration (after get_config with CLI)")
  print("-" * 70)

  _reset_factories()

  @dataclass
  class Config:
    name: str = "default"

  @dataclass
  class LatePlugin:
    enabled: bool = True

  # Load config with CLI - this configures the parser
  config = get_config(
    Config,
    name="test",
    user=False,
    project=False,
    cli=True,
    args=[],
  )

  try:
    register_field(Config, "plugin", LatePlugin)
    print("ERROR: Should have raised RuntimeError!")
  except RuntimeError as e:
    print(f"✓ Caught RuntimeError: {e}")

  print("\n✓ Error handling complete\n")


def example_plugin_pattern():
  """Demonstrate a realistic plugin architecture pattern.

  This shows how a plugin system would use dynamic registration.
  """
  print("=" * 70)
  print("Example 5: Plugin Architecture Pattern")
  print("=" * 70)

  _reset_factories()

  # Main application config (NOT frozen to allow plugin registration)
  @dataclass
  class ToolsConfig:
    """Container for tool configurations."""
    list: str = "default"
    read: str = "default"

  @dataclass
  class AgentsConfig:
    """Container for agent configurations."""
    default: str = "default"

  @dataclass
  class AppConfig:
    """Main application configuration."""
    name: str = "myapp"
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)

  # Plugin definitions (could be in separate modules)
  @dataclass
  class PkgqToolConfig:
    """Pkgq tool configuration."""
    enabled: bool = True
    cache_directory: str = "~/.cache/pkgq"
    timeout: int = 30

  @dataclass
  class PkgqAgentConfig:
    """Pkgq agent configuration."""
    max_results: int = 10
    include_prerelease: bool = False

  @dataclass
  class GitToolConfig:
    """Git tool configuration."""
    enabled: bool = True
    timeout: int = 60

  # Plugin loader (simulates plugin discovery and registration)
  def load_plugins():
    """Load and register all plugins.

    In a real application, this would:
    1. Discover plugin packages
    2. Import their config classes
    3. Register them with the appropriate parent config
    """
    print("\nLoading plugins...")

    # Register pkgq plugin
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)
    print("  ✓ Registered pkgq tool config")

    register_field(AgentsConfig, "pkgq", PkgqAgentConfig)
    print("  ✓ Registered pkgq agent config")

    # Register git plugin
    register_field(ToolsConfig, "git", GitToolConfig)
    print("  ✓ Registered git tool config")

  # Load plugins before loading config
  load_plugins()

  # Create configuration with plugins
  config = AppConfig()
  print("\n✓ Application configuration with plugins:")
  print(f"  - name: {config.name}")
  print(f"  - tools.list: {config.tools.list}")
  print(f"  - tools.pkgq.enabled: {config.tools.pkgq.enabled}")
  print(f"  - tools.pkgq.cache_directory: {config.tools.pkgq.cache_directory}")
  print(f"  - tools.git.enabled: {config.tools.git.enabled}")
  print(f"  - agents.default: {config.agents.default}")
  print(f"  - agents.pkgq.max_results: {config.agents.pkgq.max_results}")

  print("\n✓ Plugin pattern complete\n")


def example_with_toml_and_cli():
  """Demonstrate complete workflow with TOML and CLI overrides.

  This shows the full integration: plugins + TOML + CLI arguments.
  """
  print("=" * 70)
  print("Example 6: Complete Workflow (Plugins + TOML + CLI)")
  print("=" * 70)

  _reset_factories()

  # Define configs
  @dataclass
  class ToolsConfig:
    list: str = "default"

  @dataclass
  class PkgqToolConfig:
    enabled: bool = True
    timeout: int = 30
    cache_directory: str = "~/.cache/pkgq"

  @dataclass
  class GitToolConfig:
    enabled: bool = True
    timeout: int = 60

  @dataclass
  class Config:
    name: str = "myapp"
    tools: ToolsConfig = field(default_factory=ToolsConfig)

  # Register plugins
  register_field(ToolsConfig, "pkgq", PkgqToolConfig)
  register_field(ToolsConfig, "git", GitToolConfig)

  # Create TOML with plugin configuration
  with tempfile.TemporaryDirectory() as tmpdir:
    config_file = Path(tmpdir) / "app.toml"
    config_file.write_text(
      """
name = "MyApp"

[tools]
list = "from-toml"

[tools.pkgq]
enabled = true
timeout = 45
cache_directory = "/custom/cache"

[tools.git]
enabled = false
timeout = 120
"""
    )

    print(f"\nCreated TOML file:")
    print(config_file.read_text())

    # Load with CLI overrides
    import os

    original_dir = os.getcwd()
    try:
      os.chdir(tmpdir)
      config = get_config(
        Config,
        name="app",
        user=False,
        project=True,
        cli=True,
        args=["--tools-pkgq-timeout", "90"],  # CLI overrides TOML
        security={
          "file_permissions": SecurityAction.DONT_CHECK,
          "directory_permissions": SecurityAction.DONT_CHECK,
        },
      )

      print("✓ Configuration loaded with TOML + CLI:")
      print(f"  - name: {config.name} (from TOML)")
      print(f"  - tools.list: {config.tools.list} (from TOML)")
      print(f"  - tools.pkgq.enabled: {config.tools.pkgq.enabled} (from TOML)")
      print(f"  - tools.pkgq.timeout: {config.tools.pkgq.timeout} (CLI override!)")
      print(f"  - tools.pkgq.cache_directory: {config.tools.pkgq.cache_directory} (from TOML)")
      print(f"  - tools.git.enabled: {config.tools.git.enabled} (from TOML)")
      print(f"  - tools.git.timeout: {config.tools.git.timeout} (from TOML)")

    finally:
      os.chdir(original_dir)

  print("\n✓ Complete workflow demonstration complete\n")


def main():
  """Run all examples."""
  print("\n" + "=" * 70)
  print("Dynamic Field Registration Examples")
  print("=" * 70)
  print("\nThis demonstrates the register_field() function for plugin architectures.")
  print("Plugins can inject their own configuration sections at runtime.\n")

  # Run all examples
  example_basic_registration()
  example_toml_loading()
  example_cli_arguments()
  example_error_handling()
  example_plugin_pattern()
  example_with_toml_and_cli()

  print("=" * 70)
  print("All examples completed successfully!")
  print("=" * 70)
  print("\nKey Takeaways:")
  print("1. Use @dataclass (NOT frozen=True) for parent configs")
  print("2. Call register_field() before get_config()")
  print("3. TOML sections follow the hierarchy: [parent.field]")
  print("4. CLI args use dashed names: --parent-field-option")
  print("5. Plugins can register to multiple parent configs")
  print("\n")


if __name__ == "__main__":
  main()