"""Tests for the _register_arg_name function.

This module tests the argument name registration and conflict detection
functionality in the factory module.
"""

import argparse

import pytest

from clevis.factory import (
  _register_arg_name,
  _registry,
  _reset_factories,
)


class TestRegisterArgName:
  """Tests for _register_arg_name function."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_basic_registration(self):
    """Test that arg_name is added to registry for the parser."""
    parser = argparse.ArgumentParser()

    # Register an argument name
    _register_arg_name(parser, "--packages", "packages")

    # Verify it was added
    assert _registry.is_arg_name_registered(parser, "--packages")

  def test_multiple_registrations_same_parser(self):
    """Test that multiple argument names can be registered for the same parser."""
    parser = argparse.ArgumentParser()

    # Register multiple argument names
    _register_arg_name(parser, "--packages", "packages")
    _register_arg_name(parser, "--name", "name")
    _register_arg_name(parser, "--verbose", "verbose")

    # Verify all were added
    assert _registry.is_arg_name_registered(parser, "--packages")
    assert _registry.is_arg_name_registered(parser, "--name")
    assert _registry.is_arg_name_registered(parser, "--verbose")

  def test_multiple_parsers_independent(self):
    """Test that registrations are independent per parser."""
    parser1 = argparse.ArgumentParser()
    parser2 = argparse.ArgumentParser()

    # Register same arg_name for both parsers
    _register_arg_name(parser1, "--packages", "packages")
    _register_arg_name(parser2, "--packages", "packages")

    # Verify both parsers have it registered
    assert _registry.is_arg_name_registered(parser1, "--packages")
    assert _registry.is_arg_name_registered(parser2, "--packages")

  def test_conflict_detection_same_parser(self):
    """Test that registering the same arg_name twice for the same parser raises ValueError."""
    parser = argparse.ArgumentParser()

    # Register an argument name
    _register_arg_name(parser, "--packages", "packages")

    # Try to register the same arg_name again - should raise
    with pytest.raises(ValueError) as exc_info:
      _register_arg_name(parser, "--packages", "other_field")

    # Verify the error message includes both arg_name and field_name
    error_msg = str(exc_info.value)
    assert "--packages" in error_msg
    assert "other_field" in error_msg

  def test_error_message_includes_arg_name(self):
    """Test that error message includes the conflicting arg_name."""
    parser = argparse.ArgumentParser()

    # Register an argument name
    _register_arg_name(parser, "--verbose", "verbose")

    # Try to register the same arg_name
    with pytest.raises(ValueError) as exc_info:
      _register_arg_name(parser, "--verbose", "another_verbose")

    error_msg = str(exc_info.value)
    assert "'--verbose'" in error_msg
    assert "conflicts" in error_msg.lower()

  def test_error_message_includes_field_name(self):
    """Test that error message includes the field_name parameter."""
    parser = argparse.ArgumentParser()

    # Register an argument name
    _register_arg_name(parser, "--name", "name_field")

    # Try to register the same arg_name for a different field
    with pytest.raises(ValueError) as exc_info:
      _register_arg_name(parser, "--name", "title_field")

    error_msg = str(exc_info.value)
    assert "'title_field'" in error_msg

  def test_no_conflict_different_parsers(self):
    """Test that same arg_name can be registered for different parsers."""
    parser1 = argparse.ArgumentParser()
    parser2 = argparse.ArgumentParser()

    # Register same arg_name for both parsers - should not raise
    _register_arg_name(parser1, "--config", "config")
    _register_arg_name(parser2, "--config", "config")

    # Verify both succeeded
    assert _registry.is_arg_name_registered(parser1, "--config")
    assert _registry.is_arg_name_registered(parser2, "--config")

  def test_error_message_format(self):
    """Test the complete error message format."""
    parser = argparse.ArgumentParser()

    # Register an argument name
    _register_arg_name(parser, "--alias", "field_one")

    # Try to register the same arg_name
    with pytest.raises(ValueError) as exc_info:
      _register_arg_name(parser, "--alias", "field_two")

    # Check complete error message
    expected_msg = "Alias '--alias' conflicts with existing argument for field 'field_two'"
    assert str(exc_info.value) == expected_msg


class TestRegisterArgNameIntegration:
  """Integration tests for _register_arg_name with reset functionality."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_reset_clears_registered_arg_names(self):
    """Test that _reset_factories clears the registry."""
    parser = argparse.ArgumentParser()

    # Register an argument name
    _register_arg_name(parser, "--test", "test")

    # Verify it's registered
    assert _registry.is_arg_name_registered(parser, "--test")

    # Reset
    _reset_factories()

    # Verify it's cleared
    assert not _registry.is_arg_name_registered(parser, "--test")

  def test_registration_after_reset(self):
    """Test that registration works correctly after reset."""
    parser = argparse.ArgumentParser()

    # Register before reset
    _register_arg_name(parser, "--before-reset", "before")

    # Reset
    _reset_factories()

    # Register after reset
    _register_arg_name(parser, "--after-reset", "after")

    # Verify only the new registration exists
    assert not _registry.is_arg_name_registered(parser, "--before-reset")
    assert _registry.is_arg_name_registered(parser, "--after-reset")

