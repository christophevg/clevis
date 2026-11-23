"""Tests for the clevis console command (clevis.cli)."""
import getpass
import json
import sys
import types

import pytest

from clevis.cli import main


@pytest.fixture
def fake_keyring(monkeypatch):
  """Inject a fake keyring module with an in-memory credential store."""
  store: dict[tuple[str, str], str] = {}
  module = types.ModuleType("keyring")
  module.get_password = lambda service, username: store.get((service, username))
  module.set_password = (
    lambda service, username, password: store.update({(service, username): password})
  )
  monkeypatch.setitem(sys.modules, "keyring", module)
  return module


class TestKeyringSet:
  """Tests for `clevis keyring set`."""

  def test_set_success(self, fake_keyring, monkeypatch, capsys):
    """Matching password prompts store the secret and exit 0."""
    prompts = iter(["s3cret", "s3cret"])
    monkeypatch.setattr(getpass, "getpass", lambda *_: next(prompts))
    exit_code = main(["keyring", "set", "svc", "user"])
    assert exit_code == 0
    assert fake_keyring.get_password("svc", "user") == "s3cret"
    assert "Stored secret for svc/user." in capsys.readouterr().out

  def test_set_password_mismatch(self, fake_keyring, monkeypatch, capsys):
    """Mismatched repeats exit 2 without storing anything."""
    prompts = iter(["s3cret", "typo"])
    monkeypatch.setattr(getpass, "getpass", lambda *_: next(prompts))
    exit_code = main(["keyring", "set", "svc", "user"])
    assert exit_code == 2
    assert "do not match" in capsys.readouterr().err
    assert fake_keyring.get_password("svc", "user") is None

  def test_set_without_keyring(self, monkeypatch, capsys):
    """Missing keyring package exits 1 with an install hint."""
    monkeypatch.setitem(sys.modules, "keyring", None)
    exit_code = main(["keyring", "set", "svc", "user"])
    assert exit_code == 1
    assert "pip install clevis" in capsys.readouterr().err

  def test_stored_secret_usable_by_clevis(self, fake_keyring, monkeypatch):
    """A CLI-stored secret resolves through ${keyring:...} in clevis.loads."""
    import clevis

    prompts = iter(["s3cret", "s3cret"])
    monkeypatch.setattr(getpass, "getpass", lambda *_: next(prompts))
    assert main(["keyring", "set", "svc", "user"]) == 0
    assert clevis.loads('pw = "${keyring:svc/user}"') == {"pw": "s3cret"}


class TestParserBasics:
  """Basic CLI parser behavior."""

  def test_version_flag(self, capsys):
    """--version prints the program name and exits 0."""
    with pytest.raises(SystemExit) as exc_info:
      main(["--version"])
    assert exc_info.value.code == 0
    assert "clevis" in capsys.readouterr().out

  def test_missing_subcommand(self):
    """No subcommand exits with an argparse usage error."""
    with pytest.raises(SystemExit) as exc_info:
      main([])
    assert exc_info.value.code == 2

  def test_keyring_without_action(self):
    """`clevis keyring` without set exits with an argparse usage error."""
    with pytest.raises(SystemExit) as exc_info:
      main(["keyring"])
    assert exc_info.value.code == 2


class TestCat:
  """Tests for `clevis cat`."""

  def test_cat_plain_toml(self, tmp_path, capsys):
    """A plain TOML file is dumped as JSON."""
    config = tmp_path / "config.toml"
    config.write_text('name = "test"\nvalue = 42\n')
    exit_code = main(["cat", str(config)])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {"name": "test", "value": 42}

  def test_cat_applies_keyring_expansion(self, tmp_path, capsys, monkeypatch):
    """${keyring:...} placeholders are resolved in the dumped output."""
    import types
    store = {("test", "api"): "s3cret"}
    fake_keyring = types.ModuleType("keyring")
    fake_keyring.get_password = lambda service, username: store.get(
      (service, username)
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    config = tmp_path / "config.toml"
    config.write_text('api_key = "${keyring:test/api}"\n')
    exit_code = main(["cat", str(config)])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {"api_key": "s3cret"}

  def test_cat_missing_file(self, tmp_path, capsys):
    """An unreadable file exits 1 with a one-line error."""
    exit_code = main(["cat", str(tmp_path / "nope.toml")])
    assert exit_code == 1
    assert "cannot read" in capsys.readouterr().err

  def test_cat_invalid_toml(self, tmp_path, capsys):
    """Invalid TOML exits 1 with a one-line error."""
    config = tmp_path / "config.toml"
    config.write_text("not = [valid\n")
    exit_code = main(["cat", str(config)])
    assert exit_code == 1
    assert "Error:" in capsys.readouterr().err

  def test_cat_env_expansion_applied(self, tmp_path, capsys, monkeypatch):
    """Backend env-var interpolation shows in the dumped output."""
    pytest.importorskip("envtoml")
    monkeypatch.setenv("CLEVIS_CAT_EXPAND_VAR", "expanded")
    config = tmp_path / "config.toml"
    config.write_text('x = "${CLEVIS_CAT_EXPAND_VAR}"\n')
    exit_code = main(["cat", str(config)])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {"x": "expanded"}
