"""Tests for the configurable default subcommand feature (P1-005)."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from clevis import (
  configclass,
  get_config,
  get_cmd,
  get_factory,
  _reset_factories,
  SecurityAction,
)
from clevis.factory import _default_cmds, _parse_with_default


class TestDefaultSubcommand:
  """Tests for the default_cmd parameter on @configclass."""

  def test_default_cmd_returns_default_when_no_subcommand(self):
    """get_cmd with no args returns the default subcommand name."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    cmd = get_cmd(args=[])
    assert cmd == "chat"

  def test_default_cmd_runs_config_with_defaults(self):
    """get_config with no args loads the default subcommand config."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"
      verbose: bool = False

    config = get_config(
      ChatConfig,
      name="test",
      user=False,
      project=False,
      args=[],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.model == "gpt-4"
    assert config.verbose is False

  def test_default_cmd_with_options_applies_them(self, capsys):
    """Default subcommand picks up its options from the CLI."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"
      verbose: bool = False

    config = get_config(
      ChatConfig,
      name="test",
      user=False,
      project=False,
      args=["--verbose"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.verbose is True
    # No spurious "invalid choice" error should leak to stderr during the
    # two-pass parse (regression guard for H1).
    captured = capsys.readouterr()
    assert "invalid choice" not in captured.err
    assert captured.err == ""

  def test_explicit_subcommand_overrides_default(self):
    """An explicit subcommand still runs instead of the default."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    @configclass(cmd="run")
    class RunConfig:
      speed: str = "fast"

    cmd = get_cmd(args=["run"])
    assert cmd == "run"

  def test_no_default_unchanged_errors_on_missing_subcommand(self):
    """Without a default, missing subcommand raises SystemExit (argparse error)."""
    _reset_factories()

    @configclass(cmd="chat")
    class ChatConfig:
      model: str = "gpt-4"

    with pytest.raises(SystemExit) as exc_info:
      get_cmd(args=[])
    assert exc_info.value.code == 2

  def test_help_shows_top_level_help(self, capsys):
    """--help with no subcommand shows top-level help listing all subcommands."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True, help="Chat with the model")
    class ChatConfig:
      model: str = "gpt-4"

    @configclass(cmd="run", help="Run something")
    class RunConfig:
      speed: str = "fast"

    with pytest.raises(SystemExit) as exc_info:
      get_cmd(args=["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "chat" in captured.out
    assert "run" in captured.out

  def test_unknown_subcommand_still_errors(self):
    """An unknown subcommand produces an argparse error, not the default."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    with pytest.raises(SystemExit) as exc_info:
      get_cmd(args=["foobar"])
    assert exc_info.value.code == 2

  def test_multiple_defaults_raise_value_error(self):
    """Two configclasses with default_cmd=True on the same parser raises ValueError."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    @configclass(cmd="build", default_cmd=True)
    class BuildConfig:
      target: str = "dist"

    with pytest.raises(ValueError, match="Multiple default subcommands"):
      get_cmd(args=[])

  def test_default_cmd_without_cmd_raises_value_error(self):
    """@configclass(default_cmd=True) without cmd raises ValueError."""
    _reset_factories()

    with pytest.raises(ValueError, match="default_cmd.*requires.*cmd"):

      @configclass(default_cmd=True)
      class BadConfig:
        name: str = "default"

  def test_default_with_aliases_works(self):
    """Aliases work alongside default_cmd."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True, aliases=["c"])
    class ChatConfig:
      model: str = "gpt-4"

    # No subcommand → default (canonical name)
    cmd = get_cmd(args=[])
    assert cmd == "chat"

    # Alias works
    cmd = get_cmd(args=["c"])
    assert cmd == "c"

  def test_default_with_toml_section_extraction(self):
    """TOML section extraction works with default_cmd."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True, config="conversation")
    class ChatConfig:
      model: str = "gpt-4"
      verbose: bool = False

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('[conversation]\nmodel = "claude"\nverbose = true\n')

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          ChatConfig,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.model == "claude"
        assert config.verbose is True
      finally:
        os.chdir(original_dir)

  def test_factory_default_cmd_field_true(self):
    """Factory.default_cmd is True when default_cmd=True is set."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    assert get_factory(ChatConfig).default_cmd is True

  def test_factory_default_cmd_field_false_by_default(self):
    """Factory.default_cmd is False when default_cmd is not set."""
    _reset_factories()

    @configclass(cmd="run")
    class RunConfig:
      speed: str = "fast"

    assert get_factory(RunConfig).default_cmd is False

  def test_reset_factories_clears_default_cmds(self):
    """_reset_factories clears the _default_cmds dict."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    # Trigger configuration to populate _default_cmds
    get_cmd(args=[])
    assert len(_default_cmds) > 0

    _reset_factories()
    assert len(_default_cmds) == 0

  def test_default_subcommand_with_value_option(self, capsys):
    """Default subcommand picks up scalar option values from the CLI."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    config = get_config(
      ChatConfig,
      name="test",
      user=False,
      project=False,
      args=["--model", "claude"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.model == "claude"
    # The two-pass parse must not leak a spurious "invalid choice: 'claude'"
    # message to stderr when 'claude' is an option value, not a subcommand
    # (regression guard for H1).
    captured = capsys.readouterr()
    assert "invalid choice" not in captured.err
    assert captured.err == ""

  def test_get_cmd_returns_none_without_subcommands(self):
    """get_cmd returns None when no subcommands are registered at all."""
    _reset_factories()

    @dataclass
    class PlainConfig:
      name: str = "default"

    cmd = get_cmd(args=[])
    assert cmd is None

  def test_parse_with_default_no_default_delegates_to_parse_args(self):
    """_parse_with_default delegates to parse_args when no default is configured."""
    _reset_factories()

    import argparse

    parser = argparse.ArgumentParser()

    @dataclass
    class PlainConfig:
      name: str = "default"

    # No subcommands, no default — should parse normally
    namespace = _parse_with_default(parser, [])
    assert namespace is not None

  def test_default_subcommand_with_equals_syntax(self, capsys):
    """The --option=value syntax works with the default subcommand."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"

    config = get_config(
      ChatConfig,
      name="test",
      user=False,
      project=False,
      args=["--model=claude"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.model == "claude"
    # Equals syntax places no positional on the command line, so the probe
    # pass should never produce an "invalid choice" error.
    captured = capsys.readouterr()
    assert "invalid choice" not in captured.err
    assert captured.err == ""

  def test_default_cmd_verbose_with_bare_positional_errors(self):
    """--verbose foobar: foobar is a bare positional and errors as invalid."""
    _reset_factories()

    @configclass(cmd="chat", default_cmd=True)
    class ChatConfig:
      model: str = "gpt-4"
      verbose: bool = False

    # 'foobar' is not preceded by an option flag (--verbose is a store_true
    # switch with no value), so it is treated as a genuine invalid subcommand
    # and argparse surfaces the "invalid choice" error.
    with pytest.raises(SystemExit) as exc_info:
      get_config(
        ChatConfig,
        name="test",
        user=False,
        project=False,
        args=["--verbose", "foobar"],
        security={
          "file_permissions": SecurityAction.DONT_CHECK,
          "directory_permissions": SecurityAction.DONT_CHECK,
        },
      )
    assert exc_info.value.code == 2
