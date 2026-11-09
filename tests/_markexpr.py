"""new-case: read the pytest ``-m`` exclusion expression from pyproject addopts (#1122).

The opt-in marker exclusion list for the default suite lives in
``[tool.pytest.ini_options].addopts`` as ``-m '<expr>'``. This helper is the
single place that parses it, so ``DEFAULT_MARKEXPR`` in
``tests/dcc/test_ac08_xview_native_parity.py`` cannot drift from pyproject.toml
(see docs/research/merge-gate-deselect-190-vs-card-417.md, finding 6).

Behaviour (documented, card rule 21):
- ``-m 'not blender and not job'`` -> ``'not blender and not job'``.
- addopts without ``-m`` -> ``''``.
- a trailing ``-m`` with no following token -> ``ValueError`` (malformed input).
"""
import shlex
import tomllib


def markexpr_from_addopts(addopts):
    """Return the ``-m`` expression from a pytest addopts string, ``''`` when absent.

    ``shlex.split`` (posix) turns ``-m 'not blender and not job'`` into a single
    expression token. ``-m`` must be a flag token immediately followed by its
    value; a ``-m`` with no value raises ``ValueError`` naming the input.
    """
    tokens = shlex.split(addopts or "")
    for index, token in enumerate(tokens):
        if token != "-m":
            continue
        if index + 1 >= len(tokens):
            raise ValueError("addopts '-m' has no expression: {!r}".format(addopts))
        return tokens[index + 1]
    return ""


def markexpr_from_pyproject(pyproject_path):
    """Return the ``-m`` expression from ``[tool.pytest.ini_options].addopts``.

    A missing section or key is treated as no ``-m`` (``''``).
    """
    with open(pyproject_path, "rb") as fh:
        data = tomllib.load(fh)
    addopts = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", "")
    return markexpr_from_addopts(addopts)
