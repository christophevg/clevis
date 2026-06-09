"""Test Clevis compatibility with yoker config schema.

This test file verifies that all type constructs used in yoker's config schema
work correctly with Clevis configuration loading:

1. Literal["DEBUG", "INFO", ...] for log levels
2. tuple[str, ...] for filesystem_paths, allowed_extensions, blocked_patterns
3. dict[str, HandlerConfig] for handlers
4. frozen=True dataclasses
5. Nested dataclasses
6. Complex validation in __post_init__
"""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pytest

from clevis import (
  ConfigError,
  SecurityAction,
  get_config,
  _reset_factories,
)


# Recreate yoker's config classes (essential subset for testing)
# These match the patterns used in yoker/src/yoker/config/schema.py


@dataclass(frozen=True)
class HarnessConfig:
  """Harness metadata configuration."""

  name: str = "yoker"
  version: str = "1.0"
  log_level: str = "INFO"

  def __post_init__(self) -> None:
    """Validate harness configuration."""
    if not self.name or not self.name.strip():
      raise ValueError("harness.name must be non-empty")
    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if self.log_level.upper() not in valid_levels:
      raise ValueError(f"harness.log_level must be one of {valid_levels}")


@dataclass(frozen=True)
class OllamaParameters:
  """Ollama model parameters."""

  temperature: float = 0.7
  top_p: float = 0.9
  top_k: int = 40
  num_ctx: int = 4096

  def __post_init__(self) -> None:
    """Validate Ollama parameters."""
    if not 0.0 <= self.temperature <= 2.0:
      raise ValueError("temperature must be between 0.0 and 2.0")
    if not 0.0 <= self.top_p <= 1.0:
      raise ValueError("top_p must be between 0.0 and 1.0")
    if self.top_k <= 0:
      raise ValueError("top_k must be positive")
    if self.num_ctx <= 0:
      raise ValueError("num_ctx must be positive")


@dataclass(frozen=True)
class OllamaConfig:
  """Ollama backend configuration."""

  base_url: str = "http://localhost:11434"
  model: str = "llama3.2:latest"
  timeout_seconds: int = 60
  parameters: OllamaParameters = field(default_factory=OllamaParameters)

  def __post_init__(self) -> None:
    """Validate Ollama configuration."""
    if not self.base_url or not self.base_url.strip():
      raise ValueError("base_url must be non-empty")
    if not self.model or not self.model.strip():
      raise ValueError("model must be non-empty")
    if self.timeout_seconds <= 0:
      raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class BackendConfig:
  """Backend provider configuration."""

  provider: str = "ollama"
  ollama: OllamaConfig = field(default_factory=OllamaConfig)

  def __post_init__(self) -> None:
    """Validate backend configuration."""
    if self.provider not in ("ollama",):
      raise ValueError(f"provider must be one of ('ollama',), got {self.provider}")


@dataclass(frozen=True)
class HandlerConfig:
  """Permission handler configuration."""

  mode: str = "block"
  message: str | None = None


@dataclass(frozen=True)
class PermissionsConfig:
  """Permission boundaries configuration - tests tuple[str, ...] and dict[str, HandlerConfig]."""

  filesystem_paths: tuple[str, ...] = (".",)
  network_access: str = "none"
  max_file_size_kb: int = 500
  max_recursion_depth: int = 3
  handlers: dict[str, HandlerConfig] = field(default_factory=dict)

  def __post_init__(self) -> None:
    """Validate permissions configuration."""
    if self.network_access not in ("none", "local", "all"):
      raise ValueError(f"network_access must be one of ('none', 'local', 'all')")
    if self.max_file_size_kb <= 0:
      raise ValueError("max_file_size_kb must be positive")
    if self.max_recursion_depth < 0:
      raise ValueError("max_recursion_depth must be non-negative")
    if not self.filesystem_paths:
      raise ValueError("filesystem_paths must not be empty")


@dataclass(frozen=True)
class LoggingConfig:
  """Logging configuration - tests Literal types."""

  level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
  format: Literal["json", "text"] = "text"
  file: str | None = None
  include_tool_calls: bool = True

  def __post_init__(self) -> None:
    """Validate logging configuration."""
    # Literal types are validated by dacite/clevis
    pass


@dataclass(frozen=True)
class Config:
  """Root configuration container - tests nested dataclasses."""

  harness: HarnessConfig = field(default_factory=HarnessConfig)
  backend: BackendConfig = field(default_factory=BackendConfig)
  permissions: PermissionsConfig = field(default_factory=PermissionsConfig)
  logging: LoggingConfig = field(default_factory=LoggingConfig)


class TestYokerSchema:
  """Test compatibility with yoker's config schema patterns."""

  def test_default_config_loads(self):
    """Default configuration should load without errors."""
    _reset_factories()

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

    assert config.harness.name == "yoker"
    assert config.harness.log_level == "INFO"
    assert config.backend.provider == "ollama"
    assert config.permissions.filesystem_paths == (".",)
    assert config.permissions.handlers == {}
    assert config.logging.level == "INFO"
    assert config.logging.format == "text"

  def test_literal_types_valid_values(self):
    """Literal types should accept valid values from TOML."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        """
[logging]
level = "DEBUG"
format = "json"
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
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
        assert config.logging.level == "DEBUG"
        assert config.logging.format == "json"
      finally:
        os.chdir(original_dir)

  def test_literal_types_invalid_values(self):
    """Literal types should reject invalid values."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        """
[logging]
level = "INVALID"
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # dacite should raise WrongTypeError which Clevis wraps in ConfigError
        with pytest.raises((ConfigError, Exception)):
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

  def test_tuple_types_from_toml_list(self):
    """TOML arrays should convert to tuple[str, ...]."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        """
[permissions]
filesystem_paths = [".", "/tmp", "/home/user/data"]
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
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
        # TOML list should be cast to tuple
        assert isinstance(config.permissions.filesystem_paths, tuple)
        assert config.permissions.filesystem_paths == (".", "/tmp", "/home/user/data")
      finally:
        os.chdir(original_dir)

  def test_dict_of_dataclasses(self):
    """dict[str, HandlerConfig] should load nested dataclass values."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        """
[permissions.handlers.read]
mode = "allow"
message = "Allow read operations"

[permissions.handlers.write]
mode = "ask_user"
message = "Ask before writing"
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
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
        assert isinstance(config.permissions.handlers, dict)
        assert "read" in config.permissions.handlers
        assert "write" in config.permissions.handlers
        assert config.permissions.handlers["read"].mode == "allow"
        assert config.permissions.handlers["read"].message == "Allow read operations"
        assert config.permissions.handlers["write"].mode == "ask_user"
      finally:
        os.chdir(original_dir)

  def test_frozen_dataclasses_are_immutable(self):
    """Frozen dataclasses should be immutable after creation."""
    _reset_factories()

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

    # Attempting to modify a frozen dataclass should raise FrozenInstanceError
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
      config.harness.name = "modified"

    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
      config.permissions.filesystem_paths = ("/modified",)

  def test_nested_dataclass_validation(self):
    """Nested dataclass __post_init__ validation should work."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Invalid temperature (out of range)
      config_file.write_text(
        """
[backend.ollama.parameters]
temperature = 5.0
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # __post_init__ validation should catch invalid values
        with pytest.raises((ValueError, Exception)):
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

  def test_full_yoker_config_from_toml(self):
    """Complete yoker-style config should load all nested sections."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # This is a realistic yoker config
      config_file.write_text(
        """
[harness]
name = "yoker-test"
version = "2.0"
log_level = "DEBUG"

[backend]
provider = "ollama"

[backend.ollama]
base_url = "http://localhost:11434"
model = "llama3.2:latest"
timeout_seconds = 120

[backend.ollama.parameters]
temperature = 0.8
top_p = 0.95
top_k = 50
num_ctx = 8192

[permissions]
filesystem_paths = [".", "/tmp", "/workspace"]
network_access = "local"
max_file_size_kb = 1000
max_recursion_depth = 5

[permissions.handlers.file_read]
mode = "allow"
message = "Allow file read operations"

[permissions.handlers.file_write]
mode = "block"
message = "Block file write operations"

[logging]
level = "INFO"
format = "json"
file = "/var/log/yoker.log"
include_tool_calls = false
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
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

        # Verify harness config
        assert config.harness.name == "yoker-test"
        assert config.harness.version == "2.0"
        assert config.harness.log_level == "DEBUG"

        # Verify backend config
        assert config.backend.provider == "ollama"
        assert config.backend.ollama.base_url == "http://localhost:11434"
        assert config.backend.ollama.model == "llama3.2:latest"
        assert config.backend.ollama.timeout_seconds == 120

        # Verify nested backend.ollama.parameters
        assert config.backend.ollama.parameters.temperature == 0.8
        assert config.backend.ollama.parameters.top_p == 0.95
        assert config.backend.ollama.parameters.top_k == 50
        assert config.backend.ollama.parameters.num_ctx == 8192

        # Verify permissions (tuple type)
        assert config.permissions.filesystem_paths == (".", "/tmp", "/workspace")
        assert config.permissions.network_access == "local"
        assert config.permissions.max_file_size_kb == 1000
        assert config.permissions.max_recursion_depth == 5

        # Verify dict[str, HandlerConfig]
        assert len(config.permissions.handlers) == 2
        assert config.permissions.handlers["file_read"].mode == "allow"
        assert config.permissions.handlers["file_read"].message == "Allow file read operations"
        assert config.permissions.handlers["file_write"].mode == "block"
        assert config.permissions.handlers["file_write"].message == "Block file write operations"

        # Verify logging (Literal types)
        assert config.logging.level == "INFO"
        assert config.logging.format == "json"
        assert config.logging.file == "/var/log/yoker.log"
        assert config.logging.include_tool_calls is False

      finally:
        os.chdir(original_dir)

  def test_cli_args_override_toml(self):
    """CLI arguments should override TOML values for all nested levels."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      config_file.write_text(
        """
[harness]
log_level = "DEBUG"

[permissions]
max_file_size_kb = 500
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        config = get_config(
          Config,
          name="test",
          user=False,
          project=True,
          args=["--harness-log-level", "ERROR", "--permissions-max-file-size-kb", "2000"],
          security={
            "file_permissions": SecurityAction.DONT_CHECK,
            "directory_permissions": SecurityAction.DONT_CHECK,
          },
        )

        # CLI args should override TOML
        assert config.harness.log_level == "ERROR"
        assert config.permissions.max_file_size_kb == 2000

      finally:
        os.chdir(original_dir)

  def test_empty_tuple_not_allowed_with_validation(self):
    """Empty filesystem_paths should fail validation in __post_init__."""
    _reset_factories()

    with tempfile.TemporaryDirectory() as tmpdir:
      config_file = Path(tmpdir) / "test.toml"
      # Empty tuple should fail validation
      config_file.write_text(
        """
[permissions]
filesystem_paths = []
"""
      )

      original_dir = os.getcwd()
      try:
        os.chdir(tmpdir)
        # __post_init__ should reject empty paths
        with pytest.raises((ValueError, Exception)):
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

  def test_nested_dataclass_factory_fields(self):
    """Fields with default_factory should create nested dataclasses correctly."""
    _reset_factories()

    # When TOML doesn't specify a section, default_factory should create defaults
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

    # All nested dataclasses should have default values
    assert isinstance(config.harness, HarnessConfig)
    assert isinstance(config.backend, BackendConfig)
    assert isinstance(config.backend.ollama, OllamaConfig)
    assert isinstance(config.backend.ollama.parameters, OllamaParameters)
    assert isinstance(config.permissions, PermissionsConfig)
    assert isinstance(config.logging, LoggingConfig)
