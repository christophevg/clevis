"""Tests for advanced type support in Clevis configuration.

This module tests types that may be needed for yoker config schema:
1. Literal["A", "B", "C"] - Does dacite/Clevis validate literal types?
2. tuple[str, ...] - Does TOML list convert to tuple?
3. dict[str, DataclassType] - Does nested dict with dataclass values work?
4. frozen=True - Do frozen dataclasses work?
"""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pytest

from clevis import (
  ConfigError,
  SecurityAction,
  get_config,
  _reset_factories,
)


class TestLiteralTypes:
  """Tests for Literal type support."""

  def test_literal_with_valid_value(self):
    """Literal type should accept valid values."""
    _reset_factories()

    @dataclass
    class LoggingConfig:
      level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    config = get_config(LoggingConfig, name="test", user=False, project=False, args=[])
    assert config.level == "INFO"

  def test_literal_with_valid_value_from_toml(self):
    """Literal type should accept valid values from TOML."""
    _reset_factories()

    @dataclass
    class LoggingConfig:
      level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('level = "DEBUG"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          LoggingConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.level == "DEBUG"
      finally:
        os.chdir(original_dir)

  def test_literal_with_invalid_value_from_toml(self):
    """Literal type should reject invalid values."""
    _reset_factories()

    @dataclass
    class LoggingConfig:
      level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('level = "INVALID"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Should raise ConfigError or dacite error
        with pytest.raises((ConfigError, Exception)) as exc_info:
          get_config(
            LoggingConfig,
            name="test",
            user=False,
            project=True,
            args=[],
            security={
              "file_permissions": SecurityAction.DONT_CHECK,
              "directory_permissions": SecurityAction.DONT_CHECK,
            },
          )
        # Should mention type mismatch or invalid value
        print(f"Exception: {exc_info.value}")
      finally:
        os.chdir(original_dir)


class TestTupleTypes:
  """Tests for tuple type support."""

  def test_tuple_with_default_value(self):
    """Tuple type should work with default values."""
    _reset_factories()

    @dataclass
    class PathsConfig:
      paths: tuple[str, ...] = (".",)

    config = get_config(PathsConfig, name="test", user=False, project=False, args=[])
    assert config.paths == (".",)
    assert isinstance(config.paths, tuple)

  def test_tuple_from_toml_list(self):
    """TOML list should convert to tuple."""
    _reset_factories()

    @dataclass
    class PathsConfig:
      paths: tuple[str, ...] = (".",)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('paths = ["src", "lib", "tests"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PathsConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Should convert list to tuple
        assert isinstance(config.paths, tuple)
        assert config.paths == ("src", "lib", "tests")
      finally:
        os.chdir(original_dir)

  def test_tuple_of_ints_from_toml(self):
    """TOML list of ints should convert to tuple of ints."""
    _reset_factories()

    @dataclass
    class PortsConfig:
      ports: tuple[int, ...] = (8080,)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("ports = [8080, 8081, 8082]\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PortsConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert isinstance(config.ports, tuple)
        assert config.ports == (8080, 8081, 8082)
        assert all(isinstance(p, int) for p in config.ports)
      finally:
        os.chdir(original_dir)


class TestDictWithDataclassValues:
  """Tests for dict[str, DataclassType] support."""

  def test_dict_with_dataclass_values_default(self):
    """Dict with dataclass values should work with default_factory."""
    _reset_factories()

    @dataclass
    class HandlerConfig:
      mode: str = "block"
      enabled: bool = True

    @dataclass
    class PermissionsConfig:
      handlers: dict[str, HandlerConfig] = field(default_factory=dict)

    config = get_config(PermissionsConfig, name="test", user=False, project=False, args=[])
    assert config.handlers == {}
    assert isinstance(config.handlers, dict)

  def test_dict_with_dataclass_values_from_toml(self):
    """TOML dict should convert to dict with dataclass values."""
    _reset_factories()

    @dataclass
    class HandlerConfig:
      mode: str = "block"
      enabled: bool = True

    @dataclass
    class PermissionsConfig:
      handlers: dict[str, HandlerConfig] = field(default_factory=dict)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
[handlers.read]
mode = "allow"
enabled = true

[handlers.write]
mode = "block"
enabled = false
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PermissionsConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Should have two handlers
        assert len(config.handlers) == 2
        # Check read handler
        assert "read" in config.handlers
        assert isinstance(config.handlers["read"], HandlerConfig)
        assert config.handlers["read"].mode == "allow"
        assert config.handlers["read"].enabled is True
        # Check write handler
        assert "write" in config.handlers
        assert isinstance(config.handlers["write"], HandlerConfig)
        assert config.handlers["write"].mode == "block"
        assert config.handlers["write"].enabled is False
      finally:
        os.chdir(original_dir)

  def test_dict_with_nested_dataclass_partial_values(self):
    """Dict with dataclass values should allow partial values (use defaults)."""
    _reset_factories()

    @dataclass
    class HandlerConfig:
      mode: str = "block"
      enabled: bool = True

    @dataclass
    class PermissionsConfig:
      handlers: dict[str, HandlerConfig] = field(default_factory=dict)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Only specify mode, enabled should use default
      config_file.write_text("""
[handlers.admin]
mode = "super"
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PermissionsConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert "admin" in config.handlers
        assert config.handlers["admin"].mode == "super"
        assert config.handlers["admin"].enabled is True  # Uses default
      finally:
        os.chdir(original_dir)


class TestFrozenDataclass:
  """Tests for frozen dataclass support."""

  def test_frozen_dataclass_basic(self):
    """Frozen dataclass should work with defaults."""
    _reset_factories()

    @dataclass(frozen=True)
    class FrozenConfig:
      name: str = "test"
      value: int = 42

    config = get_config(FrozenConfig, name="test", user=False, project=False, args=[])
    assert config.name == "test"
    assert config.value == 42

  def test_frozen_dataclass_from_toml(self):
    """Frozen dataclass should work with TOML values."""
    _reset_factories()

    @dataclass(frozen=True)
    class FrozenConfig:
      name: str = "test"
      value: int = 42

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
name = "custom"
value = 100
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          FrozenConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.name == "custom"
        assert config.value == 100
      finally:
        os.chdir(original_dir)

  def test_frozen_dataclass_immutability(self):
    """Frozen dataclass should prevent modification."""
    _reset_factories()

    @dataclass(frozen=True)
    class FrozenConfig:
      name: str = "test"
      value: int = 42

    config = get_config(FrozenConfig, name="test", user=False, project=False, args=[])

    # Should raise FrozenInstanceError when trying to modify
    with pytest.raises(Exception):  # FrozenInstanceError
      config.name = "modified"  # type: ignore

  def test_frozen_nested_in_regular(self):
    """Frozen dataclass nested in regular dataclass should work."""
    _reset_factories()

    @dataclass(frozen=True)
    class ImmutableSettings:
      timeout: int = 30
      retries: int = 3

    @dataclass
    class AppConfig:
      name: str = "app"
      settings: ImmutableSettings = field(default_factory=ImmutableSettings)

    config = get_config(AppConfig, name="test", user=False, project=False, args=[])
    assert config.name == "app"
    assert config.settings.timeout == 30
    assert config.settings.retries == 3

  def test_frozen_nested_from_toml(self):
    """Frozen dataclass nested in regular dataclass should work from TOML."""
    _reset_factories()

    @dataclass(frozen=True)
    class ImmutableSettings:
      timeout: int = 30
      retries: int = 3

    @dataclass
    class AppConfig:
      name: str = "app"
      settings: ImmutableSettings = field(default_factory=ImmutableSettings)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
[settings]
timeout = 60
retries = 5
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          AppConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.name == "app"
        assert config.settings.timeout == 60
        assert config.settings.retries == 5
      finally:
        os.chdir(original_dir)


class TestCombinedAdvancedTypes:
  """Tests combining multiple advanced types."""

  def test_literal_and_tuple_together(self):
    """Literal and tuple should work together."""
    _reset_factories()

    @dataclass
    class ServiceConfig:
      level: Literal["DEBUG", "INFO", "WARNING"] = "INFO"
      paths: tuple[str, ...] = (".",)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
level = "DEBUG"
paths = ["src", "lib"]
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          ServiceConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.level == "DEBUG"
        assert config.paths == ("src", "lib")
      finally:
        os.chdir(original_dir)

  def test_dict_and_frozen_together(self):
    """Dict with dataclass values and frozen dataclass should work together."""
    _reset_factories()

    @dataclass(frozen=True)
    class ImmutableHandler:
      mode: str = "block"
      priority: int = 1

    @dataclass
    class HandlersConfig:
      handlers: dict[str, ImmutableHandler] = field(default_factory=dict)
      default_timeout: int = 30

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
default_timeout = 60

[handlers.read]
mode = "allow"
priority = 2
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          HandlersConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.default_timeout == 60
        assert "read" in config.handlers
        assert config.handlers["read"].mode == "allow"
        assert config.handlers["read"].priority == 2
      finally:
        os.chdir(original_dir)

  def test_all_advanced_types_together(self):
    """All advanced types should work together."""
    _reset_factories()

    @dataclass(frozen=True)
    class Endpoint:
      host: str = "localhost"
      port: int = 8080

    @dataclass
    class AdvancedConfig:
      log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
      search_paths: tuple[str, ...] = (".",)
      endpoints: dict[str, Endpoint] = field(default_factory=dict)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
log_level = "DEBUG"
search_paths = ["src", "lib", "tests"]

[endpoints.api]
host = "api.example.com"
port = 443

[endpoints.db]
host = "db.example.com"
port = 5432
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          AdvancedConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.log_level == "DEBUG"
        assert config.search_paths == ("src", "lib", "tests")
        assert len(config.endpoints) == 2
        assert config.endpoints["api"].host == "api.example.com"
        assert config.endpoints["api"].port == 443
        assert config.endpoints["db"].host == "db.example.com"
        assert config.endpoints["db"].port == 5432
      finally:
        os.chdir(original_dir)


class TestListType:
  """Tests for list[str] type support."""

  def test_list_str_from_toml(self):
    """list[str] should load from TOML array."""
    _reset_factories()

    @dataclass
    class PathsConfig:
      paths: list[str] = field(default_factory=list)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('paths = ["dir1", "dir2", "dir3"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PathsConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.paths == ["dir1", "dir2", "dir3"]
      finally:
        os.chdir(original_dir)

  def test_list_str_from_toml_no_cli(self):
    """list[str] should load from TOML when CLI parsing is disabled."""
    _reset_factories()

    @dataclass
    class PathsConfig:
      paths: list[str] = field(default_factory=list)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('paths = ["dir1", "dir2", "dir3"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PathsConfig,
          name="test",
          user=False,
          project=True,
          cli=False,  # Disable CLI - like yoker does
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.paths == ["dir1", "dir2", "dir3"]
      finally:
        os.chdir(original_dir)


class TestDictType:
  """Tests for dict[str, int] type support."""

  def test_dict_str_int_from_toml(self):
    """dict[str, int] should load from TOML table."""
    _reset_factories()

    @dataclass
    class PortsConfig:
      ports: dict[str, int] = field(default_factory=dict)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
[ports]
http = 80
https = 443
custom = 8080
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PortsConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.ports == {"http": 80, "https": 443, "custom": 8080}
        assert isinstance(config.ports, dict)
        assert all(isinstance(v, int) for v in config.ports.values())
      finally:
        os.chdir(original_dir)

  def test_dict_str_int_no_cli(self):
    """dict[str, int] should load from TOML when CLI parsing is disabled."""
    _reset_factories()

    @dataclass
    class PortsConfig:
      ports: dict[str, int] = field(default_factory=dict)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
[ports]
api = 8000
db = 5432
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PortsConfig,
          name="test",
          user=False,
          project=True,
          cli=False,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.ports == {"api": 8000, "db": 5432}
      finally:
        os.chdir(original_dir)


class TestSetType:
  """Tests for set[int] type support."""

  def test_set_int_from_toml(self):
    """set[int] should load from TOML array."""
    _reset_factories()

    @dataclass
    class IdsConfig:
      ids: set[int] = field(default_factory=set)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("ids = [1, 2, 3, 3, 2, 1]\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          IdsConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Sets deduplicate
        assert config.ids == {1, 2, 3}
        assert isinstance(config.ids, set)
      finally:
        os.chdir(original_dir)
