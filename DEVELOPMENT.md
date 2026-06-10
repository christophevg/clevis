# DEVELOPMENT.md

## Project Overview

Clevis is a type-safe configuration management library for Python applications. It connects multiple configuration sources (TOML files, environment variables, CLI arguments) into a unified dataclass-based interface with automatic CLI argument generation.

**Core Features**:
- Dataclass schemas with type hints
- Layered configuration with priority merging
- Auto-discovery of TOML files
- CLI argument generation from dataclass fields
- Environment variable interpolation (${VAR})
- Subcommand support
- Plugin architecture with dynamic field registration
- Security validation for file permissions

## Architecture

### Module Structure

```
src/clevis/
├── __init__.py       # Main entry: get_config, get_cmd, SecurityAction
├── factory.py        # Factory pattern, CLI argument generation
├── configclass.py    # @configclass decorator for subcommands
└── registration.py   # Dynamic field registration for plugins
```

### Data Flow

Configuration sources merge in priority order:
1. Dataclass defaults (lowest)
2. User TOML (~/.name.toml)
3. Project TOML (./name.toml)
4. CLI arguments (highest)

Result converted to dataclass instance via dacite.

### Module Responsibilities

**__init__.py**: Public API, configuration loading orchestration
- `get_config()` - Load configuration from all sources
- `get_cmd()` - Get active subcommand
- `_get_toml_parser()` - Select TOML parser (envtoml → tomlev → tomli → tomllib)
- `_check_file_permissions()` - TOCTOU-safe security validation
- `_merge_list_args()` - Merge CLI list args with TOML values

**factory.py**: Factory pattern & CLI generation
- `Factory` - Singleton per config class
- `Parser` Protocol - Interface for argparse-compatible parsers
- `get_factory()` - Get or create Factory instance
- `unpack_type()` - Unpack Optional[T] and Union types
- `apply_to_dict()` - Apply dotted CLI args to nested dict

**configclass.py**: Decorator pattern
- `configclass()` - Applies @dataclass and registers factory

**registration.py**: Dynamic registration
- `register_field()` - Add field to parent dataclass at runtime

## Key Patterns

### 1. Factory Pattern
Singleton factory per config class enables multi-module coordination.

```python
@configclass
class AppConfig:
  name: str = "default"

factory = get_factory(AppConfig)
factory.prefix = "app1"
factory.parser = shared_parser
config = get_config(AppConfig)
```

### 2. Decorator Pattern (@configclass)
Combines @dataclass with factory registration. Note: `config` parameter requires `cmd` parameter.

```python
@configclass
class Config:
  name: str = "default"

@configclass(cmd="check", help="Run diagnostics", aliases=["c"])
class CheckConfig:
  verbose: bool = False

@configclass(cmd="cli", config="client")
class CliConfig:
  server_url: str = "http://localhost"
```

### 3. Parser Protocol
Extensibility via structural typing.

```python
class Parser(Protocol):
  def add_argument(self, *name_or_flags, **kwargs) -> Action: ...
  def add_subparsers(self, **kwargs) -> SubParser: ...
  def parse_args(self, args=None) -> Namespace: ...

get_factory(Config).parser = CustomParser()
```

### 4. TOML + CLI + Environment Merging
Priority (highest to lowest): CLI arguments → Environment variables → Project TOML → User TOML → Dataclass defaults

```python
config_dict = {}
config_dict.update(load_toml("~/.myapp.toml"))
config_dict.update(load_toml("./myapp.toml"))
cli_args = factory.get_args()
apply_to_dict(cli_args, config_dict)
return from_dict(data_class=Config, data=config_dict)
```

### 5. List-Append Behavior
CLI list values append to TOML values. Use `--no-field` to clear.

```bash
# TOML: packages = ["base"]
# CLI: --packages plugin1 --packages plugin2
# Result: packages = ["base", "plugin1", "plugin2"]
```

### 6. Dynamic Field Registration
Plugin architecture with runtime field injection. Requirements: parent config must NOT be frozen; registration must happen before get_config().

```python
@dataclass
class ToolsConfig:
  list: ListToolConfig = field(default_factory=ListToolConfig)

@dataclass
class PkgqToolConfig:
  enabled: bool = True

register_field(ToolsConfig, "pkgq", PkgqToolConfig)
```

## Important Design Decisions

### Why Factory Pattern?

**Problem**: Coordinate configuration across multiple modules

**Solution**: Singleton Factory per config class

**Rationale**:
- Single source of truth
- Orchestration point for customization
- Test isolation via reset

### Why config requires cmd?

`config` parameter extracts TOML sections:
```toml
[client]  # config="client"
server_url = "http://localhost"
```

This only makes sense with subcommands (defined by `cmd`), so `config` requires `cmd`.

### Why List-Append Instead of List-Replace?

**Options**:
1. Replace (CLI replaces TOML values)
2. Append (CLI adds to TOML values) - CHOSEN

**Rationale**:
- Composition: TOML base + CLI additions
- Flexibility: --no-field clears if needed
- Common pattern: matches package managers

### Why Aliases Replace Entire Argument Name?

Aliases are short-form alternatives:
- Canonical: `--app-packages X`
- Alias: `--with X` (not `--app-with X`)

Double-prefixing defeats the purpose of aliases.

### Why Conflict Detection for Field Names?

Same argument registered twice → argparse error. Early detection prevents silent failures where argparse just uses the last one defined.

## Development Workflow

### Setup

```bash
git clone https://github.com/christophevg/clevis.git
cd clevis
make env-dev  # Python 3.10+
make test
make check
```

### Commands

```bash
make test          # Run tests
make test-cov      # Run with coverage
make format        # Format code (Ruff)
make lint          # Check linting
make typecheck     # Run mypy
make check         # All quality checks
make build         # Build packages
make pre-publish   # Pre-publication checks
```

### Test Structure

```
tests/
├── test_parser.py          # TOML parser selection
├── test_security.py        # Security validation
├── test_list_append.py     # List-append CLI behavior
├── test_cli_aliases.py     # CLI alias support
└── test_bug_regression.py  # Bug fix regression tests
```

### Running Tests

```bash
make test                                    # All tests
make test TEST=tests/test_parser.py          # Specific file
make test TEST=tests/test_parser.py::TestTomlParser::test_envtoml_has_priority  # Specific test
make test-cov                                # With coverage report
```

### Code Style

- **Formatter**: Ruff (Black-compatible)
- **Line Length**: 100 characters
- **Indentation**: 2 spaces
- **Quotes**: Double quotes
- **Import Sorting**: Ruff isort

Configuration in pyproject.toml:
```toml
[tool.ruff]
line-length = 100
indent-width = 2

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Type Checking

- **Type Checker**: mypy
- **Python Version**: 3.10+
- **Strict Mode**: Enabled

```bash
make typecheck
```

### PR Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes (follow style, add tests, update docs)
3. Run checks: `make check`
4. Commit: `git commit -m "feat: add your feature"`
5. Push and create PR

## Testing Guidelines

### Test Structure

```python
class TestFeatureName:
  """Tests for feature description."""

  def test_basic_case(self):
    """Test description."""
    config = Config(name="test")
    result = get_config(Config)
    assert result.name == "test"
```

### Common Patterns

**Global State Reset** (essential for test isolation):
```python
def test_factory_isolation():
  from clevis import _reset_factories
  _reset_factories()  # Clean slate before test
  # ... test code ...
  _reset_factories()  # Clean up after test
```

**CLI Arguments**:
```python
def test_cli_args():
  from clevis import _reset_factories
  _reset_factories()

  @dataclass
  class Config:
    name: str = "default"
    debug: bool = False

  config = get_config(Config, args=["--name", "custom", "--debug"])
  assert config.name == "custom"
  assert config.debug is True
```

### Coverage Expectations

- **Target**: 80%+ coverage
- **Focus Areas**: Configuration loading, CLI argument generation, TOML parser selection, security validation, list-append merging

## Common Tasks

### Add New Configuration Field

```python
@dataclass
class Config:
  name: str = "default"
  new_field: str = "value"

def test_new_field():
  config = get_config(Config, args=["--new-field", "custom"])
  assert config.new_field == "custom"
```

### Add New Parser

```python
class CustomParser:
  def add_argument(self, *name_or_flags, **kwargs):
    pass

  def parse_args(self, args=None):
    return Namespace(**parsed)

custom_parser = CustomParser()
get_factory(Config).parser = custom_parser
config = get_config(Config)
```

## Reference

### Key Files

1. **src/clevis/__init__.py** - Main entry point (get_config, get_cmd, security)
2. **src/clevis/factory.py** - Factory pattern, CLI generation
3. **src/clevis/configclass.py** - @configclass decorator
4. **src/clevis/registration.py** - Dynamic registration

### Examples

- **examples/main.py** - Basic configuration loading
- **examples/nested.py** - Nested dataclasses
- **examples/commands.py** - CLI subcommands
- **examples/dynamic.py** - Dynamic field registration
- **examples/plugin.py** - Plugin pattern

### Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| dacite | Dict → dataclass conversion | Yes |
| tomllib | TOML parsing (Python 3.11+) | Yes (stdlib) |
| tomli | TOML parsing (Python 3.10) | Optional |
| envtoml | ${VAR} interpolation | Optional |
| tomlev | ${VAR\|default} syntax | Optional |

### Version Compatibility

- **Python**: 3.10, 3.11, 3.12
- **Type Hints**: Strict typing with mypy


