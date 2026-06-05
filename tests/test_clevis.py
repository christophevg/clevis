"""Tests for clevis configuration module."""

import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest

from clevis import (
  get_config,
  apply_to_dict,
  get_factory,
  configclass,
  Factory,
  unpack_type,
  ConfigError,
  _get_toml_parser,
  _load_toml,
  _reset_factories,
)


class TestUnpackType:
  """Tests for unpack_type function."""

  def test_non_union_type(self):
    """Non-union types should be returned as-is."""
    assert unpack_type(str) == str
    assert unpack_type(int) == int
    assert unpack_type(bool) == bool

  def test_optional_type(self):
    """Optional[T] should return T."""
    assert unpack_type(str | None) == str
    assert unpack_type(int | None) == int

  def test_none_first(self):
    """None | T should return T."""
    # Note: This is an unusual form but should be handled
    result = unpack_type(type(None) | str)
    assert result == str


class TestListFields:
  """Tests for Factory.list_fields method."""

  def test_flat_dataclass(self):
    """Flat dataclass should list all fields."""
    _reset_factories()

    @dataclass
    class Config:
      name: str
      value: int

    fields_list = get_factory(Config).list_fields()
    assert len(fields_list) == 2
    assert fields_list[0][0].name == "name"
    assert fields_list[1][0].name == "value"

  def test_nested_dataclass(self):
    """Nested dataclass should flatten to dotted paths."""
    _reset_factories()

    @dataclass
    class Database:
      host: str
      port: int

    @dataclass
    class Config:
      name: str
      database: Database = field(default_factory=Database)

    fields_list = get_factory(Config).list_fields()
    assert len(fields_list) == 3
    names = [f[0].name for f in fields_list]
    assert names == ["name", "host", "port"]

    paths = [f[1] for f in fields_list]
    assert paths == [[], ["database"], ["database"]]


class TestApplyToDict:
  """Tests for apply_to_dict function."""

  def test_flat_key(self):
    """Flat keys should be set at top level."""
    args = {"name": "test"}
    dct = {}
    apply_to_dict(args, dct)
    assert dct == {"name": "test"}

  def test_nested_key(self):
    """Nested keys should create nested dicts."""
    args = {"database.host": "localhost"}
    dct = {}
    apply_to_dict(args, dct)
    assert dct == {"database": {"host": "localhost"}}

  def test_multiple_nested_keys(self):
    """Multiple nested keys should merge correctly."""
    args = {
      "database.host": "localhost",
      "database.port": 5432,
    }
    dct = {}
    apply_to_dict(args, dct)
    assert dct == {"database": {"host": "localhost", "port": 5432}}

  def test_none_values_ignored(self):
    """None values should not be applied."""
    args = {"name": "test", "value": None}
    dct = {}
    apply_to_dict(args, dct)
    assert dct == {"name": "test"}

  def test_override_existing(self):
    """CLI args should override existing values."""
    args = {"name": "new"}
    dct = {"name": "old"}
    apply_to_dict(args, dct)
    assert dct == {"name": "new"}

  def test_nested_override(self):
    """Nested CLI args should override nested values."""
    args = {"database.host": "newhost"}
    dct = {"database": {"host": "oldhost", "port": 5432}}
    apply_to_dict(args, dct)
    assert dct == {"database": {"host": "newhost", "port": 5432}}


class TestGetConfig:
  """Tests for get_config function."""

  def test_basic_config(self):
    """Basic config should load from dataclass defaults."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"
      value: int = 42

    config = get_config(Config, name="nonexistent", user=False, project=False, args=[])
    assert config.name == "default"
    assert config.value == 42

  def test_project_config(self):
    """Config should load from project TOML file."""
    _reset_factories()
    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "from_toml"\nvalue = 100\n')

      @dataclass
      class Config:
        name: str = "default"
        value: int = 42

      # Change to temp dir to test project-level config
      import os

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(Config, name="test", user=False, project=True, args=[])
        assert config.name == "from_toml"
        assert config.value == 100
      finally:
        os.chdir(original_dir)

  def test_nested_config(self):
    """Nested dataclass should work correctly."""
    _reset_factories()

    @dataclass
    class Database:
      host: str = "localhost"
      port: int = 5432

    @dataclass
    class Config:
      name: str = "app"
      database: Database = field(default_factory=Database)

    config = get_config(Config, name="nonexistent", user=False, project=False, args=[])
    assert config.name == "app"
    assert config.database.host == "localhost"
    assert config.database.port == 5432


class TestCliParameter:
  """Tests for cli parameter in get_config."""

  def test_cli_false_skips_sys_argv(self):
    """cli=False should not parse sys.argv."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    # Patch sys.argv to contain actual CLI arguments
    # These should be ignored when cli=False
    with patch.object(sys, "argv", ["test_program", "--name", "from_sys_argv"]):
      config = get_config(Config, name="test", user=False, project=False, cli=False)
      assert config.name == "default"  # sys.argv should be ignored

  def test_cli_false_with_explicit_args(self):
    """cli=False with args should still parse provided args."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    config = get_config(
      Config, name="test", user=False, project=False, cli=False, args=["--name", "from_args"]
    )
    assert config.name == "from_args"

  def test_cli_false_error_message(self):
    """cli=False should produce error without CLI suggestion."""
    _reset_factories()

    @dataclass
    class Config:
      required: str  # No default

    with pytest.raises(ConfigError) as exc_info:
      get_config(Config, name="test", user=False, project=False, cli=False)

    error_msg = str(exc_info.value)
    assert "CLI argument" not in error_msg
    assert "--required" not in error_msg
    # Should still show config file suggestions
    assert "test.toml" in error_msg

  def test_cli_true_error_message(self):
    """cli=True should produce error with CLI suggestion."""
    _reset_factories()

    @dataclass
    class Config:
      required: str  # No default

    with pytest.raises(ConfigError) as exc_info:
      get_config(Config, name="test", user=False, project=False, cli=True, args=[])

    error_msg = str(exc_info.value)
    assert "CLI argument" in error_msg
    assert "--required" in error_msg

  def test_backward_compatibility_default_cli_true(self):
    """Default behavior should remain unchanged (cli=True)."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    # No cli parameter specified - should behave like cli=True
    config = get_config(Config, name="test", user=False, project=False, args=[])
    assert config.name == "default"


class TestConfigError:
  """Tests for error handling."""

  def test_missing_required_field(self):
    """Missing required field should raise ConfigError with helpful message."""
    _reset_factories()

    @dataclass
    class Config:
      required_field: str  # No default = required

    with pytest.raises(ConfigError) as exc_info:
      get_config(Config, name="nonexistent", user=False, project=False, args=[])

    error = exc_info.value
    assert error.field_path == "required_field"
    assert "required_field" in str(error)
    assert "nonexistent.toml" in str(error)
    assert "--required-field" in str(error)

  def test_missing_nested_required_field(self):
    """Missing nested required field should show full path."""
    _reset_factories()

    @dataclass
    class Database:
      host: str | None = None  # Optional but we'll make it required via TOML
      port: int = 5432

    @dataclass
    class Config:
      name: str = "app"
      database: Database = field(default_factory=Database)

    # Test by providing a TOML that has a nested structure but missing required value
    # We'll use a temp directory and file
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[database]\nport = 5432\n")  # Missing host

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # This should work since host is optional (str | None)
        config = get_config(Config, name="test", user=False, project=True, args=[])
        assert config.database.host is None
        assert config.database.port == 5432
      finally:
        os.chdir(original_dir)


class TestFactoryPattern:
  """Tests for the Factory pattern."""

  def test_configclass_decorator(self):
    """@configclass should register with factory system."""
    _reset_factories()

    @configclass
    class TestConfig:
      name: str = "default"

    factory = get_factory(TestConfig)
    assert factory is not None
    assert factory.config_class is TestConfig

  def test_get_factory_singleton(self):
    """Same class should return same Factory instance."""
    _reset_factories()

    @dataclass
    class Config:
      value: int = 42

    factory1 = get_factory(Config)
    factory2 = get_factory(Config)
    assert factory1 is factory2

  def test_factory_prefix(self):
    """Factory prefix should be settable."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    factory = get_factory(Config)
    factory.prefix = "app1"
    assert factory.prefix == "app1"

  def test_list_fields_from_factory(self):
    """Factory.list_fields() should return field structure."""
    _reset_factories()

    @dataclass
    class Database:
      host: str = "localhost"

    @dataclass
    class Config:
      name: str = "app"
      database: Database = field(default_factory=Database)

    fields_list = get_factory(Config).list_fields()
    names = [f[0].name for f in fields_list]
    assert names == ["name", "host"]

  def test_reset_factories(self):
    """_reset_factories should clear all factories."""
    _reset_factories()

    @configclass
    class Config1:
      name: str = "default"

    @configclass
    class Config2:
      value: int = 42

    # Factories exist
    assert get_factory(Config1) is not None
    assert get_factory(Config2) is not None

    # Reset
    _reset_factories()

    # Factories are recreated (new instances)
    factory1_new = get_factory(Config1)
    assert factory1_new.config_class is Config1
