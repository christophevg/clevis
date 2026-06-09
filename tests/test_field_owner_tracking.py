"""Test to verify _registered_field_owners is necessary.

This test checks whether duplicate field registration is prevented correctly
when multiple factories share the same parser and reference the same config class.
"""

from dataclasses import dataclass, field

import pytest

from clevis import get_config, get_factory, _reset_factories, SecurityAction


class TestDuplicateFieldRegistration:
  """Test that fields are not registered multiple times across shared configs."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_same_field_not_registered_twice_in_hierarchy(self):
    """
    Verify that the same field (owner_class, field_name) is not registered
    twice when processing nested config hierarchies.

    This was the original issue that _registered_field_owners was meant to prevent.
    """
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class ModuleConfig:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # If _registered_field_owners works correctly, this should not raise
    # an error about duplicate arguments
    config = get_config(
      ModuleConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-list-enabled", "--tools-list-format", "json"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert config.tools.list.enabled is True
    assert config.tools.list.format == "json"

  def test_multiple_calls_to_configure_parser(self):
    """
    Test that calling configure_parser multiple times doesn't register
    fields multiple times.

    This is what _registered_field_owners prevents - when the same
    Factory.configure_parser() is called multiple times (e.g., through
    _ensure_configured being called multiple times), fields should
    only be registered once per parser.
    """
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    # Create first config - this will configure the parser
    config1 = get_config(
      ToolsConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--list-enabled", "--list-format", "json"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Create second config - this should reuse the configured parser
    # Without _registered_field_owners, fields might be registered twice
    config2 = get_config(
      ToolsConfig,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--list-enabled", "--list-format", "yaml"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    assert config1.list.enabled is True
    assert config1.list.format == "json"
    assert config2.list.enabled is True
    assert config2.list.format == "yaml"

  def test_nested_config_shared_across_roots(self):
    """
    Test that when a nested config appears in multiple root configs,
    fields are registered correctly without duplication.

    This tests the scenario where:
    - RootConfig1 contains ToolsConfig
    - RootConfig2 also contains ToolsConfig
    - Both share the same default parser
    - ToolsConfig's fields should only be registered once

    With _nested_prefix tracking, this should work correctly because:
    - Each factory has its own _configured flag
    - ToolsConfig factory gets called once during first root config
    - Second root config's ToolsConfig is already configured
    """
    _reset_factories()

    @dataclass
    class ListToolConfig:
      enabled: bool = True
      format: str = "table"

    @dataclass
    class ToolsConfig:
      list: ListToolConfig = field(default_factory=ListToolConfig)

    @dataclass
    class RootConfig1:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    @dataclass
    class RootConfig2:
      tools: ToolsConfig = field(default_factory=ToolsConfig)

    # First root config - configures parser with ToolsConfig fields
    config1 = get_config(
      RootConfig1,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-list-enabled"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # Verify nested prefix is set correctly
    tools_factory = get_factory(ToolsConfig)
    assert tools_factory._nested_prefix == "tools"
    # Note: _configured is False because nested configs don't call configure_parser()

    # Second root config - ToolsConfig should NOT register fields again
    # because _registered_field_owners tracks that they're already registered
    config2 = get_config(
      RootConfig2,
      name="test",
      user=False,
      project=False,
      cli=True,
      args=["--tools-list-format", "json"],
      security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK,
      },
    )

    # If _registered_field_owners didn't prevent duplicate registration,
    # argparse would raise an error about conflicting option strings
    assert config1.tools.list.enabled is True
    assert config2.tools.list.format == "json"