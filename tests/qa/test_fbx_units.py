"""Pure-Python FBX GlobalSettings unit readback (V002)."""
import random
import struct
import subprocess

import pytest

from twinqa.fbx_header import fbx_units
from twinqa.scene import find_blender

MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"


class _Writer:
    def __init__(self, version: int):
        self.version = version
        self.buf = bytearray(MAGIC + struct.pack("<I", version))

    def _hlen(self) -> int:
        return 13 if self.version < 7500 else 25

    def node(self, name: str, props: list[bytes] | None = None, children=None) -> None:
        props = props or []
        start = len(self.buf)
        hlen = self._hlen()
        self.buf += b"\x00" * hlen
        name_b = name.encode("ascii")
        self.buf += name_b
        prop_bytes = b"".join(props)
        self.buf += prop_bytes
        if children is not None:
            children()
            self.buf += b"\x00" * hlen
        end = len(self.buf)
        counts = (end, len(props), len(prop_bytes))
        if self.version < 7500:
            meta = struct.pack("<III", *counts) + bytes([len(name_b)])
        else:
            meta = struct.pack("<QQQ", *counts) + bytes([len(name_b)])
        self.buf[start:start + hlen] = meta

    def finish(self) -> bytes:
        self.buf += b"\x00" * self._hlen()
        return bytes(self.buf)


def _s(text: str) -> bytes:
    raw = text.encode("ascii")
    return b"S" + struct.pack("<I", len(raw)) + raw


def _d(value: float) -> bytes:
    return b"D" + struct.pack("<d", float(value))


def _arr_d(values: list[float]) -> bytes:
    payload = struct.pack("<" + "d" * len(values), *[float(v) for v in values])
    return b"d" + struct.pack("<III", len(values), 0, len(payload)) + payload


def _double_p(name: str, value: float) -> list[bytes]:
    return [_s(name), _s("double"), _s("Number"), _s(""), _d(value)]


def fbx_bytes(version: int, unit: float | None, *, prefix: bool = False, original: float | None = None) -> bytes:
    writer = _Writer(version)
    if prefix:
        writer.node("NodeAttribute", [_s("Mesh"), _arr_d([1.0, 2.0, 3.0]), _s("Geometry")])

    def properties():
        if unit is not None:
            writer.node("P", _double_p("UnitScaleFactor", unit))
        if original is not None:
            writer.node("P", _double_p("OriginalUnitScaleFactor", original))
        if unit is None:
            writer.node("P", [_s("UpAxis"), _s("int"), _s("Integer"), _s(""), b"I" + struct.pack("<i", 1)])

    writer.node("GlobalSettings", children=lambda: writer.node("Properties70", children=properties))
    return writer.finish()


def test_unit_scale_factor_7400_metre():
    parsed = fbx_units(fbx_bytes(7400, 100.0, original=100.0))
    assert parsed == {"unit_scale_factor": 100.0, "original_unit_scale_factor": 100.0, "error": None}


def test_unit_scale_factor_7400_centimetre():
    parsed = fbx_units(fbx_bytes(7400, 1.0, original=1.0))
    assert parsed["unit_scale_factor"] == 1.0 and parsed["error"] is None


def test_unit_scale_factor_7500_64bit_header():
    parsed = fbx_units(fbx_bytes(7500, 100.0, original=100.0))
    assert parsed["unit_scale_factor"] == 100.0 and parsed["error"] is None


def test_global_settings_found_after_array_and_string_node():
    parsed = fbx_units(fbx_bytes(7400, 100.0, prefix=True, original=100.0))
    assert parsed["unit_scale_factor"] == 100.0 and parsed["error"] is None


def test_global_settings_without_unit_scale_factor():
    parsed = fbx_units(fbx_bytes(7400, None, original=100.0))
    assert parsed["unit_scale_factor"] is None
    assert parsed["error"] == "UnitScaleFactor not declared"


def test_missing_global_settings():
    writer = _Writer(7400)
    writer.node("NodeAttribute", [_s("Mesh"), _arr_d([1.0]), _s("Geometry")])
    parsed = fbx_units(writer.finish())
    assert parsed["unit_scale_factor"] is None and parsed["original_unit_scale_factor"] is None
    assert parsed["error"] == "GlobalSettings not found"


def test_ascii_fbx_is_an_error():
    parsed = fbx_units(b"; FBX 7.4.0 project file")
    assert parsed["unit_scale_factor"] is None and parsed["original_unit_scale_factor"] is None
    assert parsed["error"] == "ASCII FBX"


def test_truncated_prefixes_never_raise():
    data = fbx_bytes(7400, 100.0, prefix=True, original=100.0)
    for size in range(len(data)):
        parsed = fbx_units(data[:size])
        assert set(parsed) == {"unit_scale_factor", "original_unit_scale_factor", "error"}


def test_global_settings_after_nested_objects_tree():
    writer = _Writer(7400)
    writer.node("Objects", children=lambda: writer.node(
        "Geometry",
        children=lambda: writer.node(
            "Vertices",
            [_arr_d([0.0, 1.0, 2.0]), b"I" + struct.pack("<i", 3), b"L" + struct.pack("<q", 4)],
        ),
    ))
    writer.node("GlobalSettings", children=lambda: writer.node(
        "Properties70",
        children=lambda: writer.node("P", _double_p("UnitScaleFactor", 100.0)),
    ))
    parsed = fbx_units(writer.finish())
    assert parsed["unit_scale_factor"] == 100.0 and parsed["error"] is None


def test_fuzz_byte_flips_never_raise():
    rng = random.Random(159)
    bases = (fbx_bytes(7400, 100.0, original=100.0), fbx_bytes(7500, 100.0, original=100.0))
    keys = {"unit_scale_factor", "original_unit_scale_factor", "error"}
    for _ in range(2000):
        for base in bases:
            data = bytearray(base)
            for _flip in range(rng.randint(1, 4)):
                pos = rng.randrange(27, len(data))
                data[pos] ^= 0xFF
            parsed = fbx_units(bytes(data))
            assert set(parsed) == keys
            assert parsed["unit_scale_factor"] is None or isinstance(parsed["unit_scale_factor"], float)


def test_global_settings_end_offset_before_start_returns_error():
    data = bytearray(fbx_bytes(7400, 100.0))
    start = 27
    assert data[start + 13:start + 13 + len(b"GlobalSettings")] == b"GlobalSettings"
    struct.pack_into("<I", data, start, start - 1)
    parsed = fbx_units(bytes(data))
    assert parsed["unit_scale_factor"] is None
    assert parsed["error"] == f"truncated node at offset {start}"


BLENDER = find_blender()
_EXPORT = """
import bpy, sys
out, mode = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2)
kwargs = {'filepath': out}
if mode == 'metres':
    kwargs['apply_scale_options'] = 'FBX_SCALE_UNITS'
bpy.ops.export_scene.fbx(**kwargs)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
def test_blender_export_unit_scale_factor(tmp_path):
    for mode, expected in (("default", 1.0), ("metres", 100.0)):
        path = tmp_path / f"{mode}.fbx"
        subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python-expr", _EXPORT, "--", str(path), mode],
                       check=True, capture_output=True, timeout=300)
        assert fbx_units(path.read_bytes())["unit_scale_factor"] == expected
