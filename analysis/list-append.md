# Design: List-Append Convention for Config Cascade (`@append` Sentinel)

**Date**: 2026-09-01
**Task**: Feature design (pre-backlog; register as MBI when picked up)
**Status**: Design Complete — awaiting implementation decision

## Summary

This document specifies a convention that lets later layers of the
configuration cascade **append** to a list defined at an earlier level,
instead of replacing it. A list whose **first element** is the sentinel
string `"@append"` triggers append semantics:

```toml
# user.toml
packages = [1, 2, 3]

# project.toml
packages = ["@append", 4, 5]

# effective config
packages = [1, 2, 3, 4, 5]
```

The default replace strategy is unchanged. Additionally, the dataclass
field defaults participate as the base of the cascade, so a first-level
`"@append"` list extends the dataclass default list. The sentinel string
is overridable via a `get_config` argument for users whose data may
legitimately start a list with `"@append"`.

---

## 1. Motivation

Today the cascade middle layer replaces lists wholesale (deep merge:
nested dicts merge recursively, lists and scalars are replaced). To add
one item to a list defined at user level, the project level must repeat
the full list. With the append convention, the project level states only
the delta. This also composes across more than two levels and works in
nested tables.

## 2. Current Architecture (as of 2026-09)

Relevant code, all in `src/clevis/__init__.py`:

### 2.1 Pipeline

```
get_config(clz, name, user, project, cli, args, security, cascade)
    |
    v
[1] Build active cascade (default: user TOML, project TOML; or custom)
    |
    v
[2] Middle cascade merge:  cfg = deep_merge(cfg, provider())   (line ~942)
    |                          cfg starts as {}
    v
[3] Subcommand extraction: pop [cmd] section to root level
    |
    v
[4] CLI merge: _merge_list_args(clz, cli_args, cfg)            (line ~971)
    |          - CLI list values append to TOML base
    |          - "--no-field" (empty list) clears to []
    |          - non-list CLI args replace
    v
[5] dacite from_dict (fills dataclass defaults for missing keys,
    casts list -> tuple / set per field type)                 (line ~976)
    |
    v
  Config instance
```

### 2.2 `deep_merge(base, overlay)` (line 603, exported in `__all__`)

- Both values dicts at a key -> recurse.
- Otherwise -> overlay wins (lists replaced, not appended).
- Inputs are not modified (recursive copies).

### 2.3 `_get_list_fields(clz, prefix)` / `_merge_list_args` (line 739)

CLI layer only. Appends CLI list values onto the TOML base for
`list[T]` fields. Non-list CLI args replace.

### 2.4 Where dataclass defaults enter today

Defaults are **not** part of the merge. They are filled by dacite at
step [5] for keys absent from the merged config. Consequence: CLI list
values currently append onto the *TOML* value, but when no TOML level
defines the field, CLI values *replace* the dataclass default
(dacite never sees the key). There is no defaults bookend provider in
the code (TODO.md mentions one as design prose; it does not exist).

### 2.5 Field-owner tracking

`factory.py` `_registered_field_owners` is CLI-parser registration
bookkeeping. Unaffected by any merge-layer change.

## 3. Proposed Design

### 3.1 Convention

- Applies to values of list type at any depth (root keys and inside
  nested tables) in the **cascade middle layer only**.
- Rule: if `overlay[key]` is a list and `overlay[key][0] == sentinel`,
  the merge result is `base[key] + overlay[key][1:]` when
  `base[key]` exists and is a list; otherwise `overlay[key][1:]`.
- The sentinel applies only when it is the **first** element. Any
  other position is a literal string value.
- CLI layer (`_merge_list_args`) never interprets the sentinel; CLI
  values are appended as-is on top of the cascade result.

### 3.2 `deep_merge` changes (in-place, additive)

```python
DEFAULT_APPEND_SENTINEL = "@append"

def deep_merge(
  base: dict[str, Any],
  overlay: dict[str, Any],
  *,
  append_sentinel: str = DEFAULT_APPEND_SENTINEL,
) -> dict[str, Any]:
```

Merge rules per key (overlay value is `v`):

| `v` condition                       | base condition              | result                       |
|-------------------------------------|-----------------------------|------------------------------|
| list, `v[0] == append_sentinel`     | key in base, base is list   | `list(base_list) + v[1:]`    |
| list, `v[0] == append_sentinel`     | no base, or base not a list | `v[1:]` (warn if base was non-list non-missing) |
| list, `v == [append_sentinel]`      | key in base, base is list   | base list unchanged (no-op)  |
| list, no sentinel                   | any                         | `v` (unchanged behavior)     |
| dict / scalar / other               | any                         | unchanged behavior           |

- Sentinel stripping: `v[0]` equals the sentinel exactly (string
  comparison; `v` empty list -> plain replace, unchanged).
- New lists are constructed (`list(base_list) + rest`); the input
  dicts are never mutated (existing contract, also protects
  dataclass default lists, see 3.3).
- `append_sentinel` is threaded through both recursive calls.
- Backwards compatible: existing two-positional-arg callers keep
  behavior; only configs whose lists legitimately start with the
  literal `"@append"` change meaning (documented limitation,
  changelog note).

### 3.3 Dataclass defaults as cascade base (new)

To support `"@append"` at the *first* provider level extending the
dataclass default list (owner decision: defaults must be the base, not
discarded):

1. New internal helper `_get_list_defaults(clz) -> dict[str, list]`:
   - Traverses the dataclass (same traversal style as
     `_get_list_fields`, including nested dataclasses) collecting
     dotted paths of list-typed fields that have a resolved default
     list (`default=list` or `default_factory` returning a list).
   - Returns **copies** of the default lists. `field(default=[...])`
     lists are shared mutable class state; merge must never mutate
     them.
2. `get_config` seeds the cascade before the provider loop:

   ```python
   cfg: dict[str, Any] = _get_list_defaults(clz)
   for provider in active_cascade:
     cfg = deep_merge(cfg, provider(), append_sentinel=append_sentinel)
   ```

   Applies to both default and custom cascades (defaults represent the
   dataclass, not a config source).

**Scoping decision**: only list-typed fields are seeded. Scalar and
nested-table defaults stay dacite-driven. Seeding all defaults would
silently change nested-table partial-merge semantics (a partially
specified `[db]` table at TOML level would lose dataclass defaults for
unspecified keys) and is not part of this feature.

**Known consequence (accepted)**: CLI list args now append onto the
dataclass default when no TOML level defines the field:

```
packages: list[str] = ["d1", "d2"]     (dataclass default)
--pkg x  ->  ["d1", "d2", "x"]         (today: ["x"])
```

This is the consistent reading of "append to the default list". A small
number of existing tests may pin the old behavior; update them
intentionally and note it in the changelog. (`--no-field` still clears
to `[]`, so a replace-from-scratch path exists.)

### 3.4 Sentinel override (owner decision #3)

```python
def get_config(
  ...,
  append_sentinel: str | None = "@append",
) -> T:
```

- Custom string (e.g. `"@@append"`) for users whose data legitimately
  starts lists with `"@append"`.
- `None` disables the convention entirely (off-switch; lists always
  replace, defaults seeding still happens but is then invisible for
  plain lists — see 3.5 note).
- Threaded into every `deep_merge` call in the cascade loop. The CLI
  layer is not sentinel-aware.

### 3.5 Interaction matrix

| Scenario                                          | Result                                   |
|---------------------------------------------------|------------------------------------------|
| user `[a,b]`, project `["@append",c]`             | `[a,b,c]`                                |
| dataclass default `[a]`, first provider `["@append",b]` | `[a,b]`                            |
| first provider `["@append",b]`, no default        | `[b]` (sentinel stripped)                |
| project `["@append"]` only                        | base list unchanged                      |
| base scalar, project `["@append",x]`              | `[x]` + warning                          |
| project `[x,y]` (no sentinel)                     | `[x,y]` (replace, unchanged)             |
| CLI `--f c` on top of cascade `[a,b]`             | `[a,b,c]` (unchanged CLI semantics)      |
| `--no-f`                                          | `[]` (unchanged)                         |
| sentinel inside nested table                      | works (deep_merge recurses)              |
| `tuple`/`set` fields                              | unaffected; dacite casts after merge     |

Note on `append_sentinel=None`: seeding still seeds list defaults, and
without a sentinel there is no way to append at TOML level — the seed
only matters when a later level or CLI appends. Verify in tests that
`append_sentinel=None` behaves exactly like pre-feature replace
semantics.

## 4. Test Plan

### 4.1 `tests/test_config_cascade.py` — `TestDeepMergeListAppend`

- append onto base list; multi-item rest; empty rest (`["@append"]` no-op)
- no base -> stripped remainder; empty base list -> append works
- base scalar / dict -> remainder + warning (use `caplog`)
- base is tuple-like? (TOML lists are lists; only in-process callers
  could pass tuples — test list-ness strictly)
- nested tables: append inside `[db]` at depth 2 and 3
- input immutability: base, overlay, and nested lists unchanged after merge
- custom sentinel string honored; `append_sentinel=None` -> replace
- list legitimately containing `"@append"` as second element (literal)

### 4.2 `tests/test_list_append.py` — integration

- dataclass default + `@append` at first provider (user/project TOML
  and custom cascade variants)
- three-level chain: default -> user `@append` -> project `@append`
- TOML `@append` + CLI values on top; `--no-field` clears everything
- scalar fields and nested-table partial merge unchanged (guard tests)
- `list[tuple]` / `list[set]`? — confirm dacite cast still correct
- triage existing failures: intentional-change (update + changelog)
  vs regression (fix). Known candidates: CLI-over-default tests
  (`test_cli_aliases.py` line ~450 uses defaults + CLI values).

## 5. Documentation Plan

- README: cascade section — new "List append (`@append`)" subsection
  with examples (user/project TOML and dataclass default).
- `docs/` pages covering config cascade (mirror README text).
- CHANGELOG: Unreleased — feature entry + behavior-change note for
  CLI-over-defaults + literal `"@append"` limitation.
- REQUIREMENTS.md: new requirement (next free R-number, e.g. R120)
  with the acceptance rules from 3.1/3.5.
- TODO.md: task entry referencing this document.
- `src/clevis/__init__.pyi`: update `deep_merge` signature and
  docstring; note `append_sentinel` on `get_config` stub.

## 6. Implementation Checklist

1. `DEFAULT_APPEND_SENTINEL` constant + `deep_merge` sentinel logic
   (with `append_sentinel` param, recursion threading, warnings).
2. `_get_list_defaults(clz)` helper (traversal + copies).
3. `get_config`: `append_sentinel` parameter; seed cascade with
   `_get_list_defaults(clz)`; thread sentinel into `deep_merge`.
4. Stub (`__init__.pyi`) updates.
5. Tests (4.1, 4.2) — TDD: write failing tests first.
6. Docs (section 5).
7. `make check` gate; fix triage per 4.2.
8. Optional: API review (api-architect) + security review
   (security-engineer) pass, mirroring P2-011 treatment of the CLI
   list-append feature. Security surface is minimal: the sentinel is
   config-content semantics, no file/permission involvement; the
   review should focus on the `append_sentinel=None` off-switch and
   warning-vs-error choice for non-list bases.

## 7. Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Implement in-place in `deep_merge` (additive sentinel check) | Convention only activates on sentinel; non-sentinel behavior byte-identical; `deep_merge` already public API |
| 2 | First-level `@append` extends dataclass default list (defaults seeded as cascade base, list fields only) | Owner decision; "append to the default list" is the feature's stated goal |
| 3 | `append_sentinel: str \| None = "@append"` on `get_config`; `None` disables | Owner decision; escape hatch for data containing the literal sentinel |
| 4 | CLI args append onto seeded defaults (behavior change vs today) | Consistency; owner asked to confirm — recommendation accepted in design review 2026-09-01 |
| 5 | No escape hatch for literal `"@append"` beyond overriding the sentinel | Simplest v1; overriding the sentinel is the escape hatch |
| 6 | Sentinel stripped (remainder used) when base missing / non-list; warning (not error) on non-list base | Keeps first-level UX simple; error would make `@append` unusable without knowing base state |

## 8. Risks / Open Items

- **Literal `"@append"` as first list item** changes meaning for
  existing configs. Mitigated by overridable sentinel + changelog
  note. Search-able risk: low (sentinel string is unusual).
- **CLI-over-defaults behavior change** may surface in downstream
  users' tests; changelog must call it out explicitly.
- **`_get_list_defaults` traversal** must handle: nested dataclasses,
  `Optional[list[T]]` with a default (decide: seed only when default
  resolves to an actual list), `init=False` fields (skip — dacite
  ignores them anyway), and inheritance (walk `mro`-resolved fields
  the same way `_get_list_fields` does).
- Register the MBI in PLAN.md / assign a P-number when this moves to
  implementation.