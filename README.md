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
- **TOML support** — Load from `.toml` files with automatic discovery
- **Env vars** — `${VAR}` interpolation (with envtoml/tomlev extras)
- **CLI generation** — Auto-generate argparse from dataclass
- **Layered config** — User config < project config < CLI args
- **Subcommands** — Build CLI apps with multiple commands
- **Dynamic registration** — Plugin architecture with runtime field injection
- **Security** — File permission validation to protect credentials

## Quick Start

Get running in 30 seconds:

```bash
# Install (Python 3.11+)
pip install clevis

# Or with environment variable support
pip install clevis[envtoml]
```

```python
from dataclasses import dataclass
from clevis import get_config

@dataclass
class Config:
    name: str = "MyApp"
    debug: bool = False
    port: int = 8080

# Load from ~/.myapp.toml, ./myapp.toml, and CLI args
config = get_config(Config, name="myapp")

print(config.name)   # Access as attribute
print(config.debug)  # Type-safe access
print(config.port)   # Automatic type conversion
```

**That's it!** Create a `myapp.toml` file:

```toml
name = "Production App"
debug = true

[database]
host = "db.example.com"
port = 5432
```

Override with CLI:

```bash
python app.py --name "Custom App" --port 9000
```

## Features Overview

| Feature | Description | Example |
|---------|-------------|---------|
| **Dataclass schemas** | Type-safe configuration with Python dataclasses | `@dataclass class Config: ...` |
| **TOML loading** | Auto-discover config files in user/project directories | `get_config(Config, name="myapp")` |
| **Environment vars** | `${VAR}` interpolation in TOML files | `pip install clevis[envtoml]` |
| **CLI arguments** | Auto-generate argparse from dataclass fields | `python app.py --database-host localhost` |
| **Layered config** | Defaults < User < Project < CLI | Priority-based merging |
| **Nested configs** | Hierarchical configuration with nested dataclasses | `[database] host = "localhost"` |
| **Subcommands** | Build multi-command CLI apps | `@configclass(cmd="build")` |
| **Factory pattern** | Multi-module orchestration with shared parsers | `get_factory(Config).prefix = "app1"` |
| **Dynamic registration** | Plugin architecture with runtime field injection | `register_field(Parent, "plugin", PluginConfig)` |
| **Security** | Validate file permissions to protect credentials | `SecurityAction.REJECT` (default) |
| **Custom validation** | Post-initialization validation with `__post_init__` | `def __post_init__(self): ...` |
| **Library mode** | Use Clevis without CLI argument parsing | `get_config(Config, cli=False)` |

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

# Env vars with defaults
pip install clevis[tomlev]
```

**Development installation:**

```bash
git clone https://github.com/christophevg/clevis.git
cd clevis
make env-dev  # Creates development environment
```

## Core Concepts

### 1. Configuration Schemas

Define your configuration structure using Python dataclasses:

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

**Key points:**
- All fields should have defaults (for fallback)
- Use `field(default_factory=...)` for nested dataclasses
- Optional fields use `str | None = None`

### 2. TOML Files

Create TOML files matching your dataclass structure:

```toml
name = "Production App"
debug = false

[database]
host = "db.example.com"
port = 5432
user = "appuser"
password = "${DB_PASSWORD}"  # Environment variable
```

**Auto-discovered locations:**
- User-level: `~/.{name}.toml` (personal defaults)
- Project-level: `./{name}.toml` (checked into VCS)

### 3. CLI Arguments

Clevis auto-generates CLI arguments from your dataclass:

```bash
# Flat fields
python app.py --name "Custom App" --debug

# Nested fields (dots become dashes)
python app.py --database-host localhost --database-port 5433

# Boolean flags
python app.py --debug  # Sets debug=True
```

### 4. Configuration Priority

Values are merged in order (highest priority wins):

1. **CLI arguments** — `--database-host localhost`
2. **Environment variables** — Only when using envtoml/tomlev
3. **Project TOML** — `./myapp.toml`
4. **User TOML** — `~/.myapp.toml`
5. **Dataclass defaults** — Default values in class definition

### 5. Security

Clevis validates file permissions by default:

```python
from clevis import get_config, SecurityAction

# Default: reject insecure configurations
config = get_config(Config, name="myapp")

# Disable checks (for containers, testing)
config = get_config(
    Config,
    name="myapp",
    security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK
    }
)

# Log warnings instead of rejecting
config = get_config(
    Config,
    name="myapp",
    security={
        "file_permissions": SecurityAction.LOG,
        "directory_permissions": SecurityAction.LOG
    }
)
```

**Fix security issues:**

```bash
# Secure: owner read/write only
chmod 600 ~/.myapp.toml
```

## Examples Showcase

The `examples/` directory contains 9 comprehensive examples:

| Example | Features Demonstrated | Run Command |
|---------|----------------------|-------------|
| **[main.py](examples/main.py)** | Basic config, CLI args, TOML, security | `uv run python main.py --help` |
| **[nested.py](examples/nested.py)** | Nested dataclasses, TOML sections | `uv run python nested.py --tool-settings-x 10` |
| **[validation.py](examples/validation.py)** | Custom validation, `__post_init__` | `uv run python validation.py --server-url "http://localhost"` |
| **[environment.py](examples/environment.py)** | `${VAR}` interpolation, credentials | `export DB_HOST=localhost && uv run python environment.py` |
| **[factory.py](examples/factory.py)** | Multi-module orchestration, prefixes | `uv run python factory.py --app1-name "first"` |
| **[commands.py](examples/commands.py)** | CLI subcommands, aliases | `uv run python commands.py check --verbose` |
| **[library_mode.py](examples/library_mode.py)** | Web framework integration, testing | `uv run python library_mode.py` |
| **[dynamic.py](examples/dynamic.py)** | Plugin architecture, `register_field()` | `uv run python dynamic.py --help` |
| **[plugin.py](examples/plugin.py)** | Practical plugin implementation | `uv run python plugin.py --pkgq-timeout 60` |

See [examples/README.md](examples/README.md) for detailed feature matrix and learning path.

## Usage Patterns

### Basic Configuration

```python
from dataclasses import dataclass
from clevis import get_config

@dataclass
class Config:
    name: str = "MyApp"
    debug: bool = False

# Load from user/project TOML + CLI args
config = get_config(Config, name="myapp")
```

### Environment Variables

```bash
pip install clevis[envtoml]
```

```toml
# myapp.toml
[database]
password = "${DB_PASSWORD}"
host = "${DB_HOST}"
```

```bash
export DB_PASSWORD=secret
export DB_HOST=prod.db.com
python app.py
```

### CLI Subcommands

```python
from clevis import configclass, get_cmd, get_config

@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig:
    verbose: bool = False
    fix: bool = False

@configclass(cmd="build", help="Build the project")
class BuildConfig:
    output: str = "dist"

if __name__ == "__main__":
    cmd = get_cmd()
    if cmd == "check":
        config = get_config(CheckConfig, project=False, user=False)
        print(f"Checking with verbose={config.verbose}")
    elif cmd == "build":
        config = get_config(BuildConfig, project=False, user=False)
        print(f"Building to {config.output}")
```

```bash
python app.py check --verbose
python app.py c --fix      # Alias
python app.py build --output dist
```

### Factory Pattern (Multi-Module)

```python
from clevis import configclass, get_config, get_factory
import argparse

@configclass
class AppConfig:
    verbose: bool = False

@configclass
class Module1Config:
    name: str = "module1"

@configclass
class Module2Config:
    name: str = "module2"

# Configure prefixes for CLI args
get_factory(Module1Config).prefix = "m1"  # --m1-name
get_factory(Module2Config).prefix = "m2"  # --m2-name

# Share parser across modules
parser = argparse.ArgumentParser(description="Multi-Module App")
get_factory(AppConfig).parser = parser
get_factory(Module1Config).parser = parser
get_factory(Module2Config).parser = parser

# Each module gets its own prefixed config
m1 = Module1()  # Uses --m1-name
m2 = Module2()  # Uses --m2-name
```

### Dynamic Registration (Plugin Architecture)

```python
from dataclasses import dataclass
from clevis import register_field, get_config

# Parent config (must NOT be frozen)
@dataclass
class ToolsConfig:
    list: str = "default"

# Plugin config
@dataclass
class PkgqToolConfig:
    enabled: bool = True
    timeout: int = 30

# Register plugin field at runtime
register_field(ToolsConfig, "pkgq", PkgqToolConfig)

# Now ToolsConfig has a pkgq field
config = get_config(ToolsConfig, name="tools")
print(config.pkgq.enabled)  # True
print(config.pkgq.timeout)  # 30
```

**TOML support:**

```toml
[tools.list]
format = "json"

[tools.pkgq]  # Registered field works with TOML
enabled = true
timeout = 60
```

**CLI support:**

```bash
python app.py --tools-pkgq-enabled --tools-pkgq-timeout 90
```

See [examples/dynamic.py](examples/dynamic.py) and [examples/plugin.py](examples/plugin.py) for complete examples.

### Custom Validation

```python
from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass
class Config:
    server_url: str | None = None

    def __post_init__(self):
        if self.server_url:
            parsed = urlparse(self.server_url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL: scheme must be http or https")
            if not parsed.netloc:
                raise ValueError(f"Invalid URL: missing host")

# Raises ValueError for invalid URLs
config = get_config(Config, name="myapp")
```

### Library Mode

Use Clevis in web frameworks, tests, or embedded contexts:

```python
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
```

## API Reference

### `get_config(data_class, name="project", user=True, project=True, cli=True, args=None, security=None)`

Load configuration from TOML files and CLI arguments.

**Parameters:**
- `data_class` — The dataclass type to populate
- `name` — Config file name (without `.toml` extension)
- `user` — Load user-level config (`~/.{name}.toml`)
- `project` — Load project-level config (`./{name}.toml`)
- `cli` — Parse CLI arguments from `sys.argv` (default: `True`)
- `args` — CLI arguments (defaults to `sys.argv[1:]` when `cli=True`)
- `security` — Security check configuration (default: maximally strict)

**Returns:** Instance of the dataclass with merged configuration

**Raises:**
- `ConfigError` — Missing required fields or wrong types
- `SecurityError` — Security check failed (when `action="reject"`)
- `ImportError` — No TOML parser available

### `configclass(cls=None, cmd=None, help=None, aliases=None)`

Decorator that applies `@dataclass` and registers the class for CLI subcommands.

**Parameters:**
- `cls` — The class to decorate
- `cmd` — Subcommand name (e.g., `"build"`)
- `help` — Help text for the subcommand
- `aliases` — List of aliases for the subcommand (e.g., `["b"]`)

### `register_field(parent_class, field_name, field_type)`

Register a field to a dataclass at runtime (for plugin architectures).

**Parameters:**
- `parent_class` — The parent dataclass to extend (must NOT be frozen)
- `field_name` — Name of the field to add
- `field_type` — The dataclass type for the field

**Raises:**
- `TypeError` — Parent class is frozen
- `ValueError` — Field name already exists
- `RuntimeError` — Called after `get_config()` with CLI enabled

### `get_factory(config_class)`

Get the Factory instance for a configuration class (for advanced use).

### `get_cmd(parser=None, args=None)`

Get the active subcommand name from parsed arguments.

### `SecurityAction`

Enum for security check actions:
- `SecurityAction.DONT_CHECK` — Skip validation
- `SecurityAction.LOG` — Log warning, continue
- `SecurityAction.REJECT` — Raise `SecurityError` (default)

### `ConfigError`

Raised when configuration is missing or invalid. Provides helpful error messages with actionable suggestions.

### `SecurityError`

Raised when security validation fails. Contains `path` and `check` attributes.

For complete API documentation, see [docs/api.rst](docs/api.rst) or visit [clevis.readthedocs.io](https://clevis.readthedocs.io).

## Error Messages

Clevis provides helpful, actionable errors:

**When using CLI (default):**

```
======================================================================
Configuration Error
======================================================================

Field: database.host
Issue: Required field has no value

Provide this value in one of these ways:

  1. Project config: ./myapp.toml
     [database]
     host = "your_value"

  2. User config: ~/.myapp.toml
     (same format as above)

  3. CLI argument: --database-host <value>

======================================================================
```

**When using library mode (`cli=False`):**

```
======================================================================
Configuration Error
======================================================================

Field: database.host
Issue: Required field has no value

Provide this value in one of these ways:

  1. Project config: ./myapp.toml
     [database]
     host = "your_value"

  2. User config: ~/.myapp.toml
     (same format as above)

======================================================================
```

## Testing

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Run tests on all Python versions
make test-all
```

## Documentation

- **Quick Start** — This README
- **Examples** — [examples/README.md](examples/README.md) with feature matrix
- **Usage Guide** — [docs/usage.rst](docs/usage.rst) comprehensive guide
- **API Reference** — [docs/api.rst](docs/api.rst) or [clevis.readthedocs.io](https://clevis.readthedocs.io)

## Contributing

We welcome contributions! Please see our development setup:

```bash
# Clone the repository
git clone https://github.com/christophevg/clevis.git
cd clevis

# Create development environment
make env-dev

# Run tests
make test

# Run quality checks
make check

# Format code
make format
```

See [Makefile](Makefile) for all available targets.

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