Installation
============

Clevis requires Python 3.10 or later and supports multiple installation options
depending on your needs.

Requirements
------------

- **Python**: 3.10 or later
- **Dependencies**:
  - ``dacite`` (for dictionary-to-dataclass conversion)
  - A TOML parser (see options below)

Basic Installation
------------------

The simplest installation works with Python 3.11+ using the built-in ``tomllib``:

.. code-block:: bash

   pip install clevis

This uses Python's standard library TOML parser (available since Python 3.11).

Python 3.10 Support
-------------------

For Python 3.10, you need the ``tomli`` extra which provides a pure-Python TOML parser:

.. code-block:: bash

   pip install clevis[tomli]

Environment Variable Support
-----------------------------

Clevis supports two extras for environment variable interpolation in TOML files.

envtoml
~~~~~~~

The ``envtoml`` extra enables ``${VAR}`` syntax for environment variables:

.. code-block:: bash

   pip install clevis[envtoml]

Example TOML:

.. code-block:: toml

   [database]
   password = "${DB_PASSWORD}"
   host = "${DB_HOST}"

.. note::

   If the environment variable is not set, this will raise an error when loading.

tomlev
~~~~~~

The ``tomlev`` extra enables ``${VAR|default}`` syntax with fallback values:

.. code-block:: bash

   pip install clevis[tomlev]

Example TOML:

.. code-block:: toml

   [database]
   password = "${DB_PASSWORD}"
   host = "${DB_HOST|localhost}"
   port = "${DB_PORT|5432}"

.. note::

   The ``|default`` syntax provides a fallback when the environment variable is not set.

Choosing Your Parser
--------------------

+------------------+----------------------------+------------------------------------------+
| Extra            | Features                   | Use When                                 |
+==================+============================+==========================================+
| *(none)*         | Stdlib ``tomllib``         | Python 3.11+, minimal dependencies       |
+------------------+----------------------------+------------------------------------------+
| ``tomli``        | Pure Python TOML parser    | Python 3.10 compatibility                |
+------------------+----------------------------+------------------------------------------+
| ``envtoml``      | ``${VAR}`` interpolation   | Environment-based configuration          |
+------------------+----------------------------+------------------------------------------+
| ``tomlev``       | ``${VAR|default}`` syntax  | Env vars with fallback defaults          |
+------------------+----------------------------+------------------------------------------+

Priority Order
~~~~~~~~~~~~~~

If multiple extras are installed, Clevis selects parsers in this order:

1. **envtoml** - Best for environment variable interpolation
2. **tomlev** - Alternative with default value support
3. **tomli** - Pure Python fallback
4. **tomllib** - Stdlib (Python 3.11+)

Combining Extras
----------------

You can install multiple extras at once:

.. code-block:: bash

   # Development with all extras
   pip install clevis[envtoml,dev]

   # Or for development from source
   pip install -e .[envtoml,dev]

Development Installation
------------------------

To contribute to Clevis or run tests locally:

.. code-block:: bash

   git clone https://github.com/christophevg/clevis.git
   cd clevis
   make env-dev

This creates a development environment with all dependencies including test tools.

Development Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~

The development installation includes:

- **Testing**: ``pytest``, ``pytest-cov``, ``coverage``
- **Type checking**: ``mypy``
- **Linting**: ``ruff``
- **Documentation**: ``sphinx``, ``sphinx-rtd-theme``
- **All TOML parsers**: For testing across all backends

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

   # Run tests
   make test

   # Run tests with coverage
   make test-cov

   # Run tests on all Python versions
   make test-all

   # Run specific test file
   make test TEST=tests/test_config.py

   # Run specific test function
   make test TEST=tests/test_config.py::test_basic_config

Verifying Installation
----------------------

To verify your installation:

.. code-block:: python

   from clevis import get_config
   from dataclasses import dataclass

   @dataclass
   class Config:
       name: str = "Test"

   config = get_config(Config, name="test")
   print(config.name)  # Output: Test

Check TOML Parser
~~~~~~~~~~~~~~~~~

To check which TOML parser is being used:

.. code-block:: python

   from clevis import _get_toml_parser

   parser = _get_toml_parser()
   print(f"Using parser: {parser.__module__}")

   # Output examples:
   # Using parser: tomllib (Python 3.11+)
   # Using parser: tomli (Python 3.10)
   # Using parser: envtoml (with env var support)

Troubleshooting
---------------

No TOML Parser Available
~~~~~~~~~~~~~~~~~~~~~~~~~

If you see this error:

.. code-block:: text

   ImportError: No TOML parser available.

Install one of the extras:

.. code-block:: bash

   pip install clevis[tomli]      # Python 3.10
   pip install clevis[envtoml]    # Environment variable support

Python Version Issues
~~~~~~~~~~~~~~~~~~~~~

If you're using Python 3.10 and see import errors for ``tomllib``, install the
``tomli`` extra:

.. code-block:: bash

   pip install clevis[tomli]

Import Errors with envtoml/tomlev
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If environment variable interpolation isn't working, ensure you've installed
the correct extra:

.. code-block:: bash

   pip install clevis[envtoml]    # For ${VAR} syntax
   pip install clevis[tomlev]     # For ${VAR|default} syntax

Security Permission Errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you see ``SecurityError`` about file permissions:

.. code-block:: text

   SecurityError: Configuration file ~/.myapp.toml is readable by group/other.

Fix the permissions:

.. code-block:: bash

   # Secure: owner read/write only
   chmod 600 ~/.myapp.toml

   # Or skip security checks for development
   # In your code:
   # get_config(Config, security={"file_permissions": SecurityAction.DONT_CHECK})

Development Container Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If running in a container with different user/group IDs:

.. code-block:: python

   from clevis import get_config, SecurityAction

   # Skip security checks in containers
   config = get_config(
       Config,
       security={
           "file_permissions": SecurityAction.DONT_CHECK,
           "directory_permissions": SecurityAction.DONT_CHECK
       }
   )

Upgrading
---------

To upgrade to the latest version:

.. code-block:: bash

   pip install --upgrade clevis

   # Or with extras
   pip install --upgrade clevis[envtoml]

Check the `changelog <https://github.com/christophevg/clevis/blob/master/HISTORY.md>`_
for release notes and breaking changes.

Version Compatibility
---------------------

Clevis follows semantic versioning:

- **Major version (X.0.0)**: Breaking changes
- **Minor version (0.X.0)**: New features, backward compatible
- **Patch version (0.0.X)**: Bug fixes, backward compatible

**Supported Python versions:**

- Python 3.10: Supported with ``tomli`` extra
- Python 3.11+: Full support with stdlib ``tomllib``
- Python 3.12+: Tested and supported

**Dependency versions:**

- ``dacite`` >= 1.8.0
- ``tomli`` >= 2.0.0 (Python 3.10)
- ``envtoml`` >= 1.0.0 (optional)
- ``tomlev`` >= 1.0.0 (optional)