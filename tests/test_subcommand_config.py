"""Tests for subcommand config extraction from TOML sections."""

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


class TestSubcommandConfig:
  """Tests for subcommand config extraction from TOML sections."""

  def test_subcommand_loads_from_matching_toml_section(self):
    """Subcommand config should extract its section from TOML."""
    _reset_factories()

    @configclass(cmd="print")
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
          args=["print"],  # Subcommand is required
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)

  def test_subcommand_cli_overrides_toml(self):
    """CLI args should override TOML values."""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\nrich = false\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Note: --rich is a store_true action, so presence sets it to True
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print", "--rich"],  # Subcommand + flag
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)

  def test_subcommand_missing_toml_section_uses_defaults(self):
    """Use defaults when section missing."""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Write a different section, not [print]
      config_file.write_text("[other]\nvalue = 42\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],  # Subcommand is required
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Should use default value since [print] section doesn't exist
        assert config.rich is False
      finally:
        os.chdir(original_dir)

  def test_subcommand_with_nested_fields(self):
    """Handle nested fields correctly."""
    _reset_factories()

    @dataclass
    class Database:
      host: str = "localhost"
      port: int = 5432

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False
      database: Database = None  # type: ignore

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        '[print]\nrich = true\n[print.database]\nhost = "db.example.com"\nport = 3306\n'
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],  # Subcommand is required
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

  def test_non_subcommand_ignores_extraction(self):
    """Non-subcommand config should not extract."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Regular flat config, not a subcommand
      config_file.write_text('name = "from_toml"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.name == "from_toml"
      finally:
        os.chdir(original_dir)

  def test_cmd_and_prefix_raises_error_at_configure(self):
    """Setting both cmd and prefix should raise ValueError."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    # Create factory with both cmd and prefix
    factory = get_factory(Config)
    factory.cmd = "print"
    factory.prefix = "app"

    # Should raise when trying to configure
    with pytest.raises(ValueError, match="Cannot set both 'cmd' and 'prefix'"):
      factory.configure_parser()

  def test_cmd_without_prefix_works(self):
    """Config with only cmd should work."""
    _reset_factories()

    @configclass(cmd="print")
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
          args=["print"],  # Subcommand is required
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)

  def test_prefix_without_cmd_works(self):
    """Config with only prefix should work."""
    _reset_factories()

    from dataclasses import field

    @dataclass
    class Config:
      name: str = "default"

    # Set prefix manually
    factory = get_factory(Config)
    factory.prefix = "app"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('[app]\nname = "from_toml"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Note: This test verifies that prefix-only works (existing behavior)
        # The extraction logic doesn't apply here since prefix is for CLI args,
        # not TOML section extraction
        assert config.name == "default"
      finally:
        os.chdir(original_dir)

  def test_multiple_subcommands_load_independently(self):
    """Each subcommand loads its own section."""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    @configclass(cmd="check")
    class CheckConfig:
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\nrich = true\n[check]\nverbose = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)

        # Load print config
        print_config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],  # Subcommand is required
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert print_config.rich is True

        # Load check config
        check_config = get_config(
          CheckConfig,
          name="test",
          user=False,
          project=True,
          args=["check"],  # Subcommand is required
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert check_config.verbose is True
      finally:
        os.chdir(original_dir)

  def test_global_and_subcommand_are_independent(self):
    """Global config and subcommand config load independently."""
    _reset_factories()

    import argparse
    from dataclasses import field

    # Use separate parsers to avoid conflict between subcommand and non-subcommand configs
    global_parser = argparse.ArgumentParser()
    subcommand_parser = argparse.ArgumentParser()

    @dataclass
    class GlobalConfig:
      app_name: str = "myapp"

    # Register GlobalConfig with its own parser (no subcommand)
    from clevis import Factory

    factory_global = Factory(GlobalConfig, parser=global_parser)

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    # Manually set the parser for PrintConfig
    factory_print = get_factory(PrintConfig)
    factory_print.parser = subcommand_parser

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('app_name = "global_app"\n[print]\nrich = true\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)

        # Global config loads without extraction
        global_config = get_config(
          GlobalConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert global_config.app_name == "global_app"

        # Print config extracts [print] section
        print_config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],  # Subcommand is required
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert print_config.rich is True
      finally:
        os.chdir(original_dir)

  def test_boolean_flag_absent_uses_toml_value(self):
    """Absent boolean flag should use TOML value."""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\nrich = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # No --rich CLI flag - should use TOML value
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print"],  # Subcommand only, no --rich flag
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)

  def test_boolean_flag_present_overrides_toml(self):
    """Present boolean flag should override TOML."""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # TOML has rich=false
      config_file.write_text("[print]\nrich = false\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # CLI has --rich flag which sets it to True (store_true action)
        config = get_config(
          PrintConfig,
          name="test",
          user=False,
          project=True,
          args=["print", "--rich"],  # Subcommand + flag
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.rich is True
      finally:
        os.chdir(original_dir)
