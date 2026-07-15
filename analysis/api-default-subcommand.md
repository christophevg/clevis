# API Design Analysis: Configurable Default Subcommand (P1-005)

**Date**: 2026-07-15
**Task**: P1-005 — Configurable Default Subcommand
**GitHub Issue**: #32
**Status**: Design complete, ready for implementation

## Summary

This document analyzes the API design for adding a `default_cmd` boolean flag to `@configclass`, allowing a subcommand to be marked as the default. When no subcommand is given on the CLI, the default subcommand runs instead of argparse erroring. The design preserves full backward compatibility, handles `--help` correctly, rejects unknown subcommands, and detects ambiguous multiple-default configurations at configuration time.

---

## Current Architecture

### How Subcommands Work Now

The subcommand system spans three files with a clear data flow:

```
@configclass(cmd="chat", help="...", aliases=["c"])
    │
    ▼
configclass.py: decorator sets factory.cmd, factory.help, factory.aliases
    │
    ▼
factory.py: Factory dataclass stores subcommand metadata
    │
    ▼
configure_parser(): calls get_sub_parser(parser).add_parser(cmd, ...)
    │
    ▼
get_sub_parser(): creates subparsers with dest="cmd", required=True
    │
    ▼
__init__.py: get_cmd() / get_config() trigger _ensure_configured() → parse_args()
```

### Key Components

| Component | Location | Role |
|-----------|----------|------|
| `@configclass(cmd=...)` | `configclass.py:53` | Decorator accepting `cmd`, `help`, `aliases`, `config` params |
| `Factory` dataclass | `factory.py:375` | Stores `cmd`, `help`, `aliases`, `config`, `sub_parser` per config class |
| `get_sub_parser()` | `factory.py:172` | Creates/retrieves subparsers object with `dest="cmd"`, `required=True` |
| `configure_parser()` | `factory.py:406` | Registers subcommand via `add_parser()`, configures field arguments |
| `_ensure_configured()` | `factory.py:333` | Lazy configuration: loops all factories sharing a parser, calls `configure_parser` on each |
| `get_cmd()` | `__init__.py:394` | Parses args, pops `cmd` from namespace, returns subcommand name |
| `Factory.get_args()` | `factory.py:671` | Parses args, returns dict (used by `get_config`) |

### Current Behavior with No Subcommand

When subcommands are registered, `get_sub_parser()` sets `required=True` on the subparsers action. If the CLI is called with no subcommand:

1. `parse_args([])` is called
2. argparse sees no positional matching the subparsers action
3. `required=True` triggers `parser.error("the following arguments are required: cmd")`
4. argparse prints error to stderr and exits with code 2

This is the behavior that `default_cmd` must replace when a default is configured.

### Parser Configuration Lifecycle

Parser configuration is **lazy** — it happens on the first `get_cmd()` or `get_config()` call:

1. `_ensure_configured(parser)` checks if parser is already configured (via `_registry`)
2. If not, it loops through ALL factories in `_factories` that share this parser
3. For each factory, calls `configure_parser()` which:
   - Creates the subparser via `get_sub_parser(parser).add_parser(cmd, ...)`
   - Configures field arguments on the subparser
4. Marks the parser as configured

This lazy loop is critical: it means all factories for a parser are configured in a single pass before any parsing occurs. The default-detection and `required` flag management can happen during this loop.

---

## Proposed API Design

### New Parameter: `default_cmd`

```python
@configclass(cmd="chat", default_cmd=True)
class ChatConfig:
    model: str = "gpt-4"
    verbose: bool = False
```

**API contract:**
- `default_cmd: bool = False` — added alongside `cmd` on `@configclass`
- Requires `cmd` to be set (raises `ValueError` if `default_cmd=True` without `cmd`)
- Only one `default_cmd=True` per parser (raises `ValueError` at configuration time if multiple)
- When no subcommand is given on the CLI, the default subcommand runs
- When no default is configured, behavior is unchanged (`required=True` stays)

### RESTful / API Design Note

This is a Python library API (decorator parameter), not an HTTP API. The design follows Python decorator conventions consistent with the existing `cmd`, `help`, `aliases`, and `config` parameters. The parameter is a simple boolean flag — no over-engineering.

### Data Flow with `default_cmd`

```
@configclass(cmd="chat", default_cmd=True)
    │
    ▼
configclass.py: validates default_cmd requires cmd, sets factory.default_cmd = True
    │
    ▼
factory.py: Factory.default_cmd field stores the flag
    │
    ▼
configure_parser(): if default_cmd, registers default in _default_cmds[parser] = "chat"
                   sets subparsers.required = False
                   detects multiple defaults → raises ValueError
    │
    ▼
_parse_with_default(): if default exists, uses parse_known_args to detect subcommand
                       if none given, prepends default cmd name and re-parses
    │
    ▼
get_cmd() / get_args(): use _parse_with_default() instead of raw parse_args()
```

---

## Implementation Approach

### 1. `configclass.py` Changes

**Add `default_cmd` parameter to the decorator:**

```python
def configclass(
  cls: type[T] | None = None,
  cmd: str | None = None,
  help: str | None = None,
  aliases: list[str] | None = None,
  config: str | None = None,
  default_cmd: bool = False,
) -> type[T] | Callable[[type[T]], type[T]]:
```

**Validate `default_cmd` requires `cmd` (in `decorator()`):**

```python
if default_cmd and cmd is None:
  raise ValueError(
    f"@configclass parameter 'default_cmd' requires 'cmd' parameter. "
    f"Use @configclass(cmd='name', default_cmd=True) instead. "
    f"Class: {clz.__name__}"
  )
```

**Set `factory.default_cmd`:**

```python
if default_cmd:
  factory.default_cmd = default_cmd
```

**Update decorator return condition** (line 154) — add `and not default_cmd`:

```python
if cls and not cmd and help is None and aliases is None and config is None and not default_cmd:
```

This ensures `@configclass` (no parentheses) still works as before, and `@configclass(default_cmd=True)` (without cmd) enters the parameterized path where the validation error fires.

### 2. `factory.py` Changes

**Add `sys` import** (needed for `sys.argv[1:]` when `args is None`):

```python
import sys
```

**Add `default_cmd` field to `Factory` dataclass:**

```python
@dataclass
class Factory:
  config_class: type
  prefix: str | None = None
  parser: Parser = field(default_factory=_get_default_parser)
  cmd: str | None = None
  help: str | None = None
  aliases: list[str] | None = None
  config: str | None = None
  default_cmd: bool = False                    # NEW
  sub_parser: Parser | None = field(init=False, default=None)
  _nested_prefix: str | None = field(init=False, default=None)
  _configured: bool = False
```

**Add module-level default tracking dict:**

```python
# Maps parser → default subcommand name (the cmd value of the factory with default_cmd=True)
_default_cmds: dict[Parser, str] = {}
```

**Update `configure_parser()` — register default and detect multiples:**

Inside the `if self.cmd:` block, after the existing `add_parser` logic:

```python
if self.cmd:
  # ... existing add_parser kwargs and sub_parser creation ...
  self.sub_parser = get_sub_parser(self.parser).add_parser(self.cmd, **add_parser_kwargs)

  # Register default subcommand
  if self.default_cmd:
    if self.parser in _default_cmds:
      existing_default = _default_cmds[self.parser]
      raise ValueError(
        f"Multiple default subcommands configured on the same parser: "
        f"'{existing_default}' and '{self.cmd}'. "
        f"Only one @configclass can have default_cmd=True per CLI. "
        f"Remove default_cmd=True from all but one."
      )
    _default_cmds[self.parser] = self.cmd
    get_sub_parser(self.parser).required = False
```

The `required=False` is set here so that the subparsers don't error on a missing subcommand. This is safe because `_ensure_configured` calls `configure_parser` on ALL factories sharing the parser before any parsing occurs.

**Add `_parse_with_default()` helper function:**

```python
def _parse_with_default(parser: Parser, args: list[str] | None = None) -> Namespace:
  """
  Parse arguments, applying the default subcommand if none was given.

  If a default subcommand is configured for this parser and no subcommand
  is present in the args, the default subcommand name is prepended to the
  args before parsing. This ensures the default subcommand's arguments are
  properly parsed.

  --help/-h is handled by argparse natively during the first
  parse_known_args pass: if no subcommand precedes --help, top-level help
  is shown (listing all subcommands). If a subcommand precedes --help,
  that subcommand's help is shown.

  An unknown positional (e.g., 'myapp foobar') is not swallowed: it is
  left for argparse to reject with an 'invalid choice' error.

  If no default is configured, this delegates to parse_args directly
  (unchanged behavior, required=True on subparsers).
  """
  configured_parser = _ensure_configured(parser)
  default_cmd = _default_cmds.get(parser)

  # No default configured — normal behavior (subparsers required=True)
  if default_cmd is None:
    return configured_parser.parse_args(args)

  # First pass: use parse_known_args to detect whether a subcommand is present.
  # With required=False, this does NOT error on a missing subcommand.
  # --help is handled natively by argparse here (SystemExit before return).
  namespace, unknown = configured_parser.parse_known_args(args)

  # A valid subcommand was given — do a full parse for proper validation
  if getattr(namespace, "cmd", None) is not None:
    return configured_parser.parse_args(args)

  # No subcommand was given. Check for unknown positionals (invalid subcommand).
  # If present, let argparse produce the "invalid choice" error via full parse.
  unknown_positionals = [a for a in unknown if not a.startswith("-")]
  if unknown_positionals:
    return configured_parser.parse_args(args)

  # No subcommand, no invalid positional — only options or empty args.
  # Prepend the default subcommand name and parse.
  raw_args = sys.argv[1:] if args is None else list(args)
  return configured_parser.parse_args([default_cmd] + raw_args)
```

**Update `Factory.get_args()` to use `_parse_with_default()`:**

```python
def get_args(self, args: list[str] | None = None) -> dict[str, Any]:
  args_dict = vars(_parse_with_default(self.parser, args))
  # ... existing prefix-stripping logic unchanged ...
```

**Update `_reset_factories()` to clear `_default_cmds`:**

```python
def _reset_factories() -> None:
  global _factories, _default_parser, _sub_parsers, _registry, _default_cmds
  _factories.clear()
  _sub_parsers.clear()
  _registry.clear()
  _default_cmds.clear()
  _default_parser = None
```

### 3. `__init__.py` Changes

**Update `get_cmd()` to use `_parse_with_default()`:**

```python
def get_cmd(parser: Any = None, args: list[str] | None = None) -> str | None:
  if not parser:
    parser = _factory_module._get_default_parser()
  parsed_args = vars(_factory_module._parse_with_default(parser, args))
  cmd: str | None = parsed_args.pop("cmd", None)
  return cmd
```

**Update imports** to include `_parse_with_default` (if not already importing from factory module via `_factory_module`):

The existing code already accesses factory via `_factory_module._get_default_parser()`, so `_factory_module._parse_with_default()` works without new imports.

### 4. No Changes Needed

- `get_sub_parser()` — unchanged; `required=True` stays as the default, overridden to `False` in `configure_parser` when a default exists
- `registration.py` — no interaction with subcommand defaults
- TOML loading, security, error handling — no changes needed

---

## Edge Cases and How They're Handled

### 1. No subcommand given, default configured

**Input**: `myapp` (empty args)
**Flow**: `parse_known_args([])` → `cmd=None`, `unknown=[]` → no positionals → prepend `"chat"` → `parse_args(["chat"])` → chat runs with defaults
**Result**: Default subcommand executes. Correct.

### 2. No subcommand given, no default configured

**Input**: `myapp` (empty args)
**Flow**: `default_cmd is None` → `parse_args([])` → argparse errors "the following arguments are required: cmd"
**Result**: Unchanged behavior. Correct (acceptance criterion 3).

### 3. Default subcommand with its options, no subcommand name

**Input**: `myapp --verbose` (where `--verbose` belongs to `chat`)
**Flow**: `parse_known_args(["--verbose"])` → `cmd=None`, `unknown=["--verbose"]` → no positionals (only options) → prepend `"chat"` → `parse_args(["chat", "--verbose"])` → chat runs with `verbose=True`
**Result**: Default subcommand runs with the provided options. Correct.

### 4. `--help` with no subcommand

**Input**: `myapp --help`
**Flow**: `parse_known_args(["--help"])` → argparse processes `--help` at top level → SystemExit(0) with top-level help (lists all subcommands)
**Result**: Top-level help shown. Never reaches default-prepending logic. Correct (acceptance criterion 4).

### 5. `--help` with subcommand

**Input**: `myapp chat --help`
**Flow**: `parse_known_args(["chat", "--help"])` → argparse recognizes `chat` as subcommand, delegates to chat subparser, processes `--help` → SystemExit(0) with chat's help
**Result**: Subcommand-specific help shown. Correct.

### 6. Unknown subcommand

**Input**: `myapp foobar`
**Flow**: `parse_known_args(["foobar"])` → `cmd=None`, `unknown=["foobar"]` → `foobar` is a positional → `parse_args(["foobar"])` → argparse errors "invalid choice: 'foobar'"
**Result**: Argparse error, not swallowed by default. Correct (acceptance criterion 5).

### 7. Multiple `default_cmd=True`

**Input**: Two configclasses with `default_cmd=True` sharing the same parser
**Flow**: During `_ensure_configured` loop, first factory registers `_default_cmds[parser] = "chat"`. Second factory with `default_cmd=True` finds parser already in `_default_cmds` → raises `ValueError`
**Error message**:
```
ValueError: Multiple default subcommands configured on the same parser: 'chat' and 'build'. Only one @configclass can have default_cmd=True per CLI. Remove default_cmd=True from all but one.
```
**Result**: Clear configuration error at configuration time. Correct (acceptance criterion 6).

### 8. `default_cmd=True` without `cmd`

**Input**: `@configclass(default_cmd=True)` without `cmd`
**Flow**: Validation in `configclass.py` raises `ValueError` at decorator time
**Error message**:
```
ValueError: @configclass parameter 'default_cmd' requires 'cmd' parameter. Use @configclass(cmd='name', default_cmd=True) instead. Class: ChatConfig
```
**Result**: Clear error, fails fast. Correct.

### 9. Default subcommand with aliases

**Input**: `@configclass(cmd="chat", default_cmd=True, aliases=["c"])`
**Flow**: Default is registered as `"chat"` (the canonical name). `myapp` → prepend `"chat"` → runs. `myapp c` → `parse_known_args` recognizes `c` as subcommand → `cmd="c"` → full parse → runs via alias.
**Result**: Aliases work with default subcommand. Correct (acceptance criterion 7).

### 10. Default subcommand with TOML section extraction

**Input**: `@configclass(cmd="chat", default_cmd=True, config="conversation")`
**Flow**: Default is `"chat"`. When no subcommand given, prepend `"chat"`, parse. `get_config(ChatConfig)` uses `factory.config or factory.cmd` = `"conversation"` for TOML extraction.
**Result**: TOML `[conversation]` section correctly extracted. Correct (acceptance criterion 7).

### 11. Default subcommand with `get_config` called directly

**Input**: `get_config(ChatConfig, args=[])` where ChatConfig has `default_cmd=True`
**Flow**: `get_factory(ChatConfig).get_args([])` → `_parse_with_default(parser, [])` → prepends `"chat"` → parses `["chat"]` → returns dict with chat's fields
**Result**: `get_config` works correctly for the default subcommand. Correct.

### 12. Options before `--help` with default configured

**Input**: `myapp --verbose --help` (where `--verbose` belongs to chat)
**Flow**: `parse_known_args(["--verbose", "--help"])` → `--verbose` unknown to top-level (goes to unknown), `--help` triggers top-level help → SystemExit(0)
**Result**: Top-level help shown. Correct.

### 13. Top-level options with values (edge case)

**Input**: `myapp --global-config /path/to/config.toml` (where `--global-config` is a top-level option)
**Flow**: `parse_known_args` recognizes `--global-config` as a top-level option, consumes `/path/to/config.toml` as its value. `cmd=None`, `unknown=[]`. No positionals. Prepends default: `parse_args(["chat", "--global-config", "/path/to/config.toml"])`.
**Caveat**: This may or may not work correctly depending on whether the subparser also accepts `--global-config`. If `--global-config` is only on the top-level parser, prepending `chat` means argparse delegates to chat's subparser, which doesn't know `--global-config` → error. This is an edge case with top-level + subcommand configs combined with defaults. The typical subcommand pattern has no top-level options, so this is unlikely to arise. If needed, a future enhancement could handle this with a more sophisticated pre-parse scan.

### 14. `get_cmd()` returns the default name

**Input**: `myapp` with `chat` as default
**Flow**: `_parse_with_default` prepends `"chat"`, parses. `namespace.cmd = "chat"`. `get_cmd` pops and returns `"chat"`.
**Result**: User code `cmd = get_cmd()` receives `"chat"`, dispatches to chat handler. Correct.

---

## Backward Compatibility Assessment

### No Default Configured (Unchanged Behavior)

When no `default_cmd=True` is set on any configclass:
- `_default_cmds` is empty for all parsers
- `_parse_with_default` takes the `default_cmd is None` branch → calls `parse_args` directly
- `required=True` stays on subparsers (no factory sets it to `False`)
- All behavior identical to current code

**Risk**: None. The code path is identical.

### Existing Tests

All existing tests that don't use `default_cmd` will follow the unchanged path. Tests that use `_reset_factories` will also clear `_default_cmds`. No existing test should break.

**Risk**: Very low. The only changes to existing code paths are:
1. `get_cmd()` and `get_args()` call `_parse_with_default` instead of `_ensure_configured(parser).parse_args(args)` — but `_parse_with_default` delegates to `parse_args` when no default is configured
2. `Factory` has a new field `default_cmd=False` — doesn't affect existing instantiation

### API Surface

- `@configclass` gains an optional `default_cmd=False` parameter — backward compatible (defaults to False)
- `Factory` gains an optional `default_cmd=False` field — backward compatible
- No public API signatures change
- No existing parameters change meaning

**Risk**: None for API consumers.

---

## Testing Strategy

### New Test Cases Required

1. **Basic default**: `@configclass(cmd="chat", default_cmd=True)` → `get_cmd(args=[])` returns `"chat"`
2. **No args runs default**: `get_config(ChatConfig, args=[])` returns chat config with defaults
3. **Default with options**: `get_cmd(args=["--verbose"])` returns `"chat"` (with verbose parsed)
4. **Explicit subcommand overrides default**: `get_cmd(args=["run"])` returns `"run"` (with `run` as another subcommand)
5. **No default, unchanged**: `get_cmd(args=[])` raises SystemExit (argparse error) when no default configured
6. **`--help` shows top-level help**: `get_cmd(args=["--help"])` raises SystemExit(0), top-level help output contains all subcommand names
7. **Unknown subcommand errors**: `get_cmd(args=["foobar"])` raises SystemExit(2)
8. **Multiple defaults raise ValueError**: Two configclasses with `default_cmd=True` on same parser → `ValueError` at configure time
9. **`default_cmd` without `cmd` raises ValueError**: `@configclass(default_cmd=True)` → `ValueError` at decorator time
10. **Default with aliases**: `@configclass(cmd="chat", default_cmd=True, aliases=["c"])` → `get_cmd(args=["c"])` returns `"c"`, `get_cmd(args=[])` returns `"chat"`
11. **Default with TOML section**: `@configclass(cmd="chat", default_cmd=True, config="conversation")` → TOML `[conversation]` section extracted correctly
12. **Factory.default_cmd field**: `get_factory(ChatConfig).default_cmd == True`
13. **Non-default factory**: `get_factory(RunConfig).default_cmd == False`
14. **`_reset_factories` clears defaults**: After reset, `_default_cmds` is empty

### Test Placement

- Subcommand default tests: `tests/test_clevis.py` in `TestSubcommands` class
- Edge case tests: `tests/test_edge_cases.py`
- Factory-level tests: `tests/test_factory.py`

---

## Action Items

### Implementation (for python-developer agent)

1. **`configclass.py`**: Add `default_cmd` parameter, validation, factory assignment, decorator return condition update
2. **`factory.py`**: Add `sys` import, `default_cmd` field on Factory, `_default_cmds` dict, default registration + multiple-detection in `configure_parser`, `_parse_with_default()` helper, update `get_args()`, update `_reset_factories()`
3. **`__init__.py`**: Update `get_cmd()` to use `_factory_module._parse_with_default()`
4. **Tests**: Add all test cases listed in Testing Strategy
5. **Documentation**: Update docstrings on `@configclass`, `Factory`, `get_cmd` to mention `default_cmd`

### Documentation (for documentation skill)

1. Update `PACKAGE.md` subcommand section with `default_cmd` example
2. Update `README.md` if subcommands are documented there
3. Update `docs/usage.rst` with default subcommand section
4. Add changelog entry

### Verification

1. Run `make test` — all existing tests pass
2. Run `make check` — linting, type checking pass
3. Manually verify: `myapp` (no args) runs default, `myapp --help` shows top-level help, `myapp foobar` errors