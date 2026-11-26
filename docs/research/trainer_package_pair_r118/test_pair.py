from pathlib import Path

import pytest

from replay import explicit_pair


def test_pair_ignores_nested_decoys_and_refuses_bad_references(tmp_path):
    built = tmp_path / "built"
    built.mkdir()
    for name in ("body.fbx", "package.zip", "wrong.txt"):
        (built / name).touch()
    nested = built / "nested"
    nested.mkdir()
    (nested / "body.fbx").touch()
    (nested / "package.zip").touch()
    (tmp_path / "outside.zip").touch()
    assert explicit_pair(built, Path("body.fbx"), Path("package.zip")) == (
        built / "body.fbx", built / "package.zip"
    )
    for fbx, archive in [("missing.fbx", "package.zip"), ("body.fbx", "missing.zip"),
                         ("wrong.txt", "package.zip"), ("body.fbx", "../outside.zip"),
                         ("body.fbx", str(tmp_path / "outside.zip"))]:
        with pytest.raises(ValueError):
            explicit_pair(built, Path(fbx), Path(archive))
