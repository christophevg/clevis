# List-Append CLI Arguments - Implementation Plan

## Overview

This feature adds append behavior for list fields in CLI arguments, allowing users to accumulate values instead of replacing them. It also adds support for `--no-field` prefixes to set boolean fields to False or list fields to empty lists.

**GitHub Issue**: #14
**Satisfies**: R110-R114

## Problem Statement

Currently, list fields in configuration can only be set via TOML files. CLI arguments for list fields would require special handling to:
1. Append values to lists (e.g., `--packages pkgq --packages c3` → `["pkgq", "c3"]`)
2. Clear lists to empty (e.g., `--no-packages` → `[]`)
3. Set boolean fields to False (e.g., `--no-debug` → `debug=False`)
4. Merge CLI values with TOML values instead of replacing

## Current Behavior

### List Fields
- Lists load from TOML: `packages = ["pkgq", "c3"]`
- No CLI argument generation for `list[T]` fields
- The `unpack_type()` function returns list types as-is (line 90-92 in factory.py)

### Boolean Fields
- Only `store_true` action: `--debug` sets `debug=True`
- No way to set a boolean to `False` via CLI

### Argument Generation
- In `Factory._configure_fields()` (line 239-329 in factory.py):
  - Boolean fields get `store_true` action
  - All other types use `type=concrete_type`
  - No special handling for container types

## Proposed Solution

### 1. List Field CLI Arguments

**Append Pattern**:
```python
# Config
@dataclass
class Config:
  packages: list[str] = field(default_factory=list)

# CLI Usage
app --packages pkgq --packages c3 --packages agent

# Result
config.packages == ["pkgq", "c3", "agent"]
```

**Implementation**:
- Detect list types in `_configure_fields()`
- Use `action="append"` for list fields
- Set `default=None` (not `[]`) to detect when no CLI args provided

```python
# In Factory._configure_fields()
origin = get_origin(concrete_type)
if origin is list:
  # List field - use append action
  arg = functools.partial(
    target_parser.add_argument,
    f"--{cli_name}",
    dest=name,
    default=None,  # None means no CLI args provided
    action="append",
    help=f"append to {name} (can be used multiple times)",
  )
  # Get the element type for type conversion
  element_type = get_args(concrete_type)[0]
  _ = arg(type=element_type)
```

### 2. Merge with TOML Values

**Current Behavior**: CLI args override TOML values completely.

**New Behavior**: CLI list values are appended to TOML list values.

```python
# In get_config()
# After loading TOML and CLI args...

# CLI args with append return list or None
cli_packages = parsed_args.get("packages")  # None or ["pkgq", "c3"]

# TOML provides base values
toml_packages = cfg.get("packages", [])  # ["agent"] or []

# Merge: CLI appends to TOML
if cli_packages is not None:
  cfg["packages"] = toml_packages + cli_packages
```

**Implementation Location**: In `get_config()` after line 450 where `apply_to_dict()` is called.

```python
# Current
if cli or args is not None:
  apply_to_dict(get_factory(clz).get_args(args), cfg)

# Proposed - handle list merging
if cli or args is not None:
  cli_args = get_factory(clz).get_args(args)
  # Separate list args from non-list args
  # Merge list args with existing TOML values
  # Apply merged result
```

### 3. `--no-field` Prefix

**Pattern**: Clear lists or set booleans to False.

```python
# Boolean: --no-debug sets debug=False
# List: --no-packages sets packages=[]
```

**Implementation**:
- Generate additional `--no-<field>` argument for boolean and list fields
- Use `store_const` action to set specific value
- For booleans: `--no-debug` → `debug=False`
- For lists: `--no-packages` → `packages=[]`

```python
# In Factory._configure_fields()
if concrete_type is bool:
  # Main argument: --debug (store_true)
  arg = functools.partial(
    target_parser.add_argument,
    f"--{cli_name}",
    dest=name,
    default=None,
    action="store_true",
    help=f"set {name} to True",
  )
  _ = arg()

  # Negation argument: --no-debug (store_false)
  arg_no = functools.partial(
    target_parser.add_argument,
    f"--no-{cli_name}",
    dest=name,
    default=None,
    action="store_const",
    const=False,
    help=f"set {name} to False",
  )
  _ = arg_no()

elif origin is list:
  # Main argument: --packages VALUE (append)
  arg = functools.partial(
    target_parser.add_argument,
    f"--{cli_name}",
    dest=name,
    default=None,
    action="append",
    type=element_type,
    help=f"append to {name}",
  )
  _ = arg()

  # Clear argument: --no-packages (store_const)
  arg_no = functools.partial(
    target_parser.add_argument,
    f"--no-{cli_name}",
    dest=name,
    default=None,
    action="store_const",
    const=[],  # Empty list
    help=f"clear {name} (set to empty list)",
  )
  _ = arg_no()
```

### 4. Handling Conflicts

**Question**: What if both `--packages X` and `--no-packages` are provided?

**Resolution**: Use the **last** argument wins (standard argparse behavior).

```bash
# Example 1: Clear then add
app --no-packages --packages new
# Result: packages = ["new"]

# Example 2: Add then clear
app --packages old --no-packages
# Result: packages = []

# Example 3: Add, clear, add
app --packages a --no-packages --packages b
# Result: packages = ["b"]
```

This matches user expectations: the last flag on the command line wins.

## Implementation Steps

### Phase 1: Detect List Types
1. Modify `unpack_type()` to keep list type information
2. Use `get_origin()` and `get_args()` to extract element type
3. Handle `list[str]`, `list[int]`, etc.

### Phase 2: Generate List CLI Arguments
1. In `Factory._configure_fields()`, add special case for `list[T]`
2. Use `action="append"` for list fields
3. Extract element type for type conversion
4. Generate `--field` with append action
5. Generate `--no-field` with `store_const` for clearing

### Phase 3: Merge CLI and TOML Lists
1. Modify `get_config()` to handle list field merging
2. Get list of all list fields in the config class
3. For each list field with CLI values:
   - Get TOML base list
   - Get CLI appended list
   - Merge: TOML base + CLI values
   - Handle `--no-field` const value (empty list)
4. Apply merged values to config dict

### Phase 4: Boolean `--no-field` Support
1. In `Factory._configure_fields()`, add `--no-field` for boolean fields
2. Use `action="store_const"` with `const=False`
3. Ensure it doesn't conflict with existing `--field`

### Phase 5: Testing
1. Test list append: `--field val1 --field val2`
2. Test list clear: `--no-field`
3. Test boolean false: `--no-field` for booleans
4. Test merge: TOML + CLI
5. Test all list types: `list[str]`, `list[int]`, `list[Path]`, etc.
6. Test conflict resolution: `--field X --no-field --field Y`

## Files to Modify

### `/Users/xtof/Workspace/agentic/clevis/src/clevis/factory.py`
- Modify `unpack_type()` to preserve list type info
- Modify `_configure_fields()` to handle list and boolean fields
- Add helper method `_get_list_fields()` to identify list fields in a config class
- Add helper method `_merge_list_args()` to merge CLI and TOML list values

### `/Users/xtof/Workspace/agentic/clevis/src/clevis/__init__.py`
- Modify `get_config()` to call list merge logic after `apply_to_dict()`
- Handle `--no-field` const values in the merge step

### `/Users/xtof/Workspace/agentic/clevis/tests/test_advanced_types.py`
- Add `TestListAppendCLI` test class
- Add tests for append, clear, merge, and conflict cases
- Add tests for boolean `--no-field` negation

### `/Users/xtof/Workspace/agentic/clevis/tests/test_clevis.py`
- Add integration tests for list field CLI usage
- Test end-to-end scenarios with TOML + CLI

## Acceptance Criteria

### Functional Requirements

1. **List Append**:
   - `--packages pkgq --packages c3` results in `["pkgq", "c3"]`
   - Works for all list types: `list[str]`, `list[int]`, `list[Path]`, etc.
   - Can be used multiple times

2. **List Clear**:
   - `--no-packages` results in `[]` (empty list)
   - Overrides any previous `--packages` arguments when used last

3. **Boolean Negation**:
   - `--no-debug` sets boolean `debug` to `False`
   - Complements existing `--debug` (sets to True)

4. **Merge with TOML**:
   - TOML `packages = ["pkgq"]` + CLI `--packages c3` = `["pkgq", "c3"]`
   - TOML values come first, CLI values appended
   - `--no-packages` clears TOML values (results in `[]`)

5. **Conflict Resolution**:
   - Last argument wins when both `--field` and `--no-field` provided
   - `--field a --no-field --field b` → `["b"]`

### Test Coverage

1. **Unit Tests**:
   - List field append behavior
   - List field clear behavior
   - Boolean field negation
   - Merge logic for TOML + CLI
   - All list types (str, int, Path, etc.)

2. **Integration Tests**:
   - End-to-end: TOML file + CLI args
   - Nested configs with list fields
   - Multiple list fields in same config

3. **Edge Cases**:
   - Empty list from TOML + CLI append
   - List from TOML + clear via CLI
   - Boolean defaults + `--no-field`

## Design Decisions

### D1: Last Argument Wins
**Decision**: When both `--field` and `--no-field` are provided, the last one wins.

**Rationale**:
- Matches argparse standard behavior
- Allows override patterns: `--no-packages --packages urgent`
- Predictable and intuitive for users

### D2: Append, Not Replace
**Decision**: CLI list values **append** to TOML values, not replace.

**Rationale**:
- Plugin architectures (like Yoker) need to extend base config
- Users can always clear with `--no-field` first if needed
- TOML provides base configuration, CLI extends it

**Alternative Considered**: CLI replaces TOML values.
- **Rejected**: Breaks plugin use case
- Users would need to repeat all values on CLI

### D3: Separate `--no-field` Flag
**Decision**: Generate a separate `--no-field` argument instead of overloading `--field`.

**Rationale**:
- Clear intent: `--no-packages` explicitly clears
- No ambiguity about what value to pass
- Works with both booleans and lists

**Alternative Considered**: `--packages ""` for empty list.
- **Rejected**: Doesn't work for booleans
- Ambiguous: is empty string a valid value?

### D4: Type Conversion for List Elements
**Decision**: Use `type=element_type` with `action="append"`.

**Rationale**:
- Ensures type safety: `--ports 80 443` converts to `[80, 443]`
- argparse handles validation: `"abc"` fails for `list[int]`
- Consistent with scalar field type conversion

### D5: None vs Empty List
**Decision**: Use `default=None` to detect "no CLI args provided".

**Rationale**:
- Distinguishes between:
  - No `--packages` argument → `None` → use TOML only
  - `--no-packages` argument → `[]` → empty list, override TOML
- Cannot use `default=[]` because it's mutable
- `None` is the sentinel for "CLI didn't touch this field"

## Implementation Notes

### Type Hints for List Elements

```python
from typing import get_origin, get_args

origin = get_origin(concrete_type)  # list
if origin is list:
  element_type = get_args(concrete_type)[0]  # str, int, Path, etc.
```

### Handling Optional List Fields

```python
# Optional[list[str]] = list[str] | None
# unpack_type() extracts the list[str] part
concrete_type = unpack_type(field.type)  # list[str]
origin = get_origin(concrete_type)  # list
```

### Merge Implementation

```python
def _merge_list_args(
  self,
  cli_args: dict[str, Any],
  toml_cfg: dict[str, Any],
  list_fields: set[str],
) -> dict[str, Any]:
  """
  Merge CLI list arguments with TOML configuration.

  For list fields:
  - None (no CLI arg) → keep TOML value
  - [] (--no-field) → clear, result is []
  - [...] (--field X --field Y) → TOML base + CLI values

  Args:
    cli_args: CLI arguments (dotted keys)
    toml_cfg: TOML configuration
    list_fields: Set of dotted field names that are list types

  Returns:
    Merged configuration with CLI overriding/appending to TOML
  """
  merged = toml_cfg.copy()

  for field_name in list_fields:
    cli_value = cli_args.get(field_name)

    if cli_value is None:
      # No CLI argument for this field - keep TOML value
      continue

    if isinstance(cli_value, list) and len(cli_value) == 0:
      # --no-field: empty list marker, clear the field
      merged[field_name] = []
    elif isinstance(cli_value, list):
      # --field X --field Y: append to TOML base
      toml_value = merged.get(field_name, [])
      if not isinstance(toml_value, list):
        toml_value = []
      merged[field_name] = toml_value + cli_value
    else:
      # Shouldn't happen, but handle gracefully
      merged[field_name] = cli_value

  # Apply non-list CLI args (they override TOML)
  for key, value in cli_args.items():
    if key not in list_fields and value is not None:
      merged[key] = value

  return merged
```

### Boolean Handling in Merge

```python
# Boolean fields are handled separately in _configure_fields()
# --field sets to True, --no-field sets to False
# Both use store_const with default=None

# In get_config():
# Boolean values from CLI override TOML (no merge needed)
# None means no CLI arg, keep TOML value
# True/False are explicit CLI values, override TOML
```

## Testing Strategy

### Test Class: `TestListAppendCLI`

```python
class TestListAppendCLI:
  """Tests for list-append CLI argument behavior."""

  def test_append_multiple_values(self):
    """--field val1 --field val2 should result in [val1, val2]."""
    ...

  def test_append_to_toml(self):
    """TOML base + CLI append should merge correctly."""
    ...

  def test_clear_list(self):
    """--no-field should set list to empty []."""
    ...

  def test_clear_after_append(self):
    """--field a --no-field --field b should result in [b]."""
    ...

  def test_append_different_types(self):
    """Should work for list[str], list[int], list[Path]."""
    ...

class TestBooleanNegation:
  """Tests for --no-field boolean negation."""

  def test_no_flag_sets_false(self):
    """--no-debug should set debug=False."""
    ...

  def test_yes_and_no_flags(self):
    """--debug --no-debug should result in False (last wins)."""
    ...

  def test_no_flag_overrides_toml(self):
    """TOML debug=true + --no-debug should result in False."""
    ...
```

## References

- GitHub Issue #14: List-append behavior for CLI arguments
- `analysis/dynamic-registration.md`: Context for plugin architectures
- `src/clevis/factory.py`: Current CLI argument generation
- `src/clevis/__init__.py`: Configuration loading and merging
- `tests/test_advanced_types.py`: Existing type tests