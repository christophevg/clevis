"""Tests for edge cases and potential bugs in clevis configuration."""

import argparse
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from clevis import (
  configclass,
  get_config,
  get_factory,
  get_cmd,
  Factory,
  _reset_factories,
  SecurityAction,
)


class TestInheritanceWithCmd:
  """Tests for inheritance scenarios with cmd parameter."""

  def test_inheritance_parent_has_cmd(self):
    """What happens when child inherits from class with cmd set?"""
    _reset_factories()

    @configclass(cmd="base")
    class BaseConfig:
      verbose: bool = False

    @dataclass
    class ChildConfig(BaseConfig):
      name: str = "child"

    # Child should inherit the cmd from parent
    base_factory = get_factory(BaseConfig)
    child_factory = get_factory(ChildConfig)

    # Both should have cmd set? Or only base?
    assert base_factory.cmd == "base"
    # This might be unexpected - child gets its own factory
    # but does it inherit the cmd?
    print(f"Base cmd: {base_factory.cmd}, Child cmd: {child_factory.cmd}")

  def test_inheritance_both_have_cmd(self):
    """What if both parent and child have cmd set?"""
    _reset_factories()

    @configclass(cmd="base")
    class BaseConfig:
      verbose: bool = False

    # Can we even decorate a dataclass that inherits from a configclass?
    @configclass(cmd="child")
    class ChildConfig(BaseConfig):
      name: str = "child"

    # Both have their own cmd
    base_factory = get_factory(BaseConfig)
    child_factory = get_factory(ChildConfig)

    assert base_factory.cmd == "base"
    assert child_factory.cmd == "child"

  def test_inheritance_cmd_field_name_collision(self):
    """What if parent has field named 'cmd' and child sets cmd?"""
    _reset_factories()

    @dataclass
    class BaseConfig:
      cmd: str = "default_command"  # Field named 'cmd'

    # Decorating with cmd parameter should work
    # But what happens to the field named 'cmd'?
    @configclass(cmd="print")
    class PrintConfig(BaseConfig):
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('[print]\nrich = true\ncmd = "override"\n')

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
        # Does the field 'cmd' get the value from TOML?
        # Or does it conflict with the cmd parameter?
        print(f"Field cmd value: {config.cmd}")
        assert config.rich is True
      finally:
        os.chdir(original_dir)


class TestCmdMismatch:
  """Tests for cmd name that doesn't match field names."""

  def test_cmd_name_different_from_field(self):
    """What if cmd='print' but there's a field named 'printer'?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      printer: str = "default"
      copies: int = 1

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Should extract [print] section, not [printer]
      config_file.write_text('[print]\nprinter = "hp"\ncopies = 2\n')

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
        assert config.printer == "hp"
        assert config.copies == 2
      finally:
        os.chdir(original_dir)


class TestTOMLRootAndSection:
  """Tests for TOML with both root fields and section."""

  def test_root_fields_and_section_same_config(self):
    """What if TOML has both root-level fields and a [print] section?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False
      output: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Root fields AND [print] section
      config_file.write_text("""
verbose = true
output = "root"

[print]
verbose = false
output = "section"
""")

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
        # Which wins? Root or section?
        # Section should win since it's extracted after root is loaded
        print(f"verbose: {config.verbose}, output: {config.output}")
        # The extraction pops the section and updates, so section should override
        assert config.verbose is False
        assert config.output == "section"
      finally:
        os.chdir(original_dir)


class TestEmptyTOMLSection:
  """Tests for empty TOML sections."""

  def test_empty_section_uses_defaults(self):
    """What if [print] exists but is empty?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False
      output: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\n")  # Empty section

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
        # Should use defaults
        assert config.verbose is False
        assert config.output == "default"
      finally:
        os.chdir(original_dir)

  def test_section_with_whitespace_only(self):
    """What if [print] exists but only has whitespace/comments?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\n  \n# comment\n")

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
        assert config.verbose is False
      finally:
        os.chdir(original_dir)


class TestTOMLNonDictValue:
  """Tests for TOML section with non-dict value."""

  def test_section_as_string(self):
    """What if TOML has 'print = "string"' instead of '[print]'?

    With the fix for Bug 2, this should raise ConfigError with a clear message
    about the type mismatch.
    """
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # This is valid TOML but print is a string, not a dict
      config_file.write_text('print = "some_string"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Should raise ConfigError about type mismatch
        with pytest.raises(Exception) as exc_info:
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
        # Verify it's a ConfigError with helpful message
        assert "must be a table" in str(exc_info.value) or "Configuration Error" in str(
          exc_info.value
        )
      finally:
        os.chdir(original_dir)

  def test_section_as_number(self):
    """What if TOML has 'print = 42' instead of '[print]'?

    With the fix for Bug 2, this should raise ConfigError with a clear message
    about the type mismatch.
    """
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("print = 42\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        with pytest.raises(Exception) as exc_info:
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
        # Verify it's a ConfigError with helpful message
        assert "must be a table" in str(exc_info.value) or "Configuration Error" in str(
          exc_info.value
        )
      finally:
        os.chdir(original_dir)

  def test_section_as_array(self):
    """What if TOML has 'print = ["a", "b"]' instead of '[print]'?

    With the fix for Bug 2, this should raise ConfigError with a clear message
    about the type mismatch.
    """
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      rich: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('print = ["a", "b"]\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        with pytest.raises(Exception) as exc_info:
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
        # Verify it's a ConfigError with helpful message
        assert "must be a table" in str(exc_info.value) or "Configuration Error" in str(
          exc_info.value
        )
      finally:
        os.chdir(original_dir)


class TestAliasedCommands:
  """Tests for aliased commands in TOML."""

  def test_alias_in_toml_instead_of_canonical(self):
    """What if TOML has [c] instead of [check] when aliases=['c']?"""
    _reset_factories()

    @configclass(cmd="check", aliases=["c"])
    class CheckConfig:
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Use alias instead of canonical name
      config_file.write_text("[c]\nverbose = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          CheckConfig,
          name="test",
          user=False,
          project=True,
          args=["check"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Does it find the section using the alias?
        # Or does it look for [check] only?
        print(f"verbose: {config.verbose}")
        # Current implementation looks for factory.cmd in cfg
        # So [c] won't match factory.cmd="check"
        assert config.verbose is False  # Uses default, doesn't find [c]
      finally:
        os.chdir(original_dir)

  def test_both_canonical_and_alias_in_toml(self):
    """What if TOML has both [check] and [c] sections?"""
    _reset_factories()

    @configclass(cmd="check", aliases=["c"])
    class CheckConfig:
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
[check]
verbose = false

[c]
verbose = true
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          CheckConfig,
          name="test",
          user=False,
          project=True,
          args=["check"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # [check] should be used
        assert config.verbose is False
      finally:
        os.chdir(original_dir)


class TestOverlappingFieldNames:
  """Tests for overlapping field names between root and section."""

  def test_root_and_section_same_field(self):
    """What if root has 'verbose = true' and [print] has 'verbose = false'?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
verbose = true

[print]
verbose = false
""")

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
        # Section should override root
        assert config.verbose is False
      finally:
        os.chdir(original_dir)

  def test_root_field_not_in_section(self):
    """What if root has field that's not in [print]?

    With the fix for Bug 1 (root field leakage), root fields should NOT
    leak into subcommand configs. Only the [print] section should be used.
    """
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Root has 'verbose', but [print] doesn't
      config_file.write_text("""
verbose = true

[print]
# verbose not specified here
""")

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
        # Section is empty, so should use default
        # Root verbose should NOT pollute the subcommand config
        # With the fix, cfg.clear() prevents root fields from leaking
        assert config.verbose is False
      finally:
        os.chdir(original_dir)


class TestDoubleDecoration:
  """Tests for applying @configclass twice."""

  def test_double_decoration_same_class(self):
    """What if @configclass is applied twice to the same class?"""
    _reset_factories()

    @configclass
    @configclass
    class Config:
      name: str = "default"

    # Should it raise an error or silently succeed?
    factory = get_factory(Config)
    print(f"Factory configured: {factory._configured}")

  @pytest.mark.xfail(reason="Not a bug - Python decorator syntax allows this, outer decorator wins")
  def test_double_decoration_different_params(self):
    """What if @configclass is applied twice with different params?"""
    _reset_factories()

    # This is a syntax test - can you even do this?
    # If you can, which cmd wins?
    with pytest.raises(TypeError):
      # Can't apply decorator twice inline like this
      @configclass(cmd="print")
      @configclass(cmd="check")
      class Config:
        name: str = "default"


class TestSettingCmdAfterDecoration:
  """Tests for manually setting cmd after decoration."""

  def test_set_cmd_after_decoration(self):
    """What if someone sets factory.cmd = 'print' manually?"""
    _reset_factories()

    @configclass
    class Config:
      verbose: bool = False

    # Manually set cmd after decoration
    factory = get_factory(Config)
    factory.cmd = "print"

    # Should this work?
    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\nverbose = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Does the manual cmd setting work?
        assert config.verbose is True
      finally:
        os.chdir(original_dir)

  def test_set_cmd_after_configure(self):
    """What if someone sets cmd after configure_parser() has been called?"""
    _reset_factories()

    @configclass
    class Config:
      verbose: bool = False

    factory = get_factory(Config)
    # Trigger configuration
    factory.configure_parser()

    # Now try to set cmd
    factory.cmd = "print"

    # Does this cause issues?
    # Can't reconfigure since _configured is True
    assert factory._configured is True
    assert factory.cmd == "print"


class TestConfigWithRequiredFields:
  """Tests for subcommand configs with required fields."""

  def test_required_field_in_subcommand(self):
    """What if subcommand config has a required field?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      output: str  # Required, no default

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('[print]\noutput = "file.txt"\n')

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
        assert config.output == "file.txt"
      finally:
        os.chdir(original_dir)

  def test_required_field_missing_in_toml(self):
    """What if required field is not in TOML section?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      output: str  # Required

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("[print]\n")  # Missing 'output'

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        with pytest.raises(Exception) as exc_info:
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
        # Should raise ConfigError about missing field
        print(f"Exception: {exc_info.value}")
        assert "output" in str(exc_info.value)
      finally:
        os.chdir(original_dir)


class TestTOMLWithNestedSection:
  """Tests for nested sections within command section."""

  def test_nested_section_in_command(self):
    """What if [print.options.format] but extraction flattens it?"""
    _reset_factories()

    @dataclass
    class Format:
      type: str = "pdf"

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False
      format: Format = field(default_factory=Format)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Nested section within command section
      config_file.write_text("""
[print]
verbose = true

[print.format]
type = "html"
""")

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
        # Does nested section work correctly?
        assert config.verbose is True
        assert config.format.type == "html"
      finally:
        os.chdir(original_dir)


class TestMultipleGetConfigCalls:
  """Tests for using same config class with different TOML files."""

  def test_multiple_config_files(self):
    """What if same config class is used with different TOML files?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False

    # First config file
    with tempfile.TemporaryDirectory() as tmpdir1:
      config_file1 = Path(tmpdir1) / "test1.toml"
      config_file1.write_text("[print]\nverbose = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir1)
        config1 = get_config(
          PrintConfig,
          name="test1",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config1.verbose is True
      finally:
        os.chdir(original_dir)

    # Second config file
    with tempfile.TemporaryDirectory() as tmpdir2:
      config_file2 = Path(tmpdir2) / "test2.toml"
      config_file2.write_text("[print]\nverbose = false\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir2)
        config2 = get_config(
          PrintConfig,
          name="test2",
          user=False,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config2.verbose is False
      finally:
        os.chdir(original_dir)


class TestUserAndProjectConfigSameSection:
  """Tests for user config + project config both having same section."""

  def test_user_and_project_same_section(self):
    """Which wins: user config or project config?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      project_config = Path(tmpdir) / "test.toml"
      project_config.write_text("[print]\nverbose = false\n")

      user_config = Path.home() / ".test.toml"
      user_config.write_text("[print]\nverbose = true\n")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintConfig,
          name="test",
          user=True,
          project=True,
          args=["print"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Project should override user
        print(f"verbose: {config.verbose}")
        # Based on code: user is loaded first, then project
        # So project should win
        assert config.verbose is False
      finally:
        os.chdir(original_dir)
        # Clean up user config
        user_config.unlink(missing_ok=True)

  def test_user_only_project_missing(self):
    """What if user config has section but project config is missing?"""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False

    user_config = Path.home() / ".test.toml"
    user_config.write_text("[print]\nverbose = true\n")

    try:
      with tempfile.TemporaryDirectory() as tmpdir:
        original_dir = os.getcwd()
        try:
          os.chdir(tmpdir)
          # No project config file
          config = get_config(
            PrintConfig,
            name="test",
            user=True,
            project=True,
            args=["print"],
            security={
              "file_permissions": SecurityAction.DONT_CHECK,
              "directory_permissions": SecurityAction.DONT_CHECK,
            },
          )
          # Should use user config
          assert config.verbose is True
        finally:
          os.chdir(original_dir)
    finally:
      user_config.unlink(missing_ok=True)


class TestCmdWithDots:
  """Tests for cmd with dots in the name."""

  @pytest.mark.xfail(reason="Low priority bug - cmd names with dots not supported yet (issue #4)")
  def test_cmd_with_dots(self):
    """What if cmd='print.format'?"""
    _reset_factories()

    # Is this even valid TOML?
    # TOML allows dots in section names: [print.format]
    @configclass(cmd="print.format")
    class PrintFormatConfig:
      type: str = "pdf"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Does this create a nested structure or flat section name?
      config_file.write_text('[print.format]\ntype = "html"\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          PrintFormatConfig,
          name="test",
          user=False,
          project=True,
          args=["print.format"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        # Does it work?
        assert config.type == "html"
      finally:
        os.chdir(original_dir)


class TestExtractionTypeHandling:
  """Tests for extraction handling different TOML types."""

  def test_extraction_with_nested_dict(self):
    """Does cfg.pop(cmd) handle nested dict correctly?"""
    _reset_factories()

    @dataclass
    class Database:
      host: str = "localhost"
      port: int = 5432

    @configclass(cmd="app")
    class AppConfig:
      name: str = "app"
      database: Database = field(default_factory=Database)

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
[app]
name = "myapp"

[app.database]
host = "db.example.com"
port = 3306
""")

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          AppConfig,
          name="test",
          user=False,
          project=True,
          args=["app"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.name == "myapp"
        assert config.database.host == "db.example.com"
        assert config.database.port == 3306
      finally:
        os.chdir(original_dir)

  def test_cmd_section_with_mixed_types(self):
    """Handle cmd section with various TOML types."""
    _reset_factories()

    @configclass(cmd="print")
    class PrintConfig:
      enabled: bool = True
      count: int = 1
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text("""
[print]
enabled = false
count = 42
name = "custom"
""")

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
        assert config.enabled is False
        assert config.count == 42
        assert config.name == "custom"
      finally:
        os.chdir(original_dir)


class TestCmdInheritance:
  """Tests for cmd inheritance through dataclass hierarchy."""

  def test_non_configclass_parent_with_cmd_field(self):
    """Parent has 'cmd' field, child has @configclass(cmd=...)."""
    _reset_factories()

    @dataclass
    class BaseConfig:
      cmd: str = "base_command"  # Regular field named 'cmd'

    @configclass(cmd="print")
    class PrintConfig(BaseConfig):
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('[print]\ncmd = "overridden"\nverbose = true\n')

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
        # Field 'cmd' should get value from TOML
        assert config.cmd == "overridden"
        assert config.verbose is True
      finally:
        os.chdir(original_dir)

  def test_parent_configclass_child_undecorated(self):
    """Parent has @configclass(cmd=...), child is plain dataclass."""
    _reset_factories()

    @configclass(cmd="base")
    class BaseConfig:
      verbose: bool = False

    @dataclass
    class ChildConfig(BaseConfig):
      name: str = "child"

    # Child should not have cmd set
    child_factory = get_factory(ChildConfig)
    # What is the expected behavior?
    # Does child inherit the parent's cmd?
    print(f"Child factory cmd: {child_factory.cmd}")


class TestEdgeCasesWithGetCmd:
  """Tests for get_cmd edge cases."""

  def test_get_cmd_with_multiple_subcommands(self):
    """get_cmd should return the correct command."""
    _reset_factories()

    parser = argparse.ArgumentParser()

    @configclass(cmd="print")
    class PrintConfig:
      verbose: bool = False

    factory_print = get_factory(PrintConfig)
    factory_print.parser = parser

    @configclass(cmd="check")
    class CheckConfig:
      verbose: bool = False

    factory_check = get_factory(CheckConfig)
    factory_check.parser = parser

    # Test different subcommands
    cmd = get_cmd(parser=parser, args=["print"])
    assert cmd == "print"

    cmd = get_cmd(parser=parser, args=["check"])
    assert cmd == "check"

  def test_get_cmd_no_subcommand(self):
    """get_cmd should return None when no subcommand used."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    # No cmd set on factory
    cmd = get_cmd(args=[])
    assert cmd is None
