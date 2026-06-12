# Functional Analysis: Clevis Configuration Library

## Executive Summary

Clevis is a Python configuration management library providing type-safe configuration through dataclass schemas with TOML file support, environment variable interpolation, automatic CLI argument generation, and plugin architecture support through dynamic field registration.

**Current Status**: v0.4.0 released (2026-06-11). All Phase 1 and Phase 2 tasks completed. Phase 3 polish tasks in progress.

**Key Features**:
- TOML configuration with layered precedence (user < project < CLI)
- Automatic CLI argument generation from dataclass fields
- Factory pattern for multi-module orchestration
- Subcommand support for CLI applications
- Dynamic field registration for plugin architectures
- Security validation for configuration files
- List-append behavior for CLI arguments
- CLI argument aliases

---

## Project Overview

### Purpose

Clevis connects multiple configuration sources into a unified dataclass-based interface:
- **User-level TOML**: `~/.{name}.toml` (lowest priority)
- **Project-level TOML**: `./{name}.toml`
- **CLI arguments**: Auto-generated from dataclass fields (highest priority)

### Naming Philosophy

A "clevis" is a U-shaped mechanical fastener that connects components while allowing pivoting. The library follows this metaphor: connecting configuration sources while allowing flexibility in how they're combined.

### Core Value Proposition

- **Type Safety**: Strongly-typed configuration through Python dataclasses
- **Layered Config**: Multiple sources with clear precedence
- **Developer Experience**: Auto-generated CLI arguments, helpful error messages
- **Extensibility**: Multiple TOML parser options (envtoml, tomlev, tomli, stdlib)
- **Factory Pattern**: Multi-module orchestration with shared parsers and prefixes
- **Subcommands**: CLI applications with multiple commands (like `git`, `docker`)
- **Plugin Architecture**: Dynamic field registration at runtime
- **Security**: File permission validation with configurable actions

---

## Architecture Overview

### Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| `get_config()` | Load configuration from all sources | `__init__.py` |
| `@configclass` | Decorator combining `@dataclass` with factory registration | `configclass.py` |
| `Factory` | Manages parser configuration and CLI argument generation | `factory.py` |
| `register_field()` | Add fields to dataclasses at runtime | `registration.py` |
| `SecurityAction` | Enum for security check actions | `__init__.py` |
| `apply_to_dict()` | Merge dictionaries with dotted keys | `__init__.py` |

### Factory Pattern Architecture

The Factory pattern enables four distinct use cases:

#### Use Case 1: Simple Configuration

The simplest case - direct `get_config()` call without any factory setup:

```python
from clevis import get_config
from dataclasses import dataclass

@dataclass
class Config:
    name: str = "MyApp"
    debug: bool = False

config = get_config(Config, name="myapp")
```

Clevis automatically creates a factory with the default parser. No setup required.

#### Use Case 2: Module Development

For library/module developers who want their module to be configurable:

```python
from clevis import configclass, get_config

@configclass
class ModuleConfig:
    api_key: str | None = None
    timeout: int = 30

class MyModule:
    def __init__(self):
        self.config = get_config(ModuleConfig, name="mymodule")
```

The `@configclass` decorator:
1. Applies `@dataclass` to the class
2. Registers it with Clevis's factory system

Orchestration code can later customize the factory before the module is instantiated.

#### Use Case 3: Multi-Module Orchestration

For CLI applications that use multiple modules, each with their own configuration:

```python
import argparse
from clevis import configclass, get_config, get_factory

# Module 1's config
@configclass
class App1Config:
    name: str | None = None

# Module 2's config
@configclass
class App2Config:
    name: str | None = None

# Orchestration: configure factories before instantiation
get_factory(App1Config).prefix = "app1"
get_factory(App2Config).prefix = "app2"

# Share a single parser
parser = argparse.ArgumentParser(description="Multi-Module App")
get_factory(AppConfig).parser = parser
get_factory(App1Config).parser = parser
get_factory(App2Config).parser = parser

# Modules get their config automatically
# CLI args: --app1-name X --app2-name Y
app1 = App1()  # Uses prefixed args: --app1-name
app2 = App2()  # Uses prefixed args: --app2-name
```

#### Use Case 4: Subcommands

For CLI applications with multiple commands (like `git`, `docker`):

```python
from clevis import configclass, get_cmd, get_config

@configclass(cmd="check")
class CheckConfig:
    verbose: bool = False

@configclass(cmd="print")
class PrintConfig:
    rich: bool = False

if __name__ == "__main__":
    cmd = get_cmd()
    if cmd == "check":
        config = get_config(CheckConfig, project=False, user=False)
        print(f"checking verbose={config.verbose}")
    elif cmd == "print":
        config = get_config(PrintConfig, project=False, user=False)
        print(config)
```

Running:
```bash
python app.py --help           # Shows: {check, print} subcommands
python app.py check --help     # Shows: --verbose
python app.py check --verbose  # Runs: checking verbose=True
```

#### Use Case 5: Dynamic Field Registration

For plugin architectures that need to inject configuration fields at runtime:

```python
from dataclasses import dataclass, field
from clevis import register_field

# Main application (NOT frozen)
@dataclass
class ToolsConfig:
    list: ListToolConfig = field(default_factory=ListToolConfig)

# Plugin module
@dataclass
class PkgqToolConfig:
    enabled: bool = True
    cache_directory: str = "~/.cache/pkgq"

# Plugin loader
register_field(ToolsConfig, "pkgq", PkgqToolConfig)

# Result:
# - ToolsConfig.pkgq field added
# - TOML: [tools.pkgq] → config.tools.pkgq
# - CLI: --tools-pkgq-enabled
```

### Configuration Loading Pipeline

```
get_config(Config)
    ↓
Security Validation (file permissions, directory permissions)
    ↓
TOML Loading (user + project configs)
    ↓
CLI Argument Parsing (sys.argv or provided args)
    ↓
List Field Merging (TOML values + CLI values)
    ↓
Dacite Conversion (dict to dataclass)
    ↓
Validation (required fields, types)
    ↓
Return Config instance
```

---

## Feature Analysis

### 1. TOML Parser Selection (`_get_toml_parser`)

**Implementation**: Priority-based fallback chain

| Priority | Parser | Features | Use Case |
|----------|--------|----------|----------|
| 1 | envtoml | `${VAR}` interpolation | Environment-based config |
| 2 | tomlev | `${VAR\|default}` syntax | Env vars with defaults |
| 3 | tomli | Pure Python TOML | Python 3.10 compatibility |
| 4 | tomllib | Stdlib | Python 3.11+ minimal deps |

**Quality**: Well-implemented with clear error message when no parser available.

### 2. Configuration Loading (`get_config`)

**Implementation**: Layered merge strategy

```
Dataclass defaults (base)
    + User TOML (~/.{name}.toml)
    + Project TOML (./{name}.toml)
    + CLI args (sys.argv or provided)
= Final configuration
```

**Security Validation**: Configurable via `security` parameter:
- `DONT_CHECK`: Skip validation
- `LOG`: Log warnings, continue
- `REJECT`: Raise SecurityError (default)

### 3. CLI Argument Generation

**Scalar Fields**: Generate `--field-name VALUE` arguments with type conversion.

**Boolean Fields**: Generate `--field-name` (store_true) and `--no-field-name` (store_const, const=False).

**List Fields**: Generate `--field-name VALUE` (action=append, repeatable) and `--no-field-name` (store_const, const=[]).

**List Behavior**:
- Multiple arguments append: `--packages a --packages b` → `["a", "b"]`
- `--no-field` clears: `--no-packages` → `[]`
- Merge with TOML: TOML `packages = ["x"]` + CLI `--packages y` → `["x", "y"]`

### 4. CLI Argument Aliases

Fields can have alternative CLI argument names via metadata:

```python
@dataclass
class Config:
    packages: list[str] = field(
        default_factory=list,
        metadata={"cli_aliases": ["with"]}
    )
```

Creates both `--packages` and `--with`. Aliases replace the entire argument name (no prefix for nested configs).

**Behavior**:
- Aliases conflict detection prevents duplicate argument names
- Both canonical and alias append to the same list
- Works for scalar, boolean, and list fields

### 5. Subcommand Support

The `@configclass(cmd="name")` decorator registers configurations as CLI subcommands:

```python
@configclass(cmd="check", help="Run diagnostics", aliases=["chk", "c"])
class CheckConfig:
    verbose: bool = False
```

**Features**:
- Automatic subparser creation
- Help text and aliases support
- `get_cmd()` returns active subcommand name
- `config` parameter for TOML section override

### 6. Dynamic Field Registration

Add fields to non-frozen dataclasses at runtime:

```python
def register_field(
    parent: type,
    name: str,
    field_type: type,
    default_factory: Callable[[], Any] | None = None,
) -> None:
    """Add a field to a parent config class at runtime.

    Modifies the parent class in-place. Namespace for TOML/CLI is
    automatically derived from parent hierarchy.

    Raises:
        TypeError: If parent is a frozen dataclass
        ValueError: If field name already exists
        RuntimeError: If called after get_config() (parser already configured)
    """
```

**Use Case**: Plugin architectures where plugins inject configuration into specific sections.

### 7. Security Features

**File Permission Validation**:
```python
config = get_config(
    Config,
    security={
        "file_permissions": SecurityAction.REJECT,
        "directory_permissions": SecurityAction.LOG,
    }
)
```

**Checks**:
- File permissions: Reject if readable by group/other (mode & 0o044)
- Directory permissions: Reject if world-writable (mode & 0o002)
- Home directory trusted for user config

### 8. Error Handling

**ConfigError** provides actionable messages:

```
======================================================================
Configuration Error
======================================================================

Field: database.host
Issue: Required field has no value

Provide this value in one of these ways:
  1. Project config: ./project.toml
  2. User config: ~/.project.toml
  3. CLI argument: --database-host <value>
======================================================================
```

Error messages adapt based on `cli` parameter (omit CLI suggestion when `cli=False`).

---

## Implemented Features

### Phase 1: Core Functionality (Completed)

- **P1-001**: Initial git commit
- **P1-002**: Create missing documentation files
- **P1-003**: Make CLI support optional (`cli=False` parameter)

### Phase 2: Extensions (Completed)

- **P2-001**: Factory pattern for multi-module configuration
- **P2-002**: Security parameter for file permission validation
- **P2-003**: Resolve `project.toml` repository file
- **P2-004**: Add type stub files
- **P2-005**: Add cookbook entries to docs
- **P2-006**: Enhance subcommand support (help, aliases)
- **P2-007**: Implement dynamic field registration
- **P2-008**: Update `@configclass` decorator (config parameter validation)
- **P2-009**: Add comprehensive documentation and examples
- **P2-010**: Verify dynamic field registration tests
- **P2-011**: Add list-append behavior for CLI arguments
- **P2-012**: Add CLI argument aliases
- **P2-013-P2-018**: Code quality improvements (refactoring, documentation)

### Phase 3: Polish (In Progress)

Optional improvements for future releases:
- **P3-008**: Encapsulate global state in ParserRegistry class
- **P3-009**: Refactor `_merge_list_args` to return merged dict
- **P3-010**: Extract methods from `_configure_fields`
- **P3-011-P3-015**: Various code quality improvements
- **P3-004**: Achieve 90%+ test coverage

### Phase 4: Parking Lot (Speculative)

Ideas with no current demand:
- **P4-001**: Async configuration loading
- **P4-002**: Configuration hot-reload
- **P4-003**: Schema validation (constraint-based)
- **P4-004**: Support additional config formats (YAML, JSON)

---

## Design Decisions

This section documents intentional design decisions made during implementation, including alternatives considered and the rationale for the final choices.

### 1. Dynamic Field Registration - Automatic Namespace Derivation

**Decision**: Namespace is automatically derived from the parent hierarchy. The `register_field()` function requires no explicit namespace parameter.

```python
register_field(ToolsConfig, "pkgq", PkgqToolConfig)
# TOML: [tools.pkgq] → config.tools.pkgq
# CLI: --tools-pkgq-enabled
```

**Alternatives Considered**:
- Explicit namespace parameter: `register_field(parent, name, field_type, default_factory, namespace="tools")`
- Manual namespace specification in each call
- Configuration file for namespace mappings

**Rationale**: Automatic namespace derivation from the parent hierarchy eliminates a common source of errors. Users cannot accidentally specify a mismatched namespace, and the API is simpler with one less parameter. The parent field path naturally maps to both TOML sections and CLI argument prefixes.

### 2. List-Append Behavior - Unified Clear Pattern

**Decision**: Lists are cleared using the `--no-field` prefix (e.g., `--no-packages`), which is the same pattern used for setting booleans to False.

**Behavior**:
- Multiple arguments append: `--packages a --packages b` → `["a", "b"]`
- Clear with prefix: `--no-packages` → `[]`
- Merge with TOML: TOML `packages = ["x"]` + CLI `--packages y` → `["x", "y"]`

**Alternatives Considered**:
- Separate `--field-clear` flag (e.g., `--packages-clear`)
- `--field-reset` flag
- `--field` with empty value (e.g., `--packages=""`)
- Special syntax like `--field=[]`

**Rationale**: The `--no-field` prefix provides a consistent pattern for both booleans and lists. This follows established conventions from tools like `git` (e.g., `git diff --no-color`). A single clear mechanism reduces cognitive load and makes the API more predictable.

### 3. CLI Argument Aliases - Full Name Replacement

**Decision**: Aliases replace the entire argument name, not just add a suffix.

```python
@dataclass
class Config:
    packages: list[str] = field(
        default_factory=list,
        metadata={"cli_aliases": ["with"]}
    )
# Creates both --packages and --with (not --packages-with)
```

**Alternatives Considered**:
- Suffix-based aliases: `--packages-with` for `packages` field
- Prefix-based aliases: `--with-packages` for `packages` field
- Namespace-specific aliases that preserve the field path

**Rationale**: Full name replacement provides genuinely shorter alternatives, which is particularly valuable for nested configs where the canonical name might be `--tools-pkgq-enabled` but users want `--pkgq`. Suffix-based aliases would still result in long argument names for nested configurations.

### 4. Security Implementation - Documented TOCTOU Limitation

**Decision**: TOCTOU (Time-of-Check-Time-of-Use) race condition is acknowledged as a known limitation with configurable security actions.

**Implementation**: File permission checks validate before reading, but there's a window between check and read. This is documented as an acceptable trade-off for most use cases.

**Alternatives Considered**:
- File descriptor-based reading: Open file first, then check permissions on the descriptor (eliminates TOCTOU)
- Atomic file operations using platform-specific mechanisms
- Complete rejection of files with any race window
- Caching security status with periodic revalidation

**Rationale**: Full TOCTOU protection using file descriptors adds significant complexity for a relatively rare threat model. Most configuration files are in controlled environments (user home directories, project directories). The security parameter allows users to configure `SecurityAction.DONT_CHECK` for trusted environments or `SecurityAction.LOG` for monitoring. The limitation is explicitly documented for users with higher security requirements.

### 5. Subcommand Configuration - Explicit Config Parameter

**Decision**: The `config` parameter is required when the TOML section name differs from the command name.

```python
@configclass(cmd="cli", config="client")
class CliConfig:
    verbose: bool = False
# Command: myapp cli --verbose
# TOML: [client] section (not [cli])
```

**Alternatives Considered**:
- Automatic TOML section detection based on command name
- Convention over configuration (always use command name as section)
- Naming convention requirements (command must match TOML section)

**Rationale**: Explicit is better than implicit. Automatic detection could lead to subtle bugs when a command name is renamed but TOML sections aren't updated. The `config` parameter makes the mapping clear and handles edge cases like `cmd="cli"` loading from `[client]` TOML section. This follows Python's philosophy of explicit over implicit and makes debugging easier.

---

## Code Quality Assessment

### Strengths

1. **Type Safety**: Full type hints throughout, proper use of Union types, generic return types
2. **Error UX**: Helpful, actionable error messages with resolution paths
3. **Extensibility**: Pluggable TOML parsers, configurable security, dynamic registration
4. **Test Coverage**: ~80% baseline, comprehensive test suite for new features
5. **Documentation**: Comprehensive docs, examples, PACKAGE.md

### Design Patterns

- **Factory pattern**: `Factory` dataclass manages parser configuration
- **Decorator pattern**: `@configclass` registers dataclass with factory
- **Singleton pattern**: `get_factory()` returns same Factory for same class
- **Lazy initialization**: Parser configured on first `get_config()` call
- **Protocol pattern**: `Parser` and `SubParser` Protocols for pluggable parsers

### Code Organization

```
src/clevis/
├── __init__.py       # Public API, config loading, error handling
├── configclass.py    # @configclass decorator
├── factory.py        # Factory pattern, CLI argument generation
└── registration.py  # Dynamic field registration

tests/
├── test_clevis.py          # Core functionality tests
├── test_factory.py        # Factory pattern tests
├── test_registration.py   # Dynamic registration tests
├── test_list_append.py    # List-append behavior tests
└── test_cli_aliases.py    # CLI argument aliases tests
```

---

## Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| dacite | Dict-to-dataclass conversion | Yes |
| envtoml | TOML + env vars | Optional |
| tomlev | TOML + env defaults | Optional |
| tomli | Pure Python TOML | Optional |

---

## Future Enhancements

### Planned (Phase 3)

1. **Encapsulate Global State**: Refactor into `ParserRegistry` class
2. **Improve Code Organization**: Extract methods from large functions
3. **Add Documentation**: Expand inline comments for complex logic

### Considered (Phase 4)

1. **Async Configuration Loading**: `get_config_async()` with `aiofiles`
2. **Configuration Hot-Reload**: Watch TOML files for changes
3. **Schema Validation**: Add `min`, `max`, `pattern` validators
4. **Additional Formats**: YAML/JSON support as extras

### Known Limitations

1. **TOCTOU Race Condition**: Security checks and file reads have a race window (acceptable for most use cases)
2. **Thread Safety**: Module-level globals not thread-safe (single-threaded usage assumed)
3. **Network Filesystems**: Permission checks may not be reliable on NFS/CIFS (documented limitation)

---

## References

### Documentation

- `README.md`: User-facing documentation
- `PACKAGE.md`: Comprehensive package documentation with all 6 use cases
- `docs/usage.rst`: Detailed usage guide with examples
- `docs/api.rst`: API reference

### Supplementary Analysis Documents

The following standalone documents provide additional depth on specific topics:

- **`dynamic-registration.md`**: Comprehensive plugin architecture design with examples and migration guide
- **`P2-002-security-parameter.md`**: Detailed security validation design with implementation plan
- **`api-cli-optional.md`**: Library integration design (making CLI support optional)
- **`edge-case-analysis.md`**: Edge case testing results, documented bugs, and behavior analysis

Historical development reviews (API reviews, functional reviews, security reviews) have been consolidated into this master document.

### Related GitHub Issues

- #1: CLI support optional
- #3: Factory pattern
- #4: Security parameter
- #9: Subcommand enhancements
- #10: Namespace support
- #11: Dynamic field registration
- #13: CLI argument aliases
- #14: List-append behavior

---

## Conclusion

Clevis is a well-architected configuration library with comprehensive features for modern Python applications. The Factory pattern enables powerful multi-module orchestration, the subcommand support enables CLI applications, and the dynamic field registration enables plugin architectures.

**Current Version**: 0.4.0

**Test Coverage**: ~90%

**Key Strengths**:
1. Type-safe configuration management
2. Flexible layered configuration (user, project, CLI)
3. Automatic CLI argument generation with aliases and list support
4. Plugin architecture support through dynamic registration
5. Security features for production deployment
6. Excellent error messages for developer experience

**Future Focus**:
- Continue improving code quality (Phase 3 tasks)
- Expand test coverage to 90%+
- Polish documentation and examples