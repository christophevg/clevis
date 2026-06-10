# TODO

This is the prioritized backlog. Phases group tasks by priority. Each task is atomic with verifiable acceptance criteria and traces back to one or more requirements in `REQUIREMENTS.md`.

## Backlog

### Phase 2: Dynamic Field Registration (P2 - High)

Plugin configuration support for architectures like Yoker.


- [ ] **P2-008: Update @configclass decorator**
  - Add validation: `config` parameter requires `cmd` parameter
  - Raise clear error if `config` used without `cmd`
  - Document `config` parameter is for TOML section override with subcommands
  - **Satisfies**: R107 (new requirement)
  - **Acceptance**:
    - `@configclass(cmd="cli", config="client")` works
    - `@configclass(config="output")` raises error with message
  - **Reference**: `analysis/dynamic-registration.md`

- [ ] **P2-009: Add comprehensive documentation and examples**
  - Update `PACKAGE.md` with all 6 use cases
  - Add `examples/plugin.py` demonstrating dynamic registration
  - Add `examples/subcommands.py` demonstrating subcommands with TOML override
  - Update `README.md` with plugin configuration section
  - **Satisfies**: R108 (new requirement)
  - **Acceptance**:
    - All 6 use cases documented with code examples
    - Plugin example runs successfully
    - README includes plugin configuration guide
  - **Reference**: `analysis/dynamic-registration.md`

- [ ] **P2-010: Add tests for dynamic field registration**
  - Test `register_field()` basic functionality
  - Test error cases (frozen parent, duplicate, late registration)
  - Test TOML loading for registered fields
  - Test CLI arg generation for registered fields
  - Test backward compatibility with existing patterns
  - **Satisfies**: R109 (new requirement)
  - **Acceptance**:
    - All tests pass
    - Coverage for new code ≥90%
    - Existing tests continue to pass

### Phase 3: Polish (P3 - Medium)

Optional improvements for future releases.

- [ ] **P3-004: Achieve 90%+ test coverage**
  - Nice-to-have: bring coverage from current ~80% to ≥90%
  - Single parent task with the following sub-checklist. Each item is a real, named test case.
    - [ ] Tests for parser fallback branches: tomlev path, tomli path, tomllib stdlib path (R75)
    - [ ] Tests for error handling branches: WrongTypeError path, generic DaciteError path (R76)
    - [ ] Tests for user-level config loading: `~/.{name}.toml`, precedence, `user=False` disable (R77)
    - [ ] Tests for boolean CLI arguments: `store_true` action, `--debug` sets to True, absence uses default (R78)
    - [ ] Tests for type preservation with complex union types (R48)
  - Use mocking (`unittest.mock`) to simulate missing parsers
  - **Satisfies**: R44, R48, R75-R78
  - **Acceptance**:
    - `make test-cov` reports ≥ 90% line coverage
    - All sub-checklist items have at least one passing test
    - No previously-tested behavior regresses

### Phase 4: Parking Lot (P4 - Speculative, No Owner)

These are ideas with no current demand or owner. They are kept here so the intent is not lost, but they are **not scheduled** and should not be picked up without explicit user request and a re-evaluation.

- [ ] **P4-001: Async configuration loading**
  - `get_config_async()` variant using `aiofiles`
  - Useful for async applications
  - **No owner, no demand, not scheduled**

- [ ] **P4-002: Configuration hot-reload**
  - Watch TOML files for changes and reload automatically
  - Useful for long-running services
  - **No owner, no demand, not scheduled**

- [ ] **P4-003: Schema validation (constraint-based)**
  - Add `min`, `max`, `pattern` validators
  - Likely unnecessary: `__post_init__` covers most cases
  - **No owner, no demand, not scheduled**

- [ ] **P4-004: Support additional config formats (YAML, JSON)**
  - Add YAML/JSON loaders as extras
  - TOML remains the default
  - **No owner, no demand, not scheduled**

## Done

- [x] **P2-011: Add list-append behavior for CLI arguments** ✅ 2026-06-10 (PR #15)
  - Implement append behavior for `list[T]` fields: `--field value` can be used multiple times
  - Add `--no-field` prefix to set list fields to empty list
  - Add `--no-field` prefix for boolean fields to set to False (complement to `--field`)
  - CLI values should merge (append) with TOML values, not replace
  - Support all list types (`list[str]`, `list[int]`, etc.)
  - **GitHub Issue**: #14
  - **Satisfies**: R110-R114
  - **Acceptance**:
    - `--packages pkgq ---packages c3` results in `["pkgq", "c3"]` (append)
    - `--no-packages` results in `[]` (empty list)
    - `--no-debug` sets boolean `debug` to `False`
    - TOML `packages = ["pkgq"]` + CLI `--packages c3` = `["pkgq", "c3"]` (merge)
    - Works for `list[str]`, `list[int]`, and other list types
    - Tests cover: append, empty list, merge with TOML, all list types

- [x] **P2-007: Implement dynamic field registration** ✅ 2026-06-09 (PR #12)
  - Add `register_field(parent, name, field_type, default_factory)` function
  - Support adding fields to non-frozen dataclasses at runtime
  - Derive TOML namespace from parent hierarchy (no explicit namespace param)
  - Generate CLI args for registered fields (`--parent-name-field`)
  - Handle error cases: frozen parent, duplicate field, late registration
  - **Satisfies**: R100-R106 (new requirements to be added)
  - **Acceptance**:
    - `register_field(ToolsConfig, "pkgq", PkgqToolConfig)` adds field
    - TOML `[tools.pkgq]` loads into `config.tools.pkgq`
    - CLI `--tools-pkgq-enabled` sets value
    - `TypeError` raised for frozen parent
    - `ValueError` raised for duplicate field name
    - `RuntimeError` raised if called after `get_config()`
  - **Reference**: `analysis/dynamic-registration.md`

- [x] **P2-006: Enhance subcommand support** ✅ 2026-06-05 (PR #9)
  - Add `help` parameter to `@configclass(cmd="name", help="description")` for subcommand help text
  - Add `aliases` parameter to `@configclass(cmd="check", aliases=["chk", "c"])` for subcommand aliases
  - Pass help and aliases through to `subparsers.add_parser()`
  - **Satisfies**: R59-R60
  - **Acceptance**:
    - `@configclass(cmd="check", help="Run diagnostics")` shows help in `--help` output
    - `@configclass(cmd="check", aliases=["c"])` allows `python app.py c --verbose`
    - Tests cover help text and aliases

- [x] **P2-005: Add cookbook entries to docs** ✅ 2026-06-05 (PR #8)
  - Add a "Cookbook" section to `docs/usage.rst` with practical patterns:
    - Nested configuration with environment overrides
    - Using `${VAR}` and `${VAR|default}` env var syntax
    - Custom validation via `__post_init__` (with the `server_url` example from `main.py`)
  - **Satisfies**: R58
  - **Acceptance**:
    - `docs/usage.rst` has a Cookbook section
    - At least 3 practical patterns are documented
    - Code examples are runnable and tested manually

- [x] **P2-004: Add type stub files** ✅ 2026-06-05 (PR #7)
  - Create `src/clevis/__init__.pyi` with type stubs
  - Include all public functions, Factory, Parser Protocol, SubParser Protocol, ConfigError class
  - Verify mypy strict mode passes against the stubs
  - **Satisfies**: R49
  - **Acceptance**:
    - `src/clevis/__init__.pyi` exists with type information
    - mypy validates stubs cleanly
    - IDEs show improved autocomplete for clevis users

- [x] **P2-003: Resolve `project.toml` repository file** ✅ 2026-06-05
  - Moved `project.toml` to `examples/project.toml` as part of P2-001 implementation
  - File now serves as example configuration in the examples directory
  - **Satisfies**: R91
  - **Note**: Resolved during P2-001 when creating examples for Factory pattern

- [x] **P2-002: Add security parameter to `get_config()`** ✅ 2026-06-05 (PR #6)
  - Add optional `security` argument to `get_config()` function
  - Default security policy: maximally strict (reject on security issues)
  - Per-check options: Don't Check | Log | Reject
  - Implement configuration file permission validation (group/other readable)
  - Implement parent directory security validation (world-writable)
  - Out of scope: validation support (dataclasses handle this)
  - **GitHub Issue**: #4
  - **Satisfies**: R39-R43
  - **Acceptance**:
    - `get_config(..., security={...})` parameter works
    - Default behavior rejects insecure configurations
    - Individual checks can be configured (Don't Check, Log, Reject)
    - Configuration file permission validation implemented and tested
    - Directory security validation implemented and tested

- [x] **P2-001: Implement Factory Pattern for Multi-Module Configuration** ✅ 2026-06-05 (PR #5)
  - The Factory pattern enables four use cases:
    1. **Simple case**: Direct `get_config()` call with auto-discovered parser
    2. **Module development**: Pre-register configs with `@configclass` decorator
    3. **Multi-module orchestration**: Shared parser with prefixes, custom parser injection
    4. **Subcommands**: CLI applications with multiple commands (like `git`, `docker`)

  - **Implementation Requirements**:
    - Add `@configclass` decorator that applies `@dataclass` and registers with factory
    - Add `get_factory(Config)` to access Factory for customization
    - Add `Factory` dataclass with `config_class`, `prefix`, `parser`, `cmd` attributes
    - Add `Factory.configure_parser()` to lazily add arguments to parser
    - Add `Factory.get_args()` to parse and return dict with dotted keys
    - Add `Factory.list_fields()` to expose field structure
    - Add `Parser` Protocol for pluggable parsers (argparse-compatible)
    - Add `SubParser` Protocol for subparser operations
    - Add `get_cmd()` to return active subcommand name
    - Add `get_sub_parser(parser)` to create or return existing subparser
    - Lazy parser configuration on first `get_config()` call
    - Support multiple configs sharing one parser
    - Support subcommands via `@configclass(cmd="name")`
    - Prefix stripping in `Factory.get_args()` when prefix is set
    - Add `_reset_factories()` for test isolation (must also reset `_sub_parsers`)

  - **Code Quality Fixes Required**:
    - Fix duplicate import: `typing.Callable` imported at line 20 and line 202 (R50)
    - Ensure `_reset_factories()` resets `_sub_parsers` global (R51)
    - Add return type `-> SubParser` to `Parser.add_subparsers()` in Protocol

  - **Breaking Changes** (acceptable in 0.x):
    - `list_fields()` is now `Factory.list_fields()` method (not module-level function)

  - **GitHub Issue**: #3
  - **Satisfies**: R20-R33, R50-R51, R79-R90
  - **Acceptance**:
    - `@configclass` decorator works and registers factory
    - `@configclass(cmd="check")` registers as subcommand
    - `get_factory(MyConfig)` returns same Factory instance for same class
    - `factory.prefix = "app1"` causes CLI args to be `--app1-name`
    - `factory.cmd = "check"` creates subparser for "check" command
    - `get_cmd()` returns active subcommand name
    - Multiple factories can share one parser for orchestrated CLI
    - Multiple subcommands work together in single CLI app
    - `factory.get_args()` returns dict with dotted keys (prefix stripped if set)
    - `examples/factory.py` demonstrates simple, module, orchestration use cases
    - `examples/commands.py` demonstrates subcommand use case
    - Tests cover: decorator, singleton, prefix, shared parser, lazy config, get_args, subcommands
    - Documentation updated with Factory pattern and subcommand sections
    - No debug print statements in production code
    - `_reset_factories()` clears all globals including `_sub_parsers`
    - No duplicate imports

- [x] **P1-003: Make CLI support optional** ✅ 2026-05-30 (PR #2)
  - Added `cli=False` parameter to `get_config()` to skip sys.args handling
  - Adapted error messages for library context
  - Enabled integration in yoker and roomz projects
  - **GitHub Issue**: #1 → #2 (PR)
  - **Satisfies**: R45, R46, R47 (library integration requirements)

- [x] **P1-002: Create missing documentation files** ✅ 2026-05-30
  - `docs/installation.rst`, `docs/usage.rst`, `docs/api.rst` created
  - `docs/index.rst` toctree references all three
  - **Satisfies**: R52, R53, R54, R55, R56, R57

- [x] **P1-001: Create initial git commit** ✅ 2026-05-30
  - Initial commit with source, tests, docs, configuration
  - **Satisfies**: R67