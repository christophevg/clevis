# Development Summary: P1-003 - Make CLI Support Optional

**Date**: 2026-05-30
**Task**: P1-003 - Add `cli=False` parameter to `get_config()` to skip sys.args handling
**Branch**: feature/1-optional-cli-support

## Implementation Overview

Successfully implemented optional CLI support for the Clevis configuration library, enabling clean library integration without CLI argument parsing overhead.

## What Was Implemented

### 1. Core API Changes

**Added `cli` parameter to `get_config()`**
- New signature: `get_config(data_class, name="project", user=True, project=True, cli=True, args=None)`
- Default `cli=True` maintains backward compatibility
- When `cli=False` and `args=None`, CLI parsing is completely skipped
- When `cli=False` with explicit `args`, programmatic usage is enabled

**Updated `ConfigError` class**
- Added `suggest_cli: bool = True` parameter
- Error messages now adapt based on context
- CLI suggestions only shown when `suggest_cli=True`

### 2. Control Flow Changes

Modified `get_config()` to conditionally parse CLI arguments:
```python
# Parse CLI args if requested
if cli or args is not None:
  cli_args = get_args_config(data_class, args)
  apply_to_dict(cli_args, cfg)
```

This ensures:
- `cli=False, args=None` → Skip CLI parsing entirely (library mode)
- `cli=False, args=['--opt']` → Parse provided args (programmatic)
- `cli=True, args=None` → Parse sys.argv (default behavior)
- `cli=True, args=['--opt']` → Parse provided args (current behavior)

### 3. Context-Aware Error Messages

Error messages now adapt based on the `cli` parameter:

**With CLI (default):**
```
Provide this value in one of these ways:
  1. Project config: ./project.toml
  2. User config: ~/.project.toml
  3. CLI argument: --field-name <value>
```

**Without CLI (`cli=False`):**
```
Provide this value in one of these ways:
  1. Project config: ./project.toml
  2. User config: ~/.project.toml
```

### 4. Test Coverage

Added 5 new test cases in `TestCliParameter`:
1. `test_cli_false_skips_sys_argv` - Verifies CLI parsing is skipped
2. `test_cli_false_with_explicit_args` - Verifies programmatic usage
3. `test_cli_false_error_message` - Verifies error messages adapt
4. `test_cli_true_error_message` - Verifies CLI suggestions shown
5. `test_backward_compatibility_default_cli_true` - Verifies default behavior unchanged

All existing tests remain passing, confirming backward compatibility.

### 5. Documentation Updates

**README.md additions:**
- New "Library Integration" section with usage examples
- Updated API reference to document `cli` parameter
- Updated "Error Messages" section showing context-aware examples
- Explained why `cli=False` is better than `args=[]`

**Usage examples added:**
```python
# Library mode - skip sys.argv parsing
config = get_config(Config, name="myapp", cli=False)

# Programmatic control with explicit args
config = get_config(Config, name="myapp", cli=False, args=["--debug"])

# Testing
def test_my_config():
    config = get_config(TestConfig, cli=False, user=False, project=False)
    assert config.name == "default"
```

## Files Modified

### Source Code
- **`src/clevis/__init__.py`**
  - Updated `get_config()` signature with `cli` parameter
  - Modified control flow to skip CLI parsing when appropriate
  - Updated `ConfigError` class with `suggest_cli` parameter
  - Updated all error handling to pass `cli` context
  - Updated docstring to document new parameter

### Tests
- **`tests/test_clevis.py`**
  - Added `TestCliParameter` class with 5 new test cases
  - All 25 tests passing (20 existing + 5 new)

### Documentation
- **`README.md`**
  - Added "Library Integration" section
  - Updated API reference
  - Updated "Error Messages" section

## Quality Checks

All quality checks passed:
- ✅ **Tests**: 25/25 tests passing
- ✅ **Lint**: ruff check passed with no issues
- ✅ **Typecheck**: mypy passed with no issues
- ✅ **Format**: ruff format applied (3 files reformatted)
- ✅ **Coverage**: 79% (no decrease from baseline)

## Acceptance Criteria Met

✅ `get_config(cli=False)` does not parse sys.args
   - Verified by `test_cli_false_skips_sys_argv`

✅ `get_config(cli=False, args=['--option', 'value'])` works for programmatic usage
   - Verified by `test_cli_false_with_explicit_args`

✅ Error messages indicate library context when `cli=False`
   - Verified by `test_cli_false_error_message` and `test_cli_true_error_message`

✅ Follows Python Package best practices
   - Backward compatible (default `cli=True`)
   - Explicit parameter with clear intent
   - Well-documented with examples
   - Type annotated
   - Comprehensive test coverage

✅ Enables integration in yoker and roomz projects
   - Library mode available with `cli=False`
   - No CLI overhead when not needed
   - Clear error messages for library users

## Design Decisions

### Why Add `cli` Parameter Instead of Using `args=[]`?

The existing `args=[]` workaround works but has issues:

**Problems with `args=[]`:**
1. **Unintuitive**: Purpose not obvious
2. **Error Messages**: Still suggest CLI arguments
3. **Overhead**: Creates argparse parser unnecessarily
4. **Not Self-Documenting**: Intent unclear in code

**Advantages of `cli=False`:**
1. **Explicit Intent**: Clearly states "no CLI parsing"
2. **Adaptive Errors**: Error messages omit CLI suggestions
3. **No Overhead**: Skips argparse entirely when `cli=False` and `args=None`
4. **Self-Documenting**: Code clearly expresses library usage

### Parameter Semantics

| `cli` | `args` | Behavior |
|-------|--------|----------|
| `True` | `None` | Parse `sys.argv[1:]` (current default) |
| `True` | `['--opt']` | Parse provided args (current) |
| `False` | `None` | Skip CLI parsing entirely (library mode) |
| `False` | `['--opt']` | Parse provided args (programmatic) |

This design allows:
- **Default behavior unchanged**: `cli=True` preserves existing functionality
- **Library mode**: `cli=False` for clean integration
- **Programmatic control**: `cli=False, args=['--opt']` for testing/scripting
- **No validation needed**: All combinations are valid and useful

## Backward Compatibility

**100% backward compatible** - No breaking changes:
- Default parameter `cli=True` preserves existing behavior
- All existing code continues to work identically
- Error messages unchanged for CLI users
- Performance unchanged for CLI users

## Integration Examples

### Web Server (Flask/FastAPI)
```python
from flask import Flask
from clevis import get_config

@dataclass
class Config:
  database_url: str
  debug: bool = False

# No CLI parsing - web servers don't use sys.argv for app config
app = Flask(__name__)
config = get_config(Config, name="myapp", cli=False)
```

### Library Integration
```python
from clevis import get_config

def configure_yoker():
  # Library mode - skip sys.argv
  return get_config(YokerConfig, name="yoker", cli=False)
```

### Testing
```python
def test_config_loading():
  # Isolated test environment
  config = get_config(
    TestConfig,
    cli=False,
    user=False,
    project=False
  )
  assert config.name == "default"
```

## Next Steps

Ready for integration into:
1. **yoker** - CLI tool can use Clevis with `cli=True` (default)
2. **roomz** - Web server can use Clevis with `cli=False`

## Conclusion

Implementation complete and verified. All acceptance criteria met, all tests passing, documentation updated. The feature is backward compatible and ready for production use.