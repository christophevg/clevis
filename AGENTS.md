# Clevis Agent Guide

Essential context for working on the Clevis codebase. For user-facing documentation, see [README.md](README.md).

### Retry Policy

**Never retry the same failing command more than 3 times.** After 3 failed attempts, STOP and ask the user for permission before trying again. This gives the user a chance to intervene, investigate, or provide guidance.

Repeatedly retrying a failing command wastes context budget and processing credit without making progress. Common scenarios where this happens:

- `make publish` upload fails with HTTP 400 (version may already be on PyPI)
- CI workflow check times out or returns transient errors
- A tool produces output that exceeds size limits

When a command fails:
1. **First attempt**: Run it, observe the error.
2. **Second attempt**: Adjust parameters (e.g. tighter `post_filter`, higher
   `timeout_ms`) and try once more.
3. **Third attempt**: Try a different approach if one is obvious.
4. **Stop**: Ask the user — "I've tried 3 times and it's still failing with
   [error]. Should I continue trying, or do you want to investigate?"

Do NOT silently keep retrying with the same or slightly tweaked parameters.

Don't look for workarounds!

Don't try to spawn a random agent to do something you don't have the right tool for.

### Denied Permissions

When the user denies the use of a tool, don't look for a work around. ASK what to do instead! There is a reason why the user denied the use of the tool.

## Conventions

- **Indentation**: Two spaces in all file types.
- **Package manager**: `uv` (see `Makefile` for standard targets).
- **Code quality**: `make check` runs format, lint, typecheck, and test.
- **Entry point**: `python -m yoker` is the application entry point.
- **Version source of truth**: `src/yoker/__init__.py` must match `pyproject.toml`.
- **Commit attribution**: Use `🤖 Implemented together with Yoker` as the trailer line on agent-made commits. No `Co-authored-by` format.
- **Fully qualified imports**: `from yoker.backends.protocol import ChatChunk` — not `from yoker.backends import ChatChunk`.

## Makefile

The Makefile has many targets that are useful and available through the `make` tool:

```
build           Build distribution packages
check-all       Run all quality checks and test all
check           Run all quality checks and test
clean-all       Remove virtualenv and lock file
clean-sessions  Delete session .jsonl files older than $(SESSION_MAX_AGE_DAYS) days
clean           Remove build artifacts
demo            Generate main session screenshot (media/session.svg)
demos           Generate all demo screenshots
demos-to-docs   Copy generated demo files to docs/_static folder
docs-view       Build and open documentation
docs            Build HTML documentation
env-dev         Install all dependencies (dev + docs)
env-run         Install runtime dependencies only
format-check    Run all quality checks
format          Format code and fix linting issues
install-pythons Install Python 3.10, 3.11, 3.12
lint            Check code for linting issues
pre-publish     Pre-publication checks (run before publishing)
publish-test    Publish to TestPyPI
publish         Publish to PyPI (clean + build + pre-publish + upload)
upload          Upload to PyPI only (DON'T USE DIRECTLY — use `publish` target)
run             Run the application
test-all        Run tests on all Python versions
test-cov        Run tests with coverage
test            Run tests (usage: make test / optional: TEST=file|file:test_name)
typecheck       Run type checking
```

## Tool Output Discipline

**Always use `post_filter` on every tool call** to keep only lines relevant to
the task. Tool outputs can be very large and consume context budget rapidly.

- `make test` / `make check`: `post_filter="FAILED|ERROR|error|Traceback|assert"`
  — positive output (passing tests, formatting success) is useless noise.
- `read` / `search` on large files: filter for structure markers (`class |def |import `)
  or specific patterns (`TODO|FIXME|HACK`).
- `git log` / `git diff`: filter for the specific file, author, or pattern you need.
- `list` on large directories: use `pattern` or `post_filter` to avoid flooding
  context with thousands of entries.

**Rule of thumb**: if you expect more than ~20 lines of output, you should be filtering. Not filtering wastes context and processing credit on irrelevant content.
