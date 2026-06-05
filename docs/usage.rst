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

   # Don't use --no-debug (not supported)
   # Just don't pass --debug if you want False

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

How Subcommands Work
~~~~~~~~~~~~~~~~~~~

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

``@configclass(cmd="name")``
   Decorator that registers the config as a subcommand. Creates a subparser
   with that command name.

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
~~~~~~~~~~~~~~~

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