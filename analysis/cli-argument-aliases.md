# CLI Argument Aliases - Analysis Document

## Overview

This document analyzes the implementation of CLI argument aliases for the Clevis configuration library. The feature allows config fields to have alternative CLI argument names, improving user experience by providing shorter or more intuitive argument names.

**GitHub Issue**: #13
**Task**: P2-012
**Priority**: P2 (High)

## Requirements

From TODO.md:

1. Allow config fields to have alternative CLI argument names (aliases)
2. Support multiple aliases per field via metadata: `field(metadata={"cli_aliases": ["with", "add"]})`
3. Aliases replace entire argument name including prefixes
4. Merge behavior: aliases treated as original argument name
5. Conflict resolution: raise Error if alias conflicts with existing field
6. Let argparse handle help text display

## Acceptance Criteria

1. `packages: list[str] = field(metadata={"cli_aliases": ["with"]})` creates `--packages` and `--with`
2. `--with pkgq --packages c3` works same as `--packages pkgq --packages c3`
3. Nested: `tools.packages` with alias `with` creates `--tools-packages` and `--tools-with`
4. Error raised if alias conflicts with existing field name
5. Tests cover: single alias, multiple aliases, nested configs, conflict detection

## Current Implementation

### CLI Argument Generation (factory.py)

The current implementation in `Factory._configure_fields()` generates CLI arguments based on field names:

```python
# Build the argument name
name = ".".join(path + [f.name])
cli_name = name.replace(".", "-").replace("_", "-")

# Apply nested prefix if set
if self._nested_prefix:
  cli_name = f"{self._nested_prefix}-{cli_name}"
  name = f"{self._nested_prefix}.{name}"
```

For each field, it adds arguments like:
- `--field-name` for scalar fields
- `--field-name` (append action) and `--no-field-name` for list fields
- `--field-name` (store_true) and `--no-field-name` for boolean fields

### argparse Behavior

argparse supports multiple names for the same argument through the `name_or_flags` parameter:

```python
parser.add_argument('--name', '--alias', dest='name', ...)
```

All aliases are stored in the same destination, making them equivalent.

## Implementation Approach

### Step 1: Extract Aliases from Field Metadata

Add logic to extract `cli_aliases` from field metadata:

```python
# Extract aliases from field metadata
aliases = f.metadata.get("cli_aliases", [])
if not isinstance(aliases, list):
  aliases = []
```

### Step 2: Validate Aliases

Before generating CLI arguments, validate that aliases don't conflict:

```python
# Build full names for conflict detection
full_names = [cli_name] + [
  f"{self._nested_prefix}-{alias}" if self._nested_prefix else alias
  for alias in aliases
]

# Check for conflicts with existing fields
# This requires tracking all registered field names
for alias_name in full_names[1:]:  # Skip the original name
  if alias_name in _registered_field_names[target_parser]:
    raise ValueError(
      f"CLI alias '{alias_name}' conflicts with existing field "
      f"in {clz.__name__}"
    )
```

### Step 3: Generate Aliases in argparse

Modify the argument registration to include aliases:

```python
# Build argument names (original + aliases)
arg_names = [f"--{cli_name}"]
for alias in aliases:
  # Aliases replace entire argument name (including prefixes)
  if self._nested_prefix:
    alias_full = f"--{self._nested_prefix}-{alias}"
  else:
    alias_full = f"--{alias}"
  arg_names.append(alias_full)

# Register the argument with all names
target_parser.add_argument(
  *arg_names,
  dest=name,
  ...
)
```

### Step 4: Handle Negation Arguments

For boolean and list fields, also generate negation arguments with aliases:

```python
# Boolean fields: --field/--alias and --no-field/--no-alias
negation_names = [f"--no-{cli_name}"]
for alias in aliases:
  if self._nested_prefix:
    negation_names.append(f"--no-{self._nested_prefix}-{alias}")
  else:
    negation_names.append(f"--no-{alias}")

target_parser.add_argument(
  *negation_names,
  dest=name,
  action="store_const",
  const=False,  # or [] for lists
  ...
)
```

## Design Decisions

### Decision 1: Alias Format

**Choice**: Aliases replace the entire argument name, including any nested prefix.

**Rationale**: This provides flexibility and shorter alternatives. For example:
- Field: `tools.packages` with alias `with`
- Generates: `--tools-packages` and `--tools-with`
- User can use either: `--tools-packages pkgq` or `--tools-with pkgq`

**Alternative considered**: Append alias to prefix (e.g., `--tools-packages-with`)
- Rejected: Too verbose, doesn't achieve the goal of shorter alternatives

### Decision 2: Conflict Detection

**Choice**: Raise `ValueError` if an alias conflicts with an existing field name.

**Rationale**: Prevents confusing behavior where two fields have the same CLI argument.

**Implementation**:
- Track all registered field names and aliases in `_registered_field_names`
- Check before registering each alias
- Clear error message indicating the conflict

### Decision 3: Multiple Aliases

**Choice**: Support multiple aliases per field.

**Rationale**: Some fields may benefit from multiple alternatives:
- `packages` could have `--with` and `--add`
- Users can choose the most intuitive option

### Decision 4: Help Text

**Choice**: Let argparse handle help text display.

**Rationale**: argparse automatically lists all aliases in the help output:
```
--packages PACKAGES, --with PACKAGES, --add PACKAGES
                        append to packages (can be used multiple times)
```

This is clearer than custom formatting and requires no additional code.

### Decision 5: Metadata Format

**Choice**: Use list of strings in field metadata.

**Format**: `field(metadata={"cli_aliases": ["with", "add"]})`

**Rationale**:
- Simple and explicit
- Easy to validate (must be list of strings)
- Consistent with Python's dataclass metadata patterns
- Alternative: `field(metadata={"cli_alias": "with"})` - rejected because it doesn't support multiple aliases

## Files to Modify

### 1. `/Users/xtof/Workspace/agentic/clevis/src/clevis/factory.py`

**Changes**:
- Add `_registered_field_names: dict[Parser, set[str]]` to track all CLI argument names
- Modify `_configure_fields()` to extract and validate aliases
- Update argument registration to include aliases
- Update `_reset_factories()` to clear the tracking dict

**Lines to modify**:
- Line 119: Add new tracking dict after `_registered_field_owners`
- Line 205: Initialize tracking in `configure_parser()`
- Lines 298-370: Modify the leaf field registration logic

### 2. `/Users/xtof/Workspace/agentic/clevis/tests/test_cli_aliases.py` (new file)

**Test cases**:
- `test_single_alias`: Field with one alias creates both arguments
- `test_multiple_aliases`: Field with multiple aliases creates all arguments
- `test_alias_merge_behavior`: Using alias or original name produces same result
- `test_nested_alias`: Nested config with alias generates correct prefix
- `test_alias_conflict_detection`: Error raised when alias conflicts with existing field
- `test_boolean_alias`: Boolean fields with aliases also get negation arguments
- `test_list_alias`: List fields with aliases also get clear arguments
- `test_alias_with_toml`: Aliases work with TOML configuration

### 3. `/Users/xtof/Workspace/agentic/clevis/examples/cli_aliases.py` (new file)

**Purpose**: Demonstrate the feature with a practical example

**Content**:
- Simple config with aliased fields
- Show different ways to use the same field
- Demonstrate conflict detection

## Edge Cases

### 1. Alias Conflict with Nested Field

**Scenario**: Top-level field has alias that matches nested field name

```python
@dataclass
class Database:
  host: str

@dataclass
class Config:
  packages: list[str] = field(metadata={"cli_aliases": ["database"]})
  database: Database
```

**Expected**: `ValueError` raised because `--database` would be ambiguous

### 2. Multiple Fields with Same Alias

**Scenario**: Two fields try to use the same alias

```python
@dataclass
class Config:
  packages: list[str] = field(metadata={"cli_aliases": ["with"]})
  tools: list[str] = field(metadata={"cli_aliases": ["with"]})
```

**Expected**: `ValueError` raised when registering the second field

### 3. Alias with Hyphens

**Scenario**: Alias contains hyphens

```python
@dataclass
class Config:
  verbose: bool = field(metadata={"cli_aliases": ["extra-verbose"]})
```

**Expected**: Generates `--verbose` and `--extra-verbose` (no double hyphen)

### 4. Nested Config with Top-Level Alias

**Scenario**: Nested field with alias at different level

```python
@dataclass
class Tools:
  packages: list[str] = field(metadata={"cli_aliases": ["with"]})

@dataclass
class Config:
  tools: Tools
```

**Expected**: Generates `--tools-packages` and `--tools-with`

### 5. Empty Alias List

**Scenario**: Empty list in metadata

```python
@dataclass
class Config:
  packages: list[str] = field(metadata={"cli_aliases": []})
```

**Expected**: Treated as no aliases, generates only `--packages`

### 6. Invalid Alias Type

**Scenario**: Non-string in alias list

```python
@dataclass
class Config:
  packages: list[str] = field(metadata={"cli_aliases": [123]})
```

**Expected**: `ValueError` raised during validation

## Test Plan

### Unit Tests

1. **Alias Extraction**
   - Test extraction from metadata
   - Test handling of missing metadata
   - Test handling of invalid metadata types

2. **Alias Validation**
   - Test conflict detection with existing fields
   - Test conflict detection between aliases
   - Test validation of alias format

3. **Argument Generation**
   - Test single alias generation
   - Test multiple aliases generation
   - Test alias with nested prefix
   - Test boolean field with alias (includes negation)
   - Test list field with alias (includes clear)

4. **Argument Parsing**
   - Test using alias sets the field value
   - Test using original name sets the field value
   - Test mixing alias and original name
   - Test alias with TOML configuration

### Integration Tests

1. **End-to-End Usage**
   - Create config with aliases
   - Parse CLI arguments using aliases
   - Verify correct values in config object

2. **Error Handling**
   - Attempt to create conflicting aliases
   - Verify error message is clear and actionable

### Example Script

Create a runnable example demonstrating:
- Defining fields with aliases
- Using different aliases interchangeably
- Conflict detection
- Integration with TOML

## Implementation Checklist

- [ ] Add `_registered_field_names` tracking dict
- [ ] Add `cli_aliases` extraction from metadata
- [ ] Add alias validation logic
- [ ] Modify argument registration to include aliases
- [ ] Update `_reset_factories()` to clear tracking
- [ ] Create unit tests
- [ ] Create integration tests
- [ ] Create example script
- [ ] Update documentation (if needed)
- [ ] Run full test suite
- [ ] Manual testing

## References

- GitHub Issue: #13
- Task: P2-012 in TODO.md
- Related: P2-011 (list-append behavior)
- Python argparse documentation: https://docs.python.org/3/library/argparse.html