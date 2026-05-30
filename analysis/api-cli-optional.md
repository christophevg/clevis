# API Analysis: Make CLI Support Optional (P1-003)

**Date**: 2026-05-30
**Reviewer**: API Architect Agent
**Task**: P1-003 - Add `cli=False` parameter to `get_config()` to skip sys.args handling

## Summary

This analysis reviews the current `get_config()` API and proposes changes to make CLI support optional. The primary use case is library integration (yoker and roomz projects) where parsing `sys.argv` is undesirable or causes issues.

**Recommendation**: Add a `cli: bool = True` parameter to `get_config()` with adaptive error messages.

## Current API

### Signature

```python
def get_config(
  data_class: type,
  name: str = "project",
  user: bool = True,
  project: bool = True,
  args: list[str] | None = None,
) -> Any:
```

### Behavior

1. **TOML Loading**: Loads from `~/.{name}.toml` (user) and `./{name}.toml` (project)
2. **CLI Parsing**: **Always** calls `get_args_config(data_class, args)`
3. **Argument Precedence**: CLI args > project TOML > user TOML > dataclass defaults
4. **Error Messages**: Always suggest CLI arguments as an option

### Problem

When `get_config()` is called in non-CLI contexts (library usage, web servers, tests):

- `argparse.ArgumentParser.parse_args()` is invoked
- `sys.argv[1:]` is accessed by default (when `args=None`)
- Error messages reference CLI arguments even when not applicable
- Test environments may have unexpected `sys.argv` values

## Proposed API

### New Signature

```python
def get_config(
  data_class: type,
  name: str = "project",
  user: bool = True,
  project: bool = True,
  cli: bool = True,
  args: list[str] | None = None,
) -> Any:
```

### Parameter Semantics

| `cli` | `args` | Behavior |
|-------|--------|----------|
| `True` | `None` | Parse `sys.argv[1:]` (current behavior) |
| `True` | `['--opt']` | Parse provided args (current behavior) |
| `False` | `None` | **Skip CLI parsing entirely** |
| `False` | `['--opt']` | Parse provided args (programmatic usage) |

### Key Behaviors

1. **Backward Compatible**: Default `cli=True` preserves existing behavior
2. **Library Mode**: `cli=False` with `args=None` skips all CLI parsing
3. **Programmatic Override**: `cli=False` with explicit `args` allows programmatic control
4. **Error Adaptation**: Error messages adapt based on `cli` parameter

### Why Not Use Empty `args=[]`?

The existing `args` parameter could technically be used to avoid `sys.argv`:

```python
# This works today
config = get_config(Config, args=[])
```

**Problems with this approach**:
1. **Unintuitive**: The purpose of `args=[]` is not obvious
2. **Error Messages Still Show CLI**: Error messages still reference CLI arguments
3. **Performance Overhead**: Still creates the argparse parser unnecessarily
4. **Not Self-Documenting**: Intent is not clear in code

**With `cli=False`**:
1. **Explicit Intent**: Clearly states "no CLI parsing"
2. **Adaptive Errors**: Error messages omit CLI suggestions
3. **No Parser Overhead**: Skips argparse entirely when `cli=False` and `args=None`
4. **Self-Documenting**: Code clearly expresses library usage

## Implementation Details

### Core Function Changes

```python
def get_config(
  data_class: type,
  name: str = "project",
  user: bool = True,
  project: bool = True,
  cli: bool = True,
  args: list[str] | None = None,
) -> Any:
  """
  Load configuration from TOML files and CLI arguments.

  Merges configuration from (in order of precedence):
  1. CLI arguments (highest priority) - only when cli=True or args is provided
  2. Project-level TOML: ./{name}.toml
  3. User-level TOML: ~/.{name}.toml
  4. Dataclass defaults (lowest priority)

  Args:
      data_class: The dataclass type to populate
      name: Configuration file name (without .toml extension)
      user: Whether to load user-level config (~/.{name}.toml)
      project: Whether to load project-level config (./{name}.toml)
      cli: Whether to parse CLI arguments from sys.argv
      args: Optional list of CLI arguments (overrides sys.argv when provided)

  Returns:
      An instance of the dataclass with merged configuration

  Raises:
      ConfigError: If required fields are missing or values have wrong type
      ImportError: If no TOML parser is available
  """
  cfg: dict[str, Any] = {}

  # Load user-level config
  if user:
    user_path = Path.home() / f".{name}.toml"
    if user_path.exists():
      cfg.update(_load_toml(user_path.open("rb")))

  # Load project-level config
  if project:
    project_path = Path.cwd() / f"{name}.toml"
    if project_path.exists():
      cfg.update(_load_toml(project_path.open("rb")))

  # Parse CLI args if requested
  if cli or args is not None:
    cli_args = get_args_config(data_class, args)
    apply_to_dict(cli_args, cfg)

  # Convert dict to dataclass
  try:
    return from_dict(data_class=data_class, data=cfg)
  except MissingValueError as e:
    # ... error handling
```

### Error Message Adaptation

The `ConfigError` class needs to know whether to suggest CLI arguments:

```python
class ConfigError(Exception):
  """Raised when configuration is missing or invalid."""

  def __init__(
    self,
    message: str,
    field_path: str,
    config_name: str,
    suggest_cli: bool = True,
  ):
    self.message = message
    self.field_path = field_path
    self.config_name = config_name
    self.suggest_cli = suggest_cli
    super().__init__(self._format_message())

  def _format_message(self) -> str:
    """Format a helpful error message with actionable suggestions."""
    lines = [f"\n{'=' * 70}"]
    lines.append("Configuration Error")
    lines.append(f"{'=' * 70}\n")

    lines.append(f"Field: {self.field_path}")
    lines.append(f"Issue: {self.message}\n")

    lines.append("Provide this value in one of these ways:\n")

    # Project config
    lines.append(f"  1. Project config: ./{self.config_name}.toml")
    parts = self.field_path.split(".")
    if len(parts) == 1:
      lines.append(f'     {parts[0]} = "your_value"')
    else:
      lines.append(f"     [{parts[0]}]")
      lines.append(f'     {".".join(parts[1:])} = "your_value"')
    lines.append("")

    # User config
    lines.append(f"  2. User config: ~/.{self.config_name}.toml")
    lines.append("     (same format as above)\n")

    # CLI argument - only suggest when appropriate
    if self.suggest_cli:
      cli_arg = "--" + self.field_path.replace(".", "-").replace("_", "-")
      lines.append(f"  3. CLI argument: {cli_arg} <value>\n")

    lines.append(f"{'=' * 70}")
    return "\n".join(lines)
```

And in `get_config()`:

```python
except MissingValueError as e:
  error_msg = str(e)
  if '"' in error_msg:
    field_path = error_msg.split('"')[1]
  else:
    field_path = error_msg
  raise ConfigError(
    message="Required field has no value",
    field_path=field_path,
    config_name=name,
    suggest_cli=cli,  # Pass through the cli parameter
  ) from None
```

### Edge Cases and Validation

| Scenario | Behavior |
|----------|----------|
| `cli=False, args=None` | Skip CLI entirely (library mode) |
| `cli=False, args=['--opt']` | Parse provided args (programmatic) |
| `cli=True, args=None` | Parse sys.argv (current default) |
| `cli=True, args=['--opt']` | Parse provided args (current) |
| `cli=True, args=[]` | Parse empty list (current - no overrides) |

**No validation needed**: `cli=False` with `args=['--opt']` is valid and useful for:
- Testing with programmatic arguments
- Library code that constructs arguments
- Web servers that parse args from requests

## Testing Strategy

### New Test Cases

```python
class TestCliParameter:
  """Tests for cli parameter in get_config."""

  def test_cli_false_skips_sys_argv(self):
    """cli=False should not parse sys.argv."""
    @dataclass
    class Config:
      name: str = "default"
    
    # sys.argv may contain pytest args, but cli=False ignores them
    config = get_config(Config, name="test", user=False, project=False, cli=False)
    assert config.name == "default"

  def test_cli_false_with_explicit_args(self):
    """cli=False with args should still parse provided args."""
    @dataclass
    class Config:
      name: str = "default"
    
    config = get_config(
      Config, name="test", user=False, project=False,
      cli=False, args=["--name", "from_args"]
    )
    assert config.name == "from_args"

  def test_cli_false_error_message(self):
    """cli=False should produce error without CLI suggestion."""
    @dataclass
    class Config:
      required: str  # No default
    
    with pytest.raises(ConfigError) as exc_info:
      get_config(Config, name="test", user=False, project=False, cli=False)
    
    error_msg = str(exc_info.value)
    assert "CLI argument" not in error_msg
    assert "--required" not in error_msg

  def test_cli_true_error_message(self):
    """cli=True should produce error with CLI suggestion."""
    @dataclass
    class Config:
      required: str  # No default
    
    with pytest.raises(ConfigError) as exc_info:
      get_config(Config, name="test", user=False, project=False, cli=True)
    
    error_msg = str(exc_info.value)
    assert "CLI argument" in error_msg
    assert "--required" in error_msg
```

## Backward Compatibility

### Full Compatibility

- **Default behavior unchanged**: `cli=True` preserves current behavior
- **Existing code works**: All existing calls continue to work identically
- **No breaking changes**: Error messages for current users unchanged

### Migration Path

For library users:

```python
# Before (works but unintuitive)
config = get_config(Config, args=[])

# After (clear intent)
config = get_config(Config, cli=False)
```

For programmatic usage:

```python
# Before (current approach)
config = get_config(Config, args=["--name", "value"])

# After (same behavior, clearer intent)
config = get_config(Config, cli=False, args=["--name", "value"])
```

## Documentation Updates

### API Reference Update

```markdown
### `get_config(data_class, name="project", user=True, project=True, cli=True, args=None)`

Load configuration from TOML files and CLI arguments.

**Parameters:**
- `data_class` — The dataclass type to populate
- `name` — Config file name (without `.toml`)
- `user` — Load user-level config (`~/.{name}.toml`)
- `project` — Load project-level config (`./{name}.toml`)
- `cli` — Parse CLI arguments from `sys.argv` (default: `True`)
- `args` — CLI arguments (defaults to `sys.argv[1:]` when `cli=True`)

**Returns:** Instance of the dataclass with merged configuration

**Raises:**
- `ConfigError` — Missing required fields or wrong types
- `ImportError` — No TOML parser available

**Library Usage:**
```python
# Skip CLI parsing for library/integration use
config = get_config(Config, name="myapp", cli=False)

# Programmatic control with explicit args
config = get_config(Config, name="myapp", cli=False, args=["--debug"])
```
```

### README Usage Examples

Add a "Library Integration" section:

```markdown
### Library Integration

When using Clevis as a library (not a CLI app), disable CLI parsing:

```python
# Web server integration
app_config = get_config(AppConfig, name="myapp", cli=False)

# Library integration
config = get_config(Config, cli=False)

# Testing
def test_my_config():
    config = get_config(TestConfig, cli=False, user=False, project=False)
    assert config.name == "default"
```
```

## Acceptance Criteria Mapping

| Criterion | How Met |
|-----------|---------|
| `get_config(cli=False)` does not parse sys.args | `cli=False` with `args=None` skips `get_args_config()` |
| `get_config(cli=False, args=['--option', 'value'])` works | `cli=False` with explicit `args` still calls `get_args_config()` |
| Error messages indicate library context when `cli=False` | `ConfigError.suggest_cli=False` omits CLI suggestions |
| Follows Python Package best practices | Backward compatible, explicit parameter, documented |
| Enables integration in yoker and roomz | Clear library mode with `cli=False` |

## Action Items

1. **Update `get_config()` signature**: Add `cli: bool = True` parameter
2. **Modify CLI parsing logic**: Only call `get_args_config()` when `cli=True` or `args` is provided
3. **Update `ConfigError` class**: Add `suggest_cli` parameter to control error message content
4. **Add tests**: Cover all combinations of `cli` and `args` parameters
5. **Update documentation**: README and API reference with library usage examples
6. **Update docstring**: Document the new `cli` parameter and its interaction with `args`

## Conclusion

**Status**: Approved for implementation

The proposed API change is:
- **Backward compatible**: Default `cli=True` preserves current behavior
- **Clear and explicit**: Parameter name clearly expresses intent
- **Flexible**: Supports both library and programmatic use cases
- **Well-documented**: Error messages adapt to execution context

The change follows RESTful-like principles for API design (explicit parameters over side effects) and maintains the principle of least surprise for existing users.

## Related Files

- `/Users/xtof/Workspace/agentic/clevis/src/clevis/__init__.py` - Main implementation
- `/Users/xtof/Workspace/agentic/clevis/tests/test_clevis.py` - Test suite
- `/Users/xtof/Workspace/agentic/clevis/README.md` - User-facing documentation