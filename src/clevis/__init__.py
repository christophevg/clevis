"""
Clevis - Configuration management for Python projects.

Provides dataclass-based configuration with TOML file support,
environment variable interpolation, and CLI argument generation.

TOML Parser Selection (priority order):
  1. envtoml  - Env var interpolation (${VAR}) - install: pip install clevis[envtoml]
  2. tomlev   - Tomlev parser - install: pip install clevis[tomlev]
  3. tomli    - Pure Python TOML - install: pip install clevis[tomli]
  4. tomllib  - Stdlib (Python 3.11+) - no extras needed
"""

import logging
import os
import re
import stat
from collections.abc import Callable
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict, TypeVar, get_origin

from dacite import Config, from_dict
from dacite.exceptions import DaciteError, MissingValueError, WrongTypeError

from clevis import factory as _factory_module
from clevis.configclass import configclass
from clevis.factory import (
  Factory,
  Parser,
  SubParser,
  _ensure_configured,
  _reset_factories,
  apply_to_dict,
  get_factory,
  has_factory,
  unpack_type,
)
from clevis.registration import register_field

__version__ = "0.4.0"

logger = logging.getLogger(__name__)


# TOML Configuration File Constants

TOML_EXT = ".toml"
"""File extension for TOML files."""

USER_CONFIG_TEMPLATE = ".{name}.toml"
"""Template for user-level config files (e.g., ~/.clevis.toml)."""

PROJECT_CONFIG_TEMPLATE = "{name}.toml"
"""Template for project-level config files (e.g., ./clevis.toml)."""


# Security Types


class SecurityAction(Enum):
  """Action to take when security check fails."""

  DONT_CHECK = "dont_check"
  LOG = "log"
  REJECT = "reject"


class SecurityConfig(TypedDict, total=False):
  """Configuration for security checks."""

  file_permissions: SecurityAction
  directory_permissions: SecurityAction


class SecurityError(Exception):
  """Raised when a security check fails."""

  def __init__(self, message: str, path: str, check: str) -> None:
    self.path = path
    self.check = check
    super().__init__(message)


def _check_file_permissions(path: Path, action: SecurityAction) -> tuple[bool, int | None]:
  """Check if file has secure permissions (owner-only readable).

  Uses file descriptor to prevent TOCTOU race condition between
  permission check and file read.

  Args:
    path: Path to configuration file
    action: Security action to take if check fails

  Returns:
    Tuple of (check_passed, file_descriptor):
    - check_passed: True if check passes or is skipped
    - file_descriptor: Opened file descriptor if file exists and check passes,
      None if file doesn't exist or check is skipped

  Raises:
    SecurityError: If action is REJECT and check fails

  Note:
    If file_descriptor is returned (not None), caller MUST close it
    after use to avoid resource leaks.
  """
  if action == SecurityAction.DONT_CHECK:
    if path.exists():
      # Open file without security check when DONT_CHECK
      return True, os.open(path, os.O_RDONLY)
    return True, None

  if not path.exists():
    return True, None

  try:
    # Open file to get file descriptor - prevents TOCTOU
    fd = os.open(path, os.O_RDONLY)
  except FileNotFoundError:
    # File was deleted between exists() and open()
    return True, None

  try:
    st = os.fstat(fd)
    mode = st.st_mode
    # Check if group or other can read
    if mode & (stat.S_IRGRP | stat.S_IROTH):
      msg = (
        f"Configuration file {path} is readable by group/other "
        f"(mode {oct(mode & 0o777)}). "
        f"Use 'chmod 600 {path}' to fix."
      )
      if action == SecurityAction.REJECT:
        os.close(fd)
        raise SecurityError(msg, str(path), "file_permissions")
      elif action == SecurityAction.LOG:
        logger.warning(msg)
    return True, fd
  except SecurityError:
    # Don't close fd again - already closed before raising SecurityError
    raise
  except BaseException:
    # Close fd on any exception, including system exceptions (KeyboardInterrupt,
    # SystemExit, GeneratorExit). This is intentional: we clean up the file
    # descriptor before re-raising. Using `except Exception:` would leak FDs
    # on system exceptions. See P2-013 in TODO.md for rationale.
    os.close(fd)
    raise


def _check_directory_permissions(path: Path, action: SecurityAction) -> bool:
  """Check if parent directory is world-writable.

  Returns True if check passes or is skipped.
  Raises SecurityError if action is REJECT and check fails.
  Logs warning if action is LOG and check fails.
  """
  if action == SecurityAction.DONT_CHECK:
    return True

  parent = path.parent
  if not parent.exists():
    return True  # No directory to check

  # Home directory is trusted
  if parent == Path.home() or str(parent).startswith(str(Path.home())):
    return True

  mode = parent.stat().st_mode
  # Check if world-writable
  if mode & stat.S_IWOTH:
    msg = (
      f"Directory {parent} is world-writable "
      f"(mode {oct(mode & 0o777)}). "
      f"This allows symlink attacks. Move config to a secure location."
    )
    if action == SecurityAction.REJECT:
      raise SecurityError(msg, str(parent), "directory_permissions")
    elif action == SecurityAction.LOG:
      logger.warning(msg)
  return True


# TOML Parser Selection
# ---------------------
# Tries parsers in this order: envtoml > tomlev > tomli > tomllib


def _get_toml_parser() -> Callable[[Any], dict[str, Any]]:
  """
  Get the appropriate TOML parser based on installed packages.

  Priority: envtoml > tomlev > tomli > tomllib (stdlib)

  Returns:
      A function that loads TOML from a file object

  Raises:
      ImportError: If no TOML parser is available
  """
  # envtoml: supports ${VAR} interpolation
  try:
    import envtoml

    return envtoml.load
  except ImportError:
    pass

  # tomlev: supports ${VAR|default} interpolation
  try:
    import tomllib  # type: ignore[import-not-found]
    from tomlev.env_loader import expandvars  # type: ignore[attr-defined]

    def load_with_tomlev(file: Any) -> dict[str, Any]:
      content = file.read()
      if isinstance(content, bytes):
        content = content.decode("utf-8")
      expanded = expandvars(content)
      return tomllib.loads(expanded)  # type: ignore[no-any-return]

    return load_with_tomlev
  except ImportError:
    pass

  # tomli: pure Python TOML (Python 3.10)
  try:
    import tomli

    return tomli.load
  except ImportError:
    pass

  # tomllib: stdlib (Python 3.11+)
  try:
    import tomllib

    return tomllib.load  # type: ignore[no-any-return]
  except ImportError:
    pass

  raise ImportError(
    "No TOML parser available.\n\n"
    "Install one of:\n"
    "  pip install clevis[tomli]      # Python 3.10\n"
    "  pip install clevis[envtoml]    # Env var interpolation\n"
    "  pip install clevis[tomlev]     # Env var with defaults\n\n"
    "Note: Python 3.11+ has built-in tomllib (no extras needed)"
  )


# Module-level parser (loaded once)
_toml_load: Callable[[Any], dict[str, Any]] | None = None


def _load_toml(file: Any) -> dict[str, Any]:
  """
  Load TOML from a file object using the selected parser.

  Args:
      file: File object opened in binary mode

  Returns:
      Dictionary of parsed TOML data
  """
  global _toml_load
  if _toml_load is None:
    _toml_load = _get_toml_parser()
  return _toml_load(file)


def _load_toml_from_fd(fd: int) -> dict[str, Any]:
  """
  Load TOML from a file descriptor.

  Wraps the file descriptor in a file object for TOML parser.
  Does NOT close the file descriptor - caller's responsibility.

  Args:
      fd: File descriptor opened in read mode

  Returns:
      Dictionary of parsed TOML data
  """
  file_obj = os.fdopen(fd, "rb")
  # File object takes ownership of fd and will close it
  return _load_toml(file_obj)


class ConfigError(Exception):
  """Raised when configuration is missing or invalid."""

  def __init__(self, message: str, field_path: str, config_name: str, suggest_cli: bool = True):
    self.message = message
    self.field_path = field_path
    self.config_name = config_name
    self.suggest_cli = suggest_cli
    super().__init__(self._format_message())

  def _format_message(self) -> str:
    """Format a helpful error message with actionable suggestions."""
    lines = [f"\n{'=' * 70}"]
    lines.append("Configuration Error")
    lines.append(f"{'=' * 70}\n")

    lines.append(f"Field: {self.field_path}")
    lines.append(f"Issue: {self.message}\n")

    lines.append("Provide this value in one of these ways:\n")

    # Project config
    lines.append(f"  1. Project config: ./{PROJECT_CONFIG_TEMPLATE.format(name=self.config_name)}")
    parts = self.field_path.split(".")
    if len(parts) == 1:
      lines.append(f'     {parts[0]} = "your_value"')
    else:
      lines.append(f"     [{parts[0]}]")
      lines.append(f'     {".".join(parts[1:])} = "your_value"')
    lines.append("")

    # User config
    lines.append(f"  2. User config: ~/{USER_CONFIG_TEMPLATE.format(name=self.config_name)}")
    lines.append("     (same format as above)\n")

    # CLI argument - only suggest when appropriate
    if self.suggest_cli:
      cli_arg = "--" + self.field_path.replace(".", "-").replace("_", "-")
      lines.append(f"  3. CLI argument: {cli_arg} <value>\n")

    lines.append(f"{'=' * 70}")
    return "\n".join(lines)


def get_cmd(parser: Any = None, args: list[str] | None = None) -> str | None:
  """
  Get the active subcommand name from parsed arguments.

  Args:
    parser: Optional parser to use (defaults to creating a new default parser)
    args: Optional list of CLI arguments (for testing)

  Returns:
    The subcommand name or None if no subcommand was used
  """
  if not parser:
    parser = _factory_module._get_default_parser()
  parsed_args = vars(_ensure_configured(parser).parse_args(args))
  cmd: str | None = parsed_args.pop("cmd", None)
  return cmd


def _merge_list_args(
  clz: type,
  cli_args: dict[str, Any],
  toml_cfg: dict[str, Any],
) -> dict[str, Any]:
  """
  Merge CLI list arguments with TOML configuration.

  For list fields:
  - None (no CLI arg) → keep TOML value
  - [] (--no-field) → clear, result is []
  - [...] (--field X --field Y) → TOML base + CLI values

  This function does NOT modify the input dictionaries. It returns a new
  dictionary with the merged configuration.

  Args:
    clz: The dataclass type
    cli_args: CLI arguments (dotted keys)
    toml_cfg: TOML configuration

  Returns:
    New dictionary with merged list values. Non-list CLI args are included
    unchanged. List args are merged with TOML values according to the rules
    above.
  """
  # Get all list fields in the config class
  list_fields = _get_list_fields(clz, [])

  # Start with a copy of TOML config (deep copy for nested dicts)
  result: dict[str, Any] = {}
  for key, value in toml_cfg.items():
    if isinstance(value, dict):
      # Deep copy nested dicts
      result[key] = dict(value)
    else:
      result[key] = value

  # Merge list fields
  for field_name in list_fields:
    cli_value = cli_args.get(field_name)

    if cli_value is None:
      # No CLI argument for this field - keep TOML value (already in result)
      continue

    # Navigate to the nested location in result
    parts = field_name.split(".")
    final_key = parts.pop()
    scope = result
    for step in parts:
      if step not in scope:
        scope[step] = {}
      scope = scope[step]

    if isinstance(cli_value, list) and len(cli_value) == 0:
      # --no-field: empty list marker, clear the field
      scope[final_key] = []
    elif isinstance(cli_value, list):
      # --field X --field Y: append to TOML base
      toml_value = scope.get(final_key, [])
      if not isinstance(toml_value, list):
        logger.warning(
          f"Expected list for {field_name}, got {type(toml_value).__name__}. "
          f"Converting to empty list."
        )
        toml_value = []
      scope[final_key] = toml_value + cli_value

  # Add non-list CLI args to result (they override TOML values)
  # Skip None values (default optional value, can't be set through command line)
  for key, value in cli_args.items():
    if key not in list_fields and value is not None:
      # Navigate to nested location and set value
      parts = key.split(".")
      if len(parts) == 1:
        result[key] = value
      else:
        final_key = parts.pop()
        scope = result
        for step in parts:
          if step not in scope:
            scope[step] = {}
          scope = scope[step]
        scope[final_key] = value

  return result


def _get_list_fields(clz: type, path: list[str]) -> list[str]:
  """
  Recursively find all list fields in a dataclass.

  Args:
    clz: The dataclass type to inspect
    path: Current path in the hierarchy (used for recursion)

  Returns:
    List of dotted field names that are list types
  """
  result = []
  for f in fields(clz):
    concrete_type = unpack_type(f.type)  # type: ignore[arg-type]

    if is_dataclass(concrete_type):
      # Recurse into nested dataclass
      nested_fields = _get_list_fields(concrete_type, path + [f.name])
      result.extend(nested_fields)
    else:
      # Check if this is a list field
      origin = get_origin(concrete_type)
      if origin is list:
        # Add dotted path to this field
        field_path = ".".join(path + [f.name])
        result.append(field_path)

  return result


T = TypeVar("T")


def get_config(
  clz: type[T],
  name: str = "project",
  user: bool = True,
  project: bool = True,
  cli: bool = True,
  args: list[str] | None = None,  # used for testing, simulating sys.argv
  security: SecurityConfig | None = None,
) -> T:
  """
  Load configuration from TOML files and CLI arguments.

  Merges configuration from (in order of precedence):
  1. CLI arguments (highest priority) - only when cli=True or args is provided
  2. Project-level TOML: ./{name}.toml
  3. User-level TOML: ~/.{name}.toml
  4. Dataclass defaults (lowest priority)

  TOML Parser Selection:
      Automatically selects parser based on installed extras:
      - envtoml: Supports ${VAR} interpolation - pip install clevis[envtoml]
      - tomlev: Alternative parser - pip install clevis[tomlev]
      - tomli: Pure Python - pip install clevis[tomli]
      - tomllib: Python 3.11+ stdlib (no extras needed)

  Args:
      clz: The dataclass type to populate
      name: Configuration file name (without .toml extension)
      user: Whether to load user-level config(~/.{name}.toml)
      project: Whether to load project-level config (./{name}.toml)
      cli: Whether to parse CLI arguments from sys.argv (default: True)
      args: Optional list of CLI arguments (overrides sys.argv when provided)
      security: Security check configuration. If None, defaults to maximally
          strict (reject on all security issues).

  Returns:
      An instance of the dataclass with merged configuration

  Raises:
      ConfigError: If required fields are missing or values have wrong type
      SecurityError: If security checks fail (when action="reject")
      ImportError: If no TOML parser is available
  """
  # Default security: reject all
  if security is None:
    security = {
      "file_permissions": SecurityAction.REJECT,
      "directory_permissions": SecurityAction.REJECT,
    }

  cfg: dict[str, Any] = {}

  # Get config file paths
  user_config = Path.home() / USER_CONFIG_TEMPLATE.format(name=name)
  project_config = Path.cwd() / PROJECT_CONFIG_TEMPLATE.format(name=name)

  # Validate security and load config files
  # Note: TOCTOU-safe file permission checks
  file_action = security.get("file_permissions", SecurityAction.REJECT)
  dir_action = security.get("directory_permissions", SecurityAction.REJECT)

  # Check directory permissions (not TOCTOU-critical)
  _check_directory_permissions(user_config, dir_action)
  _check_directory_permissions(project_config, dir_action)

  # Load user-level config (TOCTOU-safe)
  # Note: _load_toml_from_fd wraps fd in a file object that takes ownership
  # and closes it when done. No explicit fd close needed here.
  if user:
    _, user_fd = _check_file_permissions(user_config, file_action)
    if user_fd is not None:
      cfg.update(_load_toml_from_fd(user_fd))

  # Load project-level config (TOCTOU-safe)
  # Note: _load_toml_from_fd wraps fd in a file object that takes ownership
  # and closes it when done. No explicit fd close needed here.
  if project:
    _, project_fd = _check_file_permissions(project_config, file_action)
    if project_fd is not None:
      cfg.update(_load_toml_from_fd(project_fd))

  # Extract subcommand section from TOML config if applicable
  # When @configclass(cmd="print") or @configclass(config="print") is used,
  # TOML config like [print]\nrich = true should be extracted to root level before from_dict
  factory = get_factory(clz)
  toml_key = factory.config or factory.cmd
  if toml_key and toml_key in cfg:
    # Extract the command section and merge to root level
    cmd_cfg = cfg.pop(toml_key)
    if isinstance(cmd_cfg, dict):
      # Clear cfg to prevent root fields from leaking into subcommand config
      cfg.clear()
      cfg.update(cmd_cfg)
    else:
      raise ConfigError(
        message=(
          f"Configuration section '{toml_key}' must be a table "
          f"(e.g., [{toml_key}]), got {type(cmd_cfg).__name__}"
        ),
        field_path=toml_key,
        config_name=name,
        suggest_cli=cli,
      )

  # Parse CLI args if requested and merge them into the config
  if cli or args is not None:
    cli_args = get_factory(clz).get_args(args)
    # Merge list args with TOML values, keeping non-list CLI args
    cfg = _merge_list_args(clz, cli_args, cfg)

  # Convert dict to dataclass
  # Use cast=[tuple, set] to convert TOML lists to tuples and sets
  try:
    return from_dict(data_class=clz, data=cfg, config=Config(cast=[tuple, set]))
  except MissingValueError as e:
    # Extract field path from dacite error message
    # Format: 'missing value for field "database.host"'
    error_msg = str(e)
    if '"' in error_msg:
      field_path = error_msg.split('"')[1]
    else:
      field_path = error_msg
    raise ConfigError(
      message="Required field has no value",
      field_path=field_path,
      config_name=name,
      suggest_cli=cli,
    ) from None
  except WrongTypeError as e:
    # Extract field path and type info from dacite error
    error_msg = str(e)
    if '"' in error_msg:
      field_path = error_msg.split('"')[1]
    else:
      field_path = error_msg
    raise ConfigError(
      message="Wrong type for field",
      field_path=field_path,
      config_name=name,
      suggest_cli=cli,
    ) from None
  except DaciteError as e:
    # Catch any other dacite errors
    raise ConfigError(
      message=str(e),
      field_path="unknown",
      config_name=name,
      suggest_cli=cli,
    ) from None
  except TypeError as e:
    # Catch TypeError from dacite when default_factory fails
    # (e.g., required field in nested dataclass)
    # Try to extract field name from error message
    error_msg = str(e)
    # Format: "DatabaseConfig.__init__() missing 1 required positional argument: 'host'"
    if "required positional argument:" in error_msg:
      # Extract the class name and argument name
      match = re.search(r"(\w+)\.__init__\(\).*missing.*argument: '(\w+)'", error_msg)
      if match:
        class_name = match.group(1)
        arg_name = match.group(2)
        # Try to find the matching field in the dataclass
        for f in fields(clz):
          if is_dataclass(f.type):
            concrete_type = unpack_type(f.type)
            if concrete_type.__name__ == class_name:
              field_path = f"{f.name}.{arg_name}"
              raise ConfigError(
                message=f"Required nested field '{arg_name}' has no value",
                field_path=field_path,
                config_name=name,
                suggest_cli=cli,
              ) from None
    # Fallback if we can't parse the error
    raise ConfigError(
      message=f"Configuration initialization error: {error_msg}",
      field_path="unknown",
      config_name=name,
      suggest_cli=cli,
    ) from None


__all__ = [
  "Factory",
  "Parser",
  "SubParser",
  "SecurityAction",
  "SecurityConfig",
  "SecurityError",
  "get_factory",
  "has_factory",
  "configclass",
  "register_field",
  "get_config",
  "get_cmd",
  "ConfigError",
  "apply_to_dict",
  "unpack_type",
  "_reset_factories",
]
