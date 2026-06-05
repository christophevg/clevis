# History

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.3.0 (2026-06-05)

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

## 0.1.0 (2025-01-14)

### Added

- Initial release
- Configuration management for Python projects with dataclass-based schemas
- TOML file support with layered configuration (user < project < CLI)
- Environment variable interpolation via envtoml/tomlev
- Auto-generated CLI arguments from dataclass fields
- Helpful, actionable error messages
