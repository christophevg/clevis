"""
Type stubs for clevis - Configuration management for Python projects.

Provides type hints for IDE autocompletion and static type checking.
"""

from argparse import Action, Namespace
from collections.abc import Callable
from dataclasses import Field, dataclass
from enum import Enum
from typing import Any, Protocol, TypedDict, TypeVar

# Type Variables

T = TypeVar("T")

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

  path: str
  check: str

  def __init__(self, message: str, path: str, check: str) -> None: ...

# Protocols

class Parser(Protocol):
  """
  Protocol for argparse-compatible parsers.

  Any class implementing these methods can be used as a parser for Clevis configuration.
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

  def add_subparsers(self, **kwargs: Any) -> SubParser: ...
  def parse_args(self, args: list[str] | None = None) -> Namespace:
    """Parse arguments and return a Namespace."""
    ...

class SubParser(Protocol):
  """Protocol for sub-parser management."""

  def add_parser(
    self,
    name: str,
    help: str | None = ...,
    aliases: list[str] | None = ...,
    **kwargs: Any,
  ) -> Parser:
    """Add a subparser with optional help and aliases."""
    ...

# Classes

@dataclass
class Factory:
  """
  Configuration factory for a dataclass.

  Collects parser configuration for deferred setup, allowing orchestration
  code to customize prefixes and parsers before configuration loading.
  """

  config_class: type
  prefix: str | None = None
  parser: Parser = ...
  cmd: str | None = None
  help: str | None = None
  aliases: list[str] | None = None
  sub_parser: Parser | None = ...

  _configured: bool = False

  def configure_parser(self) -> None:
    """
    Configure the parser with arguments for this config class.

    Called automatically on first get_config() - usually not called directly.
    """
    ...

  def get_args(self, args: list[str] | None = None) -> dict[str, Any]:
    """
    Parse CLI arguments and return as dictionary.

    Args:
      args: CLI arguments (defaults to sys.argv[1:])

    Returns:
      Dictionary with dotted keys (e.g., {"database.host": "localhost"}).
      If prefix is set, keys are stripped of the prefix.
    """
    ...

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
    ...

class ConfigError(Exception):
  """Raised when configuration is missing or invalid."""

  message: str
  field_path: str
  config_name: str
  suggest_cli: bool

  def __init__(
    self,
    message: str,
    field_path: str,
    config_name: str,
    suggest_cli: bool = ...,
  ) -> None: ...

# Functions

def get_config(
  clz: type[T],
  name: str = ...,
  user: bool = ...,
  project: bool = ...,
  cli: bool = ...,
  args: list[str] | None = ...,
  security: SecurityConfig | None = ...,
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
  ...

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
  ...

def get_cmd(parser: Any = None, args: list[str] | None = None) -> str | None:
  """
  Get the active subcommand name from parsed arguments.

  Args:
    parser: Optional parser to use (defaults to _default_parser)
    args: Optional list of CLI arguments (for testing)

  Returns:
    The subcommand name or None if no subcommand was used.
  """
  ...

def get_sub_parser(parser: Parser) -> SubParser:
  """
  Get or create a sub-parser for a given parser.

  Args:
    parser: The parser to get a sub-parser for.

  Returns:
    The SubParser instance for adding subcommands.
  """
  ...

def apply_to_dict(args: dict[str, Any], dct: dict[str, Any]) -> None:
  """
  Apply dotted command line arguments to a nested dictionary.

  Modifies the dictionary in-place, creating nested structure as needed.

  Args:
      args: Dictionary with dotted keys (e.g., "database.host")
      dct: Target dictionary to modify
  """
  ...

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
  ...

def configclass(
  cls: type[T] | None = None,
  cmd: str | None = None,
  help: str | None = None,
  aliases: list[str] | None = None,
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
    cls: The class to decorate (when used without parentheses)
    cmd: Optional subcommand name for this config
    help: Optional help text for the subcommand
    aliases: Optional list of alternative names for the subcommand

  Returns:
    The decorated class (now a dataclass).
  """
  ...

def _reset_factories() -> None:
  """
  Clear all registered factories and configured parsers.

  For testing only - ensures test isolation by resetting global state.
  Creates a fresh default parser.
  """
  ...
