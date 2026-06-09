Examples
========

This guide provides comprehensive examples demonstrating all features of Clevis.
Each example builds on previous concepts to create a progressive learning path.

Overview
--------

The ``examples/`` directory contains 9 example scripts demonstrating Clevis features:

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - Example
     - Features Demonstrated
     - Run Command
   * - :doc:`main`
     - Basic config, CLI args, TOML, security
     - ``python main.py --help``
   * - :doc:`nested`
     - Nested dataclasses, TOML sections
     - ``python nested.py --tool-settings-x 10``
   * - :doc:`validation`
     - Custom validation, ``__post_init__``
     - ``python validation.py --server-url "http://localhost"``
   * - :doc:`environment`
     - ``${VAR}`` interpolation, credentials
     - ``export DB_HOST=localhost && python environment.py``
   * - :doc:`factory`
     - Multi-module orchestration, prefixes
     - ``python factory.py --app1-name "first"``
   * - :doc:`commands`
     - CLI subcommands, aliases
     - ``python commands.py check --verbose``
   * - :doc:`library_mode`
     - Web framework integration, testing
     - ``python library_mode.py``
   * - :doc:`dynamic`
     - Plugin architecture, ``register_field()``
     - ``python dynamic.py --help``
   * - :doc:`plugin`
     - Practical plugin implementation
     - ``python plugin.py --pkgq-timeout 60``

Feature Matrix
--------------

.. list-table::
   :widths: 15 8 8 8 8 8 8 8 8 8
   :header-rows: 1

   * - Feature
     - main
     - nested
     - valid
     - env
     - factory
     - cmd
     - lib
     - dyn
     - plugin
   * - Environment variables
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - CLI arguments
     - ✓
     - ✓
     - ✓
     -
     - ✓
     - ✓
     -
     - ✓
     - ✓
   * - TOML files
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Nested configs
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Security validation
     - ✓
     -
     - ✓
     -
     - ✓
     -
     - ✓
     - ✓
     - ✓
   * - Custom validation
     -
     -
     - ✓
     -
     -
     -
     -
     -
     -
   * - ``${VAR}`` interpolation
     -
     -
     -
     - ✓
     -
     -
     -
     -
     -
   * - Shared parser
     -
     -
     -
     -
     - ✓
     -
     -
     -
     -
   * - Subcommands
     -
     -
     -
     -
     -
     - ✓
     -
     -
     -
   * - Library mode (``cli=False``)
     -
     -
     -
     -
     -
     -
     - ✓
     -
     -
   * - Dynamic registration
     -
     -
     -
     -
     -
     -
     -
     - ✓
     - ✓
   * - Plugin pattern
     -
     -
     -
     -
     -
     -
     -
     -
     - ✓

Learning Path
-------------

We recommend exploring examples in this order:

1. **main.py** - Start here for basics
   Learn: Configuration loading, CLI arguments, TOML files, security validation

2. **nested.py** - Organizing configuration hierarchies
   Learn: Nested dataclasses, TOML sections, ``@configclass`` decorator

3. **validation.py** - Custom validation rules
   Learn: ``__post_init__``, error handling, custom error messages

4. **environment.py** - Environment variable interpolation
   Learn: ``${VAR}`` syntax, type conversion, secure credentials

5. **factory.py** - Shared configuration parsers
   Learn: Multiple configs, prefix namespacing, shared ``ArgumentParser``

6. **commands.py** - CLI subcommands
   Learn: Command aliases, per-command configuration, global config sharing

7. **library_mode.py** - Library-only usage
   Learn: ``cli=False``, web framework integration, testing patterns

8. **dynamic.py** - Dynamic field registration (Advanced)
   Learn: ``register_field()``, plugin architecture, runtime injection

9. **plugin.py** - Plugin pattern (Advanced)
   Learn: Practical plugin implementation, module-level registration

Prerequisites
-------------

Install Clevis with required extras:

.. code-block:: bash

   # Basic installation
   pip install clevis

   # For environment.py (environment variable interpolation)
   pip install clevis[envtoml]

   # For development/testing
   pip install clevis[dev]

   # Or using uv (recommended)
   uv pip install clevis[envtoml]

Running Examples
----------------

Each example can be run directly:

.. code-block:: bash

   # Basic usage
   python main.py

   # Show help for CLI arguments
   python main.py --help

   # Override with CLI arguments
   python main.py --database-host localhost --features-enabled

   # Use environment variables
   ENV=test python main.py

   # Library mode (no CLI)
   python library_mode.py

   # Or using uv (recommended)
   uv run python main.py --help

TOML Configuration Files
-------------------------

Most examples use auto-discovered TOML files. Clevis searches for:

- ``./<name>.toml`` (project directory)
- ``./.<name>.toml`` (project directory, hidden)
- ``~/.<name>.toml`` (user directory)

For example, ``main.py`` looks for:

- ``./app.toml`` or ``./.app.toml``
- ``~/.app.toml``

Example files are provided:

- ``examples/nested.toml`` - For nested.py
- ``examples/validation.toml`` - For validation.py
- ``examples/environment.toml`` - For environment.py

Example 1: Basic Configuration (main.py)
-----------------------------------------

Demonstrates the core functionality:

- Defining configuration dataclasses with type hints
- Automatic configuration discovery (user/project directories)
- Priority: CLI > environment > TOML > defaults
- Security validation for file permissions

.. code-block:: python

   from dataclasses import dataclass, field
   from clevis import get_config, SecurityAction

   @dataclass
   class DatabaseConfig:
       host: str = "localhost"
       port: int = 5432
       user: str | None = None
       password: str | None = None

   @dataclass
   class FeaturesConfig:
       enabled: bool = False
       beta: bool = False

   @dataclass
   class AppConfig:
       name: str = "MyApp"
       debug: bool = False
       database: DatabaseConfig = field(default_factory=DatabaseConfig)
       features: FeaturesConfig = field(default_factory=FeaturesConfig)

   # Load configuration
   config = get_config(AppConfig, name="app")

   print(f"Name: {config.name}")
   print(f"Debug: {config.debug}")
   print(f"Database: {config.database.host}:{config.database.port}")

Running:

.. code-block:: bash

   uv run python main.py
   uv run python main.py --help
   ENV=test uv run python main.py --database-host localhost

Example 2: Nested Configuration (nested.py)
--------------------------------------------

Organizing configuration hierarchies:

- Nested dataclasses for logical grouping
- ``@configclass`` decorator only on top-level
- TOML sections map to nested configs
- CLI arguments with namespacing (``--tool-settings-x``)

.. code-block:: python

   from dataclasses import dataclass, field
   from clevis import configclass, get_config

   @dataclass
   class SettingsConfig:
       x: int = 10
       y: int = 20

   @dataclass
   class ToolConfig:
       name: str = "default"
       settings: SettingsConfig = field(default_factory=SettingsConfig)

   @configclass
   class Config:
       tool: ToolConfig = field(default_factory=ToolConfig)

   config = get_config(Config, name="nested")

Running:

.. code-block:: bash

   uv run python nested.py
   uv run python nested.py --tool-settings-x 10

Example 3: Custom Validation (validation.py)
---------------------------------------------

Custom validation rules:

- ``__post_init__`` for validation logic
- Regex validation for URLs
- Range validation for numeric values
- Custom ``ConfigError`` with helpful messages

.. code-block:: python

   from dataclasses import dataclass
   from urllib.parse import urlparse
   from clevis import get_config, ConfigError

   @dataclass
   class ServerConfig:
       url: str | None = None
       port: int = 8080
       timeout: int = 30

       def __post_init__(self):
           # Validate URL format
           if self.url:
               parsed = urlparse(self.url)
               if parsed.scheme not in ("http", "https"):
                   raise ValueError(f"Invalid URL: scheme must be http or https")

           # Validate port range
           if not (1 <= self.port <= 65535):
               raise ValueError(f"Port must be 1-65535, got {self.port}")

           # Validate timeout
           if self.timeout < 0:
               raise ValueError(f"Timeout must be >= 0, got {self.timeout}")

   config = get_config(ServerConfig, name="validation")

Running:

.. code-block:: bash

   uv run python validation.py --help
   uv run python validation.py --server-url "http://localhost:8080"

Example 4: Environment Interpolation (environment.py)
------------------------------------------------------

Dynamic configuration from environment:

- ``${VAR}`` syntax in TOML files
- Automatic type conversion
- Secure credential handling
- Requires ``clevis[envtoml]``

.. code-block:: toml

   # environment.toml
   [database]
   host = "${DB_HOST}"
   port = "${DB_PORT}"
   user = "${DB_USER}"
   password = "${DB_PASSWORD}"

.. code-block:: bash

   export DB_HOST=localhost
   export DB_PORT=5432
   export DB_USER=myuser
   export DB_PASSWORD=mypassword
   uv run python environment.py

Example 5: Factory Pattern (factory.py)
----------------------------------------

Shared configuration across components:

- ``get_factory()`` for configuration management
- Prefix namespacing (``--app1-name``, ``--app2-name``)
- Shared ``ArgumentParser`` for unified CLI
- Multi-package configuration coordination

.. code-block:: python

   from clevis import configclass, get_config, get_factory
   import argparse

   @configclass
   class App1Config:
       name: str | None = None

   @configclass
   class App2Config:
       name: str | None = None

   # Configure prefixes
   get_factory(App1Config).prefix = "app1"
   get_factory(App2Config).prefix = "app2"

   # Share parser
   parser = argparse.ArgumentParser(description="Multi-Module App")
   get_factory(App1Config).parser = parser
   get_factory(App2Config).parser = parser

Running:

.. code-block:: bash

   uv run python factory.py --help
   uv run python factory.py --app1-name "first" --app2-name "second"

Example 6: Subcommands (commands.py)
--------------------------------------

CLI applications with multiple commands:

- ``cmd`` parameter for subcommand definition
- Command aliases (``c``, ``chk`` for ``check``)
- Per-command configuration classes
- Global configuration sharing

.. code-block:: python

   from clevis import configclass, get_cmd, get_config

   @configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
   class CheckConfig:
       verbose: bool = False
       fix: bool = False

   @configclass(cmd="print", help="Print configuration")
   class PrintConfig:
       output: str = "text"
       rich: bool = False

   if __name__ == "__main__":
       cmd = get_cmd()
       if cmd == "check":
           config = get_config(CheckConfig, project=False, user=False)
           print(f"Checking with verbose={config.verbose}")
       elif cmd == "print":
           config = get_config(PrintConfig, project=False, user=False)
           print(f"Output format: {config.output}")

Running:

.. code-block:: bash

   uv run python commands.py --help
   uv run python commands.py check --verbose
   uv run python commands.py c --fix  # Alias
   uv run python commands.py print --rich

Example 7: Library Mode (library_mode.py)
------------------------------------------

Using Clevis in non-CLI contexts:

- ``cli=False`` to disable ``sys.argv`` parsing
- ``args=[]`` for programmatic control
- Web framework integration patterns
- Testing with injected configuration

.. code-block:: python

   from clevis import get_config

   # Library mode - skip CLI parsing
   config = get_config(Config, name="myapp", cli=False)

   # Programmatic control
   config = get_config(Config, name="myapp", cli=False, args=["--debug"])

   # Testing
   def test_my_config():
       config = get_config(
           TestConfig,
           user=False,
           project=False,
           args=[]
       )
       assert config.name == "default"

Running:

.. code-block:: bash

   uv run python library_mode.py  # No CLI interference

Example 8: Dynamic Registration (dynamic.py)
---------------------------------------------

Plugin architecture configuration:

- ``register_field()`` for runtime injection
- Non-frozen parent configs
- Plugin discovery and registration
- Complete workflow examples

.. code-block:: python

   from dataclasses import dataclass, field
   from clevis import register_field, get_config

   # Parent config (must NOT be frozen)
   @dataclass
   class ToolsConfig:
       list: str = "default"

   # Plugin config
   @dataclass
   class PkgqToolConfig:
       enabled: bool = True
       cache_directory: str = "~/.cache/pkgq"
       timeout: int = 30

   # Register plugin field at runtime
   register_field(ToolsConfig, "pkgq", PkgqToolConfig)

   # Now ToolsConfig has a pkgq field
   config = get_config(ToolsConfig, name="tools")
   print(config.pkgq.enabled)  # True

Running:

.. code-block:: bash

   uv run python dynamic.py
   uv run python dynamic.py --help
   uv run python dynamic.py --tools-pkgq-enabled --tools-pkgq-timeout 60

Example 9: Plugin Pattern (plugin.py)
--------------------------------------

Practical plugin implementation:

- Module-level configuration registration
- Integration with existing configs
- TOML and CLI support
- Real-world plugin structure

.. code-block:: python

   # Built-in tool configuration
   @dataclass
   class ListToolConfig:
       enabled: bool = True
       format: str = "table"

   # Application defines ToolsConfig (non-frozen for plugin registration)
   @dataclass  # NOT frozen
   class ToolsConfig:
       list: ListToolConfig = field(default_factory=ListToolConfig)

   # Plugin module defines its configuration
   @dataclass
   class PkgqToolConfig:
       active: bool = True
       timeout: int = 30

   # Plugin registers itself
   register_field(ToolsConfig, "pkgq", PkgqToolConfig)

   # Application uses extended config
   # TOML: [tools.list] and [tools.pkgq] work seamlessly
   # CLI: --list-enabled and --pkgq-timeout work
   config = get_config(ToolsConfig, name="tools")

Running:

.. code-block:: bash

   uv run python plugin.py --help
   uv run python plugin.py --pkgq-timeout 45

Configuration Priority
----------------------

Clevis uses a clear priority order (highest to lowest):

1. **CLI arguments** - ``--database-host localhost``
2. **Environment variables** - Only when using envtoml/tomlev
3. **Project TOML** - ``./<name>.toml``
4. **User TOML** - ``~/.<name>.toml``
5. **Default values** - Dataclass defaults

Security Features
-----------------

Clevis validates configuration file security:

.. code-block:: python

   from clevis import get_config, SecurityAction

   config = get_config(
     AppConfig,
     security={
       "file_permissions": SecurityAction.LOG,      # Log warnings
       "directory_permissions": SecurityAction.LOG,  # Log warnings
     }
   )

Security actions:

- ``SecurityAction.REJECT`` - Raise error (default)
- ``SecurityAction.LOG`` - Log warning
- ``SecurityAction.DONT_CHECK`` - Skip validation

Next Steps
---------

After working through the examples:

1. Read the :doc:`usage` guide for detailed patterns
2. Review the :doc:`api` reference for complete API documentation
3. Check the `test suite <https://github.com/christophevg/clevis/tree/master/tests>`_
   for comprehensive usage patterns
4. Build your own configuration with the patterns that fit your needs

Support
-------

- **Documentation**: https://clevis.readthedocs.io
- **Repository**: https://github.com/christophevg/clevis
- **Issues**: https://github.com/christophevg/clevis/issues