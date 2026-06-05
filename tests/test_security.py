"""Tests for security parameter in get_config()."""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from clevis import (
  SecurityAction,
  SecurityConfig,
  SecurityError,
  get_config,
  _reset_factories,
)


class TestSecurityAction:
  """Tests for SecurityAction enum."""

  def test_security_action_values(self):
    """SecurityAction should have expected values."""
    assert SecurityAction.DONT_CHECK.value == "dont_check"
    assert SecurityAction.LOG.value == "log"
    assert SecurityAction.REJECT.value == "reject"

  def test_security_action_from_string(self):
    """SecurityAction should be creatable from string."""
    assert SecurityAction("dont_check") == SecurityAction.DONT_CHECK
    assert SecurityAction("log") == SecurityAction.LOG
    assert SecurityAction("reject") == SecurityAction.REJECT


class TestSecurityConfig:
  """Tests for SecurityConfig TypedDict."""

  def test_security_config_with_file_permissions(self):
    """SecurityConfig should accept file_permissions."""
    config: SecurityConfig = {"file_permissions": SecurityAction.DONT_CHECK}
    assert config["file_permissions"] == SecurityAction.DONT_CHECK

  def test_security_config_with_directory_permissions(self):
    """SecurityConfig should accept directory_permissions."""
    config: SecurityConfig = {"directory_permissions": SecurityAction.LOG}
    assert config["directory_permissions"] == SecurityAction.LOG

  def test_security_config_with_both(self):
    """SecurityConfig should accept both permissions."""
    config: SecurityConfig = {
      "file_permissions": SecurityAction.LOG,
      "directory_permissions": SecurityAction.DONT_CHECK,
    }
    assert config["file_permissions"] == SecurityAction.LOG
    assert config["directory_permissions"] == SecurityAction.DONT_CHECK

  def test_security_config_empty(self):
    """Empty SecurityConfig should be valid."""
    config: SecurityConfig = {}
    assert config == {}


class TestSecurityError:
  """Tests for SecurityError exception."""

  def test_security_error_attributes(self):
    """SecurityError should have path and check attributes."""
    error = SecurityError("Test message", "/path/to/file", "file_permissions")
    assert error.path == "/path/to/file"
    assert error.check == "file_permissions"
    assert str(error) == "Test message"

  def test_security_error_message_formatting(self):
    """SecurityError message should contain all relevant info."""
    error = SecurityError(
      "Configuration file /path/to/file is readable by group/other (mode 0o644).",
      "/path/to/file",
      "file_permissions",
    )
    assert "readable by group/other" in str(error)
    assert "/path/to/file" in str(error)


class TestFilePermissions:
  """Tests for file permission checking."""

  def test_secure_file_permissions_pass(self):
    """File with 0o600 permissions should pass security check."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o600)  # Secure: owner read/write only

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Default security should pass with secure permissions
        config = get_config(Config, name="test", user=False, project=True, args=[])
        assert config.name == "test"
      finally:
        os.chdir(original_dir)

  def test_insecure_file_permissions_reject(self):
    """File with 0o644 permissions should be rejected by default."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o644)  # Insecure: world readable

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        with pytest.raises(SecurityError) as exc_info:
          get_config(Config, name="test", user=False, project=True, args=[])
        assert "readable by group/other" in str(exc_info.value)
        assert exc_info.value.check == "file_permissions"
      finally:
        os.chdir(original_dir)

  def test_insecure_file_permissions_log(self):
    """File with 0o644 permissions should log warning when action is LOG."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o644)  # Insecure

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Should not raise, but should log (no exception = test passes)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=[],
          security={
            "file_permissions": SecurityAction.LOG,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )
        assert config.name == "test"
      finally:
        os.chdir(original_dir)

  def test_insecure_file_permissions_dont_check(self):
    """File with 0o644 permissions should be skipped with DONT_CHECK."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o644)  # Insecure

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Should not raise when check is skipped
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
        assert config.name == "test"
      finally:
        os.chdir(original_dir)

  def test_nonexistent_file_passes(self):
    """Non-existent file should pass security check."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    # No config file exists - should not raise
    config = get_config(Config, name="nonexistent", user=False, project=True, args=[])
    assert config.name == "default"


class TestDirectoryPermissions:
  """Tests for directory permission checking."""

  def test_home_directory_trusted(self):
    """Home directory should be trusted for directory checks."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    # Home directory check should be skipped
    # This test just verifies the logic doesn't raise
    config = get_config(
      Config,
      name="test",
      user=True,
      project=False,
      args=[],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.REJECT,
      },
    )
    # Test passes if no exception raised

  def test_world_writable_directory_reject(self):
    """World-writable directory should be rejected by default."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o600)  # Secure file

      # Make directory world-writable (not recommended, but for testing)
      Path(tmpdir).chmod(0o777)

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        with pytest.raises(SecurityError) as exc_info:
          get_config(Config, name="test", user=False, project=True, args=[])
        assert "world-writable" in str(exc_info.value)
        assert exc_info.value.check == "directory_permissions"
      finally:
        os.chdir(original_dir)
        # Cleanup: restore directory permissions
        Path(tmpdir).chmod(0o755)

  def test_world_writable_directory_dont_check(self):
    """World-writable directory should be skipped with DONT_CHECK."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o600)  # Secure file

      # Make directory world-writable
      Path(tmpdir).chmod(0o777)

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Should not raise when check is skipped
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
        assert config.name == "test"
      finally:
        os.chdir(original_dir)
        # Cleanup: restore directory permissions
        Path(tmpdir).chmod(0o755)


class TestDefaultSecurity:
  """Tests for default security behavior."""

  def test_default_is_reject(self):
    """Default security should be maximally strict (REJECT)."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o644)  # Insecure

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # No security parameter - should use default REJECT
        with pytest.raises(SecurityError) as exc_info:
          get_config(Config, name="test", user=False, project=True, args=[])
        assert exc_info.value.check == "file_permissions"
      finally:
        os.chdir(original_dir)

  def test_backward_compatibility(self):
    """Existing code should work without changes."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    # No security parameter - should still work with secure defaults
    # (or fail with secure checks when insecure)
    config = get_config(Config, name="nonexistent", user=False, project=False, args=[])
    assert config.name == "default"


class TestIntegration:
  """Integration tests for security parameter."""

  def test_get_config_with_security_parameter(self):
    """get_config should accept security parameter."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    config = get_config(
      Config,
      name="test",
      user=False,
      project=False,
      args=[],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.name == "default"

  def test_fine_grained_security_config(self):
    """Should allow fine-grained security configuration."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o644)  # Insecure file

      # Make directory world-writable
      Path(tmpdir).chmod(0o777)

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Only check file permissions, skip directory
        with pytest.raises(SecurityError) as exc_info:
          get_config(
            Config,
            name="test",
            user=False,
            project=True,
            args=[],
            security={
              "file_permissions": SecurityAction.REJECT,
              "directory_permissions": SecurityAction.DONT_CHECK,
            },
          )
        assert exc_info.value.check == "file_permissions"
      finally:
        os.chdir(original_dir)
        # Cleanup
        Path(tmpdir).chmod(0o755)

  def test_partial_security_config(self):
    """Partial security config should use defaults for missing keys."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "test"\n')
      config_file.chmod(0o644)  # Insecure file

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Only specify file_permissions, directory_permissions should default to REJECT
        # But since we're in a secure directory, only file check should fail
        with pytest.raises(SecurityError) as exc_info:
          get_config(
            Config,
            name="test",
            user=False,
            project=True,
            args=[],
            security={"file_permissions": SecurityAction.REJECT},
          )
        assert exc_info.value.check == "file_permissions"
      finally:
        os.chdir(original_dir)

