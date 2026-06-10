Usage
=====

This guide covers how to use Clevis for configuration management in your Python
applications.

Overview
--------

Clevis provides a layered configuration system:

1. **Dataclass defaults** - Define your configuration schema with defaults
2. **User-level TOML** - User-specific settings (``~/.{name}.toml``)
3. **Project-level TOML** - Project-specific settings (``./{name}.toml``)
4. **CLI arguments** - Runtime overrides (``--{arg}``)

Each layer overrides the previous one, with CLI arguments having the highest priority.

Defining Configuration Schemas
------------------------------

Basic Schemas
~~~~~~~~~~~~~

Define your configuration using Python dataclasses:

.. code-block:: python

   from dataclasses import dataclass

   @dataclass
   class Config:
       name: str = "MyApp"
       debug: bool = False
       port: int = 8080

All fields should have default values to ensure your application can start even
without configuration files.

Nested Schemas
~~~~~~~~~~~~~~

Organize related settings using nested dataclasses:

.. code-block:: python

   from dataclasses import dataclass, field

   @dataclass
   class DatabaseConfig:
       host: str = "localhost"
       port: int = 5432
       user: str | None = None
       password: str | None = None

   @dataclass
   class LoggingConfig:
       level: str = "INFO"
       format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

   @dataclass
   class AppConfig:
       name: str = "MyApp"
       debug: bool = False
       database: DatabaseConfig = field(default_factory=DatabaseConfig)
       logging: LoggingConfig = field(default_factory=LoggingConfig)

.. important::

   Use ``field(default_factory=ClassName)`` for nested dataclasses to avoid
   the mutable default argument problem.

Optional Fields
~~~~~~~~~~~~~~~

Mark fields as optional using ``| None``:

.. code-block:: python

   from dataclasses import dataclass

   @dataclass
   class Config:
       api_key: str | None = None
       timeout: int | None = None

.. note::

   Optional fields can be ``None`` if not provided in configuration.

Loading Configuration
---------------------

Basic Usage
~~~~~~~~~~~

Load configuration with a single function call:

.. code-block:: python

   from clevis import get_config
   from dataclasses import dataclass

   @dataclass
   class Config:
       name: str = "MyApp"
       debug: bool = False

   # Load from ~/.myapp.toml and ./myapp.toml
   config = get_config(Config, name="myapp")

   print(config.name)   # Access as attribute
   print(config.debug)  # Access as attribute

The ``name`` parameter determines the TOML file names:

- **User config**: ``~/.myapp.toml``
- **Project config**: ``./myapp.toml``

Loading from Specific Paths
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Control which configuration files to load:

.. code-block:: python

   # Only project-level config (ignore user config)
   config = get_config(Config, name="myapp", user=False)

   # Only user-level config (ignore project config)
   config = get_config(Config, name="myapp", project=False)

   # Neither (dataclass defaults only)
   config = get_config(Config, name="myapp", user=False, project=False)

Loading Without CLI Arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To ignore command-line arguments (e.g., in tests or when running as a library):

.. code-block:: python

   # Pass empty list to skip CLI argument parsing
   config = get_config(Config, name="myapp", args=[])

   # Or pass specific arguments programmatically
   config = get_config(Config, name="myapp", args=["--debug", "--name", "TestApp"])

TOML Configuration Files
------------------------

File Locations
~~~~~~~~~~~~~~

Clevis looks for configuration files in two locations:

- **User-level**: ``~/.{name}.toml`` (in your home directory)
- **Project-level**: ``./{name}.toml`` (in the current working directory)

User-level configuration provides personal defaults, while project-level
configuration is typically checked into version control.

File Format
~~~~~~~~~~~

Create a TOML file matching your dataclass structure:

.. code-block:: toml

   name = "Production App"
   debug = false

   [database]
   host = "db.example.com"
   port = 5432
   user = "appuser"
   password = "${DB_PASSWORD}"

   [logging]
   level = "WARNING"
   format = "%(asctime)s - %(levelname)s - %(message)s"

The TOML structure maps directly to your dataclass hierarchy.

Environment Variable Interpolation
----------------------------------

Using envtoml
~~~~~~~~~~~~~

Install with environment variable support:

.. code-block:: bash

   pip install clevis[envtoml]

Then use ``${VAR}`` syntax in your TOML files:

.. code-block:: toml

   [database]
   password = "${DB_PASSWORD}"
   host = "${DB_HOST}"

Environment variables are expanded when the TOML file is loaded.

.. warning::

   If ``DB_PASSWORD`` is not set, this will raise an error when loading.

Using tomlev (with Defaults)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For fallback values, use the ``tomlev`` extra:

.. code-block:: bash

   pip install clevis[tomlev]

Then use ``${VAR|default}`` syntax:

.. code-block:: toml

   [database]
   password = "${DB_PASSWORD|default_password}"
   host = "${DB_HOST|localhost}"
   port = "${DB_PORT|5432}"

If the environment variable is not set, the default value is used.

.. note::

   All values in TOML are strings. Convert to appropriate types in your dataclass.

CLI Argument Generation
-----------------------

Automatic Argument Parsing
~~~~~~~~~~~~~~~~~~~~~~~~~~

Clevis automatically generates CLI arguments from your dataclass:

.. code-block:: python

   from clevis import get_config
   from dataclasses import dataclass, field

   @dataclass
   class DatabaseConfig:
       host: str = "localhost"
       port: int = 5432

   @dataclass
   class Config:
       name: str = "MyApp"
       debug: bool = False
       database: DatabaseConfig = field(default_factory=DatabaseConfig)

   # CLI args are automatically parsed
   config = get_config(Config, name="myapp")

Run your application:

.. code-block:: bash

   python app.py --name "Custom App" --debug
   python app.py --database-host prod.db.example.com --database-port 5433

Argument Naming Convention
~~~~~~~~~~~~~~~~~~~~~~~~~~

CLI arguments follow these conventions:

- **Dots become dashes**: ``database.host`` → ``--database-host``
- **Underscores become dashes**: ``db_name`` → ``--db-name``
- **Boolean flags**: ``--debug`` (no value needed)

Boolean Arguments
~~~~~~~~~~~~~~~~~

Boolean fields use flag-style arguments:

.. code-block:: bash

   # Enable debug mode
   python app.py --debug

   # Disable debug mode (explicit False)
   python app.py --no-debug

   # Last flag wins
   python app.py --debug --no-debug  # Result: debug=False

Boolean fields support both ``--flag`` (sets to ``True``) and ``--no-flag`` (sets to ``False``).
This allows explicit control over boolean values from the command line.

List Arguments
~~~~~~~~~~~~~~

List fields support append behavior - values accumulate when the argument is repeated:

.. code-block:: python

   from dataclasses import dataclass, field

   @dataclass
   class Config:
       packages: list[str] = field(default_factory=list)
       ports: list[int] = field(default_factory=list)

**Appending values:**

.. code-block:: bash

   # Append multiple values
   python app.py --packages pkgq --packages c3 --packages agent
   # Result: packages = ["pkgq", "c3", "agent"]

   # Works with all list types
   python app.py --ports 8080 --ports 8081 --ports 8082
   # Result: ports = [8080, 8081, 8082]

**Clearing lists:**

.. code-block:: bash

   # Set list to empty
   python app.py --no-packages
   # Result: packages = []

   # Clear then add (last wins)
   python app.py --packages old --no-packages --packages new
   # Result: packages = ["new"]

**Merging with TOML:**

List values from CLI are **appended** to TOML values, not replaced:

.. code-block:: toml

   # myapp.toml
   packages = ["base", "core"]

.. code-block:: bash

   # CLI appends to TOML values
   python app.py --packages plugin1 --packages plugin2
   # Result: packages = ["base", "core", "plugin1", "plugin2"]

   # Clear TOML values with --no-field
   python app.py --no-packages --packages urgent
   # Result: packages = ["urgent"]

**Type conversion:**

List elements are type-converted just like scalar fields:

.. code-block:: python

   from pathlib import Path

   @dataclass
   class Config:
       paths: list[Path] = field(default_factory=list)
       ports: list[int] = field(default_factory=list)

.. code-block:: bash

   # Path conversion
   python app.py --paths /var/log --paths /var/run
   # Result: paths = [Path("/var/log"), Path("/var/run")]

   # Int conversion with validation
   python app.py --ports 80 --ports 443
   # Result: ports = [80, 443]

   # Invalid value raises error
   python app.py --ports abc
   # Error: argument --ports: invalid int value: 'abc'

**Conflict resolution:**

When both ``--field`` and ``--no-field`` are provided, the **last one wins**:

.. code-block:: bash

   # Add, clear, add
   python app.py --packages a --no-packages --packages b
   # Result: packages = ["b"]

   # Clear, add
   python app.py --no-packages --packages urgent
   # Result: packages = ["urgent"]

   # Add, add, clear
   python app.py --packages a --packages b --no-packages
   # Result: packages = []

Overriding Defaults
~~~~~~~~~~~~~~~~~~~

CLI arguments have the highest priority and override all other configuration:

.. code-block:: bash

   # Override TOML settings
   python app.py --database-host localhost --debug

   # All three layers: TOML defaults, TOML files, CLI args
   # Result: debug=True, database.host="localhost"

Factory Pattern for Multi-Module Apps
-------------------------------------

Clevis provides a Factory pattern for advanced use cases where multiple modules
need their own configuration, or when you need to customize how CLI arguments
are generated.

Three Use Cases
~~~~~~~~~~~~~~~

The Factory pattern supports three distinct patterns:

1. **Simple case**: Direct ``get_config()`` call - no factory setup needed
2. **Module development**: Pre-register configs with ``@configclass``
3. **Multi-module orchestration**: Shared parser with prefixes

Simple Configuration
~~~~~~~~~~~~~~~~~~~~

For most applications, just use ``get_config()`` directly:

.. code-block:: python

   from clevis import get_config
   from dataclasses import dataclass

   @dataclass
   class Config:
       name: str = "MyApp"
       debug: bool = False

   config = get_config(Config, name="myapp")

Clevis automatically creates a factory with the default parser. No setup required.

Module Development
~~~~~~~~~~~~~~~~~~

When developing a library or module that uses Clevis for its configuration,
use the ``@configclass`` decorator to pre-register your configuration:

.. code-block:: python

   from clevis import configclass, get_config

   @configclass
   class ModuleConfig:
       api_key: str | None = None
       timeout: int = 30
       retries: int = 3

   class MyModule:
       def __init__(self):
           self.config = get_config(ModuleConfig, name="mymodule")

The ``@configclass`` decorator:

1. Applies ``@dataclass`` to your class
2. Registers it with Clevis's factory system

This allows orchestration code (the application using your module) to customize
the configuration before your module is instantiated.

Multi-Module Orchestration
~~~~~~~~~~~~~~~~~~~~~~~~~~

For CLI applications that combine multiple modules, each with their own
configuration, use factories to orchestrate argument parsing:

.. code-block:: python

   import argparse
   from clevis import configclass, get_config, get_factory

   # Your application's config
   @configclass
   class AppConfig:
       verbose: bool = False

   # Module 1's config (could be from an external package)
   @configclass
   class App1Config:
       name: str | None = None

   # Module 2's config (could be from another external package)
   @configclass
   class App2Config:
       name: str | None = None

   # Configure factories before instantiation
   get_factory(App1Config).prefix = "app1"  # CLI args: --app1-name
   get_factory(App2Config).prefix = "app2"  # CLI args: --app2-name

   # Share a single parser across all configs
   parser = argparse.ArgumentParser(description="Multi-Module App")
   get_factory(AppConfig).parser = parser
   get_factory(App1Config).parser = parser
   get_factory(App2Config).parser = parser

   # Now instantiate modules - each gets its own prefixed config
   app1 = App1()  # Uses --app1-name from CLI
   app2 = App2()  # Uses --app2-name from CLI

   if get_config(AppConfig).verbose:
       print(app1, app2)

Running this application:

.. code-block:: bash

   % python app.py --help
   usage: app.py [-h] [--app1-name APP1.NAME] [--app2-name APP2.NAME]
                 [--verbose]

   options:
     -h, --help            show this help message and exit
     --app1-name APP1.NAME
                           provide app1.name
     --app2-name APP2.NAME
                           provide app2.name
     --verbose             provide verbose

   % python app.py --app1-name "first" --app2-name "second" --verbose
   App1Config(name='first')
   App2Config(name='second')

Factory API
~~~~~~~~~~~

``get_factory(config_class)``
   Returns the Factory instance for a configuration class.
   Creates a new Factory if one doesn't exist (singleton per class).

``@configclass``
   Decorator that applies ``@dataclass`` and registers the class with
   the factory system. Equivalent to::

      @dataclass
      class Config: ...
      _ = get_factory(Config)

Factory Attributes
~~~~~~~~~~~~~~~~~~

``Factory.config_class``
   The dataclass type this factory configures.

``Factory.prefix``
   Optional prefix for CLI arguments. When set, arguments become
   ``--{prefix}-{field}`` and the prefix is stripped from parsed values.

``Factory.parser``
   The argparse-compatible parser to use. Defaults to a shared parser.
   Set this to use a custom parser or share across multiple configs.

Factory Methods
~~~~~~~~~~~~~~~

``Factory.list_fields()``
   Returns a list of ``(Field, path)`` tuples for all fields in the config,
   including nested fields. Useful for introspection.

``Factory.get_args(args=None)``
   Parse CLI arguments and return as a dictionary with dotted keys.
   If ``prefix`` is set, keys are stripped of the prefix.

``Factory.configure_parser()``
   Configures the parser with arguments for this config class.
   Called automatically on first ``get_config()`` - usually not called directly.

Custom Parsers
~~~~~~~~~~~~~~

You can use any argparse-compatible parser by implementing the ``Parser`` protocol:

.. code-block:: python

   from clevis import Parser

   class MyCustomParser:
       def add_argument(self, *args, **kwargs):
           # Your implementation
           pass

       def parse_args(self, args=None):
           # Your implementation
           pass

   get_factory(Config).parser = MyCustomParser()

This enables integration with alternative argument parsing libraries.

Testing with Factories
~~~~~~~~~~~~~~~~~~~~~~

For test isolation, use ``_reset_factories()`` to clear all registered factories:

.. code-block:: python

   from clevis import _reset_factories

   def setup_method():
       _reset_factories()

   def test_my_config():
       @configclass
       class TestConfig:
           value: str = "default"

       config = get_config(TestConfig, user=False, project=False, args=[])
       assert config.value == "default"

.. important::

   Always reset factories in test setup to avoid state leakage between tests.

Subcommands (CLI Applications)
-------------------------------

For CLI applications with multiple commands (like ``git``, ``docker``, etc.),
use the ``cmd`` parameter with ``@configclass``:

.. code-block:: python

   from clevis import configclass, get_cmd, get_config

   @configclass(cmd="check")
   class CheckConfig:
       verbose: bool = False
       fix: bool = False

   @configclass(cmd="print")
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

Running this application:

.. code-block:: bash

   % python app.py --help
   usage: app.py [-h] {check,print} ...

   positional arguments:
     {check,print}

   options:
     -h, --help     show this help message and exit

   % python app.py check --help
   usage: app.py check [-h] [--verbose] [--fix]

   options:
     -h, --help   show this help message and exit
     --verbose    provide verbose
     --fix        provide fix

   % python app.py check --verbose
   Checking with verbose=True

Subcommand Help Text
~~~~~~~~~~~~~~~~~~~~

Add help text for subcommands using the ``help`` parameter:

.. code-block:: python

   from clevis import configclass, get_cmd, get_config

   @configclass(cmd="check", help="Run diagnostics on the project")
   class CheckConfig:
       verbose: bool = False

   @configclass(cmd="build", help="Build the project")
   class BuildConfig:
       output: str = "dist"

The help text appears in the main command listing:

.. code-block:: bash

   % python app.py --help
   usage: app.py [-h] {check,build} ...

   positional arguments:
     {check,build}
       check         Run diagnostics on the project
       build         Build the project

   options:
     -h, --help     show this help message and exit

Subcommand Aliases
~~~~~~~~~~~~~~~~~~

Create shortcuts for commands using the ``aliases`` parameter:

.. code-block:: python

   from clevis import configclass, get_cmd, get_config

   @configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
   class CheckConfig:
       verbose: bool = False

   @configclass(cmd="build", help="Build the project", aliases=["b"])
   class BuildConfig:
       output: str = "dist"

Users can invoke commands using any alias:

.. code-block:: bash

   % python app.py check --verbose    # Full command
   % python app.py c --verbose        # Short alias
   % python app.py chk --verbose      # Another alias

All aliases normalize to the actual command name internally:

.. code-block:: python

   cmd = get_cmd(args=["c"])
   # cmd == "check"

   cmd = get_cmd(args=["chk"])
   # cmd == "check"

How Subcommands Work
~~~~~~~~~~~~~~~~~~~~

When you use ``@configclass(cmd="name")``:

1. Clevis creates a subparser for that command
2. ``get_cmd()`` returns the command name from parsed arguments
3. ``get_config()`` uses the subparser's arguments for that config

You can mix subcommand configs with regular configs:

.. code-block:: python

   @configclass
   class GlobalConfig:
       debug: bool = False

   @configclass(cmd="build")
   class BuildConfig:
       output: str = "dist"

   @configclass(cmd="test")
   class TestConfig:
       coverage: bool = False

   # Global config applies to all commands
   global_config = get_config(GlobalConfig)
   cmd = get_cmd()

   if cmd == "build":
       build_config = get_config(BuildConfig, project=False, user=False)
       ...
   elif cmd == "test":
       test_config = get_config(TestConfig, project=False, user=False)
       ...

Subcommand API
~~~~~~~~~~~~~~

``@configclass(cmd="name", help="description", aliases=["alias1", "alias2"])``
   Decorator that registers the config as a subcommand. Creates a subparser
   with that command name. Optional ``help`` parameter provides description
   text for the command listing. Optional ``aliases`` parameter provides
   alternative names for the command.

``get_cmd(parser=None)``
   Returns the active subcommand name from parsed arguments.
   If no parser specified, uses the default parser.

``get_sub_parser(parser)``
   Creates or returns the existing subparser for a parser.
   Called automatically by Factory when ``cmd`` is set.

Layered Configuration (Precedence)
----------------------------------

Configuration is merged in order of priority (highest to lowest):

1. **CLI arguments** - Highest priority, overrides everything
2. **Project TOML** - ``./{name}.toml``, project-specific settings
3. **User TOML** - ``~/.{name}.toml``, personal defaults
4. **Dataclass defaults** - Lowest priority, fallback values

Example Layering
~~~~~~~~~~~~~~~~

Given this dataclass:

.. code-block:: python

   @dataclass
   class Config:
       host: str = "localhost"
       port: int = 8080
       debug: bool = False

And these files:

``~/.myapp.toml``:

.. code-block:: toml

   host = "user-host"
   port = 9000

``./myapp.toml``:

.. code-block:: toml

   host = "project-host"
   debug = true

Running with ``--port 3000``:

.. code-block:: python

   config = get_config(Config, name="myapp")
   # config.host = "project-host"    # Project overrides user
   # config.port = 3000              # CLI overrides all
   # config.debug = True             # Project sets this

Error Handling
--------------

Missing Required Fields
~~~~~~~~~~~~~~~~~~~~~~~~

When a required field has no value across all layers:

.. code-block:: python

   from clevis import get_config, ConfigError
   from dataclasses import dataclass

   @dataclass
   class Config:
       api_key: str  # No default - required!

   try:
       config = get_config(Config, name="myapp")
   except ConfigError as e:
       print(e)
       # Detailed error message with actionable suggestions

Clevis provides helpful error messages:

.. code-block:: text

   ======================================================================
   Configuration Error
   ======================================================================

   Field: api_key
   Issue: Required field has no value

   Provide this value in one of these ways:

     1. Project config: ./myapp.toml
        api_key = "your_value"

     2. User config: ~/.myapp.toml
        (same format as above)

     3. CLI argument: --api-key <value>

   ======================================================================

Wrong Type Errors
~~~~~~~~~~~~~~~~~

When a configuration value doesn't match the field type:

.. code-block:: toml

   port = "not_a_number"  # Should be int

This raises a ``ConfigError`` with details about the type mismatch.

Import Errors
~~~~~~~~~~~~~

When no TOML parser is installed:

.. code-block:: python

   try:
       config = get_config(Config, name="myapp")
   except ImportError as e:
       print("Install a TOML parser:")
       print("  pip install clevis[tomli]")

Catching Configuration Errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from clevis import get_config, ConfigError

   try:
       config = get_config(Config, name="myapp")
   except ConfigError as e:
       print(f"Configuration error: {e.field_path}")
       print(f"Message: {e.message}")
       # Handle the error (e.g., show user-friendly message)
   except ImportError as e:
       print("Missing TOML parser - install with: pip install clevis[tomli]")

Testing with Configuration
--------------------------

Mocking Configuration
~~~~~~~~~~~~~~~~~~~~~

In tests, pass ``args=[]`` to avoid CLI argument parsing:

.. code-block:: python

   from clevis import get_config
   from dataclasses import dataclass

   @dataclass
   class Config:
       debug: bool = False
       name: str = "TestApp"

   def test_my_app():
       # Use dataclass defaults only
       config = get_config(Config, name="testapp", user=False, project=False, args=[])

       # Or provide specific test values
       config = get_config(Config, name="testapp", args=["--debug", "--name", "Test"])

Integration Testing
~~~~~~~~~~~~~~~~~~~

Create test configuration files:

.. code-block:: python

   import pytest
   import tempfile
   from pathlib import Path
   from clevis import get_config

   @pytest.fixture
   def temp_config_file():
       with tempfile.TemporaryDirectory() as tmpdir:
           config_path = Path(tmpdir) / "test.toml"
           config_path.write_text("""
               name = "TestConfig"
               debug = true
           """)
           yield tmpdir

   def test_with_config(temp_config_file, monkeypatch):
       monkeypatch.chdir(temp_config_file)
       config = get_config(Config, name="test", user=False)
       assert config.name == "TestConfig"

Security
--------

Clevis validates configuration file security by default to protect against
common vulnerabilities:

- **File permissions**: Rejects files readable by group/other (mode 0o644)
- **Directory permissions**: Rejects files in world-writable directories

This protects against:

1. **Credential exposure**: Config files with sensitive data readable by other users
2. **Symlink attacks**: Attackers replacing config files in world-writable directories

Default Behavior (Maximally Strict)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, Clevis rejects configuration files with security issues:

.. code-block:: python

   from clevis import get_config

   # Default: reject insecure configurations
   config = get_config(Config, name="myapp")

This will raise ``SecurityError`` if either:

- Config file is readable by group/other (``chmod 644`` vs ``chmod 600``)
- Config file is in a world-writable directory (like ``/tmp``)

Disable Security Checks
~~~~~~~~~~~~~~~~~~~~~~~~

For trusted environments (containers, development):

.. code-block:: python

   from clevis import get_config, SecurityAction

   # Skip all security checks
   config = get_config(
       Config,
       name="myapp",
       security={
           "file_permissions": SecurityAction.DONT_CHECK,
           "directory_permissions": SecurityAction.DONT_CHECK
       }
   )

Log Security Issues
~~~~~~~~~~~~~~~~~~~

For development with monitoring:

.. code-block:: python

   from clevis import get_config, SecurityAction

   # Log warnings instead of rejecting
   config = get_config(
       Config,
       name="myapp",
       security={
           "file_permissions": SecurityAction.LOG,
           "directory_permissions": SecurityAction.LOG
       }
   )

Fine-Grained Control
~~~~~~~~~~~~~~~~~~~~~

Configure each security check independently:

.. code-block:: python

   from clevis import get_config, SecurityAction

   # Check file permissions, ignore directory
   config = get_config(
       Config,
       name="myapp",
       security={
           "file_permissions": SecurityAction.REJECT,  # Strict
           "directory_permissions": SecurityAction.DONT_CHECK  # Skip
       }
   )

Security Actions
~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - ``SecurityAction.DONT_CHECK``
     - Skip validation entirely
   * - ``SecurityAction.LOG``
     - Log warning, continue loading
   * - ``SecurityAction.REJECT``
     - Raise ``SecurityError`` (default)

Fixing Security Issues
~~~~~~~~~~~~~~~~~~~~~~~

**File permissions:**

.. code-block:: bash

   # Secure: owner read/write only
   chmod 600 ~/.myapp.toml

   # Check current permissions
   ls -la ~/.myapp.toml
   # -rw------- 1 user user 1234 Jan  1 12:00 ~/.myapp.toml

**Directory permissions:**

.. code-block:: bash

   # Move config from world-writable location
   mv /tmp/myapp.toml ~/.myapp.toml

   # Or secure the directory (not recommended for shared systems)
   chmod 755 ~/myproject

Trusted Locations
~~~~~~~~~~~~~~~~~

Clevis trusts certain locations and skips security checks:

- **User's home directory** (``~/.myapp.toml``) — directory check is skipped
- **Non-existent files** — all checks are skipped (no file to attack)

Security Error Example
~~~~~~~~~~~~~~~~~~~~~~

When security validation fails:

.. code-block:: text

   SecurityError: Configuration file /tmp/myapp.toml is readable by group/other (mode 0o644).
   Use 'chmod 600 /tmp/myapp.toml' to fix.

Or:

.. code-block:: text

   SecurityError: Directory /tmp is world-writable (mode 0o777).
   This allows symlink attacks. Move config to a secure location.

Testing with Security
~~~~~~~~~~~~~~~~~~~~~

In tests with temporary files, disable security checks:

.. code-block:: python

   import tempfile
   from pathlib import Path
   from clevis import get_config, SecurityAction

   def test_with_temp_file():
       with tempfile.TemporaryDirectory() as tmpdir:
           config_file = Path(tmpdir) / "test.toml"
           config_file.write_text("name = \"test\"\n")

           # Temp files have insecure permissions, skip checks
           config = get_config(
               Config,
               name="test",
               user=False,
               project=True,
               args=[],
               security={
                   "file_permissions": SecurityAction.DONT_CHECK,
                   "directory_permissions": SecurityAction.DONT_CHECK
               }
           )
           assert config.name == "test"

TOCTOU-Safe Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clevis uses a TOCTOU-safe (Time-of-Check-Time-of-Use) implementation for file
permission validation to prevent race conditions:

**How it works:**

1. Opens the file with ``os.open()`` to get a file descriptor
2. Checks permissions on the opened file descriptor using ``os.fstat()``
3. Passes the file descriptor to the TOML parser for reading

This prevents an attacker from modifying the file between the permission check
and the file read, eliminating a common security vulnerability.

**Why this matters:**

Without this protection, an attacker could:

1. See the security check pass on a file
2. Quickly replace or modify the file during the race window
3. Have the application read a compromised file

The TOCTOU-safe implementation ensures that the file checked is the same file
read, preventing this attack vector.

Dynamic Field Registration (Plugin Architecture)
-------------------------------------------------

For plugin architectures where modules need to add their own configuration
fields at runtime, use ``register_field()``:

Basic Registration
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from dataclasses import dataclass, field
   from clevis import register_field, get_config

   # Parent config (must NOT be frozen)
   @dataclass
   class ToolsConfig:
       """Container for tool configurations."""
       list: str = "default"

   # Plugin config
   @dataclass
   class PkgqToolConfig:
       """Configuration for pkgq tool plugin."""
       enabled: bool = True
       cache_directory: str = "~/.cache/pkgq"
       timeout: int = 30

   # Register the plugin's config as a field
   register_field(ToolsConfig, "pkgq", PkgqToolConfig)

   # Create an instance - the field is now available
   config = ToolsConfig()
   print(config.pkgq.enabled)  # True
   print(config.pkgq.timeout)   # 30

TOML Support
~~~~~~~~~~~~

Registered fields work seamlessly with TOML configuration:

.. code-block:: toml

   # tools.toml
   list = "from-toml"

   # Plugin configuration section
   [tools.pkgq]
   enabled = true
   timeout = 45
   cache_directory = "/custom/cache"

.. code-block:: python

   config = get_config(ToolsConfig, name="tools")
   # config.pkgq.enabled = True (from TOML)
   # config.pkgq.timeout = 45 (from TOML)

CLI Argument Support
~~~~~~~~~~~~~~~~~~~~~

Registered fields automatically generate CLI arguments:

.. code-block:: bash

   # Arguments follow the hierarchy: parent-field-option
   python app.py --tools-pkgq-enabled --tools-pkgq-timeout 60

.. code-block:: python

   config = get_config(
       ToolsConfig,
       name="tools",
       args=["--tools-pkgq-enabled", "--tools-pkgq-timeout", "60"]
   )
   # config.pkgq.enabled = True (from CLI)
   # config.pkgq.timeout = 60 (from CLI)

Plugin Pattern Example
~~~~~~~~~~~~~~~~~~~~~~

A realistic plugin architecture:

.. code-block:: python

   # main_app.py - Main application
   from dataclasses import dataclass, field
   from clevis import get_config

   @dataclass  # NOT frozen - allows dynamic registration
   class ToolsConfig:
       """Base tools configuration that plugins can extend."""
       list: ListToolConfig = field(default_factory=ListToolConfig)

   @dataclass
   class AppConfig:
       name: str = "myapp"
       tools: ToolsConfig = field(default_factory=ToolsConfig)

   # plugin_pkgq.py - Plugin module
   from clevis import register_field

   @dataclass
   class PkgqToolConfig:
       """Pkgq tool configuration."""
       enabled: bool = True
       cache_directory: str = "~/.cache/pkgq"
       timeout: int = 30

   # Plugin registers itself when imported
   def register():
       register_field(ToolsConfig, "pkgq", PkgqToolConfig)

   # application.py - Application startup
   from main_app import AppConfig, ToolsConfig
   from plugin_pkgq import register

   # Load plugins before getting config
   register()

   # Now ToolsConfig has pkgq field
   config = get_config(AppConfig, name="myapp")
   print(config.tools.pkgq.timeout)  # 30 (default)

Registration Rules
~~~~~~~~~~~~~~~~~~

**Important constraints:**

1. **Parent must NOT be frozen**:

   .. code-block:: python

      # ❌ Wrong - frozen parent
      @dataclass(frozen=True)
      class FrozenConfig:
          name: str = "default"

      # Raises TypeError
      register_field(FrozenConfig, "plugin", PluginConfig)

      # ✓ Correct - mutable parent
      @dataclass
      class MutableConfig:
          name: str = "default"

      # Works fine
      register_field(MutableConfig, "plugin", PluginConfig)

2. **Register before get_config with CLI**:

   .. code-block:: python

      # ✓ Correct order
      register_field(ToolsConfig, "pkgq", PkgqToolConfig)
      config = get_config(ToolsConfig, name="tools")

      # ❌ Wrong order - raises RuntimeError
      config = get_config(ToolsConfig, name="tools")
      register_field(ToolsConfig, "pkgq", PkgqToolConfig)  # Too late!

      # ✓ Works if CLI is disabled
      register_field(ToolsConfig, "pkgq", PkgqToolConfig)
      config = get_config(ToolsConfig, name="tools", cli=False)

3. **No duplicate field names**:

   .. code-block:: python

      register_field(Config, "plugin", PluginConfig)

      # ❌ Raises ValueError - duplicate
      register_field(Config, "plugin", OtherPluginConfig)

      # ✓ Different names work
      register_field(Config, "plugin1", PluginConfig)
      register_field(Config, "plugin2", OtherPluginConfig)

Error Handling
~~~~~~~~~~~~~~

.. code-block:: python

   from clevis import register_field
   from dataclasses import dataclass

   # Example 1: Frozen parent
   @dataclass(frozen=True)
   class FrozenConfig:
       name: str = "default"

   @dataclass
   class PluginConfig:
       enabled: bool = True

   try:
       register_field(FrozenConfig, "plugin", PluginConfig)
   except TypeError as e:
       print(f"Error: {e}")
       # Error: Cannot add field to frozen dataclass

   # Example 2: Duplicate field name
   @dataclass
   class Config:
       existing: str = "value"

   @dataclass
   class NewConfig:
       value: int = 10

   register_field(Config, "new_field", NewConfig)

   try:
       register_field(Config, "new_field", NewConfig)  # Already registered
   except ValueError as e:
       print(f"Error: {e}")
       # Error: Field 'new_field' already exists

   # Example 3: Late registration after CLI
   from clevis import get_config, _reset_factories

   _reset_factories()

   @dataclass
   class Config:
       name: str = "default"

   @dataclass
   class LatePlugin:
       enabled: bool = True

   # Load config with CLI - this configures the parser
   config = get_config(Config, name="test", user=False, project=False, args=[])

   try:
       register_field(Config, "plugin", LatePlugin)
   except RuntimeError as e:
       print(f"Error: {e}")
       # Error: Cannot register field after parser has been configured

Complete Workflow Example
~~~~~~~~~~~~~~~~~~~~~~~~~~

Full example with plugins, TOML, and CLI:

.. code-block:: python

   from dataclasses import dataclass, field
   from pathlib import Path
   import tempfile
   from clevis import register_field, get_config, SecurityAction

   # Define configs
   @dataclass
   class ToolsConfig:
       list: str = "default"

   @dataclass
   class PkgqToolConfig:
       enabled: bool = True
       timeout: int = 30
       cache_directory: str = "~/.cache/pkgq"

   @dataclass
   class GitToolConfig:
       enabled: bool = True
       timeout: int = 60

   @dataclass
   class Config:
       name: str = "myapp"
       tools: ToolsConfig = field(default_factory=ToolsConfig)

   # Register plugins
   register_field(ToolsConfig, "pkgq", PkgqToolConfig)
   register_field(ToolsConfig, "git", GitToolConfig)

   # Create TOML with plugin configuration
   with tempfile.TemporaryDirectory() as tmpdir:
       config_file = Path(tmpdir) / "app.toml"
       config_file.write_text("""
   name = "MyApp"

   [tools]
   list = "from-toml"

   [tools.pkgq]
   enabled = true
   timeout = 45
   cache_directory = "/custom/cache"

   [tools.git]
   enabled = false
   timeout = 120
   """)

       import os
       original_dir = os.getcwd()
       try:
           os.chdir(tmpdir)
           # Load with TOML + CLI override
           config = get_config(
               Config,
               name="app",
               user=False,
               project=True,
               cli=True,
               args=["--tools-pkgq-timeout", "90"],  # CLI overrides TOML
               security={
                   "file_permissions": SecurityAction.DONT_CHECK,
                   "directory_permissions": SecurityAction.DONT_CHECK,
               },
           )

           print(f"name: {config.name}")  # MyApp (from TOML)
           print(f"tools.list: {config.tools.list}")  # from-toml (from TOML)
           print(f"tools.pkgq.enabled: {config.tools.pkgq.enabled}")  # True (from TOML)
           print(f"tools.pkgq.timeout: {config.tools.pkgq.timeout}")  # 90 (CLI override!)
           print(f"tools.git.enabled: {config.tools.git.enabled}")  # False (from TOML)
       finally:
           os.chdir(original_dir)

Key Takeaways
~~~~~~~~~~~~~

1. **Use @dataclass (NOT frozen=True)** for parent configs
2. **Call register_field() before get_config()** when CLI is enabled
3. **TOML sections follow hierarchy**: ``[parent.field]``
4. **CLI args use dashed names**: ``--parent-field-option``
5. **Plugins can register to multiple parent configs**
6. **Test with _reset_factories()** to avoid state leakage

Complete Example
----------------

Here's a complete example of a configurable application:

``config.py``:

.. code-block:: python

   from dataclasses import dataclass, field

   @dataclass
   class DatabaseConfig:
       host: str = "localhost"
       port: int = 5432
       name: str = "myapp"
       user: str | None = None
       password: str | None = None

   @dataclass
   class LoggingConfig:
       level: str = "INFO"
       file: str | None = None

   @dataclass
   class AppConfig:
       name: str = "MyApp"
       debug: bool = False
       database: DatabaseConfig = field(default_factory=DatabaseConfig)
       logging: LoggingConfig = field(default_factory=LoggingConfig)

   def load_config():
       from clevis import get_config
       return get_config(AppConfig, name="myapp")

``main.py``:

.. code-block:: python

   from config import load_config

   def main():
       config = load_config()

       print(f"Starting {config.name}")
       print(f"Debug: {config.debug}")
       print(f"Database: {config.database.host}:{config.database.port}")
       print(f"Log level: {config.logging.level}")

       if config.debug:
           print("Debug mode enabled!")

   if __name__ == "__main__":
       main()

``~/.myapp.toml`` (user config):

.. code-block:: toml

   debug = true

   [logging]
   level = "DEBUG"

``./myapp.toml`` (project config):

.. code-block:: toml

   name = "Production App"

   [database]
   host = "db.example.com"
   port = 5432

Run the application:

.. code-block:: bash

   # Use configuration files
   python main.py

   # Override from command line
   python main.py --database-host localhost --database-port 5433

Cookbook
--------

This section provides practical patterns for common configuration scenarios.

Pattern 1: Nested Configuration with Environment Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This pattern demonstrates how to structure nested configuration with three layers:
dataclass defaults, environment variables, and TOML files.

**config.py:**

.. code-block:: python

   from dataclasses import dataclass, field
   from clevis import get_config

   @dataclass
   class DatabaseConfig:
     host: str = "localhost"
     port: int = 5432
     name: str = "myapp"
     user: str = "app"
     password: str | None = None

   @dataclass
   class CacheConfig:
     host: str = "localhost"
     port: int = 6379
     ttl: int = 3600

   @dataclass
   class AppConfig:
     app_name: str = "MyApp"
     environment: str = "development"
     database: DatabaseConfig = field(default_factory=DatabaseConfig)
     cache: CacheConfig = field(default_factory=CacheConfig)

   def load_config():
     return get_config(AppConfig, name="myapp")

**TOML file (~/.myapp.toml):**

.. code-block:: toml

   app_name = "Production App"
   environment = "production"

   [database]
   host = "${DB_HOST}"
   port = "${DB_PORT}"
   password = "${DB_PASSWORD}"

   [cache]
   host = "${REDIS_HOST}"
   port = "${REDIS_PORT}"

**Usage:**

.. code-block:: python

   import os
   from config import load_config

   # Set environment variables
   os.environ["DB_HOST"] = "prod.db.example.com"
   os.environ["DB_PORT"] = "5433"
   os.environ["DB_PASSWORD"] = "secret123"
   os.environ["REDIS_HOST"] = "cache.example.com"
   os.environ["REDIS_PORT"] = "6380"

   config = load_config()

   # Result:
   # - app_name = "Production App"  # From TOML
   # - environment = "production"    # From TOML
   # - database.host = "prod.db.example.com"  # From env var
   # - database.port = 5433                    # From env var (converted)
   # - database.password = "secret123"         # From env var
   # - database.name = "myapp"                 # From dataclass default
   # - database.user = "app"                    # From dataclass default
   # - cache.host = "cache.example.com"         # From env var
   # - cache.port = 6380                        # From env var
   # - cache.ttl = 3600                         # From dataclass default

**Override with CLI:**

.. code-block:: bash

   python app.py --database-host localhost --cache-ttl 7200

Pattern 2: Environment Variables with Defaults
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This pattern shows how to use environment variable interpolation with fallback
values for optional configuration.

**Install with tomlev support:**

.. code-block:: bash

   pip install clevis[tomlev]

**config.py:**

.. code-block:: python

   from dataclasses import dataclass
   from clevis import get_config

   @dataclass
   class Config:
     api_key: str | None = None
     timeout: int = 30
     retries: int = 3

   config = get_config(Config, name="myapp")

**TOML file with defaults (./myapp.toml):**

.. code-block:: toml

   # Use environment variable or fallback to default
   api_key = "${API_KEY}"

   [database]
   host = "${DB_HOST|localhost}"
   port = "${DB_PORT|5432}"
   name = "${DB_NAME|myapp}"

   [cache]
   enabled = "${CACHE_ENABLED|false}"
   ttl = "${CACHE_TTL|300}"

**Behavior:**

.. code-block:: python

   # Scenario 1: All env vars set
   # DB_HOST=prod.db.com DB_PORT=5433 DB_NAME=proddb
   # Result: database.host="prod.db.com", database.port=5433, database.name="proddb"

   # Scenario 2: No env vars set
   # Result: database.host="localhost", database.port=5432, database.name="myapp"

   # Scenario 3: Mixed
   # DB_HOST=prod.db.com (port and name use defaults)
   # Result: database.host="prod.db.com", database.port=5432, database.name="myapp"

**Important:** All values in TOML are strings. Clevis converts them to the
appropriate types based on your dataclass field types.

Pattern 3: Custom Validation with __post_init__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``__post_init__`` for custom validation logic that runs after configuration
is loaded.

**config.py:**

.. code-block:: python

   from dataclasses import dataclass, field
   from urllib.parse import urlparse
   from clevis import get_config

   @dataclass
   class DatabaseConfig:
     host: str = "localhost"
     port: int = 5432
     name: str = "myapp"

   @dataclass
   class AppConfig:
     app_name: str = "MyApp"
     debug: bool = False
     server_url: str | None = None
     database: DatabaseConfig = field(default_factory=DatabaseConfig)

     def __post_init__(self):
       # Validate server URL format
       if self.server_url:
         parsed = urlparse(self.server_url)
         if parsed.scheme not in ("http", "https"):
           raise ValueError(
             f"Invalid server URL: scheme must be http or https, got {parsed.scheme}"
           )

         # Ensure URL has a host
         if not parsed.netloc:
           raise ValueError(
             f"Invalid server URL: missing host"
           )

   # This will raise ValueError if server_url is invalid
   config = get_config(AppConfig, name="myapp")

**Valid configuration:**

.. code-block:: toml

   server_url = "https://api.example.com"

**Invalid configuration:**

.. code-block:: toml

   # Invalid: wrong scheme
   server_url = "ftp://files.example.com"
   # Raises: ValueError: Invalid server URL: scheme must be http or https, got ftp

   # Invalid: missing host
   server_url = "https://"
   # Raises: ValueError: Invalid server URL: missing host

**Advanced validation example:**

.. code-block:: python

   from dataclasses import dataclass
   import re

   @dataclass
   class Config:
     email: str | None = None
     phone: str | None = None

     def __post_init__(self):
       # Validate email format
       if self.email:
         email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
         if not re.match(email_pattern, self.email):
           raise ValueError(f"Invalid email format: {self.email}")

       # Validate phone format (simple US format)
       if self.phone:
         phone_pattern = r'^\+1-\d{3}-\d{3}-\d{4}$'
         if not re.match(phone_pattern, self.phone):
           raise ValueError(
             f"Invalid phone format: {self.phone}. Expected: +1-XXX-XXX-XXXX"
           )

       # At least one contact method required
       if not self.email and not self.phone:
         raise ValueError("At least one contact method (email or phone) required")

**Testing validation:**

.. code-block:: python

   import pytest
   from clevis import get_config, ConfigError

   def test_valid_email():
     config = get_config(
       Config,
       name="test",
       args=["--email", "user@example.com"],
       user=False,
       project=False
     )
     assert config.email == "user@example.com"

   def test_invalid_email():
     with pytest.raises(ValueError, match="Invalid email format"):
       get_config(
         Config,
         name="test",
         args=["--email", "not-an-email"],
         user=False,
         project=False
       )

   def test_no_contact_method():
     with pytest.raises(ValueError, match="At least one contact method"):
       get_config(
         Config,
         name="test",
         args=[],
         user=False,
         project=False
       )