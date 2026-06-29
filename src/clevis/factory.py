"""Factory module for configuration management.

This module implements the Factory pattern for Clevis configuration classes,
providing singleton factories that manage parser configuration and CLI argument
generation.

Architecture:
  Factory (singleton per config class)
    ├── Manages argparse parser configuration
    ├── Generates CLI arguments from dataclass fields
    ├── Supports nested configuration with prefix propagation
    └── Coordinates across multiple modules via shared parser

Key Components:
  - Factory: Singleton per config class, manages parser setup
  - Parser/SubParser protocols: Interface for argparse-compatible parsers
  - ParserRegistry: Tracks configured parsers and prevents argument conflicts

Relationships:
  - configclass.py: Uses get_factory() to register decorated classes
  - registration.py: Uses get_factory() to add dynamic fields
  - __init__.py: Uses Factory.get_args() and _ensure_configured()

Lazy Configuration:
  Parser configuration is deferred until get_config() is called, allowing
  orchestration code to customize prefixes and parsers before CLI parsing.

  Example:
    factory = get_factory(AppConfig)
    factory.prefix = "app1"      # CLI args: --app1-name, --app1-debug
    factory.parser = custom_parser  # Use custom parser
    config = get_config(AppConfig)  # Parser configured here
"""

import argparse
from argparse import Action, Namespace
from collections.abc import Iterator
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


class ParserRegistry:
  """
  Registry for tracking parser-related state across factories.

  Manages three types of global state:
  - Configured parsers: Track which parsers have had their arguments added
  - Field owners: Prevent duplicate field registrations per parser
  - Argument names: Prevent argument name conflicts per parser

  This class provides a cleaner API for managing parser state that was
  previously managed via module-level global dictionaries.
  """

  def __init__(self) -> None:
    """Initialize an empty registry."""
    self._configured_parsers: list[Parser] = []
    # Track which field owner classes have had their CLI args registered for each parser
    # Key: parser, Value: set of (owner_class, field_name) tuples
    self._registered_field_owners: dict[Parser, set[tuple[type, str]]] = {}
    # Track all registered argument names (canonical + aliases) for conflict detection
    # Key: parser, Value: set of argument names (e.g., {"--packages", "--with"})
    self._registered_arg_names: dict[Parser, set[str]] = {}

  def is_configured(self, parser: Parser) -> bool:
    """Check if a parser has been configured."""
    return parser in self._configured_parsers

  def mark_configured(self, parser: Parser) -> None:
    """Mark a parser as configured."""
    self._configured_parsers.append(parser)

  def is_field_registered(self, parser: Parser, owner: type, field_name: str) -> bool:
    """Check if a field has been registered for a parser."""
    if parser not in self._registered_field_owners:
      return False
    return (owner, field_name) in self._registered_field_owners[parser]

  def register_field(self, parser: Parser, owner: type, field_name: str) -> None:
    """Register a field for a parser."""
    if parser not in self._registered_field_owners:
      self._registered_field_owners[parser] = set()
    self._registered_field_owners[parser].add((owner, field_name))

  def is_arg_name_registered(self, parser: Parser, arg_name: str) -> bool:
    """Check if an argument name is registered for a parser."""
    if parser not in self._registered_arg_names:
      return False
    return arg_name in self._registered_arg_names[parser]

  def register_arg_name(self, parser: Parser, arg_name: str) -> None:
    """Register an argument name for a parser."""
    if parser not in self._registered_arg_names:
      self._registered_arg_names[parser] = set()
    self._registered_arg_names[parser].add(arg_name)

  def clear(self) -> None:
    """Clear all registry state (for testing)."""
    self._configured_parsers.clear()
    self._registered_field_owners.clear()
    self._registered_arg_names.clear()


# Module-level state
_sub_parsers: dict[Parser, Any] = {}

# Global reference to default parser (created lazily by _get_default_parser)
_default_parser: argparse.ArgumentParser | None = None

# Module-level parser registry
_registry = ParserRegistry()

# Factory instances for each configuration class
# Use forward reference since Factory is defined later
_factories: dict[type, "Factory"] = {}


def _get_default_parser() -> Parser:
  """
  Get or create the default parser.

  Creates the parser lazily on first access instead of at module import time.
  All Factories that don't specify a parser share this default instance.

  Returns:
    The shared default ArgumentParser instance.
  """
  global _default_parser
  if _default_parser is None:
    _default_parser = argparse.ArgumentParser()
  return _default_parser  # type: ignore[return-value]


def get_sub_parser(parser: Parser) -> SubParser:
  global _sub_parsers
  try:
    return _sub_parsers[parser]  # type: ignore[no-any-return]
  except KeyError:
    _sub_parsers[parser] = parser.add_subparsers(dest="cmd")
    _sub_parsers[parser].required = True
    return _sub_parsers[parser]  # type: ignore[no-any-return]


def _unpack_union_type(type_def: type) -> type:
  """
  Unpack a Union type (Optional[T] or T | None) to get the non-None type.

  Args:
    type_def: A Union type like Optional[T] or T | None

  Returns:
    The non-None type from the union

  Raises:
    ValueError: If union has more than 2 types (complex unions not supported)
  """
  from types import UnionType

  origin = get_origin(type_def)
  # Not a union type - return as-is (shouldn't happen, but safety check)
  if origin is not Union and origin is not UnionType:
    return type_def

  types = get_args(type_def)
  # Empty union - return as-is
  if len(types) == 0:
    return type_def
  # Complex unions (more than 2 types) are not supported
  if len(types) > 2:
    raise ValueError("Complex unions not supported")
  # T | None or None | T - return the non-None type
  return types[0] if types[1] is type(None) else types[1]  # type: ignore[no-any-return]


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
  """
  from types import UnionType

  origin = get_origin(type_def)

  # Container types (list, dict, set, tuple) - return as-is
  # dacite handles these directly
  if origin in (list, dict, set, tuple):
    return type_def

  # Literal types - return as-is
  # dacite validates the value is one of the literal values
  if origin is Literal:
    return type_def

  # Union types (Optional[T] / T | None) - unpack to get the non-None type
  # This handles both typing.Union and types.UnionType (Python 3.10+)
  origin = get_origin(type_def)
  if origin is Union or origin is UnionType:
    return _unpack_union_type(type_def)

  # Non-union, non-container type - return as-is
  return type_def


def _is_cli_excluded(f: Field[Any]) -> bool:
  """
  Return True iff this field must be hidden from the CLI subsystem.

  Triggers ONLY on an explicit False (strict identity check):
    metadata["cli"] is False  -> True  (exclude)
    metadata["cli"] absent     -> False (include)
    metadata["cli"] is None    -> False (include; None is not False)
    metadata["cli"] == 0       -> False (include; 0 is not False)
    metadata["cli"] == ""      -> False (include; "" is not False)
    metadata["cli"] is True    -> False (include)

  This is the ONLY predicate that decides CLI visibility. It is used by:
    - the ``_iter_cli_fields`` walker (driving parser configuration and
      field listing), and
    - ``_is_field_path_excluded`` in ``__init__.py`` for the
      ``suggest_cli=False`` point-query along a specific dotted path
      (ConfigError suggestion suppression).
  """
  return f.metadata.get("cli", True) is False


def _iter_cli_fields(
  clz: type,
  path: list[str] | None = None,
  owner: type | None = None,
) -> Iterator[tuple[Any, ...]]:
  """
  Single source of truth for fields visible to the CLI subsystem.

  Yields tagged tuples so consumers can dispatch on entry kind:
    ("leaf", field, path, owner_class)
        a leaf field (non-dataclass) visible to CLI.
    ("nested", field, path, owner_class, concrete_type)
        a nested-dataclass field visible to CLI; its children follow
        immediately in the stream.

  Exclusion rules (enforced in exactly one ``continue`` statement):
    - Leaf field with metadata["cli"] is False  -> skipped (not yielded).
    - Nested-dataclass field with metadata["cli"] is False -> the entire
      subtree is skipped (no recursion into the nested class). Descendants
      with cli=True remain excluded because they are never visited.
    - Any other value (including absence of the key, None, 0, "") -> included.

  All field-list consumers (``_configure_fields``, ``list_fields``,
  ``list_fields_with_owners``) MUST obtain their fields through this walker.
  The exclusion check appears nowhere else.
  """
  if path is None:
    path = []
  current_owner = owner if owner is not None else clz
  for f in fields(clz):
    if _is_cli_excluded(f):
      continue  # single exclusion point: skip leaf OR skip entire subtree
    concrete_type = unpack_type(f.type)  # type: ignore[arg-type]
    if is_dataclass(concrete_type):
      yield ("nested", f, path, current_owner, concrete_type)
      yield from _iter_cli_fields(concrete_type, path + [f.name], concrete_type)
    else:
      yield ("leaf", f, path, current_owner)


def _register_arg_name(parser: Parser, arg_name: str, field_name: str) -> None:
  """
  Register an argument name and check for conflicts.

  Args:
    parser: The parser to register the argument name for
    arg_name: The argument name to register (e.g., "--packages", "--with")
    field_name: The field name for error messages

  Raises:
    ValueError: If the argument name is already registered for this parser
  """
  if _registry.is_arg_name_registered(parser, arg_name):
    raise ValueError(
      f"Alias '{arg_name}' conflicts with existing argument for field '{field_name}'"
    )
  _registry.register_arg_name(parser, arg_name)


def _ensure_configured(parser: Parser) -> Parser:
  """
  Ensure a parser is fully configured by all factories that use it.

  Lazy configuration - called on first get_config() for a given parser.
  """
  if not _registry.is_configured(parser):
    # lazy configure using each factory having this parser
    # Convert to list to avoid RuntimeError if factories dict changes during iteration
    for factory in list(_factories.values()):
      if factory.parser is parser:
        factory.configure_parser()
    _registry.mark_configured(parser)
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
  parser: Parser = field(default_factory=_get_default_parser)
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

    # Configure fields with nested prefix tracking
    self._configure_fields(self.config_class, [], target_parser, set())

  def _configure_fields(
    self,
    clz: type,
    path: list[str],
    target_parser: Parser,
    visited: set[type],
  ) -> None:
    """
    Configure fields for nested dataclasses using the single CLI walker.

    Recursion is driven by ``_iter_cli_fields``; this method dispatches on the
    walker's tagged entries ("nested" / "leaf"). The exclusion check lives
    solely inside the walker — consumers never call ``_is_cli_excluded``.

    Args:
      clz: The dataclass to configure
      path: Initial path in the hierarchy (field names from the root caller)
      target_parser: The parser to add arguments to
      visited: Set of config classes already visited in this hierarchy
    """
    # Precompute the root prefix parts so we can compute each nested entry's
    # nested_prefix directly from the walker-provided path (no parent_prefix
    # stack needed). The root prefix is self._nested_prefix set in
    # configure_parser (which equals self.prefix or None).
    root_parts: list[str] = self._nested_prefix.split(".") if self._nested_prefix else []

    for kind, f, fpath, owner, *extra in _iter_cli_fields(clz, path):
      if kind == "nested":
        concrete_type = extra[0]

        # Check if nested config has cmd - that's not allowed
        if has_factory(concrete_type):
          nested_factory = get_factory(concrete_type)
          if nested_factory.cmd:
            raise ValueError(
              f"Cannot nest subcommand config '{concrete_type.__name__}' "
              f"inside '{owner.__name__}'. Subcommand configs must be at root level."
            )

        # Build nested prefix for this field directly from the walker path.
        # fpath is the accumulated field-name path from the root config class
        # to the parent of this nested field. Appending f.name gives the full
        # dotted path; prepending root_parts incorporates the top-level prefix.
        nested_prefix = ".".join(root_parts + fpath + [f.name])

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

      else:  # leaf
        # Leaf field - add argument
        # Check if this field has already been registered
        if _registry.is_field_registered(target_parser, owner, f.name):
          continue

        # Mark this field as registered
        _registry.register_field(target_parser, owner, f.name)

        # Build the argument name
        name = ".".join(fpath + [f.name])
        cli_name = name.replace(".", "-").replace("_", "-")

        # Apply nested prefix if set
        if self._nested_prefix:
          cli_name = f"{self._nested_prefix}-{cli_name}"
          name = f"{self._nested_prefix}.{name}"

        # Compute the concrete (non-dataclass) type for this leaf
        concrete_type = unpack_type(f.type)

        # Detect list types
        origin = get_origin(concrete_type)

        # Extract aliases from field metadata
        cli_aliases = f.metadata.get("cli_aliases", [])
        if not isinstance(cli_aliases, list):
          cli_aliases = []

        # Register canonical argument names
        if concrete_type is bool:
          _register_arg_name(target_parser, f"--{cli_name}", name)
          _register_arg_name(target_parser, f"--no-{cli_name}", name)
        elif origin is list:
          _register_arg_name(target_parser, f"--{cli_name}", name)
          _register_arg_name(target_parser, f"--no-{cli_name}", name)
        else:
          _register_arg_name(target_parser, f"--{cli_name}", name)

        # Register alias argument names
        for alias in cli_aliases:
          if not isinstance(alias, str):
            continue
          # Alias replaces the entire cli_name (without prefixes)
          if concrete_type is bool:
            _register_arg_name(target_parser, f"--{alias}", name)
            _register_arg_name(target_parser, f"--no-{alias}", name)
          elif origin is list:
            _register_arg_name(target_parser, f"--{alias}", name)
            _register_arg_name(target_parser, f"--no-{alias}", name)
          else:
            _register_arg_name(target_parser, f"--{alias}", name)

        # Add canonical arguments
        if concrete_type is bool:
          # Boolean field: --field sets to True, --no-field sets to False
          target_parser.add_argument(
            f"--{cli_name}",
            dest=name,
            default=None,
            action="store_true",
            help=f"set {name} to True",
          )

          # Add negation argument
          target_parser.add_argument(
            f"--no-{cli_name}",
            dest=name,
            default=None,
            action="store_const",
            const=False,
            help=f"set {name} to False",
          )

        elif origin is list:
          # List field: --field VALUE appends values
          element_type = get_args(concrete_type)[0]
          target_parser.add_argument(
            f"--{cli_name}",
            dest=name,
            default=None,
            action="append",
            type=element_type,
            help=f"append {element_type.__name__} to {name} list (can be used multiple times)",
          )

          # Add clear argument
          target_parser.add_argument(
            f"--no-{cli_name}",
            dest=name,
            default=None,
            action="store_const",
            const=[],  # Empty list marker
            help=f"clear {name} (set to empty list)",
          )

        else:
          # Default: scalar field with type conversion
          target_parser.add_argument(
            f"--{cli_name}",
            dest=name,
            default=None,
            type=concrete_type,
            help=f"provide {name}",
          )

        # Add alias arguments (same dest as canonical)
        for alias in cli_aliases:
          if not isinstance(alias, str):
            continue

          if concrete_type is bool:
            # Boolean alias: --alias sets to True, --no-alias sets to False
            target_parser.add_argument(
              f"--{alias}",
              dest=name,
              default=None,
              action="store_true",
              help=f"set {name} to True (alias for --{cli_name})",
            )

            # Add negation argument for alias
            target_parser.add_argument(
              f"--no-{alias}",
              dest=name,
              default=None,
              action="store_const",
              const=False,
              help=f"set {name} to False (alias for --no-{cli_name})",
            )

          elif origin is list:
            # List alias: --alias VALUE appends values
            element_type = get_args(concrete_type)[0]
            target_parser.add_argument(
              f"--{alias}",
              dest=name,
              default=None,
              action="append",
              type=element_type,
              help=(
                f"append {element_type.__name__} to {name} list "
                f"(can be used multiple times, alias for --{cli_name})"
              ),
            )

            # Add clear argument for alias
            target_parser.add_argument(
              f"--no-{alias}",
              dest=name,
              default=None,
              action="store_const",
              const=[],  # Empty list marker
              help=f"clear {name} (alias for --no-{cli_name})",
            )

          else:
            # Scalar alias: --alias VALUE
            target_parser.add_argument(
              f"--{alias}",
              dest=name,
              default=None,
              type=concrete_type,
              help=f"provide {name} (alias for --{cli_name})",
            )

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
    List all CLI-visible leaf fields in nested dataclasses.

    Delegates to the single ``_iter_cli_fields`` walker, filtering for "leaf"
    entries. Fields and subtrees marked ``metadata["cli"] is False`` are
    excluded by the walker and never appear here.

    Args:
      clz: The dataclass to inspect (defaults to self.config_class)
      path: Current path in the hierarchy (used for recursion)

    Returns:
      List of (field, path) tuples for each visible leaf field.
    """
    clz = self.config_class if clz is None else clz
    path = [] if path is None else path
    return [(f, p) for kind, f, p, _owner, *_extra in _iter_cli_fields(clz, path) if kind == "leaf"]

  def list_fields_with_owners(
    self, clz: type | None = None, path: list[str] | None = None
  ) -> list[tuple[Field[Any], list[str], type]]:
    """
    List all CLI-visible leaf fields in nested dataclasses with owner class.

    Delegates to the single ``_iter_cli_fields`` walker, filtering for "leaf"
    entries. Fields and subtrees marked ``metadata["cli"] is False`` are
    excluded by the walker and never appear here.

    Args:
      clz: The dataclass to inspect (defaults to self.config_class)
      path: Current path in the hierarchy (used for recursion)

    Returns:
      List of (field, path, owner_class) tuples for each visible leaf field.
      owner_class is the dataclass that directly owns the field.
    """
    clz = self.config_class if clz is None else clz
    path = [] if path is None else path
    return [
      (f, p, owner) for kind, f, p, owner, *_extra in _iter_cli_fields(clz, path) if kind == "leaf"
    ]


def _reset_factories() -> None:
  """
  Clear all registered factories and configured parsers.

  For testing only - ensures test isolation by resetting global state.
  Creates a fresh default parser.
  """
  global _factories, _default_parser, _sub_parsers, _registry
  # Clear dictionaries/lists in-place instead of reassigning
  # This ensures all module references see the changes
  _factories.clear()
  _sub_parsers.clear()
  _registry.clear()
  # Reset default parser by setting to None (will be recreated lazily)
  _default_parser = None


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
  Get or create the Factory for a configuration class.

  This function implements the singleton pattern for Factory instances:
  - If a Factory already exists for the class, returns the existing instance
  - If no Factory exists, creates a new one, registers it, and returns it

  The singleton behavior ensures that:
  - All parts of the code get the same Factory instance for a config class
  - Configuration state (prefix, parser, cmd, etc.) is shared consistently
  - Test isolation can be achieved via _reset_factories()

  Args:
    clz: The dataclass type to get a factory for.

  Returns:
    Factory instance for the given class (existing or newly created).

  Example:
      @configclass
      class AppConfig:
          name: str = "default"

      # Get the factory (creates if needed)
      factory = get_factory(AppConfig)
      factory.prefix = "app1"

      # Later, same instance is returned
      factory2 = get_factory(AppConfig)
      assert factory2.prefix == "app1"  # Same instance
  """
  global _factories
  try:
    return _factories[clz]
  except KeyError:
    # create default factory
    _factories[clz] = Factory(clz)
    return _factories[clz]
