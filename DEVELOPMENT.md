# DEVELOPMENT.md

## Project Overview

### What is Clevis?

Clevis is a type-safe configuration management library for Python applications. It connects multiple configuration sources (TOML files, environment variables, CLI arguments) into a unified dataclass-based interface with automatic CLI argument generation.

**Core Purpose**: Provide a simple, type-safe way to manage configuration across multiple sources with clear precedence.

### Key Features

1. **Dataclass Schemas** - Define configuration structure with Python dataclasses and type hints
2. **Layered Configuration** - Merge configuration from multiple sources with clear priority
3. **TOML Support** - Auto-discover configuration files in user/project directories
4. **CLI Generation** - Auto-generate argparse arguments from dataclass fields
5. **Environment Variables** - `${VAR}` interpolation in TOML files (with envtoml/tomlev)
6. **Subcommands** - Build CLI applications with multiple commands
7. **Factory Pattern** - Multi-module orchestration with shared parsers
8. **Dynamic Registration** - Plugin architecture with runtime field injection
9. **Security Validation** - File permission checks to protect credentials

### Why Clevis?

- **Type Safety**: Strongly-typed configuration with IDE support and runtime validation
- **Developer Experience**: Helpful error messages with actionable suggestions
- **Flexibility**: Multiple TOML parsers (envtoml, tomlev, tomli, stdlib)
- **No Lock-in**: Works with plain dataclasses, easy to test, easy to migrate away from

---

## Architecture Overview

### Module Structure

```
src/clevis/
├── __init__.py       # Main entry point: get_config, get_cmd, SecurityAction
├── factory.py        # Factory pattern implementation, CLI argument generation
├── configclass.py    # @configclass decorator for subcommands
└── registration.py   # Dynamic field registration for plugins
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      Configuration Sources                       │
│  ┌───────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Dataclass     │  │ User TOML    │  │ Project TOML          │ │
│  │ Defaults      │  │ ~/.name.toml │  │ ./name.toml           │ │
│  │ (lowest)      │  │              │  │                       │ │
│  └───────────────┘  └──────────────┘  └───────────────────────┘ │
│         │                   │                    │               │
│         └───────────────────┴────────────────────┘               │
│                             │                                    │
│                             ▼                                    │
│                    ┌─────────────────┐                           │
│                    │   Merge Layer   │                           │
│                    │   (dict update) │                           │
│                    └─────────────────┘                           │
│                             │                                    │
│                             ▼                                    │
│                    ┌─────────────────┐                           │
│                    │  CLI Arguments  │                           │
│                    │  (highest)      │                           │
│                    └─────────────────┘                           │
│                             │                                    │
│                             ▼                                    │
│                    ┌─────────────────┐                           │
│                    │    dacite      │                           │
│                    │  dict → class  │                           │
│                    └─────────────────┘                           │
│                             │                                    │
│                             ▼                                    │
│                    ┌─────────────────┐                           │
│                    │  Config Class  │                           │
│                    │   Instance     │                           │
│                    └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

#### `__init__.py` - Main Entry Point

**Purpose**: Public API and configuration loading orchestration

**Key Functions**:
- `get_config()` - Load configuration from all sources
- `get_cmd()` - Get active subcommand from parsed arguments
- `_get_toml_parser()` - Select appropriate TOML parser
- `_check_file_permissions()` - Security validation
- `_merge_list_args()` - Merge CLI list arguments with TOML values

**Patterns**:
- **Lazy Loading**: TOML parser loaded once on first use
- **TOCTOU Prevention**: File descriptor-based permission checks
- **Priority-based Parser Selection**: envtoml → tomlev → tomli → tomllib

#### `factory.py` - Factory Pattern & CLI Generation

**Purpose**: Manage dataclass configuration and generate CLI arguments

**Key Components**:
- `Factory` - Configuration factory for a dataclass (singleton per class)
- `Parser` Protocol - Interface for argparse-compatible parsers
- `get_factory()` - Get or create Factory for a config class
- `unpack_type()` - Unpack Optional[T] and Union types
- `apply_to_dict()` - Apply dotted CLI args to nested dict

**Patterns**:
- **Factory Pattern**: Singleton factory per config class
- **Lazy Configuration**: Parser configured on first `get_config()`
- **Protocol**: Parser protocol for extensibility

#### `configclass.py` - Decorator

**Purpose**: Combine `@dataclass` with factory registration

**Key Function**:
- `configclass()` - Decorator that applies `@dataclass` and registers factory

**Patterns**:
- **Decorator Pattern**: Transparently enhance dataclasses
- **Parameter Validation**: Warn on invalid parameter combinations

#### `registration.py` - Dynamic Field Registration

**Purpose**: Enable plugin architectures with runtime field injection

**Key Function**:
- `register_field()` - Add field to parent dataclass at runtime

**Patterns**:
- **Plugin Architecture**: Runtime modification of dataclasses
- **Validation-First**: Check constraints before modification

---

## Key Patterns

### 1. Factory Pattern for Configuration Management

**Why**: Multiple modules need coordinated configuration with shared parsers.

**How it works**:
```python
# Each config class gets a singleton Factory
@configclass
class AppConfig:
  name: str = "default"

# Factory is created automatically
factory = get_factory(AppConfig)

# Orchestration code can customize before get_config()
factory.prefix = "app1"  # CLI args: --app1-name
factory.parser = shared_parser  # Share across modules

# Later: get_config() uses the configured factory
config = get_config(AppConfig)
```

**Key Concepts**:
- **Singleton per class**: One factory per config class
- **Lazy configuration**: Parser setup happens on first `get_config()`
- **Global state reset**: `_reset_factories()` for test isolation

### 2. Decorator Pattern (@configclass)

**Why**: Simplify the common case of registering a config class.

**How it works**:
```python
# Basic: @configclass applies @dataclass and registers factory
@configclass
class Config:
  name: str = "default"

# With subcommands:
@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig:
  verbose: bool = False

# With TOML override:
@configclass(cmd="cli", config="client")
class CliConfig:
  server_url: str = "http://localhost"
```

**Key Concepts**:
- **Transparent**: Works just like `@dataclass` with extra registration
- **Validation**: Warns on invalid parameter combinations
- **Subcommand Isolation**: TOML `[cmd]` section becomes entire config

### 3. Parser Protocol for Extensibility

**Why**: Allow alternative argument parsers beyond argparse.

**How it works**:
```python
class Parser(Protocol):
  def add_argument(self, *name_or_flags, **kwargs) -> Action: ...
  def add_subparsers(self, **kwargs) -> SubParser: ...
  def parse_args(self, args=None) -> Namespace: ...

# Any class implementing this protocol can be used
class CustomParser:
  def add_argument(self, *args, **kwargs):
    # Custom implementation
    pass
  # ... other methods

# Use custom parser
get_factory(Config).parser = CustomParser()
```

**Key Concepts**:
- **Protocol**: Structural typing, no inheritance required
- **Flexibility**: Support alternative parsers in future

### 4. TOML + CLI + Environment Merging

**Why**: Multiple configuration sources with clear precedence.

**Priority Order** (highest to lowest):
1. CLI arguments (`--database-host localhost`)
2. Environment variables (when using envtoml/tomlev)
3. Project TOML (`./myapp.toml`)
4. User TOML (`~/.myapp.toml`)
5. Dataclass defaults

**How it works**:
```python
# 1. Start with defaults
config_dict = {}

# 2. Load user TOML
config_dict.update(load_toml("~/.myapp.toml"))

# 3. Load project TOML (overrides user)
config_dict.update(load_toml("./myapp.toml"))

# 4. Parse CLI args (overrides TOML)
cli_args = factory.get_args()
apply_to_dict(cli_args, config_dict)

# 5. Convert to dataclass
return from_dict(data_class=Config, data=config_dict)
```

**Key Concepts**:
- **Layered Update**: Later sources override earlier ones
- **Type Conversion**: dacite handles dict → dataclass conversion
- **List Append**: CLI list values append to TOML values

### 5. List-Append Behavior for CLI Arguments

**Why**: Allow accumulating list values instead of replacing.

**Behavior**:
- `--field X --field Y` → Append to list
- `--no-field` → Clear list (set to `[]`)
- TOML values provide base, CLI values append

**How it works**:
```python
# TOML: packages = ["base"]
# CLI: --packages plugin1 --packages plugin2
# Result: packages = ["base", "plugin1", "plugin2"]

# Implementation in get_config():
cli_args = factory.get_args()
_merge_list_args(Config, cli_args, config_dict)
# _merge_list_args combines TOML + CLI values for list fields
```

**Key Concepts**:
- **Append Action**: argparse `action="append"` for list fields
- **Empty List Marker**: `const=[]` for `--no-field` arguments
- **None Marker**: `default=None` to detect when no CLI args provided

### 6. Dynamic Field Registration for Plugins

**Why**: Enable plugin architectures to inject configuration at runtime.

**How it works**:
```python
# Parent config (must NOT be frozen)
@dataclass
class ToolsConfig:
  list: ListToolConfig = field(default_factory=ListToolConfig)

# Plugin config
@dataclass
class PkgqToolConfig:
  enabled: bool = True

# Plugin registration
register_field(ToolsConfig, "pkgq", PkgqToolConfig)

# Now ToolsConfig has a pkgq field
# TOML: [tools.pkgq] works
# CLI: --tools-pkgq-enabled works
```

**Key Concepts**:
- **Runtime Modification**: Add fields after class definition
- **Namespace Derivation**: Automatic from parent hierarchy
- **Validation**: Parent must not be frozen, registration before `get_config()`

---

## Important Design Decisions

### Why Factory Pattern?

**Problem**: How to coordinate configuration across multiple modules?

**Solution**: Singleton Factory per config class.

**Rationale**:
- **Single Source of Truth**: One factory manages one config class
- **Orchestration Point**: Customize before `get_config()` (prefix, parser)
- **Test Isolation**: `_reset_factories()` clears global state

**Alternatives Considered**:
- Global configuration object: Less flexible, harder to test
- Per-instance factories: No coordination, duplication

### Why `config` Parameter requires `cmd`?

**Problem**: TOML section extraction needs context.

**Context**: The `config` parameter specifies which TOML section to extract:
```toml
[client]  # config="client"
server_url = "http://localhost"
```

**Rationale**:
- `config` is for TOML extraction, which only makes sense with subcommands
- Subcommands need `cmd` parameter to define the command name
- Without `cmd`, there's no subcommand context, so `config` has no use case

**Error Message**:
```
@configclass parameter 'config' requires 'cmd' parameter.
Use @configclass(cmd='name', config='section') instead.
```

### Why List-Append Instead of List-Replace?

**Problem**: How should CLI list arguments interact with TOML values?

**Options**:
1. **Replace**: CLI values replace TOML values entirely
2. **Append**: CLI values append to TOML values (chosen)

**Rationale for Append**:
- **Composition**: Allow TOML base + CLI additions
- **Flexibility**: Users can still clear with `--no-field`
- **Common Pattern**: Matches package managers (pip, apt)

**Example**:
```bash
# TOML: packages = ["base"]
# CLI: --packages plugin1
# Result: packages = ["base", "plugin1"]

# To clear and replace:
# CLI: --no-packages --packages only-this
# Result: packages = ["only-this"]
```

### Why Aliases Replace Entire Argument Name?

**Problem**: How should aliases interact with prefixes?

**Context**:
```python
@dataclass
class Config:
  packages: list[str] = field(
    default_factory=list,
    metadata={"cli_aliases": ["with"]}
  )

get_factory(Config).prefix = "app"
```

**Behavior**:
- **Canonical**: `--app-packages X`
- **Alias**: `--with X` (not `--app-with X`)

**Rationale**:
- **Short-Form Intent**: Aliases are meant to be short alternatives
- **No Double-Prefixing**: `--app-with` defeats the purpose of aliases
- **User Control**: User explicitly chooses the alias name

### Why Conflict Detection for Field Names?

**Problem**: Same argument registered twice → argparse error.

**Context**:
```python
# If we allowed this:
@dataclass
class Config:
  packages: list[str] = field(
    metadata={"cli_aliases": ["with"]}
  )
  # And later:
  with: bool = False  # Conflict!
```

**Solution**: Detect conflicts at configuration time, not runtime.

**Rationale**:
- **Early Error**: Catch issues before `parse_args()`
- **Clear Message**: Tell user which field causes conflict
- **Prevent Silent Failures**: argparse just uses the last one defined

---

## Development Workflow

### Environment Setup

```bash
# Clone repository
git clone https://github.com/christophevg/clevis.git
cd clevis

# Create development environment (Python 3.10+)
make env-dev

# Run tests
make test

# Run all quality checks
make check
```

### Development Commands

```bash
# Run tests with coverage
make test-cov

# Format code
make format

# Run linter
make lint

# Run type checker
make typecheck

# Run all checks (format + lint + typecheck + test)
make check

# Build distribution packages
make build

# Pre-publish checks
make pre-publish
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
# Run all tests
make test

# Run specific test file
make test TEST=tests/test_parser.py

# Run specific test function
make test TEST=tests/test_parser.py::TestTomlParser::test_envtoml_has_priority

# Run with coverage report
make test-cov
# Open htmlcov/index.html in browser
```

### Code Style Conventions

- **Formatter**: Ruff (compatible with Black)
- **Line Length**: 100 characters
- **Indentation**: 2 spaces
- **Quotes**: Double quotes
- **Import Sorting**: Ruff isort

**Configuration** (in `pyproject.toml`):
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

**Run type checking**:
```bash
make typecheck
```

### PR Workflow

1. **Create Feature Branch**:
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make Changes**:
   - Follow code style conventions
   - Add tests for new functionality
   - Update documentation if needed

3. **Run Quality Checks**:
   ```bash
   make check
   ```

4. **Commit Changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature"
   ```

5. **Push and Create PR**:
   ```bash
   git push origin feature/your-feature
   # Create PR via GitHub UI
   ```

---

## Testing Guidelines

### Test Structure

Tests follow pytest conventions with clear organization:

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

### Writing Tests

**Use Fixtures for Common Setup**:
```python
@pytest.fixture
def temp_config_file():
  """Create a temporary TOML config file."""
  with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
    f.write('[database]\nhost = "localhost"\n')
    yield f.name
  os.unlink(f.name)

def test_config_loading(temp_config_file):
  """Test loading configuration from file."""
  # Use fixture
  pass
```

**Reset Global State**:
```python
def test_factory_isolation():
  """Test that factories are properly isolated."""
  from clevis import _reset_factories

  _reset_factories()  # Clean slate before test
  # ... test code ...
  _reset_factories()  # Clean up after test
```

**Test Edge Cases**:
```python
def test_list_field_append_to_toml():
  """Test that CLI list values append to TOML values."""
  # Test the append behavior, not just replacement
  pass

def test_empty_list_marker():
  """Test that --no-field creates empty list."""
  # Test the clear behavior
  pass
```

### Test Coverage Expectations

- **Target**: 80%+ coverage
- **Focus Areas**:
  - Configuration loading (`get_config`)
  - CLI argument generation (`Factory._configure_fields`)
  - TOML parser selection (`_get_toml_parser`)
  - Security validation (`_check_file_permissions`)
  - List-append merging (`_merge_list_args`)

### Common Test Patterns

**Testing CLI Arguments**:
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

**Testing Security**:
```python
def test_insecure_file_permissions():
  """Test that insecure file permissions are rejected."""
  from clevis import SecurityAction, SecurityError

  with tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as f:
    f.write('name = "test"')
    f.flush()
    os.chmod(f.name, 0o644)  # World-readable

    with pytest.raises(SecurityError):
      get_config(Config, name=f.name[:-5])  # Strip .toml
```

**Testing Dynamic Registration**:
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

---

## Common Tasks

### How to Add a New Configuration Field

1. **Add to Dataclass**:
   ```python
   @dataclass
   class Config:
     name: str = "default"
     new_field: str = "value"  # Add here
   ```

2. **Update TOML Examples** (if needed):
   ```toml
   # myapp.toml
   name = "MyApp"
   new_field = "custom"  # Add here
   ```

3. **Test**:
   ```python
   def test_new_field():
     config = get_config(Config, args=["--new-field", "custom"])
     assert config.new_field == "custom"
   ```

### How to Add a New CLI Argument Type

1. **Identify Type Handling** in `factory.py`:
   - `Factory._configure_fields()` handles argument generation
   - Current types: bool, list, scalar (int, str, float)

2. **Add Type Support**:
   ```python
   # In Factory._configure_fields()
   if concrete_type is NewType:
     # Custom argument handling
     target_parser.add_argument(...)
   ```

3. **Test**:
   ```python
   def test_new_type():
     @dataclass
     class Config:
       field: NewType = default_value

     config = get_config(Config, args=["--field", "value"])
     assert config.field == expected_value
   ```

### How to Add a New Parser

1. **Create Parser Class**:
   ```python
   class CustomParser:
     """Custom parser implementing Parser protocol."""

     def add_argument(self, *name_or_flags, **kwargs):
       # Implementation
       pass

     def parse_args(self, args=None):
       # Implementation
       return Namespace(**parsed)
   ```

2. **Use Custom Parser**:
   ```python
   custom_parser = CustomParser()
   get_factory(Config).parser = custom_parser
   config = get_config(Config)
   ```

### How to Debug Configuration Issues

**Problem**: Configuration not loading correctly.

**Debug Steps**:

1. **Check TOML Files**:
   ```bash
   # Check file permissions
   ls -la ~/.myapp.toml ./myapp.toml

   # Should be owner-only:
   # -rw------- (600)
   ```

2. **Enable Logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logger = logging.getLogger("clevis")
   ```

3. **Inspect Factory**:
   ```python
   from clevis import get_factory

   factory = get_factory(Config)
   print(f"Prefix: {factory.prefix}")
   print(f"Configured: {factory._configured}")
   ```

4. **Check Argument Names**:
   ```python
   # List expected arguments
   parser = argparse.ArgumentParser()
   get_factory(Config).parser = parser
   get_config(Config)  # Configure parser
   parser.print_help()
   ```

5. **Test Isolation**:
   ```python
   from clevis import _reset_factories

   # Reset before test to avoid cross-test contamination
   _reset_factories()
   ```

---

## Reference

### Key Files to Understand First

1. **`src/clevis/__init__.py`** - Main entry point and public API
   - `get_config()` - Core configuration loading
   - `get_cmd()` - Subcommand handling
   - Security validation

2. **`src/clevis/factory.py`** - Factory pattern implementation
   - `Factory` - Singleton factory per config class
   - `Parser` Protocol - Extensibility interface
   - CLI argument generation

3. **`src/clevis/configclass.py`** - Decorator pattern
   - `@configclass` - Convenience decorator

4. **`src/clevis/registration.py`** - Dynamic registration
   - `register_field()` - Plugin architecture support

### Where to Find Examples

- **`examples/main.py`** - Basic configuration loading
- **`examples/nested.py`** - Nested dataclasses
- **`examples/commands.py`** - CLI subcommands
- **`examples/dynamic.py`** - Dynamic field registration
- **`examples/plugin.py`** - Plugin pattern

### Related Documentation

- **README.md** - Quick start and feature overview
- **examples/README.md** - Progressive learning path
- **docs/usage.rst** - Comprehensive usage guide
- **docs/api.rst** - API reference

### External Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| `dacite` | Dict → dataclass conversion | Yes |
| `tomllib` | TOML parsing (Python 3.11+) | Yes (stdlib) |
| `tomli` | TOML parsing (Python 3.10) | Optional |
| `envtoml` | `${VAR}` interpolation | Optional |
| `tomlev` | `${VAR\|default}` syntax | Optional |

### Version Compatibility

- **Python**: 3.10, 3.11, 3.12
- **Tested**: All versions via tox
- **Type Hints**: Strict typing with mypy

---

## Summary

Clevis provides a clean, type-safe approach to configuration management with:

1. **Layered Configuration** - Merge multiple sources with clear precedence
2. **Factory Pattern** - Coordinate configuration across modules
3. **Dynamic Registration** - Enable plugin architectures
4. **Security** - Validate file permissions to protect credentials
5. **Developer Experience** - Helpful error messages and auto-generated CLI

The codebase is well-organized with clear separation of concerns:
- `__init__.py` orchestrates configuration loading
- `factory.py` manages CLI generation
- `configclass.py` provides convenience decorators
- `registration.py` enables plugin architectures

For questions or issues:
- **GitHub Issues**: https://github.com/christophevg/clevis/issues
- **Documentation**: https://clevis.readthedocs.io