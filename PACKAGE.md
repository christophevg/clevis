# Clevis

> Configuration management for Python projects with dataclass-based schemas

## Overview

Clevis provides type-safe configuration management for Python applications. It connects multiple configuration sources — TOML files, environment variables, and CLI arguments — into a single, cohesive interface using Python dataclasses as schemas.

The library follows the principle of layered configuration with clear precedence:
1. **CLI arguments** (highest priority)
2. **Project-level TOML** (`./{name}.toml`)
3. **User-level TOML** (`~/.{name}.toml`)
4. **Dataclass defaults** (lowest priority)

## Installation

```bash
# Python 3.11+ (uses stdlib tomllib)
pip install clevis

# Python 3.10 (requires tomli)
pip install clevis[tomli]

# With environment variable support
pip install clevis[envtoml]  # ${VAR} interpolation
pip install clevis[tomlev]    # ${VAR|default} syntax
```

## Quick Start

```python
from dataclasses import dataclass
from clevis import get_config

@dataclass
class Config:
  name: str = "MyApp"
  debug: bool = False

# Load from ~/.myapp.toml and ./myapp.toml
config = get_config(Config, name="myapp")
print(config.name)  # Uses dataclass default if no TOML found
```

## Key Components

### `get_config(data_class, name="project", user=True, project=True, cli=True, args=None, security=None)`

The main entry point for loading configuration. Merges configuration from multiple sources and returns a populated dataclass instance.

```python
from dataclasses import dataclass, field
from clevis import get_config

@dataclass
class DatabaseConfig:
  host: str = "localhost"
  port: int = 5432

@dataclass
class AppConfig:
  name: str = "MyApp"
  debug: bool = False
  database: DatabaseConfig = field(default_factory=DatabaseConfig)

config = get_config(AppConfig, name="app")
```

**Parameters:**
- `data_class` — The dataclass type to populate
- `name` — Configuration file name (without `.toml` extension)
- `user` — Whether to load `~/.{name}.toml` (default: True)
- `project` — Whether to load `./{name}.toml` (default: True)
- `cli` — Whether to parse CLI arguments from `sys.argv` (default: True)
- `args` — CLI arguments (defaults to `sys.argv[1:]`)
- `security` — Security check configuration (default: reject all insecure configs)

**Returns:** Instance of the dataclass with merged configuration

**Raises:**
- `ConfigError` — Missing required fields or wrong types
- `SecurityError` — Security checks fail (when `security` action is `REJECT`)
- `ImportError` — No TOML parser available

---

### `@configclass(cmd=None, help=None, aliases=None)`

Decorator that combines `@dataclass` with factory registration. Simplifies configuration class definition and enables subcommand support.

```python
from clevis import configclass, get_factory

# Basic usage (equivalent to @dataclass + get_factory)
@configclass
class Config:
  name: str = "default"

# With subcommand support
@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig:
  verbose: bool = False
```

**Parameters:**
- `cls` — The class to decorate (when used without parentheses)
- `cmd` — Optional subcommand name for multi-command CLI applications
- `help` — Help text for the subcommand (requires `cmd` parameter)
- `aliases` — List of aliases for the subcommand (requires `cmd` parameter)

**Returns:** The decorated class (now a dataclass)

---

### `get_factory(clz)`

Get the Factory for a configuration class. Returns a singleton Factory instance for each config class.

```python
from clevis import get_factory, configclass

@configclass
class AppConfig:
  name: str = "default"

# Get factory for customization
factory = get_factory(AppConfig)
factory.prefix = "app1"  # Prefix all CLI args with --app1-

# Configure parser with custom settings
factory.parser = custom_parser
```

**Parameters:**
- `clz` — The dataclass type to get a factory for

**Returns:** Factory instance for the class (singleton pattern)

---

### `get_cmd(parser=None, args=None)`

Get the active subcommand name from parsed arguments. Used in multi-command CLI applications.

```python
from clevis import get_cmd

cmd = get_cmd()
if cmd == "check":
  # Handle check subcommand
  pass
elif cmd == "run":
  # Handle run subcommand
  pass
```

**Parameters:**
- `parser` — Optional parser to use (defaults to default parser)
- `args` — Optional list of CLI arguments (for testing)

**Returns:** The subcommand name or `None` if no subcommand was used

---

### `Factory`

Configuration factory for a dataclass. Collects parser configuration for deferred setup, allowing orchestration code to customize prefixes and parsers before configuration loading.

```python
from dataclasses import dataclass
from clevis import get_factory

@dataclass
class AppConfig:
  name: str = "default"

# Get factory and customize
factory = get_factory(AppConfig)
factory.prefix = "app1"  # CLI args become --app1-name
factory.parser = custom_parser  # Use custom parser
```

**Attributes:**
- `config_class` — The dataclass type this factory configures
- `prefix` — Optional CLI argument prefix (e.g., "app1" → "--app1-name")
- `parser` — The argparse-compatible parser to use
- `cmd` — Optional subcommand name for multi-command CLIs
- `help` — Help text for subcommand (used with `cmd` parameter)
- `aliases` — List of aliases for subcommand (used with `cmd` parameter)

**Methods:**
- `configure_parser()` — Configure the parser with arguments (called automatically)
- `get_args(args=None)` — Parse CLI arguments and return as dictionary
- `list_fields(clz=None, path=None)` — Recursively list all fields in nested dataclasses

---

### `SecurityAction`

Enum defining actions for security checks on configuration files.

```python
from clevis import SecurityAction, get_config, SecurityConfig

# Don't check permissions (useful for testing)
config = get_config(Config, name="app", security={"file_permissions": SecurityAction.DONT_CHECK})

# Log warnings for insecure permissions
config = get_config(Config, name="app", security={"file_permissions": SecurityAction.LOG})

# Reject insecure configs (default behavior)
config = get_config(Config, name="app", security={"file_permissions": SecurityAction.REJECT})
```

**Values:**
- `DONT_CHECK` — Skip security checks entirely
- `LOG` — Log warnings for insecure permissions but continue
- `REJECT` — Raise `SecurityError` for insecure configurations (default)

---

### `SecurityConfig`

TypedDict for configuring security behavior.

```python
from clevis import SecurityConfig, SecurityAction

security: SecurityConfig = {
  "file_permissions": SecurityAction.LOG,          # Check file permissions
  "directory_permissions": SecurityAction.REJECT,  # Check directory permissions
}

config = get_config(Config, name="app", security=security)
```

**Fields:**
- `file_permissions` — Action for file permission checks (default: `REJECT`)
- `directory_permissions` — Action for directory permission checks (default: `REJECT`)

---

### `SecurityError`

Exception raised when security checks fail with `REJECT` action.

```python
from clevis import SecurityError, get_config, SecurityAction

try:
  config = get_config(Config, name="app", security={"file_permissions": SecurityAction.REJECT})
except SecurityError as e:
  print(f"Security issue: {e}")
  print(f"Path: {e.path}")
  print(f"Check: {e.check}")
```

**Attributes:**
- `path` — Path to the problematic file or directory
- `check` — Type of check that failed (`"file_permissions"` or `"directory_permissions"`)

---

### `ConfigError`

Exception raised when configuration is missing or invalid. Provides helpful, actionable error messages with suggestions for how to fix the issue.

```python
from clevis import get_config, ConfigError

@dataclass
class Config:
  required_field: str  # No default = required

try:
  config = get_config(Config, name="app")
except ConfigError as e:
  print(e.field_path)  # "required_field"
  print(e.message)     # "Required field has no value"
  # Error message includes suggestions for fixing
```

**Attributes:**
- `field_path` — Dotted path to the problematic field
- `message` — Human-readable description of the issue
- `config_name` — Name of the configuration file

---

### `list_fields(clz, path=None)`

Recursively flatten all fields in nested dataclasses. Useful for introspection and building custom CLI parsers.

```python
from dataclasses import dataclass, field
from clevis import list_fields

@dataclass
class Database:
  host: str
  port: int

@dataclass
class Config:
  name: str
  database: Database = field(default_factory=Database)

fields_list = list_fields(Config)
# Returns: [(Field('name'), []), (Field('host'), ['database']), (Field('port'), ['database'])]
```

---

### `unpack_type(type_def)`

Extract the non-None type from `Optional[T]` or `T | None`. Used internally for type handling.

```python
from clevis import unpack_type

assert unpack_type(str | None) == str
assert unpack_type(int | None) == int
assert unpack_type(bool) == bool  # Non-union types returned as-is
```

---

### `get_args_config(clz, args=None)`

Generate an argparse parser from a dataclass hierarchy. Creates CLI arguments using dashed notation for nested fields.

```python
from clevis import get_args_config

# Returns dict with dotted keys: {"database.host": "localhost", "database.port": 5432}
args = get_args_config(Config, args=["--database-host", "localhost"])
```

---

### `apply_to_dict(args, dct)`

Apply dotted command line arguments to a nested dictionary. Modifies in-place.

```python
from clevis import apply_to_dict

args = {"database.host": "localhost", "database.port": 5432}
dct = {}
apply_to_dict(args, dct)
# dct = {"database": {"host": "localhost", "port": 5432}}
```

## Common Patterns

### Nested Configuration

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

config = get_config(AppConfig, name="app")
```

TOML file (`app.toml`):
```toml
name = "Production App"
debug = true

[database]
host = "db.example.com"
port = 5432
```

### Environment Variables

Install with envtoml or tomlev for `${VAR}` interpolation:

```bash
pip install clevis[envtoml]
```

TOML file:
```toml
[database]
password = "${DB_PASSWORD}"
host = "${DB_HOST|localhost}"  # tomlev only (with default)
```

### CLI Arguments

Nested dataclasses become dashed arguments:

```bash
python app.py --database-host localhost --database-port 5432 --debug
```

Boolean fields use `--flag` (store_true):

```bash
python app.py --debug  # Sets debug=True
```

### Factory Pattern for Multi-Module Apps

When building multi-module applications where different modules use different configuration prefixes, use the Factory pattern to customize parser behavior:

```python
from dataclasses import dataclass
from clevis import configclass, get_config, get_factory

# Define configuration classes
@configclass
class DatabaseConfig:
  host: str = "localhost"
  port: int = 5432

@configclass
class AppConfig:
  name: str = "MyApp"
  version: str = "1.0.0"

# Get factories for customization
db_factory = get_factory(DatabaseConfig)
db_factory.prefix = "db"  # CLI args: --db-host, --db-port

app_factory = get_factory(AppConfig)
app_factory.prefix = "app"  # CLI args: --app-name, --app-version

# Load configurations with custom prefixes
db_config = get_config(DatabaseConfig, name="database")
app_config = get_config(AppConfig, name="app")
```

Usage:
```bash
python app.py --db-host db.example.com --app-name MyApp --debug
```

### CLI Subcommands

For CLI applications with multiple commands, use `@configclass` with the `cmd` parameter:

```python
import argparse
from clevis import configclass, get_config, get_cmd

# Define subcommand configurations
@configclass(cmd="run", help="Run the application", aliases=["r"])
class RunConfig:
  port: int = 8080
  workers: int = 4

@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig:
  verbose: bool = False

# Parse and dispatch
cmd = get_cmd()
if cmd == "run":
  config = get_config(RunConfig, name="app")
  print(f"Running on port {config.port} with {config.workers} workers")
elif cmd == "check":
  config = get_config(CheckConfig, name="app")
  print(f"Checking... (verbose={config.verbose})")
```

Usage:
```bash
python app.py run --port 3000 --workers 2
python app.py check --verbose
python app.py c --verbose  # Using alias
```

### Security Configuration

By default, Clevis performs security checks on configuration files:

- **File permissions**: Ensures files are not readable by group/other
- **Directory permissions**: Ensures parent directories are not world-writable

Control security behavior with the `security` parameter:

```python
from clevis import SecurityAction, SecurityConfig, get_config

# Default: reject insecure configs
config = get_config(Config, name="app")  # Raises SecurityError if insecure

# Log warnings but continue
config = get_config(Config, name="app", security={
  "file_permissions": SecurityAction.LOG,
  "directory_permissions": SecurityAction.LOG,
})

# Skip all security checks (development/testing only)
config = get_config(Config, name="app", security={
  "file_permissions": SecurityAction.DONT_CHECK,
  "directory_permissions": SecurityAction.DONT_CHECK,
})
```

**Security recommendations:**
- Use `REJECT` (default) for production
- Use `LOG` for development to be notified of issues
- Use `DONT_CHECK` only in controlled test environments

### Testing with Configuration

```python
import tempfile
from pathlib import Path
from clevis import get_config, SecurityAction

def test_with_config():
  with tempfile.TemporaryDirectory() as tmpdir:
    config_file = Path(tmpdir) / "test.toml"
    config_file.write_text('name = "test"\nvalue = 42\n')

    @dataclass
    class Config:
      name: str = "default"
      value: int = 0

    import os
    original_dir = os.getcwd()
    try:
      os.chdir(tmpdir)
      # Disable CLI parsing and security checks for clean test isolation
      config = get_config(
        Config,
        name="test",
        user=False,
        cli=False,
        security={"file_permissions": SecurityAction.DONT_CHECK}
      )
      assert config.name == "test"
      assert config.value == 42
    finally:
      os.chdir(original_dir)
```

### Library Mode (No CLI)

When embedding Clevis in a library or testing, disable CLI parsing:

```python
from clevis import get_config, SecurityAction

# Library mode - only load from files, ignore sys.argv
config = get_config(Config, name="app", cli=False)

# Testing - combine with other parameters
config = get_config(
  Config,
  name="app",
  user=False,
  cli=False,
  security={"file_permissions": SecurityAction.DONT_CHECK}
)
```

## TOML Parser Selection

Clevis automatically selects the best available TOML parser:

| Priority | Parser | Features | Install |
|----------|--------|----------|---------|
| 1 | envtoml | `${VAR}` interpolation | `pip install clevis[envtoml]` |
| 2 | tomlev | `${VAR\|default}` syntax | `pip install clevis[tomlev]` |
| 3 | tomli | Pure Python TOML | `pip install clevis[tomli]` |
| 4 | tomllib | Python 3.11+ stdlib | No extras needed |

## Dependencies

**Required:**
- `dacite` — Dictionary to dataclass conversion

**Optional (extras):**
- `tomli` — Pure Python TOML parser (Python 3.10)
- `envtoml` — Environment variable interpolation
- `tomlev` — Environment variables with defaults

## Version Notes

### 0.3.0

**New Features:**
- **Factory Pattern**: New `Factory` class and `configclass` decorator for multi-module configuration orchestration
  - `get_factory(clz)` returns singleton Factory for each config class
  - `@configclass` decorator combines `@dataclass` with factory registration
  - Support for custom CLI argument prefixes
  - Custom parser support
- **Subcommands**: CLI applications with multiple commands
  - `@configclass(cmd="name")` for subcommand registration
  - `help` and `aliases` parameters for subcommand documentation
  - `get_cmd()` function to retrieve active subcommand
- **Security Checks**: File and directory permission validation
  - `SecurityAction` enum: `DONT_CHECK`, `LOG`, `REJECT`
  - `SecurityConfig` typed dict for security configuration
  - `SecurityError` exception for rejected configs
  - TOCTOU-safe file permission checks using file descriptors
- **Type Stubs**: Added `py.typed` marker and type stub files for IDE support

**Improvements:**
- Better error messages maintain formatting after factory pattern changes

### 0.2.0

**New Features:**
- `cli` parameter in `get_config()` - Control CLI argument parsing
  - Set `cli=False` to disable CLI parsing (library mode, testing)
  - Default `cli=True` preserves backward compatibility

**Improvements:**
- Better error messages when `cli=False` - omits CLI-related suggestions
- Cleaner test setup without CLI interference

### 0.1.0

First public release. Core functionality includes:
- Dataclass-based configuration schemas
- TOML file loading with parser fallback
- Layered configuration (user < project < CLI)
- CLI argument generation from dataclass
- Helpful error messages for missing fields

## Migration Guides

### From 0.2.x to 0.3.x

No breaking changes. The new features are additive and backward compatible.

**New Optional Behavior:**

**Security Checks (v0.3.0+):**
Security checks are now enabled by default. If your configuration files have permissive permissions, you may see `SecurityError`:

```python
# Before (0.2.x) - No security checks
config = get_config(Config, name="app")

# After (0.3.x) - Security checks enabled by default
# Option 1: Fix file permissions
#   chmod 600 ~/.myapp.toml
#   chmod 700 ~/.  # If needed

# Option 2: Disable security checks (development only)
from clevis import SecurityAction
config = get_config(Config, name="app", security={
  "file_permissions": SecurityAction.DONT_CHECK,
  "directory_permissions": SecurityAction.DONT_CHECK,
})
```

**Factory Pattern (v0.3.0+):**
For multi-module applications, use the new factory pattern:

```python
# Before (0.2.x) - No way to customize parser or prefix
config = get_config(Config, name="app")

# After (0.3.x) - Use factory for customization
from clevis import get_factory

factory = get_factory(Config)
factory.prefix = "module1"  # --module1-name instead of --name
config = get_config(Config, name="app")
```

**Subcommands (v0.3.0+):**
New decorator simplifies subcommand configuration:

```python
# Before (0.2.x) - Manual argparse setup required
# After (0.3.x) - Use @configclass decorator
from clevis import configclass, get_cmd

@configclass(cmd="run", help="Run application", aliases=["r"])
class RunConfig:
  port: int = 8080

cmd = get_cmd()
if cmd == "run":
  config = get_config(RunConfig, name="app")
```

### From 0.1.x to 0.2.x

No breaking changes. The new `cli` parameter is optional with default `True`.

**New Optional Behavior:**

If using Clevis in a library or test context where CLI parsing is not desired:

```python
# Before (0.1.x) - CLI parsing always happened
config = get_config(Config, name="app")

# After (0.2.x) - Disable CLI parsing when needed
config = get_config(Config, name="app", cli=False)  # Library mode
config = get_config(Config, name="app", cli=False, args=[])  # Testing
```

**Error Messages:**

When `cli=False`, error messages no longer suggest CLI arguments (e.g., "try --database-host") since CLI is disabled.

## References

- **PyPI**: https://pypi.org/project/clevis/
- **Documentation**: https://clevis.readthedocs.io
- **Repository**: https://github.com/christophevg/clevis
- **License**: MIT