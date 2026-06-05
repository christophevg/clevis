# Functional Analysis: Clevis Configuration Library

## Executive Summary

Clevis is a well-designed Python configuration management library that provides type-safe configuration through dataclass schemas. The implementation is feature-complete with support for TOML files, environment variable interpolation, and automatic CLI argument generation. The Factory pattern (P2-001) extends the library to support multi-module orchestration and CLI subcommands.

**Current Status**: v0.2.0 released. Factory pattern and subcommand support implementation in progress (P2-001). ~80% test coverage.

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

---

## Core Functionality Analysis

### 1. TOML Parser Selection (`_get_toml_parser`)

**Implementation**: Priority-based fallback chain

| Priority | Parser | Features | Use Case |
|----------|--------|----------|----------|
| 1 | envtoml | `${VAR}` interpolation | Environment-based config |
| 2 | tomlev | `${VAR\|default}` syntax | Env vars with defaults |
| 3 | tomli | Pure Python TOML | Python 3.10 compatibility |
| 4 | tomllib | Stdlib | Python 3.11+ minimal deps |

**Quality**: Well-implemented with clear error message when no parser available.

**Test Coverage Gap**: Fallback branches not fully covered - only envtoml is tested since all extras are installed.

### 2. Configuration Loading (`get_config`)

**Implementation**: Layered merge strategy

```
Dataclass defaults (base)
    + User TOML (~/.{name}.toml)
    + Project TOML (./{name}.toml)
    + CLI args (sys.argv or provided)
= Final configuration
```

**Quality**: Clean implementation with proper path handling.

**Test Coverage Gap**: User-level config loading not fully covered.

### 3. Factory Pattern (P2-001)

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

#### Use Case 4: Subcommands (NEW)

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

#### Factory Architecture

```
@configclass → registers → _factories[type] = Factory(config_class)
                               ↓
get_factory(Config) → returns → Factory instance
                               ↓
Factory.prefix = "app1" → customizes → CLI arg prefix
Factory.parser = custom → injects → Custom/shared parser
Factory.cmd = "check" → creates → Subparser for command
                               ↓
get_config(Config) → triggers → Factory.configure_parser()
                               ↓
                        Factory.get_args() → parses CLI → dict
                               ↓
get_cmd() → returns → Active subcommand name
```

#### Key Components

| Component | Purpose |
|-----------|---------|
| `@configclass` | Decorator that registers dataclass with factory system |
| `@configclass(cmd="name")` | Decorator that registers config as subcommand |
| `get_factory(clz)` | Returns singleton Factory for a config class |
| `get_cmd()` | Returns active subcommand name |
| `Factory.config_class` | The dataclass type being configured |
| `Factory.prefix` | Optional prefix for CLI arguments |
| `Factory.parser` | The argparse-compatible parser to use |
| `Factory.cmd` | Optional subcommand name |
| `Factory.sub_parser` | Subparser instance (when cmd is set) |
| `Factory._configured` | Flag to prevent double configuration |
| `Factory.configure_parser()` | Lazily adds arguments to parser |
| `Factory.get_args()` | Parses CLI and returns dict with dotted keys |
| `Factory.list_fields()` | Exposes field structure for introspection |
| `Parser` Protocol | Interface for argparse-compatible parsers |
| `SubParser` Protocol | Interface for subparser operations |
| `get_sub_parser(parser)` | Creates or returns existing subparser |
| `_configured_parsers` | Tracks which parsers have been configured |
| `_sub_parsers` | Maps parsers to their subparsers |
| `_reset_factories()` | Clears all factories (for testing) |

### 4. Dictionary Merging (`apply_to_dict`)

**Implementation**: In-place nested dictionary modification

- Creates intermediate dictionaries as needed
- Handles dotted keys properly
- Preserves non-overridden values

**Quality**: Well-tested with good coverage.

### 5. Error Handling (`ConfigError`)

**Implementation**: Custom exception with actionable messages

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

**Test Coverage Gap**: `WrongTypeError` and generic `DaciteError` branches not fully covered.

---

## Architecture Assessment

### Strengths

1. **Clean Separation of Concerns**
   - Parser selection isolated in `_get_toml_parser`
   - Factory pattern separates config definition from parser orchestration
   - Subcommand handling integrated into Factory pattern
   - Dictionary utilities are pure functions

2. **Extensibility**
   - Multiple TOML parser options via extras
   - Pluggable parser via `Parser` Protocol
   - Factory pattern enables multi-module orchestration
   - Subcommands enable CLI application patterns
   - Optional user/project config loading

3. **Type Safety**
   - Full type hints throughout
   - Proper use of Union types (e.g., `str | None`)
   - Generic return type preserves dataclass type

4. **Error UX**
   - Helpful, actionable error messages
   - Clear guidance on resolution paths
   - Field path extraction from dacite errors

### Design Patterns Used

- **Factory pattern**: `Factory` dataclass manages parser configuration
- **Decorator pattern**: `@configclass` registers dataclass with factory
- **Singleton pattern**: `get_factory()` returns same Factory for same class
- **Lazy initialization**: Parser configured on first `get_config()` call
- **Protocol pattern**: `Parser` and `SubParser` Protocols for pluggable parsers
- **Module-level caching**: `_toml_load` cached parser, `_factories` registry

### Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| dacite | Dict-to-dataclass conversion | Yes |
| envtoml | TOML + env vars | Optional |
| tomlev | TOML + env defaults | Optional |
| tomli | Pure Python TOML | Optional |

---

## Code Quality Issues (From Code Review)

### Must Fix Before Merge (P2-001)

| Issue | Location | Description | Status |
|-------|----------|-------------|--------|
| Debug print statement | Line 141 in `get_args()` | `print(args_dict)` left in production code | ✅ Fixed |
| `_sub_parsers` not reset | `_reset_factories()` | Global not cleared in test isolation | Pending |
| Duplicate import | Lines 20 and 202 | `typing.Callable` imported twice | Pending |
| Type annotation missing | `Parser.add_subparsers()` | No return type annotation | Pending |

### Should Fix Before Merge

| Issue | Location | Description |
|-------|----------|-------------|
| Subparser shared state | `_sub_parsers` dict | May have stale entries after parser changes |
| SubParser Protocol incomplete | `SubParser` | Minimal protocol, doesn't cover all argparse features |
| Type mismatch | Example usage | `project=None` passed where `project: bool` expected |

### Nice to Have

| Issue | Description |
|-------|-------------|
| Subcommand help text | No way to specify help text for subcommands |
| Subcommand aliases | No way to specify aliases for subcommands |
| `_configured` naming | Private attribute used in public method |

---

## Quality Assessment

### Code Quality

| Metric | Status | Notes |
|--------|--------|-------|
| Type Hints | Complete | All functions fully typed |
| Documentation | Good | Docstrings for all public functions |
| Code Style | Excellent | Follows ruff/mypy standards |
| Complexity | Medium | Factory pattern + subcommands add complexity but justified |
| Error Handling | Good | Custom exception with helpful messages |

### Test Quality

**Coverage**: ~80% (before P2-001 tests complete)

**Test Gaps (addressed in P2-001)**:

1. **Factory Pattern Tests**
   - `@configclass` decorator
   - `get_factory()` singleton behavior
   - `Factory.prefix` application
   - Shared parser (multiple configs, one parser)
   - Lazy parser configuration
   - `Factory.get_args()` with prefix stripping
   - `_reset_factories()` test isolation

2. **Subcommand Tests (NEW)**
   - `@configclass(cmd="check")` registers subcommand
   - `get_cmd()` returns correct command
   - Subcommand arguments parsed correctly
   - Multiple subcommands work together
   - `_reset_factories()` clears `_sub_parsers`

3. **Parser Fallback Branches**
   - tomlev parser code path
   - tomli parser code path
   - tomllib stdlib fallback

4. **Error Handling Branches**
   - `WrongTypeError` handling
   - Generic `DaciteError` handling

5. **Edge Cases**
   - Complex union types (>2 types)
   - Boolean `store_true` action
   - User-level config loading

**Test Organization**:
- `test_clevis.py`: Core functionality tests
- `test_parser.py`: Parser selection tests
- `test_factory.py`: Factory pattern tests (to be created)

### Documentation Status

| File | Status | Notes |
|------|--------|-------|
| README.md | Complete | Full usage documentation |
| docs/conf.py | Complete | Sphinx configuration |
| docs/index.rst | Complete | Index page with toctree |
| docs/installation.rst | Complete | Installation guide |
| docs/usage.rst | Needs Update | Factory pattern + subcommand sections to add |
| docs/api.rst | Complete | API reference |

---

## Examples

### `examples/factory.py`

Demonstrates three use cases:
1. Simple configuration (MyConfig)
2. Module development (App1Config, App2Config)
3. Multi-module orchestration (shared parser, prefixes)

### `examples/commands.py`

Demonstrates subcommand use case:
- `@configclass(cmd="check")` for check command
- `@configclass(cmd="print")` for print command
- `get_cmd()` to dispatch based on command
- `project=False, user=False` to skip config files

---

## Recommendations

### Immediate (P2-001 Completion)

1. **Fix remaining code quality issues**
   - Add `_sub_parsers` reset to `_reset_factories()`
   - Remove duplicate import
   - Add return type to `Parser.add_subparsers()`

2. **Add comprehensive tests**
   - Factory pattern tests (R79-R85)
   - Subcommand tests (R86-R90)

3. **Update documentation**
   - Factory pattern section in `docs/usage.rst`
   - Subcommand section in `docs/usage.rst`
   - Update API reference

### Near-Term (P2-002, P3)

4. **Security Parameter**
   - Implement file permission validation
   - Implement directory security validation

5. **Improve Test Coverage**
   - Target 90%+ coverage
   - Cover all fallback branches

### Future (P3, P4)

6. **Type Stubs**
   - Improve IDE experience

7. **Subcommand Enhancements (P3-003)**
   - Add `help` parameter for subcommand help text
   - Add `aliases` parameter for subcommand aliases

---

## Conclusion

Clevis is a well-architected configuration library. The Factory pattern (P2-001) significantly enhances its capabilities for:

1. **Simple use cases**: Direct `get_config()` for single-app configuration
2. **Module development**: `@configclass` for library developers
3. **Orchestration**: Factory customization for multi-module CLI apps
4. **Subcommands**: CLI applications with multiple commands

Key priorities:
1. Complete remaining code quality fixes (duplicate import, `_sub_parsers` reset)
2. Add comprehensive tests for Factory and subcommand patterns
3. Update documentation
4. Implement P2-002 security parameter
5. Achieve 90%+ test coverage