from pathlib import Path

import pytest

from dt_ai.cli.main import _native_path

BS = chr(92)


@pytest.mark.parametrize("text,nt,want", [
    ("/c/Users/a/tmp/evals", True, Path("C:/Users/a/tmp/evals")),
    (BS + "c" + BS + "Users" + BS + "a", True, Path("C:/Users/a")),
    ("C:/x/evals", True, Path("C:/x/evals")),
    ("tmp/evals", True, Path("tmp/evals")),
    ("/c/Users/a", False, Path("/c/Users/a")),
    ("/cc/x", True, Path("/cc/x")),
])
def test_native_path(text, nt, want):
    assert _native_path(text, nt=nt) == want
