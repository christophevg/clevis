"""Tests for TOML parser selection."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from clevis import _get_toml_parser, _load_toml


class TestTomlParser:
  """Tests for TOML parser selection."""

  def test_get_toml_parser_returns_callable(self):
    """Parser selection should return a callable."""
    parser = _get_toml_parser()
    assert callable(parser)

  def test_envtoml_has_priority(self):
    """envtoml should be selected if installed."""
    # Since we installed all extras, envtoml should be selected
    import clevis

    # Force re-detection
    clevis.__dict__["_toml_load"] = None
    parser = _get_toml_parser()
    # envtoml.load is the parser when envtoml is installed
    import envtoml

    assert parser == envtoml.load

  def test_load_toml_uses_selected_parser(self):
    """_load_toml should use the selected parser."""
    # Create a simple TOML file
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'name = "test"\nvalue = 42\n')
      f.flush()

      result = _load_toml(open(f.name, "rb"))
      assert result == {"name": "test", "value": 42}

  def test_no_parser_error_message(self):
    """Should provide helpful error when no parser available."""
    # Save original modules
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
      if name in ("envtoml", "tomlev", "tomli", "tomllib"):
        raise ImportError(f"No module named '{name}'")
      return original_import(name, *args, **kwargs)

    # Clear cached parser
    import clevis

    clevis.__dict__["_toml_load"] = None

    with patch("builtins.__import__", side_effect=mock_import):
      with pytest.raises(ImportError) as exc_info:
        _get_toml_parser()

      error_msg = str(exc_info.value)
      assert "No TOML parser available" in error_msg
      assert "clevis[tomli]" in error_msg
      assert "clevis[envtoml]" in error_msg
      assert "clevis[tomlev]" in error_msg
