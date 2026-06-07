# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## 0.2.0 (2025-12-15)

### Added
- Initial release with core configuration management
- TOML file support
- Dataclass-based schema validation
- CLI argument generation from dataclass fields
- Nested configuration support
- User and project-level configuration files

## 0.1.0 (2025-11-01)

### Added
- Proof of concept implementation