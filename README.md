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

## Features

| Feature | Description | Example |
|---------|-------------|---------|
| **Dataclass schemas** | Type-safe configuration | `@dataclass class Config: ...` |
| **TOML loading** | Auto-discover config files | `get_config(Config, name="myapp")` |
| **Environment vars** | `${VAR}` interpolation | `pip install clevis[envtoml]` |
| **CLI arguments** | Auto-generate argparse | `python app.py --database-host localhost` |
| **Boolean flags** | `--flag` for True, `--no-flag` for False | `python app.py --debug` / `--no-debug` |
| **List append** | Repeat `--field val` | `python app.py --packages pkg --packages c3` |
| **Layered config** | Defaults < User < Project < CLI | Priority-based merging |
| **Nested configs** | Hierarchical configuration | `[database] host = "localhost"` |
| **Subcommands** | Multi-command CLI apps | `@configclass(cmd="build")` |
| **Factory pattern** | Multi-module orchestration | `get_factory(Config).prefix = "app1"` |
| **Dynamic registration** | Plugin architecture | `register_field(Parent, "plugin", PluginConfig)` |
| **Security** | File permission validation | `SecurityAction.REJECT` (default) |

## Installation

Choose your TOML parser based on needs:

| Extra | Features | Use When |
|-------|----------|----------|
| *(none)* | Stdlib `tomllib` | Python 3.11+, minimal deps |
| [`tomli`][tomli] | Pure Python TOML | Python 3.10 compatibility |
| [`envtoml`][envtoml] | `${VAR}` interpolation | Environment-based config |
| [`tomlev`][tomlev] | `${VAR|default}` syntax | Env vars with defaults |

```bash
# Python 3.11+ - no extras needed
pip install clevis

# Python 3.10
pip install clevis[tomli]

# Environment variable support
pip install clevis[envtoml]
```

## Core Concepts

### Configuration Priority

Values are merged in order (highest priority wins):

1. **CLI arguments** — `--database-host localhost`
2. **Environment variables** — Only when using envtoml/tomlev
3. **Project TOML** — `./myapp.toml`
4. **User TOML** — `~/.myapp.toml`
5. **Dataclass defaults** — Default values in class definition

### Security

Clevis validates file permissions by default:

```python
from clevis import get_config, SecurityAction

# Default: reject insecure configurations
config = get_config(Config, name="myapp")

# Disable checks (for containers, testing)
config = get_config(
    Config,
    name="myapp",
    security={"file_permissions": SecurityAction.DONT_CHECK}
)

# Log warnings instead of rejecting
config = get_config(
    Config,
    name="myapp",
    security={"file_permissions": SecurityAction.LOG}
)
```

## Examples

The `examples/` directory contains 10 comprehensive examples:

| Example | Features Demonstrated | Run Command |
|---------|----------------------|-------------|
| **[main.py](examples/main.py)** | Basic config, CLI args, TOML, security | `uv run python main.py --help` |
| **[nested.py](examples/nested.py)** | Nested dataclasses, TOML sections | `uv run python nested.py --tool-settings-x 10` |
| **[validation.py](examples/validation.py)** | Custom validation, `__post_init__` | `uv run python validation.py --server-url "http://localhost"` |
| **[environment.py](examples/environment.py)** | `${VAR}` interpolation, credentials | `export DB_HOST=localhost && uv run python environment.py` |
| **[factory.py](examples/factory.py)** | Multi-module orchestration, prefixes | `uv run python factory.py --app1-name "first"` |
| **[commands.py](examples/commands.py)** | CLI subcommands, aliases | `uv run python commands.py check --verbose` |
| **[subcommands.py](examples/subcommands.py)** | TOML override with `config` parameter | `uv run python subcommands.py cli --server-url "https://api.example.com"` |
| **[library_mode.py](examples/library_mode.py)** | Web framework integration, testing | `uv run python library_mode.py` |
| **[dynamic.py](examples/dynamic.py)** | Plugin architecture, `register_field()` | `uv run python dynamic.py --help` |
| **[plugin.py](examples/plugin.py)** | Practical plugin implementation | `uv run python plugin.py --pkgq-timeout 60` |

See [examples/README.md](examples/README.md) for detailed feature matrix and learning path.

## Usage Patterns

For detailed usage patterns and API reference, see [PACKAGE.md](PACKAGE.md).

### Basic Configuration

```python
from dataclasses import dataclass
from clevis import get_config

@dataclass
class Config:
    name: str = "MyApp"
    debug: bool = False

config = get_config(Config, name="myapp")
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

### Library Mode

```python
from clevis import get_config

# Library mode - skip CLI parsing
config = get_config(Config, name="myapp", cli=False)

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

For complete API documentation, see [PACKAGE.md](PACKAGE.md) or [docs/api.rst](docs/api.rst).

**Key functions:**

- `get_config(data_class, name, ...)` — Load configuration from TOML and CLI
- `configclass(cmd=None, help=None, ...)` — Decorator for configuration classes
- `register_field(parent_class, field_name, field_type)` — Register plugin fields
- `get_factory(config_class)` — Get Factory for multi-module apps
- `get_cmd()` — Get active subcommand name

## Documentation

- **Quick Start** — This README
- **Examples** — [examples/README.md](examples/README.md) with feature matrix
- **Package Guide** — [PACKAGE.md](PACKAGE.md) comprehensive API and patterns
- **API Reference** — [docs/api.rst](docs/api.rst) or [clevis.readthedocs.io](https://clevis.readthedocs.io)

## Testing

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Run quality checks
make check
```

## Contributing

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