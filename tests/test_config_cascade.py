"""Tests for configurable config override cascade + public TOML API (P1-006)."""

import io
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from clevis import (
  DEFAULT_CASCADE,
  ConfigProvider,
  FileConfigProvider,
  ProjectConfigProvider,
  SecurityAction,
  SecurityError,
  UserConfigProvider,
  _reset_factories,
  build_default_cascade,
  deep_merge,
  get_config,
  load,
  load_toml,
  load_toml_file,
  loads,
  loads_toml,
)


# Shared minimal config used by the default-cascade flag-filtering tests.
@dataclass
class Config:
  name: str = "default"


# ---------------------------------------------------------------------------
# ConfigProvider Protocol
# ---------------------------------------------------------------------------


class TestConfigProviderProtocol:
  """Tests for the ConfigProvider Protocol."""

  def test_protocol_is_runtime_checkable(self):
    """ConfigProvider should be a runtime_checkable Protocol."""
    assert isinstance(UserConfigProvider("x"), ConfigProvider)

  def test_simple_callable_satisfies_protocol(self):
    """A zero-arg callable returning a dict satisfies the Protocol."""

    class MyProvider:
      def __call__(self) -> dict:
        return {"a": 1}

    assert isinstance(MyProvider(), ConfigProvider)

  def test_function_satisfies_protocol(self):
    """A plain function returning a dict satisfies the Protocol."""

    def my_provider() -> dict:
      return {"a": 1}

    assert isinstance(my_provider, ConfigProvider)


# ---------------------------------------------------------------------------
# UserConfigProvider / ProjectConfigProvider
# ---------------------------------------------------------------------------


class TestUserConfigProvider:
  """Tests for UserConfigProvider."""

  def test_returns_dict_when_file_exists(self, monkeypatch, tmp_path):
    """UserConfigProvider loads user TOML from ~/.{name}.toml."""
    config_file = tmp_path / ".myapp.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o600)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    provider = UserConfigProvider(
      "myapp",
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    result = provider()
    assert result == {"name": "test"}

  def test_returns_empty_dict_when_file_missing(self, monkeypatch, tmp_path):
    """UserConfigProvider returns {} when file does not exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    provider = UserConfigProvider("nonexistent")
    assert provider() == {}

  def test_raises_on_insecure_permissions(self, monkeypatch, tmp_path):
    """UserConfigProvider raises SecurityError for world-readable files."""
    config_file = tmp_path / ".myapp.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o644)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    provider = UserConfigProvider("myapp")
    with pytest.raises(SecurityError) as exc_info:
      provider()
    assert exc_info.value.check == "file_permissions"

  def test_default_security_is_reject(self, monkeypatch, tmp_path):
    """Default security config is REJECT for both checks."""
    config_file = tmp_path / ".myapp.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o644)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    provider = UserConfigProvider("myapp")
    # World-readable file should be rejected by default.
    with pytest.raises(SecurityError):
      provider()


class TestProjectConfigProvider:
  """Tests for ProjectConfigProvider."""

  def test_returns_dict_when_file_exists(self, tmp_path, monkeypatch):
    """ProjectConfigProvider loads project TOML from ./{name}.toml."""
    config_file = tmp_path / "myapp.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o600)
    monkeypatch.chdir(tmp_path)

    provider = ProjectConfigProvider(
      "myapp",
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    result = provider()
    assert result == {"name": "test"}

  def test_returns_empty_dict_when_file_missing(self, tmp_path, monkeypatch):
    """ProjectConfigProvider returns {} when file does not exist."""
    monkeypatch.chdir(tmp_path)
    provider = ProjectConfigProvider("nonexistent")
    assert provider() == {}

  def test_raises_on_insecure_permissions(self, tmp_path, monkeypatch):
    """ProjectConfigProvider raises SecurityError for world-readable files."""
    config_file = tmp_path / "myapp.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o644)
    monkeypatch.chdir(tmp_path)

    provider = ProjectConfigProvider("myapp")
    with pytest.raises(SecurityError) as exc_info:
      provider()
    assert exc_info.value.check == "file_permissions"

  def test_path_uses_cwd(self, tmp_path, monkeypatch):
    """ProjectConfigProvider resolves path against Path.cwd()."""
    monkeypatch.chdir(tmp_path)
    provider = ProjectConfigProvider("myapp")
    assert provider._path == tmp_path / "myapp.toml"


# ---------------------------------------------------------------------------
# DEFAULT_CASCADE
# ---------------------------------------------------------------------------


class TestDefaultCascade:
  """Tests for DEFAULT_CASCADE."""

  def test_contains_user_then_project(self):
    """DEFAULT_CASCADE contains UserConfigProvider then ProjectConfigProvider."""
    assert DEFAULT_CASCADE == (UserConfigProvider, ProjectConfigProvider)

  def test_entries_are_classes_not_instances(self):
    """DEFAULT_CASCADE entries are classes, not instances."""
    for entry in DEFAULT_CASCADE:
      assert isinstance(entry, type)

  def test_entries_satisfy_protocol_when_instantiated(self):
    """Instantiated DEFAULT_CASCADE entries satisfy ConfigProvider."""
    for cls in DEFAULT_CASCADE:
      instance = cls("test")
      assert isinstance(instance, ConfigProvider)


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


class TestDeepMerge:
  """Tests for the deep_merge function."""

  def test_empty_dicts(self):
    """Merging two empty dicts returns an empty dict."""
    assert deep_merge({}, {}) == {}

  def test_base_only(self):
    """Keys only in base are preserved."""
    assert deep_merge({"a": 1}, {}) == {"a": 1}

  def test_overlay_only(self):
    """Keys only in overlay are added."""
    assert deep_merge({}, {"b": 2}) == {"b": 2}

  def test_scalar_replaced(self):
    """Overlay scalar replaces base scalar."""
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

  def test_nested_dicts_merged(self):
    """Nested dicts are recursively merged."""
    base = {"db": {"host": "localhost", "port": 5432}}
    overlay = {"db": {"host": "prod.db"}}
    assert deep_merge(base, overlay) == {"db": {"host": "prod.db", "port": 5432}}

  def test_lists_replaced_not_appended(self):
    """Lists are replaced, not appended (unlike CLI behavior)."""
    assert deep_merge({"items": [1, 2]}, {"items": [3, 4]}) == {"items": [3, 4]}

  def test_type_mismatch_overlay_wins_dict_to_list(self):
    """Type mismatch: dict → list, overlay wins."""
    assert deep_merge({"a": {"x": 1}}, {"a": [1, 2]}) == {"a": [1, 2]}

  def test_type_mismatch_overlay_wins_list_to_dict(self):
    """Type mismatch: list → dict, overlay wins."""
    assert deep_merge({"a": [1, 2]}, {"a": {"x": 1}}) == {"a": {"x": 1}}

  def test_none_overlay_wins(self):
    """None base is replaced by dict overlay."""
    assert deep_merge({"a": None}, {"a": {"x": 1}}) == {"a": {"x": 1}}

  def test_inputs_not_modified(self):
    """deep_merge must not modify its input dicts."""
    base = {"db": {"host": "localhost"}}
    overlay = {"db": {"port": 5432}}
    deep_merge(base, overlay)
    assert base == {"db": {"host": "localhost"}}
    assert overlay == {"db": {"port": 5432}}

  def test_deeply_nested(self):
    """Three-level nesting merges correctly."""
    base = {"a": {"b": {"c": 1, "d": 2}}}
    overlay = {"a": {"b": {"c": 99}}}
    assert deep_merge(base, overlay) == {"a": {"b": {"c": 99, "d": 2}}}

  def test_multiple_keys_some_dict_some_scalar(self):
    """Mix of dict and scalar keys merges correctly."""
    base = {"a": 1, "b": {"x": 1}, "c": "hello"}
    overlay = {"b": {"y": 2}, "c": "world", "d": "new"}
    assert deep_merge(base, overlay) == {
      "a": 1,
      "b": {"x": 1, "y": 2},
      "c": "world",
      "d": "new",
    }


# ---------------------------------------------------------------------------
# Public TOML API
# ---------------------------------------------------------------------------


class TestPublicTomlApi:
  """Tests for load / loads / load_toml / loads_toml."""

  def test_load_from_binary_file(self):
    """load parses TOML from a binary file object."""
    data = b'name = "test"\nport = 5432\n'
    result = load(io.BytesIO(data))
    assert result == {"name": "test", "port": 5432}

  def test_loads_from_string(self):
    """loads parses TOML from a string."""
    result = loads('name = "test"\nport = 5432\n')
    assert result == {"name": "test", "port": 5432}

  def test_load_toml_is_alias_of_load(self):
    """load_toml is the same function as load."""
    assert load_toml is load

  def test_loads_toml_is_alias_of_loads(self):
    """loads_toml is the same function as loads."""
    assert loads_toml is loads

  def test_load_toml_works(self):
    """load_toml works as an alias."""
    result = load_toml(io.BytesIO(b'name = "x"\n'))
    assert result == {"name": "x"}

  def test_loads_toml_works(self):
    """loads_toml works as an alias."""
    result = loads_toml('name = "x"\n')
    assert result == {"name": "x"}

  def test_load_nested_tables(self):
    """load parses nested tables."""
    data = b'[database]\nhost = "localhost"\nport = 5432\n'
    result = load(io.BytesIO(data))
    assert result == {"database": {"host": "localhost", "port": 5432}}

  def test_loads_empty_string(self):
    """loads of empty string returns empty dict."""
    assert loads("") == {}

  def test_load_no_security_checks(self):
    """load does not perform security checks (raw parser)."""
    # Should parse regardless of file permissions — it's just a parser.
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
      f.write(b'name = "test"\n')
      f.flush()
      path = Path(f.name)
      path.chmod(0o644)  # Insecure permissions
      try:
        with open(path, "rb") as fh:
          result = load(fh)
        assert result == {"name": "test"}
      finally:
        path.unlink(missing_ok=True)

  def test_loads_list_values(self):
    """loads parses list values."""
    result = loads('items = ["a", "b", "c"]\n')
    assert result == {"items": ["a", "b", "c"]}

  def test_loads_invalid_toml_raises(self):
    """loads raises on invalid TOML."""
    # tomllib.TOMLDecodeError is a ValueError subclass.
    with pytest.raises(ValueError):
      loads("name = \n")


# ---------------------------------------------------------------------------
# cascade parameter on get_config
# ---------------------------------------------------------------------------


class TestCascadeParameter:
  """Tests for the cascade parameter on get_config."""

  def test_custom_cascade_replaces_defaults(self):
    """A custom cascade replaces the default user/project providers."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    class StaticProvider:
      def __call__(self) -> dict:
        return {"name": "from-cascade"}

    config = get_config(Config, name="myapp", cascade=[StaticProvider()], args=[])
    assert config.name == "from-cascade"

  def test_plain_function_works_in_cascade(self):
    """A plain function (not a class) works as a ConfigProvider in the cascade."""
    _reset_factories()

    @dataclass
    class Config:
      api_key: str = "default"

    def env_provider() -> dict:
      return {"api_key": "from-function"}

    cascade = build_default_cascade("test") + [env_provider]
    assert isinstance(env_provider, ConfigProvider)
    config = get_config(Config, name="test", cascade=cascade, args=[])
    assert config.api_key == "from-function"

  def test_empty_cascade_uses_defaults_only(self):
    """An empty cascade means no middle providers — only defaults + CLI."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"
      debug: bool = False

    config = get_config(Config, name="myapp", cascade=[], args=["--debug"])
    assert config.name == "default"
    assert config.debug is True

  def test_multiple_providers_deep_merged(self):
    """Multiple providers are deep-merged in cascade order."""
    _reset_factories()

    @dataclass
    class Config:
      a: str = "default"
      b: str = "default"

    class FirstProvider:
      def __call__(self) -> dict:
        return {"a": "first", "b": "first"}

    class SecondProvider:
      def __call__(self) -> dict:
        return {"b": "second"}

    config = get_config(
      Config,
      name="myapp",
      cascade=[FirstProvider(), SecondProvider()],
      args=[],
    )
    # Second provider overrides 'b' but 'a' survives from first.
    assert config.a == "first"
    assert config.b == "second"

  def test_cascade_with_nested_dict_merge(self):
    """Deep merge consolidates nested dicts across providers."""
    _reset_factories()

    @dataclass
    class DbConfig:
      host: str = "localhost"
      port: int = 5432

    @dataclass
    class Config:
      database: DbConfig = field(default_factory=DbConfig)

    class UserLikeProvider:
      def __call__(self) -> dict:
        return {"database": {"host": "localhost", "port": 5432}}

    class ProjectLikeProvider:
      def __call__(self) -> dict:
        return {"database": {"host": "prod.db"}}

    config = get_config(
      Config,
      name="myapp",
      cascade=[UserLikeProvider(), ProjectLikeProvider()],
      args=[],
    )
    assert config.database.host == "prod.db"
    assert config.database.port == 5432

  def test_user_project_flags_ignored_with_cascade(self):
    """user/project flags are ignored when cascade is provided."""
    _reset_factories()

    @dataclass
    class Config:
      name: str = "default"

    class StaticProvider:
      def __call__(self) -> dict:
        return {"name": "cascade-value"}

    # user=False, project=True — but cascade is provided, so flags ignored.
    config = get_config(
      Config,
      name="myapp",
      user=False,
      project=True,
      cascade=[StaticProvider()],
      args=[],
    )
    assert config.name == "cascade-value"


# ---------------------------------------------------------------------------
# user/project flag filtering with default cascade
# ---------------------------------------------------------------------------


class TestUserProjectFlagFiltering:
  """Tests for user/project flag filtering with the default cascade."""

  def test_user_false_excludes_user_provider(self, monkeypatch, tmp_path):
    """user=False removes UserConfigProvider from default cascade."""
    _reset_factories()

    user_file = tmp_path / ".myapp.toml"
    user_file.write_text('name = "from-user"\n')
    user_file.chmod(0o600)

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('name = "from-project"\n')
    project_file.chmod(0o600)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config = get_config(
      Config,
      name="myapp",
      user=False,
      project=True,
      args=[],
    )
    assert config.name == "from-project"

  def test_project_false_excludes_project_provider(self, monkeypatch, tmp_path):
    """project=False removes ProjectConfigProvider from default cascade."""
    _reset_factories()

    user_file = tmp_path / ".myapp.toml"
    user_file.write_text('name = "from-user"\n')
    user_file.chmod(0o600)

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('name = "from-project"\n')
    project_file.chmod(0o600)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config = get_config(
      Config,
      name="myapp",
      user=True,
      project=False,
      args=[],
    )
    assert config.name == "from-user"

  def test_both_false_uses_no_providers(self, monkeypatch, tmp_path):
    """user=False, project=False → no middle providers, defaults only."""
    _reset_factories()

    user_file = tmp_path / ".myapp.toml"
    user_file.write_text('name = "from-user"\n')
    user_file.chmod(0o600)

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('name = "from-project"\n')
    project_file.chmod(0o600)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config = get_config(
      Config,
      name="myapp",
      user=False,
      project=False,
      args=[],
    )
    assert config.name == "default"


# ---------------------------------------------------------------------------
# Breaking change: shallow → deep merge
# ---------------------------------------------------------------------------


class TestDeepMergeBreakingChange:
  """Verify the shallow→deep merge behavioral change."""

  def test_nested_sections_merge_instead_of_replace(self, monkeypatch, tmp_path):
    """Project TOML nested section merges into user TOML (not replaces)."""
    _reset_factories()

    @dataclass
    class DbConfig:
      host: str = "localhost"
      port: int = 5432

    @dataclass
    class Cfg:
      database: DbConfig = field(default_factory=DbConfig)

    user_file = tmp_path / ".myapp.toml"
    user_file.write_text('[database]\nhost = "localhost"\nport = 5432\n')
    user_file.chmod(0o600)

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('[database]\nhost = "prod.db"\n')
    project_file.chmod(0o600)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config = get_config(Cfg, name="myapp", args=[])
    # Deep merge: port survives from user TOML.
    assert config.database.host == "prod.db"
    assert config.database.port == 5432


# ---------------------------------------------------------------------------
# Subcommand extraction with cascade
# ---------------------------------------------------------------------------


class TestSubcommandExtractionWithCascade:
  """Tests for subcommand TOML extraction with custom cascades."""

  def test_multiple_providers_contribute_cmd_section(self):
    """Multiple providers can contribute to a [cmd] section via deep merge."""
    _reset_factories()

    from clevis import configclass

    @configclass(cmd="chat", default_cmd=True)
    class ChatCfg:
      model: str = "gpt-4"
      verbose: bool = False

    class DefaultsProvider:
      def __call__(self) -> dict:
        return {"chat": {"verbose": True}}

    class UserLikeProvider:
      def __call__(self) -> dict:
        return {"chat": {"model": "claude"}}

    config = get_config(
      ChatCfg,
      name="myapp",
      cascade=[DefaultsProvider(), UserLikeProvider()],
      args=[],
    )
    # Both [chat] sections are deep-merged before extraction.
    assert config.model == "claude"
    assert config.verbose is True


# ---------------------------------------------------------------------------
# List field handling: providers replace, CLI appends
# ---------------------------------------------------------------------------


class TestListFieldHandling:
  """List fields: override providers replace; CLI args append."""

  def test_provider_replaces_list(self):
    """A provider's list replaces the base list (deep merge semantics)."""
    _reset_factories()

    @dataclass
    class Cfg:
      items: list[str] = field(default_factory=lambda: ["default"])

    class FirstProvider:
      def __call__(self) -> dict:
        return {"items": ["base", "from-first"]}

    class SecondProvider:
      def __call__(self) -> dict:
        return {"items": ["from-second"]}

    config = get_config(
      Cfg,
      name="myapp",
      cascade=[FirstProvider(), SecondProvider()],
      args=[],
    )
    # Second provider's list replaces first provider's list.
    assert config.items == ["from-second"]

  def test_cli_appends_to_provider_list(self):
    """CLI args append to the list that survived the cascade."""
    _reset_factories()

    @dataclass
    class Cfg:
      items: list[str] = field(default_factory=list)

    class BaseProvider:
      def __call__(self) -> dict:
        return {"items": ["base"]}

    config = get_config(
      Cfg,
      name="myapp",
      cascade=[BaseProvider()],
      args=["--items", "cli1", "--items", "cli2"],
    )
    # CLI appends to the provider's list.
    assert config.items == ["base", "cli1", "cli2"]

  def test_cli_no_field_clears_provider_list(self):
    """--no-field clears the list that came from providers."""
    _reset_factories()

    @dataclass
    class Cfg:
      items: list[str] = field(default_factory=list)

    class BaseProvider:
      def __call__(self) -> dict:
        return {"items": ["base"]}

    config = get_config(
      Cfg,
      name="myapp",
      cascade=[BaseProvider()],
      args=["--no-items"],
    )
    assert config.items == []


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
  """Tests that existing behavior is preserved when cascade is not used."""

  def test_no_cascade_preserves_behavior(self, monkeypatch, tmp_path):
    """Without cascade, get_config behaves as before (minus deep merge)."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('name = "from-project"\n')
    project_file.chmod(0o600)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config = get_config(Cfg, name="myapp", user=False, project=True, args=[])
    assert config.name == "from-project"

  def test_security_param_applies_to_default_providers(self, monkeypatch, tmp_path):
    """security= still applies to default cascade providers."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('name = "from-project"\n')
    project_file.chmod(0o644)  # Insecure

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SecurityError):
      get_config(Cfg, name="myapp", user=False, project=True, args=[])

  def test_security_param_with_dont_check_works(self, monkeypatch, tmp_path):
    """security=DONT_CHECK bypasses permission checks for default providers."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('name = "from-project"\n')
    project_file.chmod(0o644)  # Insecure

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config = get_config(
      Cfg,
      name="myapp",
      user=False,
      project=True,
      args=[],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert config.name == "from-project"

  def test_cli_still_highest_priority(self):
    """CLI args override provider values (fixed last bookend)."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    class StaticProvider:
      def __call__(self) -> dict:
        return {"name": "from-provider"}

    config = get_config(
      Cfg,
      name="myapp",
      cascade=[StaticProvider()],
      args=["--name", "from-cli"],
    )
    assert config.name == "from-cli"

  def test_existing_security_tests_still_pass(self, monkeypatch, tmp_path):
    """Existing security behavior (TOCTOU-safe, reject by default) preserved."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    project_file = tmp_path / "myapp.toml"
    project_file.write_text('name = "test"\n')
    project_file.chmod(0o600)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config = get_config(Cfg, name="myapp", user=False, project=True, args=[])
    assert config.name == "test"


# ---------------------------------------------------------------------------
# Provider exception propagation & security= ignore with cascade=
# ---------------------------------------------------------------------------


class TestProviderExceptionPropagation:
  """Verify provider exceptions propagate to the get_config() caller."""

  def test_provider_runtime_error_propagates(self):
    """An exception raised by a provider surfaces from get_config()."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    class BoomProvider:
      def __call__(self) -> dict:
        raise RuntimeError("provider exploded")

    with pytest.raises(RuntimeError, match="provider exploded"):
      get_config(Cfg, name="myapp", cascade=[BoomProvider()], args=[])

  def test_provider_security_error_propagates(self):
    """A SecurityError raised by a provider surfaces from get_config()."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    class InsecureProvider:
      def __call__(self) -> dict:
        raise SecurityError("insecure", "/some/path", "file_permissions")

    with pytest.raises(SecurityError) as exc_info:
      get_config(Cfg, name="myapp", cascade=[InsecureProvider()], args=[])
    assert exc_info.value.check == "file_permissions"

  def test_exception_from_second_provider_propagates(self):
    """Exception from a later provider still propagates (first ran clean)."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    class GoodProvider:
      def __call__(self) -> dict:
        return {"name": "good"}

    class BadProvider:
      def __call__(self) -> dict:
        raise ValueError("bad provider")

    with pytest.raises(ValueError, match="bad provider"):
      get_config(
        Cfg,
        name="myapp",
        cascade=[GoodProvider(), BadProvider()],
        args=[],
      )


class TestSecurityIgnoredWithCascade:
  """Verify security= is ignored when cascade= is provided."""

  def test_security_reject_ignored_with_cascade(self, monkeypatch, tmp_path):
    """security=REJECT is ignored when cascade= is given; insecure config loads."""
    _reset_factories()

    @dataclass
    class Cfg:
      name: str = "default"

    # A provider that returns an "insecure" config without any security checks.
    class InsecureFileProvider:
      def __call__(self) -> dict:
        return {"name": "from-insecure-provider"}

    config = get_config(
      Cfg,
      name="myapp",
      cascade=[InsecureFileProvider()],
      args=[],
      security={
        "file_permissions": SecurityAction.REJECT,
        "directory_permissions": SecurityAction.REJECT,
      },
    )
    # security=REJECT would normally reject insecure files, but with cascade=
    # the parameter is ignored and the provider's value is loaded.
    assert config.name == "from-insecure-provider"

  def test_security_ignored_warning_logged(self, caplog):
    """security= ignored with cascade= logs a warning (not just info)."""
    _reset_factories()
    import logging

    @dataclass
    class Cfg:
      name: str = "default"

    class StaticProvider:
      def __call__(self) -> dict:
        return {"name": "x"}

    with caplog.at_level(logging.WARNING, logger="clevis"):
      get_config(
        Cfg,
        name="myapp",
        cascade=[StaticProvider()],
        args=[],
        security={
          "file_permissions": SecurityAction.REJECT,
          "directory_permissions": SecurityAction.REJECT,
        },
      )
    assert any(
      "security= parameter is ignored" in record.message
      and record.levelno == logging.WARNING
      for record in caplog.records
    )


# ---------------------------------------------------------------------------
# deep_merge deep-copy of untouched nested base dicts
# ---------------------------------------------------------------------------


class TestDeepMergeDeepCopy:
  """Verify deep_merge recursively copies nested base dicts (not shallow)."""

  def test_untouched_nested_base_dict_is_copied(self):
    """Mutating result's nested dict must not affect the base input."""
    base = {"db": {"host": "localhost", "port": 5432}}
    overlay = {"other": 1}
    result = deep_merge(base, overlay)
    result["db"]["host"] = "mutated"
    # base must be unchanged — the nested dict was deep-copied.
    assert base["db"]["host"] == "localhost"

  def test_deeply_nested_untouched_dict_is_copied(self):
    """Three-level nested base dict that overlay doesn't touch is copied."""
    base = {"a": {"b": {"c": 1, "d": 2}}}
    overlay = {"x": 99}
    result = deep_merge(base, overlay)
    result["a"]["b"]["c"] = 999
    assert base["a"]["b"]["c"] == 1


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------


class TestExports:
  """Verify all new public names are exported."""

  def test_all_new_names_in_all(self):
    """__all__ should contain all new public names."""
    import clevis

    expected = [
      "ConfigProvider",
      "FileConfigProvider",
      "UserConfigProvider",
      "ProjectConfigProvider",
      "DEFAULT_CASCADE",
      "build_default_cascade",
      "deep_merge",
      "load",
      "loads",
      "load_toml",
      "loads_toml",
      "check_file_permissions",
      "check_directory_permissions",
      "load_toml_from_fd",
      "load_toml_file",
    ]
    for name in expected:
      assert name in clevis.__all__, f"{name} missing from __all__"
      assert hasattr(clevis, name), f"{name} not importable from clevis"

  def test_security_helpers_callable(self):
    """check_file_permissions, check_directory_permissions, load_toml_from_fd are callable."""
    import clevis

    assert callable(clevis.check_file_permissions)
    assert callable(clevis.check_directory_permissions)
    assert callable(clevis.load_toml_from_fd)
    assert callable(clevis.load_toml_file)
    assert callable(clevis.build_default_cascade)


# ---------------------------------------------------------------------------
# build_default_cascade()
# ---------------------------------------------------------------------------


class TestBuildDefaultCascade:
  """Tests for the build_default_cascade() helper."""

  def test_returns_user_then_project(self, monkeypatch, tmp_path):
    """build_default_cascade returns User then Project provider instances."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    cascade = build_default_cascade("myapp")
    assert len(cascade) == 2
    assert isinstance(cascade[0], UserConfigProvider)
    assert isinstance(cascade[1], ProjectConfigProvider)

  def test_user_false_excludes_user_provider(self, monkeypatch, tmp_path):
    """user=False excludes UserConfigProvider from the built cascade."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    cascade = build_default_cascade("myapp", user=False)
    assert len(cascade) == 1
    assert isinstance(cascade[0], ProjectConfigProvider)

  def test_project_false_excludes_project_provider(self, monkeypatch, tmp_path):
    """project=False excludes ProjectConfigProvider from the built cascade."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    cascade = build_default_cascade("myapp", project=False)
    assert len(cascade) == 1
    assert isinstance(cascade[0], UserConfigProvider)

  def test_both_false_returns_empty(self, monkeypatch, tmp_path):
    """user=False, project=False returns an empty cascade."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    cascade = build_default_cascade("myapp", user=False, project=False)
    assert cascade == []

  def test_append_custom_provider_to_defaults(self, monkeypatch, tmp_path):
    """Appending a custom provider to build_default_cascade works with get_config."""
    _reset_factories()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    @dataclass
    class Cfg:
      name: str = "default"
      extra: str = "none"

    class ExtraProvider:
      def __call__(self) -> dict:
        return {"extra": "from-custom"}

    cascade = build_default_cascade(
      "myapp",
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    ) + [ExtraProvider()]
    config = get_config(Cfg, name="myapp", cascade=cascade, args=[])
    assert config.extra == "from-custom"

  def test_security_applied_to_built_providers(self, monkeypatch, tmp_path):
    """security= passed to build_default_cascade applies to the providers."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".myapp.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o644)  # Insecure

    cascade = build_default_cascade("myapp")  # Default: REJECT
    with pytest.raises(SecurityError):
      cascade[0]()

  def test_instances_satisfy_protocol(self, monkeypatch, tmp_path):
    """Built provider instances satisfy the ConfigProvider protocol."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    cascade = build_default_cascade("myapp")
    for provider in cascade:
      assert isinstance(provider, ConfigProvider)


# ---------------------------------------------------------------------------
# load_toml_file()
# ---------------------------------------------------------------------------


class TestLoadTomlFile:
  """Tests for the load_toml_file() convenience function."""

  def test_loads_existing_file(self, tmp_path):
    """load_toml_file loads an existing TOML file securely."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('name = "test"\nport = 5432\n')
    config_file.chmod(0o600)

    result = load_toml_file(
      config_file,
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert result == {"name": "test", "port": 5432}

  def test_returns_empty_dict_for_missing_file(self, tmp_path):
    """load_toml_file returns {} when the file does not exist."""
    result = load_toml_file(tmp_path / "nonexistent.toml")
    assert result == {}

  def test_applies_security_checks_by_default(self, tmp_path):
    """load_toml_file applies default REJECT security for insecure files."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o644)  # Insecure

    with pytest.raises(SecurityError):
      load_toml_file(config_file)

  def test_dont_check_bypasses_security(self, tmp_path):
    """load_toml_file with DONT_CHECK loads insecure files."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('name = "test"\n')
    config_file.chmod(0o644)

    result = load_toml_file(
      config_file,
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert result == {"name": "test"}

  def test_loads_nested_tables(self, tmp_path):
    """load_toml_file parses nested TOML tables."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[database]\nhost = "localhost"\nport = 5432\n')
    config_file.chmod(0o600)

    result = load_toml_file(
      config_file,
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    assert result == {"database": {"host": "localhost", "port": 5432}}


# ---------------------------------------------------------------------------
# FileConfigProvider subclassing
# ---------------------------------------------------------------------------


class TestFileConfigProviderSubclass:
  """Tests for subclassing FileConfigProvider."""

  def test_subclass_loads_from_custom_path(self, tmp_path, monkeypatch):
    """A FileConfigProvider subclass loads TOML from a custom root dir."""
    config_file = tmp_path / "custom.toml"
    config_file.write_text('name = "custom"\n')
    config_file.chmod(0o600)

    class CustomProvider(FileConfigProvider):
      _path_template = "{name}.toml"

      def _root_dir(self) -> Path:
        return tmp_path

    provider = CustomProvider(
      "custom",
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )
    result = provider()
    assert result == {"name": "custom"}

  def test_subclass_security_checks_work(self, tmp_path):
    """A FileConfigProvider subclass applies security checks by default."""
    config_file = tmp_path / "custom.toml"
    config_file.write_text('name = "custom"\n')
    config_file.chmod(0o644)  # Insecure

    class CustomProvider(FileConfigProvider):
      _path_template = "{name}.toml"

      def _root_dir(self) -> Path:
        return tmp_path

    provider = CustomProvider("custom")
    with pytest.raises(SecurityError):
      provider()

  def test_subclass_returns_empty_for_missing_file(self, tmp_path):
    """A FileConfigProvider subclass returns {} for missing files."""

    class CustomProvider(FileConfigProvider):
      _path_template = "{name}.toml"

      def _root_dir(self) -> Path:
        return tmp_path

    provider = CustomProvider("nonexistent")
    assert provider() == {}

  def test_subclass_satisfies_protocol(self, tmp_path):
    """A FileConfigProvider subclass satisfies ConfigProvider protocol."""

    class CustomProvider(FileConfigProvider):
      _path_template = "{name}.toml"

      def _root_dir(self) -> Path:
        return tmp_path

    provider = CustomProvider("x")
    assert isinstance(provider, ConfigProvider)
