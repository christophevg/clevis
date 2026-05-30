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