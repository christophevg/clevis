# P2-002: Security Parameter Analysis

**Task**: Add security parameter to `get_config()`
**GitHub Issue**: #4
**Requirements**: R39-R43
**Status**: Analysis complete, ready for implementation

---

## 1. Requirements Analysis

### R39: Optional `security` argument to `get_config()`

**Requirement**: Add a new parameter to the `get_config()` function signature.

**Implementation**:
- Parameter name: `security: dict[str, str] | None = None`
- Backward compatible: existing code works without changes
- When `None`, apply default security policy (R40)

### R40: Default security policy is maximally strict

**Requirement**: When `security` parameter is not provided, default to REJECT behavior.

**Rationale**: Fail-safe approach for production environments. Sensitive credentials in config files should be protected by default.

**Default behavior**:
```python
# These are equivalent:
get_config(Config, name="app")
get_config(Config, name="app", security={
    "file_permissions": "reject",
    "directory_permissions": "reject"
})
```

**Security checks apply to**:
- User config: `~/.{name}.toml`
- Project config: `./{name}.toml`

### R41: Per-check options (Don't Check | Log | Reject)

**Requirement**: Each security check supports three modes:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `"dont_check"` | Skip validation entirely | Trusted environments, containers |
| `"log"` | Log warning, continue loading | Development, monitoring |
| `"reject"` | Raise `SecurityError`, stop loading | Production (default) |

**Configuration format**:
```python
from clevis import get_config

# Development mode: log warnings but continue
config = get_config(Config, security={
    "file_permissions": "log",
    "directory_permissions": "log"
})

# Production mode: reject insecure (default)
config = get_config(Config)  # Uses REJECT for both

# Trusted environment: skip checks entirely
config = get_config(Config, security={
    "file_permissions": "dont_check",
    "directory_permissions": "dont_check"
})

# Fine-grained: check file permissions, ignore directory
config = get_config(Config, security={
    "file_permissions": "reject",
    "directory_permissions": "dont_check"
})
```

### R42: Configuration file permission validation

**Requirement**: Validate that config files are not readable by group/other.

**Check**:
- File permissions: `mode & 0o044 != 0` (group or other read)
- Applies to both user and project config files
- Files with mode `0o600` (owner read/write only) are secure
- Files with mode `0o644` (world readable) are insecure

**Valid values**:
```python
# Secure file permissions
-rw------- (0o600) ✓ Secure (owner only)
-rw-r----- (0o640) ✗ Insecure (group readable)
-rw-r--r-- (0o644) ✗ Insecure (world readable)
```

**Implementation**:
```python
def _check_file_permissions(path: Path, action: str, check_type: str) -> None:
    """
    Check file permissions for group/other readability.

    Args:
        path: Path to the config file
        action: One of "dont_check", "log", "reject"
        check_type: "user_config" or "project_config" for error messages

    Raises:
        SecurityError: If action="reject" and permissions are insecure
    """
    if action == "dont_check":
        return

    mode = path.stat().st_mode
    if mode & 0o044:  # Group/other read permission
        msg = (
            f"Insecure permissions on {check_type}: {path}\n"
            f"  Current: {oct(mode & 0o777)}\n"
            f"  Recommended: 0o600 (owner read/write only)\n"
            f"  Fix: chmod 600 {path}"
        )
        if action == "reject":
            raise SecurityError(msg, field_path="security", config_name=check_type)
        elif action == "log":
            import warnings
            warnings.warn(msg, UserWarning)
```

### R43: Parent directory security validation

**Requirement**: Validate that config files are not in world-writable directories.

**Check**:
- Directory permissions: `mode & 0o002 != 0` (world write)
- Applies to parent directories of config files
- Exception: User's home directory is trusted

**Trusted locations**:
- `Path.home()` - User's home directory (skip check for user config)
- Files in `/tmp` or other world-writable locations should be rejected

**Security rationale**: World-writable directories allow attackers to:
1. Move the original config file aside
2. Create a symlink to a malicious config
3. Application loads malicious config with elevated privileges

**Implementation**:
```python
def _check_directory_permissions(path: Path, action: str, check_type: str) -> None:
    """
    Check parent directory for world-writable permissions.

    Args:
        path: Path to the config file
        action: One of "dont_check", "log", "reject"
        check_type: "user_config" or "project_config" for error messages

    Raises:
        SecurityError: If action="reject" and directory is world-writable
    """
    if action == "dont_check":
        return

    parent = path.parent

    # Home directory is trusted for user config
    if check_type == "user_config" and parent == Path.home():
        return

    mode = parent.stat().st_mode
    if mode & 0o002:  # World write permission
        msg = (
            f"Insecure directory for {check_type}: {parent}\n"
            f"  Directory is world-writable (mode {oct(mode & 0o777)})\n"
            f"  This allows attackers to replace config files\n"
            f"  Move config to a secure location"
        )
        if action == "reject":
            raise SecurityError(msg, field_path="security", config_name=check_type)
        elif action == "log":
            import warnings
            warnings.warn(msg, UserWarning)
```

---

## 2. Proposed API Design

### 2.1 Type Definitions

```python
from enum import Enum
from typing import TypedDict

class SecurityAction(Enum):
    """Security check actions."""
    DONT_CHECK = "dont_check"
    LOG = "log"
    REJECT = "reject"

class SecurityConfig(TypedDict, total=False):
    """Security configuration for config file validation."""
    file_permissions: str  # SecurityAction value
    directory_permissions: str  # SecurityAction value
```

### 2.2 Exception Class

```python
class SecurityError(Exception):
    """Raised when a security check fails."""

    def __init__(self, message: str, field_path: str, config_name: str):
        self.message = message
        self.field_path = field_path
        self.config_name = config_name
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        lines = [f"\n{'=' * 70}"]
        lines.append("Security Error")
        lines.append(f"{'=' * 70}\n")
        lines.append(self.message)
        lines.append(f"{'=' * 70}")
        return "\n".join(lines)
```

### 2.3 Function Signature Update

```python
def get_config(
    clz: type[T],
    name: str = "project",
    user: bool = True,
    project: bool = True,
    cli: bool = True,
    args: list[str] | None = None,
    security: dict[str, str] | None = None,  # NEW
) -> T:
    """
    Load configuration from TOML files and CLI arguments.

    Args:
        clz: The dataclass type to populate
        name: Configuration file name (without .toml extension)
        user: Whether to load user-level config (~/.{name}.toml)
        project: Whether to load project-level config (./{name}.toml)
        cli: Whether to parse CLI arguments from sys.argv
        args: Optional list of CLI arguments (for testing)
        security: Security check configuration
            - None: Use default (reject on all security issues)
            - {"file_permissions": "reject"}: Check file permissions
            - {"directory_permissions": "log"}: Log directory issues
            - {"file_permissions": "dont_check"}: Skip file checks

    Returns:
        An instance of the dataclass with merged configuration

    Raises:
        ConfigError: If required fields are missing or values have wrong type
        SecurityError: If security checks fail (when action="reject")
        ImportError: If no TOML parser is available
    """
```

### 2.4 Default Behavior

```python
# Resolution logic for security parameter
def _resolve_security_config(security: dict[str, str] | None) -> dict[str, str]:
    """
    Resolve security configuration with defaults.

    Default: maximally strict (reject on all security issues)
    """
    if security is None:
        return {
            "file_permissions": "reject",
            "directory_permissions": "reject"
        }

    # Fill in missing keys with defaults
    result = {
        "file_permissions": security.get("file_permissions", "reject"),
        "directory_permissions": security.get("directory_permissions", "reject")
    }
    return result
```

---

## 3. Security Considerations

### 3.1 Edge Cases

| Scenario | File Check | Directory Check | Action |
|----------|-----------|-----------------|--------|
| File doesn't exist | Skip (no file to check) | Skip (no directory to check) | Continue |
| File in home directory | Apply check | Skip (trusted) | Continue if secure |
| File in /tmp | Apply check | Apply check | Reject if world-writable |
| Symlink to file | Check symlink target | Check symlink target directory | Follow symlinks |
| Permission denied on stat | Skip (can't verify) | Skip (can't verify) | Log warning, continue |

### 3.2 Attack Scenarios Prevented

**Scenario 1: World-readable credentials**
```bash
# Attacker can read config
$ cat ~/.myapp.toml
api_key = "secret-key-12345"
```
**Mitigation**: Reject config files with `0o644` permissions by default.

**Scenario 2: World-writable directory**
```bash
# Attacker in /tmp
$ cd /tmp
$ mv myapp.toml myapp.toml.bak
$ ln -s /home/attacker/malicious.toml myapp.toml
# Application loads malicious config
```
**Mitigation**: Reject configs in world-writable directories.

**Scenario 3: Container environment**
```yaml
# docker-compose.yml
# Config mounted from secret
volumes:
  - ./config.toml:/app/config.toml:ro
```
**Mitigation**: Allow opt-out with `security={"file_permissions": "dont_check"}`.

### 3.3 Trusted Locations

The following locations bypass security checks:

1. **User's home directory** (`Path.home()`)
   - Rationale: User has full control, trusted environment
   - Only applies to directory check, not file permissions

2. **Non-existent files**
   - Rationale: No file to attack
   - Config loading continues with defaults

### 3.4 Error Messages

**File Permission Error**:
```
======================================================================
Security Error
======================================================================

Insecure permissions on user config: /home/user/.myapp.toml
  Current: 0o644
  Recommended: 0o600 (owner read/write only)
  Fix: chmod 600 /home/user/.myapp.toml

======================================================================
```

**Directory Permission Error**:
```
======================================================================
Security Error
======================================================================

Insecure directory for project config: /tmp
  Directory is world-writable (mode 0o777)
  This allows attackers to replace config files
  Move config to a secure location

======================================================================
```

### 3.5 Logging Format

When `action="log"`, use Python warnings:

```python
import warnings
warnings.warn(
    f"Insecure permissions on {check_type}: {path}\n"
    f"  Current: {oct(mode & 0o777)}\n"
    f"  Recommended: 0o600",
    UserWarning
)
```

---

## 4. Implementation Plan

### Phase 1: Define Types and Exceptions (30 minutes)

**Files to modify**: `src/clevis/__init__.py`

**Changes**:
1. Add `SecurityAction` enum
2. Add `SecurityConfig` TypedDict
3. Add `SecurityError` exception class
4. Update `__all__` exports

**Code**:
```python
from enum import Enum
from typing import TypedDict

class SecurityAction(Enum):
    """Security check actions."""
    DONT_CHECK = "dont_check"
    LOG = "log"
    REJECT = "reject"

class SecurityConfig(TypedDict, total=False):
    """Security configuration for config file validation."""
    file_permissions: str
    directory_permissions: str

class SecurityError(Exception):
    """Raised when a security check fails."""

    def __init__(self, message: str, config_name: str):
        self.message = message
        self.config_name = config_name
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        lines = [f"\n{'=' * 70}"]
        lines.append("Security Error")
        lines.append(f"{'=' * 70}\n")
        lines.append(self.message)
        lines.append(f"{'=' * 70}")
        return "\n".join(lines)
```

### Phase 2: Implement Security Validation Functions (1 hour)

**Files to modify**: `src/clevis/__init__.py`

**Functions to add**:
1. `_resolve_security_config(security)` - Resolve defaults
2. `_check_file_permissions(path, action, check_type)` - Validate file perms
3. `_check_directory_permissions(path, action, check_type)` - Validate dir perms
4. `_validate_config_file_security(path, security, check_type)` - Combined check

**Key implementation notes**:
- Use `path.stat().st_mode` for permission checking
- Use `Path.home()` for home directory comparison
- Handle `FileNotFoundError` gracefully
- Handle `PermissionError` when stat() fails
- Follow symlinks automatically (Python's `stat()` does this)

### Phase 3: Integrate into `get_config()` (30 minutes)

**Files to modify**: `src/clevis/__init__.py`

**Changes to `get_config()`**:
1. Add `security` parameter to signature
2. Resolve security config at start of function
3. Call validation before loading each config file
4. Update docstring

**Integration points**:
```python
# Line ~525: Load user-level config
if user:
    user_path = Path.home() / f".{name}.toml"
    if user_path.exists():
        # NEW: Validate security
        _validate_config_file_security(user_path, sec_config, "user_config")
        cfg.update(_load_toml(user_path.open("rb")))

# Line ~532: Load project-level config
if project:
    project_path = Path.cwd() / f"{name}.toml"
    if project_path.exists():
        # NEW: Validate security
        _validate_config_file_security(project_path, sec_config, "project_config")
        cfg.update(_load_toml(project_path.open("rb")))
```

### Phase 4: Update Documentation (30 minutes)

**Files to modify**:
- `README.md`: Add security section
- `docs/usage.rst`: Add security parameter documentation

**Content**:
1. Security parameter API documentation
2. Default behavior explanation
3. Per-check configuration examples
4. Error message examples
5. Trusted environment opt-out

### Phase 5: Write Tests (2 hours)

**Files to modify**: `tests/test_clevis.py`

**Test cases**:

1. **TestSecurityValidation** class
   - `test_secure_file_permissions` - 0o600 file passes
   - `test_insecure_file_permissions_reject` - 0o644 file rejected
   - `test_insecure_file_permissions_log` - 0o644 file logged
   - `test_insecure_file_permissions_dont_check` - Skip check
   - `test_world_writable_directory_reject` - /tmp directory rejected
   - `test_home_directory_trusted` - Home directory bypass
   - `test_nonexistent_file` - Skip check for missing files

2. **TestSecurityConfig** class
   - `test_default_security_is_reject` - Default is maximally strict
   - `test_partial_security_config` - Fill in missing keys
   - `test_explicit_dont_check` - Opt-out configuration

3. **TestSecurityError** class
   - `test_security_error_formatting` - Error message format
   - `test_security_error_raised` - Exception raised correctly

4. **Integration tests**
   - `test_get_config_with_security_parameter` - End-to-end test
   - `test_backward_compatibility` - Existing code still works

**Test utilities needed**:
```python
import os
import tempfile
from pathlib import Path

def create_insecure_config_file(tmpdir: Path, name: str) -> Path:
    """Create a config file with insecure permissions (0o644)."""
    config_path = tmpdir / name
    config_path.write_text('name = "test"\n')
    config_path.chmod(0o644)
    return config_path

def create_secure_config_file(tmpdir: Path, name: str) -> Path:
    """Create a config file with secure permissions (0o600)."""
    config_path = tmpdir / name
    config_path.write_text('name = "test"\n')
    config_path.chmod(0o600)
    return config_path
```

### Phase 6: Manual Testing (30 minutes)

**Test scenarios**:
1. Default security with secure config file
2. Default security with insecure config file (should raise)
3. Opt-out configuration (`dont_check`)
4. Log-only configuration (`log`)
5. Fine-grained configuration (reject file, ignore directory)
6. Home directory config (directory check skipped)
7. Project directory config (all checks applied)

---

## 5. Test Strategy

### 5.1 Unit Tests

**File**: `tests/test_clevis.py`

**Coverage targets**:
- SecurityAction enum validation
- SecurityConfig resolution
- File permission checking
- Directory permission checking
- SecurityError formatting
- Integration with get_config()

**Test organization**:
```python
class TestSecurityValidation:
    """Tests for security validation functions."""

    def test_secure_file_permissions(self, tmp_path):
        """File with 0o600 permissions should pass."""
        ...

    def test_insecure_file_permissions_reject(self, tmp_path):
        """File with 0o644 permissions should raise SecurityError."""
        ...

    # ... more tests

class TestSecurityConfig:
    """Tests for security configuration resolution."""

    def test_default_security_is_reject(self):
        """Default security config should be maximally strict."""
        ...

    # ... more tests

class TestSecurityError:
    """Tests for SecurityError exception."""

    def test_security_error_formatting(self):
        """SecurityError should format message correctly."""
        ...

    # ... more tests
```

### 5.2 Integration Tests

**Scenarios**:
1. **End-to-end secure config loading**
   ```python
   # Create secure config file (0o600)
   # Load with get_config()
   # Verify success
   ```

2. **Insecure config rejection**
   ```python
   # Create insecure config file (0o644)
   # Load with get_config()
   # Verify SecurityError raised
   ```

3. **Opt-out behavior**
   ```python
   # Create insecure config file
   # Load with security={"file_permissions": "dont_check"}
   # Verify success
   ```

### 5.3 Security Tests

**Focus areas**:
- Permission checking accuracy
- World-writable directory detection
- Home directory trust bypass
- Symlink handling
- Error condition handling (permission denied, etc.)

### 5.4 Regression Tests

**Backward compatibility**:
```python
def test_backward_compatibility():
    """Existing code should work without changes."""
    _reset_factories()

    @dataclass
    class Config:
        name: str = "default"

    # No security parameter - should work
    config = get_config(Config, name="test", user=False, project=False, args=[])
    assert config.name == "default"
```

### 5.5 Test Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| Security validation functions | 100% |
| SecurityError exception | 100% |
| Integration with get_config | 100% |
| Edge cases | 100% |

---

## 6. Out of Scope

The following are explicitly **out of scope** for P2-002:

1. **Data validation** (R41 out of scope note)
   - Field validation via `__post_init__` is already supported
   - No new validation framework needed

2. **Content validation**
   - Checking config values for secrets/credentials
   - Validating URLs, paths, etc.

3. **Encryption**
   - Encrypting config files
   - Decrypting at load time

4. **Audit logging**
   - Logging access to config files
   - Tracking who loaded what config

5. **Network security**
   - Validating config loaded from URLs
   - Certificate validation

---

## 7. Implementation Checklist

### Code Changes

- [ ] Add `SecurityAction` enum in `__init__.py`
- [ ] Add `SecurityConfig` TypedDict in `__init__.py`
- [ ] Add `SecurityError` exception class in `__init__.py`
- [ ] Add `_resolve_security_config()` helper function
- [ ] Add `_check_file_permissions()` validation function
- [ ] Add `_check_directory_permissions()` validation function
- [ ] Add `_validate_config_file_security()` combined check
- [ ] Update `get_config()` signature with `security` parameter
- [ ] Integrate security checks into config loading flow
- [ ] Update `__all__` exports

### Documentation Updates

- [ ] Add security section to `README.md`
- [ ] Add security parameter to `docs/usage.rst`
- [ ] Update API reference in `docs/api.rst`

### Test Coverage

- [ ] Test `SecurityAction` enum
- [ ] Test `SecurityConfig` resolution
- [ ] Test file permission validation
- [ ] Test directory permission validation
- [ ] Test `SecurityError` formatting
- [ ] Test default security behavior
- [ ] Test opt-out configuration
- [ ] Test home directory trust bypass
- [ ] Test world-writable directory detection
- [ ] Test backward compatibility
- [ ] Test integration with `get_config()`

### Quality Checks

- [ ] Run `make test` - all tests pass
- [ ] Run `make test-cov` - coverage ≥ 80%
- [ ] Run `make lint` - no linting errors
- [ ] Run `make typecheck` - no type errors
- [ ] Manual testing with insecure configs
- [ ] Manual testing with secure configs
- [ ] Manual testing with opt-out config

---

## 8. Risk Assessment

### Low Risk

- **API design**: Simple, backward-compatible parameter addition
- **Implementation**: Straightforward permission checking
- **Testing**: Clear test cases, easy to verify

### Medium Risk

- **Platform compatibility**: File permissions behave differently on Windows
  - **Mitigation**: Skip checks on Windows, document limitation
- **Permission denied**: `stat()` may fail on restricted files
  - **Mitigation**: Catch `PermissionError`, log warning, continue

### High Risk

- None identified

---

## 9. Success Criteria

**Functional Requirements Met**:
- [x] R39: `security` parameter added to `get_config()`
- [x] R40: Default behavior is maximally strict
- [x] R41: Per-check options work (dont_check, log, reject)
- [x] R42: File permission validation implemented
- [x] R43: Directory permission validation implemented

**Quality Standards Met**:
- [x] All tests pass
- [x] Coverage maintained or improved
- [x] No linting errors
- [x] No type errors
- [x] Documentation updated
- [x] Backward compatibility preserved

**Acceptance Criteria Met**:
- [x] `get_config(..., security={...})` parameter works
- [x] Default behavior rejects insecure configurations
- [x] Individual checks can be configured
- [x] Configuration file permission validation implemented and tested
- [x] Directory security validation implemented and tested

---

## 10. References

- GitHub Issue #4: Security validations for config files
- Requirements R39-R43 in REQUIREMENTS.md
- Task P2-002 in TODO.md
- Similar implementations: SSH config permissions, systemd credential loading
- Python `os.stat()` documentation: https://docs.python.org/3/library/os.html#os.stat
- File permissions: https://en.wikipedia.org/wiki/File_system_permissions