"""Factory module for configuration management.

Provides the Factory class for managing configuration dataclass parsers
and CLI argument generation.
"""

import argparse
import functools
from argparse import Action, Namespace
from dataclasses import Field, dataclass, field, fields, is_dataclass
from typing import Any, Literal, Protocol, Union, get_args, get_origin


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
  def add_parser(
    self,
    name: str,
    help: str | None = ...,
    aliases: list[str] | None = ...,
    **kwargs: Any,
  ) -> Parser: ...


# the default parser is assigned to Factories that aren't initialized with a parser
_default_parser: argparse.ArgumentParser = argparse.ArgumentParser()

_sub_parsers: dict[Parser, Any] = {}


def get_sub_parser(parser: Parser) -> SubParser:
  global _sub_parsers
  try:
    return _sub_parsers[parser]  # type: ignore[no-any-return]
  except KeyError:
    _sub_parsers[parser] = parser.add_subparsers(dest="cmd")
    _sub_parsers[parser].required = True
    return _sub_parsers[parser]  # type: ignore[no-any-return]


def unpack_type(type_def: type) -> type:
  """
  Given a type, if a union type, return the not-None type (dataclass).

  For Optional[T] or T | None, returns T.
  For container types (list, dict, set, tuple), returns as-is.
  For Literal types, returns as-is.
  For non-union types, returns the type as-is.

  Args:
      type_def: The type to unpack

  Returns:
      The non-None type from a union, or the type itself

  Raises:
      ValueError: If union has more than 2 types (not supported yet)
  """
  from types import UnionType

  origin = get_origin(type_def)

  # Handle container types (list, dict, set, tuple) - return as-is
  if origin in (list, dict, set, tuple):
    return type_def

  # Handle Literal types - return as-is (dacite validates)
  if origin is Literal:
    return type_def

  # Handle Union types (Optional[T] / T | None)
  # Not a union type - return as-is
  if origin is not Union and origin is not UnionType:
    return type_def

  types = get_args(type_def)
  # <type> | None is only supported combination
  if len(types) == 0:
    return type_def  # Not a generic/union
  if len(types) > 2:
    raise ValueError("Complex unions not supported")
  # T | None or None | T
  return types[0] if types[1] is type(None) else types[1]  # type: ignore[no-any-return]


# keeps track if parser is configured
_configured_parsers: list[Parser] = []

# Track which field owner classes have had their CLI args registered for each parser
# Key: parser, Value: set of (owner_class, field_name) tuples
# This prevents the same field from being registered twice
# (e.g., as --list-enabled and --tools-list-enabled)
_registered_field_owners: dict[Parser, set[tuple[type, str]]] = {}


def _ensure_configured(parser: Parser) -> Parser:
  """
  Ensure a parser is fully configured by all factories that use it.

  Lazy configuration - called on first get_config() for a given parser.
  """
  global _configured_parsers
  if parser not in _configured_parsers:
    # lazy configure using each factory having this parser
    # Convert to list to avoid RuntimeError if factories dict changes during iteration
    for factory in list(_factories.values()):
      if factory.parser is parser:
        factory.configure_parser()
    _configured_parsers.append(parser)
  return parser


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
    cmd: Optional subcommand name for CLI applications with multiple commands.
    help: Optional help text for the subcommand (used with cmd parameter).
    aliases: Optional list of aliases for the subcommand (used with cmd parameter).
    config: Optional TOML extraction key (defaults to cmd if not set).
    _nested_prefix: Tracks the nesting level in config hierarchy (internal).
  """

  config_class: type
  prefix: str | None = None
  parser: Parser = field(default_factory=lambda: _default_parser)  # type: ignore[assignment]
  cmd: str | None = None
  help: str | None = None
  aliases: list[str] | None = None
  config: str | None = None
  sub_parser: Parser | None = field(init=False, default=None)
  _nested_prefix: str | None = field(init=False, default=None)

  _configured: bool = False

  def configure_parser(self) -> None:
    """
    Configure the parser with arguments for this config class.

    Called automatically on first get_config() - usually not called directly.

    Raises:
      ValueError: If both cmd and prefix are set (mutually exclusive).
    """
    global _registered_field_owners
    if self._configured:
      return

    # Validate that cmd and prefix are not both set
    if self.cmd and self.prefix:
      raise ValueError("Cannot set both 'cmd' and 'prefix' on the same config class")

    # Initialize nested_prefix from prefix if set
    if self.prefix:
      self._nested_prefix = self.prefix

    # For subcommands, nested_prefix is None (new root context)
    # For top-level (no cmd, no prefix), nested_prefix is None

    if self.cmd:
      # Build kwargs for add_parser with optional help and aliases
      add_parser_kwargs: dict[str, Any] = {}
      if self.help is not None:
        add_parser_kwargs["help"] = self.help
      if self.aliases is not None:
        add_parser_kwargs["aliases"] = self.aliases
      self.sub_parser = get_sub_parser(self.parser).add_parser(self.cmd, **add_parser_kwargs)
    self._configured = True

    # Get the target parser
    target_parser = self.sub_parser if self.sub_parser else self.parser

    # Initialize tracking for this parser if needed
    if target_parser not in _registered_field_owners:
      _registered_field_owners[target_parser] = set()

    # Configure fields with nested prefix tracking
    self._configure_fields(self.config_class, [], self._nested_prefix, target_parser, set())

  def _configure_fields(
    self,
    clz: type,
    path: list[str],
    parent_prefix: str | None,
    target_parser: Parser,
    visited: set[type],
  ) -> None:
    """
    Recursively configure fields for nested dataclasses.

    Args:
      clz: The dataclass to configure
      path: Current path in the hierarchy (field names)
      parent_prefix: The nested prefix from parent config (if any)
      target_parser: The parser to add arguments to
      visited: Set of config classes already visited in this hierarchy
    """
    for f in fields(clz):
      concrete_type = unpack_type(f.type)  # type: ignore[arg-type]

      if is_dataclass(concrete_type):
        # Check if nested config has cmd - that's not allowed
        if has_factory(concrete_type):
          nested_factory = get_factory(concrete_type)
          if nested_factory.cmd:
            raise ValueError(
              f"Cannot nest subcommand config '{concrete_type.__name__}' "
              f"inside '{clz.__name__}'. Subcommand configs must be at root level."
            )

        # Build nested prefix for this field
        # path contains the path from the current config class to this field
        # parent_prefix is the full prefix from the root to this point
        if parent_prefix:
          nested_prefix = f"{parent_prefix}.{f.name}"
        else:
          nested_prefix = f.name

        # Check for duplicate config class in hierarchy
        if concrete_type in visited:
          raise ValueError(
            f"Duplicate config class {concrete_type.__name__} in hierarchy. "
            f"Config class appears multiple times in the same hierarchy. "
            f"Create distinct subclasses to resolve this."
          )

        # Set nested_prefix on the nested config's factory
        factory = get_factory(concrete_type)
        factory._nested_prefix = nested_prefix

        # Mark as visited for duplicate detection
        visited.add(concrete_type)

        # Recurse into nested dataclass
        self._configure_fields(
          concrete_type, path + [f.name], nested_prefix, target_parser, visited
        )
      else:
        # Leaf field - add argument
        # Check if this field has already been registered
        field_key = (clz, f.name)
        if field_key in _registered_field_owners[target_parser]:
          continue

        # Mark this field as registered
        _registered_field_owners[target_parser].add(field_key)

        # Build the argument name
        name = ".".join(path + [f.name])
        cli_name = name.replace(".", "-").replace("_", "-")

        # Apply nested prefix if set
        if self._nested_prefix:
          cli_name = f"{self._nested_prefix}-{cli_name}"
          name = f"{self._nested_prefix}.{name}"

        # Detect list types
        origin = get_origin(concrete_type)

        if concrete_type is bool:
          # Boolean field: --field sets to True, --no-field sets to False
          arg = functools.partial(
            target_parser.add_argument,
            f"--{cli_name}",
            dest=name,
            default=None,
            action="store_true",
            help=f"set {name} to True",
          )
          _ = arg()

          # Add negation argument
          arg_no = functools.partial(
            target_parser.add_argument,
            f"--no-{cli_name}",
            dest=name,
            default=None,
            action="store_const",
            const=False,
            help=f"set {name} to False",
          )
          _ = arg_no()

        elif origin is list:
          # List field: --field VALUE appends values
          element_type = get_args(concrete_type)[0]
          arg = functools.partial(
            target_parser.add_argument,
            f"--{cli_name}",
            dest=name,
            default=None,
            action="append",
            type=element_type,
            help=f"append to {name} (can be used multiple times)",
          )
          _ = arg()

          # Add clear argument
          arg_no = functools.partial(
            target_parser.add_argument,
            f"--no-{cli_name}",
            dest=name,
            default=None,
            action="store_const",
            const=[],  # Empty list marker
            help=f"clear {name} (set to empty list)",
          )
          _ = arg_no()

        else:
          # Default: scalar field with type conversion
          arg = functools.partial(
            target_parser.add_argument,
            f"--{cli_name}",
            dest=name,
            default=None,
            type=concrete_type,
            help=f"provide {name}",
          )
          _ = arg()

  def get_args(self, args: list[str] | None = None) -> dict[str, Any]:
    """
    Parse CLI arguments and return as dictionary.

    Args:
      args: CLI arguments (defaults to sys.argv[1:])

    Returns:
      Dictionary with dotted keys (e.g., {"database.host": "localhost"}).
      If _nested_prefix is set, keys are stripped of the prefix.
    """
    args_dict = vars(_ensure_configured(self.parser).parse_args(args))
    if self._nested_prefix:
      prefix = self._nested_prefix + "."
      return {
        key[len(prefix) :]: value for key, value in args_dict.items() if key.startswith(prefix)
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

  def list_fields_with_owners(
    self, clz: type | None = None, path: list[str] | None = None
  ) -> list[tuple[Field[Any], list[str], type]]:
    """
    Recursively list all fields in nested dataclasses with owner class info.

    Args:
      clz: The dataclass to inspect (defaults to self.config_class)
      path: Current path in the hierarchy (used for recursion)

    Returns:
      List of (field, path, owner_class) tuples for each leaf field.
      owner_class is the dataclass that directly owns the field.
    """
    clz = self.config_class if clz is None else clz
    path = [] if path is None else path
    result = []
    for f in fields(clz):
      concrete_type = unpack_type(f.type)  # type: ignore[arg-type]
      if is_dataclass(concrete_type):
        result.extend(self.list_fields_with_owners(concrete_type, path=path + [f.name]))
      else:
        result.append((f, path, clz))
    return result


# factories for configurations
_factories: dict[type, Factory] = {}


def _reset_factories() -> None:
  """
  Clear all registered factories and configured parsers.

  For testing only - ensures test isolation by resetting global state.
  Creates a fresh default parser.
  """
  global _factories, _configured_parsers, _default_parser, _sub_parsers, _registered_field_owners
  # Clear dictionaries/lists in-place instead of reassigning
  # This ensures all module references see the changes
  _factories.clear()
  _configured_parsers.clear()
  _sub_parsers.clear()
  _registered_field_owners.clear()
  # Create a new parser by reassigning (this is unavoidable for parser objects)
  _default_parser = argparse.ArgumentParser()


def has_factory(clz: type) -> bool:
  """
  Check if a Factory exists for a configuration class.

  Args:
    clz: The dataclass type to check.

  Returns:
    True if a factory exists for the class, False otherwise.
  """
  return clz in _factories


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
