# History

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
