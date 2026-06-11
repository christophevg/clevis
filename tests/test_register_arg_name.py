"""Tests for the _register_arg_name function.

This module tests the argument name registration and conflict detection
functionality in the factory module.
"""

import argparse

import pytest

from clevis.factory import (
  _register_arg_name,
  _registered_arg_names,
  _reset_factories,
)


class TestRegisterArgName:
  """Tests for _register_arg_name function."""

  def setup_method(self):
    """Reset factories before each test."""
    _reset_factories()

  def test_basic_registration(self):
    """Test that arg_name is added to _registered_arg_names for the parser."""
    parser = argparse.ArgumentParser()

    # Initialize the parser in _registered_arg_names
    _registered_arg_names[parser] = set()

    # Register an argument name
    _register_arg_name(parser, "--packages", "packages")

    # Verify it was added
    assert "--packages" in _registered_arg_names[parser]
    assert len(_registered_arg_names[parser]) == 1

  def test_multiple_registrations_same_parser(self):
    """Test that multiple argument names can be registered for the same parser."""
    parser = argparse.ArgumentParser()

    # Initialize the parser in _registered_arg_names
    _registered_arg_names[parser] = set()

    # Register multiple argument names
    _register_arg_name(parser, "--packages", "packages")
    _register_arg_name(parser, "--name", "name")
    _register_arg_name(parser, "--verbose", "verbose")

    # Verify all were added
    assert len(_registered_arg_names[parser]) == 3
    assert "--packages" in _registered_arg_names[parser]
    assert "--name" in _registered_arg_names[parser]
    assert "--verbose" in _registered_arg_names[parser]

  def test_multiple_parsers_independent(self):
    """Test that registrations are independent per parser."""
    parser1 = argparse.ArgumentParser()
    parser2 = argparse.ArgumentParser()

    # Initialize both parsers in _registered_arg_names
    _registered_arg_names[parser1] = set()
    _registered_arg_names[parser2] = set()

    # Register same arg_name for both parsers
    _register_arg_name(parser1, "--packages", "packages")
    _register_arg_name(parser2, "--packages", "packages")

    # Verify both parsers have it registered
    assert "--packages" in _registered_arg_names[parser1]
    assert "--packages" in _registered_arg_names[parser2]

  def test_conflict_detection_same_parser(self):
    """Test that registering the same arg_name twice for the same parser raises ValueError."""
    parser = argparse.ArgumentParser()

    # Initialize the parser in _registered_arg_names
    _registered_arg_names[parser] = set()

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

    # Initialize the parser in _registered_arg_names
    _registered_arg_names[parser] = set()

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

    # Initialize the parser in _registered_arg_names
    _registered_arg_names[parser] = set()

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

    # Initialize both parsers in _registered_arg_names
    _registered_arg_names[parser1] = set()
    _registered_arg_names[parser2] = set()

    # Register same arg_name for both parsers - should not raise
    _register_arg_name(parser1, "--config", "config")
    _register_arg_name(parser2, "--config", "config")

    # Verify both succeeded
    assert "--config" in _registered_arg_names[parser1]
    assert "--config" in _registered_arg_names[parser2]

  def test_error_message_format(self):
    """Test the complete error message format."""
    parser = argparse.ArgumentParser()

    # Initialize the parser in _registered_arg_names
    _registered_arg_names[parser] = set()

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
    """Test that _reset_factories clears _registered_arg_names."""
    parser = argparse.ArgumentParser()

    # Initialize the parser in _registered_arg_names
    _registered_arg_names[parser] = set()

    # Register an argument name
    _register_arg_name(parser, "--test", "test")

    # Verify it's registered
    assert "--test" in _registered_arg_names[parser]

    # Reset
    _reset_factories()

    # Verify it's cleared
    assert parser not in _registered_arg_names

  def test_registration_after_reset(self):
    """Test that registration works correctly after reset."""
    parser = argparse.ArgumentParser()

    # Register before reset
    _registered_arg_names[parser] = set()
    _register_arg_name(parser, "--before-reset", "before")

    # Reset
    _reset_factories()

    # Re-initialize and register after reset
    _registered_arg_names[parser] = set()
    _register_arg_name(parser, "--after-reset", "after")

    # Verify only the new registration exists
    assert "--before-reset" not in _registered_arg_names[parser]
    assert "--after-reset" in _registered_arg_names[parser]
