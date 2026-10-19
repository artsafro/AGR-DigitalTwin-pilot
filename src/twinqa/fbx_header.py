# Header test ported from AGR src/dt_ai/validate/bundle.py (sha256 f02a83cd99bb) and
# tools/check_profile_snapshot.py (sha256 e3d001b4a9cb) on 2026-10-06; changes: standalone
# function with a reason string; ASCII FBX recognised.
"""Binary FBX 7.4/2014 header check (reg p.4 NPM, p.24 VPM; YAML asset_format)."""
import struct

MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"  # 23 bytes, then uint32 LE version
REQUIRED_VERSION = 7400  # FBX 7.4 = "2014/2015" format


def fbx_header(data: bytes) -> tuple[str, int | None]:
    """('binary', version) | ('ascii', None) | ('unknown', None)."""
    if len(data) >= 27 and data[:23] == MAGIC:
        return "binary", struct.unpack("<I", data[23:27])[0]
    if b"FBX" in data[:200] and data[:1] == b";":
        return "ascii", None
    return "unknown", None


def check_fbx_header(data: bytes) -> tuple[bool, str]:
    encoding, version = fbx_header(data)
    if encoding == "binary":
        return version == REQUIRED_VERSION, f"binary FBX version {version}"
    if encoding == "ascii":
        return False, "ASCII FBX"
    return False, "not an FBX header"


class _FbxError(Exception):
    """Binary FBX node walk failed; fbx_units turns this into the error string."""


def _header_len(version: int) -> int:
    return 25 if version >= 7500 else 13


def _need(offset: int, size: int, end: int) -> None:
    if size < 0 or offset < 0 or offset > end or size > end - offset:
        raise _FbxError(f"truncated node at offset {offset}")


def _parse_props(data: bytes, start: int, end: int, count: int) -> list[tuple[str, object]]:
    if count == 0:
        if start != end:
            raise _FbxError(f"truncated node at offset {start}")
        return []
    if count > end - start:
        raise _FbxError(f"truncated node at offset {start}")
    offset = start
    props: list[tuple[str, object]] = []
    for _ in range(count):
        _need(offset, 1, end)
        code = chr(data[offset])
        offset += 1
        if code == "Y":
            _need(offset, 2, end)
            props.append((code, struct.unpack_from("<h", data, offset)[0]))
            offset += 2
        elif code == "C":
            _need(offset, 1, end)
            props.append((code, data[offset]))
            offset += 1
        elif code == "I":
            _need(offset, 4, end)
            props.append((code, struct.unpack_from("<i", data, offset)[0]))
            offset += 4
        elif code == "F":
            _need(offset, 4, end)
            props.append((code, struct.unpack_from("<f", data, offset)[0]))
            offset += 4
        elif code == "D":
            _need(offset, 8, end)
            props.append((code, struct.unpack_from("<d", data, offset)[0]))
            offset += 8
        elif code == "L":
            _need(offset, 8, end)
            props.append((code, struct.unpack_from("<q", data, offset)[0]))
            offset += 8
        elif code in ("S", "R"):
            _need(offset, 4, end)
            length = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            _need(offset, length, end)
            raw = data[offset:offset + length]
            offset += length
            props.append((code, raw.decode("latin-1")))
        elif code in ("f", "d", "l", "i", "b"):
            _need(offset, 12, end)
            _array_len, _encoding, compressed = struct.unpack_from("<III", data, offset)
            offset += 12
            _need(offset, compressed, end)
            offset += compressed
            props.append((code, None))
        else:
            raise _FbxError(f"truncated node at offset {offset - 1}")
    if offset != end:
        raise _FbxError(f"truncated node at offset {offset}")
    return props


def _read_header(data: bytes, offset: int, end: int, version: int) -> dict | None:
    """Node name and span, or None at a null terminator. Does not read properties."""
    hlen = _header_len(version)
    if offset + hlen > end:
        raise _FbxError(f"truncated node at offset {offset}")
    if data[offset:offset + hlen] == b"\x00" * hlen:
        return None
    if version < 7500:
        end_offset, num_props, prop_len = struct.unpack_from("<III", data, offset)
        name_len = data[offset + 12]
        name_at = offset + 13
    else:
        end_offset, num_props, prop_len = struct.unpack_from("<QQQ", data, offset)
        name_len = data[offset + 24]
        name_at = offset + 25
    if end_offset <= offset or end_offset > len(data) or end_offset > end:
        raise _FbxError(f"truncated node at offset {offset}")
    _need(name_at, name_len, end_offset)
    props_at = name_at + name_len
    props_end = props_at + prop_len
    if props_end > end_offset:
        raise _FbxError(f"truncated node at offset {offset}")
    return {
        "name": data[name_at:name_at + name_len].decode("latin-1"),
        "num_props": num_props,
        "props_at": props_at,
        "props_end": props_end,
        "end_offset": end_offset,
    }


def _iter_nodes(data: bytes, start: int, end: int, version: int):
    """Yield node headers, advancing by endOffset. Child bytes are not parsed."""
    offset = start
    while offset < end:
        node = _read_header(data, offset, end, version)
        if node is None:
            break
        yield node
        offset = node["end_offset"]


def _double_prop(props: list[tuple[str, object]], name: str) -> float | None:
    label = next((value for code, value in props if code == "S"), None)
    if label != name:
        return None
    value = next((value for code, value in props if code == "D"), None)
    return None if value is None else float(value)


def fbx_units(data: bytes) -> dict:
    """UnitScaleFactor from GlobalSettings -> Properties70 -> P. Never raises.

    Top-level nodes are skipped by end offset. Only the first GlobalSettings is
    opened, and only its Properties70 -> P records are parsed. Values are
    centimetres per file unit. Missing or unreadable data leaves both factors
    None and sets error.
    """
    result = {"unit_scale_factor": None, "original_unit_scale_factor": None, "error": None}
    try:
        encoding, version = fbx_header(data)
        if encoding == "ascii":
            raise _FbxError("ASCII FBX")
        if encoding != "binary" or version is None:
            raise _FbxError("not a binary FBX")
        settings = None
        for node in _iter_nodes(data, 27, len(data), version):
            if node["name"] == "GlobalSettings":
                settings = node
                break
        if settings is None:
            raise _FbxError("GlobalSettings not found")
        unit = original = None
        for props70 in _iter_nodes(data, settings["props_end"], settings["end_offset"], version):
            if props70["name"] != "Properties70":
                continue
            for record in _iter_nodes(data, props70["props_end"], props70["end_offset"], version):
                if record["name"] != "P":
                    continue
                props = _parse_props(data, record["props_at"], record["props_end"], record["num_props"])
                found = _double_prop(props, "UnitScaleFactor")
                if found is not None:
                    unit = found
                found = _double_prop(props, "OriginalUnitScaleFactor")
                if found is not None:
                    original = found
        if unit is None:
            raise _FbxError("UnitScaleFactor not declared")
        result["unit_scale_factor"] = unit
        result["original_unit_scale_factor"] = original
    except _FbxError as exc:
        result["error"] = str(exc)
    except Exception as exc:
        result["error"] = str(exc) or exc.__class__.__name__
    return result
