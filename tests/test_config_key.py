"""Tests for config= parameter in @configclass decorator.

This feature allows specifying a TOML extraction key independently from the CLI command name.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from clevis import (
  configclass,
  get_config,
  get_factory,
  _reset_factories,
  SecurityAction,
)


class TestConfigKey:
  """Tests for config parameter in @configclass."""

  def test_config_with_cmd_different_names(self):
    """config and cmd can have different names for CLI and TOML."""
    _reset_factories()

    @configclass(cmd="print", config="output")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # TOML uses [output] section, not [print]
      config_file.write_text("[output]\nrich = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],  # CLI uses 'print' command
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)

  def test_config_without_cmd_raises_error(self):
    """config without cmd should raise ValueError."""
    _reset_factories()

    with pytest.raises(ValueError) as exc_info:

      @configclass(config="output")
      class OutputConfig:
        rich: bool = False

    assert "config' requires 'cmd'" in str(exc_info.value)

  def test_cmd_without_config_backward_compatible(self):
    """cmd without config should use cmd for TOML extraction (backward compatible)."""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Uses [print] section (cmd name)
      config_file.write_text("[print]\nrich = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)

  def test_config_and_cmd_same_value(self):
    """Setting config and cmd to same value should work (explicit but equivalent to default)."""
    _reset_factories()

    @configclass(cmd="print", config="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\nrich = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)

  def test_inheritance_with_config(self):
    """config parameter should work with inheritance."""
    _reset_factories()

    @dataclass
    class BaseConfig:
      verbose: bool = False

    @configclass(cmd="print", config="output")
    class PrintConfig(BaseConfig):
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[output]\nrich = true\nverbose = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
        assert config.verbose is True
      finally:
        os.chdir(original_dir)

  def test_multiple_commands_same_toml_section(self):
    """Multiple commands can share same TOML section using config parameter."""
    _reset_factories()

    @configclass(cmd="print", config="display")
    class PrintConfig:
      rich: bool = False

    @configclass(cmd="show", config="display")
    class ShowConfig:
      color: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Both commands use [display] section
      config_file.write_text("[display]\nrich = true\ncolor = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)

        # Load print config
        print_config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert print_config.rich is True

        # Load show config
        show_config = get_config(
          ShowConfig,
          name="test",
          user=False,
          project=True,
          args=["show"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert show_config.color is True
      finally:
        os.chdir(original_dir)

  def test_config_missing_toml_section_uses_defaults(self):
    """Missing config section should use defaults."""
    _reset_factories()

    @configclass(cmd="print", config="output")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Write a different section, not [output]
      config_file.write_text("[other]\nvalue = 42\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Should use default value since [output] section doesn't exist
        assert config.rich is False
      finally:
        os.chdir(original_dir)

  def test_config_with_nested_fields(self):
    """config parameter should work with nested fields."""
    _reset_factories()

    @dataclass
    class Database:
      host: str = "localhost"
      port: int = 5432

    @configclass(cmd="print", config="output")
    class PrintConfig:
      rich: bool = False
      database: Database = None  # type: ignore

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        '[output]\nrich = true\n[output.database]\nhost = "db.example.com"\nport = 3306\n'
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
        assert config.database.host == "db.example.com"
        assert config.database.port == 3306
      finally:
        os.chdir(original_dir)

  def test_config_not_table_raises_error(self):
    """config section must be a table, not a scalar value."""
    _reset_factories()

    @configclass(cmd="print", config="output")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # output is a scalar, not a table
      config_file.write_text('output = "not a table"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        with pytest.raises(Exception):  # ConfigError or similar
          get_config(
            PrintConfig,
            name="test",
            user=False,
            project=True,
            args=["print"],
            security={
              "file_permissions": SecurityAction.DONT_CHECK,
              "directory_permissions": SecurityAction.DONT_CHECK,
            },
          )
      finally:
        os.chdir(original_dir)

  def test_factory_has_config_attribute(self):
    """Factory should have config attribute initialized to None."""
    _reset_factories()

    from dataclasses import fields

    @dataclass
    class TestConfig:
      name: str = "test"

    factory = get_factory(TestConfig)
    # Check that config attribute exists
    assert hasattr(factory, "config")

  def test_config_parameter_stored_in_factory(self):
    """config parameter should be stored in Factory instance."""
    _reset_factories()

    @configclass(cmd="test", config="mysection")
    class TestConfig:
      name: str = "test"

    factory = get_factory(TestConfig)
    assert factory.config == "mysection"
