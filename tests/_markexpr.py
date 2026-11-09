"""new-case: read the pytest ``-m`` exclusion expression from pyproject addopts (#1122).

The opt-in marker exclusion list for the default suite lives in
``[tool.pytest.ini_options].addopts`` as ``-m '<expr>'``. This helper is the
single place that parses it, so ``DEFAULT_MARKEXPR`` in
``tests/dcc/test_ac08_xview_native_parity.py`` cannot drift from pyproject.toml
(see docs/research/merge-gate-deselect-190-vs-card-417.md, finding 6).

Behaviour (documented, card rule 21):
- ``-m 'not blender and not job'`` -> ``'not blender and not job'``.
- a space-separated ``-m`` takes exactly the next token (pytest ``store``
  semantics): a missing next token or one starting with ``-`` -> ``ValueError``.
- glued forms ``-mnot job`` and ``-m=not job`` -> ``'not job'``; the value runs
  from ``-m``/``-m=`` to the next option token or the end of the string. This
  continuation is a deliberate deviation from pytest, which gives ``'not'`` for
  ``-mnot job`` (its ``-m`` ``store`` action consumes only ``not``).
- an empty glued ``-m=`` -> ``ValueError`` (malformed input).
- ``-m a -m b`` -> ``'b'`` (pytest ``store``: the last occurrence wins).
- addopts without ``-m`` -> ``''``.
- ``addopts`` may be a TOML string or an array of strings; a non-string item in
  the array, or any other type, -> ``ValueError`` naming it.
"""
import shlex
import tomllib


def _last_m_expr(tokens, raw):
    """Return the value of the last ``-m`` option in ``tokens``, ``''`` when absent.

    A space-separated ``-m`` takes exactly the next token; a missing next token
    or one starting with ``-`` raises ``ValueError``. The glued ``-m=X``/``-mX``
    forms continue across following non-option tokens (a documented deviation
    from pytest's ``store`` action, which consumes only the glued value).
    """
    result = ""
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        if token == "-m":
            # Space-separated form: take exactly the next token.
            if i + 1 >= n or tokens[i + 1].startswith("-"):
                raise ValueError("addopts '-m' has no expression: {!r}".format(raw))
            result = tokens[i + 1]
            i += 2
        elif token.startswith("-m="):
            parts = [token[len("-m="):]]
            i += 1
            while i < n and not tokens[i].startswith("-"):
                parts.append(tokens[i])
                i += 1
            value = " ".join(part for part in parts if part)
            if not value:
                raise ValueError("addopts '-m=' has an empty expression: {!r}".format(raw))
            result = value
        elif token.startswith("-m") and len(token) > 2:
            parts = [token[2:]]
            i += 1
            while i < n and not tokens[i].startswith("-"):
                parts.append(tokens[i])
                i += 1
            result = " ".join(part for part in parts if part)
        else:
            i += 1
    return result


def markexpr_from_addopts(addopts):
    """Return the ``-m`` expression from a pytest addopts string, ``''`` when absent.

    ``shlex.split`` (posix) turns ``-m 'not blender and not job'`` into a single
    expression token. ``-m`` must be a flag token followed by its value; a glued
    value (``-mnot job``, ``-m=not job``) is accepted, and with several ``-m``
    flags the last one wins (matching pytest's ``store`` action). A ``-m`` with no
    value raises ``ValueError`` naming the input.
    """
    if not isinstance(addopts, str):
        raise ValueError(
            "addopts must be a string, got {}: {!r}".format(type(addopts).__name__, addopts)
        )
    return _last_m_expr(shlex.split(addopts or ""), addopts)


def markexpr_from_pyproject(pyproject_path):
    """Return the ``-m`` expression from ``[tool.pytest.ini_options].addopts``.

    ``addopts`` may be a TOML string or an array of strings (pytest accepts
    both). A missing section or key is treated as no ``-m`` (``''``); any other
    value type, or a non-string item in the array, raises ``ValueError`` naming
    it.
    """
    with open(pyproject_path, "rb") as fh:
        data = tomllib.load(fh)
    addopts = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", "")
    if isinstance(addopts, str):
        return markexpr_from_addopts(addopts)
    if isinstance(addopts, list):
        if not all(isinstance(item, str) for item in addopts):
            raise ValueError(
                "addopts array items must be strings: {!r}".format(addopts)
            )
        return _last_m_expr(list(addopts), addopts)
    raise ValueError(
        "addopts must be a string or an array of strings, got {}: {!r}".format(
            type(addopts).__name__, addopts
        )
    )
