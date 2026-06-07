# Edge Case Analysis for Clevis Configuration Package

## Summary

Created comprehensive test suite for clevis configuration package edge cases. **6 tests failed out of 31 total**, revealing actual bugs and unexpected behaviors.

**Test Results:**
- **Passed:** 25 tests (80.6%)
- **Failed:** 6 tests (19.4%)

## Failed Tests (Bugs Found)

### 1. **BUG: Non-dict TOML value for command section doesn't raise error**

**Tests:**
- `test_section_as_string`
- `test_section_as_number`
- `test_section_as_array`

**Expected Behavior:** When TOML has `print = "string"` instead of `[print]`, should raise a clear error indicating the section must be a dict/table.

**Actual Behavior:** Code silently fails and uses default values. The extraction logic in `get_config()` at line 774-778:

```python
if factory.cmd and factory.cmd in cfg:
  cmd_cfg = cfg.pop(factory.cmd)
  if isinstance(cmd_cfg, dict):
    cfg.update(cmd_cfg)
```

The `isinstance(cmd_cfg, dict)` check prevents the error, but **no error is raised** when it's not a dict. The result is that defaults are used without any warning.

**Impact:** Users will not be notified of malformed TOML configuration. A typo like:

```toml
print = "settings"  # Should be [print]
```

will silently use defaults instead of raising an error.

**Recommendation:** Add explicit error handling:

```python
if factory.cmd and factory.cmd in cfg:
  cmd_cfg = cfg.pop(factory.cmd)
  if isinstance(cmd_cfg, dict):
    cfg.update(cmd_cfg)
  else:
    raise ConfigError(
      f"Configuration section '{factory.cmd}' must be a table/dict, "
      f"got {type(cmd_cfg).__name__}: {cmd_cfg}",
      field_path=factory.cmd,
      config_name=name
    )
```

---

### 2. **BUG: Root-level fields leak into subcommand config**

**Test:** `test_root_field_not_in_section`

**Expected Behavior:** When `verbose = true` is at root level and `[print]` section exists but doesn't specify `verbose`, the subcommand should use its default value (`False`).

**Actual Behavior:** Root-level `verbose = true` pollutes the subcommand config, resulting in `verbose = True`.

**Root Cause:** The extraction logic updates the entire `cfg` dict:

```python
if factory.cmd and factory.cmd in cfg:
  cmd_cfg = cfg.pop(factory.cmd)
  if isinstance(cmd_cfg, dict):
    cfg.update(cmd_cfg)
```

But `cfg` already contains root-level fields before the update. When `[print]` doesn't have `verbose`, the root `verbose` remains.

**Impact:** This is a **scoping issue**. Root-level fields should not leak into subcommand-specific configs. Consider:

```toml
# Global settings
verbose = true
debug = false

[print]
# Subcommand settings - should NOT inherit global verbose
```

A user would expect `[print]` to have complete control over its settings, not have them overridden by unrelated root fields.

**Recommendation:** Clear root-level fields before extracting subcommand:

```python
if factory.cmd and factory.cmd in cfg:
  cmd_cfg = cfg.pop(factory.cmd)
  if isinstance(cmd_cfg, dict):
    # For subcommands, only use the section, not root fields
    cfg.clear()  # Remove root fields
    cfg.update(cmd_cfg)
```

Or, alternatively, make this behavior explicit with a parameter:

```python
def get_config(
  clz: type[T],
  name: str = "project",
  ...,
  subcommand_strict: bool = True,  # New parameter
):
```

---

### 3. **NOT A BUG: Double decoration with different params succeeds**

**Test:** `test_double_decoration_different_params`

**Expected Behavior:** Should raise TypeError when applying `@configclass` twice with different params.

**Actual Behavior:** The test was expecting a TypeError, but Python's decorator syntax doesn't work that way. When you write:

```python
@configclass(cmd="print")
@configclass(cmd="check")
class Config:
  pass
```

This is actually valid Python - it applies decorators bottom-up. The inner decorator creates a dataclass, then the outer decorator sees a dataclass (not a class that needs to be decorated again). The second `cmd` parameter wins.

**Verdict:** This is **not a bug**. The test expectation was wrong. The current behavior is: the outer decorator wins (last applied = first in source code).

**Recommendation:** Remove this test or update it to verify the actual behavior (outer decorator wins).

---

### 4. **BUG: Command names with dots don't work correctly**

**Test:** `test_cmd_with_dots`

**Expected Behavior:** When `cmd="print.format"`, the TOML section `[print.format]` should match.

**Actual Behavior:** The config uses default value `"pdf"` instead of TOML value `"html"`.

**Root Cause:** The TOML section `[print.format]` creates a nested structure:

```python
{
  "print": {
    "format": {
      "type": "html"
    }
  }
}
```

But the extraction logic looks for `factory.cmd` (which is `"print.format"`) directly in `cfg`. It should look for `cfg["print"]["format"]` instead.

**Impact:** Users cannot use command names with dots, even though TOML supports them.

**Recommendation:** Split the cmd on dots and navigate the nested dict:

```python
if factory.cmd:
  cmd_parts = factory.cmd.split(".")
  cmd_cfg = cfg
  for part in cmd_parts:
    if part in cmd_cfg and isinstance(cmd_cfg[part], dict):
      cmd_cfg = cmd_cfg[part]
    else:
      cmd_cfg = {}
      break
  cfg.clear()
  cfg.update(cmd_cfg)
```

---

## Passing Tests (Expected Behavior)

The following edge cases work correctly:

### Inheritance Scenarios
- ✅ Child inherits from parent with `cmd` set
- ✅ Both parent and child can have their own `cmd`
- ✅ Field named `cmd` doesn't conflict with parameter `cmd`

### Command Name Collisions
- ✅ `cmd="print"` with field `printer` works correctly

### TOML Structure
- ✅ Root fields AND section in same file (section wins)
- ✅ Empty section uses defaults
- ✅ Whitespace-only section uses defaults

### Aliases
- ✅ TOML with alias section instead of canonical name (defaults used)
- ✅ TOML with both canonical and alias sections (canonical used)

### Overlapping Fields
- ✅ Same field in root and section (section wins)

### Double Decoration
- ✅ Applying `@configclass` twice to same class works (outer wins)

### Manual CMD Setting
- ✅ Setting `factory.cmd` after decoration works
- ✅ Setting `factory.cmd` after `configure_parser()` works but doesn't reconfigure

### Required Fields
- ✅ Required fields in subcommand config work
- ✅ Missing required field raises proper error

### Nested Sections
- ✅ Nested sections within command section work correctly

### Multiple Config Calls
- ✅ Same config class with different TOML files works

### User + Project Config
- ✅ User and project config with same section (project wins)
- ✅ User config only (project missing) works

### Type Handling
- ✅ Extraction handles nested dicts correctly
- ✅ Mixed types (bool, int, str) in command section work

### Inheritance Edge Cases
- ✅ Parent with `cmd` field, child with `@configclass(cmd=...)` works
- ✅ Parent with `@configclass(cmd=...)`, child plain dataclass (child doesn't inherit cmd)

---

## Severity Assessment

| Bug | Severity | Impact |
|-----|----------|--------|
| Non-dict TOML value | **Medium** | Silent failures, hard to debug |
| Root field leakage | **High** | Incorrect config values, unexpected behavior |
| Dots in cmd name | **Low** | Edge case, but documented TOML feature |

## Recommended Actions

1. **High Priority:** Fix root field leakage into subcommand configs (Bug #2)
2. **Medium Priority:** Add error handling for non-dict TOML values (Bug #1)
3. **Low Priority:** Support command names with dots (Bug #4)
4. **Documentation:** Document that root-level fields are cleared for subcommand configs
5. **Tests:** Update/remove test for double decoration with different params (not a bug)

## Test Coverage

Current coverage for edge cases: **63%** (329 statements, 109 missed, 120 branches, 22 partial)

Additional tests needed for:
- Error messages and edge cases
- Security checks with subcommands
- CLI argument parsing with various edge cases
