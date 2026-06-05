"""Test for error message formatting regression."""

import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest

from clevis import ConfigError, get_config, _reset_factories, SecurityAction


def test_config_error_suppresses_internal_traceback():
  """
  ConfigError should suppress internal traceback from dacite.

  Regression test: Exception chaining with 'from e' shows full traceback
  from dacite internals, but should only show user-friendly ConfigError message.
  """
  _reset_factories()

  @dataclass
  class DatabaseConfig:
    host: str  # Required field with no default

  @dataclass
  class AppConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

  # When a required field is missing, ConfigError should be raised
  # The traceback should NOT include dacite internals
  with pytest.raises(ConfigError) as exc_info:
    get_config(AppConfig, name="test", user=False, project=False, args=[])

  error = exc_info.value
  error_str = str(error)

  # The error message should be formatted nicely
  assert "Configuration Error" in error_str
  assert "database.host" in error_str
  assert "test.toml" in error_str

  # The __cause__ attribute should be None (suppressed chain)
  # If it's not None, then 'from e' was used instead of 'from None'
  assert error.__cause__ is None, "Internal dacite exception should be suppressed"


def test_config_error_message_format():
  """Test that ConfigError produces a user-friendly formatted message."""
  _reset_factories()

  error = ConfigError(
    message="Required field has no value", field_path="database.host", config_name="project"
  )

  error_str = str(error)

  # Check all parts of the formatted message
  assert "=" * 70 in error_str  # Separator line
  assert "Configuration Error" in error_str
  assert "Field: database.host" in error_str
  assert "Issue: Required field has no value" in error_str
  assert "project.toml" in error_str
  assert "~/.project.toml" in error_str
  assert "--database-host" in error_str


def test_missing_value_error_chaining():
  """Test that MissingValueError is properly converted to ConfigError without chain."""
  _reset_factories()

  @dataclass
  class Config:
    required_field: str  # No default = required

  with pytest.raises(ConfigError) as exc_info:
    get_config(Config, name="test", user=False, project=False, args=[])

  # The ConfigError should not have a __cause__ (chain should be suppressed)
  assert exc_info.value.__cause__ is None
  assert "required_field" in str(exc_info.value)


def test_wrong_type_error_chaining():
  """Test that WrongTypeError is properly converted to ConfigError without chain."""
  _reset_factories()

  @dataclass
  class Config:
    count: int

  # Provide wrong type
  with tempfile.TemporaryDirectory() as tmpdir:
    config_file = Path(tmpdir) / "test.toml"
    config_file.write_text('count = "not a number"\n')

    import os

    original_dir = os.getcwd()
    try:
      os.chdir(tmpdir)
      with pytest.raises(ConfigError) as exc_info:
        # Temp files have insecure permissions, skip security checks
        get_config(
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
    finally:
      os.chdir(original_dir)

  # The ConfigError should not have a __cause__ (chain should be suppressed)
  assert exc_info.value.__cause__ is None
