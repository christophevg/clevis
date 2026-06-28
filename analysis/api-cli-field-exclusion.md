# API Design: CLI Field Exclusion (P1-004)

**Date**: 2026-06-28
**Task**: P1-004 — Support excluding dataclass fields from CLI argument generation
**Issue**: https://github.com/christophevg/clevis/issues/30
**Reviewer**: API Architect Agent
**Status**: Design only — no implementation

## Summary

This document designs a single, centralized exclusion point for metadata-based
CLI argument suppression in clevis. The owner explicitly requires ONE
well-designed exclusion point rather than scattered checks across consumers.
The recommended design is a **single recursive walker** that becomes the sole
source of truth for "which fields are visible to the CLI subsystem," used by
all three consumers (`_configure_fields`, `list_fields`, `list_fields_with_owners`).

## Current Architecture

Three independent code paths walk the dataclass field tree, each with its own
recursion and leaf/nested branching logic:

### 1. `_configure_fields` (factory.py:382-601)
Recurses in place to add argparse arguments. Key structure (lines 400-439):
```python
for f in fields(clz):
  concrete_type = unpack_type(f.type)
  if is_dataclass(concrete_type):
    # ... nested prefix bookkeeping ...
    self._configure_fields(concrete_type, path + [f.name], nested_prefix, ...)
  else:
    # leaf: register arg name, add canonical + alias arguments
```
- Does NOT call `list_fields` — it has its own recursion.
- Reads `f.metadata.get("cli_aliases", [])` at line 462 for alias handling.
- Tracks `visited` set for duplicate-class detection (specific to this path).
- Mutates `factory._nested_prefix` on nested factories (specific to this path).

### 2. `list_fields` (factory.py:622-644)
Independent recursion returning `[(Field, path)]` for leaves only.

### 3. `list_fields_with_owners` (factory.py:646-669)
Independent recursion returning `[(Field, path, owner_class)]` for leaves only.

### 4. `register_field` (registration.py:55-161)
Dynamically adds a field to a parent dataclass. Currently hardcodes
`metadata={}` at line 150 when constructing the `Field`. There is no parameter
to pass metadata through.

### 5. Metadata conventions
`cli_aliases` is read via `f.metadata.get("cli_aliases", [])` with defensive
type-checking (lines 462-464, 478-479). This establishes the precedent that
field metadata is the CLI-control channel.

## Design Goals (from acceptance criteria)

1. **Single exclusion point**: one place decides "this field is invisible to
   the CLI subsystem." All consumers use it; no scattered checks.
2. **Strict trigger**: `metadata["cli"] is False` (explicit `False` only — not
   falsy). Absence of the key means "include."
3. **Any field level**: leaf fields skip their argument; nested-dataclass
   fields skip the entire subtree (no recursion).
4. **Alias suppression**: a `cli=False` field also suppresses
   `cli_aliases` registration — naturally handled by skipping the field
   entirely.
5. **Dynamic registration**: `register_field()` accepts optional metadata so
   plugins can mark a dynamically added field `cli=False`.
6. **Regression safety**: fields without `metadata["cli"]` or with non-`False`
   values behave unchanged.

## Recommended Design

### Decision: One walker, not a scattered predicate

The owner's directive — "avoid calling functions all over the place" — rules
out the seemingly simple option of a `_should_exclude_cli(field)` predicate
called at three separate iteration sites. That would technically be "one
predicate" but three call sites, which is exactly the scattering the owner
wants avoided.

Instead, the recommended design is a **single recursive generator** that
encapsulates both the tree walk and the exclusion decision. All three
consumers stop doing their own recursion and instead consume from this
walker. The exclusion check lives in exactly one place: inside the walker.

### The walker

Location: `src/clevis/factory.py` (private module-level function, not a
method, so it has no hidden `self` state and is easy to test in isolation).

```python
def _iter_cli_fields(
  clz: type,
  path: list[str] | None = None,
  owner: type | None = None,
) -> Iterator[tuple[Field[Any], list[str], type]]:
  """
  Single source of truth for fields visible to the CLI subsystem.

  Yields (field, path, owner_class) for every leaf field reachable from
  ``clz`` that is not excluded by metadata["cli"] is False.

  Exclusion rules:
    - Leaf field with metadata["cli"] is False  -> skipped (not yielded).
    - Nested-dataclass field with metadata["cli"] is False -> the entire
      subtree is skipped (no recursion into the nested class).
    - Any other value (including absence of the key, None, 0, "") -> included.

  This function is the ONLY place that decides CLI visibility. All field-list
  consumers (_configure_fields, list_fields, list_fields_with_owners) must
  obtain their fields through this walker.
  """
  if path is None:
    path = []
  current_owner = owner if owner is not None else clz
  for f in fields(clz):
    if _is_cli_excluded(f):
      continue  # single exclusion point: skip leaf OR skip subtree
    concrete_type = unpack_type(f.type)
    if is_dataclass(concrete_type):
      yield from _iter_cli_fields(concrete_type, path + [f.name], current_owner)
    else:
      yield (f, path, current_owner)
```

### The exclusion predicate (private, used only by the walker)

```python
def _is_cli_excluded(f: Field[Any]) -> bool:
  """
  Return True iff this field must be hidden from the CLI subsystem.

  Triggers ONLY on an explicit False:
    metadata["cli"] is False  -> True (exclude)
    metadata["cli"] absent    -> False (include)
    metadata["cli"] == None   -> False (include; None is not False)
    metadata["cli"] == 0       -> False (include; 0 is not False)
    metadata["cli"] == ""      -> False (include; "" is not False)
    metadata["cli"] == True    -> False (include)
  """
  return f.metadata.get("cli", True) is False
```

Note the `is False` comparison — this is the strict identity check that
satisfies acceptance criterion 2. `0`, `""`, `None` are all deliberately
included because the criterion says "explicit `False`, not general falsy."

### Why a single predicate is not enough

A predicate alone, called at three sites, leaves the recursion duplicated
three times and forces each site to independently decide "skip leaf" vs "skip
subtree." The walker collapses both decisions into one `continue` statement
(see comment in the walker). This is the cleanest expression of the owner's
"single exclusion point" requirement.

## Consumer Integration

### `_configure_fields` (factory.py:382-601)

This is the most invasive change because the method currently interleaves
recursion with prefix bookkeeping, duplicate-class detection, registry
mutations, and argument registration. The walker cannot absorb all of that;
it should only own the **field iteration + exclusion** concern.

Refactoring approach:

1. Replace the `for f in fields(clz):` loop and its nested/leaf branching with
   iteration over `_iter_cli_fields(clz)` at the top of the recursion.
2. **BUT** the walker yields only leaves, while `_configure_fields` needs to
   visit nested dataclasses too (to set `factory._nested_prefix`, detect
   duplicates, detect subcommand nesting). So we have two options:

   **Option A (recommended): walker yields nested markers too.** Extend the
   walker to yield either `("leaf", field, path, owner)` or
   `("nested", field, path, owner, concrete_type)` tagged tuples. Then
   `_configure_fields` consumes both kinds and performs its
   prefix/duplicate/subcommand bookkeeping on `("nested", ...)` entries. This
   keeps the exclusion check in ONE place (the walker still decides whether a
   nested field is skipped entirely) while preserving the configure-specific
   side effects.

   **Option B: walker stays leaf-only; `_configure_fields` keeps its own
   recursion but calls `_is_cli_excluded` at the top.** This re-introduces a
   second call site for the predicate, which violates the owner's directive.

   Option A is recommended because it keeps the predicate used in exactly one
   location (inside the walker). The cost is that the walker's yield type
   becomes a tagged union, which is a reasonable tradeoff for true
   centralization.

   Concretely, the walker becomes:
   ```python
   def _iter_cli_fields(clz, path=None, owner=None):
     """Yields ('leaf', field, path, owner) or ('nested', field, path, owner, type)."""
     ...
     for f in fields(clz):
       if _is_cli_excluded(f):
         continue
       concrete_type = unpack_type(f.type)
       if is_dataclass(concrete_type):
         yield ("nested", f, path, current_owner, concrete_type)
         yield from _iter_cli_fields(concrete_type, path + [f.name], current_owner)
       else:
         yield ("leaf", f, path, current_owner)
   ```

   `_configure_fields` then restructures its body to dispatch on the tag:
   ```python
   for kind, f, path_segment, owner_clz, *extra in _iter_cli_fields(clz, path):
     if kind == "nested":
       concrete_type = extra[0]
       # existing nested bookkeeping: subcommand check, nested_prefix,
       # duplicate-class detection, factory._nested_prefix set, recurse...
       # (the recurse call is removed — the walker already recurses)
     else:  # leaf
       # existing leaf body: registry check, arg name, aliases, add_argument
   ```

   Note: `_configure_fields` currently recurses explicitly. With the walker
   driving recursion, the method's own recursive call (line 437-439) is
   removed. The nested-specific logic (prefix, duplicate detection) moves
   into the `"nested"` branch of the dispatch. The `visited` set must be
   tracked as a closure variable or parameter since recursion is now
   walker-driven; the cleanest option is to keep a `visited` set on the
   `Factory` instance during `configure_parser()` and check it inside the
   `"nested"` branch.

   **Subtlety — duplicate detection**: the current code raises on
   `concrete_type in visited` before recursing (lines 422-427). With the
   walker, the check happens in the `"nested"` branch before processing the
   nested entry's children (which the walker yields next). This preserves the
   invariant.

   **Subtlety — nested prefix**: currently set on the nested factory before
   recursing. With walker-driven iteration, it must be set when the
   `"nested"` entry is encountered, before its children are yielded. Since the
   walker yields the `"nested"` marker immediately before recursing into
   children, the prefix assignment in the `"nested"` branch happens in the
   right order. Good.

### `list_fields` (factory.py:622-644)

Becomes trivial — delegate to the walker, filtering for `"leaf"` entries:
```python
def list_fields(self, clz=None, path=None):
  clz = self.config_class if clz is None else clz
  path = [] if path is None else path
  return [
    (f, p)
    for kind, f, p, _owner, *extra in _iter_cli_fields(clz, path)
    if kind == "leaf"
  ]
```

### `list_fields_with_owners` (factory.py:646-669)

Same, returning the owner:
```python
def list_fields_with_owners(self, clz=None, path=None):
  clz = self.config_class if clz is None else clz
  path = [] if path is None else path
  return [
    (f, p, owner)
    for kind, f, p, owner, *extra in _iter_cli_fields(clz, path)
    if kind == "leaf"
  ]
```

### `register_field` (registration.py:55-161)

Extend the signature to accept optional `metadata`:

```python
def register_field(
  parent: type[Any],
  name: str,
  field_type: type[Any],
  default_factory: Callable[[], Any] | None = None,
  metadata: dict[str, Any] | None = None,
) -> None:
```

Flow:
- `metadata` defaults to `None`; if `None`, use `{}` (preserving current
  behavior — regression safe).
- If provided, passed through to the `Field(...)` constructor at line 150:
  ```python
  new_field = Field(
    ...,
    metadata=metadata if metadata is not None else {},
    ...,
  )
  ```
- A plugin can call `register_field(ToolsConfig, "pkgq", PkgqToolConfig,
  metadata={"cli": False})` to register a field that is loadable via
  TOML/env/defaults but invisible to the CLI argument generator.

Document the parameter in the docstring with an example:
```python
register_field(ToolsConfig, "secret", SecretConfig, metadata={"cli": False})
# Field is in __dataclass_fields__, loadable via TOML [tools.secret],
# but no --tools-secret-* CLI arguments are generated.
```

## Edge Cases

| Case | Behavior | Why |
|------|----------|-----|
| `metadata={}` (no `cli` key) | Included | `_is_cli_excluded` returns False; regression safe |
| `metadata={"cli": False}` | Excluded | Strict `is False` check |
| `metadata={"cli": None}` | Included | `None is False` → False |
| `metadata={"cli": 0}` | Included | `0 is False` → False (0 is not False) |
| `metadata={"cli": ""}` | Included | `"" is False` → False |
| `metadata={"cli": True}` | Included | `True is False` → False |
| Leaf `cli=False` with `cli_aliases` | Aliases suppressed | Field is skipped entirely by walker; no alias registration happens |
| Nested `cli=False` | Entire subtree skipped | Walker's `continue` skips recursion; no descendants yielded |
| Nested `cli=False` with descendant that has `cli=True` | Still excluded | Subtree pruning is at the parent; descendants never visited |
| Dynamically registered field with `metadata={"cli": False}` | Excluded | Metadata flows through `register_field` into the Field object; walker sees it like any other |
| Field with `metadata={"cli": False}` but no `cli_aliases` | Excluded | Same as leaf exclusion; aliases are irrelevant |

### Type identity caveat for `is False`

`f.metadata.get("cli", True) is False` relies on Python's singleton `False`.
This is safe for `False` produced by Python literals (`{"cli": False}`) and
by boolean operations. It would NOT match a `bool` subclass instance, but
such subclasses are not produced by normal dataclass metadata. This is the
standard idiom for "strict False check" and matches the acceptance criterion
exactly.

### Interaction with nested-prefix bookkeeping

When a nested-dataclass field is excluded, the walker does not recurse, so
`factory._nested_prefix` is never set for the nested factory. This is
correct: if the subtree is CLI-invisible, its prefix does not need to be
configured. The nested factory remains in its default state, which is fine
because `configure_parser` for that nested class is never driven through the
CLI path. (It may still be driven if someone calls `get_config()` directly on
the nested class, in which case that class has its own factory and its own
`configure_parser` path — unaffected.)

### Interaction with duplicate-class detection

A nested-dataclass field excluded via `cli=False` is skipped before the
`visited` set is updated. If the same class appears elsewhere (non-excluded)
in the hierarchy, the duplicate detection still fires at the non-excluded
site. This is correct: the excluded subtree is not "visited" for CLI purposes,
so it should not poison duplicate detection for the visible tree.

## Risks and Tradeoffs

### Risk 1: Tagged-union yield type
The walker yields tagged tuples (`("leaf", ...)` / `("nested", ...)`). This is
slightly less ergonomic than two separate iterators. The alternative — a
`dataclass`-typed yield — adds overhead. Tagged tuples with a leading string
discriminator are a common Python pattern and readable enough. Acceptable.

### Risk 2: `_configure_fields` restructuring is non-trivial
The method currently mixes recursion with side effects. Moving recursion
into the walker requires careful re-ordering of the nested-prefix and
duplicate-detection side effects. This is the highest-risk part of the
implementation. Mitigation: the existing test suite (especially
`test_cli_aliases.py` nested cases) plus new exclusion tests should catch
ordering regressions. Recommend the implementer add a "golden" test that
records the exact sequence of `factory._nested_prefix` assignments for a
3-level nested config before the refactor, then asserts the same sequence
after.

### Risk 3: Two walkers vs one
An alternative design has two walkers: `_iter_cli_leaves` (leaf-only, for
`list_fields*`) and `_iter_cli_nodes` (leaf+nested, for `_configure_fields`),
both calling `_is_cli_excluded`. This keeps the predicate in one place but
duplicates the recursion logic. The single-walker-with-tags design is
preferred because it has exactly one recursion implementation; the exclusion
check appears once; the consumers just filter on the tag. This best matches
the owner's "single exclusion point" directive.

### Risk 4: Public API surface
`list_fields` and `list_fields_with_owners` are public-ish methods on
`Factory`. Their signatures and return types are unchanged by this design —
only their internal implementation delegates to the walker. No external
caller breaks. Good.

### Risk 5: `register_field` backward compatibility
Adding `metadata` as a keyword-only-or-positional optional parameter with
default `None` is backward compatible. Existing callers pass 3-4 positional
args and are unaffected. The new parameter is keyword-friendly. Recommend
making it keyword-only to avoid positional-arg confusion:
```python
def register_field(parent, name, field_type, default_factory=None, *, metadata=None):
```
This is a minor API evolution; document it in the changelog.

## Action Items

1. Implement `_is_cli_excluded` and `_iter_cli_fields` (with tagged yields) in
   `src/clevis/factory.py`.
2. Refactor `_configure_fields` to dispatch on walker tags; remove its
   explicit recursion; preserve nested-prefix and duplicate-detection side
   effects in the `"nested"` branch.
3. Delegate `list_fields` and `list_fields_with_owners` to the walker.
4. Add `metadata` keyword-only parameter to `register_field`; flow it into the
   `Field(...)` constructor.
5. Add tests covering:
   - Leaf exclusion (`cli=False` field absent from `sys.argv`-derived parsing,
     still loadable via config/TOML/env/defaults — the "secret field" scenario).
   - Nested-subtree exclusion (no recursion; descendants with `cli=True` still
     excluded).
   - Alias suppression (field with `cli=False` and `cli_aliases` produces no
     `--<alias>` args; confirm via `get_config` with `args=[]` not raising and
     via attempting to use the alias raising argparse error).
   - Dynamic registration with `metadata={"cli": False}` via `register_field`.
   - Strict-trigger cases: `cli=None`, `cli=0`, `cli=""` all INCLUDED.
   - Regression: existing tests in `test_cli_aliases.py` pass unchanged.
6. Document the `cli` metadata key in the user-facing docs (alongside
   `cli_aliases`).

## Conclusion

The recommended design places the exclusion decision in exactly one location
— inside `_iter_cli_fields`, the single recursive walker — and routes all
three field-list consumers through it. This satisfies the owner's directive
of "one well-designed exclusion point" without scattering predicate calls.
The tagged-yield shape lets `_configure_fields` preserve its
prefix/duplicate/subcommand side effects while delegating iteration and
exclusion to the walker. `register_field` gains a keyword-only `metadata`
parameter for plugin-driven exclusion. The strict `is False` trigger and
subtree-pruning semantics match every acceptance criterion.