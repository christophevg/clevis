"""Configclass decorator for registering dataclasses with Clevis.

Provides the @configclass decorator that combines @dataclass with factory registration.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from clevis.factory import get_factory

logger = logging.getLogger(__name__)

# TypeVar for the decorator pattern.
# Unconstrained (no bound) because the decorator can be applied to any class
# that will become a dataclass. The TypeVar preserves type information so that
# @configclass class X returns type X (not a generic "type" or "object").
T = TypeVar("T")


def configclass(
  cls: type[T] | None = None,
  cmd: str | None = None,
  help: str | None = None,
  aliases: list[str] | None = None,
  config: str | None = None,
) -> type[T] | Callable[[type[T]], type[T]]:
  """
  Decorator that registers a dataclass with Clevis's factory system.

  Applies @dataclass to the class and registers it with get_factory().

  Usage::

    @configclass
    class MyConfig:
      name: str = "default"

  This is equivalent to::

    @dataclass
    class MyConfig:
      name: str = "default"

    get_factory(MyConfig)  # register

  For subcommands::

    @configclass(cmd="check", help="Run diagnostics", aliases=["c", "chk"])
    class CheckConfig:
      verbose: bool = False

  For config extraction without CLI subcommand::

    @configclass(config="output")
    class OutputConfig:
      rich: bool = False

  Args:
    cls: The class to decorate.
    cmd: Optional subcommand name for CLI applications with multiple commands.
    help: Optional help text for the subcommand (used with cmd parameter).
    aliases: Optional list of aliases for the subcommand (used with cmd parameter).
    config: Optional TOML extraction key (requires cmd parameter).

  Returns:
    The decorated class (now a dataclass).

  Raises:
    ValueError: If config parameter is provided without cmd parameter.
  """

  def decorator(clz: type[T]) -> type[T]:
    clz = dataclass(clz)
    factory = get_factory(clz)  # get_factory upserts if not yet available

    # Validate config requires cmd
    if config is not None and cmd is None:
      raise ValueError(
        f"@configclass parameter 'config' requires 'cmd' parameter. "
        f"Use @configclass(cmd='name', config='section') instead. "
        f"Class: {clz.__name__}"
      )

    # Warn if help/aliases used without cmd
    if not cmd:
      if help is not None:
        logger.warning(
          f"@configclass parameter 'help' has no effect without 'cmd' on class {clz.__name__}"
        )
      if aliases is not None:
        logger.warning(
          f"@configclass parameter 'aliases' has no effect without 'cmd' on class {clz.__name__}"
        )

    if cmd:
      factory.cmd = cmd
    if help is not None:
      factory.help = help
    if aliases is not None:
      factory.aliases = aliases
    if config is not None:
      factory.config = config
    return clz

  # Decorator return logic:
  # Python decorators can be used in two ways:
  #
  # 1. Without arguments: @configclass
  #    - cls is passed directly, parameters are None
  #    - Decorator is called immediately
  #    - Return the decorated class directly
  #
  # 2. With arguments: @configclass(cmd="check")
  #    - cls is None, parameters are provided
  #    - Decorator must return a function that takes cls
  #    - Return a lambda that will be called with cls
  #
  # The condition checks for the "without arguments" case:
  # - cls is not None (decorator received class directly)
  # - All optional parameters are None (no parentheses or empty @configclass())
  if cls and not cmd and help is None and aliases is None and config is None:
    # Case 1: @configclass without arguments
    # The decorator was used as @configclass, not @configclass(...)
    # Apply the decorator immediately and return the result
    return decorator(cls)
  else:
    # Case 2: @configclass with arguments or cls is None
    # The decorator was used as @configclass(cmd="check") or similar
    # Return a function that takes the class and applies the decorator
    return lambda clz: decorator(clz)
