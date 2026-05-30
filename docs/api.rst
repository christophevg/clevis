API Reference
=============

This section documents the public API of Clevis.

Main Functions
--------------

.. autofunction:: clevis.get_config

Exceptions
----------

.. autoclass:: clevis.ConfigError
   :members: __init__, _format_message
   :member-order: bysource

Helper Functions
----------------

These functions are used internally but may be useful for advanced use cases.

.. autofunction:: clevis.list_fields

.. autofunction:: clevis.unpack_type

.. autofunction:: clevis.get_args_config

.. autofunction:: clevis.apply_to_dict

Internal Functions
------------------

.. autofunction:: clevis._get_toml_parser

.. autofunction:: clevis._load_toml

Type Hints
----------

All public functions are fully type-hinted. Here are the key type signatures:

.. code-block:: python

   from typing import Any, Callable
   from dataclasses import Field

   def get_config(
       data_class: type,
       name: str = "project",
       user: bool = True,
       project: bool = True,
       args: list[str] | None = None,
   ) -> Any: ...

   def list_fields(
       clz: type,
       path: list[str] | None = None
   ) -> list[tuple[Field, list[str]]]: ...

   def unpack_type(type_def: type) -> type: ...

   def get_args_config(
       clz: type,
       args: list[str] | None = None
   ) -> dict[str, Any]: ...

   def apply_to_dict(
       args: dict[str, Any],
       dct: dict[str, Any]
   ) -> None: ...