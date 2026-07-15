# Consensus: P1-006 — Configurable Config Override Cascade

## Agents Invoked

| Agent | Scope | Status |
|-------|-------|--------|
| api-architect | Backend API design | ✅ Approved |
| security-engineer | Security review | ✅ Approved (with implementation requirements) |

## Design Summary

### API Design (api-architect)
1. `ConfigProvider` Protocol: zero-argument callable `__call__() -> dict[str, Any]`
2. `UserConfigProvider` / `ProjectConfigProvider` classes encapsulate security + TOML loading
3. `DEFAULT_CASCADE` as tuple of provider classes (need name + security at runtime)
4. `cascade` parameter: None = build from DEFAULT_CASCADE filtered by user/project; list = used directly
5. `deep_merge` as new standalone function for recursive dict merge
6. `load(fp)` / `loads(s)` matching stdlib tomllib conventions, with `load_toml`/`loads_toml` aliases
7. Subcommand extraction remains fixed post-cascade transform

### Security Requirements (security-engineer)
1. Security checks MUST move into default providers (not stay in get_config)
2. `security` parameter backward compat: construct default providers with security config when no cascade; ignore when custom cascade (with info log)
3. Provider classes must be public API (safe building blocks for custom providers)
4. `load_toml`/`loads_toml` are raw parsers (no security checks, like stdlib)
5. Deep merge increases tamper precision — documented as security-relevant breaking change
6. Custom provider security ownership must be documented

## Consensus

All invoked agents approve the design. Security findings are implementation requirements, not design rejections. The api-architect's design already incorporates the security requirements (providers encapsulate security checks).

## References

- API analysis: `analysis/api-config-cascade.md`
- Security analysis: `analysis/security-config-cascade.md`
- GitHub Issue: #33