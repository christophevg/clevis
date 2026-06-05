# Security Review: P2-002 Security Parameter Implementation

## Executive Summary

The P2-002 implementation provides a robust security framework for configuration file permission validation with appropriate defaults and flexible configuration. The implementation correctly identifies insecure file and directory permissions and provides helpful error messages. However, a **TOCTOU (Time-of-Check to Time-of-Use) race condition** exists between security checks and file reads, which could be exploited in certain scenarios. The default security posture is maximally strict, following fail-safe principles.

## Critical Findings (CVSS 9.0-10.0)

None identified.

## High Findings (CVSS 7.0-8.9)

### H1: TOCTOU Race Condition in Permission Checks

**OWASP A05:2021 - Injection / A06:2025 - Insecure Design**

**Description**: A time-of-check to time-of-use race condition exists between permission validation and file reading. The security checks (lines 637-640) are performed before the actual file reads (lines 646, 651), creating a window where file permissions or content could be modified by an attacker.

**Location**: `src/clevis/__init__.py`, lines 637-652 in `get_config()`

**Attack Vector**:
1. Attacker identifies config file location
2. Attacker monitors for `get_config()` calls (via process monitoring)
3. Attacker waits for permission check to pass
4. Attacker modifies file permissions or replaces file between check and read
5. Application reads unvalidated file

**Impact**:
- Configuration file tampering
- Potential credential exposure if attacker-controlled config is loaded
- Security bypass in multi-user systems

**CVSS Score**: 7.5 (High)

**Remediation**:
```python
# Instead of checking then reading:
# 1. Open file descriptor
# 2. Check permissions using fstat(fd) instead of path.stat()
# 3. Read from the already-validated file descriptor
```

**Example Secure Pattern**:
```python
def _check_and_load_toml_secure(path: Path, action: SecurityAction) -> dict[str, Any]:
    """Securely check permissions and load file with TOCTOU protection."""
    if action == SecurityAction.DONT_CHECK or not path.exists():
        return _load_toml(path.open("rb"))

    # Open file descriptor first
    fd = os.open(path, os.O_RDONLY)
    try:
        # Check permissions on open fd (prevents TOCTOU)
        stat_result = os.fstat(fd)
        mode = stat_result.st_mode

        if mode & (stat.S_IRGRP | stat.S_IROTH):
            msg = f"Configuration file {path} is readable by group/other..."
            if action == SecurityAction.REJECT:
                raise SecurityError(msg, str(path), "file_permissions")
            elif action == SecurityAction.LOG:
                logger.warning(msg)

        # Read from validated file descriptor
        with os.fdopen(fd, 'rb') as f:
            return _load_toml(f)
    except:
        os.close(fd)
        raise
```

**Priority**: High - Should be addressed before production deployment in multi-user environments.

## Medium Findings (CVSS 4.0-6.9)

None identified.

## Low Findings (CVSS 0.1-3.9)

### L1: Missing Test Coverage for TOCTOU Scenarios

**Description**: Test suite lacks coverage for race condition scenarios where file permissions change between validation and reading.

**Location**: `tests/test_security.py`

**Impact**: Low - Testing gap only, does not create vulnerability

**Remediation**: Add tests that:
- Modify file permissions after security check but before file read
- Test hardlink scenarios
- Test symlink scenarios
- Test concurrent modification scenarios

### L2: Documentation Missing TOCTOU Limitations

**OWASP A09:2021 - Security Logging Failures / A10:2025 - Exception Handling**

**Description**: Security documentation does not mention the TOCTOU race condition limitation or provide guidance for high-security environments.

**Location**: `docs/usage.rst`, lines 810-962

**Impact**: Low - Users may not be aware of limitation

**Remediation**: Add documentation section:
```rst
Security Limitations
~~~~~~~~~~~~~~~~~~~~

**TOCTOU Race Condition**: Clevis checks file permissions before reading.
In high-security environments or multi-user systems with active attackers,
consider:

1. Using environment variables instead of config files
2. Storing configs in secure locations (e.g., secrets managers)
3. Using mandatory access controls (SELinux, AppArmor)
4. Running on trusted filesystems only

**Network Filesystems**: Permission checks may not be reliable on NFS,
CIFS, or other network filesystems due to permission mapping.
```

### L3: No Guidance for Network Filesystems

**Description**: No documentation or validation for network filesystems (NFS, CIFS) where permission models differ.

**Location**: Documentation and implementation

**Impact**: Low - Edge case for most deployments

**Remediation**: Add warning in documentation and potentially detect network mounts.

## Positive Observations

### Verified Security Aspects

1. **Correct Permission Checks**:
   - File check correctly identifies group/other readable files using `stat.S_IRGRP | stat.S_IROTH`
   - Directory check correctly identifies world-writable directories using `stat.S_IWOTH`
   - Proper use of `stat` module constants

2. **Secure Defaults**:
   - Default security is maximally strict (REJECT all issues)
   - Missing `security` parameter defaults to REJECT
   - Missing keys in `SecurityConfig` default to REJECT via `.get(key, SecurityAction.REJECT)`
   - Fail-safe principle correctly applied

3. **Error Message Quality**:
   - Error messages provide actionable fixes (e.g., `chmod 600 {path}`)
   - No sensitive information disclosed in errors
   - Security rationale explained (symlink attacks, credential exposure)
   - Clear indication of which check failed

4. **Defense in Depth**:
   - Checks both file AND directory permissions
   - Checks both user-level and project-level configs
   - Checks performed before loading files

5. **Trusted Location Model**:
   - Home directory trust is reasonable (user-controlled)
   - Prevents false positives for common use case
   - Non-existent files are safely skipped

6. **Test Coverage Quality**:
   - All three security actions tested (DONT_CHECK, LOG, REJECT)
   - Both file and directory permission checks tested
   - Default behavior tested
   - Edge cases tested (non-existent files)
   - Integration tests provided
   - Tests use proper cleanup (try/finally blocks)

7. **Code Quality**:
   - Clear separation of concerns
   - Well-documented functions
   - Type hints for SecurityConfig
   - Custom exception with structured data

## Code Review Details

### Security Types (lines 36-57)

**SecurityAction Enum**: ✓ Correct implementation
- Three modes with clear semantics
- Simple and unambiguous

**SecurityConfig TypedDict**: ✓ Correct implementation
- `total=False` allows empty dict
- Optional fields with proper typing
- Defaults handled correctly in usage

**SecurityError Exception**: ✓ Correct implementation
- Structured exception with path and check attributes
- Allows programmatic error handling
- Inherits from Exception properly

### Permission Check Functions

**_check_file_permissions()** (lines 60-85):
- ✓ Correct permission mask: `stat.S_IRGRP | stat.S_IROTH`
- ✓ Proper stat usage
- ✓ Helpful error messages
- ✓ Mode displayed in octal (user-friendly)
- ⚠️ TOCTOU window between check and file read

**_check_directory_permissions()** (lines 88-118):
- ✓ Correct permission mask: `stat.S_IWOTH`
- ✓ Home directory trust logic correct
- ✓ String comparison for home directory check
- ✓ Rationale documented (symlink attacks)
- ⚠️ TOCTOU window between check and file read

### get_config() Integration (lines 577-695)

**Security Application** (lines 620-640):
- ✓ Default to maximally strict (REJECT)
- ✓ Extract actions with safe defaults
- ✓ Check both user and project configs
- ✓ Checks before file loading
- ⚠️ Race window between checks and loads

**File Loading** (lines 643-652):
- ✓ File existence checked before open
- ✓ Binary mode used for TOML parsing
- ⚠️ Separate operations create race condition

## Attack Scenarios

### Scenario 1: Multi-User System with TOCTOU
**Environment**: Shared Linux server
**Attacker**: Low-privilege user on same system
**Target**: Config file with database credentials

**Steps**:
1. Attacker identifies user has `~/.myapp.toml` with `mode 0o600`
2. Attacker monitors for `get_config()` calls
3. User runs application, permission check passes
4. Attacker races to replace file with symlink to `/etc/passwd` or malicious config
5. Application reads attacker-controlled content

**Mitigation**: Use file descriptor-based permission check (see H1 remediation)

### Scenario 2: World-Writable Directory Attack
**Environment**: Application running from `/tmp` (world-writable)
**Attacker**: Local user

**Steps**:
1. Attacker creates symlink: `/tmp/myapp.toml` -> `/etc/passwd`
2. Application checks directory, finds it's world-writable
3. SecurityError raised before file read
4. Attack prevented ✓

**Status**: ✓ Correctly mitigated by directory check

### Scenario 3: Network Filesystem Permission Mapping
**Environment**: Application on NFS mount
**Issue**: NFS may map permissions differently

**Steps**:
1. File appears as `0o600` locally
2. NFS permission mapping makes it readable by others on server
3. Local check passes, file is actually insecure

**Mitigation**: Documentation warning for network filesystems (see L3)

## STRIDE Threat Model Analysis

### Spoofing
- **Threat**: Attacker replaces config file with malicious content
- **Mitigation**: Permission checks prevent unauthorized reads
- **Gap**: TOCTOU allows replacement during race window

### Tampering
- **Threat**: Attacker modifies config file content
- **Mitigation**: File permission checks
- **Gap**: TOCTOU allows modification after check

### Repudiation
- **Threat**: Attack leaves no audit trail
- **Mitigation**: LOG mode provides warning logs
- **Status**: ✓ Adequate

### Information Disclosure
- **Threat**: Config file readable by other users
- **Mitigation**: File permission checks reject group/other readable
- **Status**: ✓ Correctly mitigated

### Denial of Service
- **Threat**: Attacker creates world-writable directory to block app startup
- **Mitigation**: LOG or DONT_CHECK modes available
- **Status**: ✓ Flexible response

### Elevation of Privilege
- **Threat**: Config file in world-writable directory allows symlink attack
- **Mitigation**: Directory permission checks
- **Status**: ✓ Correctly mitigated

## OWASP Top 10:2025 Mapping

| Finding | OWASP Category | Justification |
|---------|----------------|---------------|
| H1 (TOCTOU) | A06:2025 - Insecure Design | Architectural flaw in check-then-act pattern |
| L1 (Tests) | A09:2021 - Security Logging | Missing test coverage for security scenarios |
| L2 (Docs) | A10:2025 - Exception Handling | Missing documentation of limitations |
| L3 (Network FS) | A06:2025 - Insecure Design | No guidance for filesystem variations |

## Recommendations

### Immediate Actions (Before Production)

1. **Fix TOCTOU Race Condition** (H1):
   - Refactor permission checks to use file descriptors
   - Implement atomic check-and-read pattern
   - Add tests for race condition scenarios

2. **Update Documentation** (L2, L3):
   - Add security limitations section
   - Document TOCTOU limitations
   - Add guidance for network filesystems
   - Provide recommendations for high-security environments

### Future Enhancements

3. **Add File Ownership Checks**:
   - Verify file is owned by current user
   - Prevent attacks via hardlinks owned by others

4. **Add SELinux/AppArmor Context Checks**:
   - Validate mandatory access control contexts
   - Provide guidance for MAC-enabled systems

5. **Add Network Filesystem Detection**:
   - Warn when running on NFS/CIFS
   - Provide alternative recommendations

6. **Enhanced Test Coverage**:
   - Add concurrent modification tests
   - Add hardlink/symlink tests
   - Add permission change timing tests

## Security Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| H1: TOCTOU race condition | **Blocking** | Fix in current task before merge |
| L1: Missing TOCTOU tests | Related | Add to current task scope |
| L2: Missing TOCTOU docs | Related | Add to current task scope |
| L3: Network FS guidance | New | Add to backlog |

## Conclusion

The P2-002 implementation demonstrates strong security fundamentals with correct permission checks, secure defaults, and helpful error messages. However, the TOCTOU race condition is a significant security gap that should be addressed before production deployment, especially in multi-user environments. The test coverage is good for normal cases but missing race condition scenarios. Documentation would benefit from explicit security limitations and high-security guidance.

**Overall Assessment**: **CONDITIONAL PASS** - Implement H1 remediation before merging to production.

**Recommended Path Forward**:
1. Fix TOCTOU race condition (H1)
2. Add test coverage for race scenarios (L1)
3. Update documentation with limitations (L2, L3)
4. Consider future enhancements for ownership and MAC checks

## References

- OWASP A05:2021 - Injection: https://owasp.org/Top10/A05_2021-Injection/
- OWASP A06:2025 - Insecure Design: https://owasp.org/Top10/A06_2025-Insecure_Design/
- CWE-367: Time-of-check Time-of-use (TOCTOU) Race Condition: https://cwe.mitre.org/data/definitions/367.html
- CWE-732: Incorrect Permission Assignment for Critical Resource: https://cwe.mitre.org/data/definitions/732.html