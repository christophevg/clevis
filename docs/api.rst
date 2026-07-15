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

.. warning::

   **v0.7.0 breaking change:** The merge of user-level and project-level TOML files
   changed from shallow (``dict.update``) to deep (recursive dict merge). Nested
   tables now merge key-by-key instead of being replaced wholesale.

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

   from typing import Any, BinaryIO, Callable, Protocol, TypeVar, runtime_checkable
   from dataclasses import Field, dataclass
   from argparse import Action, Namespace
   from enum import Enum
   from pathlib import Path

   T = TypeVar("T")

   # Main functions
   def get_config(
       clz: type[T],
       name: str = "project",
       user: bool = True,
       project: bool = True,
       cli: bool = True,
       args: list[str] | None = None,
       security: SecurityConfig | None = None,
       cascade: list[ConfigProvider] | None = None,
   ) -> T: ...

   def get_cmd(parser=None, args: list[str] | None = None) -> str | None: ...

   # Factory pattern
   def configclass(
       cls: type[T] | None = None,
       cmd: str | None = None,
       help: str | None = None,
       aliases: list[str] | None = None,
       config: str | None = None,
       default_cmd: bool = False,
   ) -> type[T] | Callable[[type[T]], type[T]]: ...

   def get_factory(clz: type) -> Factory: ...

   @dataclass
   class Factory:
       config_class: type
       prefix: str | None = None
       parser: Parser = ...
       cmd: str | None = None
       help: str | None = None
       aliases: list[str] | None = None
       config: str | None = None
       default_cmd: bool = False
       sub_parser: Parser | None = ...
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

       def add_subparsers(self, **kwargs: Any) -> SubParser: ...
       def parse_args(self, args: list[str] | None = None) -> Namespace: ...
       def parse_known_args(self, args: list[str] | None = None) -> tuple[Namespace, list[str]]: ...

   class SubParser(Protocol):
       required: bool
       def add_parser(self, name: str, help: str | None = ..., aliases: list[str] | None = ..., **kwargs: Any) -> Parser: ...

   # Config Override Cascade
   @runtime_checkable
   class ConfigProvider(Protocol):
       def __call__(self) -> dict[str, Any]: ...

   class FileConfigProvider:
       _path_template: str
       def __init__(self, name: str, security: SecurityConfig | None = None) -> None: ...
       def _root_dir(self) -> Path: ...
       def __call__(self) -> dict[str, Any]: ...

   class UserConfigProvider(FileConfigProvider): ...
   class ProjectConfigProvider(FileConfigProvider): ...

   DEFAULT_CASCADE: tuple[type[ConfigProvider], ...]

   def build_default_cascade(
       name: str,
       security: SecurityConfig | None = None,
       user: bool = True,
       project: bool = True,
   ) -> list[ConfigProvider]: ...

   def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]: ...

   # Public TOML API
   def load(fp: BinaryIO) -> dict[str, Any]: ...
   def loads(s: str) -> dict[str, Any]: ...
   load_toml: Callable[[BinaryIO], dict[str, Any]]
   loads_toml: Callable[[str], dict[str, Any]]

   # Security helpers
   def check_file_permissions(path: Path, action: SecurityAction) -> tuple[bool, int | None]: ...
   def check_directory_permissions(path: Path, action: SecurityAction) -> bool: ...
   def load_toml_from_fd(fd: int) -> dict[str, Any]: ...
   def load_toml_file(path: Path, security: SecurityConfig | None = None) -> dict[str, Any]: ...

   # Utilities
   def unpack_type(type_def: type) -> type: ...
   def apply_to_dict(args: dict[str, Any], dct: dict[str, Any]) -> None: ...