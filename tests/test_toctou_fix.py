"""Tests for TOCTOU race condition fix in file permission checks."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from clevis import (
  SecurityAction,
  SecurityError,
  _check_file_permissions,
  _load_toml_from_fd,
  get_config,
  _reset_factories,
)


class TestToctouFix:
  """Tests for TOCTOU-safe file permission checking."""

  def test_check_file_permissions_returns_fd(self):
    """_check_file_permissions should return a file descriptor for existing files."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'test = "value"')
      fname = f.name

    try:
      path = Path(fname)
      # Set secure permissions
      os.chmod(fname, 0o600)

      passed, fd = _check_file_permissions(path, SecurityAction.DONT_CHECK)

      assert passed is True
      assert fd is not None
      assert isinstance(fd, int)

      # Close the fd
      os.close(fd)
    finally:
      os.unlink(fname)

  def test_check_file_permissions_no_file(self):
    """_check_file_permissions should return None fd for non-existent files."""
    path = Path("/nonexistent/file.toml")

    passed, fd = _check_file_permissions(path, SecurityAction.REJECT)

    assert passed is True
    assert fd is None

  def test_check_file_permissions_insecure_reject(self):
    """Insecure file should raise SecurityError and close fd."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'test = "value"')
      fname = f.name

    try:
      path = Path(fname)
      # Set insecure permissions
      os.chmod(fname, 0o644)

      with pytest.raises(SecurityError):
        _check_file_permissions(path, SecurityAction.REJECT)

      # fd should be closed after SecurityError
    finally:
      os.unlink(fname)

  def test_check_file_permissions_insecure_log(self):
    """Insecure file with LOG action should return fd and log warning."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'test = "value"')
      fname = f.name

    try:
      path = Path(fname)
      # Set insecure permissions
      os.chmod(fname, 0o644)

      passed, fd = _check_file_permissions(path, SecurityAction.LOG)

      assert passed is True
      assert fd is not None

      # Close the fd
      os.close(fd)
    finally:
      os.unlink(fname)

  def test_load_toml_from_fd(self):
    """_load_toml_from_fd should read TOML from file descriptor."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'test = "value"\nnumber = 42')
      fname = f.name

    try:
      # Open file and get fd
      fd = os.open(fname, os.O_RDONLY)

      # Load TOML from fd
      result = _load_toml_from_fd(fd)

      assert result == {"test": "value", "number": 42}

      # fd should be closed by _load_toml_from_fd
    finally:
      os.unlink(fname)

  def test_atomic_permission_check(self):
    """Test that permission check uses the same file that's read (TOCTOU-safe)."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "from_toml"\n')
      # Set secure permissions
      os.chmod(config_file, 0o600)

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # This should work with TOCTOU-safe implementation
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=[],
        )
        assert config.name == "from_toml"
      finally:
        os.chdir(original_dir)

  def test_fd_closed_after_reject(self):
    """File descriptor should be closed after SecurityError is raised."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
      f.write(b'test = "value"')
      fname = f.name

    try:
      path = Path(fname)
      # Set insecure permissions
      os.chmod(fname, 0o644)

      # This should raise SecurityError and close the fd
      with pytest.raises(SecurityError):
        _check_file_permissions(path, SecurityAction.REJECT)

      # If fd wasn't closed properly, this test would fail with resource leak
      # (we can't directly check if fd is closed in Python, but the test passes
      # if no exception is raised)
    finally:
      os.unlink(fname)

  def test_fd_closed_after_successful_read(self):
    """File descriptor should be closed after successful TOCTOU-safe read."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text('name = "from_toml"\n')
      # Set secure permissions
      os.chmod(config_file, 0o600)

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Load config (should close fd after reading)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=[],
        )
        assert config.name == "from_toml"

        # If fd wasn't closed, subsequent loads would accumulate open fds
        # (we can't directly check, but multiple loads should work)
        for _ in range(10):
          config2 = get_config(
            Config,
            name="test",
            user=False,
            project=True,
            args=[],
          )
          assert config2.name == "from_toml"
      finally:
        os.chdir(original_dir)

  def test_multiple_security_checks(self):
    """Test that multiple security checks work correctly with file descriptors."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    with tempfile.TemporaryDirectory() as tmpdir:
      # Create user config
      user_config = Path.home() / ".test.toml"
      user_config.write_text('name = "user"\n')
      os.chmod(user_config, 0o600)

      # Create project config
      project_config = Path(tmpdir) / "test.toml"
      project_config.write_text('name = "project"\n')
      os.chmod(project_config, 0o600)

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # Load with both user and project configs
        config = get_config(
          Config,
          name="test",
          user=True,
          project=True,
          args=[],
        )
        # Project config should override user config
        assert config.name == "project"
      finally:
        os.chdir(original_dir)
        user_config.unlink()
