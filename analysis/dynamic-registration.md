# Dynamic Field Registration - Architecture & Implementation

## Executive Summary

This document describes the addition of dynamic field registration to Clevis, enabling plugin architectures to inject configuration fields at runtime. The implementation preserves 100% backward compatibility with existing code.

---

## Motivation

### Use Case: Plugin Configuration

Applications like Yoker need to inject plugin configurations into specific sections of their config hierarchy:

```toml
# yoker.toml
[tools.list]
max_depth = 5

[tools.pkgq]  # Plugin tool config - added at runtime
enabled = true
cache_directory = "/custom/cache"

[agents.default]
max_recursion_depth = 3

[agents.pkgq]  # Plugin agent config - added at runtime
max_results = 20
```

Before this feature, frozen dataclasses (`ToolsConfig`) couldn't add fields (`pkgq`) at runtime.

---

## Compatibility Analysis

### Existing Projects

| Project | Clevis Features Used | Compatibility |
|---------|---------------------|---------------|
| **Baseweb** | `@configclass(cmd)`, `get_config()`, `get_cmd()`, nested dataclasses | ✅ Compatible |
| **Roomz** | `@configclass(cmd, config)`, `get_config()`, `get_cmd()`, nested dataclasses | ✅ Compatible |
| **Yoker** | `get_config()`, nested frozen dataclasses, `SecurityAction` | ✅ Compatible |

### Breaking Changes

**None.** All existing code works unchanged.

### Deprecation

- `config` parameter now requires `cmd` parameter
- This was already the only documented use case (roomz uses it this way)
- No existing code uses `config` without `cmd`

---

## Feature Set Summary

### 1. Basic Configuration
```python
@dataclass
class Config:
    name: str = "default"
    debug: bool = False

config = get_config(Config, name="myapp")
# TOML: name = "MyApp"
# CLI: --name "MyApp" --debug
```

### 2. Nested Configuration
```python
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432

@dataclass
class Config:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

config = get_config(Config, name="myapp")
# TOML: [database]\nhost = "db.example.com"
# CLI: --database-host "db.example.com"
```

### 3. Dynamic Field Registration (NEW)
```python
# Parent config (NOT frozen)
@dataclass
class ToolsConfig:
    list: ListToolConfig = field(default_factory=ListToolConfig)
    read: ReadToolConfig = field(default_factory=ReadToolConfig)

# Plugin config
@dataclass
class PkgqToolConfig:
    enabled: bool = True
    cache_directory: str = "~/.cache/pkgq"

# Register at runtime
register_field(ToolsConfig, "pkgq", PkgqToolConfig)

# TOML: [tools.pkgq]\nenabled = true
# CLI: --tools-pkgq-enabled
```

### 4. Subcommands
```python
@configclass(cmd="check", help="Run diagnostics")
class CheckConfig:
    verbose: bool = False

@configclass(cmd="print", help="Print configuration")
class PrintConfig:
    output: str = "text"

cmd = get_cmd()
if cmd == "check":
    config = get_config(CheckConfig, name="myapp")
# CLI: myapp check --verbose
# TOML: [check]\nverbose = true
# Behavior: Isolation - [check] section becomes entire CheckConfig
```

### 5. Subcommands with TOML Override
```python
@configclass(cmd="cli", help="Run TUI chat client", config="client")
class CliConfig(ClientConfig):
    pass

# CLI: myapp cli --server-url
# TOML: [client]  (not [cli])
# Behavior: Isolation - [client] section becomes entire CliConfig
```

### 6. Multi-Module Aggregation
```python
@configclass
class App1Config:
    name: str = "default"

@configclass
class App2Config:
    name: str = "default"

get_factory(App1Config).prefix = "app1"
get_factory(App2Config).prefix = "app2"

parser = argparse.ArgumentParser()
get_factory(App1Config).parser = parser
get_factory(App2Config).parser = parser

config1 = get_config(App1Config, name="app1")  # loads app1.toml
config2 = get_config(App2Config)              # loads project.toml
# CLI: --app1-name X --app2-name Y
# Behavior: Separate configs, shared parser, prefixed CLI args
```

---

## API Reference

### `register_field()`

```python
def register_field(
    parent: type,
    name: str,
    field_type: type,
    default_factory: Callable[[], Any] | None = None,
) -> None:
    """
    Add a field to a parent config class at runtime.
    
    Modifies the parent class in-place. The parent must be a non-frozen dataclass.
    Namespace for TOML/CLI is automatically derived from parent hierarchy.
    
    Args:
        parent: Parent config class to extend (e.g., ToolsConfig)
        name: Field name to add (e.g., "pkgq")
        field_type: Config class for this field (e.g., PkgqToolConfig)
        default_factory: Optional factory (defaults to field_type)
    
    Example:
        @dataclass  # Must NOT be frozen
        class ToolsConfig:
            list: ListToolConfig = field(default_factory=ListToolConfig)
        
        @dataclass
        class PkgqToolConfig:
            enabled: bool = True
        
        register_field(ToolsConfig, "pkgq", PkgqToolConfig)
        
        # Result:
        # - ToolsConfig.pkgq field added
        # - TOML: [tools.pkgq] → config.tools.pkgq
        # - CLI: --tools-pkgq-enabled
    
    Raises:
        TypeError: If parent is a frozen dataclass
        ValueError: If field name already exists
        RuntimeError: If called after get_config() (parser already configured)
    """
```

### `@configclass` Decorator

```python
@configclass(
    cls: type | None = None,
    cmd: str | None = None,      # Subcommand name (creates subparser)
    help: str | None = None,      # Help text for subcommand
    aliases: list[str] | None = None,  # Aliases for subcommand
    config: str | None = None,    # TOML section override (requires cmd)
) -> type | Callable[[type], type]:
    """
    Decorator that applies @dataclass and registers with Clevis factory.
    
    Parameters:
        cmd: Subcommand name for CLI applications
        help: Help text for subcommand (requires cmd)
        aliases: List of aliases for subcommand (requires cmd)
        config: TOML section override (requires cmd)
    
    Valid combinations:
        @configclass                          # Basic registration
        @configclass(cmd="check")              # Subcommand
        @configclass(cmd="check", help="...")  # Subcommand with help
        @configclass(cmd="cli", config="client")  # Subcommand with TOML override
    
    Invalid combinations:
        @configclass(config="output")  # Error: config requires cmd
    """
```

### `get_config()` (Unchanged)

```python
def get_config(
    clz: type[T],
    name: str = "project",
    user: bool = True,
    project: bool = True,
    cli: bool = True,
    args: list[str] | None = None,
    security: SecurityConfig | None = None,
) -> T:
    """Load configuration from TOML files and CLI arguments."""
```

---

## Implementation Details

### TOML Namespace Derivation

Namespaces are derived automatically from the dataclass hierarchy:

```python
Config
  └── tools: ToolsConfig
        ├── list: ListToolConfig      → [tools.list]
        ├── read: ReadToolConfig      → [tools.read]
        └── pkgq: PkgqToolConfig      → [tools.pkgq]  (added via register_field)
```

No explicit namespace parameter is needed.

### Field Registration Process

1. **Validation**: Check parent is not frozen, field name doesn't exist
2. **Field Creation**: Create new `dataclasses.field()` with default factory
3. **Class Modification**: Add field to parent's `__dataclass_fields__`
4. **Annotation Update**: Add field type to parent's `__annotations__`
5. **Factory Update**: Refresh factory's field list for CLI arg generation

### Error Cases

| Error | Condition | Solution |
|-------|-----------|----------|
| `TypeError` | Parent is frozen | Remove `frozen=True` from parent |
| `ValueError` | Field name exists | Choose different field name |
| `RuntimeError` | Called after `get_config()` | Call before any `get_config()` |

---

## Migration Guide

### For Plugin Developers

**Before** (no way to add fields):
```python
@dataclass(frozen=True)
class ToolsConfig:
    list: ListToolConfig = field(default_factory=ListToolConfig)
    # Cannot add pkgq at runtime
```

**After**:
```python
# Main application (NOT frozen)
@dataclass
class ToolsConfig:
    list: ListToolConfig = field(default_factory=ListToolConfig)

# Plugin module
@dataclass
class PkgqToolConfig:
    enabled: bool = True

# Plugin loader
register_field(ToolsConfig, "pkgq", PkgqToolConfig)
```

### For Frozen Dataclass Users

If you currently use `@dataclass(frozen=True)` and need dynamic registration:

**Option 1: Remove frozen**
```python
# Before
@dataclass(frozen=True)
class ToolsConfig:
    ...

# After
@dataclass
class ToolsConfig:
    ...
    
    def __post_init__(self):
        # Add validation here instead of relying on frozen
        ...
```

**Option 2: Use `__post_init__` for validation**
```python
@dataclass
class ToolsConfig:
    ...
    
    def __post_init__(self):
        # Validate immutability constraints
        self._validate()
    
    def _validate(self):
        # Custom validation logic
        pass
```

---

## Examples

### Example 1: Basic Plugin System

```python
# main_app/config.py
from dataclasses import dataclass, field

@dataclass  # NOT frozen
class ToolsConfig:
    list: ListToolConfig = field(default_factory=ListToolConfig)
    read: ReadToolConfig = field(default_factory=ReadToolConfig)

@dataclass
class Config:
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)

# main_app/plugins/loader.py
from clevis import register_field
from main_app.config import ToolsConfig, AgentsConfig

def load_plugins(plugin_list: list[str]):
    for package_name in plugin_list:
        module = importlib.import_module(f"{package_name}.plugin")
        
        if hasattr(module, "ToolConfig"):
            register_field(ToolsConfig, package_name, module.ToolConfig)
        
        if hasattr(module, "AgentConfig"):
            register_field(AgentsConfig, package_name, module.AgentConfig)

# pkgq/plugin.py
from dataclasses import dataclass

@dataclass
class ToolConfig:
    enabled: bool = True
    cache_directory: str = "~/.cache/pkgq"
    timeout_seconds: int = 30

@dataclass
class AgentConfig:
    max_results: int = 10
    include_prerelease: bool = False

# main_app/__main__.py
load_plugins(["pkgq", "git"])
config = get_config(Config, name="myapp")
# config.tools.pkgq.enabled → from [tools.pkgq] in TOML
# config.tools.git.enabled → from [tools.git] in TOML
```

### Example 2: Conditional Feature Registration

```python
import os

@dataclass
class ExperimentalConfig:
    feature_x: bool = False
    feature_y: bool = False

@dataclass
class Config:
    name: str = "default"

# Only register experimental config if enabled
if os.environ.get("ENABLE_EXPERIMENTAL"):
    register_field(Config, "experimental", ExperimentalConfig)

config = get_config(Config, name="myapp")
# config.experimental.feature_x if ENABLE_EXPERIMENTAL
```

### Example 3: Subcommands with TOML Override

```python
# roomz uses this pattern
@configclass(cmd="cli", help="Run TUI chat client", config="client")
class CliConfig(ClientConfig):
    """Configuration for cli command.
    
    Inherits ClientConfig fields for CLI overrides.
    CLI args: --server-url, --display-name
    """
    pass

# TOML file: roomz.toml
# [client]  <- config="client" overrides default [cli]
# server_url = "http://localhost:8000"
# display_name = "User"

# CLI: roomz cli --server-url "http://example.com"
```

---

## Test Plan

### Unit Tests

1. **`register_field()` basic functionality**
   - Add field to non-frozen dataclass
   - Verify field appears in `fields(parent)`
   - Verify default factory works

2. **`register_field()` error cases**
   - Frozen parent raises `TypeError`
   - Duplicate field name raises `ValueError`
   - Late registration raises `RuntimeError`

3. **TOML loading**
   - Registered field loads from correct namespace
   - Nested registered fields work correctly
   - CLI args for registered fields work

4. **CLI argument generation**
   - Registered fields generate correct CLI args
   - Nested paths create dashed args (`--tools-pkgq-enabled`)

5. **Backward compatibility**
   - All existing `@configclass` patterns work
   - Nested dataclasses without registration work
   - Subcommands work unchanged

### Integration Tests

1. **Plugin registration workflow**
   - Load config before and after registration
   - Verify TOML sections map correctly
   - Verify CLI args override correctly

2. **Multiple registrations**
   - Register multiple fields to same parent
   - Register to different parents
   - Register same type to different parents

---

## Open Questions

None. All decisions have been made and validated against existing projects.

---

## References

- GitHub Issue #10: Namespace support in @configclass
- GitHub Issue #11: Dynamic field registration for plugin architectures
- `analysis/handoff.md`: Original analysis document