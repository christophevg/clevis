# Clevis

[![PyPI][pypi-badge]][pypi]
[![Python][python-badge]][python]
[![CI][ci-badge]][ci]
[![Coverage][coverage-badge]][coverage]
[![License][license-badge]][license]
[![Agentic][agentic-badge]][agentic]
[![PACKAGE.md](https://img.shields.io/badge/pkgq-PACKAGE.md-blueviolet)](https://github.com/christophevg/pkgq#readme)

> Configuration management for Python projects with dataclass-based schemas

Clevis provides type-safe configuration management for Python applications:

- **Dataclass schemas** — Define config structure with Python dataclasses
- **TOML support** — Load from `.toml` files
- **Env vars** — `${VAR}` interpolation (with envtoml/tomlev)
- **CLI generation** — Auto-generate argparse from dataclass
- **Layered config** — User config < project config < CLI args

## About the Name

A **clevis** is a U-shaped mechanical fastener that connects components while allowing pivoting. It's used in everything from agricultural equipment to aerospace control systems — a simple, robust connector that provides flexibility without compromising strength.

This library follows the same principle: it **connects** multiple configuration sources (TOML files, environment variables, CLI arguments) into a single, cohesive interface. Just as a mechanical clevis allows articulation, Clevis allows your configuration to flex and adapt — user-level defaults, project-level settings, and runtime overrides all pivot around a single dataclass schema.

## Quick Start

```bash
# Install (Python 3.11+)
pip install clevis

# Or with env var support
pip install clevis[envtoml]
```

```python
from dataclasses import dataclass
from clevis import get_config

@dataclass
class Config:
    name: str = "MyApp"
    debug: bool = False

config = get_config(Config, name="app")
```

## Installation

Choose your TOML parser based on needs:

| Extra | Features | Use When |
|-------|----------|----------|
| *(none)* | Stdlib `tomllib` | Python 3.11+, minimal deps |
| [`tomli`][tomli] | Pure Python TOML | Python 3.10 compatibility |
| [`envtoml`][envtoml] | `${VAR}` interpolation | Environment-based config |
| [`tomlev`][tomlev] | `${VAR\|default}` syntax | Env vars with defaults |

```bash
# Python 3.11+ - no extras needed
pip install clevis

# Python 3.10
pip install clevis[tomli]

# Environment variable support
pip install clevis[envtoml]
```

## Usage

### Define Your Config

```python
from dataclasses import dataclass, field

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    user: str | None = None
    password: str | None = None

@dataclass
class AppConfig:
    name: str = "MyApp"
    debug: bool = False
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
```

### Load Configuration

```python
from clevis import get_config

# Load from ~/.myapp.toml and ./myapp.toml
config = get_config(AppConfig, name="myapp")
```

Configuration layers (lowest to highest priority):

1. **Dataclass defaults**
2. **User-level TOML** — `~/.{name}.toml`
3. **Project-level TOML** — `./{name}.toml`
4. **CLI arguments** — `--database-host`, `--debug`

### TOML Files

Create `myapp.toml`:

```toml
name = "Production App"
debug = true

[database]
host = "db.example.com"
port = 5432
```

With env var support (`clevis[envtoml]` or `clevis[tomlev]`):

```toml
[database]
password = "${DB_PASSWORD}"        # envtoml
host = "${DB_HOST|localhost}"       # tomlev (with default)
```

### CLI Arguments

Clevis auto-generates CLI arguments:

```bash
python app.py --database-host localhost
python app.py --database-port 5432
python app.py --debug
```

Nested dataclasses become dashed arguments: `database.host` → `--database-host`

## Testing

```bash
# Run tests
make test

# Run with coverage
make test-cov
```

## API Reference

### `get_config(data_class, name="project", user=True, project=True, args=None)`

Load configuration from TOML files and CLI arguments.

**Parameters:**
- `data_class` — The dataclass type to populate
- `name` — Config file name (without `.toml`)
- `user` — Load user-level config (`~/.{name}.toml`)
- `project` — Load project-level config (`./{name}.toml`)
- `args` — CLI arguments (defaults to `sys.argv[1:]`)

**Returns:** Instance of the dataclass with merged configuration

**Raises:**
- `ConfigError` — Missing required fields or wrong types
- `ImportError` — No TOML parser available

## Error Messages

Clevis provides helpful, actionable errors:

```
======================================================================
Configuration Error
======================================================================

Field: database.host
Issue: Required field has no value

Provide this value in one of these ways:

  1. Project config: ./project.toml
     [database]
     host = "your_value"

  2. User config: ~/.project.toml
     (same format as above)

  3. CLI argument: --database-host <value>

======================================================================
```

## Acknowledgments

Clevis builds on excellent work from the Python community:

- **[tomllib](https://docs.python.org/3/library/tomllib.html)** — Python 3.11+ stdlib
- **[tomli](https://github.com/hukkin/tomli)** — Pure Python TOML 1.0
- **[envtoml](https://github.com/sank8m/envtoml)** — Env var interpolation
- **[tomlev](https://github.com/thesimj/tomlev)** — Env vars with defaults
- **[dacite](https://github.com/konradhalas/dacite)** — Dict-to-dataclass conversion

## License

MIT

[pypi]: https://pypi.org/project/clevis/
[pypi-badge]: https://img.shields.io/pypi/v/clevis.svg
[python]: https://www.python.org/
[python-badge]: https://img.shields.io/badge/Python-3.10+-blue.svg
[ci]: https://github.com/christophevg/clevis/actions/workflows/test.yml
[ci-badge]: https://img.shields.io/github/actions/workflow/status/christophevg/clevis/test.yml.svg
[coverage]: https://coveralls.io/github/christophevg/clevis
[coverage-badge]: https://img.shields.io/coveralls/github/christophevg/clevis.svg
[license]: LICENSE
[license-badge]: https://img.shields.io/github/license/christophevg/clevis.svg
[agentic]: https://christophe.vg/about/Agentic-Workflow
[agentic-badge]: https://img.shields.io/badge/workflow-agentic-blueviolet?style=flat-square
[tomli]: https://github.com/hukkin/tomli
[envtoml]: https://github.com/sank8m/envtoml
[tomlev]: https://github.com/thesimj/tomlev
