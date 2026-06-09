"""Tests for _nested_prefix tracking in config class hierarchy.

This module tests the nested prefix functionality which tracks nesting depth
in config hierarchies and ensures proper CLI argument generation.
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from clevis import (
  configclass,
  get_config,
  get_factory,
  _reset_factories,
  SecurityAction,
)


class TestSimpleNesting:
  """Tests for simple nesting with nested config classes."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_nested_prefix_set_for_nested_config(self):
    """Nested config should have _nested_prefix set."""
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class ModuleConfig:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Get factories
    tools_factory = get_factory(ToolsConfig)
    list_factory = get_factory(ListToolConfig)

    # Configure parser to trigger nested prefix tracking
    config = get_config(
      ModuleConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=[],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefix is set
    assert tools_factory._nested_prefix == "tools"
    assert list_factory._nested_prefix == "tools.list"

  def test_nested_cli_args_format(self):
    """Nested config CLI args should use dotted format."""
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class ModuleConfig:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Test CLI args
    config = get_config(
      ModuleConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-list-enabled", "--tools-list-format", "json"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert config.tools.list.enabled is True
    assert config.tools.list.format == "json"

  def test_get_config_on_nested_config_strips_prefix(self):
    """get_config on nested config should strip the nested prefix."""
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class ModuleConfig:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Load root config first to configure parser
    root_config = get_config(
      ModuleConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-list-enabled", "--tools-list-format", "json"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Now get nested config - should strip "tools." prefix
    tools_config = get_config(
      ToolsConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-list-enabled", "--tools-list-format", "yaml"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert tools_config.list.enabled is True
    assert tools_config.list.format == "yaml"


class TestMultipleLevels:
  """Tests for multi-level nesting."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_three_level_nesting(self):
    """Three levels of nesting should track prefixes correctly."""
    _reset_factories()

    @dataclass
    class Level3Config:
      value: str = "default"

    @dataclass
    class Level2Config:
      level3: Level3Config = field(default_factory=Level3Config)

    @dataclass
    class Level1Config:
      level2: Level2Config = field(default_factory=Level2Config)

    @dataclass
    class RootConfig:
      level1: Level1Config = field(default_factory=Level1Config)

    # Configure parser
    config = get_config(
      RootConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--level1-level2-level3-value", "custom"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefixes
    level1_factory = get_factory(Level1Config)
    level2_factory = get_factory(Level2Config)
    level3_factory = get_factory(Level3Config)

    assert level1_factory._nested_prefix == "level1"
    assert level2_factory._nested_prefix == "level1.level2"
    assert level3_factory._nested_prefix == "level1.level2.level3"

    assert config.level1.level2.level3.value == "custom"


class TestWithPrefixAttribute:
  """Tests for prefix attribute interaction with nested configs."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_prefix_sets_nested_prefix(self):
    """Setting prefix should initialize _nested_prefix."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class App1Config:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Set prefix on root config
    factory = get_factory(App1Config)
    factory.prefix = "app1"

    # Configure parser
    config = get_config(
      App1Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--app1-tools-list", "custom"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefixes
    app1_factory = get_factory(App1Config)
    tools_factory = get_factory(ToolsConfig)

    assert app1_factory._nested_prefix == "app1"
    assert tools_factory._nested_prefix == "app1.tools"

    assert config.tools.list == "custom"

  def test_prefix_affects_cli_only(self):
    """Prefix should only affect CLI args, not TOML loading."""
    _reset_factories()
    import os

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class App1Config:
      name: str = "app1"
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Set prefix
    factory = get_factory(App1Config)
    factory.prefix = "app1"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # TOML should be loaded normally, not from [app1] section
      config_file.write_text('name = "myapp"\n[tools]\nlist = "custom"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          App1Config,
          name="test",
          user=False,
          project=True,
          cli=False,
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Should load from root TOML, not from [app1] section
        assert config.name == "myapp"
        assert config.tools.list == "custom"
      finally:
        os.chdir(original_dir)


class TestWithCmd:
  """Tests for cmd (subcommand) with nested configs."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_cmd_creates_new_root_context(self):
    """cmd should create new root context with _nested_prefix=None."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @configclass(cmd="check")
    class CheckConfig:
      tools: ToolsConfig = field(default_factory=ToolsConfig)
      verbose: bool = False

    # Configure parser
    config = get_config(
      CheckConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["check", "--tools-list", "custom", "--verbose"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefixes
    check_factory = get_factory(CheckConfig)
    tools_factory = get_factory(ToolsConfig)

    # cmd creates new root context, so CheckConfig has None
    assert check_factory._nested_prefix is None
    # ToolsConfig is nested under CheckConfig
    assert tools_factory._nested_prefix == "tools"

    assert config.tools.list == "custom"
    assert config.verbose is True

  def test_cmd_with_nested_config(self):
    """cmd with nested config should have proper prefixes."""
    _reset_factories()

    @dataclass
    class Level3Config:
      value: str = "default"

    @dataclass
    class Level2Config:
      level3: Level3Config = field(default_factory=Level3Config)

    @configclass(cmd="test")
    class TestConfig:
      level2: Level2Config = field(default_factory=Level2Config)

    # Configure parser
    config = get_config(
      TestConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["test", "--level2-level3-value", "custom"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefixes
    test_factory = get_factory(TestConfig)
    level2_factory = get_factory(Level2Config)
    level3_factory = get_factory(Level3Config)

    assert test_factory._nested_prefix is None
    assert level2_factory._nested_prefix == "level2"
    assert level3_factory._nested_prefix == "level2.level3"

    assert config.level2.level3.value == "custom"


class TestWithCmdAndConfig:
  """Tests for cmd + config combination."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_cmd_with_config_parameter(self):
    """cmd with config parameter should work like cmd only for CLI args."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    # Using configclass with cmd and config
    @configclass(cmd="cli", config="client")
    class CliConfig:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Configure parser
    config = get_config(
      CliConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["cli", "--tools-list", "custom"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefixes - should be same as cmd only
    cli_factory = get_factory(CliConfig)
    tools_factory = get_factory(ToolsConfig)

    assert cli_factory._nested_prefix is None
    assert tools_factory._nested_prefix == "tools"

    assert config.tools.list == "custom"


class TestDuplicateDetection:
  """Tests for duplicate config class detection."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_same_config_class_twice_raises_error(self):
    """Using same config class twice should raise ValueError."""
    _reset_factories()

    @dataclass
    class ToolConfig:
      enabled: bool = True

    @dataclass
    class Config:
      tools1: ToolConfig = field(default_factory=ToolConfig)
      tools2: ToolConfig = field(default_factory=ToolConfig)

    # This should raise ValueError because ToolConfig is used twice
    with pytest.raises(ValueError, match="Duplicate config class"):
      config = get_config(
        Config,
        name="test",
        user=False,
        project=False,
        cli=True,
        args=[],
        security={
          "file_permissions": SecurityAction.DONT_CHECK,
          "directory_permissions": SecurityAction.DONT_CHECK,
        },
      )

  def test_different_instances_allowed(self):
    """Different instances of same type should be allowed with distinct subclasses."""
    _reset_factories()

    # Create distinct subclasses to avoid duplication
    @dataclass
    class ToolConfig:
      enabled: bool = True

    @dataclass
    class Tools1Config(ToolConfig):
      pass

    @dataclass
    class Tools2Config(ToolConfig):
      pass

    @dataclass
    class Config:
      tools1: Tools1Config = field(default_factory=Tools1Config)
      tools2: Tools2Config = field(default_factory=Tools2Config)

    # This should work because they are different classes
    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=[],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert config.tools1.enabled is True
    assert config.tools2.enabled is True


class TestDynamicFieldRegistration:
  """Tests for dynamic field registration with nesting."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_register_field_on_nested_config(self):
    """register_field on nested config should update _nested_prefix."""
    _reset_factories()
    from clevis import register_field

    @dataclass
    class ListToolConfig:
      enabled: bool = True

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class PkgqToolConfig:
      active: bool = True

    # Register dynamic field
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    @dataclass
    class RootConfig:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Configure parser
    config = get_config(
      RootConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-pkgq-active"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefix includes dynamic field
    pkgq_factory = get_factory(PkgqToolConfig)
    assert pkgq_factory._nested_prefix == "tools.pkgq"

    assert config.tools.pkgq.active is True


class TestMultipleGetConfigCalls:
  """Tests for multiple get_config calls on same configs."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_root_and_nested_config_calls(self):
    """Multiple get_config calls should work correctly."""
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class RootConfig:
      name: str = "app"
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # First call: root config
    root_config = get_config(
      RootConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--name", "myapp", "--tools-list-format", "json"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert root_config.name == "myapp"
    assert root_config.tools.list.format == "json"

    # Second call: nested config (should strip prefix correctly)
    tools_config = get_config(
      ToolsConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-list-enabled", "--tools-list-format", "yaml"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert tools_config.list.enabled is True
    assert tools_config.list.format == "yaml"

  def test_repeated_calls_same_config(self):
    """Repeated calls to same config should maintain state correctly."""
    _reset_factories()

    @dataclass
    class Config:
      value: str = "default"

    # First call
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--value", "first"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Second call
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--value", "second"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert config1.value == "first"
    assert config2.value == "second"
