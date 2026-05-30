# Requirements

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

### Error Handling

- [x] R20: MissingValueError conversion to helpful ConfigError
- [x] R21: WrongTypeError conversion to helpful ConfigError
- [x] R22: Generic DaciteError handling
- [x] R23: Field path extraction from error messages
- [x] R24: Multi-source resolution suggestions in errors

## Non-Functional Requirements

### Code Quality

- [ ] R25: 90%+ test coverage (currently 78%)
- [x] R26: Full type hints on all public functions
- [x] R27: Docstrings on all public functions
- [x] R28: Code style compliance (ruff/mypy)
- [ ] R29: All parser fallback branches tested

### Documentation

- [x] R30: README.md with full usage documentation
- [x] R31: docs/conf.py for Sphinx/ReadTheDocs
- [x] R32: docs/index.rst with toctree
- [ ] R33: docs/installation.rst (missing)
- [ ] R34: docs/usage.rst (missing)
- [ ] R35: docs/api.rst (missing)

### Project Infrastructure

- [x] R36: pyproject.toml with proper metadata
- [x] R37: Makefile with standard targets
- [x] R38: .github/workflows/test.yml for CI
- [x] R39: .readthedocs.yaml for documentation
- [x] R40: LICENSE file (MIT)
- [x] R41: .gitignore for Python projects
- [ ] R42: Initial git commit (not done yet)

### Release Readiness

- [x] R43: Version in pyproject.toml and __init__.py
- [x] R44: Makefile has pre-publish checks
- [x] R45: Makefile has publish target
- [x] R46: PyPI badges in README.md
- [ ] R47: PyPI publication (not done yet)

### Testing

- [x] R48: Unit tests for core functionality
- [x] R49: Unit tests for parser selection
- [ ] R50: Tests for user-level config loading
- [ ] R51: Tests for boolean CLI arguments
- [ ] R52: Tests for error handling branches
- [ ] R53: Tests for parser fallback paths

## Completed

(None yet - project not released)