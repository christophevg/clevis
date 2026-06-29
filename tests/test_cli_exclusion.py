"""Tests for CLI field exclusion via metadata["cli"] = False.

This module tests the CLI exclusion feature (P1-004, issue #30) which allows
dataclass fields to be excluded from CLI argument generation by setting
``metadata["cli"] = False`` on the field. Excluded fields remain loadable
via TOML, env interpolation, and dataclass defaults — they are simply not
exposed as CLI arguments.

Acceptance criteria covered:
  1. Single exclusion point: one centralized walker used by
     _configure_fields, list_fields, list_fields_with_owners, and
     ConfigError (suggest_cli=False).
  2. Trigger only on metadata["cli"] is False (explicit False, not falsy:
     None/0/"" all include). Absence of the key = include.
  3. Any level: leaf cli=False -> CLI arg skipped; nested-dataclass cli=False
     -> entire subtree skipped (no recursion; descendants with cli=True still
     excluded).
  4. cli=False suppresses cli_aliases — no --<alias> arguments generated.
  5. register_field() accepts optional keyword-only metadata; plugin can
     register a cli=False field.
  6. Regression safety: fields without metadata["cli"] (or non-False) behave
     unchanged.
  7. Tests cover: leaf exclusion, nested-subtree exclusion (no recursion),
     alias suppression, dynamic registration via register_field(), and a
     secret-field scenario (absent from sys.argv-derived parsing while still
     loadable via config/TOML/env/defaults).

These are passing tests covering the implemented CLI field exclusion feature.
The golden test is the exception — it captures current behavior to protect the
_configure_fields refactor and should PASS both before and after the refactor.
"""

from dataclasses import dataclass, field

import pytest

from clevis import (
  ConfigError,
  Factory,
  SecurityAction,
  _reset_factories,
  get_config,
  get_factory,
  register_field,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECURITY_DONT_CHECK = {
  "file_permissions": SecurityAction.DONT_CHECK,
  "directory_permissions": SecurityAction.DONT_CHECK,
}


def _get_config(clz, args=None):
  """Convenience wrapper around get_config with no TOML files and dont-check security."""
  return get_config(
    clz,
    name="test",
    user=False,
    project=False,
    cli=True,
    args=args if args is not None else [],
    security=SECURITY_DONT_CHECK,
  )


# ---------------------------------------------------------------------------
# Criterion 3: Leaf field exclusion
# ---------------------------------------------------------------------------


class TestLeafExclusion:
  """Tests for leaf fields with metadata["cli"] = False."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_leaf_field_with_cli_false_excluded_from_parser_dests(self):
    """
    Given: A configclass with a leaf field marked metadata={"cli": False}
    When: The parser is configured
    Then: No CLI argument dest is registered for that field
    """

    @dataclass
    class Config:
      visible: str = field(default="seen")
      secret: str = field(default="hidden", metadata={"cli": False})

    factory = get_factory(Config)
    cli_args = factory.get_args([])

    # The excluded field's dest must not appear in parsed args
    assert "secret" not in cli_args, (
      f"Excluded field 'secret' should not have a CLI dest, got: {cli_args}"
    )
    # The visible field's dest should still be present (None since no arg passed)
    assert "visible" in cli_args

  def test_leaf_field_with_cli_false_rejects_cli_value(self):
    """
    Given: A configclass with a leaf field marked metadata={"cli": False}
    When: A user passes --secret <value> on the command line
    Then: argparse rejects it as an unrecognized argument (SystemExit)
    """

    @dataclass
    class Config:
      visible: str = field(default="seen")
      secret: str = field(default="hidden", metadata={"cli": False})

    with pytest.raises(SystemExit):
      _get_config(Config, args=["--secret", "leaked"])

  def test_leaf_field_with_cli_false_still_loadable_from_default(self):
    """
    Given: A configclass with a leaf field marked metadata={"cli": False}
    When: Configuration is loaded with no CLI args
    Then: The excluded field still receives its dataclass default value
    """

    @dataclass
    class Config:
      visible: str = field(default="seen")
      secret: str = field(default="hidden", metadata={"cli": False})

    config = _get_config(Config, args=[])
    assert config.secret == "hidden"
    assert config.visible == "seen"

  def test_leaf_field_with_cli_false_excluded_from_list_fields(self):
    """
    Given: A configclass with a leaf field marked metadata={"cli": False}
    When: list_fields and list_fields_with_owners are called
    Then: The excluded field is NOT listed (single exclusion point consistency)
    """

    @dataclass
    class Config:
      visible: str = field(default="seen")
      secret: str = field(default="hidden", metadata={"cli": False})

    factory = get_factory(Config)
    listed = factory.list_fields()
    listed_names = {f.name for (f, _path) in listed}
    assert "visible" in listed_names
    assert "secret" not in listed_names, (
      f"Excluded field 'secret' should not appear in list_fields(), got: {listed_names}"
    )

    listed_owners = factory.list_fields_with_owners()
    listed_owner_names = {f.name for (f, _path, _owner) in listed_owners}
    assert "visible" in listed_owner_names
    assert "secret" not in listed_owner_names


# ---------------------------------------------------------------------------
# Criterion 3: Nested subtree exclusion (no recursion)
# ---------------------------------------------------------------------------


class TestNestedSubtreeExclusion:
  """Tests for nested-dataclass fields with metadata["cli"] = False."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_nested_subtree_with_cli_false_pruned_entirely(self):
    """
    Given: A nested-dataclass field marked metadata={"cli": False}
    When: The parser is configured
    Then: No CLI arguments are generated for any descendant leaf field
    """

    @dataclass
    class CredentialsConfig:
      api_key: str = field(default="from-default")
      timeout: int = field(default=30)

    @dataclass
    class Config:
      name: str = field(default="app")
      credentials: CredentialsConfig = field(
        default_factory=CredentialsConfig, metadata={"cli": False}
      )

    factory = get_factory(Config)
    cli_args = factory.get_args([])

    # No dest for any descendant of the excluded subtree
    assert "credentials.api_key" not in cli_args, (
      f"Excluded subtree leaf 'credentials.api_key' should not have a dest, got: {cli_args}"
    )
    assert "credentials.timeout" not in cli_args
    # The non-excluded field is still present
    assert "name" in cli_args

  def test_nested_subtree_cli_false_rejects_descendant_cli_arg(self):
    """
    Given: A nested-dataclass field marked metadata={"cli": False}
    When: A user passes --credentials-api-key <value>
    Then: argparse rejects it as an unrecognized argument (SystemExit)
    """

    @dataclass
    class CredentialsConfig:
      api_key: str = field(default="from-default")

    @dataclass
    class Config:
      name: str = field(default="app")
      credentials: CredentialsConfig = field(
        default_factory=CredentialsConfig, metadata={"cli": False}
      )

    with pytest.raises(SystemExit):
      _get_config(Config, args=["--credentials-api-key", "leaked"])

  def test_nested_subtree_cli_false_descendant_cli_true_still_excluded(self):
    """
    Given: A nested-dataclass field marked metadata={"cli": False}, with a
           descendant leaf that itself sets metadata={"cli": True}
    When: The parser is configured
    Then: The descendant is STILL excluded — subtree pruning does not recurse,
          so a descendant's cli=True cannot un-exclude itself.
    """

    @dataclass
    class CredentialsConfig:
      api_key: str = field(default="from-default", metadata={"cli": True})
      timeout: int = field(default=30)

    @dataclass
    class Config:
      name: str = field(default="app")
      credentials: CredentialsConfig = field(
        default_factory=CredentialsConfig, metadata={"cli": False}
      )

    factory = get_factory(Config)
    cli_args = factory.get_args([])

    assert "credentials.api_key" not in cli_args, (
      f"Descendant with cli=True under an excluded subtree must still be excluded; got: {cli_args}"
    )
    assert "credentials.timeout" not in cli_args

  def test_nested_subtree_cli_false_still_loadable_from_defaults(self):
    """
    Given: A nested-dataclass field marked metadata={"cli": False}
    When: Configuration is loaded with no CLI args
    Then: The excluded subtree still receives its dataclass default values
    """

    @dataclass
    class CredentialsConfig:
      api_key: str = field(default="from-default")
      timeout: int = field(default=30)

    @dataclass
    class Config:
      name: str = field(default="app")
      credentials: CredentialsConfig = field(
        default_factory=CredentialsConfig, metadata={"cli": False}
      )

    config = _get_config(Config, args=[])
    assert config.credentials.api_key == "from-default"
    assert config.credentials.timeout == 30

  def test_nested_subtree_cli_false_excluded_from_list_fields(self):
    """
    Given: A nested-dataclass field marked metadata={"cli": False}
    When: list_fields and list_fields_with_owners are called
    Then: No descendant leaf of the excluded subtree is listed
    """

    @dataclass
    class CredentialsConfig:
      api_key: str = field(default="from-default")
      timeout: int = field(default=30)

    @dataclass
    class Config:
      name: str = field(default="app")
      credentials: CredentialsConfig = field(
        default_factory=CredentialsConfig, metadata={"cli": False}
      )

    factory = get_factory(Config)
    listed = factory.list_fields()
    listed_names = {f.name for (f, _path) in listed}
    assert "name" in listed_names
    assert "api_key" not in listed_names, (
      f"Excluded subtree leaf should not appear in list_fields(), got: {listed_names}"
    )
    assert "timeout" not in listed_names

    listed_owners = factory.list_fields_with_owners()
    listed_owner_names = {f.name for (f, _path, _owner) in listed_owners}
    assert "name" in listed_owner_names
    assert "api_key" not in listed_owner_names
    assert "timeout" not in listed_owner_names


# ---------------------------------------------------------------------------
# Criterion 4: Alias suppression
# ---------------------------------------------------------------------------


class TestAliasSuppression:
  """Tests that cli=False suppresses cli_aliases registration."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_cli_false_suppresses_alias_arguments(self):
    """
    Given: A field with both metadata={"cli": False} and cli_aliases=["with"]
    When: The parser is configured
    Then: No --with alias argument is registered (passing --with is rejected)
    """

    @dataclass
    class Config:
      visible: str = field(default="seen")
      secret: str = field(
        default="hidden",
        metadata={"cli": False, "cli_aliases": ["with"]},
      )

    # Passing the alias must be rejected — the alias is not registered
    with pytest.raises(SystemExit):
      _get_config(Config, args=["--with", "leaked"])

  def test_cli_false_suppresses_alias_no_dest_registered(self):
    """
    Given: A field with both metadata={"cli": False} and cli_aliases=["with"]
    When: The parser is configured
    Then: The field's dest is not registered (neither canonical nor alias)
    """

    @dataclass
    class Config:
      visible: str = field(default="seen")
      secret: str = field(
        default="hidden",
        metadata={"cli": False, "cli_aliases": ["with"]},
      )

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "secret" not in cli_args
    assert "visible" in cli_args

  def test_cli_false_suppresses_alias_still_loadable_from_default(self):
    """
    Given: A field with both metadata={"cli": False} and cli_aliases=["with"]
    When: Configuration is loaded with no CLI args
    Then: The excluded field still receives its default value
    """

    @dataclass
    class Config:
      visible: str = field(default="seen")
      secret: str = field(
        default="hidden",
        metadata={"cli": False, "cli_aliases": ["with"]},
      )

    config = _get_config(Config, args=[])
    assert config.secret == "hidden"
    assert config.visible == "seen"


# ---------------------------------------------------------------------------
# Criterion 5: Dynamic registration via register_field()
# ---------------------------------------------------------------------------


class TestDynamicRegistration:
  """Tests that register_field() accepts optional metadata for cli=False."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_register_field_accepts_metadata_keyword(self):
    """
    Given: A plugin registers a field with metadata={"cli": False}
    When: register_field is called with the metadata keyword argument
    Then: The dynamically registered field is excluded from CLI generation
    """

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True
      api_key: str = field(default="from-default")

    @dataclass
    class ToolsConfig:
      list_enabled: bool = True

    # Plugin registers a secret nested field with cli=False
    register_field(ToolsConfig, "pkgq", PkgqToolConfig, metadata={"cli": False})

    factory = get_factory(ToolsConfig)
    cli_args = factory.get_args([])

    # The dynamically registered excluded subtree produces no CLI dests
    assert "pkgq.enabled" not in cli_args, (
      f"Dynamically registered excluded field should not have a dest, got: {cli_args}"
    )
    assert "pkgq.api_key" not in cli_args
    # The pre-existing field is still present
    assert "list_enabled" in cli_args

  def test_register_field_metadata_cli_false_rejects_cli_value(self):
    """
    Given: A plugin registers a field with metadata={"cli": False}
    When: A user passes --pkgq-api-key <value>
    Then: argparse rejects it as an unrecognized argument (SystemExit)
    """

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True
      api_key: str = field(default="from-default")

    @dataclass
    class ToolsConfig:
      list_enabled: bool = True

    register_field(ToolsConfig, "pkgq", PkgqToolConfig, metadata={"cli": False})

    with pytest.raises(SystemExit):
      _get_config(ToolsConfig, args=["--pkgq-api-key", "leaked"])

  def test_register_field_metadata_cli_false_still_loadable_from_default(self):
    """
    Given: A plugin registers a field with metadata={"cli": False}
    When: Configuration is loaded with no CLI args
    Then: The excluded dynamically-registered field still receives defaults
    """

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True
      api_key: str = field(default="from-default")

    @dataclass
    class ToolsConfig:
      list_enabled: bool = True

    register_field(ToolsConfig, "pkgq", PkgqToolConfig, metadata={"cli": False})

    config = _get_config(ToolsConfig, args=[])
    assert config.pkgq.enabled is True
    assert config.pkgq.api_key == "from-default"

  def test_register_field_without_metadata_remains_unchanged(self):
    """
    Given: A plugin registers a field WITHOUT metadata (regression safety)
    When: register_field is called without the metadata keyword
    Then: The field is exposed as a CLI argument exactly as before (included)
    """

    @dataclass
    class PkgqToolConfig:
      enabled: bool = True

    @dataclass
    class ToolsConfig:
      list_enabled: bool = True

    register_field(ToolsConfig, "pkgq", PkgqToolConfig)

    factory = get_factory(ToolsConfig)
    cli_args = factory.get_args([])
    # Without metadata, the field is included as a CLI argument
    assert "pkgq.enabled" in cli_args, (
      f"Registered field without cli metadata should be included, got: {cli_args}"
    )


# ---------------------------------------------------------------------------
# Criterion 2: Strict trigger — only explicit False excludes
# ---------------------------------------------------------------------------


class TestStrictTrigger:
  """Tests that exclusion triggers ONLY on explicit False, not falsy values."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_cli_none_value_is_included(self):
    """
    Given: A field with metadata={"cli": None}
    When: The parser is configured
    Then: The field IS included as a CLI argument (None is not False)
    """

    @dataclass
    class Config:
      field_none: str = field(default="default", metadata={"cli": None})

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "field_none" in cli_args, (
      f"Field with cli=None should be included (None is not False), got: {cli_args}"
    )

    # And the CLI value can be set
    config = _get_config(Config, args=["--field-none", "from-cli"])
    assert config.field_none == "from-cli"

  def test_cli_zero_value_is_included(self):
    """
    Given: A field with metadata={"cli": 0}
    When: The parser is configured
    Then: The field IS included as a CLI argument (0 is not False)
    """

    @dataclass
    class Config:
      field_zero: str = field(default="default", metadata={"cli": 0})

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "field_zero" in cli_args, (
      f"Field with cli=0 should be included (0 is not False), got: {cli_args}"
    )

    config = _get_config(Config, args=["--field-zero", "from-cli"])
    assert config.field_zero == "from-cli"

  def test_cli_empty_string_value_is_included(self):
    """
    Given: A field with metadata={"cli": ""}
    When: The parser is configured
    Then: The field IS included as a CLI argument ("" is not False)
    """

    @dataclass
    class Config:
      field_empty: str = field(default="default", metadata={"cli": ""})

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "field_empty" in cli_args, (
      f"Field with cli='' should be included ('' is not False), got: {cli_args}"
    )

    config = _get_config(Config, args=["--field-empty", "from-cli"])
    assert config.field_empty == "from-cli"

  def test_cli_true_value_is_included(self):
    """
    Given: A field with metadata={"cli": True}
    When: The parser is configured
    Then: The field IS included as a CLI argument
    """

    @dataclass
    class Config:
      field_true: str = field(default="default", metadata={"cli": True})

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "field_true" in cli_args

    config = _get_config(Config, args=["--field-true", "from-cli"])
    assert config.field_true == "from-cli"


# ---------------------------------------------------------------------------
# Criterion 6: Regression safety — absence / non-False values unchanged
# ---------------------------------------------------------------------------


class TestRegressionSafety:
  """Tests that fields without cli=False metadata behave unchanged."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_absent_cli_key_is_included(self):
    """
    Given: A field with no "cli" key in its metadata
    When: The parser is configured
    Then: The field IS included as a CLI argument (regression safe)
    """

    @dataclass
    class Config:
      visible: str = field(default="default", metadata={"other": "value"})

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "visible" in cli_args

    config = _get_config(Config, args=["--visible", "from-cli"])
    assert config.visible == "from-cli"

  def test_empty_metadata_is_included(self):
    """
    Given: A field with empty metadata
    When: The parser is configured
    Then: The field IS included as a CLI argument (regression safe)
    """

    @dataclass
    class Config:
      visible: str = field(default="default", metadata={})

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "visible" in cli_args

  def test_existing_aliases_still_work(self):
    """
    Given: A field with cli_aliases but NO cli=False metadata
    When: The parser is configured
    Then: Both canonical and alias arguments work as before (regression safe)
    """

    @dataclass
    class Config:
      packages: list[str] = field(default_factory=list, metadata={"cli_aliases": ["with"]})

    config = _get_config(Config, args=["--with", "pkgq", "--packages", "c3"])
    assert config.packages == ["pkgq", "c3"]


# ---------------------------------------------------------------------------
# Criterion 7: Secret-field scenario
# ---------------------------------------------------------------------------


class TestSecretFieldScenario:
  """End-to-end scenario: a secret field excluded from CLI but loadable otherwise."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_secret_field_absent_from_cli_parsing_but_loadable_from_default(self):
    """
    Given: A config with a secret field marked cli=False with a default
    When: Configuration is loaded (no TOML files, no CLI args)
    Then: The secret is NOT reachable via sys.argv-derived parsing, but IS
          loaded from the dataclass default.
    """

    @dataclass
    class Config:
      app_name: str = field(default="myapp")
      secret_api_key: str = field(
        default="loaded-from-default",
        metadata={"cli": False},
      )

    # 1. The secret is not registered as a CLI argument
    factory = get_factory(Config)
    cli_args = factory.get_args([])
    assert "secret_api_key" not in cli_args, (
      "Secret field must not be exposed as a CLI argument dest"
    )
    # The non-secret field is still present
    assert "app_name" in cli_args

    # 2. The secret cannot be supplied via the command line
    with pytest.raises(SystemExit):
      _get_config(Config, args=["--secret-api-key", "attempted-leak"])

    # 3. The secret IS loadable from the dataclass default
    config = _get_config(Config, args=[])
    assert config.secret_api_key == "loaded-from-default"
    assert config.app_name == "myapp"

  def test_secret_field_does_not_appear_in_parser_dests(self):
    """
    Given: A config with a secret field marked cli=False
    When: The parser is configured
    Then: The parser has no dest for the secret field (defensive regression guard)
    """

    @dataclass
    class Config:
      app_name: str = field(default="myapp")
      secret_api_key: str = field(
        default="loaded-from-default",
        metadata={"cli": False},
      )

    factory = get_factory(Config)
    cli_args = factory.get_args([])
    # Defensive: no dest exists for the secret field
    assert not any("secret" in key for key in cli_args), (
      f"Secret field leaked into parser dests: {cli_args}"
    )


# ---------------------------------------------------------------------------
# Criterion 1 sub-criterion: ConfigError suggest_cli=False for excluded fields
# ---------------------------------------------------------------------------


class TestConfigErrorSuggestCli:
  """Tests that ConfigError does not advertise CLI args for excluded fields."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_config_error_for_excluded_field_omits_cli_suggestion(self):
    """
    Given: A required field (no default) marked metadata={"cli": False}
    When: get_config is called with no value supplied (no TOML, no CLI)
    Then: A ConfigError is raised with suggest_cli=False, and the error
          message does NOT advertise the (hidden) CLI argument name.
    """

    @dataclass
    class Config:
      secret: str = field(metadata={"cli": False})  # required, excluded from CLI
      visible: str = field(default="ok")

    with pytest.raises(ConfigError) as exc_info:
      _get_config(Config, args=[])

    err = exc_info.value
    # The error must not suggest using a CLI argument for the excluded field
    assert err.suggest_cli is False, (
      f"ConfigError for excluded field should have suggest_cli=False, got: {err.suggest_cli}"
    )
    # The formatted message must not contain a CLI argument suggestion
    message = str(exc_info.value)
    assert "CLI argument" not in message, (
      f"ConfigError message should not advertise CLI arg for excluded field: {message}"
    )
    assert "--secret" not in message, (
      f"ConfigError message should not name the hidden CLI arg: {message}"
    )

  def test_config_error_for_included_field_still_suggests_cli(self):
    """
    Given: A required field (no default) WITHOUT cli=False metadata
    When: get_config is called with no value supplied
    Then: A ConfigError is raised with suggest_cli=True (regression safe)
    """

    @dataclass
    class Config:
      visible: str = field()  # required, included in CLI
      other: str = field(default="ok")

    with pytest.raises(ConfigError) as exc_info:
      _get_config(Config, args=[])

    err = exc_info.value
    assert err.suggest_cli is True
    message = str(exc_info.value)
    assert "CLI argument" in message

  def test_config_error_for_required_field_inside_excluded_subtree(self):
    """
    Given: A nested-dataclass field marked metadata={"cli": False} containing
           a required leaf field (no default)
    When: get_config is called with no value supplied (no TOML, no CLI, no default)
    Then: A ConfigError is raised with suggest_cli=False, and the error message
          does NOT advertise the (hidden) CLI argument name for the descendant.
          This exercises the traversal branch of _is_field_path_excluded that
          walks into a nested dataclass to find an excluded ancestor.
    """

    @dataclass
    class CredentialsConfig:
      api_key: str = field()  # required, no default

    @dataclass
    class Config:
      name: str = field(default="app")
      credentials: CredentialsConfig = field(
        default_factory=CredentialsConfig, metadata={"cli": False}
      )

    with pytest.raises(ConfigError) as exc_info:
      _get_config(Config, args=[])

    err = exc_info.value
    assert err.suggest_cli is False, (
      f"ConfigError for field inside excluded subtree should have "
      f"suggest_cli=False, got: {err.suggest_cli}"
    )
    message = str(exc_info.value)
    assert "CLI argument" not in message, (
      f"ConfigError message should not advertise CLI arg for descendant of "
      f"excluded subtree: {message}"
    )
    assert "--credentials-api-key" not in message, (
      f"ConfigError message should not name the hidden CLI arg: {message}"
    )


# ---------------------------------------------------------------------------
# Implementation risk mitigation: Golden test for _configure_fields refactor
# ---------------------------------------------------------------------------


class TestGoldenNestedPrefixSequence:
  """
  Golden test protecting the _configure_fields refactor.

  Records the exact sequence of (config_class, value) assignments to
  ``factory._nested_prefix`` for a 3-level nested config. The refactor that
  moves recursion into the _iter_cli_fields walker MUST preserve this
  ordering invariant.

  This test is expected to PASS against the current (pre-refactor) code and
  to keep passing after the refactor. It is the regression guard called for in
  the consensus document (section 9, primary risk mitigation).
  """

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_nested_prefix_assignment_sequence_preserved(self):
    """
    Given: A 3-level nested config (Config -> Level1 -> Level2 -> Level3)
    When: configure_parser runs (via get_config with empty args)
    Then: The _nested_prefix assignment sequence is exactly:
          Level1Config <- "level1"
          Level2Config <- "level1.level2"
          Level3Config <- "level1.level2.level3"
    """

    @dataclass
    class Level3Config:
      value: str = field(default="default")

    @dataclass
    class Level2Config:
      level3: Level3Config = field(default_factory=Level3Config)

    @dataclass
    class Level1Config:
      level2: Level2Config = field(default_factory=Level2Config)

    @dataclass
    class Config:
      level1: Level1Config = field(default_factory=Level1Config)

    recorded: list[tuple[str, str]] = []
    original_setattr = Factory.__setattr__

    def recording_setattr(self, name, value):
      if name == "_nested_prefix" and value is not None:
        recorded.append((self.config_class.__name__, value))
      original_setattr(self, name, value)

    Factory.__setattr__ = recording_setattr  # type: ignore[method-assign]
    try:
      _get_config(Config, args=[])
    finally:
      Factory.__setattr__ = original_setattr  # type: ignore[method-assign]

    expected = [
      ("Level1Config", "level1"),
      ("Level2Config", "level1.level2"),
      ("Level3Config", "level1.level2.level3"),
    ]
    assert recorded == expected, (
      f"_nested_prefix assignment sequence changed — refactor must preserve ordering.\n"
      f"Expected: {expected}\n"
      f"Recorded: {recorded}"
    )

  def test_nested_prefix_final_values_after_configure(self):
    """
    Given: A 3-level nested config
    When: configure_parser runs
    Then: Each nested factory's _nested_prefix has the expected final value
          (post-refactor this must still hold).
    """

    @dataclass
    class Level3Config:
      value: str = field(default="default")

    @dataclass
    class Level2Config:
      level3: Level3Config = field(default_factory=Level3Config)

    @dataclass
    class Level1Config:
      level2: Level2Config = field(default_factory=Level2Config)

    @dataclass
    class Config:
      level1: Level1Config = field(default_factory=Level1Config)

    _get_config(Config, args=[])

    assert get_factory(Level1Config)._nested_prefix == "level1"
    assert get_factory(Level2Config)._nested_prefix == "level1.level2"
    assert get_factory(Level3Config)._nested_prefix == "level1.level2.level3"

  def test_nested_prefix_sequence_unaffected_by_excluded_sibling(self):
    """
    Given: A 3-level nested config with an additional excluded subtree sibling
    When: configure_parser runs
    Then: The _nested_prefix assignment sequence for the INCLUDED subtree is
          unchanged — the excluded sibling is pruned and never assigned a prefix.
    """

    @dataclass
    class Level3Config:
      value: str = field(default="default")

    @dataclass
    class Level2Config:
      level3: Level3Config = field(default_factory=Level3Config)

    @dataclass
    class Level1Config:
      level2: Level2Config = field(default_factory=Level2Config)

    @dataclass
    class ExcludedConfig:
      inner: str = field(default="x")

    @dataclass
    class Config:
      level1: Level1Config = field(default_factory=Level1Config)
      excluded: ExcludedConfig = field(default_factory=ExcludedConfig, metadata={"cli": False})

    recorded: list[tuple[str, str]] = []
    original_setattr = Factory.__setattr__

    def recording_setattr(self, name, value):
      if name == "_nested_prefix" and value is not None:
        recorded.append((self.config_class.__name__, value))
      original_setattr(self, name, value)

    Factory.__setattr__ = recording_setattr  # type: ignore[method-assign]
    try:
      _get_config(Config, args=[])
    finally:
      Factory.__setattr__ = original_setattr  # type: ignore[method-assign]

    # The excluded subtree must NOT appear in the assignment sequence
    assert not any(cls == "ExcludedConfig" for (cls, _val) in recorded), (
      f"Excluded subtree should not have _nested_prefix assigned, got: {recorded}"
    )
    # The included subtree sequence is preserved
    expected = [
      ("Level1Config", "level1"),
      ("Level2Config", "level1.level2"),
      ("Level3Config", "level1.level2.level3"),
    ]
    assert recorded == expected, f"Sequence changed:\nExpected: {expected}\nRecorded: {recorded}"
