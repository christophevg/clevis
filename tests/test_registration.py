"""Tests for dynamic field registration.

This module tests the register_field() function which enables plugin architectures
to inject configuration fields at runtime.
"""

import tempfile
from dataclasses import dataclass, field, fields
from pathlib import Path

import pytest

from clevis import (
  configclass,
  get_config,
  get_factory,
  register_field,
  _reset_factories,
  SecurityAction,
)


class TestRegisterField:
  """Tests for register_field() basic functionality."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_register_field_adds_field_to_parent(self):
    """register_field should add a new field to the parent dataclass."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    # Register the field
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    # Verify field was added
    field_names = [f.name for f in fields(ToolsConfig)]
    assert "pkgq" in field_names
    assert "list" in field_names

  def test_register_field_with_default_factory(self):
    """register_field should use provided default_factory if specified."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    custom_factory_called = []

    def custom_factory():
      custom_factory_called.append(True)
      return PkgqToolConfig(enabled=False)

    # Register with custom factory
    register_field(ToolsConfig, "pkgq", PkgqToolConfig, custom_factory)

    # Create instance
    config = ToolsConfig()
    assert config.pkgq.enabled is False
    assert len(custom_factory_called) == 1

  def test_register_field_default_factory(self):
    """register_field should use field_type as default factory if not provided."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    # Register without custom factory
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    # Create instance
    config = ToolsConfig()
    assert config.pkgq.enabled is True

  def test_register_field_repr_includes_dynamic_field(self):
    """Dynamic fields should appear in __repr__ output."""
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class PkgqToolConfig:
      active: bool = True
      timeout: int = 30

    # Register the field
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    # Create instance
    config = ToolsConfig()

    # Check repr includes both fields
    repr_str = repr(config)
    assert "list=" in repr_str
    assert "pkgq=" in repr_str
    assert "ListToolConfig" in repr_str
    assert "PkgqToolConfig" in repr_str


class TestRegisterFieldErrors:
  """Tests for register_field() error cases."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_frozen_parent_raises_typeerror(self):
    """register_field should raise TypeError for frozen dataclass."""
    _reset_factories()

    @dataclass(frozen=True)
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    with pytest.raises(TypeError, match="frozen dataclass"):
      register_field(ToolsConfig, "pkgq", PkgqToolConfig)

  def test_duplicate_field_raises_valueerror(self):
    """register_field should raise ValueError for duplicate field name."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    # Register once
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    # Try to register again with same name
    @dataclass
    class AnotherToolConfig:
      timeout: int = 30

    with pytest.raises(ValueError, match="already exists"):
      register_field(ToolsConfig, "pkgq", AnotherToolConfig)

  def test_late_registration_raises_runtimeerror(self):
    """register_field should raise RuntimeError if called after get_config() with CLI."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    # Load config with CLI - this configures the parser
    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,  # Enable CLI parsing
      args=[],  # No args needed
    )

    # Try to register after get_config with CLI
    with pytest.raises(RuntimeError, match="after get_config"):
      register_field(Config, "pkgq", PkgqToolConfig)


class TestRegisterFieldTOML:
  """Tests for TOML loading with registered fields."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_toml_loads_registered_field(self):
    """TOML should load into registered field correctly."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class Config:
      name: str = "myapp"
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True
      cache_directory: str = "~/.cache/pkgq"

    # Register before loading
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    # Create TOML file
    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        """
name = "testapp"
[tools]
list = "custom"

[tools.pkgq]
enabled = false
cache_directory = "/custom/cache"
"""
      )

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

        assert config.name == "testapp"
        assert config.tools.list == "custom"
        assert config.tools.pkgq.enabled is False
        assert config.tools.pkgq.cache_directory == "/custom/cache"
      finally:
        os.chdir(original_dir)


class TestRegisterFieldCLI:
  """Tests for CLI argument generation with registered fields."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_cli_args_for_registered_field(self):
    """CLI should generate arguments for registered fields."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class Config:
      name: str = "myapp"
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True
      timeout: int = 30

    # Register before loading
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    # Test CLI args
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

    assert config.tools.pkgq.enabled is True
    assert config.tools.pkgq.timeout == 60


class TestRegisterFieldBackwardCompatibility:
  """Tests for backward compatibility with existing code."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_existing_configclass_works_unchanged(self):
    """Existing @configclass patterns should work without changes."""
    _reset_factories()

    @configclass
    class DatabaseConfig:
      host: str = "localhost"
      port: int = 5432

    @configclass
    class Config:
      name: str = "myapp"
      database: DatabaseConfig = field(default_factory=DatabaseConfig)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=False,
    )

    assert config.name == "myapp"
    assert config.database.host == "localhost"
    assert config.database.port == 5432

  def test_nested_dataclasses_without_registration_work(self):
    """Nested dataclasses should work without dynamic registration."""
    _reset_factories()

    @dataclass
    class DatabaseConfig:
      host: str = "localhost"

    @dataclass
    class Config:
      database: DatabaseConfig = field(default_factory=DatabaseConfig)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=False,
    )

    assert config.database.host == "localhost"

  def test_subcommands_work_unchanged(self):
    """Subcommands should work without changes."""
    _reset_factories()

    @configclass(cmd="check")
    class CheckConfig:
      verbose: bool = False

    @configclass(cmd="run")
    class RunConfig:
      name: str = "default"

    # Test check subcommand
    config = get_config(
      CheckConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["check", "--verbose"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.verbose is True

    # Test run subcommand
    config = get_config(
      RunConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["run", "--name", "custom"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.name == "custom"


class TestRegisterFieldMultipleRegistrations:
  """Tests for multiple dynamic field registrations."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_multiple_fields_same_parent(self):
    """Multiple fields can be registered to the same parent."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    @dataclass
    class GitToolConfig:
      enabled: bool = True

    # Register multiple fields
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)
    register_field(ToolsConfig, "git", GitToolConfig)

    # Verify both were added
    field_names = [f.name for f in fields(ToolsConfig)]
    assert "pkgq" in field_names
    assert "git" in field_names
    assert "list" in field_names

    # Create instance
    config = ToolsConfig()
    assert config.pkgq.enabled is True
    assert config.git.enabled is True

  def test_fields_different_parents(self):
    """Fields can be registered to different parents."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class AgentsConfig:
      default: str = "default"

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    @dataclass
    class PkgqAgentConfig:
      max_results: int = 10

    # Register to different parents
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)
    register_field(AgentsConfig, "pkgq", PkgqAgentConfig)

    # Verify both were added
    tools_fields = [f.name for f in fields(ToolsConfig)]
    agents_fields = [f.name for f in fields(AgentsConfig)]

    assert "pkgq" in tools_fields
    assert "pkgq" in agents_fields

  def test_same_type_different_parents(self):
    """Same type can be registered to different parents."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      list: str = "default"

    @dataclass
    class AgentsConfig:
      default: str = "default"

    @dataclass
    class CommonConfig:
      enabled: bool = True

    # Register same type to different parents
    register_field(ToolsConfig, "common", CommonConfig)
    register_field(AgentsConfig, "common", CommonConfig)

    # Verify both were added
    config = ToolsConfig()
    assert config.common.enabled is True

    config = AgentsConfig()
    assert config.common.enabled is True
