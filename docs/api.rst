API Reference
=============

This section documents the public API of Clevis.

Main Functions
--------------

.. autofunction:: clevis.get_config

.. autofunction:: clevis.get_cmd

Factory Pattern
---------------

The Factory pattern enables multi-module orchestration with shared parsers
and argument prefixes.

.. autofunction:: clevis.configclass

.. autofunction:: clevis.get_factory

.. autoclass:: clevis.Factory
   :members:
   :member-order: bysource

.. autoclass:: clevis.Parser
   :members:
   :member-order: bysource

.. autoclass:: clevis.SubParser
   :members:
   :member-order: bysource

Exceptions
----------

.. autoclass:: clevis.ConfigError
   :members: __init__, _format_message
   :member-order: bysource

Helper Functions
----------------

These functions are used internally but may be useful for advanced use cases.

.. autofunction:: clevis.unpack_type

.. autofunction:: clevis.apply_to_dict

.. autofunction:: clevis.get_sub_parser

Config Override Cascade (P1-006)
--------------------------------

The config override cascade enables pluggable config sources (providers)
that are deep-merged between dataclass defaults and CLI arguments.

.. autoclass:: clevis.ConfigProvider
   :members:
   :member-order: bysource

.. autoclass:: clevis.FileConfigProvider
   :members:
   :member-order: bysource

.. autoclass:: clevis.UserConfigProvider
   :members:
   :member-order: bysource

.. autoclass:: clevis.ProjectConfigProvider
   :members:
   :member-order: bysource

.. autodata:: clevis.DEFAULT_CASCADE

.. autofunction:: clevis.build_default_cascade

.. autofunction:: clevis.deep_merge

Security Helpers (P1-006)
-------------------------

Exported security functions for custom ``ConfigProvider`` authors. These
implement the TOCTOU-safe file access pattern used by the built-in providers.

.. autofunction:: clevis.check_file_permissions

.. autofunction:: clevis.check_directory_permissions

.. autofunction:: clevis.load_toml_from_fd

.. autofunction:: clevis.load_toml_file

Public TOML API (P1-006)
------------------------

Raw TOML parsers (no security checks) with stdlib-compatible signatures.

.. autofunction:: clevis.load

.. autofunction:: clevis.loads

.. autodata:: clevis.load_toml

.. autodata:: clevis.loads_toml

Testing Helpers
---------------

.. autofunction:: clevis._reset_factories

Internal Functions
------------------

.. autofunction:: clevis._get_toml_parser

.. autofunction:: clevis._load_toml

Type Hints
----------

All public functions are fully type-hinted. Here are the key type signatures:

.. code-block:: python

   from typing import Any, Callable, Protocol, Type, TypeVar
   from dataclasses import Field
   from argparse import Action, Namespace

   # Main functions
   def get_config(
       clz: type,
       name: str = "project",
       user: bool = True,
       project: bool = True,
       cli: bool = True,
       args: list[str] | None = None,
   ) -> Any: ...

   def get_cmd(parser=None) -> str | None: ...

   # Factory pattern
   def configclass(cls=None, cmd=None) -> type: ...

   def get_factory(clz: type) -> Factory: ...

   T = TypeVar('T')

   @dataclass
   class Factory:
       config_class: type
       prefix: str | None = None
       parser: Parser = field(default_factory=lambda: _default_parser)
       cmd: str | None = None
       sub_parser: Parser | None = field(init=False, default=None)
       _configured: bool = False

       def configure_parser(self) -> None: ...
       def get_args(self, args: list[str] | None = None) -> dict[str, Any]: ...
       def list_fields(
           self,
           clz: type | None = None,
           path: list[str] | None = None
       ) -> list[tuple[Field[Any], list[str]]]: ...

   class Parser(Protocol):
       def add_argument(
           self,
           *name_or_flags: str,
           action: str | type[Action] = ...,
           default: Any = ...,
           type: Any = ...,
           help: str | None = ...,
           dest: str | None = ...,
           **kwargs: Any
       ) -> Action: ...

       def add_subparsers(self, **kwargs) -> SubParser: ...

       def parse_args(self, args: list[str] | None = None) -> Namespace: ...

   class SubParser(Protocol):
       def add_parser(self, name: str, **kwargs) -> Parser: ...

   # Utilities
   def unpack_type(type_def: type) -> type: ...

   def apply_to_dict(
       args: dict[str, Any],
       dct: dict[str, Any]
   ) -> None: ...