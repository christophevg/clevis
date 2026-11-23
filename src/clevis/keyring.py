"""Keyring interpolation for Clevis TOML configuration.

Expands ``${keyring:service/username}`` placeholders against the system
keyring before the TOML parser sees the file. Clevis performs this as its
own pre-parse pass, so it works with every configured TOML backend
(envtoml, tomlev, tomli, tomllib) — no backend support required.

The ``keyring`` package is imported lazily: only when a placeholder is
actually present. Installs that never use the syntax pay nothing — no
import, no dependency (container installs stay dependency-free).

Syntax: ``${keyring:service/username}``

- Splits on the FIRST ``/``: the service may not contain ``/``, the
  username may.
- No escape syntax: a literal ``${keyring:...}`` string cannot be embedded
  in a TOML file (same limitation as the ``${VAR}`` environment syntax).

Storing secrets (interactive, never in shell history):

    clevis keyring set <service> <username>

Caveat: a stored secret containing ``${...}`` is subsequently interpolated
by env-aware backends (envtoml, tomlev), and a secret containing
``${keyring:...}`` is rejected outright — avoid ``${`` in secrets.
"""

import importlib
import re
from types import ModuleType

_KEYRING_PATTERN = re.compile(r"\$\{keyring:([^}]+)\}")
"""Matches ${keyring:service/username} refs; each ref is validated on resolution."""

_INSTALL_HINT = "Install the keyring package with:\n  pip install clevis[keyring]"

_LIB_CONTEXT = (
  "A ${keyring:...} placeholder was found in the configuration, "
  "but the 'keyring' package is not available."
)


class KeyringError(RuntimeError):
  """Raised when a ${keyring:...} placeholder cannot be resolved."""


def _get_keyring(purpose: str = _LIB_CONTEXT) -> ModuleType:
  """Lazily import and return the keyring module.

  Args:
    purpose: Sentence explaining why keyring is needed; used verbatim in
      the error message when the import fails.

  Raises:
    KeyringError: When the keyring package is not importable, with
      installation guidance appended.
  """
  try:
    return importlib.import_module("keyring")
  except ImportError as exc:
    raise KeyringError(f"{purpose} {_INSTALL_HINT}") from exc


def expand_keyring_placeholders(text: str) -> str:
  """Expand ``${keyring:service/username}`` placeholders against the system keyring.

  Fast path: text without any ``${keyring:`` prefix is returned untouched —
  the keyring package is never imported.

  Args:
    text: Raw TOML file content (pre-parse).

  Returns:
    Text with every keyring placeholder replaced by the stored secret.

  Raises:
    KeyringError: When keyring is not installed, an entry is missing, the
      placeholder syntax is malformed, or a resolved secret itself contains
      a ``${keyring:...}`` reference (nested/recursive placeholder).
  """
  if "${keyring:" not in text:
    return text
  keyring = _get_keyring()

  def _resolve(match: re.Match[str]) -> str:
    ref = match.group(1)
    service, sep, username = ref.partition("/")
    if not sep or not service or not username:
      raise KeyringError(
        f"Invalid keyring placeholder '${{keyring:{ref}}}': expected "
        "'${keyring:service/username}' (split on the first '/'; the username "
        "may contain '/')"
      )
    secret = keyring.get_password(service, username)
    if secret is None:
      raise KeyringError(
        f"No keyring entry found for service={service!r}, username={username!r}."
        f"\nStore one with:  clevis keyring set {service} {username}"
      )
    return str(secret)

  result = _KEYRING_PATTERN.sub(_resolve, text)
  if "${keyring:" in result:
    raise KeyringError(
      "An unresolved '${keyring:...}' placeholder remains after expansion: "
      "either malformed syntax (e.g. '${keyring:}') or a resolved secret "
      "itself contains a nested '${keyring:...}' reference."
    )
  return result
