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
  def test_envtoml_has_priority(self, monkeypatch):
    """The selected loader expands ${VAR} (an env-aware backend is selected)."""
    import clevis
    monkeypatch.setenv("CLEVIS_TEST_VAR", "expanded")
    # Force re-detection
    clevis.__dict__["_toml_load"] = None
    # Any env-aware backend (envtoml has priority, tomlev the fallback)
    # expands ${VAR}; a plain tomllib/tomli backend would keep it literal.
    result = _get_toml_parser()("a = '${CLEVIS_TEST_VAR}'")
    assert result == {"a": "expanded"}
  def test_load_toml_uses_selected_parser(self):
    """_load_toml should use the selected parser."""
    # Create a simple TOML file
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'name = "test"\nvalue = 42\n')
      f.flush()
      result = _load_toml(open(f.name, "rb"))
      assert result == {"name": "test", "value": 42}
  def test_load_toml_expands_keyring_placeholders(self, monkeypatch):
    """_load_toml expands ${keyring:...} placeholders before parsing."""
    import types
    store = {("test", "api"): "s3cret"}
    fake_keyring = types.ModuleType("keyring")
    fake_keyring.get_password = lambda service, username: store.get(
      (service, username)
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'api_key = "${keyring:test/api}"\n')
      f.flush()
      result = _load_toml(open(f.name, "rb"))
      assert result == {"api_key": "s3cret"}
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
