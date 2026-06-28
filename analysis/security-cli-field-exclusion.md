# Security Analysis: P1-004 — CLI Field Exclusion (`metadata["cli"] = False`)

GitHub issue: #30
Priority: P1 (Critical — another project is blocked on this)
Analysis date: 2026-06-28

## 1. Overview

The proposed feature lets users mark a dataclass field with
`metadata["cli"] = False` so it is NOT exposed as a CLI argument. The
motivating use case is preventing secrets (API keys, tokens, passwords)
from leaking via shell history, `ps`, `/proc/<pid>/cmdline`, and CI logs.
The field remains loadable via config/TOML/env/defaults — just not via
the command line.

This document analyzes the security properties of the proposed mechanism
against the current codebase, identifies guarantees and gaps, and maps
acceptance criteria to security properties.

## 2. Threat Model

### Assets
- Secret values: API keys, tokens, passwords, credentials loaded into
  config dataclasses at runtime.

### Attackers / Threats
- **Local unprivileged user** who can read `ps` output or
  `/proc/<pid>/cmdline` for any process on a shared host.
- **Shell history reader** — anyone with access to `~/.bash_history`,
  `~/.zsh_history`, or CI log artifacts that capture command invocations.
- **CI log reader** — CI systems that echo the executed command line
  (e.g., GitHub Actions step summaries, Jenkins console output).
- **Process listing in error reports** — crash reporters, telemetry,
  or monitoring that capture `ps` snapshots.

### Trust Boundaries
1. **CLI surface** — `sys.argv` / `/proc/<pid>/cmdline`: world-readable
   on multi-user hosts; captured by history and CI logs.
2. **Config file surface** — TOML files on disk: protected by clevis's
   existing file-permission checks (`SecurityAction.REJECT` by default).
3. **Environment variable surface** — `${VAR}` interpolation via
   envtoml/tomlev: readable by the process and anyone who can read
   `/proc/<pid>/environ` (owner-only by default on Linux).
4. **In-memory surface** — the constructed config object: readable by
   the process; leakable via `repr()`, logging, tracebacks, core dumps.

### STRIDE Analysis

| Category | Relevant? | Notes |
|----------|-----------|-------|
| Spoofing | No | Feature does not touch authentication. |
| Tampering | Indirect | An attacker who can inject a CLI arg could override a config value; excluding a field from CLI removes that override path, reducing tamper surface. |
| Repudiation | No | Not relevant. |
| Information Disclosure | **Yes — primary** | Secrets exposed on the command line leak via `ps`, history, `/proc`, CI logs. |
| Denial of Service | No | Not relevant. |
| Elevation of Privilege | No | Not relevant. |

## 3. Security Guarantees Provided by the Design

When correctly implemented per the acceptance criteria, the feature
provides the following guarantees.

### G1 — No CLI argument is registered for excluded fields
`argparse.add_argument()` is never called for a field with
`metadata["cli"] is False`. Consequently:
- The argument does not appear in `--help`.
- The argument is not accepted by the parser; passing `--secret-api-key
  xyz` on the command line yields `unrecognized arguments` from
  argparse, so the value never enters the parsed `Namespace`.
- No `dest` is created in the parsed args for the excluded field.

This is the core guarantee: **if argparse does not know about the
field, the field's value cannot be supplied via the command line, and
therefore cannot appear in `sys.argv`, `ps`, `/proc/<pid>/cmdline`, or
shell history for that field.**

Verification against current code: `Factory.get_args()` (factory.py
line 603) returns `vars(_ensure_configured(self.parser).parse_args(args))`.
`get_config()` (init.py line 602) calls this and merges the result into
`cfg`. Since argparse only produces values for registered arguments, an
unregistered field produces no entry, and the merge leaves the TOML /
env / default value intact. **No other code path reads `sys.argv`** (grep
confirmed: only argparse-based parsing in `factory.get_args` and
`get_cmd`; `sys.argv` references in code are docstrings/parameter docs
only).

### G2 — Excluded fields remain loadable via TOML / env / defaults
The exclusion is CLI-only. `get_config()` still:
1. Loads TOML (user + project) into `cfg` (init.py lines 564-575).
2. Interpolates env vars via envtoml/tomlev (init.py lines 224-246).
3. Falls back to dataclass defaults via `dacite.from_dict()` (init.py
   line 609) when no value is present.

The CLI merge step (`_merge_list_args`, init.py line 604) only overrides
`cfg` with non-`None` CLI values; an excluded field contributes nothing,
so the TOML/env/default value survives. **The exclusion does not
silently drop the field from configuration.**

### G3 — Aliases are suppressed for excluded fields
Per acceptance criterion #4, `cli_aliases` must not register alias
arguments for an excluded field. Without this, an attacker could still
pass `--with xyz` (an alias) to set a secret field even though the
canonical name is excluded. The centralized exclusion helper applied
before the alias-registration block (factory.py lines 477-489, 544-601)
closes this bypass.

### G4 — Subtree exclusion prevents recursion into `cli=False` nested dataclasses
Per criterion #3, a nested dataclass field with
`metadata["cli"] is False` must short-circuit recursion in
`_configure_fields` (factory.py line 437). Without this, an attacker
could pass `--credentials-api-key xyz` to reach a leaf under an excluded
subtree. Subtree exclusion ensures the entire nested config (and all
its leaf fields) is unreachable via CLI.

### G5 — Explicit `False` only (not falsy)
Per criterion #2, the trigger is `metadata["cli"] is False`. This avoids
accidental exclusion from values like `0`, `""`, `[]`, `None` that users
might place in metadata for other reasons. This is a safety property,
not strictly a security one, but it prevents unintended secret-hiding
(which could itself be a denial-of-availability risk if a field a user
expected on CLI is silently dropped).

## 4. Security Gaps and Risks

The feature addresses CLI exposure only. The following gaps are
**out of scope for P1-004** but must be communicated to users so they
do not assume broader protection than the feature provides.

### R1 — `__repr__` leaks secret values (High)
The dataclass `__repr__` (and the custom `__repr__` installed by
`register_field` in registration.py lines 233-254) includes ALL fields
where `f.repr` is `True` (the default). An excluded field's value is
still loaded from TOML/env and stored on the instance. If the config
object is printed, logged, included in an exception message, or
captured by a crash reporter, the secret leaks.

The `metadata["cli"] = False` mechanism does NOT set `repr=False`. A
user who marks a secret field `cli=False` but does not also set
`repr=False` will still leak the secret via repr.

**Recommendation**: Document that secret fields should use BOTH
`metadata={"cli": False, "repr": False}` — but note `repr` is a
dataclass field parameter, not a metadata key. The correct incantation
is `field(..., repr=False, metadata={"cli": False})`. Consider whether
clevis should auto-set `repr=False` when `cli=False`, or at least warn.
This is a design decision for the implementer and product owner, not
something to auto-apply here.

### R2 — `register_field` hardcodes `metadata={}` (High, addressed by criterion #5)
`registration.py` line 151 creates the dynamic `Field` with
`metadata={}`. A plugin registering a secret field (e.g., an API key)
cannot mark it `cli=False` today, so plugin-registered secret fields
are ALWAYS exposed as CLI arguments. Criterion #5 fixes this by
accepting an optional `metadata` argument. Without criterion #5, the
feature is incomplete for the plugin use case that motivates the
blocking project.

### R3 — Multiple field-iteration consumers must all respect exclusion (Medium)
There are six places that iterate `fields(clz)` and recurse into
nested dataclasses:

1. `factory._configure_fields` (factory.py:400) — CLI arg generation.
2. `factory.list_fields` (factory.py:638) — field listing.
3. `factory.list_fields_with_owners` (factory.py:663) — field listing
   with owners.
4. `__init__._get_list_fields` (init.py:475) — list-field detection for
   the CLI/TOML merge.
5. `__init__.get_config` error handling (init.py:658) — iterates
   `fields(clz)` looking up nested class names.
6. `registration._update_repr` (registration.py:244) — repr generation.

Criterion #1 requires a single centralized exclusion helper used by all
field consumers. If any consumer bypasses the helper, there is an
inconsistency. The most security-relevant consumers are #1 (CLI
generation) and #4 (merge logic). Consumer #4 is lower-risk because
excluded fields won't appear in `cli_args` regardless, but applying the
helper there avoids treating an excluded list field as a merge target.
Consumer #6 is the repr leak in R1 and is structurally separate (repr
is a dataclass field parameter, not clevis metadata).

**Recommendation**: The centralized helper should cover consumers 1-4
at minimum. Consumer 5 (error handling) only reads class names, not
values, so it is low-risk. Consumer 6 needs separate handling per R1.

### R4 — TOML file and env var still hold the secret (Inherent)
The feature relocates secret loading from CLI to TOML/env/defaults.
- TOML files are protected by clevis's file-permission checks
  (`SecurityAction.REJECT` default) — good.
- Env vars (`${VAR}` via envtoml/tomlev) are readable via
  `/proc/<pid>/environ` by the owner; on misconfigured hosts, by others.
- The secret still exists in process memory.

This is inherent to the feature's design and acceptable: it moves the
secret from a world-readable surface (`/proc/<pid>/cmdline`, history,
CI logs) to an owner-readable surface (TOML file perms, env vars). It
does not eliminate the secret from the system.

### R5 — `ConfigError` messages do not leak values (Low / Positive)
`ConfigError._format_message()` (init.py lines 322-353) includes the
field PATH and a suggestion to use a CLI argument, but never the value.
For excluded fields, `suggest_cli` could still suggest the CLI flag name
(`--secret-api-key`) — which reveals that such a field conceptually
exists. This is a minor information disclosure: an error for an
excluded field should probably set `suggest_cli=False` to avoid
advertising the (now-hidden) CLI argument name.

**Recommendation**: When raising `ConfigError` for a field that is
excluded from CLI, pass `suggest_cli=False`. This requires the error
path to know whether a field is excluded — feasible via the
centralized helper.

### R6 — argparse `--help` does not list excluded fields (Positive)
Because `add_argument` is never called for excluded fields, `--help`
will not list them. This is a positive: the help text does not
advertise the existence of secret fields. (Note: a determined attacker
who reads the source or the TOML schema can still discover field
names; this is not a defense against source-level disclosure.)

### R7 — Unrecognized-argument error does not leak the value (Positive)
If an attacker passes `--secret-api-key xyz` for an excluded field,
argparse rejects it as `unrecognized arguments: --secret-api-key xyz`.
This DOES echo the attacker-supplied token back to them (stderr), but
that is the attacker's own input, not a secret stored on the system.
Not a leak of clevis-held secrets. Acceptable.

## 5. Recommendations for Hardening

Prioritized list. Items marked **(in-scope)** belong to P1-004; items
marked **(out-of-scope)** should be tracked separately.

1. **(in-scope)** Implement the single centralized exclusion helper and
   apply it in `_configure_fields` (both leaf and nested-dataclass
   branches) and in `list_fields`, `list_fields_with_owners`,
   `_get_list_fields`. Use `metadata.get("cli") is False` (identity
   check, not truthiness).

2. **(in-scope)** Apply the helper BEFORE the `cli_aliases` block in
   `_configure_fields` so aliases are suppressed for excluded fields.

3. **(in-scope)** Add `metadata` parameter to `register_field()` so
   plugins can register secret fields with `metadata={"cli": False}`.

4. **(in-scope, optional)** In `ConfigError` handling, detect excluded
   fields and set `suggest_cli=False` to avoid advertising hidden CLI
   argument names in error messages.

5. **(out-of-scope, recommend backlog)** Document that secret fields
   should use `field(..., repr=False, metadata={"cli": False})` to also
   prevent repr leakage. Consider a `secret()` helper or documented
   pattern in the README.

6. **(out-of-scope, recommend backlog)** Consider auto-wiring
   `repr=False` when `cli=False`, or emitting a `logger.warning` when a
   field has `cli=False` but `repr` is not `False`, to nudge users
   toward the safe combination. This is a design decision requiring
   human validation — repr is sometimes intentionally kept for
   debugging.

7. **(out-of-scope, recommend test)** Add a regression test that asserts
   the excluded field's value does NOT appear in the parser's known
   dests after `configure_parser()` (defensive against future
   regressions that re-introduce the argument).

## 6. Acceptance-Criteria Security Checklist

| # | Criterion | Security property |
|---|-----------|-------------------|
| 1 | Single, centralized exclusion helper used by all field consumers. | Consistency: prevents bypass via any field-iterating consumer (G1, G3, G4, R3). |
| 2 | Triggers only on `metadata["cli"] is False` (explicit `False`, not falsy). | Safety: prevents accidental exclusion from benign falsy metadata values; avoids silent denial-of-availability (G5). |
| 3 | Works at any level — leaf and nested-dataclass subtrees (no recursion into `cli=False` subtrees). | Completeness: prevents reaching a secret leaf via a `--subtree-leaf` path under an excluded nested config (G4). |
| 4 | Suppresses `cli_aliases` for excluded fields. | No bypass: prevents an attacker from using an alias to set an excluded field (G3). |
| 5 | `register_field()` accepts optional metadata for plugin-registered secret fields. | Plugin parity: plugin-registered secret fields can be excluded from CLI, otherwise they are always exposed (R2). |
| 6 | Regression safety for non-excluded fields. | Non-regression: existing CLI behavior for normal fields is unchanged; no accidental mass-exclusion. |
| 7 | Tests cover secret-field scenario (absent from `sys.argv`-derived parsing, still loadable via config). | Evidence: proves the secret is unreachable via CLI yet still loaded from TOML/env/defaults (G1, G2). |

## 7. Conclusion

The proposed `metadata["cli"] = False` mechanism is a sound and
effective control for its stated threat model: preventing secrets from
appearing in `sys.argv`, `ps`, `/proc/<pid>/cmdline`, shell history, and
CI logs. The security guarantees hinge on a single property that the
current codebase satisfies: **argparse is the only code path that reads
CLI arguments**, and argparse only knows about fields for which
`add_argument()` was called. No backdoor reads `sys.argv` directly.

The feature does NOT protect against repr leakage, logging of the
config object, TOML-file disclosure, env-var disclosure, or memory
dumps. These are out of scope but must be documented so users do not
over-rely on the control.

The most important implementation-time security considerations are:
- Apply the centralized helper to ALL field-iteration consumers
  (criterion #1), not just `_configure_fields`.
- Suppress `cli_aliases` for excluded fields (criterion #4) to close
  the alias bypass.
- Skip recursion into `cli=False` nested subtrees (criterion #3) to
  prevent reaching leaves under an excluded subtree.
- Accept metadata in `register_field()` (criterion #5) so plugins can
  register secret fields.
- Recommend (out of scope) that users also set `repr=False` on secret
  fields to prevent repr leakage, since `cli=False` alone does not
  suppress repr.