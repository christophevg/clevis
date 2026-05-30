# TODO

## Backlog

### Phase 1: Release Preparation (P1 - Critical)

These tasks must be completed before any release.

- [ ] **P1-003: Make CLI Support Optional**
  - Add `cli=False` parameter to `get_config()` to skip sys.args handling
  - When `cli=False`, do not invoke argparse (no CLI argument parsing)
  - Still accept `args` parameter for external injection/pass-through
  - Adapt error messages to execution context (no CLI arguments when `cli=False`)
  - Primary use case: library usage (integration in yoker and roomz projects)
  - **GitHub Issue**: #1
  - **Satisfies**: Library integration requirement
  - **Acceptance**:
    - `get_config(cli=False)` does not parse sys.args
    - `get_config(cli=False, args=['--option', 'value'])` works for programmatic usage
    - Error messages indicate library context when `cli=False`
    - Follows Python Package best practices
    - Enables integration in yoker and roomz projects


### Phase 2: Quality Assurance (P2 - High)

These tasks improve quality and should be done before PyPI publication.

- [ ] **P2-001: Add Parser Fallback Branch Tests**
  - Test tomlev parser code path (lines 54-63)
  - Test tomli parser code path (line 71)
  - Test tomllib stdlib fallback (line 79)
  - Use mocking to simulate missing parsers
  - **Satisfies**: R3 (Test coverage requirement)
  - **Acceptance**: Coverage report shows all parser branches covered

- [ ] **P2-002: Add Error Handling Branch Tests**
  - Test WrongTypeError handling (lines 339-346)
  - Test generic DaciteError handling (lines 347-353)
  - Create test cases that trigger each error type
  - **Satisfies**: R3 (Test coverage requirement)
  - **Acceptance**: Coverage report shows error branches covered

- [ ] **P2-003: Add User-Level Config Loading Tests**
  - Test loading from `~/.{name}.toml` (lines 307-309)
  - Test precedence: user < project < CLI
  - Test user config disabled with `user=False`
  - **Satisfies**: R3 (Test coverage requirement)
  - **Acceptance**: Coverage report shows user config loading covered

- [ ] **P2-004: Add Boolean CLI Argument Tests**
  - Test `store_true` action for boolean fields (line 233)
  - Test boolean flags in CLI argument generation
  - Test that `--debug` sets value to True, absence uses default
  - **Satisfies**: R3 (Test coverage requirement)
  - **Acceptance**: Coverage report shows store_true branch covered

- [ ] **P2-005: Clean Up project.toml File**
  - File appears to be a test/example configuration
  - Either move to `examples/` directory or add to `.gitignore`
  - Update README if it's meant to be an example
  - **Satisfies**: R4 (Repository cleanliness)
  - **Acceptance**: No unused files in root, purpose is clear

- [ ] **P2-006: Achieve 90%+ Test Coverage**
  - Target: 90%+ coverage (currently 78%)
  - Combine results from P2-001 through P2-004
  - Address any remaining coverage gaps
  - **Satisfies**: R3 (Test coverage requirement)
  - **Acceptance**: `make test-cov` shows 90%+ coverage

### Phase 3: Enhancements (P3 - Medium)

These are nice-to-have improvements for better developer experience.

- [ ] **P3-001: Add Type Stub Files**
  - Create `src/clevis/__init__.pyi` with type stubs
  - Improves IDE autocomplete and type checking
  - Include all public functions and ConfigError class
  - **Satisfies**: R5 (Developer experience)
  - **Acceptance**: mypy validates stubs, IDE provides better autocomplete

- [ ] **P3-002: Add More Usage Examples**
  - Add examples for common patterns (nested configs, env vars)
  - Consider adding an examples/ directory
  - Include examples in documentation
  - **Satisfies**: R2 (Documentation quality)
  - **Acceptance**: Documentation includes practical examples

- [ ] **P3-003: Add Validation Documentation**
  - Document how to validate config beyond types
  - Show patterns for custom validation
  - Consider adding a validation callback parameter
  - **Satisfies**: R2 (Documentation completeness)
  - **Acceptance**: Users can implement custom validation

### Phase 4: Future Considerations (P4 - Low)

These are potential future enhancements that could be explored.

- [ ] **P4-001: Add Async Configuration Loading**
  - Create `get_config_async()` variant
  - Use `aiofiles` for async file reading
  - Useful for async applications
  - **Satisfies**: R6 (Future extensibility)
  - **Acceptance**: Async variant works in async context

- [ ] **P4-002: Add Configuration Hot-Reload**
  - Watch TOML files for changes
  - Reload configuration automatically
  - Useful for long-running services
  - **Satisfies**: R6 (Future extensibility)
  - **Acceptance**: Config updates without restart

- [ ] **P4-003: Add Schema Validation**
  - Support for validation beyond types
  - Add `min`, `max`, `pattern` validators
  - Consider integration with pydantic
  - **Satisfies**: R6 (Future extensibility)
  - **Acceptance**: Validation catches constraint violations

- [ ] **P4-004: Support Additional Config Formats**
  - Add YAML support via extras
  - Add JSON support
  - Maintain TOML as default
  - **Satisfies**: R6 (Future extensibility)
  - **Acceptance**: Can load from YAML/JSON files

## Done

- [x] **P1-002: Create Missing Documentation Files** ✅ 2026-05-30
  - docs/installation.rst - Installation guide with pip/uv instructions
  - docs/usage.rst - Detailed usage examples and patterns
  - docs/api.rst - API reference (can use autodoc)
  - These files are referenced in docs/index.rst toctree
  - **Satisfies**: R2 (Documentation completeness)
  - **Acceptance**: `make docs` builds without warnings, ReadTheDocs can render

- [x] **P1-001: Create Initial Git Commit** ✅ 2026-05-30
  - The repository has no commits yet - all files are untracked
  - Create initial commit with all project files
  - Include: source code, tests, docs, configuration files
  - **Satisfies**: R1 (Git history requirement)
  - **Acceptance**: `git log` shows initial commit with all files