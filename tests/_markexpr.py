"""new-case: read the pytest ``-m`` exclusion expression from pyproject addopts (#1122).

The opt-in marker exclusion list for the default suite lives in
``[tool.pytest.ini_options].addopts`` as ``-m '<expr>'``. This helper is the
single place that parses it, so ``DEFAULT_MARKEXPR`` in
``tests/dcc/test_ac08_xview_native_parity.py`` cannot drift from pyproject.toml
(see docs/research/merge-gate-deselect-190-vs-card-417.md, finding 6).

Behaviour (documented, card rule 21):
- ``-m 'not blender and not job'`` -> ``'not blender and not job'``.
- glued forms ``-mnot job`` and ``-m=not job`` -> ``'not job'`` (the value runs
  from ``-m``/``-m=`` to the next option token or the end of the string).
- ``-m a -m b`` -> ``'b'`` (pytest ``store``: the last occurrence wins).
- addopts without ``-m`` -> ``''``.
- a trailing ``-m`` with no following token -> ``ValueError`` (malformed input).
- ``addopts`` may be a TOML string or an array of strings; any other type ->
  ``ValueError`` naming it.
"""
import shlex
import tomllib


def _last_m_expr(tokens, raw):
    """Return the value of the last ``-m`` option in ``tokens``, ``''`` when absent."""
    result = ""
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        if token == "-m":
            i += 1
            parts = []
            while i < n and not tokens[i].startswith("-"):
                parts.append(tokens[i])
                i += 1
            if not parts:
                raise ValueError("addopts '-m' has no expression: {!r}".format(raw))
            result = " ".join(parts)
        elif token.startswith("-m="):
            parts = [token[len("-m="):]]
            i += 1
            while i < n and not tokens[i].startswith("-"):
                parts.append(tokens[i])
                i += 1
            result = " ".join(part for part in parts if part)
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
    value type raises ``ValueError`` naming it.
    """
    with open(pyproject_path, "rb") as fh:
        data = tomllib.load(fh)
    addopts = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", "")
    if isinstance(addopts, str):
        return markexpr_from_addopts(addopts)
    if isinstance(addopts, list):
        return _last_m_expr([str(item) for item in addopts], addopts)
    raise ValueError(
        "addopts must be a string or an array of strings, got {}: {!r}".format(
            type(addopts).__name__, addopts
        )
    )
