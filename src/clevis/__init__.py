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

import argparse
import functools
from dataclasses import Field, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Callable, get_args

from dacite import from_dict
from dacite.exceptions import DaciteError, MissingValueError, WrongTypeError

__version__ = "0.1.0"


# TOML Parser Selection
# ---------------------
# Tries parsers in this order: envtoml > tomlev > tomli > tomllib


def _get_toml_parser() -> Callable:
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
    from tomlev.env_loader import expandvars
    import tomllib

    def load_with_tomlev(file):
      content = file.read()
      if isinstance(content, bytes):
        content = content.decode("utf-8")
      expanded = expandvars(content)
      return tomllib.loads(expanded)

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

    return tomllib.load
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
_toml_load: Callable | None = None


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


class ConfigError(Exception):
  """Raised when configuration is missing or invalid."""

  def __init__(self, message: str, field_path: str, config_name: str):
    self.message = message
    self.field_path = field_path
    self.config_name = config_name
    super().__init__(self._format_message())

  def _format_message(self) -> str:
    """Format a helpful error message with actionable suggestions."""
    lines = [f"\n{'=' * 70}"]
    lines.append(f"Configuration Error")
    lines.append(f"{'=' * 70}\n")

    lines.append(f"Field: {self.field_path}")
    lines.append(f"Issue: {self.message}\n")

    lines.append("Provide this value in one of these ways:\n")

    # Project config
    lines.append(f"  1. Project config: ./{self.config_name}.toml")
    parts = self.field_path.split(".")
    if len(parts) == 1:
      lines.append(f'     {parts[0]} = "your_value"')
    else:
      lines.append(f"     [{parts[0]}]")
      lines.append(f'     {".".join(parts[1:])} = "your_value"')
    lines.append("")

    # User config
    lines.append(f"  2. User config: ~/.{self.config_name}.toml")
    lines.append("     (same format as above)\n")

    # CLI argument (use dashes for dots and underscores)
    cli_arg = "--" + self.field_path.replace(".", "-").replace("_", "-")
    lines.append(f"  3. CLI argument: {cli_arg} <value>\n")

    lines.append(f"{'=' * 70}")
    return "\n".join(lines)


def unpack_type(type_def: type) -> type:
  """
  Given a type, if a union type, return the not-None type (dataclass).

  For Optional[T] or T | None, returns T.
  For non-union types, returns the type as-is.

  Args:
      type_def: The type to unpack

  Returns:
      The non-None type from a union, or the type itself

  Raises:
      ValueError: If union has more than 2 types (not supported yet)
  """
  types = get_args(type_def)
  # not a union type
  if len(types) == 0:
    return type_def
  # <type> | None is only supported combination
  if len(types) > 2:
    raise ValueError("Complex unions not supported")
  return types[0] if types[1] is type(None) else types[1]


def list_fields(clz: type, path: list[str] | None = None) -> list[tuple[Field, list[str]]]:
  """
  Recursively flatten and list all properties in nested dataclasses.

  Args:
      clz: The dataclass to inspect
      path: Current path in the hierarchy

  Yields:
      Tuples of (field, path) for each leaf field
  """
  path = [] if not path else path
  result = []
  for f in fields(clz):
    concrete_type = unpack_type(f.type)
    if is_dataclass(concrete_type):
      result.extend(list_fields(concrete_type, path=path + [f.name]))
    else:
      result.append((f, path))
  return result


def get_args_config(clz: type, args: list[str] | None = None) -> dict[str, Any]:
  """
  Construct an argparse parser from a dataclass hierarchy.

  Creates CLI arguments for each leaf field in the dataclass,
  using dashed notation for nested fields (e.g., --database-host).

  Args:
      clz: The dataclass type to generate parser for
      args: Optional list of CLI arguments (defaults to sys.argv[1:])

  Returns:
      Dictionary of parsed arguments with dotted keys
      Unprovided arguments have None values
  """
  parser = argparse.ArgumentParser()
  for f, path in list_fields(clz):
    name = ".".join(path + [f.name])  # concatenate intermediate classes with "."
    # Convert both dots and underscores to dashes for CLI args
    cli_name = name.replace(".", "-").replace("_", "-")
    arg = functools.partial(
      parser.add_argument,
      f"--{cli_name}",
      dest=name,  # name with dots
      default=None,  # Use None so TOML values aren't overridden
      help=f"provide {name}",
    )
    # complete partial: boolean switch of store value
    concrete_type = unpack_type(f.type)
    if concrete_type is bool:
      _ = arg(action="store_true")
    else:
      _ = arg(type=concrete_type)

  return vars(parser.parse_args(args))


def apply_to_dict(args: dict[str, Any], dct: dict[str, Any]) -> None:
  """
  Apply dotted command line arguments to a nested dictionary.

  Modifies the dictionary in-place, creating nested structure as needed.

  Args:
      args: Dictionary with dotted keys (e.g., "database.host")
      dct: Target dictionary to modify
  """
  for key, value in args.items():
    if value is not None:  # default optional value, can't be set through command line
      parts = key.split(".")
      final_key = parts.pop()
      # follow path into hierarchy
      scope = dct
      for step in parts:
        try:
          scope = scope[step]  # follow
        except KeyError:
          scope[step] = {}  # create missing
          scope = scope[step]
      # set value
      scope[final_key] = value  # upsert key=value


def get_config(
  data_class: type,
  name: str = "project",
  user: bool = True,
  project: bool = True,
  args: list[str] | None = None,
) -> Any:
  """
  Load configuration from TOML files and CLI arguments.

  Merges configuration from (in order of precedence):
  1. CLI arguments (highest priority)
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
      data_class: The dataclass type to populate
      name: Configuration file name (without .toml extension)
      user: Whether to load user-level config(~/.{name}.toml)
      project: Whether to load project-level config (./{name}.toml)
      args: Optional list of CLI arguments (defaults to sys.argv[1:])

  Returns:
      An instance of the dataclass with merged configuration

  Raises:
      ConfigError: If required fields are missing or values have wrong type
      ImportError: If no TOML parser is available
  """
  cfg: dict[str, Any] = {}

  # Load user-level config
  if user:
    user_path = Path.home() / f".{name}.toml"
    if user_path.exists():
      cfg.update(_load_toml(user_path.open("rb")))

  # Load project-level config
  if project:
    project_path = Path.cwd() / f"{name}.toml"
    if project_path.exists():
      cfg.update(_load_toml(project_path.open("rb")))

  # Get CLI args based on dataclass hierarchy
  cli_args = get_args_config(data_class, args)

  # Merge CLI args into config
  apply_to_dict(cli_args, cfg)

  # Convert dict to dataclass
  try:
    return from_dict(data_class=data_class, data=cfg)
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
    ) from None
  except DaciteError as e:
    # Catch any other dacite errors
    raise ConfigError(
      message=str(e),
      field_path="unknown",
      config_name=name,
    ) from None