# Security Analysis: P1-006 — Configurable Config Override Cascade + Public TOML API

GitHub issue: #33
Priority: P1 (blocks Yoker project)
Analysis date: 2026-07-15

## 1. Overview

This document analyzes the security implications of generalizing clevis's
config cascade into a pluggable `ConfigProvider` Protocol architecture and
exposing the TOML parser as public API. The analysis covers the threat
model for the cascade architecture, security implications of public
`load_toml`/`loads_toml`, deep merge considerations, the `ConfigProvider`
security contract, and required implementation changes.

## 2. Current Security Architecture (Baseline)

Before analyzing the proposed changes, it is essential to understand what
security controls exist today and where they live.

### 2.1 Security Controls in get_config()

All security checks currently live in `get_config()` (`__init__.py` lines
576-612). The flow is:

1. **Resolve security config** — defaults to maximally strict
   (`REJECT` for both file and directory permissions).
2. **Check directory permissions** — `_check_directory_permissions()` for
   both user and project config paths. Rejects if parent directory is
   world-writable (`stat.S_IWOTH`), with an exception for the user's home
   directory.
3. **Check file permissions (TOCTOU-safe)** — `_check_file_permissions()`
   opens a file descriptor first, then checks permissions on the FD via
   `os.fstat()`. This prevents a TOCTOU race between `stat()` and `open()`.
   If group/other can read the file (`stat.S_IRGRP | stat.S_IROTH`), the
   check fails.
4. **Load TOML from FD** — `_load_toml_from_fd()` wraps the FD in a file
   object and passes it to the selected TOML parser. The FD is opened
   once, checked once, and read from the same FD — no re-open.

### 2.2 Key Security Properties Today

| Property | Mechanism | Location |
|----------|-----------|----------|
| TOCTOU-safe file permission check | Open FD, then `fstat` the FD | `_check_file_permissions` |
| World-writable directory rejection | `stat.S_IWOTH` check on parent dir | `_check_directory_permissions` |
| Home directory trust | `Path.home()` comparison bypasses dir check | `_check_directory_permissions` |
| Default-deny security | `security=None` → `REJECT` for both checks | `get_config` line 577-581 |
| Configurable strictness | `SecurityAction` enum (DONT_CHECK/LOG/REJECT) | `get_config` security param |
| FD ownership transfer | `os.fdopen()` takes ownership, closes FD | `_load_toml_from_fd` |

### 2.3 What the Security Parameter Controls

The `security` parameter on `get_config()` controls file and directory
permission checks for the two default config file locations (user TOML
and project TOML). It does NOT control:
- Content validation (values, secrets, URLs)
- Provider authentication or integrity
- TOML parser security (parser bugs, billion-laughs equivalent)
- Environment variable interpolation safety

## 3. STRIDE Threat Model for the Cascade Architecture

### 3.1 Trust Boundaries

```
┌─────────────────────────────────────────────────────────┐
│  Application Code (calls get_config)                     │
│  Trust Level: Highest — caller controls cascade          │
├─────────────────────────────────────────────────────────┤
│  ConfigProvider instances (cascade middle layers)        │
│  Trust Level: Variable — each provider owns its security │
│  ⚠ NEW BOUNDARY: providers are arbitrary callables       │
├─────────────────────────────────────────────────────────┤
│  Default bookends: dataclass defaults | CLI args         │
│  Trust Level: Fixed — not reorderable via cascade        │
├─────────────────────────────────────────────────────────┤
│  Config file sources (TOML on disk, env vars, etc.)      │
│  Trust Level: Lowest — untrusted input                   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 STRIDE Analysis

#### Spoofing
- **Threat**: A custom `ConfigProvider` could impersonate a legitimate
  config source, injecting values that appear to come from user/project
  TOML.
- **Mitigation**: The caller controls which providers are in the cascade.
  There is no provider authentication. This is acceptable — the caller
  is trusted to assemble the cascade. Document that provider provenance
  is the caller's responsibility.

#### Tampering
- **Threat**: A compromised provider (or a provider reading from a
  compromised source) could inject security-relevant config values
  (e.g., `database.ssl_mode = false`, `api.allow_insecure = true`).
- **Mitigation**: Deep merge means later providers can override earlier
  ones at the field level (see Section 5). The `cli` bookend can
  override any provider value. Content-level validation is out of scope
  for clevis (the dataclass schema + dacite provides type validation
  but not semantic validation).
- **NEW RISK**: With the current shallow merge, a project TOML replaces
  entire top-level keys from user TOML. With deep merge, a project TOML
  can surgically override individual nested fields while preserving
  others. This increases the blast radius of a compromised config file.

#### Repudiation
- **Threat**: A provider could silently fail or return unexpected data,
  and there is no audit trail of which provider contributed which values.
- **Mitigation**: The Protocol contract requires providers to raise on
  failure (not silently return empty dicts). However, there is no
  provenance tracking in the merged result. Consider logging provider
  participation for debugging (not security-critical, but useful for
  incident response).

#### Information Disclosure
- **Threat**: A malicious provider could exfiltrate config values by
  side effects (e.g., logging, network calls). Since providers are
  arbitrary callables, they can execute any code.
- **Mitigation**: None possible at the framework level — the caller
  trusts the provider code. Document that providers have full code
  execution capability and must be vetted like any dependency.

#### Denial of Service
- **Threat**: A provider could hang indefinitely, consume excessive
  memory, or raise exceptions that crash `get_config()`.
- **Mitigation**: The Protocol contract says providers "raise on
  failure" — exceptions propagate to the caller, which is the correct
  fail-fast behavior. No timeout mechanism is proposed (out of scope).
  Document that providers should be fast and reliable.

#### Elevation of Privilege
- **Threat**: A provider could inject values that elevate privileges in
  the consuming application (e.g., `admin.enabled = true`).
- **Mitigation**: Same as Tampering — content validation is the
  application's responsibility. The dataclass schema constrains types
  but not values.

## 4. Security Implications of Public `load_toml`/`loads_toml`

### 4.1 Design Question: Raw Parser vs. Security-Checked Loader

The task asks whether `load_toml(fp)` should include security checks or
be a raw parser.

**Recommendation: `load_toml(fp)` and `loads_toml(str)` should be RAW
parsers with NO security checks.**

Rationale:
1. **Stdlib alignment**: `tomllib.load(fp)` and `tomllib.loads(str)` are
   raw parsers. Matching this interface enables drop-in replacement.
   Adding security checks would break the contract.
2. **Security checks don't apply to strings**: `loads_toml(str)` takes a
   string — there is no file to check permissions on.
3. **Security checks don't apply to file objects**: `load_toml(fp)` takes
   an already-opened file object. The file is already open — checking
   permissions after opening is a TOCTOU anti-pattern. The caller
   decided how to open the file.
4. **Separation of concerns**: Parsing and security validation are
   orthogonal. The default TOML providers handle security (opening the
   FD, checking permissions, then calling the parser). The public parser
   is a building block, not a secure loader.

### 4.2 Risks of Public Exposure

| Risk | Severity | Description |
|------|----------|-------------|
| Bypass of security checks | Medium | Users building custom providers with `load_toml(open(path, "rb"))` bypass TOCTOU-safe FD permission checks. |
| Direct use without security context | Low | Users calling `load_toml()` directly for ad-hoc parsing have no security expectations (it's a parser, not a loader). |
| Parser-specific vulnerabilities | Low | If envtoml/tomlev has interpolation vulnerabilities (e.g., env var injection), public exposure increases the attack surface. |

### 4.3 Required Documentation

The public API must clearly document:

> `load_toml(fp)` and `loads_toml(str)` are raw TOML parsers with no
> security checks. They do NOT validate file permissions, directory
> permissions, or any other security properties. To load TOML config
> files with security validation, use `get_config()` or construct a
> `TomlConfigProvider` which encapsulates TOCTOU-safe file permission
> checks.

### 4.4 Naming Consideration

The task suggests naming without the `_toml` suffix (e.g., `load(fp)`
and `loads(str)`) for drop-in stdlib replacement. This is a usability
decision, not a security one. However, generic names like `load` in the
`clevis` namespace could cause confusion with other load operations.
Recommend keeping `load_toml`/`loads_toml` for clarity, or namespacing
as `clevis.toml.load` if a module approach is preferred. No security
impact either way.

## 5. Deep Merge Security Considerations

### 5.1 Behavioral Change

| Aspect | Current (shallow `dict.update`) | Proposed (deep merge) |
|--------|--------------------------------|----------------------|
| Top-level key | Project replaces user entirely | Project deep-merges into user |
| Nested dict | Project `[db]` replaces user `[db]` | Project `[db]` fields merge into user `[db]` |
| List field | Project list replaces user list | Project list replaces user list (lists are not deep-merged) |
| Scalar field | Project value replaces user value | Project value replaces user value (same) |

### 5.2 Security Impact of Deep Merge

**Scenario**: User config sets `[database]\nhost = "localhost"\nssl_mode = true`.
Project config sets `[database]\nssl_mode = false`.

- **Current (shallow)**: Project `[database]` section completely replaces
  user `[database]` section. User loses `host` setting. The replacement
  is all-or-nothing — a compromised project config must supply the
  entire `[database]` section.
- **Proposed (deep)**: Project `ssl_mode = false` merges into user
  `[database]`, preserving `host = "localhost"` but flipping
  `ssl_mode`. A compromised project config can surgically disable
  security-relevant fields while preserving benign fields, making the
  tampering less noticeable.

**Assessment**: This is a **Medium** severity behavioral change. Deep
merge does not introduce a new vulnerability class, but it increases
the precision with which a compromised config file can tamper with
security-relevant settings. In the shallow model, a tampered config
file that only sets `ssl_mode = false` would also need to supply all
other database fields or lose them — making the tampering more
detectable. In the deep model, the tampering is surgical and stealthy.

**Mitigation**: This is inherent to the deep merge design and was
approved by the owner as a documented breaking change. No additional
security control is needed, but the breaking change documentation
should mention the security-relevant behavioral difference:

> **Security note**: Deep merge allows a config source to override
> individual nested fields without replacing the entire section. This
> means a compromised config file can surgically modify
> security-relevant settings (e.g., `ssl_mode`, `verify_certificates`)
> while preserving other fields from earlier sources. In the previous
> shallow-merge behavior, overriding a nested section required
> replacing it entirely. Applications with security-sensitive nested
> config should review their config cascade trust model.

### 5.3 List Field Semantics

The task specifies: "List fields: override providers replace the entire
list; CLI args append to the resulting list."

This is consistent with current behavior (TOML list replaces, CLI
appends) and has no new security implications. Lists are not deep-merged
(which would be semantically unclear and potentially dangerous).

## 6. ConfigProvider Protocol Security Contract

### 6.1 The Core Security Question

The design states: "Each provider owns its own security/validation."

This is the most security-critical design decision in P1-006. It means:

1. **The `security` parameter on `get_config()` cannot enforce security
   on custom providers.** Currently, `get_config()` applies file/dir
   permission checks before loading any config. In the new architecture,
   `get_config()` delegates loading to providers. If security checks
   stay on `get_config()`, they only apply to the default TOML
   providers — custom providers bypass them entirely.

2. **The default TOML providers MUST encapsulate the existing security
   checks.** The TOCTOU-safe FD opening, file permission checking, and
   directory permission checking currently in `get_config()` must move
   into the default TOML provider implementations. If they stay in
   `get_config()`, the architecture is incoherent (security checks for
   providers that may not be in the cascade).

3. **There is no enforcement mechanism for custom provider security.**
   A `ConfigProvider` is just a callable. There is no way to verify
   that a custom provider performs security checks. This is acceptable
   (like any plugin architecture) but must be documented.

### 6.2 Recommended Protocol Definition

```python
class ConfigProvider(Protocol):
    """A callable that provides a configuration dictionary.

    Security Contract:
        Each provider is responsible for its own security validation.
        This includes, but is not limited to:
        - File permission checks (if reading from files)
        - Directory permission checks (if reading from files)
        - TOCTOU-safe file access (if applicable)
        - Input validation for the data it returns

        Providers MUST raise an exception on failure (file not found,
        security check failure, parse error, etc.). Providers MUST NOT
        silently return an empty dict on error — this could mask
        security-relevant failures.

        The caller (application code assembling the cascade) is
        responsible for vetting providers. Clevis does not authenticate
        or validate provider security postures.

    Returns:
        A dict of configuration values. Nested dicts are deep-merged
        across providers in cascade order.

    Raises:
        Any exception on failure. SecurityError should be raised for
        security check failures to maintain consistency with the
        default providers.
    """
    def __call__(self) -> dict[str, Any]: ...
```

### 6.3 Security Parameter Migration

**Critical design decision**: Where does the `security` parameter go?

**Option A: Keep `security` on `get_config()`, pass to default providers**
- The `security` parameter stays on `get_config()`.
- `get_config()` passes the security config to the default TOML providers
  (which are in `DEFAULT_CASCADE`).
- Custom providers do not receive the security config.
- **Pro**: Backward compatible — existing `security=` calls work.
- **Con**: Muddies the "providers own their security" principle. The
  security parameter only affects default providers, which could
  confuse users who expect it to apply to all providers.

**Option B: Security lives on the providers themselves**
- The default TOML providers accept a `security` config at construction
  time.
- `get_config()` no longer has a `security` parameter (or it's
  deprecated).
- Users configure security by constructing providers with the desired
  `SecurityConfig`.
- **Pro**: Clean separation — each provider owns its security config.
- **Con**: Breaking change for existing `security=` users. More verbose
  for the common case.

**Option C: Hybrid — `security` on `get_config()` for backward compat, providers own security**
- `get_config()` keeps the `security` parameter for backward compat.
- When `cascade` is NOT provided, `get_config()` constructs the default
  providers with the given `security` config (replacing the ones in
  `DEFAULT_CASCADE`).
- When `cascade` IS provided, the `security` parameter is ignored (or
  logged as a warning if non-default). The providers in the cascade own
  their security.
- **Pro**: Backward compatible, clean for new users, explicit about
  when security applies.
- **Con**: Two code paths for security, potential confusion.

**Recommendation: Option C (Hybrid)**

This preserves backward compatibility (the `security` parameter still
works when you don't customize the cascade) while making the security
ownership explicit when you do customize it. The key implementation
detail:

```python
def get_config(
    clz,
    name="project",
    user=True,
    project=True,
    cli=True,
    args=None,
    security=None,        # backward compat — applies to default providers
    cascade=None,         # NEW — explicit provider list
):
    if cascade is not None:
        # Explicit cascade: providers own their security.
        # Warn if security= is also provided (it's ignored).
        if security is not None:
            logger.info(
                "security= parameter is ignored when cascade= is "
                "provided. Each provider in the cascade owns its "
                "own security configuration."
            )
        active_cascade = list(cascade)
    else:
        # Default cascade: construct providers with security config.
        active_cascade = build_default_cascade(
            name=name, user=user, project=project, security=security
        )
```

### 6.4 Default TOML Provider Security Implementation

The default TOML providers MUST encapsulate the existing security
checks. The implementation should extract the current security logic
from `get_config()` into the provider:

```python
class TomlConfigProvider:
    """Default TOML config provider with TOCTOU-safe security checks.

    Encapsulates the security checks previously in get_config():
    - File permission validation (group/other readability)
    - Directory permission validation (world-writable)
    - TOCTOU-safe file descriptor access
    """

    def __init__(
        self,
        path: Path,
        security: SecurityConfig | None = None,
    ):
        self._path = path
        self._security = security or {
            "file_permissions": SecurityAction.REJECT,
            "directory_permissions": SecurityAction.REJECT,
        }

    def __call__(self) -> dict[str, Any]:
        file_action = self._security.get(
            "file_permissions", SecurityAction.REJECT
        )
        dir_action = self._security.get(
            "directory_permissions", SecurityAction.REJECT
        )

        _check_directory_permissions(self._path, dir_action)
        _, fd = _check_file_permissions(self._path, file_action)
        if fd is None:
            return {}  # File doesn't exist — not an error
        return _load_toml_from_fd(fd)
```

This preserves the exact security behavior that exists today, including
the TOCTOU-safe FD pattern.

## 7. Risks of Custom Provider Bypassing Security

### 7.1 The Bypass Scenario

```python
# Naive custom provider — NO security checks
class InsecureProvider:
    def __call__(self) -> dict:
        return load_toml(open("/etc/app/config.toml", "rb"))

config = get_config(Config, cascade=[InsecureProvider()])
```

This bypasses:
- File permission checks (no `REJECT` on world-readable files)
- Directory permission checks (no `REJECT` on world-writable directories)
- TOCTOU-safe FD access (uses `open()` instead of the FD-check-read pattern)

### 7.2 Assessment

This is **inherent to the plugin architecture** and is **acceptable** if
documented. The same risk exists in any plugin/extension system. The
caller explicitly chose to provide a custom cascade, taking
responsibility for security.

However, the documentation must be explicit:

> **Warning**: When you provide a custom `cascade`, clevis's default
> security checks (file permissions, directory permissions, TOCTOU-safe
> access) do NOT apply. Each provider in your cascade is responsible
> for its own security. If your provider reads from files, use
> `TomlConfigProvider` or replicate its security checks. Using
> `load_toml(open(path, "rb"))` directly bypasses all security
> validation.

### 7.3 Mitigation: Provide a Secure Building Block

To reduce the likelihood of insecure custom providers, clevis should
expose `TomlConfigProvider` (or equivalent) as a public, reusable
building block. This allows users to construct secure file-based
providers without reimplementing the security checks:

```python
from clevis import TomlConfigProvider, get_config

# Secure custom provider using the building block
custom = TomlConfigProvider(
    path=Path("/opt/app/override.toml"),
    security={"file_permissions": SecurityAction.REJECT},
)

config = get_config(Config, cascade=[
    TomlConfigProvider(Path.home() / ".myapp.toml"),
    custom,
    TomlConfigProvider(Path.cwd() / "myapp.toml"),
])
```

## 8. Injection Risks with the Cascade Architecture

### 8.1 Key Injection via Deep Merge

A provider can inject keys that are not in the dataclass schema. Dacite
igns unknown keys by default (unless `Config(strict=True)` is used).
This means a compromised provider can inject arbitrary nested keys that
silently pass through the merge and are dropped at dacite conversion.

**Impact**: Low — unknown keys are ignored, not stored. But they could
cause confusion during debugging (the merged dict has keys that don't
appear in the final config object).

**Recommendation**: Consider offering a `strict` mode that warns or
errors on unknown keys in the merged dict. This is out of scope for
P1-006 but could be a future enhancement.

### 8.2 Provider Ordering Attacks

A malicious provider placed early in the cascade could set a
security-relevant field, expecting it to survive if later providers
don't explicitly override it. With deep merge, a value set by an early
provider persists unless a later provider explicitly sets the same
field path.

**Impact**: This is by design (cascade precedence) and not a
vulnerability. The caller controls provider ordering. Document that
earlier providers have lower precedence and later providers override.

### 8.3 Environment Variable Interpolation Risk

The current TOML parser selection (envtoml > tomlev > tomli > tomllib)
affects what interpolation features are available. If envtoml or tomlev
is installed, `${VAR}` interpolation is active. A config file can
reference environment variables.

**Risk**: If a provider uses `load_toml()` and envtoml is installed,
environment variable interpolation happens silently. An attacker who
can set environment variables could inject values into config.

**Mitigation**: This is an existing risk, not new to P1-006. The default
providers inherit the same parser selection. Document that env var
interpolation is parser-dependent and that `load_toml()`/`loads_toml()`
use the same parser selection as `get_config()`.

## 9. Security Documentation Needed for Custom Providers

The following documentation must be created for users implementing
custom `ConfigProvider` instances:

### 9.1 Provider Security Checklist

```markdown
## Custom ConfigProvider Security Checklist

Before deploying a custom ConfigProvider, verify:

- [ ] **File permissions**: If your provider reads files, validate that
      files are not readable by group/other (use `TomlConfigProvider`
      or replicate `_check_file_permissions`).
- [ ] **Directory permissions**: If your provider reads files, validate
      that parent directories are not world-writable (prevents symlink
      attacks).
- [ ] **TOCTOU safety**: Open the file descriptor FIRST, then check
      permissions on the FD, then read from the FD. Do not use
      `stat()` followed by `open()` — this has a race window.
- [ ] **Failure handling**: Raise an exception on failure. Do NOT
      silently return an empty dict — this masks security-relevant
      failures.
- [ ] **Input validation**: Validate the data you return. Clevis
      validates types via dacite, but semantic validation (e.g., URL
      is HTTPS, path is within allowed directory) is your
      responsibility.
- [ ] **No side effects**: Providers should not log config values,
      make network calls, or write to disk. Providers have full code
      execution capability — vet them like any dependency.
- [ ] **Provenance**: Only use providers from trusted sources. A
      malicious provider has full access to the config dict and can
      inject any values.
```

### 9.2 API Documentation Additions

The `get_config()` docstring must be updated:

```python
def get_config(
    clz,
    name="project",
    user=True,
    project=True,
    cli=True,
    args=None,
    security=None,
    cascade=None,  # NEW
):
    """
    ...
    Args:
        cascade: Optional list of ConfigProvider instances replacing
            the default middle layers (user TOML + project TOML).
            When provided, each provider owns its own security. The
            `security` parameter is ignored. When not provided, the
            default cascade is used with the `security` parameter
            applied to the default TOML providers.

            WARNING: Custom providers bypass clevis's default security
            checks (file permissions, directory permissions, TOCTOU-safe
            access). Each provider is responsible for its own security
            validation. Use TomlConfigProvider for secure file-based
            providers.
    ...
    """
```

## 10. Required Implementation Changes for Security

### 10.1 MUST: Extract Security Checks into Default Providers (Blocking)

The security checks currently in `get_config()` (lines 591-612) must be
extracted into the default TOML provider implementations. If this is
not done, the refactoring will either:
- Leave dead security checks in `get_config()` that don't apply to the
  cascade, or
- Remove security checks entirely, creating a regression.

**Verification**: After implementation, confirm that:
- `get_config(Config, security={"file_permissions": SecurityAction.REJECT})`
  still rejects world-readable config files.
- The TOCTOU-safe FD pattern is preserved (open FD → fstat → read from
  same FD).
- `_check_file_permissions` and `_check_directory_permissions` are
  called by the default providers, not by `get_config()` directly.

### 10.2 MUST: Preserve `security` Parameter Backward Compatibility (Blocking)

When `cascade` is not provided, the `security` parameter must still
work exactly as it does today. This means `get_config()` must construct
the default providers with the given security config.

**Verification**: All existing security tests must pass without
modification.

### 10.3 MUST: Expose `TomlConfigProvider` as Public API (Blocking)

To prevent users from building insecure custom providers with raw
`load_toml(open(...))`, the secure file-based provider must be publicly
exposed. This is the safe building block for custom cascades.

**Verification**: A user can construct a custom cascade with
`TomlConfigProvider` instances and get the same security guarantees as
the default cascade.

### 10.4 MUST: Document Security Implications (Blocking)

The breaking change documentation (changelog, README) must include:
1. The shallow→deep merge behavioral change and its security
   implications (Section 5.2).
2. The security ownership model for custom providers (Section 6.1).
3. The warning about bypassing security with custom cascades (Section
   7.2).
4. The raw parser nature of `load_toml`/`loads_toml` (Section 4.3).

### 10.5 SHOULD: Log When `security` Is Ignored (Related)

When `cascade` is provided AND `security` is also provided, log an info
message that `security` is ignored. This prevents silent security
regressions where a user provides `security=` expecting it to apply but
it doesn't because they also provided a custom cascade.

### 10.6 SHOULD: Consider `SecurityError` Export for Custom Providers (Related)

Custom providers that perform security checks should raise
`SecurityError` for consistency. `SecurityError` is already exported in
`__all__`, so this is already available. Document it as the recommended
exception for provider security failures.

### 10.7 NICE-TO-HAVE: Strict Mode for Unknown Keys (New/Backlog)

Consider a future `strict` parameter or `Config(strict=True)` that
warns or errors when the merged dict contains keys not in the dataclass
schema. This would help detect provider injection of unexpected fields.
Not blocking for P1-006 — add to backlog.

## 11. Security Findings Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| Security checks must move into default providers | Blocking | Extract `_check_file_permissions` and `_check_directory_permissions` calls from `get_config()` into `TomlConfigProvider` |
| `security` parameter backward compatibility | Blocking | Construct default providers with security config when `cascade` is not provided |
| Expose `TomlConfigProvider` as public API | Blocking | Add to `__all__` and document |
| Deep merge increases tamper precision | Blocking | Document as security-relevant breaking change |
| Custom providers bypass security | Blocking | Document security ownership model and provide secure building block |
| `load_toml`/`loads_toml` are raw parsers | Blocking | Document clearly, no security checks in public parser |
| Log when `security` is ignored with custom cascade | Related | Add info-level log message |
| Unknown key injection via deep merge | New | Add to backlog — strict mode for merged dict validation |
| Env var interpolation in public parser | New | Document that `load_toml` inherits parser selection including env interpolation |

## 12. Positive Security Observations

1. **TOCTOU-safe pattern is well-implemented**: The current FD-based
   permission check (`os.open` → `os.fstat` → read from FD) is the
   correct pattern. The refactoring must preserve this, and the
   `TomlConfigProvider` design in Section 6.4 does.

2. **Default-deny security posture**: The default `REJECT` behavior for
   security checks is the correct fail-safe approach. The hybrid
   approach (Option C) preserves this for the default cascade.

3. **Provider raises-on-failure contract**: Requiring providers to raise
   on failure (not silently return empty dicts) is a good security
   property — it prevents masking of security-relevant failures.

4. **Fixed bookends for defaults and CLI**: Keeping `defaults` and `cli`
   as non-reorderable bookends prevents a compromised provider from
   positioning itself after CLI args (which would allow overriding
   user-supplied CLI values).

5. **CLI list-append semantics preserved**: The design preserves the
   current behavior where CLI args append to (not replace) list values
   from providers. This maintains the principle that CLI is the
   highest-priority, most-explicit override.

6. **Existing security infrastructure is solid**: `SecurityAction`,
   `SecurityConfig`, `SecurityError`, and the permission check
   functions are well-designed and can be cleanly extracted into
   providers without modification.

## 13. Conclusion

The P1-006 design is architecturally sound from a security perspective,
provided that:

1. **Security checks move with the default providers** — the existing
   TOCTOU-safe file permission checks, directory permission checks, and
   default-deny posture must be encapsulated in `TomlConfigProvider`,
   not left in `get_config()` where they would become dead code for
   custom cascades.

2. **`TomlConfigProvider` is exposed publicly** — giving users a secure
   building block for custom cascades prevents the most likely
   insecure-implementation pattern (`load_toml(open(path))`).

3. **`load_toml`/`loads_toml` are raw parsers** — no security checks in
   the public parser, matching stdlib conventions and separating
   parsing from security validation.

4. **The deep merge breaking change is documented with security
   context** — users must understand that deep merge allows surgical
   override of nested security-relevant fields.

5. **Custom provider security ownership is documented** — users
   providing custom cascades must understand they are responsible for
   security, and clevis's default checks do not apply.

The most significant security risk is the **silent regression** scenario:
if the security checks are removed from `get_config()` but not properly
encapsulated in the default providers, all existing security validation
would be lost. This must be the top implementation priority and should
be verified with the existing security test suite before any other
work proceeds.