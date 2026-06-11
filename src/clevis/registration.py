"""Dynamic field registration for plugin architectures.

This module provides runtime field registration for dataclasses, enabling
plugin architectures to inject configuration fields into parent configs.

Key Features:
  - Add fields to dataclasses at runtime
  - Automatic CLI argument generation for registered fields
  - TOML configuration support for plugins
  - Integration with Factory pattern for seamless configuration

Requirements:
  - Parent config must NOT be frozen (frozen=True not allowed)
  - Registration must happen before get_config() is called
  - Registered fields use default_factory for initialization

Relationships:
  - factory.py: Uses get_factory() to check if parser is already configured
  - __init__.py: Exposes register_field() in public API

Example:
    from dataclasses import dataclass
    from clevis import register_field, get_config

    @dataclass  # Must NOT be frozen
    class ToolsConfig:
        list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class PkgqToolConfig:
        enabled: bool = True

    # Plugin registration
    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    # Result:
    # - ToolsConfig.pkgq field added
    # - TOML: [tools.pkgq] → config.tools.pkgq
    # - CLI: --tools-pkgq-enabled

    config = get_config(ToolsConfig, name="tools")
"""

from collections.abc import Callable
from dataclasses import MISSING, Field, fields
from typing import Any

from clevis.factory import get_factory, has_factory


class RegistrationError(Exception):
  """Raised when field registration fails."""


def register_field(
  parent: type[Any],
  name: str,
  field_type: type[Any],
  default_factory: Callable[[], Any] | None = None,
) -> None:
  """Add a field to a parent config class at runtime.

  Modifies the parent class in-place. The parent must be a non-frozen dataclass.
  Namespace for TOML/CLI is automatically derived from parent hierarchy.

  Args:
      parent: Parent config class to extend (e.g., ToolsConfig)
      name: Field name to add (e.g., "pkgq")
      field_type: Config class for this field (e.g., PkgqToolConfig)
      default_factory: Optional factory (defaults to field_type)

  Raises:
      TypeError: If parent is a frozen dataclass
      ValueError: If field name already exists
      RuntimeError: If called after get_config() (parser already configured)

  Example:
      @dataclass  # Must NOT be frozen
      class ToolsConfig:
          list: ListToolConfig = field(default_factory=ListToolConfig)

      @dataclass
      class PkgqToolConfig:
          enabled: bool = True

      register_field(ToolsConfig, "pkgq", PkgqToolConfig)

      # Now ToolsConfig has a pkgq field
      # TOML: [tools.pkgq]
      # CLI: --tools-pkgq-enabled
  """
  # Check if parent is a frozen dataclass
  if hasattr(parent, "__dataclass_params__"):
    params = parent.__dataclass_params__
    if params and params.frozen:
      raise TypeError(
        f"Cannot register field '{name}' on frozen dataclass '{parent.__name__}'. "
        f"Remove 'frozen=True' from the @dataclass decorator to enable dynamic registration."
      )

  # Check for duplicate field name
  if hasattr(parent, "__dataclass_fields__") and name in parent.__dataclass_fields__:
    raise ValueError(
      f"Field '{name}' already exists in '{parent.__name__}'. "
      f"Choose a different field name for the dynamic field."
    )

  # Check if registration is too late (after parser configured)
  # Only check if factory already exists - don't create one just to check
  if has_factory(parent) and get_factory(parent)._configured:
    raise RuntimeError(
      f"Cannot register field '{name}' after get_config() has been called. "
      f"Register fields before loading configuration."
    )

  # Use field_type as default factory if not provided
  if default_factory is None:
    default_factory = field_type

  # Add to parent's __annotations__
  if not hasattr(parent, "__annotations__"):
    parent.__annotations__ = {}
  parent.__annotations__[name] = field_type

  # Create a field object with default_factory set
  # We need to use _FIELD to mark this as a real field
  import dataclasses

  # Private API usage: dataclasses._FIELD
  # This is required to create valid Field objects at runtime. The _FIELD marker
  # is used internally by the dataclasses module to distinguish real fields from
  # class variables and other attributes. Without it, dataclass operations like
  # fields() would not recognize dynamically added fields.
  #
  # Migration path: Python 3.10+ provides dataclasses.fields() which can identify
  # fields by their _field_type attribute, but there's no public API to create
  # valid Field objects. If _FIELD is removed in future Python versions, we would
  # need to track fields manually or find an alternative approach.
  #
  # See: https://github.com/python/cpython/issues/98116 (public field creation API)
  _FIELD = dataclasses._FIELD  # type: ignore[attr-defined]

  new_field = Field(
    default=MISSING,
    default_factory=default_factory,
    init=True,
    repr=True,
    hash=None,
    compare=True,
    metadata={},
    kw_only=False,
  )
  # Set the name, type, and _field_type
  new_field.name = name
  new_field.type = field_type
  new_field._field_type = _FIELD  # type: ignore[attr-defined]

  # Add to parent's __dataclass_fields__
  if not hasattr(parent, "__dataclass_fields__"):
    parent.__dataclass_fields__ = {}
  parent.__dataclass_fields__[name] = new_field

  # Update __init__ to include the new field
  # This is necessary because the original __init__ doesn't know about the new field
  _create_init_with_new_field(parent, name, default_factory)

  # Update __repr__ to include all fields (including dynamically registered ones)
  _update_repr(parent)


def _create_init_with_new_field(
  cls: type, field_name: str, default_factory: Callable[[], Any]
) -> None:
  """Create a new __init__ that includes the dynamically added field.

  This manually creates an __init__ that handles the new field
  with its default_factory.

  Limitations:
    This manual __init__ generation does not support all dataclass features:

    - kw_only: Keyword-only fields (Python 3.10+) are not respected. All
      parameters accept both positional and keyword arguments via **kwargs.
    - init=False: Fields marked with init=False are still included in the
      generated __init__, which differs from standard dataclass behavior.
    - Field order: The original field ordering may not be preserved exactly
      as the dataclass decorator would, since dynamically added fields are
      appended.
    - __post_init__: The generated __init__ does not call __post_init__
      automatically. Classes requiring __post_init__ should use the standard
      dataclass __init__ by not using dynamic field registration.
    - Type annotations: Method signatures and type hints are not preserved.
      IDEs and type checkers will not see the dynamically added fields.

    For most use cases with simple dataclass configurations (non-frozen,
    basic field types, no kw_only), these limitations are acceptable.
    Complex configurations may need alternative approaches.

  Args:
    cls: The dataclass to update.
    field_name: The name of the newly added field.
    default_factory: Factory function for the new field's default value.
  """
  # Get existing fields (excluding the new one we just added)
  existing_fields = [f for f in fields(cls) if f.name != field_name]

  # Create __init__ that sets all fields
  def __init__(self: Any, **kwargs: Any) -> None:
    # Set existing fields from kwargs
    for f in existing_fields:
      if f.name in kwargs:
        setattr(self, f.name, kwargs[f.name])
      else:
        # Use default value
        if f.default is not MISSING:
          setattr(self, f.name, f.default)
        elif f.default_factory is not MISSING:
          setattr(self, f.name, f.default_factory())
        else:
          # Required field - should have been provided in kwargs
          pass

    # Set the new field
    if field_name in kwargs:
      setattr(self, field_name, kwargs[field_name])
    else:
      setattr(self, field_name, default_factory())

  # Replace __init__
  cls.__init__ = __init__  # type: ignore[misc]


def _update_repr(cls: type) -> None:
  """Update __repr__ to include all fields including dynamically registered ones.

  The dataclass-generated __repr__ only includes fields that existed at class
  creation time. This creates a custom __repr__ that iterates over all current
  fields in __dataclass_fields__.
  """

  def __repr__(self: Any) -> str:
    """Custom repr that includes all fields."""
    # Get all fields in the order they appear in __dataclass_fields__
    all_fields = fields(cls)
    # Build the field=value pairs
    field_values = []
    for f in all_fields:
      if f.repr:
        value = getattr(self, f.name)
        field_values.append(f"{f.name}={value!r}")
    return f"{cls.__name__}({', '.join(field_values)})"

  # Replace __repr__
  cls.__repr__ = __repr__  # type: ignore[method-assign, assignment]

