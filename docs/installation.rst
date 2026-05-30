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

   If the environment variable is not set, this will raise an error.

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

Development Installation
------------------------

To contribute to Clevis or run tests locally:

.. code-block:: bash

   git clone https://github.com/christophevg/clevis.git
   cd clevis
   make env-dev

This creates a development environment with all dependencies including test tools.

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

   # Run tests
   make test

   # Run tests with coverage
   make test-cov

   # Run tests on all Python versions
   make test-all

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