# API Design: Configurable Config Override Cascade + Public TOML API

**Date**: 2026-07-15
**Task**: P1-006 (issue #33)
**Reviewer**: API Architect Agent
**Status**: Design Complete

## Summary

This document defines the API for a configurable config override cascade in Clevis.
The design introduces a `ConfigProvider` Protocol, a `DEFAULT_CASCADE` constant,
public TOML loading functions (`load`/`loads`), and a `cascade` parameter on
`get_config`. The middle cascade switches from shallow (`dict.update`) to deep
(recursive) merge, which is a documented breaking change.

---

## Current Architecture

### Config Loading Pipeline (today)

```
get_config(clz, name, user, project, cli, args, security)
    |
    v
[1] Security validation (directory permissions for user/project paths)
    |
    v
[2] User TOML load: cfg.update(_load_toml_from_fd(user_fd))   -- shallow
    |
    v
[3] Project TOML load: cfg.update(_load_toml_from_fd(project_fd))  -- shallow
    |
    v
[4] Subcommand extraction: pop [cmd] section, clear cfg, replace with section
    |
    v
[5] CLI arg parsing + list-append merge (_merge_list_args)
    |
    v
[6] dacite from_dict (fills dataclass defaults for missing keys)
    |
    v
  Config instance
```

### Key Observations

1. **Defaults are implicit**: Dataclass defaults are filled by `dacite.from_dict`
   at step [6], not by an explicit merge step. There is no "defaults dict" in the
   pipeline.

2. **Merge is shallow**: `cfg.update()` at steps [2] and [3] means project-level
   keys completely replace user-level keys at the top level. Nested dicts are
   replaced, not merged. If user TOML has `[database]\nhost = "x"` and project
   TOML has `[database]\nport = 5432`, the result is `{"database": {"port": 5432}}`
   — `host` is lost.

3. **Subcommand extraction discards root**: At step [4], if a `[cmd]` section
   exists, the entire `cfg` is cleared and replaced with just that section.
   Root-level fields are discarded. With shallow merge, this also means only the
   last provider's `[cmd]` section survives.

4. **TOML loading is private**: `_load_toml(file)` and `_load_toml_from_fd(fd)`
   are private functions. The parser selection logic in `_get_toml_parser()` is
   also private. Users cannot load TOML through Clevis's parser selection without
   calling `get_config`.

5. **Security is in `get_config`**: File permission checks happen inside
   `get_config`, not in the TOML loading functions. The `_check_file_permissions`
   and `_check_directory_permissions` functions are called with the `security`
   parameter from `get_config`.

6. **List fields**: In the TOML/cascade layer, lists are replaced (shallow merge
   replaces the entire key). CLI args then append to whatever list survived the
   cascade, via `_merge_list_args`.

---

## Proposed API Design

### New Public Surfaces

| Name | Type | Purpose |
|------|------|---------|
| `ConfigProvider` | `Protocol` | Callable protocol: `() -> dict[str, Any]` |
| `UserConfigProvider` | `class` | Default user-TOML provider (`~/.{name}.toml`) |
| `ProjectConfigProvider` | `class` | Default project-TOML provider (`./{name}.toml`) |
| `DEFAULT_CASCADE` | `tuple[type[ConfigProvider], ...]` | Default provider classes |
| `deep_merge` | `func` | Recursive dict merge (public, for custom providers) |
| `load` | `func` | Load TOML from binary file object (stdlib-compatible) |
| `loads` | `func` | Load TOML from string (stdlib-compatible) |
| `load_toml` | `func` | Alias for `load` (descriptive name) |
| `loads_toml` | `func` | Alias for `loads` (descriptive name) |
| `cascade` param | `get_config` arg | Custom list of `ConfigProvider` instances |

### 1. ConfigProvider Protocol

```python
class ConfigProvider(Protocol):
    """Callable protocol that provides a configuration dict.

    A ConfigProvider is a zero-argument callable that returns a dict
    of configuration data. Providers own their own security/validation
    (file permission checks, path resolution, etc.) and raise on failure.

    Callers do not pass security or name arguments to the provider;
    the provider captures everything it needs at construction time.
    """

    def __call__(self) -> dict[str, Any]:
        """Return a configuration dict. Raise on failure."""
        ...
```

**Design rationale**: The Protocol is minimal (zero-argument callable) because
the issue explicitly requires "a callable returning a dict, raising on failure,
owning its own security. No richer interface." Providers capture `name` and
`security` at construction time, keeping the call site uniform.

### 2. UserConfigProvider and ProjectConfigProvider

```python
class UserConfigProvider:
    """ConfigProvider that loads user-level TOML (~/.{name}.toml).

    Owns its own security checks (file and directory permissions).
    If the file does not exist, returns an empty dict.
    """

    def __init__(
        self,
        name: str,
        security: SecurityConfig | None = None,
    ) -> None:
        self._name = name
        self._security = security or {
            "file_permissions": SecurityAction.REJECT,
            "directory_permissions": SecurityAction.REJECT,
        }

    def __call__(self) -> dict[str, Any]:
        # Resolve path: Path.home() / USER_CONFIG_TEMPLATE.format(name=self._name)
        # Check directory permissions
        # Check file permissions (TOCTOU-safe via fd)
        # Load TOML from fd
        # Return dict (or empty dict if file doesn't exist)
        ...


class ProjectConfigProvider:
    """ConfigProvider that loads project-level TOML (./{name}.toml).

    Owns its own security checks (file and directory permissions).
    If the file does not exist, returns an empty dict.
    """

    def __init__(
        self,
        name: str,
        security: SecurityConfig | None = None,
    ) -> None:
        self._name = name
        self._security = security or {
            "file_permissions": SecurityAction.REJECT,
            "directory_permissions": SecurityAction.REJECT,
        }

    def __call__(self) -> dict[str, Any]:
        # Resolve path: Path.cwd() / PROJECT_CONFIG_TEMPLATE.format(name=self._name)
        # Same security + load flow as UserConfigProvider
        ...
```

**Design rationale**: These classes extract the security + TOML loading logic
currently embedded in `get_config` lines 586-612 into reusable, self-contained
provider objects. Each provider "owns its own security" per the Protocol
requirement. The implementation reuses existing `_check_file_permissions`,
`_check_directory_permissions`, and `_load_toml_from_fd` internally.

### 3. DEFAULT_CASCADE

```python
DEFAULT_CASCADE: tuple[type[ConfigProvider], ...] = (
    UserConfigProvider,
    ProjectConfigProvider,
)
"""Default cascade of provider classes (user-TOML, then project-TOML).

Each entry is a class that accepts (name, security) at construction
and produces a ConfigProvider instance. get_config instantiates these
with the name and security arguments when cascade is not provided.

To build a custom cascade, construct provider instances directly:

    from clevis import UserConfigProvider, ProjectConfigProvider

    cascade = [
        UserConfigProvider("myapp", security),
        MyCustomProvider(),
        ProjectConfigProvider("myapp", security),
    ]
    config = get_config(Config, name="myapp", cascade=cascade)
"""
```

**Design rationale**: `DEFAULT_CASCADE` is a tuple of **classes** (not
instances) because the TOML file providers need `name` and `security` which are
runtime parameters to `get_config`. A tuple of instances would require either
mutable state (injecting name/security at call time, which is not thread-safe)
or sentinel values. A tuple of classes is immutable, introspectable, and serves
as both documentation and a programmatic base for custom cascades.

When `cascade=None` (the default), `get_config` instantiates each class from
`DEFAULT_CASCADE` with `name` and `security`, then filters by the `user` and
`project` flags.

### 4. cascade Parameter on get_config

```python
def get_config(
    clz: type[T],
    name: str = "project",
    user: bool = True,
    project: bool = True,
    cli: bool = True,
    args: list[str] | None = None,
    security: SecurityConfig | None = None,
    cascade: list[ConfigProvider] | None = None,
) -> T:
```

**Behavior**:

| `cascade` value | `user`/`project` flags | Active middle cascade |
|-----------------|------------------------|-----------------------|
| `None` (default) | `user=True, project=True` | `[UserConfigProvider(name, sec), ProjectConfigProvider(name, sec)]` |
| `None` | `user=False` | `[ProjectConfigProvider(name, sec)]` |
| `None` | `project=False` | `[UserConfigProvider(name, sec)]` |
| `None` | `user=False, project=False` | `[]` (empty middle) |
| `[provider1, ...]` | ignored | `cascade` as given |

**Rule**: When `cascade` is explicitly provided (not `None`), the `user` and
`project` flags are **ignored** — the caller has taken full control of the
middle layer. When `cascade` is `None`, the default cascade is built from
`DEFAULT_CASCADE` and filtered by `user`/`project`.

### 5. deep_merge Function

```python
def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay onto base, returning a new dict.

    - When both base[key] and overlay[key] are dicts: recurse.
    - Otherwise: overlay[key] replaces base[key] (including lists, scalars).
    - Input dicts are not modified.

    This is the merge strategy used by the config cascade middle layer.
    Override providers replace entire lists; only nested dicts are merged
    recursively.
    """
    result: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, dict):
            result[key] = dict(value)  # shallow copy; deep merge will recurse
        else:
            result[key] = value
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

**Algorithm**:
1. Copy `base` into `result` (shallow copy of top-level; nested dicts are
   copied so recursion doesn't mutate the original).
2. For each key in `overlay`:
   - If both `result[key]` and `overlay[key]` are `dict` → recurse.
   - Otherwise → `overlay[key]` replaces `result[key]`.

**Edge cases**:
| base[key] | overlay[key] | Result | Rationale |
|-----------|-------------|--------|-----------|
| `{"a": 1}` | `{"b": 2}` | `{"a": 1, "b": 2}` | Deep merge |
| `[1, 2]` | `[3, 4]` | `[3, 4]` | Lists replaced (not merged) |
| `"hello"` | `"world"` | `"world"` | Scalars replaced |
| `{"a": 1}` | `[1, 2]` | `[1, 2]` | Type mismatch: overlay wins |
| `[1, 2]` | `{"a": 1}` | `{"a": 1}` | Type mismatch: overlay wins |
| `None` | `{"a": 1}` | `{"a": 1}` | None is not a dict: overlay wins |
| `{"a": 1}` | absent | `{"a": 1}` | Key only in base: preserved |

**Design rationale**: A standalone function (not extending `apply_to_dict`)
because `apply_to_dict` operates on dotted keys (CLI arg format), while
`deep_merge` operates on nested dict structures (TOML format). They serve
different merge strategies for different layers. Making `deep_merge` public
allows custom providers to merge their own dicts consistently.

### 6. load / loads (Public TOML API)

```python
def load(fp: BinaryIO) -> dict[str, Any]:
    """Load TOML from a binary file object.

    Uses Clevis's automatic parser selection (envtoml > tomlev > tomli > tomllib).
    Drop-in compatible with tomllib.load.

    Args:
        fp: A binary file object (opened with mode 'rb').

    Returns:
        Parsed TOML as a dictionary.

    Raises:
        ImportError: If no TOML parser is available.
        TOMLParseError: If the TOML content is invalid (from the underlying parser).
    """
    return _load_toml(fp)


def loads(s: str) -> dict[str, Any]:
    """Load TOML from a string.

    Uses Clevis's automatic parser selection. Drop-in compatible with
    tomllib.loads.

    Args:
        s: A string containing TOML data.

    Returns:
        Parsed TOML as a dictionary.

    Raises:
        ImportError: If no TOML parser is available.
        TOMLParseError: If the TOML content is invalid.
    """
    import io
    return _load_toml(io.BytesIO(s.encode("utf-8")))


# Descriptive aliases (same functions, more explicit names)
load_toml = load
loads_toml = loads
```

**Design rationale**: The primary names `load`/`loads` follow stdlib conventions
(`json.load`, `json.loads`, `tomllib.load`, `tomllib.loads`) and enable
drop-in replacement: `from clevis import load, loads` instead of
`import tomllib`. The aliases `load_toml`/`loads_toml` provide discoverability
for users who search for "toml" in the namespace.

The `loads` function wraps the string in `io.BytesIO` because the underlying
parser selection returns a `load` function that expects a binary file object
(matching `tomllib.load`'s interface). The `tomlev` custom loader already
handles bytes-to-str conversion internally.

### 7. Subcommand Extraction (Post-Cascade Transform)

The subcommand extraction remains a **fixed post-cascade transform** operating
on the final merged dict. It is not a provider and cannot be reordered.

```python
# After the middle cascade is deep-merged into a single dict `cfg`:
factory = get_factory(clz)
toml_key = factory.config or factory.cmd
if toml_key and toml_key in cfg:
    cmd_cfg = cfg.pop(toml_key)
    if isinstance(cmd_cfg, dict):
        cfg.clear()
        cfg.update(cmd_cfg)
    else:
        raise ConfigError(...)
```

**What changes with deep merge**: With the old shallow merge, if user TOML has
`[print]\nrich = true` and project TOML has `[print]\nverbose = true`, the
project's `[print]` section completely replaces the user's `[print]` section.
After extraction, only `{"verbose": true}` survives.

With deep merge, the `[print]` sections are recursively merged:
`{"rich": true, "verbose": true}`. After extraction, both fields survive.
This is a key benefit of the deep merge change.

**Custom providers contributing `[cmd]` sections**: Because the cascade uses
deep merge, a custom provider can contribute partial `[cmd]` sections that are
consolidated with the user/project `[cmd]` sections before extraction:

```python
class DefaultsProvider:
    def __call__(self) -> dict[str, Any]:
        return {"print": {"rich": True}}  # contributes to [print] section

cascade = [
    DefaultsProvider(),
    UserConfigProvider("myapp"),
    ProjectConfigProvider("myapp"),
]
# After deep merge: {"print": {"rich": True, ...user_print_fields, ...project_print_fields}}
# After extraction: {"rich": True, ...user_print_fields, ...project_print_fields}
```

### 8. New Pipeline (After P1-006)

```
get_config(clz, name, user, project, cli, args, security, cascade)
    |
    v
[A] Build middle cascade:
    - If cascade is None: instantiate DEFAULT_CASCADE with (name, security),
      filter by user/project flags
    - If cascade is a list: use as-is (user/project flags ignored)
    |
    v
[B] Defaults bookend (implicit): dataclass defaults filled by dacite later
    |
    v
[C] Middle cascade: call each provider, deep_merge results in order
    cfg = {}
    for provider in active_cascade:
        cfg = deep_merge(cfg, provider())
    |
    v
[D] Subcommand extraction (fixed post-cascade transform):
    pop [cmd] section from merged dict, replace root with section
    |
    v
[E] CLI bookend (fixed last step, list-append semantics):
    parse CLI args, _merge_list_args (append to cascade result)
    |
    v
[F] dacite from_dict: fills dataclass defaults for missing keys
    |
    v
  Config instance
```

---

## Implementation Approach

### Files to Modify

| File | Changes |
|------|---------|
| `src/clevis/__init__.py` | Add `ConfigProvider`, `UserConfigProvider`, `ProjectConfigProvider`, `DEFAULT_CASCADE`, `deep_merge`, `load`, `loads`, `load_toml`, `loads_toml`; refactor `get_config` to use cascade; update `__all__` |
| `src/clevis/__init__.pyi` | Add type stubs for all new public surfaces |
| `CHANGELOG.md` | Document shallow→deep merge as breaking change |
| `tests/test_config_cascade.py` | New test file for cascade, deep merge, custom providers, public TOML API |

### Key Code Changes in `__init__.py`

#### Step 1: Extract provider classes from `get_config`

Move the security check + TOML loading logic (lines 586-612) into
`UserConfigProvider.__call__` and `ProjectConfigProvider.__call__`. These
classes reuse the existing `_check_file_permissions`,
`_check_directory_permissions`, and `_load_toml_from_fd` functions.

#### Step 2: Add `deep_merge` function

New standalone function as specified in section 5 above. Placed near
`apply_to_dict` since they are both merge utilities.

#### Step 3: Add `load` / `loads` public functions

Wrap the existing `_load_toml` and add a BytesIO wrapper for `loads`.
Add `load_toml`/`loads_toml` as aliases.

#### Step 4: Refactor `get_config`

Replace the inline user/project loading (lines 586-612) with:

```python
# Build active cascade
if cascade is not None:
    active_cascade = cascade
else:
    active_cascade = []
    for provider_cls in DEFAULT_CASCADE:
        if provider_cls is UserConfigProvider and not user:
            continue
        if provider_cls is ProjectConfigProvider and not project:
            continue
        active_cascade.append(provider_cls(name, security))

# Deep merge middle cascade
cfg: dict[str, Any] = {}
for provider in active_cascade:
    cfg = deep_merge(cfg, provider())
```

The subcommand extraction (lines 614-635) and CLI merge (lines 637-642) remain
in place, operating on the deep-merged `cfg`.

#### Step 5: Update `__all__`

```python
__all__ = [
    # ... existing exports ...
    "ConfigProvider",
    "UserConfigProvider",
    "ProjectConfigProvider",
    "DEFAULT_CASCADE",
    "deep_merge",
    "load",
    "loads",
    "load_toml",
    "loads_toml",
]
```

---

## Breaking Change Documentation

### Shallow → Deep Merge

**Affected behavior**: The merge of user-level and project-level TOML files
changes from shallow (`dict.update`) to deep (recursive dict merge).

**Before (shallow)**:
```toml
# ~/.myapp.toml
[database]
host = "localhost"
port = 5432
```
```toml
# ./myapp.toml
[database]
host = "production.db.example.com"
```
Result: `{"database": {"host": "production.db.example.com"}}` — `port` is LOST.

**After (deep)**:
Result: `{"database": {"host": "production.db.example.com", "port": 5432}}` —
`port` is PRESERVED.

**Who is affected**: Users who rely on project-level TOML partially overriding
nested tables from user-level TOML. In the shallow model, providing a `[database]`
section in project TOML replaces the entire user `[database]` section. In the
deep model, individual keys within `[database]` are merged.

**Migration**: Users who intentionally relied on shallow replacement (project
TOML completely replacing a user TOML section) should provide all keys in the
project TOML section, or use CLI args which still replace at the scalar level.

**Severity**: Medium. Most users will benefit from deep merge (it is the more
intuitive behavior). Users with intentional shallow-reliance may see unexpected
additional keys appear in nested sections.

### Changelog Entry

```markdown
## [Unreleased]

### Added

- **Configurable Config Override Cascade**: `get_config()` now accepts an
  optional `cascade` parameter — a list of `ConfigProvider` instances that
  replace the default middle layers (user-TOML and project-TOML).
  - `ConfigProvider` Protocol: zero-argument callable returning a dict
  - `UserConfigProvider` and `ProjectConfigProvider`: default provider classes
  - `DEFAULT_CASCADE`: tuple of default provider classes
  - `deep_merge`: public recursive dict merge function
  - Custom providers can contribute `[cmd]` sections consolidated by deep merge

- **Public TOML API**: `load(fp)` and `loads(s)` functions exposed with
  stdlib-compatible signatures (drop-in for `tomllib.load`/`tomllib.loads`).
  - `load_toml`/`loads_toml` aliases also available for discoverability

### Changed

- **BREAKING: Shallow → Deep Merge**: The merge of user-level and project-level
  TOML files changed from shallow (`dict.update`) to deep (recursive dict merge).
  Nested tables are now merged key-by-key instead of being replaced wholesale.
  This means a project TOML `[database]` section now adds to (not replaces) the
  user TOML `[database]` section. Users who relied on wholesale replacement
  should provide all keys in the overriding TOML section.
```

---

## Type Stub Specifications

Additions to `src/clevis/__init__.pyi`:

```python
from typing import BinaryIO, Protocol

# ... existing imports ...

class ConfigProvider(Protocol):
    """Callable protocol that provides a configuration dict."""

    def __call__(self) -> dict[str, Any]:
        """Return a configuration dict. Raise on failure."""
        ...

class UserConfigProvider:
    """ConfigProvider that loads user-level TOML (~/.{name}.toml)."""

    def __init__(
        self,
        name: str,
        security: SecurityConfig | None = ...,
    ) -> None: ...

    def __call__(self) -> dict[str, Any]: ...

class ProjectConfigProvider:
    """ConfigProvider that loads project-level TOML (./{name}.toml)."""

    def __init__(
        self,
        name: str,
        security: SecurityConfig | None = ...,
    ) -> None: ...

    def __call__(self) -> dict[str, Any]: ...

DEFAULT_CASCADE: tuple[type[ConfigProvider], ...]

def deep_merge(
    base: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    """Recursively merge overlay onto base, returning a new dict."""
    ...

def load(fp: BinaryIO) -> dict[str, Any]:
    """Load TOML from a binary file object. Drop-in for tomllib.load."""
    ...

def loads(s: str) -> dict[str, Any]:
    """Load TOML from a string. Drop-in for tomllib.loads."""
    ...

# Descriptive aliases
load_toml = load
loads_toml = loads

def get_config(
    clz: type[T],
    name: str = ...,
    user: bool = ...,
    project: bool = ...,
    cli: bool = ...,
    args: list[str] | None = ...,
    security: SecurityConfig | None = ...,
    cascade: list[ConfigProvider] | None = ...,
) -> T:
    """
    Load configuration from TOML files and CLI arguments.

    Middle cascade:
        When cascade is None (default), the default cascade (user-TOML,
        project-TOML) is used, filtered by the user/project flags. When
        cascade is a list of ConfigProvider instances, those providers
        replace the default middle layers and user/project flags are ignored.

    The middle cascade uses deep merge (recursive dict merge). CLI args
        are a fixed last step with list-append semantics.
    """
    ...
```

---

## Backward Compatibility Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| `get_config()` without `cascade` | **Preserved** (minus deep merge) | Same behavior when cascade is None |
| `user`/`project` flags | **Preserved** | Filter default cascade when cascade is None |
| `cli` flag | **Preserved** | CLI remains fixed last bookend |
| `security` parameter | **Preserved** | Used for default cascade providers |
| `args` parameter | **Preserved** | CLI testing override |
| Subcommand extraction | **Preserved** | Still a fixed post-cascade transform |
| List-append for CLI | **Preserved** | `_merge_list_args` unchanged |
| Shallow → deep merge | **BREAKING** | Documented in changelog |
| Private `_load_toml` | **Preserved** | Still works; `load` wraps it |
| Private `_load_toml_from_fd` | **Preserved** | Used by provider classes internally |
| `apply_to_dict` | **Preserved** | Unchanged (different purpose from `deep_merge`) |
| Existing `__all__` entries | **Preserved** | New entries added, none removed |

### Interactions with `user`/`project` flags when `cascade` is provided

When `cascade` is explicitly provided, `user` and `project` flags are silently
ignored. This is the correct behavior because:
1. The caller has taken full control of the middle layer.
2. The custom providers may not correspond to "user" or "project" concepts.
3. Raising an error would break the common pattern of `get_config(Config,
   cascade=[...])` with default `user=True, project=True`.

**Recommendation**: Add a docstring note and a `logger.debug` message when
flags are ignored, but do not raise.

---

## Action Items

1. **Implement provider classes**: Extract `UserConfigProvider` and
   `ProjectConfigProvider` from `get_config` lines 586-612
2. **Implement `deep_merge`**: New standalone function in `__init__.py`
3. **Implement `load`/`loads`**: Wrap existing `_load_toml`, add BytesIO for
   `loads`, add `load_toml`/`loads_toml` aliases
4. **Refactor `get_config`**: Replace inline loading with cascade building +
   deep merge loop
5. **Add `DEFAULT_CASCADE` constant**: Tuple of provider classes
6. **Update `__all__`**: Add all new public names
7. **Update type stubs**: Add all new public surfaces to `__init__.pyi`
8. **Update changelog**: Document breaking change (shallow → deep merge)
9. **Write tests**: New `tests/test_config_cascade.py` covering:
   - Default cascade behavior (equivalent to current)
   - `user=False` / `project=False` filtering
   - Custom cascade with mock providers
   - Deep merge of nested dicts from multiple providers
   - Deep merge edge cases (lists, type mismatches, None)
   - Custom provider contributing `[cmd]` section
   - `load`/`loads` public TOML API
   - `load_toml`/`loads_toml` aliases
   - Backward compatibility (existing tests pass)
10. **Update docs**: `docs/api.rst`, `PACKAGE.md`, `README.md` with new API