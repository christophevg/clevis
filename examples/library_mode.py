"""Using Clevis as a library (not CLI).

Demonstrates how to use Clevis in library mode, disabling CLI
argument parsing and controlling configuration programmatically.

Features demonstrated:
- cli=False to disable sys.argv parsing
- args=[] for programmatic control
- Using in web frameworks (Flask, FastAPI, etc.)
- Testing with injected configuration
- Avoiding sys.argv interference

Run with:
    uv run python library_mode.py  # No CLI args needed

Note: This example does NOT use CLI arguments, demonstrating
library-only usage.
"""

from dataclasses import dataclass

from rich.pretty import pprint

from clevis import get_config, SecurityAction


@dataclass
class DatabaseConfig:
  """Database connection configuration."""

  host: str
  port: int = 5432
  user: str = "admin"
  password: str | None = None
  database: str = "mydb"


@dataclass
class AppConfig:
  """Application configuration for library usage."""

  app_name: str = "MyLibraryApp"
  debug: bool = False
  database: DatabaseConfig | None = None


# Example 1: Library mode with cli=False
# ======================================
# When using Clevis as a library (e.g., in a web framework or another
# application), you want to avoid CLI argument parsing that would
# interfere with sys.argv.

print("Example 1: Library mode with cli=False")
print("=" * 60)

config1 = get_config(
  AppConfig,
  name="library_app",
  cli=False,  # Disable CLI argument parsing completely
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
)

print("Loaded config (no CLI parsing):")
pprint(config1)
print()

# Example 2: Testing with args=[]
# =================================
# When testing, you can use args=[] to inject specific configuration
# values programmatically, avoiding sys.argv interference.

print("Example 2: Testing with args=[]")
print("=" * 60)

# Inject database configuration via args
config2 = get_config(
  AppConfig,
  name="library_app",
  cli=False,  # Still disable default CLI parsing
  args=["--database-host", "test.example.com", "--database-port", "3306", "--app-name", "TestApp"],
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
)

print("Loaded config with injected args:")
pprint(config2)
print()

# Example 3: Using in web frameworks
# ==================================
# Pattern for using Clevis in Flask/FastAPI applications

print("Example 3: Web framework integration pattern")
print("=" * 60)


class WebApplication:
  """Example of a web application using Clevis for configuration."""

  def __init__(self, config_args: list[str] | None = None):
    """Initialize web application with configuration.

    Args:
        config_args: Optional CLI-style args for testing (e.g., ["--debug", "--app-name", "TestApp"])
    """
    # In production: load from config files (no CLI)
    # In testing: use args=[] to inject test config
    self.config = get_config(
      AppConfig,
      name="webapp",
      cli=False,  # Never parse CLI in web framework
      args=config_args,  # Pass None or list of args
      security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
    )

  def run(self):
    """Run the application."""
    print(f"Running {self.config.app_name}")
    if self.config.debug:
      print("  Debug mode enabled")
    if self.config.database:
      print(f"  Connected to {self.config.database.host}:{self.config.database.port}")


# Production usage
app = WebApplication()
app.run()
print()

# Testing usage with injected config
# Note: args are CLI-style, booleans are flags
test_app = WebApplication(config_args=["--app-name", "TestApp", "--debug"])
test_app.run()
print()

# Example 4: Multiple applications with shared config
# ===================================================
# When building libraries that might be used together,
# each can have its own config without CLI conflicts

print("Example 4: Multiple libraries, no CLI conflicts")
print("=" * 60)


@dataclass
class CacheConfig:
  """Cache configuration for caching library."""

  enabled: bool = True
  ttl: int = 3600
  backend: str = "redis"


@dataclass
class LoggerConfig:
  """Logging configuration for logging library."""

  level: str = "INFO"
  format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


# Each library loads its own config independently
cache_config = get_config(
  CacheConfig,
  name="cache",
  cli=False,
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
)

logger_config = get_config(
  LoggerConfig,
  name="logger",
  cli=False,
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
)

print("Cache config:")
pprint(cache_config)
print()
print("Logger config:")
pprint(logger_config)
print()

# Example 5: Configuration hierarchy
# ===================================
# Demonstrating precedence when using library mode

print("Example 5: Configuration precedence in library mode")
print("=" * 60)

# Even in library mode, the precedence still applies:
# args[] > project config > user config > defaults
#
# When cli=False:
# - args[] is the ONLY way to override via code
# - No sys.argv interference
# - Perfect for testing and embedding

config5 = get_config(
  AppConfig,
  name="library_app",
  cli=False,
  args=["--debug"],
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
)

print("Config with args override (--debug):")
pprint(config5)
print()

# Example 6: Testing pattern with fixtures
# =========================================

print("Example 6: Testing with configuration fixtures")
print("=" * 60)


def create_test_config(host: str = "localhost", port: int = 5432, database: str = "test_db"):
  """Create a test configuration programmatically.

  This pattern is useful for unit tests where you need
  specific configuration values without touching sys.argv.
  """
  return get_config(
    AppConfig,
    name="test_app",
    cli=False,
    args=[
      "--app-name",
      "TestApp",
      "--database-host",
      host,
      "--database-port",
      str(port),
      "--database-database",
      database,
    ],
    security={"file_permissions": SecurityAction.DONT_CHECK, "directory_permissions": SecurityAction.DONT_CHECK},
  )


test_config = create_test_config(host="test.example.com", port=3306, database="test_db")
print("Test config:")
pprint(test_config)
print()

print("Summary")
print("=" * 60)
print("Library mode best practices:")
print("  1. Use cli=False to avoid sys.argv parsing")
print("  2. Use args=[] to inject configuration programmatically")
print("  3. Set security checks appropriately (LOG/DONT_CHECK for libraries)")
print("  4. Each library can have its own config name")
print("  5. Perfect for web frameworks, testing, and embedding")