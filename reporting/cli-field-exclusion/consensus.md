# Consensus: P1-004 — CLI Field Exclusion (`metadata["cli"] = False`)

**Task**: P1-004 — Support excluding dataclass fields from CLI argument generation
**Issue**: #30 — https://github.com/christophevg/clevis/issues/30
**Priority**: P1 — Critical (another project is blocked on this)
**Consensus date**: 2026-06-28
**Domain analyses integrated**:
  - API architecture: `analysis/api-cli-field-exclusion.md`
  - Security: `analysis/security-cli-field-exclusion.md`

## 1. Owner Directive (Verbatim)

> "Ensure that any refactoring to create a single exclusion point is done cleanly, avoid calling functions all over the place: think deeply about the design before making changes!"

This directive rules out the apparently simple option of a `_should_exclude_cli(field)` predicate invoked at three separate iteration sites. A predicate with three call sites is technically "one predicate" but is exactly the scattering the owner rejects. The agreed design therefore centralizes both the recursion and the exclusion decision in a single walker.

## 2. Agreed Design: Single Recursive Walker

Both domain agents converge on a **single recursive generator** as the one source of truth for "which fields are visible to the CLI subsystem." The exclusion check lives in exactly one location — inside the walker — and all field-list consumers obtain their fields through it.

### The walker — `_iter_cli_fields`

Location: `src/clevis/factory.py` (private module-level function, no `self` state, easy to test in isolation).

The walker yields a tagged union so that `_configure_fields` (which needs to visit nested dataclasses for prefix/duplicate/subcommand bookkeeping) can consume the same stream as the leaf-only consumers:

- `("leaf", field, path, owner)` — a leaf field visible to CLI.
- `("nested", field, path, owner, concrete_type)` — a nested-dataclass field visible to CLI; its children follow immediately in the stream.

The walker drives the recursion. Consumers no longer recurse independently.

### The exclusion predicate — `_is_cli_excluded` (private, used only by the walker)

```python
def _is_cli_excluded(f: Field[Any]) -> bool:
  return f.metadata.get("cli", True) is False
```

The `is False` identity comparison is the strict trigger required by acceptance criterion 2. `None`, `0`, `""`, `[]` are all deliberately included because the criterion says "explicit `False`, not general falsy."

A single-walker-with-tags design is preferred over two walkers (leaf-only and leaf+nested) because it keeps exactly one recursion implementation and one exclusion check, best matching the owner's "single exclusion point" directive.

## 3. Consumer Integration

### `_configure_fields` (factory.py:382-601)

The most invasive change. The `for f in fields(clz):` loop and its nested/leaf branching are replaced by iteration over `_iter_cli_fields(clz)`. The method's explicit recursive call is removed — the walker drives recursion.

The method body dispatches on the tag:

- `("nested", ...)`: performs the existing nested-specific side effects — subcommand check, `factory._nested_prefix` assignment, duplicate-class detection via the `visited` set. The `visited` set is tracked as a `Factory` instance attribute during `configure_parser()` since recursion is now walker-driven.
- `("leaf", ...)`: performs the existing leaf body — registry check, arg-name construction, alias registration, `add_argument`.

The nested-prefix assignment happens when the `"nested"` marker is encountered, immediately before the walker yields its children — preserving the original ordering invariant.

### `list_fields` (factory.py:622-644)

Becomes trivial — delegate to the walker, filtering for `"leaf"` entries. Signature and return type unchanged; no external caller breaks.

### `list_fields_with_owners` (factory.py:646-669)

Same delegation pattern, returning the owner from the `"leaf"` entries. Signature and return type unchanged.

### `register_field` (registration.py:55-161)

Extended with a keyword-only `metadata` parameter (default `None`):

```python
def register_field(parent, name, field_type, default_factory=None, *, metadata=None):
```

When `metadata is None`, the existing `metadata={}` behavior is preserved (regression safe). When provided, it flows through to the `Field(...)` constructor. A plugin can call:

```python
register_field(ToolsConfig, "secret", SecretConfig, metadata={"cli": False})
```

to register a field loadable via TOML/env/defaults but invisible to the CLI argument generator.

## 4. Subtree Semantics

A nested-dataclass field with `metadata["cli"] is False` triggers the walker's `continue` — the entire subtree is pruned and no recursion occurs. Descendants with `cli=True` remain excluded because they are never visited. This closes the subtree bypass where an attacker could otherwise reach a secret leaf via `--subtree-leaf`.

When a nested-dataclass field is excluded, `factory._nested_prefix` is never set for the nested factory — which is correct because that subtree is CLI-invisible and its prefix does not need configuring.

The `visited` set for duplicate-class detection is not updated for excluded subtrees, so the same class appearing elsewhere (non-excluded) still triggers duplicate detection at the visible site. The excluded subtree does not poison detection for the visible tree.

## 5. Alias Suppression

Automatic. A field with `cli=False` is skipped entirely by the walker before it ever reaches the alias-registration block in `_configure_fields`. No `--<alias>` arguments are generated, and no `add_argument` call is made for either the canonical name or any alias. This closes the alias bypass where an attacker could use `--with xyz` to set an excluded field.

## 6. Security Guarantees

The mechanism provides the following guarantees, all of which hinge on the single property that argparse is the only code path that reads CLI arguments and only knows about fields for which `add_argument()` was called:

1. **No CLI argument registered** — `add_argument()` is never called for an excluded field. The argument does not appear in `--help`, is not accepted by the parser (passing `--secret-api-key xyz` yields `unrecognized arguments`), and creates no `dest` in the parsed `Namespace`.
2. **CLI-only exclusion** — the field remains loadable via TOML, env interpolation, and dataclass defaults. `get_config()` still merges TOML/env/defaults; the CLI merge step contributes nothing for the excluded field, so the non-CLI value survives.
3. **No `--help` exposure** — excluded fields do not appear in help text.
4. **Alias bypass closed** — aliases are suppressed because the field never reaches alias registration.
5. **Subtree bypass closed** — nested `cli=False` prunes the entire subtree; no descendant leaf is reachable via CLI.

## 7. In-Scope Security Addition: `suggest_cli=False`

When raising `ConfigError` for a field that is excluded from CLI, the error path must pass `suggest_cli=False` so error messages do not advertise the hidden CLI argument name (e.g., so an error for an excluded field does not suggest using `--secret-api-key`). This requires the error path to know whether a field is excluded, which is feasible via the centralized helper. This is folded into acceptance criterion 1 below as a sub-criterion.

## 8. Out-of-Scope / Backlog Items

The feature addresses CLI exposure only. The following gaps are out of scope for P1-004 and must be tracked separately:

1. **`__repr__` leaks secret values** — The dataclass `__repr__` (and the custom `__repr__` installed by `register_field`) includes all fields where `f.repr` is `True` (the default). `cli=False` does NOT set `repr=False`. A user who marks a field `cli=False` but does not also set `repr=False` will leak the secret via repr/logging/tracebacks. Recommendation: document the safe pattern `field(..., repr=False, metadata={"cli": False})`, and consider a separate follow-up task for either auto-wiring `repr=False` when `cli=False` or emitting a `logger.warning` when `cli=False` is set without `repr=False`. This is a design decision requiring human validation, deferred to a backlog task.
2. **TOML/env still hold the secret** — The feature relocates the secret from a world-readable surface (`/proc/<pid>/cmdline`, history, CI logs) to an owner-readable surface (TOML file perms, env vars). It does not eliminate the secret from the system. This is inherent to the feature's design and must be documented so users do not over-rely on the control.
3. **Regression test for parser dests** (recommended) — Add a regression test asserting the excluded field's value does NOT appear in the parser's known dests after `configure_parser()`, as a defensive guard against future regressions that re-introduce the argument.

## 9. Implementation Risks

### Primary risk: `_configure_fields` restructuring

The method currently interleaves recursion with side effects: nested-prefix assignment, `visited`-set bookkeeping, duplicate-class detection, registry mutations, and argument registration. Moving recursion into the walker requires careful re-ordering of these side effects into the `"nested"` branch of the dispatch. This is the highest-risk part of the implementation.

**Mitigation**: Add a golden test that records the exact sequence of `factory._nested_prefix` assignments for a 3-level nested config before the refactor, then asserts the same sequence after. The existing test suite (especially `test_cli_aliases.py` nested cases) plus new exclusion tests should catch ordering regressions.

### Secondary risks

- **Tagged-union yield type**: the walker yields tagged tuples rather than a `dataclass`-typed yield. This is a common Python pattern and acceptable; the alternative adds overhead.
- **Public API surface**: `list_fields` and `list_fields_with_owners` signatures and return types are unchanged; only internal implementation delegates to the walker. No external caller breaks.
- **`register_field` backward compatibility**: adding `metadata` as a keyword-only parameter with default `None` is backward compatible. Existing callers passing 3-4 positional args are unaffected. Document in the changelog.

## 10. Final Acceptance Criteria

The 7 criteria from TODO.md, with the `suggest_cli=False` addition folded into criterion 1 as a sub-criterion:

1. **Single exclusion point.** Metadata-based CLI exclusion is handled in one centralized, cleanly designed place — the `_iter_cli_fields` walker — applied consistently across `_configure_fields()`, `list_fields()`, `list_fields_with_owners()`, and any other field-list consumer. The strict `_is_cli_excluded(f)` predicate (`f.metadata.get("cli", True) is False`) lives inside the walker and is used nowhere else. No scattered function calls.
   - Sub-criterion: `ConfigError` handling for excluded fields passes `suggest_cli=False` so error messages do not advertise the hidden CLI argument name.
2. **Trigger condition.** Exclusion triggers only on `metadata["cli"] is False` (explicit `False`, not general falsy values like `0`, `""`, `None`). Absence of the key means "include."
3. **Scope — any field level.** Applies to both leaf fields and nested-dataclass fields.
   - Leaf field with `cli=False`: the CLI argument is skipped.
   - Nested-dataclass field with `cli=False`: the entire subtree is skipped (no recursion into the nested class).
4. **Alias suppression.** A field with `cli=False` also suppresses any `metadata["cli_aliases"]` registration — no `--<alias>` arguments are generated.
5. **Dynamic registration.** `register_field()` in `registration.py` is extended to accept optional metadata (keyword-only, default `None`), so plugins can mark a dynamically registered field as `cli=False`. Default `None` preserves the current `metadata={}` behavior.
6. **Regression safety.** Existing fields without `metadata["cli"]` (or with non-`False` values) behave unchanged.
7. **Tests.** Cover leaf exclusion, nested-subtree exclusion (no recursion), alias suppression, dynamic registration via `register_field()`, strict-trigger cases (`cli=None`, `cli=0`, `cli=""` all INCLUDED), and a secret-field scenario demonstrating the field is absent from `sys.argv`-derived parsing while still loadable via config/TOML/env/defaults.

## 11. Domain Agent Approval

Both domain agents — the API architect (analysis/api-cli-field-exclusion.md) and the security reviewer (analysis/security-cli-field-exclusion.md) — approve the design described above and agree that it satisfies all seven acceptance criteria plus the in-scope `suggest_cli=False` hardening. Both agents approve proceeding to implementation under the agreed single-walker design, with the implementation risk mitigation (golden test for `factory._nested_prefix` assignment sequence) in place before the `_configure_fields` refactor.