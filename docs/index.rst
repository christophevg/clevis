Clevis Documentation
====================

Configuration management for Python projects with dataclass-based schemas.

About the Name
--------------

A **clevis** is a U-shaped mechanical fastener that connects components while
allowing pivoting. It's used in everything from agricultural equipment to
aerospace control systems — a simple, robust connector that provides flexibility
without compromising strength.

This library follows the same principle: it **connects** multiple configuration
sources (TOML files, environment variables, CLI arguments) into a single, cohesive
interface. Just as a mechanical clevis allows articulation, Clevis allows your
configuration to flex and adapt — user-level defaults, project-level settings,
and runtime overrides all pivot around a single dataclass schema.

.. toctree::
   :maxdepth: 2

   installation
   usage
   api

Installation
============

.. code-block:: bash

   # Python 3.11+ - no extras needed
   pip install clevis

   # Python 3.10
   pip install clevis[tomli]

   # Environment variable support
   pip install clevis[envtoml]

Quick Start
===========

.. code-block:: python

   from dataclasses import dataclass
   from clevis import get_config

   @dataclass
   class Config:
       name: str = "MyApp"
       debug: bool = False

   config = get_config(Config, name="app")

API Reference
=============

.. autofunction:: clevis.get_config

.. autoclass:: clevis.ConfigError
   :members: