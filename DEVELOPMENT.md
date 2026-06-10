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

Singleton factory per config class enables multi-module coordination:

```python
@configclass
class AppConfig:
  name: str = "default"

factory = get_factory(AppConfig)
factory.prefix = "app1"  # CLI args: --app1-name
factory.parser = shared_parser

config = get_config(AppConfig)
```

Key concepts:
- One factory per config class (singleton)
- Lazy configuration (parser setup on first get_config())
- Test isolation via `_reset_factories()`

### 2. Decorator Pattern (@configclass)

Combines @dataclass with factory registration:

```python
@configclass
class Config:
  name: str = "default"

# With subcommands:
@configclass(cmd="check", help="Run diagnostics", aliases=["c"])
class CheckConfig:
  verbose: bool = False

# With TOML override:
@configclass(cmd="cli", config="client")
class CliConfig:
  server_url: str = "http://localhost"
```

Note: `config` parameter requires `cmd` parameter (TOML section extraction only makes sense with subcommands).

### 3. Parser Protocol

Extensibility via structural typing:

```python
class Parser(Protocol):
  def add_argument(self, *name_or_flags, **kwargs) -> Action: ...
  def add_subparsers(self, **kwargs) -> SubParser: ...
  def parse_args(self, args=None) -> Namespace: ...

# Use custom parser
get_factory(Config).parser = CustomParser()
```

### 4. TOML + CLI + Environment Merging

Priority (highest to lowest):
1. CLI arguments
2. Environment variables (envtoml/tomlev)
3. Project TOML
4. User TOML
5. Dataclass defaults

Implementation:
```python
config_dict = {}
config_dict.update(load_toml("~/.myapp.toml"))
config_dict.update(load_toml("./myapp.toml"))
cli_args = factory.get_args()
apply_to_dict(cli_args, config_dict)
return from_dict(data_class=Config, data=config_dict)
```

### 5. List-Append Behavior

CLI list values append to TOML values:

```bash
# TOML: packages = ["base"]
# CLI: --packages plugin1 --packages plugin2
# Result: packages = ["base", "plugin1", "plugin2"]

# To clear and replace:
# CLI: --no-packages --packages only-this
# Result: packages = ["only-this"]
```

Implementation uses argparse `action="append"` and `const=[]` for --no-field arguments.

### 6. Dynamic Field Registration

Plugin architecture with runtime field injection:

```python
@dataclass
class ToolsConfig:
  list: ListToolConfig = field(default_factory=ListToolConfig)

@dataclass
class PkgqToolConfig:
  enabled: bool = True

register_field(ToolsConfig, "pkgq", PkgqToolConfig)
# Now: ToolsConfig has pkgq field
# TOML: [tools.pkgq] works
# CLI: --tools-pkgq-enabled works
```

Requirements:
- Parent config must NOT be frozen
- Registration must happen before get_config()

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
    # Arrange
    config = Config(name="test")

    # Act
    result = get_config(Config)

    # Assert
    assert result.name == "test"
```

### Common Patterns

**Fixtures**:
```python
@pytest.fixture
def temp_config_file():
  """Create a temporary TOML config file."""
  with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
    f.write('[database]\nhost = "localhost"\n')
    yield f.name
  os.unlink(f.name)
```

**Global State Reset**:
```python
def test_factory_isolation():
  """Test that factories are properly isolated."""
  from clevis import _reset_factories

  _reset_factories()  # Clean slate before test
  # ... test code ...
  _reset_factories()  # Clean up after test
```

**CLI Arguments**:
```python
def test_cli_args():
  """Test CLI argument parsing."""
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

**Security**:
```python
def test_insecure_file_permissions():
  """Test that insecure file permissions are rejected."""
  from clevis import SecurityAction, SecurityError

  with tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as f:
    f.write('name = "test"')
    f.flush()
    os.chmod(f.name, 0o644)  # World-readable

    with pytest.raises(SecurityError):
      get_config(Config, name=f.name[:-5])
```

**Dynamic Registration**:
```python
def test_register_field():
  """Test dynamic field registration."""
  from clevis import _reset_factories

  _reset_factories()

  @dataclass
  class ParentConfig:
    existing: str = "default"

  @dataclass
  class ChildConfig:
    value: int = 42

  register_field(ParentConfig, "child", ChildConfig)

  config = ParentConfig()
  assert hasattr(config, "child")
  assert config.child.value == 42
```

### Coverage Expectations

- **Target**: 80%+ coverage
- **Focus Areas**:
  - Configuration loading (get_config)
  - CLI argument generation (Factory._configure_fields)
  - TOML parser selection (_get_toml_parser)
  - Security validation (_check_file_permissions)
  - List-append merging (_merge_list_args)

## Common Tasks

### Add New Configuration Field

```python
# 1. Add to dataclass
@dataclass
class Config:
  name: str = "default"
  new_field: str = "value"  # Add here

# 2. Update TOML examples
# myapp.toml
name = "MyApp"
new_field = "custom"

# 3. Test
def test_new_field():
  config = get_config(Config, args=["--new-field", "custom"])
  assert config.new_field == "custom"
```

### Add New CLI Argument Type

```python
# In Factory._configure_fields()
if concrete_type is NewType:
  # Custom argument handling
  target_parser.add_argument(...)
```

### Add New Parser

```python
class CustomParser:
  """Custom parser implementing Parser protocol."""

  def add_argument(self, *name_or_flags, **kwargs):
    # Implementation
    pass

  def parse_args(self, args=None):
    # Implementation
    return Namespace(**parsed)

# Use custom parser
custom_parser = CustomParser()
get_factory(Config).parser = custom_parser
config = get_config(Config)
```

### Debug Configuration Issues

1. **Check TOML files**:
   ```bash
   ls -la ~/.myapp.toml ./myapp.toml
   # Should be owner-only: -rw------- (600)
   ```

2. **Enable logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logger = logging.getLogger("clevis")
   ```

3. **Inspect factory**:
   ```python
   from clevis import get_factory

   factory = get_factory(Config)
   print(f"Prefix: {factory.prefix}")
   print(f"Configured: {factory._configured}")
   ```

4. **Check argument names**:
   ```python
   parser = argparse.ArgumentParser()
   get_factory(Config).parser = parser
   get_config(Config)
   parser.print_help()
   ```

5. **Test isolation**:
   ```python
   from clevis import _reset_factories
   _reset_factories()  # Reset before test
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

## Summary

Clevis provides:
1. **Layered Configuration** - Multiple sources with clear precedence
2. **Factory Pattern** - Coordinate across modules
3. **Dynamic Registration** - Plugin architectures
4. **Security** - File permission validation
5. **Developer Experience** - Auto-generated CLI, helpful errors

Module organization:
- `__init__.py` - Orchestration
- `factory.py` - CLI generation
- `configclass.py` - Decorators
- `registration.py` - Plugin support

For questions or issues:
- **GitHub Issues**: https://github.com/christophevg/clevis/issues
- **Documentation**: https://clevis.readthedocs.io