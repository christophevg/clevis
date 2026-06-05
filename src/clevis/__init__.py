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
from argparse import Action, Namespace
from collections.abc import Callable
from dataclasses import Field, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Protocol, TypeVar, get_args

from dacite import from_dict
from dacite.exceptions import DaciteError, MissingValueError, WrongTypeError

__version__ = "0.2.0"

# Factory support


class Parser(Protocol):
  """
  Protocol for argparse-compatible parsers.

  Any class implementing these two methods can be used as a parser
  for Clevis configuration.
  """

  def add_argument(
    self,
    *name_or_flags: str,
    action: str | type[Action] = ...,
    default: Any = ...,
    type: Any = ...,
    help: str | None = ...,
    dest: str | None = ...,
    **kwargs: Any,
  ) -> Action:
    """Add an argument to the parser."""
    ...

  def add_subparsers(self, **kwargs: Any) -> "SubParser": ...

  def parse_args(self, args: list[str] | None = None) -> Namespace:
    """Parse arguments and return a Namespace."""
    ...


class SubParser(Protocol):
  def add_parser(self, name: str) -> Parser: ...


# the default parser is assigned to Factories that aren't initialized with a parser
_default_parser: argparse.ArgumentParser = argparse.ArgumentParser()

_sub_parsers: dict[Parser, Any] = {}


def get_sub_parser(parser: Parser) -> "SubParser":
  global _sub_parsers
  try:
    return _sub_parsers[parser]  # type: ignore[no-any-return]
  except KeyError:
    _sub_parsers[parser] = parser.add_subparsers(dest="cmd")
    _sub_parsers[parser].required = True
    return _sub_parsers[parser]  # type: ignore[no-any-return]


@dataclass
class Factory:
  """
  Configuration factory for a dataclass.

  Collects parser configuration for deferred setup, allowing orchestration
  code to customize prefixes and parsers before configuration loading.

  Attributes:
    config_class: The dataclass type this factory configures.
    prefix: Optional CLI argument prefix (e.g., "app1" -> "--app1-name").
    parser: The argparse-compatible parser to use.
  """

  config_class: type
  prefix: str | None = None
  parser: Parser = field(default_factory=lambda: _default_parser)  # type: ignore[assignment]
  cmd: str | None = None
  sub_parser: Parser | None = field(init=False, default=None)

  _configured: bool = False

  def configure_parser(self) -> None:
    """
    Configure the parser with arguments for this config class.

    Called automatically on first get_config() - usually not called directly.
    """
    if self._configured:
      return
    if self.cmd:
      self.sub_parser = get_sub_parser(self.parser).add_parser(self.cmd)
    self._configured = True
    for f, path in self.list_fields():
      name = ".".join(path + [f.name])  # concat intermediate classes with "."
      cli_name = name.replace(".", "-").replace("_", "-")
      if self.prefix:
        cli_name = f"{self.prefix}-{cli_name}"
        name = f"{self.prefix}.{name}"
      parser = self.sub_parser if self.sub_parser else self.parser
      arg = functools.partial(
        parser.add_argument,
        f"--{cli_name}",
        dest=name,  # name with dots
        default=None,  # Use None so TOML values aren't overridden
        help=f"provide {name}",
      )
      # complete partial: boolean switch of store value
      concrete_type = unpack_type(f.type)  # type: ignore[arg-type]
      if concrete_type is bool:
        _ = arg(action="store_true")
      else:
        _ = arg(type=concrete_type)

  def get_args(self, args: list[str] | None = None) -> dict[str, Any]:
    """
    Parse CLI arguments and return as dictionary.

    Args:
      args: CLI arguments (defaults to sys.argv[1:])

    Returns:
      Dictionary with dotted keys (e.g., {"database.host": "localhost"}).
      If prefix is set, keys are stripped of the prefix.
    """
    args_dict = vars(_ensure_configured(self.parser).parse_args(args))
    if self.prefix:
      args_dict = {
        key[len(self.prefix) + 1 :]: value
        for key, value in args_dict.items()
        if key.startswith(self.prefix)
      }
    return args_dict

  def list_fields(
    self, clz: type | None = None, path: list[str] | None = None
  ) -> list[tuple[Field[Any], list[str]]]:
    """
    Recursively list all fields in nested dataclasses.

    Args:
      clz: The dataclass to inspect (defaults to self.config_class)
      path: Current path in the hierarchy (used for recursion)

    Returns:
      List of (field, path) tuples for each leaf field.
    """
    clz = self.config_class if clz is None else clz
    path = [] if path is None else path
    result = []
    for f in fields(clz):
      concrete_type = unpack_type(f.type)  # type: ignore[arg-type]
      if is_dataclass(concrete_type):
        result.extend(self.list_fields(concrete_type, path=path + [f.name]))
      else:
        result.append((f, path))
    return result


# factories for configurations
_factories: dict[type, Factory] = {}


def get_factory(clz: type) -> Factory:
  """
  Get the Factory for a configuration class.

  Returns the same Factory instance for a given class (singleton pattern).
  Creates a new Factory if one doesn't exist.

  Args:
    clz: The dataclass type to get a factory for.

  Returns:
    Factory instance for the given class.
  """
  global _factories
  try:
    return _factories[clz]
  except KeyError:
    # create default factory
    _factories[clz] = Factory(clz)
    return _factories[clz]


T = TypeVar("T")


def configclass(
  cls: type[T] | None = None, cmd: str | None = None
) -> type | Callable[[type[T]], type[T]]:
  """
  Decorator that registers a dataclass with Clevis's factory system.

  Applies @dataclass to the class and registers it with get_factory().

  Usage::

    @configclass
    class MyConfig:
      name: str = "default"

  This is equivalent to::

    @dataclass
    class MyConfig:
      name: str = "default"

    get_factory(MyConfig)  # register

  Args:
    clz: The class to decorate.

  Returns:
    The decorated class (now a dataclass).
  """

  def decorator(clz: type[T]) -> type[T]:
    clz = dataclass(clz)
    factory = get_factory(clz)  # get_factory upserts if not yet available
    if cmd:
      factory.cmd = cmd
    return clz

  if cls and not cmd:
    return decorator(cls)
  else:
    return lambda clz: decorator(clz)


def _reset_factories() -> None:
  """
  Clear all registered factories and configured parsers.

  For testing only - ensures test isolation by resetting global state.
  Creates a fresh default parser.
  """
  global _factories, _configured_parsers, _default_parser, _sub_parsers
  _factories = {}
  _configured_parsers = []
  _default_parser = argparse.ArgumentParser()
  _sub_parsers = {}


# keeps track if parser is configured
_configured_parsers: list[Parser] = []


def _ensure_configured(parser: Parser) -> Parser:
  """
  Ensure a parser is fully configured by all factories that use it.

  Lazy configuration - called on first get_config() for a given parser.
  """
  global _configured_parsers
  if parser not in _configured_parsers:
    # lazy configure using each factory having this parser
    for factory in _factories.values():
      if factory.parser is parser:
        factory.configure_parser()
    _configured_parsers.append(parser)
  return parser


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

    # CLI argument - only suggest when appropriate
    if self.suggest_cli:
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
  return types[0] if types[1] is type(None) else types[1]  # type: ignore[no-any-return]


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


def get_cmd(parser: Any = None, args: list[str] | None = None) -> str | None:
  """
  Get the active subcommand name from parsed arguments.

  Args:
    parser: Optional parser to use (defaults to _default_parser)
    args: Optional list of CLI arguments (for testing)

  Returns:
    The subcommand name or None if no subcommand was used
  """
  if not parser:
    parser = _default_parser
  parsed_args = vars(_ensure_configured(parser).parse_args(args))
  cmd: str | None = parsed_args.pop("cmd", None)
  return cmd


def get_config(
  clz: type[T],
  name: str = "project",
  user: bool = True,
  project: bool = True,
  cli: bool = True,
  args: list[str] | None = None,  # used for testing, simulating sys.argv
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

  # Parse CLI args if requested and merge them into the config
  if cli or args is not None:
    apply_to_dict(get_factory(clz).get_args(args), cfg)

  # Convert dict to dataclass
  try:
    return from_dict(data_class=clz, data=cfg)
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
      import re

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
  "get_factory",
  "configclass",
  "get_config",
  "get_cmd",
  "ConfigError",
  "apply_to_dict",
  "unpack_type",
  "_reset_factories",
]
