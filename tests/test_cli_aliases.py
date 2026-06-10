"""Tests for CLI argument aliases functionality.

This module tests the CLI aliases feature which allows fields to have
alternative argument names using metadata["cli_aliases"].
"""

from dataclasses import dataclass, field

import pytest

from clevis import (
  get_config,
  get_factory,
  _reset_factories,
  SecurityAction,
)


class TestSingleAlias:
  """Tests for single alias on a field."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_single_alias_scalar_field(self):
    """A single alias should work alongside canonical argument."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})

    # Test with canonical argument
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--packages", "pkgq", "--packages", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config1.packages == ["pkgq", "c3"]

    # Test with alias
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq", "--with", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config2.packages == ["pkgq", "c3"]

  def test_single_alias_mixed_usage(self):
    """Canonical and alias arguments can be mixed."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})

    # Mix canonical and alias
    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq", "--packages", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == ["pkgq", "c3"]

  def test_single_alias_boolean_field(self):
    """Boolean field with alias should create both --alias and --no-alias."""
    _reset_factories()

    @dataclass
    class Config:
      verbose: bool = field(default=False, metadata={"cli_aliases": ["v"]})

    # Test with canonical argument
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--verbose"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config1.verbose is True

    # Test with alias
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--v"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config2.verbose is True

    # Test with --no- alias
    config3 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--no-v"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config3.verbose is False


class TestMultipleAliases:
  """Tests for multiple aliases on a field."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_multiple_aliases(self):
    """Multiple aliases should all work."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(
        default_factory=list, metadata={"cli_aliases": ["with", "add", "pkg"]}
      )

    # Test with first alias
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config1.packages == ["pkgq"]

    # Test with second alias
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--add", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config2.packages == ["c3"]

    # Test with third alias
    config3 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--pkg", "python"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config3.packages == ["python"]

    # Test mixing all
    config4 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "a", "--add", "b", "--pkg", "c", "--packages", "d"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config4.packages == ["a", "b", "c", "d"]


class TestNestedConfigAliases:
  """Tests for aliases in nested config classes."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_nested_config_alias(self):
    """Nested config field with alias should create correct CLI arguments."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})

    @dataclass
    class Config:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Test with canonical argument
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-packages", "pkgq"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config1.tools.packages == ["pkgq"]

    # Test with alias (replaces entire name)
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config2.tools.packages == ["c3"]

    # Test mixing canonical and alias
    config3 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq", "--tools-packages", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config3.tools.packages == ["pkgq", "c3"]

  def test_deeply_nested_alias(self):
    """Deeply nested config with alias should work."""
    _reset_factories()

    @dataclass
    class Level3Config:
      value: str = field(default="default", metadata={"cli_aliases": ["v"]})

    @dataclass
    class Level2Config:
      level3: Level3Config = field(default_factory=Level3Config)

    @dataclass
    class Level1Config:
      level2: Level2Config = field(default_factory=Level2Config)

    @dataclass
    class Config:
      level1: Level1Config = field(default_factory=Level1Config)

    # Test with canonical argument
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--level1-level2-level3-value", "test"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config1.level1.level2.level3.value == "test"

    # Test with alias
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--v", "test2"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config2.level1.level2.level3.value == "test2"


class TestConflictDetection:
  """Tests for alias conflict detection."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_alias_conflicts_with_canonical(self):
    """Alias conflicting with another field's canonical name should raise error."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list)
      with_flag: bool = field(default=False, metadata={"cli_aliases": ["packages"]})

    # This should raise ValueError because "packages" alias conflicts with existing field
    with pytest.raises(ValueError, match="Alias '--packages' conflicts with existing argument"):
      get_config(
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

  def test_alias_conflicts_with_another_alias(self):
    """Alias conflicting with another field's alias should raise error."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})
      modules: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})

    # This should raise ValueError because both fields have the same alias
    with pytest.raises(ValueError, match="Alias '--with' conflicts with existing argument"):
      get_config(
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

  def test_no_conflict_different_aliases(self):
    """Different aliases should not conflict."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})
      modules: list[str] = field(default_factory=list, metadata={"cli_aliases": ["add"]})

    # This should work without error
    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq", "--add", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == ["pkgq"]
    assert config.modules == ["c3"]


class TestListFieldsWithAliases:
  """Tests for list fields with aliases."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_list_alias_append(self):
    """List field alias should support append action."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq", "--with", "c3", "--with", "python"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == ["pkgq", "c3", "python"]

  def test_list_alias_clear(self):
    """List field alias should support --no-alias to clear."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=lambda: ["default1", "default2"])

    @dataclass
    class ConfigWithAlias:
      packages: list[str] = field(
        default_factory=lambda: ["default1", "default2"], metadata={"cli_aliases": ["with"]}
      )

    config = get_config(
      ConfigWithAlias,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--no-with"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == []

  def test_list_alias_mixed_clear_and_append(self):
    """List field alias should handle clear then append."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(
        default_factory=lambda: ["default1", "default2"], metadata={"cli_aliases": ["with"]}
      )

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--no-with", "--with", "new1", "--with", "new2"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == ["new1", "new2"]


class TestBooleanFieldsWithAliases:
  """Tests for boolean fields with aliases."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_boolean_alias_true(self):
    """Boolean field alias should set to True."""
    _reset_factories()

    @dataclass
    class Config:
      verbose: bool = field(default=False, metadata={"cli_aliases": ["v"]})

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--v"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.verbose is True

  def test_boolean_alias_false(self):
    """Boolean field alias should set to False with --no-."""
    _reset_factories()

    @dataclass
    class Config:
      verbose: bool = field(default=True, metadata={"cli_aliases": ["v"]})

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--no-v"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.verbose is False

  def test_boolean_alias_last_wins(self):
    """Last boolean argument wins (canonical or alias)."""
    _reset_factories()

    @dataclass
    class Config:
      verbose: bool = field(default=False, metadata={"cli_aliases": ["v"]})

    # Last argument wins: --no-v after --v
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--v", "--no-v"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config1.verbose is False

    # Last argument wins: --v after --no-v
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--no-v", "--v"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config2.verbose is True


class TestScalarFieldsWithAliases:
  """Tests for scalar fields with aliases."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_string_alias(self):
    """String field with alias should work."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = field(default="default", metadata={"cli_aliases": ["n"]})

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--n", "custom"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.name == "custom"

  def test_int_alias(self):
    """Integer field with alias should work with type conversion."""
    _reset_factories()

    @dataclass
    class Config:
      port: int = field(default=8080, metadata={"cli_aliases": ["p"]})

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--p", "3000"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.port == 3000

  def test_alias_last_wins(self):
    """Last scalar argument wins (canonical or alias)."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = field(default="default", metadata={"cli_aliases": ["n"]})

    # Alias then canonical
    config1 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--n", "alias-value", "--name", "canonical-value"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config1.name == "canonical-value"

    # Canonical then alias
    config2 = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--name", "canonical-value", "--n", "alias-value"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config2.name == "alias-value"


class TestInvalidMetadata:
  """Tests for invalid alias metadata handling."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_non_list_metadata_ignored(self):
    """Non-list cli_aliases metadata should be ignored."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": "with"})

    # Should work without error (invalid metadata ignored)
    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--packages", "pkgq"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == ["pkgq"]

  def test_non_string_alias_ignored(self):
    """Non-string items in cli_aliases should be ignored."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(
        default_factory=list, metadata={"cli_aliases": ["with", 123, None, "add"]}
      )

    # Should work with only valid string aliases
    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq", "--add", "c3"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == ["pkgq", "c3"]

  def test_empty_alias_list(self):
    """Empty cli_aliases list should work without error."""
    _reset_factories()

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": []})

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--packages", "pkgq"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.packages == ["pkgq"]


class TestPrefixWithAliases:
  """Tests for aliases with prefix functionality."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_prefix_with_alias(self):
    """Prefix should affect canonical name, but alias replaces entire name."""
    _reset_factories()

    @dataclass
    class ToolsConfig:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})

    @dataclass
    class Config:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # Set prefix on root config
    factory = get_factory(Config)
    factory.prefix = "app"

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--with", "pkgq"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.tools.packages == ["pkgq"]
