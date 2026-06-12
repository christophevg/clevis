# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.5.0 (2026-06-12)

### Added

- **CLI Argument Aliases**: Support for short-form CLI arguments via `metadata["cli_aliases"]`
  - Define multiple names for the same argument (e.g., `["-v", "--verbose"]`)
  - Improved CLI ergonomics for frequently used options
- **List-Append CLI Behavior**: Intelligent merging of CLI list arguments with TOML configuration
  - `--field X --field Y` appends values to TOML base
  - `--no-field` clears the list (sets to empty)
  - Automatic list field detection and merging
- **Dynamic Field Registration**: Runtime field registration for plugin architectures
  - `register_field()` function to add fields after dataclass definition
  - Enables plugin systems that extend configuration schema
  - Field owner tracking for introspection
- **Security Parameter**: File permission validation configuration
  - `SecurityAction` enum: `DONT_CHECK`, `LOG`, `REJECT`
  - `SecurityConfig` typed dict for granular control
  - TOCTOU-safe checks using file descriptors
- **Factory Pattern**: Multi-module orchestration support
  - `get_factory(clz)` returns singleton Factory for each config class
  - `@configclass` decorator combines `@dataclass` with factory registration
  - Custom prefix and parser configuration per class
- **Subcommand Support**: CLI subcommands with help and aliases
  - `cmd`, `help`, and `aliases` parameters in `@configclass`
  - `get_cmd()` function to retrieve active subcommand
  - Proper TOML section extraction for subcommands

### Changed

- **Test Coverage**: Achieved 92% test coverage
- **Code Quality Polish**:
  - Refactored ParserRegistry for cleaner API
  - Lazy initialization improvements
  - Extracted constants and helper functions
- **Documentation**: Consolidated and improved documentation structure

## 0.4.0 (2026-06-09)

### Added

- **Dynamic Field Registration API (P2-007)**: New `register_field()` function enables runtime field registration for plugin systems
  - Register new configuration fields after dataclass definition
  - Support for plugins that extend configuration schema
  - Enhanced introspection with `field.owner` tracking
- **Plugin System Capabilities**: Infrastructure for extending configuration schemas dynamically
  - Field registration API for third-party extensions
  - Example plugins demonstrating dynamic registration
- **Enhanced Subcommand Validation**: Validation that subcommand configs are not nested incorrectly
  - Prevents configuration schema errors
  - Better error messages for nested configuration issues

### Fixed

- **Nested Config Handling**: Fixed duplicate CLI args from nested configs
  - Tracks `nested_prefix` for config hierarchy
  - Prevents argument duplication in subcommands
- **Dynamic Registration**: Resolved repr and TOML loading issues
  - Fixed factory creation in `register_field` check
  - Correct TOML config extraction for subcommands

### Changed

- **Documentation**: Comprehensive documentation upgrade with examples
  - Added API review and field owner tracking tests
  - New examples: environment, validation, library_mode, simple plugin registration
  - Examples README index for better navigation
  - Improved consistency across documentation

### Added

- **Factory Pattern for Multi-Module Configuration (P2-001)**: New `Factory` class and `configclass` decorator enable orchestration code to customize prefixes and parsers before configuration loading
  - `get_factory(clz)` returns singleton Factory for each config class
  - `@configclass` decorator combines `@dataclass` with factory registration
  - Support for subcommands with `cmd`, `help`, and `aliases` parameters
- **Security Parameter for Config Validation (P2-002)**: New `security` parameter in `get_config()` controls file/directory permission checks
  - `SecurityAction` enum: `DONT_CHECK`, `LOG`, `REJECT`
  - `SecurityConfig` typed dict for configuring security behavior
  - `SecurityError` exception for rejected configs
  - TOCTOU-safe file permission checks using file descriptors
- **Type Stub Files for IDE Support (P2-004)**: Added `py.typed` marker and type stub files for better IDE autocomplete and type hints
- **Cookbook Documentation (P2-005)**: New documentation section with practical usage patterns and examples
- **Subcommand Help and Aliases (P2-006)**: Extended `configclass` decorator with `help` and `aliases` parameters for subcommand documentation

### Fixed

- Addressed code review issues for PR #9 (subcommand enhancements)
- Use LOG security in examples instead of REJECT
- Update tests to use `security=DONT_CHECK` for cleaner test isolation
- Restore formatted `ConfigError` messages after factory pattern changes

## 0.3.3 (2026-06-07)

### Added
- Support for `Literal["A", "B", "C"]` types with validation
- Support for container types: `list[T]`, `dict[K, V]`, `set[T]`, `tuple[T, ...]`
- Automatic conversion of TOML arrays to `tuple` and `set` types
- Support for nested dataclasses as dict values: `dict[str, DataclassType]`
- Compatibility with `frozen=True` dataclasses

### Changed
- Enhanced `unpack_type()` to properly handle container types and Literal types
- Updated `from_dict()` to use `Config(cast=[tuple, set])` for automatic type casting
- Improved type hints with `Union` and `get_origin` imports

### Fixed
- `unpack_type()` now correctly returns container types as-is instead of treating them as unions
- `unpack_type()` now correctly returns Literal types as-is for dacite validation

## 0.3.2 (2026-06-07)

### Added
- `config` parameter in `@configclass` decorator to specify TOML extraction key independently from CLI command name
- Support for reusing TOML sections across multiple CLI commands
- Ability to extract TOML configuration without CLI subcommand

### Changed
- Enhanced Factory class with `config` attribute for flexible TOML section extraction
- Improved documentation with examples of config parameter usage

## 0.3.1 (2026-06-07)

### Fixed
- Prevent cmd/prefix conflicts and root field leakage in subcommand configs
- Raise ConfigError when TOML section is not a table/dict
- Clear root-level fields before extracting subcommand section

### Added
- Comprehensive edge case and subcommand tests (51 tests)
- Example demonstrating subcommand configuration pattern

## 0.3.0 (2026-06-05)

### Added
- Security checks for configuration file permissions
- TOCTOU-safe file permission checking using file descriptors
- ConfigError with actionable error messages
- Support for subcommands in CLI applications
- `get_cmd()` function to retrieve active subcommand
- `cmd`, `help`, and `aliases` parameters in `@configclass` decorator
- Environment variable interpolation support (via envtoml and tomlev)
- Multiple TOML parser fallback (envtoml > tomlev > tomli > tomllib)

### Changed
- Improved error messages with field path and configuration suggestions
- Better handling of nested configuration classes

### Security
- Configuration files now reject group/other readable permissions by default
- World-writable directories are rejected by default
- Security checks can be configured via SecurityAction enum

## 0.2.0 (2026-05-30)

### Added

- **Optional CLI Support**: New `cli` parameter in `get_config()` allows disabling CLI argument parsing
  - Library mode: `cli=False` skips `sys.argv` parsing entirely
  - Testing: Cleaner test setup without CLI interference
  - Better error messages: Errors omit CLI suggestions when `cli=False`
- **PACKAGE.md**: Agent-ready documentation for AI assistants
- **Package badge**: Added pkgq PACKAGE.md badge to README

### Changed

- Switched from `uv publish` to `twine` for PyPI uploads
- Improved test coverage for CLI parsing behavior

### Fixed

- Fixed `test_cli_false_skips_sys_argv` to properly verify `sys.argv` is ignored
- Removed trailing blank line from `__init__.py`

## 0.1.0 (2026-05-30)

### Added

- Initial release
- Configuration management for Python projects with dataclass-based schemas
- TOML file support with layered configuration (user < project < CLI)
- Environment variable interpolation via envtoml/tomlev
- Auto-generated CLI arguments from dataclass fields
- Helpful, actionable error messages
