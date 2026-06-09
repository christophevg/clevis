"""Configclass decorator for registering dataclasses with Clevis.

Provides the @configclass decorator that combines @dataclass with factory registration.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from clevis.factory import get_factory

logger = logging.getLogger(__name__)

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

  if cls and not cmd and help is None and aliases is None and config is None:
    return decorator(cls)
  else:
    return lambda clz: decorator(clz)
