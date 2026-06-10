"""Tests for list-append behavior for CLI arguments.

This module tests the append behavior for list[T] fields in CLI arguments,
including --no-field prefix for clearing lists and negating booleans.
"""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from clevis import (
  get_config,
  _reset_factories,
  SecurityAction,
)


class TestListAppendCLI:
  """Tests for list-append CLI argument behavior."""

  def test_append_multiple_values(self):
    """--field val1 --field val2 should result in [val1, val2]."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--packages", "pkgq", "--packages", "c3"],
    )
    assert config.packages == ["pkgq", "c3"]

  def test_append_single_value(self):
    """--field val should result in [val]."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--packages", "pkgq"],
    )
    assert config.packages == ["pkgq"]

  def test_clear_list(self):
    """--no-field should set list to empty []."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--no-packages"],
    )
    assert config.packages == []

  def test_clear_after_append(self):
    """--field a --no-field --field b should result in [b]."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--packages", "a", "--no-packages", "--packages", "b"],
    )
    assert config.packages == ["b"]

  def test_append_to_toml(self):
    """TOML base + CLI append should merge correctly."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('packages = ["pkgq"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--packages", "c3"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.packages == ["pkgq", "c3"]
      finally:
        os.chdir(original_dir)

  def test_clear_toml_values(self):
    """--no-field should clear TOML values."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('packages = ["pkgq", "c3"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--no-packages"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.packages == []
      finally:
        os.chdir(original_dir)

  def test_append_different_types(self):
    """Should work for list[str], list[int], list[Path]."""
    _reset_factories()

    @dataclass
    class Config:
      names: list[str] = field(default_factory=list)
      ports: list[int] = field(default_factory=list)
      paths: list[Path] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=[
        "--names",
        "alice",
        "--names",
        "bob",
        "--ports",
        "8080",
        "--ports",
        "9090",
        "--paths",
        "/tmp",
        "--paths",
        "/var",
      ],
    )
    assert config.names == ["alice", "bob"]
    assert config.ports == [8080, 9090]
    assert config.paths == [Path("/tmp"), Path("/var")]

  def test_empty_list_from_toml_then_append(self):
    """Empty list from TOML + CLI append should work."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("packages = []\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--packages", "new"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.packages == ["new"]
      finally:
        os.chdir(original_dir)

  def test_no_cli_args_uses_toml(self):
    """No CLI args should use TOML values unchanged."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('packages = ["pkgq", "c3"]\n')

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
        assert config.packages == ["pkgq", "c3"]
      finally:
        os.chdir(original_dir)


class TestBooleanNegation:
  """Tests for --no-field boolean negation."""

  def test_no_flag_sets_false(self):
    """--no-debug should set debug=False."""
    _reset_factories()

    @dataclass
    class Config:
      debug: bool = False

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--no-debug"],
    )
    assert config.debug is False

  def test_yes_flag_sets_true(self):
    """--debug should set debug=True."""
    _reset_factories()

    @dataclass
    class Config:
      debug: bool = False

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--debug"],
    )
    assert config.debug is True

  def test_yes_and_no_flags(self):
    """--debug --no-debug should result in False (last wins)."""
    _reset_factories()

    @dataclass
    class Config:
      debug: bool = False

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--debug", "--no-debug"],
    )
    assert config.debug is False

  def test_no_and_yes_flags(self):
    """--no-debug --debug should result in True (last wins)."""
    _reset_factories()

    @dataclass
    class Config:
      debug: bool = False

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--no-debug", "--debug"],
    )
    assert config.debug is True

  def test_no_flag_overrides_toml(self):
    """TOML debug=true + --no-debug should result in False."""
    _reset_factories()

    @dataclass
    class Config:
      debug: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("debug = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--no-debug"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.debug is False
      finally:
        os.chdir(original_dir)

  def test_yes_flag_overrides_toml(self):
    """TOML debug=false + --debug should result in True."""
    _reset_factories()

    @dataclass
    class Config:
      debug: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("debug = false\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--debug"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.debug is True
      finally:
        os.chdir(original_dir)

  def test_no_cli_args_uses_toml_boolean(self):
    """No CLI args should use TOML boolean unchanged."""
    _reset_factories()

    @dataclass
    class Config:
      debug: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("debug = true\n")

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
        assert config.debug is True
      finally:
        os.chdir(original_dir)


class TestNestedListFields:
  """Tests for list fields in nested dataclasses."""

  def test_nested_list_append(self):
    """Nested list fields should support append."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      packages: list[str] = field(default_factory=list)

    @dataclass
    class Config:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--tools-packages", "pkgq", "--tools-packages", "c3"],
    )
    assert config.tools.packages == ["pkgq", "c3"]

  def test_nested_list_clear(self):
    """Nested list fields should support --no-field."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      packages: list[str] = field(default_factory=list)

    @dataclass
    class Config:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--no-tools-packages"],
    )
    assert config.tools.packages == []

  def test_nested_list_append_to_toml(self):
    """Nested list fields should merge CLI + TOML."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      packages: list[str] = field(default_factory=list)

    @dataclass
    class Config:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('[tools]\npackages = ["base"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--tools-packages", "plugin"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.tools.packages == ["base", "plugin"]
      finally:
        os.chdir(original_dir)


class TestMultipleListFields:
  """Tests for multiple list fields in the same config."""

  def test_multiple_lists_append(self):
    """Multiple list fields should work independently."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)
      paths: list[str] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=[
        "--packages",
        "pkgq",
        "--packages",
        "c3",
        "--paths",
        "/src",
        "--paths",
        "/lib",
      ],
    )
    assert config.packages == ["pkgq", "c3"]
    assert config.paths == ["/src", "/lib"]

  def test_multiple_lists_clear_one(self):
    """Clearing one list should not affect others."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)
      paths: list[str] = field(default_factory=list)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('packages = ["pkgq"]\npaths = ["/src"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--no-packages", "--paths", "/lib"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.packages == []
        assert config.paths == ["/src", "/lib"]
      finally:
        os.chdir(original_dir)


class TestListWithOtherTypes:
  """Tests for list fields combined with other types."""

  def test_list_and_boolean_together(self):
    """List and boolean fields should work together."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)
      debug: bool = False

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=[
        "--packages",
        "pkgq",
        "--debug",
        "--packages",
        "c3",
      ],
    )
    assert config.packages == ["pkgq", "c3"]
    assert config.debug is True

  def test_list_and_scalar_together(self):
    """List and scalar fields should work together."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)
      name: str = "default"

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=[
        "--name",
        "custom",
        "--packages",
        "pkgq",
        "--packages",
        "c3",
      ],
    )
    assert config.packages == ["pkgq", "c3"]
    assert config.name == "custom"


class TestEdgeCases:
  """Tests for edge cases and special scenarios."""

  def test_empty_list_default_no_cli(self):
    """Empty list default with no CLI args should remain empty."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=[],
    )
    assert config.packages == []

  def test_list_type_conversion(self):
    """List elements should be type-converted correctly."""
    _reset_factories()

    @dataclass
    class Config:
      ports: list[int] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--ports", "80", "--ports", "443"],
    )
    # Should be integers, not strings
    assert config.ports == [80, 443]
    assert all(isinstance(p, int) for p in config.ports)

  def test_list_invalid_type(self):
    """Invalid type for list element should raise error."""
    _reset_factories()

    @dataclass
    class Config:
      ports: list[int] = field(default_factory=list)

    with pytest.raises(SystemExit):  # argparse exits on invalid argument
      get_config(
        Config,
        name="test",
        user=False,
        project=False,
        args=["--ports", "not_a_number"],
      )

  def test_optional_list_field(self):
    """Optional list fields should work with CLI args."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] | None = None

    # No CLI args - should be None (default)
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=[],
    )
    assert config1.packages is None

    # With CLI args - should be the list
    _reset_factories()
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--packages", "pkgq"],
    )
    assert config2.packages == ["pkgq"]

  def test_list_clear_then_append(self):
    """--no-field --field X should result in [X] (clear, then append)."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=["--no-packages", "--packages", "urgent"],
    )
    assert config.packages == ["urgent"]
