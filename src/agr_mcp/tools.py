"""new-case: the agr-mcp phase-0 tool catalog: schemas, host per call and handlers (plan sections 2 and 5).

Every handler wraps exactly one existing function and returns its output made JSON-safe (dataclasses ->
dicts, a JSON round trip with allow_nan=False). No handler takes a `code` argument; the only tool that does,
`agr_exec_unsafe`, is added by `catalog(unsafe=True)` and the server registers it only with AGR_MCP_UNSAFE=1.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import max_pipe

ROOT = Path(__file__).resolve().parents[2]
MAX_TIMEOUT = float(os.environ.get("AGR_MCP_MAX_TIMEOUT", "600"))


def _load(name: str, rel: str):
    """Import a repo script module (tools/qa/*.py) once, by file path."""
    key = f"agr_mcp_wrapped_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, ROOT / rel)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


def jsonable(value: Any) -> Any:
    """Dataclasses -> dicts, then a strict JSON round trip; NaN/inf is an error, never a silent null."""
    def default(o):
        if hasattr(o, "to_dict") and not isinstance(o, type):
            return o.to_dict()
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        if hasattr(o, "item"):  # numpy scalar
            return o.item()
        if hasattr(o, "tolist"):
            return o.tolist()
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        if isinstance(o, Path):
            return str(o)
        raise TypeError(f"not JSON-serializable: {type(o).__name__}")
    if hasattr(value, "to_dict") and not isinstance(value, type):
        value = value.to_dict()
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    return json.loads(json.dumps(value, default=default, allow_nan=False))


def _file(path: str, what: str, suffixes: tuple[str, ...] = ()) -> Path:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"{what} is not an existing file: {path}")
    if suffixes and p.suffix.lower() not in suffixes:
        raise ValueError(f"{what} must be one of {suffixes}: {path}")
    return p


def _profiles():
    from twinqa.profiles import load_profiles
    return load_profiles()


# ---- schemas -------------------------------------------------------------------------------------------
STR = {"type": "string", "minLength": 1}
FINDING = {"type": "object", "required": ["name", "status", "observed", "expected"],
           "properties": {"name": {"type": "string"}, "status": {"type": "string"},
                          "observed": {"type": "string"}, "expected": {"type": "string"}}}
MAX_IN = {"type": "object", "required": ["scene"], "additionalProperties": False,
          "properties": {"scene": {"type": "string", "minLength": 1,
                                   "description": "'live' (the pinned open Max document) or its exact path"},
                         "handles": {"type": "array", "uniqueItems": True,
                                     "items": {"type": "integer", "minimum": 1},
                                     "description": "node handles; empty = runtime._targets (selection or all geometry)"}}}
MAX_OUT = {"type": "object", "required": ["schema", "tool", "status", "objects"],
           "properties": {"schema": {"const": 1}, "tool": {"type": "string"}, "status": {"enum": ["pass", "fail"]},
                          "objects": {"type": "array", "items": {
                              "type": "object", "required": ["findings"], "properties": {"findings": {
                                  "type": "array", "items": {"type": "object", "required": ["code", "ids"]}}}}}}}
TEXEL_OUT = {"type": "object"}  # texel_preview's own report; exact shape is runtime's (plan: min/median px/m)


@dataclass(frozen=True)
class Spec:
    name: str
    description: str
    input: dict
    result: dict
    handler: Callable[[dict], Any]
    host: Callable[[dict], str]
    read_only: bool = True
    destructive: bool = False
    timeout: Callable[[dict], float] | None = None  # the wrapped call's own timeout; sizes the host lock (#871)


def _const(host: str) -> Callable[[dict], str]:
    return lambda _args: host


READBACK_TIMEOUT = 600  # twinqa.scene.readback default
EXEC_TIMEOUT = 120


def _arg_timeout(default: float) -> Callable[[dict], float]:
    return lambda args: float(args.get("timeout", default))


def _max_timeout(_args: dict) -> float:
    return MAX_TIMEOUT


# ---- handlers -------------------------------------------------------------------------------------------
def _max_tool(tool: str, transport=None):
    def handler(args: dict):
        payload = max_pipe.call_bridge(tool, args, MAX_TIMEOUT, transport=transport)
        return payload["result"]
    return handler


def h_fbx_readback(args: dict):
    from twinqa.scene import readback
    p = _file(args["fbx_path"], "fbx_path", (".fbx",))
    return jsonable(readback(p, blender=os.environ.get("AGR_BLENDER") or None, timeout=int(args.get("timeout", READBACK_TIMEOUT))))


def h_package_validate(args: dict):
    vp = _load("validate_package", "tools/qa/validate_package.py")
    p = _file(args["target"], "target", (".zip", ".fbx", ".png", ".geojson"))
    return jsonable(vp.validate(p, args.get("kind"), _profiles(), scene=bool(args.get("scene", False)),
                                ground_area_m2=args.get("ground_area_m2"),
                                footprint_holes=args.get("footprint_holes")))


def h_mesh_names(args: dict):
    from twinqa.naming import mesh_name_findings
    return jsonable(mesh_name_findings(list(args["names"]), args["kind"], args["role"], args["fbx_stem"],
                                       int(args["limit"]), args["src"]))


def h_geojson_check(args: dict):
    from twinqa.geojson import geojson_findings
    p = _file(args["path"], "path", (".geojson",))
    return jsonable(geojson_findings(p.read_bytes(), _profiles().vpm, bool(args["ground"]),
                                     source_name=args.get("source_name") or p.name))


def h_xview_parity(args: dict):
    xp = _load("xview_parity", "tools/qa/xview_parity.py")
    return jsonable(xp.compare(args["dump"]))


def _check_finite(value, where="dump"):
    """Reject NaN/inf anywhere in a JSON argument (JSON-RPC parsers may accept them)."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number in {where}")
    if isinstance(value, dict):
        for k, v in value.items():
            _check_finite(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _check_finite(v, f"{where}[{i}]")


def catalog(unsafe: bool = False, max_transport=None) -> dict[str, Spec]:
    specs = [
        Spec("agr_xview_check", "AGR Tools runtime.xview in the pinned open 3ds Max (selection-modifying: the "
             "runtime selects nodes with findings; geometry and files untouched).",
             MAX_IN, MAX_OUT, _max_tool("agr_xview_check", max_transport), _const("max-live"),
             timeout=_max_timeout),
        Spec("agr_matid_check", "AGR Tools runtime.matid in the pinned open 3ds Max (selection-modifying, "
             "as agr_xview_check).", MAX_IN, MAX_OUT, _max_tool("agr_matid_check", max_transport),
             _const("max-live"), timeout=_max_timeout),
        Spec("agr_texel_readout", "AGR Tools runtime.texel_preview in the pinned open 3ds Max (read-only).",
             MAX_IN, TEXEL_OUT, _max_tool("agr_texel_readout", max_transport), _const("max-live"),
             timeout=_max_timeout),
        Spec("agr_fbx_readback", "twinqa.scene.readback: headless Blender readback of one FBX (read-only).",
             {"type": "object", "required": ["fbx_path"], "additionalProperties": False,
              "properties": {"fbx_path": STR, "timeout": {"type": "integer", "minimum": 1, "maximum": 7200}}},
             {"type": "object", "required": ["source"]}, h_fbx_readback, _const("blender-batch"),
             timeout=_arg_timeout(READBACK_TIMEOUT)),
        Spec("agr_package_validate", "tools/qa/validate_package.validate on a delivery file (read-only; "
             "scene=true adds the headless Blender readback).",
             {"type": "object", "required": ["target"], "additionalProperties": False,
              "properties": {"target": STR, "kind": {"enum": ["npm", "vpm", None]}, "scene": {"type": "boolean"},
                             "ground_area_m2": {"type": ["number", "null"], "exclusiveMinimum": 0},
                             "footprint_holes": {}}},
             {"type": "object", "required": ["stages"]}, h_package_validate,
             lambda a: "blender-batch" if a.get("scene") else "offline",
             timeout=lambda _a: float(READBACK_TIMEOUT)),
        Spec("agr_mesh_names", "twinqa.naming.mesh_name_findings: V012 mesh/UCX names of one FBX (offline).",
             {"type": "object", "required": ["names", "kind", "role", "fbx_stem", "limit", "src"],
              "additionalProperties": False,
              "properties": {"names": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                             "kind": {"enum": ["npm", "vpm"]}, "role": STR, "fbx_stem": STR,
                             "limit": {"type": "integer", "exclusiveMinimum": 0}, "src": STR}},
             {"type": "array", "items": FINDING}, h_mesh_names, _const("offline")),
        Spec("agr_geojson_check", "twinqa.geojson.geojson_findings with the locked VPM profile (offline).",
             {"type": "object", "required": ["path", "ground"], "additionalProperties": False,
              "properties": {"path": STR, "ground": {"type": "boolean"}, "source_name": STR}},
             {"type": "array", "items": FINDING}, h_geojson_check, _const("offline")),
        Spec("agr_xview_parity", "tools/qa/xview_parity.compare on a Max xView dump (offline).",
             {"type": "object", "required": ["dump"], "additionalProperties": False,
              "properties": {"dump": {"type": "object", "required": ["nodes", "m_per_unit"]}}},
             {"type": "array", "items": {"type": "object",
                                          "required": ["node", "vertices_only_max", "vertices_only_ours"]}},
             h_xview_parity, _const("offline")),
    ]
    if unsafe:
        def h_exec(args: dict):
            raw = (max_transport or max_pipe.pipe_transport)(args["code"], float(args.get("timeout", EXEC_TIMEOUT)))
            return {"value": max_pipe.decode_value(raw)}
        specs.append(Spec(
            "agr_exec_unsafe", "DESTRUCTIVE debug hatch: arbitrary MAXScript in the pinned open Max. Only with "
            "AGR_MCP_UNSAFE=1; every call is audited with code_sha256/code_bytes.",
            {"type": "object", "required": ["code"], "additionalProperties": False,
             "properties": {"code": STR, "timeout": {"type": "integer", "minimum": 1, "maximum": 7200}}},
            {"type": "object", "required": ["value"]}, h_exec, _const("max-live"),
            read_only=False, destructive=True, timeout=_arg_timeout(EXEC_TIMEOUT)))
    return {s.name: s for s in specs}


PHASE0 = ("agr_xview_check", "agr_matid_check", "agr_texel_readout", "agr_fbx_readback", "agr_package_validate",
          "agr_mesh_names", "agr_geojson_check", "agr_xview_parity")
