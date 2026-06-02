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

### `get_config(data_class, name="project", user=True, project=True, cli=True, args=None)`

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

**Returns:** Instance of the dataclass with merged configuration

**Raises:**
- `ConfigError` — Missing required fields or wrong types
- `ImportError` — No TOML parser available

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

### Testing with Configuration

```python
import tempfile
from pathlib import Path
from clevis import get_config

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
      # cli=False disables CLI parsing, args=[] ensures no sys.argv interference
      config = get_config(Config, name="test", user=False, cli=False)
      assert config.name == "test"
      assert config.value == 42
    finally:
      os.chdir(original_dir)
```

### Library Mode (No CLI)

When embedding Clevis in a library or testing, disable CLI parsing:

```python
from clevis import get_config

# Library mode - only load from files, ignore sys.argv
config = get_config(Config, name="app", cli=False)

# Testing - combine with other parameters
config = get_config(Config, name="app", user=False, cli=False)
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