# Clevis

> Configuration management for Python projects with dataclass-based schemas

## Overview

Clevis provides type-safe configuration management for Python applications. It connects multiple configuration sources — TOML files, environment variables, and CLI arguments — into a single, cohesive interface using Python dataclasses as schemas.

Configuration precedence (highest to lowest): CLI arguments → Project TOML → User TOML → Dataclass defaults

## Installation

```bash
pip install clevis                        # Python 3.11+ (stdlib tomllib)
pip install clevis[tomli]                # Python 3.10
pip install clevis[envtoml]              # ${VAR} interpolation
pip install clevis[tomlev]               # ${VAR|default} syntax
```

## Quick Start

```python
from dataclasses import dataclass
from clevis import get_config

@dataclass
class Config:
  name: str = "MyApp"
  debug: bool = False

config = get_config(Config, name="myapp")
print(config.name)
```

## Key Components

### `get_config(data_class, name="project", user=True, project=True, cli=True, args=None, security=None, cascade=None)`

Load configuration from TOML files and CLI arguments.

**Parameters:**
- `data_class` — The dataclass type to populate
- `name` — Configuration file name (without `.toml` extension)
- `user` — Load `~/.{name}.toml` (default: True)
- `project` — Load `./{name}.toml` (default: True)
- `cli` — Parse CLI arguments from `sys.argv` (default: True)
- `args` — CLI arguments (defaults to `sys.argv[1:]`)
- `security` — Security check configuration (default: reject all insecure configs)
- `cascade` — List of ConfigProvider instances replacing default middle layers (default: None). When provided, `user`/`project` and `security` are ignored.

**Returns:** Instance of the dataclass with merged configuration

**Raises:** `ConfigError`, `SecurityError`, `ImportError`

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
  database: DatabaseConfig = field(default_factory=DatabaseConfig)

config = get_config(AppConfig, name="app")
```

---

### `@configclass(cmd=None, help=None, aliases=None, config=None, default_cmd=False)`

Decorator that combines `@dataclass` with factory registration.

**Parameters:**
- `cls` — The class to decorate
- `cmd` — Subcommand name (for multi-command CLIs)
- `help` — Help text for subcommand
- `aliases` — List of aliases for subcommand
- `config` — TOML section name (defaults to `cmd` value)
- `default_cmd` — If True, this subcommand runs when no subcommand is given (requires `cmd`, default: False)

```python
from clevis import configclass

# Basic usage
@configclass
class Config:
  name: str = "default"

# Subcommand support
@configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
class CheckConfig:
  verbose: bool = False

# TOML section override
@configclass(cmd="cli", config="client", help="Run CLI client")
class CliConfig:
  server_url: str = "http://localhost:8000"
```

---

### `get_factory(clz)`

Get the Factory for a configuration class (singleton pattern).

```python
from clevis import get_factory

@configclass
class AppConfig:
  name: str = "default"

factory = get_factory(AppConfig)
factory.prefix = "app1"  # CLI args become --app1-name
```

---

### `get_cmd(parser=None, args=None)`

Get active subcommand name from parsed arguments.

**Returns:** Subcommand name or `None`

```python
from clevis import get_cmd

cmd = get_cmd()
if cmd == "check":
  # Handle check subcommand
  pass
```

---

### `register_field(parent_class, field_name, field_type)`

Register a field to a dataclass at runtime (for plugin architectures).

**Parameters:**
- `parent_class` — Parent dataclass to extend (must NOT be frozen)
- `field_name` — Name of field to add
- `field_type` — Dataclass type for the field

**Raises:** `TypeError` (frozen), `ValueError` (field exists), `RuntimeError` (after CLI config)

```python
from dataclasses import dataclass
from clevis import register_field

@dataclass
class ParentConfig:
  name: str = "default"

@dataclass
class PluginConfig:
  enabled: bool = True

register_field(ParentConfig, "plugin", PluginConfig)

config = ParentConfig()
print(config.plugin.enabled)  # True
```

---

### `SecurityAction`

Enum for security check actions: `DONT_CHECK`, `LOG`, `REJECT` (default)

```python
from clevis import SecurityAction, get_config

config = get_config(Config, name="app", security={
  "file_permissions": SecurityAction.LOG
})
```

---

### `SecurityConfig`

TypedDict with fields: `file_permissions`, `directory_permissions` (both default: `REJECT`)

---

### `SecurityError`

Raised when security checks fail with `REJECT`. Attributes: `path`, `check`

---

### `ConfigError`

Raised for missing/invalid configuration. Attributes: `field_path`, `message`, `config_name`

---

### `Factory`

Configuration factory for a dataclass.

**Attributes:**
- `config_class`, `prefix`, `parser`, `cmd`, `help`, `aliases`, `config`, `default_cmd`

**Methods:**
- `configure_parser()` — Configure parser (automatic)
- `get_args(args=None)` — Parse CLI args, return dict
- `list_fields(clz=None, path=None)` — List nested fields

---

### `list_fields(clz, path=None)`

Recursively flatten fields in nested dataclasses.

```python
from clevis import list_fields

fields_list = list_fields(Config)
# [(Field('name'), []), (Field('host'), ['database'])]
```

---

### `unpack_type(type_def)`

Extract non-None type from `Optional[T]` or `T | None`.

---

### `get_args_config(clz, args=None)`

Generate argparse parser from dataclass. Returns dict with dotted keys.

---

### `apply_to_dict(args, dct)`

Apply dotted CLI arguments to nested dictionary (in-place).

---

### `ConfigProvider`

Protocol — zero-argument callable returning `dict[str, Any]`. Any function,
lambda, or class with `__call__` satisfies it. Each provider owns its security.

---

### `UserConfigProvider(name, security=None)`

ConfigProvider that loads `~/.{name}.toml` with TOCTOU-safe security checks.

---

### `ProjectConfigProvider(name, security=None)`

ConfigProvider that loads `./{name}.toml` with TOCTOU-safe security checks.

---

### `FileConfigProvider(name, security=None)`

Subclassable base for file-based TOML providers. Override `_root_dir()` and
`_path_template` to load from custom paths with automatic security checks.

---

### `DEFAULT_CASCADE`

Tuple of default provider classes: `(UserConfigProvider, ProjectConfigProvider)`.

---

### `build_default_cascade(name, security=None, user=True, project=True)`

Build a list of default ConfigProvider instances, filtered by user/project flags.

---

### `deep_merge(base, overlay)`

Recursively merge overlay onto base, returning a new dict. Nested dicts merge
key-by-key; all other types are replaced. Inputs are not modified.

---

### `load(fp)` / `loads(s)`

Raw TOML parsers (no security checks). Drop-in for `tomllib.load`/`tomllib.loads`.
`load_toml`/`loads_toml` are descriptive aliases.

---

### `load_toml_file(path, security=None)`

Securely load a TOML file with default security checks (TOCTOU-safe).

---

### `check_file_permissions(path, action)`

TOCTOU-safe file permission check. Returns `(check_passed, file_descriptor)`.

---

### `check_directory_permissions(path, action)`

Check if parent directory is world-writable. Returns bool.

---

### `load_toml_from_fd(fd)`

Load TOML from a file descriptor. File object takes ownership of the fd.

## Common Patterns

### Using @configclass

```python
from clevis import configclass, get_config

@configclass
class AppConfig:
  name: str = "default"
  debug: bool = False

config = get_config(AppConfig, name="app")
```

### Nested Configuration

```python
from dataclasses import dataclass, field

@dataclass
class DatabaseConfig:
  host: str = "localhost"
  port: int = 5432

@dataclass
class AppConfig:
  name: str = "MyApp"
  database: DatabaseConfig = field(default_factory=DatabaseConfig)

config = get_config(AppConfig, name="app")
```

TOML: `[database] host = "db.example.com"`

### Environment Variables

```bash
pip install clevis[envtoml]
```

TOML: `password = "${DB_PASSWORD}"`

### CLI Arguments

Nested fields use dashes: `--database-host localhost`

- Boolean: `--debug` (True), `--no-debug` (False)
- Lists: `--packages pkg1 --packages pkg2` (append), `--no-packages` (clear)

### Factory Pattern for Multi-Module Apps

```python
from clevis import configclass, get_config, get_factory

@configclass
class DatabaseConfig:
  host: str = "localhost"

@configclass
class AppConfig:
  name: str = "MyApp"

get_factory(DatabaseConfig).prefix = "db"
get_factory(AppConfig).prefix = "app"

db_config = get_config(DatabaseConfig, name="database")
app_config = get_config(AppConfig, name="app")
```

### CLI Subcommands

```python
from clevis import configclass, get_config, get_cmd

@configclass(cmd="run", help="Run the app", aliases=["r"])
class RunConfig:
  port: int = 8080

@configclass(cmd="check", help="Run diagnostics")
class CheckConfig:
  verbose: bool = False

cmd = get_cmd()
if cmd == "run":
  config = get_config(RunConfig, name="app")
elif cmd == "check":
  config = get_config(CheckConfig, name="app")
```

### Default Subcommand

Run a subcommand automatically when no subcommand is specified:

```python
from clevis import configclass, get_cmd, get_config

@configclass(cmd="check", default_cmd=True, help="Run diagnostics")
class CheckConfig:
  verbose: bool = False

# No subcommand specified → runs "check" automatically
cmd = get_cmd()
# cmd == "check" even when called with just --verbose (no subcommand)

config = get_config(CheckConfig, name="app")
print(config.verbose)
```

`default_cmd` requires `cmd` to be set. Multiple `default_cmd=True` raises an error.

### Dynamic Field Registration

Add fields at runtime for plugin architectures:

```python
from dataclasses import dataclass
from clevis import register_field, get_config

@dataclass
class ToolsConfig:
  """Container for tool configurations."""
  list: str = "default"

@dataclass
class PkgqToolConfig:
  """Plugin config."""
  enabled: bool = True
  timeout: int = 30

# Register plugin field
register_field(ToolsConfig, "pkgq", PkgqToolConfig)

# Works with TOML
config = get_config(ToolsConfig, name="tools")
```

TOML: `[tools.pkgq] enabled = true`

CLI: `--tools-pkgq-timeout 90`

**Plugin pattern:**
```python
# Plugin module registers itself
def load_plugins():
  register_field(ToolsConfig, "pkgq", PkgqToolConfig)

# Application loads before config
load_plugins()
config = get_config(ToolsConfig, name="tools")
```

**Best practices:**
1. Parent config: `@dataclass` (NOT `frozen=True`)
2. Call `register_field()` before `get_config()`
3. TOML: `[parent.field]`, CLI: `--parent-field-option`

### Subcommands with TOML Override

Read from different TOML section than command name:

```python
from dataclasses import dataclass
from clevis import configclass

@dataclass
class ClientConfig:
  server_url: str = "http://localhost:8000"

@configclass(cmd="cli", config="client", help="Run CLI client")
class CliConfig(ClientConfig):
  pass

@configclass(cmd="tui", config="client", help="Run TUI client")
class TUIConfig(ClientConfig):
  pass
```

Both commands read from `[client]` section.

**Use cases:** Multiple interfaces with shared config, environment-specific config.

### Security Configuration

Default: reject insecure configs.

```python
from clevis import SecurityAction, get_config

# Development: log warnings
config = get_config(Config, name="app", security={
  "file_permissions": SecurityAction.LOG
})

# Testing: skip checks
config = get_config(Config, name="app", security={
  "file_permissions": SecurityAction.DONT_CHECK
})
```

| Environment | Action |
|------------|--------|
| Production | `REJECT` (default) |
| Development | `LOG` |
| Testing | `DONT_CHECK` |

### Config Override Cascade

The middle configuration layer (between dataclass defaults and CLI arguments) is
built from a cascade of ConfigProvider instances. The default cascade loads user
TOML then project TOML. Customize it to inject config from any source.

**ConfigProvider Protocol:** Any zero-argument callable returning `dict[str, Any]`.
A plain function, lambda, or class with `__call__` all work.

```python
from clevis import build_default_cascade, get_config

def env_provider() -> dict:
  import os
  return {"api_key": os.environ.get("API_KEY", "")}

# Append to default cascade
cascade = build_default_cascade("myapp") + [env_provider]
config = get_config(Config, name="myapp", cascade=cascade)
```

**Fully custom cascade:**

```python
from clevis import UserConfigProvider, ProjectConfigProvider, get_config

class MyProvider:
  def __call__(self) -> dict:
    return {"feature_flag": True}

cascade = [
  UserConfigProvider("myapp"),
  MyProvider(),
  ProjectConfigProvider("myapp"),
]
config = get_config(Config, name="myapp", cascade=cascade)
```

When `cascade` is provided, `user`/`project` flags and `security` are ignored.
Each provider owns its own security checks.

**Deep merge:** Providers are merged with deep recursive merge — nested dicts
combine key-by-key rather than being replaced wholesale. List values are replaced
(not appended) in the cascade; only CLI args append to lists.

**Public TOML API:**

```python
from clevis import load, loads, load_toml_file

# Raw parsers (no security checks) — drop-in for tomllib
config = loads('name = "MyApp"')

# Secure file loader (TOCTOU-safe, REJECT by default)
config = load_toml_file(Path("/path/to/config.toml"))
```

**Security helpers for custom providers:**

```python
from clevis import (
  check_file_permissions, check_directory_permissions,
  load_toml_from_fd, FileConfigProvider, SecurityAction
)
from pathlib import Path

# Use exported security functions directly
class CustomFileProvider:
  def __init__(self, path: Path):
    self._path = path

  def __call__(self) -> dict:
    check_directory_permissions(self._path, SecurityAction.REJECT)
    _, fd = check_file_permissions(self._path, SecurityAction.REJECT)
    if fd is None:
      return {}
    return load_toml_from_fd(fd)

# Or subclass FileConfigProvider for automatic security checks
class CustomPathProvider(FileConfigProvider):
  _path_template = "{name}.toml"

  def __init__(self, base_dir: Path, name: str, **kwargs):
    self._base_dir = base_dir
    super().__init__(name, **kwargs)

  def _root_dir(self) -> Path:
    return self._base_dir
```

**Breaking change (v0.7.0):** Shallow `dict.update` → deep recursive merge for
config cascade. Nested tables now merge key-by-key. A project TOML `[database]`
section adds to (not replaces) the user TOML `[database]` section.

### Testing

```python
import tempfile
from pathlib import Path
from clevis import get_config, SecurityAction

def test_config():
  with tempfile.TemporaryDirectory() as tmpdir:
    config_file = Path(tmpdir) / "test.toml"
    config_file.write_text('name = "test"')

    import os
    original_dir = os.getcwd()
    try:
      os.chdir(tmpdir)
      config = get_config(
        Config,
        name="test",
        user=False,
        cli=False,
        security={"file_permissions": SecurityAction.DONT_CHECK}
      )
      assert config.name == "test"
    finally:
      os.chdir(original_dir)
```

### Library Mode

```python
from clevis import get_config

# Library mode - skip CLI parsing
config = get_config(Config, name="app", cli=False)
```

## Logging

Clevis uses Python's standard library logging. The module-level logger is named `clevis`.

### Library Usage

Configure logging to see Clevis warnings and debug messages:

```python
import logging

# Enable Clevis logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("clevis")
logger.setLevel(logging.DEBUG)  # For verbose output
```

### Logged Events

| Event | Level | Module | Description |
|-------|-------|--------|-------------|
| Security warning | WARNING | clevis | File readable by group/other |
| Security warning | WARNING | clevis | Directory world-writable |
| Type mismatch | WARNING | clevis | Expected list, got other type |
| Unused decorator param | WARNING | configclass | help/aliases without cmd |

### Custom Handler Example

```python
import logging

# Custom handler for Clevis messages
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

logger = logging.getLogger("clevis")
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
```

### Suppressing Warnings

For production with permissive file permissions:

```python
logging.getLogger("clevis").setLevel(logging.ERROR)
```

## TOML Parser Selection

Auto-selection: envtoml → tomlev → tomli → tomllib (stdlib 3.11+)

## Dependencies

Required: `dacite`

Optional: `tomli` (Python 3.10), `envtoml` (env vars), `tomlev` (env vars with defaults)

## References

- PyPI: https://pypi.org/project/clevis/
- Docs: https://clevis.readthedocs.io
- Repo: https://github.com/christophevg/clevis
- License: MIT