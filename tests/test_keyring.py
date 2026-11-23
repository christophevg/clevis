"""Tests for ${keyring:service/username} placeholder interpolation."""
import sys
import types

import pytest

import clevis
from clevis.keyring import KeyringError, expand_keyring_placeholders


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


class TestExpandKeyringPlaceholders:
  """Unit tests for the text-level expansion."""

  def test_passthrough_without_placeholder(self, monkeypatch):
    """Text without keyring placeholders is untouched; keyring is not imported."""
    # sys.modules["keyring"] = None makes any keyring import raise — proves
    # the fast path never imports it.
    monkeypatch.setitem(sys.modules, "keyring", None)
    assert expand_keyring_placeholders("a = 1\n") == "a = 1\n"

  def test_resolves_entry(self, fake_keyring):
    """Placeholders are replaced with the stored secret."""
    fake_keyring.set_password("test", "user", "s3cret")
    assert expand_keyring_placeholders("k = '${keyring:test/user}'") == "k = 's3cret'"

  def test_missing_entry(self, fake_keyring):
    """A missing keyring entry raises with a hint on how to store one."""
    with pytest.raises(KeyringError) as exc_info:
      expand_keyring_placeholders("k = '${keyring:test/absent}'")
    assert "No keyring entry found" in str(exc_info.value)
    assert "clevis keyring set test absent" in str(exc_info.value)

  def test_keyring_not_installed(self, monkeypatch):
    """When keyring cannot be imported, a clear install hint is raised."""
    monkeypatch.setitem(sys.modules, "keyring", None)
    with pytest.raises(KeyringError) as exc_info:
      expand_keyring_placeholders("k = '${keyring:test/user}'")
    assert "pip install clevis[keyring]" in str(exc_info.value)
    assert "placeholder was found" in str(exc_info.value)

  def test_invalid_placeholder_no_separator(self, fake_keyring):
    """A ref without '/' raises an invalid-placeholder error."""
    with pytest.raises(KeyringError, match="Invalid keyring placeholder"):
      expand_keyring_placeholders("k = '${keyring:no-separator}'")

  def test_empty_username(self, fake_keyring):
    """A trailing separator with empty username raises."""
    with pytest.raises(KeyringError, match="Invalid keyring placeholder"):
      expand_keyring_placeholders("k = '${keyring:svc/}'")

  def test_empty_placeholder(self, fake_keyring):
    """An empty ref (no match for the pattern) raises the unresolved error."""
    with pytest.raises(KeyringError, match="unresolved"):
      expand_keyring_placeholders("k = '${keyring:}'")

  def test_username_may_contain_slash(self, fake_keyring):
    """The ref splits on the FIRST '/', so the username may contain '/'."""
    fake_keyring.set_password("svc", "a/b", "deep")
    assert expand_keyring_placeholders("k = '${keyring:svc/a/b}'") == "k = 'deep'"

  def test_nested_keyring_reference_in_secret(self, fake_keyring):
    """A resolved secret containing ${keyring:...} is rejected, not expanded."""
    fake_keyring.set_password("svc", "user", "see ${keyring:other/x}")
    with pytest.raises(KeyringError, match="unresolved"):
      expand_keyring_placeholders("k = '${keyring:svc/user}'")

  def test_multiple_placeholders(self, fake_keyring):
    """Several placeholders in one text are all resolved."""
    fake_keyring.set_password("svc", "user", "pw")
    fake_keyring.set_password("svc2", "user2", "pw2")
    text = "a = '${keyring:svc/user}'\nb = 'x-${keyring:svc2/user2}-y'\n"
    assert expand_keyring_placeholders(text) == "a = 'pw'\nb = 'x-pw2-y'\n"


class TestKeyringThroughPublicApi:
  """Integration: expansion runs inside the TOML load path."""

  def test_loads_expands_placeholder(self, fake_keyring):
    """clevis.loads expands keyring placeholders before parsing."""
    fake_keyring.set_password("test", "api", "s3cret")
    data = clevis.loads('api_key = "${keyring:test/api}"')
    assert data == {"api_key": "s3cret"}

  def test_loads_mixed_with_env_var(self, fake_keyring, monkeypatch):
    """Keyring expansion composes with backend env-var interpolation."""
    pytest.importorskip("envtoml")
    monkeypatch.setenv("TEST_KEYRING_API", "from-env")
    fake_keyring.set_password("test", "api", "s3cret")
    data = clevis.loads(
      'api_key = "${keyring:test/api}"\n'
      'env_key = "${TEST_KEYRING_API}"\n'
    )
    assert data == {"api_key": "s3cret", "env_key": "from-env"}
