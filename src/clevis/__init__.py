"""Clevis - Configuration management for Python projects.

This module provides the main entry point for Clevis configuration management,
offering dataclass-based schemas with TOML file support, environment variable
interpolation, and automatic CLI argument generation.

Main Components:
  - get_config(): Load configuration from all sources (TOML + CLI + env)
  - get_cmd(): Get active subcommand name from parsed arguments
  - configclass: Decorator combining @dataclass with factory registration
  - register_field(): Add fields at runtime for plugin architectures

Security:
  File permission validation via SecurityAction enum (DONT_CHECK, LOG, REJECT).
  Default is REJECT for production security.

TOML Parser Selection (priority order):
  1. envtoml  - Env var interpolation (${VAR}) - pip install clevis[envtoml]
  2. tomlev   - Env vars with defaults (${VAR|default}) - pip install clevis[tomlev]
  3. tomli    - Pure Python TOML - pip install clevis[tomli]
  4. tomllib  - Stdlib (Python 3.11+) - no extras needed

Example:
  from dataclasses import dataclass
  from clevis import get_config

  @dataclass
  class Config:
      name: str = "MyApp"
      debug: bool = False

  config = get_config(Config, name="myapp")
"""

import io
import logging
import os
import re
import stat
from collections.abc import Callable
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypedDict, TypeVar, get_origin, runtime_checkable

from dacite import Config, from_dict
from dacite.exceptions import DaciteError, MissingValueError, WrongTypeError

from clevis import factory as _factory_module
from clevis.configclass import configclass
from clevis.factory import (
  Factory,
  Parser,
  SubParser,
  _is_cli_excluded,
  _reset_factories,
  apply_to_dict,
  get_factory,
  has_factory,
  unpack_type,
)
from clevis.registration import register_field

__version__ = "0.6.0"

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


def check_file_permissions(path: Path, action: SecurityAction) -> tuple[bool, int | None]:
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


def check_directory_permissions(path: Path, action: SecurityAction) -> bool:
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


def load_toml_from_fd(fd: int) -> dict[str, Any]:
  """Load TOML from a file descriptor.

  Wraps the file descriptor in a file object for TOML parser.
  The file object takes ownership of the fd and closes it.

  Args:
      fd: File descriptor opened in read mode

  Returns:
      Dictionary of parsed TOML data
  """
  file_obj = os.fdopen(fd, "rb")
  # File object takes ownership of fd and will close it
  return _load_toml(file_obj)


# Public TOML API
# ---------------
# Raw parsers (no security checks), matching stdlib tomllib signatures.
# Use the same parser selection chain as get_config (envtoml > tomlev > tomli > tomllib).


def load(fp: Any) -> dict[str, Any]:
  """Load TOML from a binary file object.

  Drop-in compatible with ``tomllib.load``. Uses Clevis's automatic parser
  selection (envtoml > tomlev > tomli > tomllib).

  This is a RAW parser: no security checks (file permissions, directory
  permissions, TOCTOU-safe access). To load TOML config files with security
  validation, use :func:`get_config` or construct a
  :class:`UserConfigProvider` / :class:`ProjectConfigProvider`.

  Args:
      fp: A binary file object (opened with mode ``'rb'``).

  Returns:
      Parsed TOML as a dictionary.

  Raises:
      ImportError: If no TOML parser is available.
      Exception: Parser-specific errors for invalid TOML.
  """
  return _load_toml(fp)


def loads(s: str) -> dict[str, Any]:
  """Load TOML from a string.

  Drop-in compatible with ``tomllib.loads``. Uses Clevis's automatic parser
  selection.

  This is a RAW parser with no security checks (there is no file to check
  for a string input).

  Args:
      s: A string containing TOML data.

  Returns:
      Parsed TOML as a dictionary.

  Raises:
      ImportError: If no TOML parser is available.
      Exception: Parser-specific errors for invalid TOML.
  """
  return _load_toml(io.BytesIO(s.encode("utf-8")))


# Descriptive aliases for discoverability (same functions, explicit "toml" name).
load_toml = load
loads_toml = loads


# Config Provider Protocol
# ------------------------
# Pluggable config sources for the cascade middle layer. Each provider is a
# zero-argument callable that owns its own security and returns a dict.


@runtime_checkable
class ConfigProvider(Protocol):
  """Callable protocol that provides a configuration dict.

  A ConfigProvider is a zero-argument callable returning a dict of
  configuration data. Providers own their own security/validation (file
  permission checks, path resolution, TOCTOU-safe access) and raise on
  failure. Callers do not pass ``name`` or ``security`` arguments to the
  provider; the provider captures everything it needs at construction time.

  Security Contract:
      Each provider is responsible for its own security validation. Clevis
      does not authenticate or validate provider security postures. Custom
      providers bypass clevis's default security checks — use
      :class:`UserConfigProvider` / :class:`ProjectConfigProvider` as secure
      building blocks for file-based providers.

  Returns:
      A dict of configuration values. Nested dicts are deep-merged across
      providers in cascade order.

  Raises:
      Any exception on failure. :class:`SecurityError` should be raised for
      security check failures to stay consistent with the default providers.
  """

  def __call__(self) -> dict[str, Any]:
    """Return a configuration dict. Raise on failure."""
    ...


def _default_security(security: SecurityConfig | None) -> SecurityConfig:
  """Resolve a security config, defaulting to maximally strict (REJECT)."""
  if security is None:
    return {
      "file_permissions": SecurityAction.REJECT,
      "directory_permissions": SecurityAction.REJECT,
    }
  return security


class FileConfigProvider:
  """Shared base for file-based TOML config providers.

  Encapsulates the TOCTOU-safe FD access pattern: open FD → fstat → read from
  the same FD. Also runs directory permission checks before opening the file.
  Subclass this to get security checks for free when loading TOML from
  non-standard paths.

  Subclasses customize resolution by setting ``_path_template`` (a
  ``{name}``-style format string) and overriding ``_root_dir`` to return the
  directory the formatted filename is joined against.
  """

  _path_template: str

  def __init__(self, name: str, security: SecurityConfig | None = None) -> None:
    self._name = name
    self._security = _default_security(security)
    self._path = self._resolve_path(name)

  def _root_dir(self) -> Path:  # pragma: no cover - overridden
    raise NotImplementedError

  def _resolve_path(self, name: str) -> Path:
    return self._root_dir() / self._path_template.format(name=name)

  def __call__(self) -> dict[str, Any]:
    file_action = self._security.get("file_permissions", SecurityAction.REJECT)
    dir_action = self._security.get("directory_permissions", SecurityAction.REJECT)

    check_directory_permissions(self._path, dir_action)
    _, fd = check_file_permissions(self._path, file_action)
    if fd is None:
      # File doesn't exist — not an error, contribute nothing.
      return {}
    # load_toml_from_fd wraps fd in a file object that takes ownership and closes it.
    return load_toml_from_fd(fd)


class UserConfigProvider(FileConfigProvider):
  """ConfigProvider that loads user-level TOML (``~/.{name}.toml``).

  Owns its own security checks (file and directory permissions, TOCTOU-safe
  FD access). If the file does not exist, returns an empty dict. This is a
  public, reusable building block for custom cascades.
  """

  _path_template = USER_CONFIG_TEMPLATE

  def _root_dir(self) -> Path:
    return Path.home()


class ProjectConfigProvider(FileConfigProvider):
  """ConfigProvider that loads project-level TOML (``./{name}.toml``).

  Owns its own security checks (file and directory permissions, TOCTOU-safe
  FD access). If the file does not exist, returns an empty dict. This is a
  public, reusable building block for custom cascades.
  """

  _path_template = PROJECT_CONFIG_TEMPLATE

  def _root_dir(self) -> Path:
    return Path.cwd()


DEFAULT_CASCADE: tuple[type[ConfigProvider], ...] = (UserConfigProvider, ProjectConfigProvider)
"""Default cascade of provider classes (user-TOML, then project-TOML).

Each entry is a class accepting ``(name, security)`` at construction and
producing a :class:`ConfigProvider` instance. ``get_config`` instantiates
these with the ``name`` and ``security`` arguments when ``cascade`` is not
provided.

The most common customization is to **append** a custom provider to the
default cascade. Use :func:`build_default_cascade` to get the default
providers, then add your own::

    from clevis import build_default_cascade, get_config

    class EnvProvider:
        def __call__(self) -> dict:
            return {"api_key": os.environ.get("API_KEY", "")}

    cascade = build_default_cascade("myapp") + [EnvProvider()]
    config = get_config(Config, name="myapp", cascade=cascade)

For a **fully custom cascade**, construct provider instances directly::

    from clevis import UserConfigProvider, ProjectConfigProvider

    cascade = [
        UserConfigProvider("myapp", security),
        MyCustomProvider(),
        ProjectConfigProvider("myapp", security),
    ]
    config = get_config(Config, name="myapp", cascade=cascade)
"""


def build_default_cascade(
  name: str,
  security: SecurityConfig | None = None,
  user: bool = True,
  project: bool = True,
) -> list[ConfigProvider]:
  """Build a list of default :class:`ConfigProvider` instances.

  Instantiates :data:`DEFAULT_CASCADE` classes with the given ``name`` and
  ``security``, filtered by the ``user``/``project`` flags. Use this to
  append custom providers while keeping the secure defaults::

      cascade = build_default_cascade("myapp") + [MyCustomProvider()]
      config = get_config(Config, name="myapp", cascade=cascade)

  Args:
      name: Configuration file name (without ``.toml`` extension).
      security: Security config for the providers. Defaults to maximally
          strict (REJECT) when ``None``.
      user: Whether to include :class:`UserConfigProvider`.
      project: Whether to include :class:`ProjectConfigProvider`.

  Returns:
      A list of instantiated :class:`ConfigProvider` objects.
  """
  result: list[ConfigProvider] = []
  for provider_cls in DEFAULT_CASCADE:
    if provider_cls is UserConfigProvider and not user:
      continue
    if provider_cls is ProjectConfigProvider and not project:
      continue
    result.append(provider_cls(name, security))
  return result


def load_toml_file(path: Path, security: SecurityConfig | None = None) -> dict[str, Any]:
  """Securely load a TOML file with Clevis's default security checks.

  Combines directory check, TOCTOU-safe file check, and TOML parsing.
  Returns an empty dict if the file does not exist. This is the
  ready-to-use function for custom :class:`ConfigProvider` authors who
  load TOML from non-standard paths.

  Args:
      path: Path to the TOML file.
      security: Security config. Defaults to maximally strict (REJECT)
          when ``None``.

  Returns:
      Parsed TOML as a dictionary, or an empty dict if the file is absent.

  Raises:
      SecurityError: If a security check fails with ``SecurityAction.REJECT``.
  """
  resolved = _default_security(security)
  file_action = resolved.get("file_permissions", SecurityAction.REJECT)
  dir_action = resolved.get("directory_permissions", SecurityAction.REJECT)

  check_directory_permissions(path, dir_action)
  _, fd = check_file_permissions(path, file_action)
  if fd is None:
    return {}
  # load_toml_from_fd wraps fd in a file object that takes ownership and closes it.
  return load_toml_from_fd(fd)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
  """Recursively merge ``overlay`` onto ``base``, returning a new dict.

  - When both ``base[key]`` and ``overlay[key]`` are dicts: recurse.
  - Otherwise: ``overlay[key]`` replaces ``base[key]`` (including lists and
    scalars; lists are replaced, not appended).
  - Input dicts are not modified.

  This is the merge strategy used by the config cascade middle layer.
  Override providers replace entire lists; only nested dicts are merged
  recursively. CLI args (a fixed last bookend) still append to list fields
  via ``_merge_list_args``.

  Args:
      base: The base dict (lower precedence).
      overlay: The overlay dict (higher precedence).

  Returns:
      A new dict with the merged result.
  """
  result: dict[str, Any] = {}
  for key, value in base.items():
    if isinstance(value, dict):
      # Recursively copy so nested base dicts that the overlay doesn't touch
      # are still independent from the input (callers can mutate result
      # without affecting base).
      result[key] = deep_merge(value, {})
    else:
      result[key] = value
  for key, value in overlay.items():
    if key in result and isinstance(result[key], dict) and isinstance(value, dict):
      result[key] = deep_merge(result[key], value)
    else:
      result[key] = value
  return result


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


def _is_field_path_excluded(clz: type, field_path: str) -> bool:
  """
  Check whether a dotted field path is excluded from the CLI subsystem.

  Walks the dataclass hierarchy following ``field_path`` and returns True if
  any field along the path has ``metadata["cli"] is False``. This uses the
  centralized ``_is_cli_excluded`` predicate so there is a single definition of
  "excluded." Used by the ConfigError path to decide whether to suppress the
  CLI argument suggestion (``suggest_cli=False``) for excluded fields.

  Args:
    clz: The root dataclass type.
    field_path: Dotted path like "database.host" or "secret".

  Returns:
    True if the field or any ancestor in the path is excluded from CLI.
  """
  parts = field_path.split(".")
  current: type = clz
  for index, part in enumerate(parts):
    found = None
    for f in fields(current):
      if f.name == part:
        found = f
        break
    if found is None:
      return False
    if _is_cli_excluded(found):
      return True
    if index < len(parts) - 1:
      concrete_type = unpack_type(found.type)  # type: ignore[arg-type]
      if not is_dataclass(concrete_type):
        return False
      current = concrete_type
  return False


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
  parsed_args = vars(_factory_module._parse_with_default(parser, args))
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
  cascade: list[ConfigProvider] | None = None,
) -> T:
  """
  Load configuration from TOML files and CLI arguments.

  Merges configuration from (in order of precedence):
  1. CLI arguments (highest priority) - only when cli=True or args is provided
  2. Middle cascade (default: project TOML, then user TOML) - deep-merged
  3. Dataclass defaults (lowest priority, filled by dacite)

  The middle cascade is a list of :class:`ConfigProvider` instances. When
  ``cascade`` is ``None`` (the default), the default cascade is built from
  :data:`DEFAULT_CASCADE` and filtered by the ``user``/``project`` flags.
  When ``cascade`` is a list, those providers replace the default middle
  layers and the ``user``/``project`` flags are ignored.

  The middle cascade uses deep (recursive) merge: nested tables are merged
  key-by-key rather than replaced wholesale. This is a breaking change from
  the previous shallow ``dict.update`` behavior — see the changelog.

  WARNING: When a custom cascade is provided, clevis's default security
  checks do NOT apply automatically. Each provider owns its own security. Use
  :class:`UserConfigProvider` / :class:`ProjectConfigProvider` as secure
  building blocks, or apply the same checks manually with
  :func:`check_file_permissions` / :func:`check_directory_permissions` /
  :func:`load_toml_from_fd`. See also :func:`load_toml_file` for a convenient
  all-in-one secure loader.

  TOML Parser Selection:
      Automatically selects parser based on installed extras:
      - envtoml: Supports ${VAR} interpolation - pip install clevis[envtoml]
      - tomlev: Alternative parser - pip install clevis[tomlev]
      - tomli: Pure Python - pip install clevis[tomli]
      - tomllib: Python 3.11+ stdlib (no extras needed)

  Args:
      clz: The dataclass type to populate
      name: Configuration file name (without .toml extension)
      user: Whether to load user-level config(~/.{name}.toml). Ignored when
          ``cascade`` is provided.
      project: Whether to load project-level config (./{name}.toml). Ignored
          when ``cascade`` is provided.
      cli: Whether to parse CLI arguments from sys.argv (default: True)
      args: Optional list of CLI arguments (overrides sys.argv when provided)
      security: Security check configuration for the default providers. If
          None, defaults to maximally strict (reject on all security issues).
          Ignored when ``cascade`` is provided (providers own their security).
      cascade: Optional list of :class:`ConfigProvider` instances replacing
          the default middle layers. When provided, ``user``/``project`` and
          ``security`` are ignored.

  Returns:
      An instance of the dataclass with merged configuration

  Raises:
      ConfigError: If required fields are missing or values have wrong type
      SecurityError: If security checks fail (when action="reject")
      ImportError: If no TOML parser is available
  """
  # Build the active middle cascade.
  if cascade is not None:
    if security is not None:
      logger.warning(
        "security= parameter is ignored when cascade= is provided. "
        "Each provider in the cascade owns its own security configuration."
      )
    active_cascade = list(cascade)
  else:
    active_cascade = build_default_cascade(name, security, user=user, project=project)

  # Deep-merge middle cascade in order (later providers override earlier).
  cfg: dict[str, Any] = {}
  for provider in active_cascade:
    cfg = deep_merge(cfg, provider())

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
      suggest_cli=cli and not _is_field_path_excluded(clz, field_path),
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
      suggest_cli=cli and not _is_field_path_excluded(clz, field_path),
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
                suggest_cli=cli and not _is_field_path_excluded(clz, field_path),
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
  # Config override cascade (P1-006)
  "ConfigProvider",
  "FileConfigProvider",
  "UserConfigProvider",
  "ProjectConfigProvider",
  "DEFAULT_CASCADE",
  "build_default_cascade",
  "deep_merge",
  # Public TOML API (P1-006)
  "load",
  "loads",
  "load_toml",
  "loads_toml",
  # Public security helpers (P1-006)
  "check_file_permissions",
  "check_directory_permissions",
  "load_toml_from_fd",
  "load_toml_file",
]
