# Requirements

This document tracks the source-of-truth requirements for Clevis. Each requirement is referenced from TODO.md tasks via its ID (R1, R2, ...).

## Functional Requirements

### Core Features (from README.md)

- [x] R1: Dataclass-based configuration schemas
- [x] R2: TOML file loading from project directory
- [x] R3: TOML file loading from user home directory
- [x] R4: Environment variable interpolation (via envtoml/tomlev extras)
- [x] R5: Automatic CLI argument generation from dataclass
- [x] R6: Layered configuration merging (defaults < user < project < CLI)
- [x] R7: Nested dataclass support with dotted paths
- [x] R8: Helpful error messages with actionable suggestions

### Parser Support

- [x] R9: envtoml parser support (${VAR} interpolation)
- [x] R10: tomlev parser support (${VAR|default} syntax)
- [x] R11: tomli parser support (Python 3.10)
- [x] R12: tomllib stdlib support (Python 3.11+)
- [x] R13: Graceful fallback when preferred parser unavailable
- [x] R14: Clear error message when no parser available

### CLI Integration

- [x] R15: Automatic argparse generation from dataclass
- [x] R16: Nested field to dashed argument conversion (database.host -> --database-host)
- [x] R17: Boolean fields with store_true action
- [x] R18: Optional field handling (None defaults)
- [x] R19: Type preservation through argparse

### Factory Pattern (P2-001, issue #3)

The Factory pattern enables three use cases:

1. **Simple case**: Direct `get_config()` call with auto-discovered parser
2. **Module development**: Pre-register configs with `@configclass` decorator
3. **Multi-module orchestration**: Shared parser with prefixes, custom parser injection
4. **Subcommands**: CLI applications with multiple commands (like `git`, `docker`)

- [ ] R20: `@configclass` decorator registers dataclass with Clevis factory system
- [ ] R21: `get_factory(Config)` returns Factory instance for configuration customization
- [ ] R22: `Factory.prefix` applies CLI argument prefix (e.g., "app1" -> "--app1-name")
- [ ] R23: `Factory.parser` allows custom or shared parser injection
- [ ] R24: Lazy parser configuration - parser configured on first `get_config()` call
- [ ] R25: `Factory.list_fields()` exposes field structure for introspection
- [ ] R26: `Factory.get_args()` returns parsed CLI arguments as dict with dotted keys
- [ ] R27: Parser Protocol for pluggable argument parsers (argparse-compatible)
- [ ] R28: Multiple configs can share one parser for orchestrated CLI
- [ ] R29: `@configclass(cmd="name")` registers config as subcommand
- [ ] R30: `get_cmd()` returns the active subcommand name
- [ ] R31: SubParser Protocol for subparser operations
- [ ] R32: `get_sub_parser(parser)` creates or returns existing subparser
- [ ] R33: Subcommand-specific arguments parsed correctly for each config

### Error Handling

- [x] R34: MissingValueError conversion to helpful ConfigError
- [x] R35: WrongTypeError conversion to helpful ConfigError
- [x] R36: Generic DaciteError handling
- [x] R37: Field path extraction from error messages
- [x] R38: Multi-source resolution suggestions in errors

### Security (P2-002, issue #4)

- [ ] R39: Optional `security` argument to `get_config()`
- [ ] R40: Default security policy is maximally strict (reject on security issues)
- [ ] R41: Per-check options: Don't Check | Log | Reject
- [ ] R42: Configuration file permission validation (group/other readable)
- [ ] R43: Parent directory security validation (world-writable)

### Dynamic Field Registration (P2-007, issues #10 and #11)

Enable plugin architectures to inject configuration fields at runtime.

- [ ] R100: `register_field(parent, name, field_type)` adds field to parent dataclass
- [ ] R101: Registered fields derive TOML namespace from parent hierarchy automatically
- [ ] R102: Registered fields generate CLI args with dotted path (`--parent-name-field`)
- [ ] R103: `register_field()` raises `TypeError` for frozen parent dataclass
- [ ] R104: `register_field()` raises `ValueError` for duplicate field name
- [ ] R105: `register_field()` raises `RuntimeError` if called after `get_config()`
- [ ] R106: Parent must be non-frozen dataclass to accept dynamic fields
- [ ] R107: `@configclass(config=...)` requires `cmd` parameter (validation)
- [ ] R108: Documentation covers all 6 use cases with examples
- [ ] R109: Tests cover dynamic registration, error cases, backward compatibility

## Non-Functional Requirements

### Code Quality

- [ ] R44: 90%+ test coverage (currently ~80%)
- [x] R45: Full type hints on all public functions
- [x] R46: Docstrings on all public functions
- [x] R47: Code style compliance (ruff/mypy)
- [ ] R48: Type-preservation tests for argparse with complex union types (>2 types)
- [ ] R49: `__init__.pyi` type stub file for IDE support
- [ ] R50: Remove duplicate imports (typing.Callable imported twice)
- [ ] R51: `_reset_factories()` must reset `_sub_parsers` global

### Documentation

- [x] R52: README.md with full usage documentation
- [x] R53: docs/conf.py for Sphinx/ReadTheDocs
- [x] R54: docs/index.rst with toctree
- [x] R55: docs/installation.rst
- [ ] R56: docs/usage.rst with Factory pattern and subcommand documentation
- [x] R57: docs/api.rst
- [ ] R58: Cookbook entries for nested configs, env vars, and custom validation patterns
- [ ] R59: Add `help` parameter to `@configclass(cmd=...)` for subcommand help text
- [ ] R60: Add `aliases` parameter to `@configclass(cmd=...)` for subcommand aliases

### Project Infrastructure

- [x] R61: pyproject.toml with proper metadata
- [x] R62: Makefile with standard targets
- [x] R63: .github/workflows/test.yml for CI
- [x] R64: .readthedocs.yaml for documentation
- [x] R65: LICENSE file (MIT)
- [x] R66: .gitignore for Python projects
- [x] R67: Initial git commit

### Release Readiness

- [x] R68: Version in pyproject.toml and __init__.py
- [x] R69: Makefile has pre-publish checks
- [x] R70: Makefile has publish target
- [x] R71: PyPI badges in README.md
- [x] R72: PyPI publication (0.2.0)

### Testing

- [x] R73: Unit tests for core functionality
- [x] R74: Unit tests for parser selection
- [ ] R75: Tests for parser fallback branches (tomlev, tomli, tomllib)
- [ ] R76: Tests for error handling branches (WrongTypeError, DaciteError)
- [ ] R77: Tests for user-level config loading (~/.{name}.toml)
- [ ] R78: Tests for boolean CLI arguments (store_true)
- [ ] R79: Tests for `@configclass` decorator
- [ ] R80: Tests for `get_factory()` function
- [ ] R81: Tests for `Factory.prefix` application
- [ ] R82: Tests for shared parser (multiple configs, one parser)
- [ ] R83: Tests for lazy parser configuration
- [ ] R84: Tests for `Factory.get_args()` with prefix stripping
- [ ] R85: Tests for `_reset_factories()` test isolation
- [ ] R86: Tests for `@configclass(cmd="name")` subcommand registration
- [ ] R87: Tests for `get_cmd()` returns correct command
- [ ] R88: Tests for subcommand arguments parsed correctly
- [ ] R89: Tests for multiple subcommands working together
- [ ] R90: Tests for `_reset_factories()` clearing `_sub_parsers`

### Repository Hygiene

- [ ] R91: `project.toml` file resolved (moved/renamed/gitignored) — purpose clear
- [ ] R92: `examples/commands.py` example working and documented

## Completed

The following requirements were satisfied by prior tasks. They are kept here for traceability.

- [x] R1-R19 (core features, parser support, CLI integration) — Iteration 1, delivered in v0.1.0
- [x] R34-R38 (error handling) — Iteration 1, delivered in v0.1.0
- [x] R45-R47, R52-H55, R57, R61-H67, R68-H72, R73-R74 — Iteration 1-2 (P1-001, P1-002, P1-003)
- [x] Initial PyPI publication at v0.2.0 — P1-003 closed