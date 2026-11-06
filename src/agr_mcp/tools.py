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
                                     "description": "node handles to check; required unless scope=selection "
                                                    "(empty without scope is the error handles_required)"},
                         "scope": {"enum": ["selection"],
                                   "description": "take the current Max selection as targets; never with handles"}}}
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
# NPM archive.fbx_total.max: 1 Ground + up to 20 OKS (standards/NPM_STANDARD.yaml).
# scene=true uses this when the FBX count cannot be read, never a single readback.
PACKAGE_SCENE_FBX_UPPER = 21


def _arg_timeout(default: float) -> Callable[[dict], float]:
    return lambda args: float(args.get("timeout", default))


def _package_fbx_count(target: str) -> int | None:
    """FBX members a scene readback will walk, or None when that cannot be known.

    Names only: the central directory, not member bytes. Missing, unreadable and
    unsupported targets return None so the caller keeps the profile upper bound.
    """
    import zipfile
    try:
        path = Path(target)
        if not path.is_file():
            return None
        suffix = path.suffix.lower()
        if suffix == ".fbx":
            return 1
        if suffix != ".zip":
            return None
        with zipfile.ZipFile(path) as archive:
            return sum(1 for info in archive.infolist()
                       if not info.is_dir() and info.filename.lower().endswith(".fbx"))
    except Exception:
        return None


def _package_validate_timeout(args: dict) -> float:
    """Lock budget for agr_package_validate.

    scene=false stays one READBACK_TIMEOUT (no Blender). scene=true is one readback
    per FBX, sequentially, each READBACK_TIMEOUT (validate_package.add_scene). A count
    below 1 is still one readback. An unreadable target uses PACKAGE_SCENE_FBX_UPPER.
    Non-finite arguments are an error, never a short lease.
    """
    _check_finite(args, "arguments")
    if not args.get("scene"):
        return float(READBACK_TIMEOUT)
    count = _package_fbx_count(str(args.get("target", "")))
    if count is None:
        count = PACKAGE_SCENE_FBX_UPPER
    if count < 1:
        count = 1
    return float(count) * float(READBACK_TIMEOUT)


def _max_timeout(_args: dict) -> float:
    return MAX_TIMEOUT


# ---- handlers -------------------------------------------------------------------------------------------
def check_targets(args: dict) -> None:
    """Selection contract (docs/plans/agr-mcp.md): refuse before Max is called."""
    if args.get("handles") and args.get("scope"):
        raise ValueError("target_conflict: handles and scope are two target sources")
    if not args.get("handles") and args.get("scope") != "selection":
        raise ValueError("handles_required: pass node handles or scope=selection; an empty target set would take "
                         "the user's selection or all geometry")


def _max_tool(tool: str, transport=None):
    def handler(args: dict):
        check_targets(args)
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


# 0.7.0 pre-delivery checks (#860): agr_<block>_<name> per docs/plans/agr-tools-suite.json, all read-only.
CHECKS_070 = (
    ("agr_scene_census", "scene census: classes, materials, maps, missing files, bbox, instances"),
    ("agr_scene_units", "system unit metres, scale 1, file gamma 1.0"),
    ("agr_model_perimeter_drop", "lowest point of OKS/Ground >= 1 m below AGR_ZERO_M"),
    ("agr_tex_material_type", "only Standard/Physical materials"),
    ("agr_ucx_audit", "existing UCX_: closed, convex, no material, name, SAT intersections, budget"),
    ("agr_atlas_sets_count", "texture sets per FBX: OKS <= 40 (+1 roof), Ground <= 20, GroundEl 1, Flora 1"),
    ("agr_qa_fbx_split", "FBX split: <= 20 OKS FBX, <= 20 objects per FBX, Ground present, numbering"),
    ("agr_qa_glass", "glass on *Glass meshes, <= 20 objects, <= 7 materials, no maps, opacity 0.5"),
    ("agr_qa_preflight", "all 0.7 object checks in one report"),
    ("agr_qa_scene_hygiene", "non-mesh objects, animation, hierarchy, groups, empty meshes, modifiers"),
    ("agr_qa_xform", "unreset scale/rotation/mirror and parents"),
    ("agr_qa_zero_area", "zero-area faces, zero-length edges, isolated vertices"),
)


# 0.8 delivery edits (#908): agr_<block>_<name> -> runtime.edits_080(<plan row id>). Read rows run once; editing
# rows are preview -> apply, and apply takes only the unaltered preview report of the previous answer.
# (name, plan row id, what, kind) with kind: read | additive (export copies / new files) | rename (in place, undo)
EDITS_080 = (
    ("agr_scene_missing_maps", "scene.missing_maps", "bitmaps with a missing path and relink candidates", "read"),
    ("agr_model_triangulate", "model.triangulate", "triangulate n-gons on export copies", "additive"),
    ("agr_tex_format_fix", "tex.format_fix", "fixed PNGs (no alpha, 24 bit, size limit) into a new folder", "additive"),
    ("agr_tex_placeholders", "tex.placeholders", "new flat Diffuse/ERM/Normal placeholders", "additive"),
    ("agr_ucx_triangulate", "ucx.triangulate", "triangulate UCX on copies, convexity checked after", "additive"),
    ("agr_ucx_rename", "ucx.rename", "rename UCX pieces to UCX_SM_<Address>_Main/Ground_NNN (one undo record)",
     "rename"),
    ("agr_udim_ids_to_udims", "udim.ids_to_udims", "material ID n to UDIM tile 1000+n on export copies", "additive"),
    ("agr_qa_names_fix", "qa.names_fix", "rename objects/materials/map files by mask on export copies", "additive"),
    ("agr_qa_package", "qa.package", "delivery ZIP: sizes, FBX/PNG/GeoJSON set, names, broken files", "read"),
    ("agr_export_geojson_write", "export.geojson_write", "write a new GeoJSON passport and check it", "additive"),
    ("agr_export_ground_fbx", "export.ground_fbx", "write a new _Ground FBX (Ground, GroundEl, Flora, GroundGlass)",
     "additive"),
    ("agr_export_pivot_place", "export.pivot_place", "pivot and placement on export copies", "additive"),
    ("agr_export_zip", "export.zip", "write a new NPM/VPM ZIP with size limits, checked before and after", "additive"),
)
_LOCATE = {k: MAX_IN["properties"][k] for k in ("scene", "handles", "scope")}
_OPTIONS = {"type": "object", "description": "tool options (paths, profile); recorded in the preview"}
READ_080_IN = {"type": "object", "required": ["scene"], "additionalProperties": False,
               "properties": dict(_LOCATE, options=_OPTIONS)}
EDIT_080_IN = {"type": "object", "required": ["scene", "mode"], "additionalProperties": False,
               "properties": dict(_LOCATE, mode={"enum": ["preview", "apply"]}, options=_OPTIONS,
                                  preview={"type": "object", "description": "apply: the unaltered preview report"}),
               "oneOf": [{"properties": {"mode": {"const": "preview"}}, "not": {"required": ["preview"]}},
                         {"properties": {"mode": {"const": "apply"}}, "required": ["preview"],
                          "not": {"required": ["options"]}}]}
EDIT_080_OUT = {"type": "object", "required": ["schema", "tool", "status", "objects", "plan"],
                "properties": {"schema": {"const": 1}, "tool": {"type": "string"},
                               "status": {"enum": ["pass", "fail", "not_implemented"]},
                               "objects": {"type": "array"},
                               "plan": {"type": "object", "required": ["mode", "done", "skipped", "ambiguous"]}}}

# 0.9 rows (#979): agr_<block>_<name> -> runtime.edits_090(<plan row id>, "preview"). Every 0.9 tool takes only
# mode=preview over MCP (nothing changes; an editing row's apply stays in the panel), so all are read-only here.
# (name, plan row id, what, plan mode) with plan mode: read | select | copy | undo | file (agr-tools-suite.json)
EDITS_090 = (
    ("agr_tex_erm_normal_check", "tex.erm_normal_check", "ERM channels (R = emission only) and DirectX normals", "read"),
    ("agr_tex_finish_map", "tex.finish_map", "ID -> finish by the colour legend sheet, seams, check", "copy"),
    ("agr_udim_matid_unwrap", "udim.matid_unwrap", "MatID -> UDIM tiles with density and packing (MAF)", "copy"),
    ("agr_udim_slots", "udim.slots", "UDIM 1001.. without gaps, <=100 maps per material, SlotNumber 1..7", "read"),
    ("agr_atlas_flora", "atlas.flora", "Flora diffuse + opacity atlas, crop by UV", "file"),
    ("agr_atlas_groundel", "atlas.groundel", "one GroundEl texture set, <=512 px", "copy"),
    ("agr_place_flora_repair", "place.flora_repair", "Flora transforms and triangles repair, set check", "copy"),
    ("agr_place_maf_checks", "place.maf_checks", "flying / sunk MAF by rays down to Ground; intersections", "read"),
    ("agr_place_replace", "place.replace", "replace objects by mask or selection with a reference", "undo"),
    ("agr_place_schedule", "place.schedule", "place MAF by a schedule: placed / no reference / no room", "copy"),
    ("agr_place_drop_to_ground", "place.drop_to_ground", "drop selected objects onto Ground by a ray down", "undo"),
    ("agr_qa_address", "qa.address", "Address against the street list, parts and length", "read"),
    ("agr_qa_facade_compare", "qa.facade_compare", "facade sheet | VPM | NPM picture in one scale, seam count", "read"),
    ("agr_qa_normals", "qa.normals", "normals to the viewer, double-sided glass/Flora, smoothing", "read"),
    ("agr_qa_sintez", "qa.sintez", "our findings against a SINTEZ report by the same rules", "read"),
    ("agr_export_batch", "export.batch", "every FBX of the scene by AGR_EXPORT_PATH in one run, one report", "file"),
    ("agr_scene_maps_usage", "scene.maps_usage", "map files used by geometry / extra in maps / missing", "read"),
    ("agr_light_check", "light.check", "<=250 lights, Omni/Spot only, Omni >=5 m, Spot >=1.5 m, root and pivot",
     "select"),
    ("agr_qa_procedural_objects", "qa.procedural_objects", "uncollapsed scatter/procedural objects before FBX",
     "read"),
)
EDIT_090_IN = {"type": "object", "required": ["scene"], "additionalProperties": False,
               "properties": dict(_LOCATE, mode={"const": "preview"}, options=_OPTIONS)}


def catalog(unsafe: bool = False, max_transport=None) -> dict[str, Spec]:
    specs = [
        Spec("agr_xview_check", "AGR Tools runtime.xview in the pinned open 3ds Max (read-only: the selection "
             "before the call is restored; geometry and files untouched).",
             MAX_IN, MAX_OUT, _max_tool("agr_xview_check", max_transport), _const("max-live"),
             timeout=_max_timeout),
        Spec("agr_matid_check", "AGR Tools runtime.matid in the pinned open 3ds Max (read-only, selection "
             "restored as agr_xview_check).", MAX_IN, MAX_OUT, _max_tool("agr_matid_check", max_transport),
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
             timeout=_package_validate_timeout),
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
    for name, what in CHECKS_070:
        specs.append(Spec(name, "AGR Tools 0.7.0 runtime.checks_070 '{}' in the pinned open 3ds Max: {} (read-only; "
                          "select=False, selection unchanged, geometry and files untouched; needs runtime >= 0.7.0)."
                          .format(name.split("_", 2)[2] if name != "agr_ucx_audit" else "ucx_audit", what),
                          MAX_IN, MAX_OUT, _max_tool(name, max_transport), _const("max-live"),
                          timeout=_max_timeout))
    for name, row, what, kind in EDITS_080:
        if kind == "read":
            text = ("AGR Tools 0.8 runtime.edits_080 '{}' in the pinned open 3ds Max: {} (read-only; one call)."
                    .format(row, what))
        else:
            text = ("AGR Tools 0.8 runtime.edits_080 '{}' in the pinned open 3ds Max: {}. mode=preview changes "
                    "nothing; mode=apply takes only the unaltered preview report of the previous answer (hash and "
                    "scene state checked), never overwrites; one undo record.".format(row, what))
        specs.append(Spec(name, text + " An empty stub answers status not_implemented.",
                          READ_080_IN if kind == "read" else EDIT_080_IN, EDIT_080_OUT,
                          _max_tool(name, max_transport), _const("max-live"), read_only=kind == "read",
                          destructive=kind == "rename", timeout=_max_timeout))
    for name, row, what, mode in EDITS_090:
        text = ("AGR Tools 0.9 runtime.edits_090 '{}' in the pinned open 3ds Max: {}. Plan mode {}; over MCP only "
                "mode=preview (changes nothing, selects nothing). An empty stub answers status not_implemented "
                "(#979).".format(row, what, mode))
        specs.append(Spec(name, text, EDIT_090_IN, EDIT_080_OUT, _max_tool(name, max_transport), _const("max-live"),
                          read_only=True, destructive=False, timeout=_max_timeout))
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


PHASE0 = tuple(n for n, _ in CHECKS_070) + tuple(n for n, *_ in EDITS_080) + tuple(n for n, *_ in EDITS_090) + ("agr_xview_check", "agr_matid_check", "agr_texel_readout", "agr_fbx_readback", "agr_package_validate",
          "agr_mesh_names", "agr_geojson_check", "agr_xview_parity")
