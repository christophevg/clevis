# Clevis Examples

This directory contains example scripts demonstrating all features of Clevis, a configuration management library for Python projects with dataclass-based schemas.

## Progressive Learning Path

We recommend reading the examples in this order to build understanding progressively:

1. **[main.py](main.py)** - Start here for basics
   Configuration loading from environment variables, CLI arguments, and TOML files.

2. **[nested.py](nested.py)** - Organizing configuration hierarchies
   Nested dataclasses and TOML sections for structured configuration.

3. **[validation.py](validation.py)** - Custom validation rules
   Post-initialization validation, error handling, and helpful error messages.

4. **[environment.py](environment.py)** - Environment variable interpolation
   Using `${VAR}` syntax in TOML files for dynamic configuration.

5. **[factory.py](factory.py)** - Shared configuration parsers
   Using factories to coordinate configuration across multiple components.

6. **[commands.py](commands.py)** - CLI subcommands
   Building command-line applications with multiple subcommands.

7. **[library_mode.py](library_mode.py)** - Library-only usage
   Using Clevis in web frameworks, testing, and embedded contexts.

8. **[dynamic.py](dynamic.py)** - Dynamic field registration (Advanced)
   Plugin architectures with runtime configuration injection.

9. **[plugin.py](plugin.py)** - Plugin pattern (Advanced)
   Practical example of plugin configuration registration.

## Example Summary

| Example | Purpose | Key Features |
|---------|---------|--------------|
| [main.py](main.py) | Basic configuration | Environment variables, CLI args, TOML files, security validation |
| [nested.py](nested.py) | Configuration hierarchy | Nested dataclasses, TOML sections, `@configclass` decorator |
| [validation.py](validation.py) | Custom validation | `__post_init__`, regex validation, range checks, required fields |
| [environment.py](environment.py) | Environment interpolation | `${VAR}` syntax, type conversion, secure credentials |
| [factory.py](factory.py) | Shared parsers | Multiple configs, prefix namespacing, shared `ArgumentParser` |
| [commands.py](commands.py) | CLI subcommands | `cmd` parameter, command aliases, per-command configuration |
| [library_mode.py](library_mode.py) | Library usage | `cli=False`, `args=[]`, web framework integration, testing |
| [dynamic.py](dynamic.py) | Dynamic registration | `register_field()`, plugin architecture, runtime injection |
| [plugin.py](plugin.py) | Plugin pattern | Practical plugin example, module-level registration |

## Prerequisites

Install Clevis with required extras:

```bash
# Basic installation
pip install clevis

# For environment.py (environment variable interpolation)
pip install clevis[envtoml]

# For development/testing
pip install clevis[dev]
```

## Running Examples

Each example can be run directly:

```bash
# Basic usage
uv run python main.py

# Show help for CLI arguments
uv run python main.py --help

# Override with CLI arguments
uv run python main.py --database-host localhost --features-enabled

# Use environment variables
ENV=test uv run python main.py

# Library mode (no CLI)
uv run python library_mode.py
```

### TOML Configuration Files

Most examples use auto-discovered TOML files. Clevis searches for:

- `./<name>.toml` (project directory)
- `./.<name>.toml` (project directory, hidden)
- `~/.<name>.toml` (user directory)

For example, `main.py` looks for:
- `./app.toml` or `./.app.toml`
- `~/.app.toml`

Example files are provided:
- [nested.toml](nested.toml) - For nested.py
- [validation.toml](validation.toml) - For validation.py
- [environment.toml](environment.toml) - For environment.py

## Feature Matrix

| Feature | main | nested | validation | environment | factory | commands | library_mode | dynamic | plugin |
|---------|------|--------|------------|-------------|---------|----------|--------------|---------|--------|
| Environment variables | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| CLI arguments | ✓ | ✓ | ✓ | - | ✓ | ✓ | - | ✓ | ✓ |
| TOML files | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Nested configs | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Security validation | ✓ | - | ✓ | - | ✓ | - | ✓ | ✓ | ✓ |
| Custom validation | - | - | ✓ | - | - | - | - | - | - |
| `${VAR}` interpolation | - | - | - | ✓ | - | - | - | - | - |
| Shared parser | - | - | - | - | ✓ | - | - | - | - |
| Subcommands | - | - | - | - | - | ✓ | - | - | - |
| Library mode (`cli=False`) | - | - | - | - | - | - | ✓ | - | - |
| Dynamic registration | - | - | - | - | - | - | - | ✓ | ✓ |
| Plugin pattern | - | - | - | - | - | - | - | - | ✓ |

## Detailed Examples

### 1. Basic Configuration (main.py)

Demonstrates the core functionality:
- Defining configuration dataclasses with type hints
- Automatic configuration discovery (user/project directories)
- Priority: CLI > environment > TOML > defaults
- Security validation for file permissions

```bash
uv run python main.py
uv run python main.py --help
ENV=test uv run python main.py --database-host localhost
```

### 2. Nested Configuration (nested.py)

Organizing configuration hierarchies:
- Nested dataclasses for logical grouping
- `@configclass` decorator only on top-level
- TOML sections map to nested configs
- CLI arguments with namespacing (`--tool-settings-x`)

```bash
uv run python nested.py
uv run python nested.py --tool-settings-x 10
```

### 3. Validation (validation.py)

Custom validation rules:
- `__post_init__` for validation logic
- Regex validation for URLs
- Range validation for numeric values
- Custom `ConfigError` with helpful messages

```bash
uv run python validation.py --help
uv run python validation.py --server-url "http://localhost:8080"
```

### 4. Environment Interpolation (environment.py)

Dynamic configuration from environment:
- `${VAR}` syntax in TOML files
- Automatic type conversion
- Secure credential handling
- Requires `clevis[envtoml]`

```bash
export DB_HOST=localhost
export DB_PORT=5432
uv run python environment.py
```

### 5. Factory Pattern (factory.py)

Shared configuration across components:
- `get_factory()` for configuration management
- Prefix namespacing (`--app1-name`, `--app2-name`)
- Shared `ArgumentParser` for unified CLI
- Multi-package configuration coordination

```bash
uv run python factory.py --help
uv run python factory.py --app1-name "first" --app2-name "second"
```

### 6. Subcommands (commands.py)

CLI applications with multiple commands:
- `cmd` parameter for subcommand definition
- Command aliases (`c`, `chk` for `check`)
- Per-command configuration classes
- Global configuration sharing

```bash
uv run python commands.py --help
uv run python commands.py check --verbose
uv run python commands.py print --rich
```

### 7. Library Mode (library_mode.py)

Using Clevis in non-CLI contexts:
- `cli=False` to disable `sys.argv` parsing
- `args=[]` for programmatic control
- Web framework integration patterns
- Testing with injected configuration

```bash
uv run python library_mode.py  # No CLI interference
```

### 8. Dynamic Registration (dynamic.py)

Plugin architecture configuration:
- `register_field()` for runtime injection
- Non-frozen parent configs
- Plugin discovery and registration
- Complete workflow examples

```bash
uv run python dynamic.py
uv run python dynamic.py --help
```

### 9. Plugin Pattern (plugin.py)

Practical plugin implementation:
- Module-level configuration registration
- Integration with existing configs
- TOML and CLI support
- Real-world plugin structure

```bash
uv run python plugin.py --help
uv run python plugin.py --pkgq-timeout 45
```

## Configuration Priority

Clevis uses a clear priority order (highest to lowest):

1. **CLI arguments** - `--database-host localhost`
2. **Environment variables** - `ENV=test`
3. **Project TOML** - `./<name>.toml`
4. **User TOML** - `~/.<name>.toml`
5. **Default values** - Dataclass defaults

## Security Features

Clevis validates configuration file security:

```python
from clevis import get_config, SecurityAction

config = get_config(
  AppConfig,
  security={
    "file_permissions": SecurityAction.LOG,      # Log warnings
    "directory_permissions": SecurityAction.LOG,  # Log warnings
  }
)
```

Security actions:
- `SecurityAction.REJECT` - Raise error (default)
- `SecurityAction.LOG` - Log warning
- `SecurityAction.DONT_CHECK` - Skip validation

## Next Steps

After working through the examples:

1. Read the [API documentation](https://clevis.readthedocs.io)
2. Review the [source code](../src/clevis/) for implementation details
3. Check the [test suite](../tests/) for comprehensive usage patterns
4. Build your own configuration with the patterns that fit your needs

## Support

- **Documentation**: https://clevis.readthedocs.io
- **Repository**: https://github.com/christophevg/clevis
- **Issues**: https://github.com/christophevg/clevis/issues