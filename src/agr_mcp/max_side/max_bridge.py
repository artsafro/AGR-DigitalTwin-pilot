"""new-case: code that agr-mcp runs INSIDE 3ds Max's Python, reached over the 3dsmax-mcp pipe.

The server sends one MAXScript expression that puts this file's folder on sys.path, imports this module and
calls `call(tool, root_hex, args_hex)`. Arguments travel hex-encoded so no MAXScript string escaping is needed.
`call` imports the INSTALLED AGR Tools `runtime.py` from `root` (default: userScripts/AGRTools-0.5.0),
resolves `handles` to nodes and calls exactly one `runtime.*` function: read-only, or a 0.8 edit
(`edits_080`: preview, or apply of that preview on export copies / new files, #908). Apart from new files
written by a 0.8 apply, it never opens, saves,
imports or exports a file and never passes `select=` (plan section 2: the runtime default is kept).
Returns a JSON string: {"ok": true, "result": ..., "runtime_version": ..., "runtime_file": ...}
or {"ok": false, "error": "..."}.
"""
import importlib
import json
import os
import sys

FUNCTIONS = {"agr_xview_check": "xview", "agr_matid_check": "matid", "agr_texel_readout": "texel_preview"}
EXPECTED_RUNTIME = "0.5.0"
# AGR Tools 0.7.0 pre-delivery checks (#860): runtime.checks_070(<check>, nodes), read-only, need runtime 0.7.0
CHECKS_070 = {"agr_scene_census": "census", "agr_scene_units": "units", "agr_model_perimeter_drop": "perimeter_drop",
              "agr_tex_material_type": "material_type", "agr_ucx_audit": "ucx_audit",
              "agr_atlas_sets_count": "sets_count", "agr_qa_fbx_split": "fbx_split", "agr_qa_glass": "glass",
              "agr_qa_preflight": "preflight", "agr_qa_scene_hygiene": "scene_hygiene", "agr_qa_xform": "xform",
              "agr_qa_zero_area": "zero_area"}
RUNTIME_070 = "0.7.0"
# AGR Tools 0.8 delivery edits (#908): runtime.edits_080(<plan row id>, mode, preview, nodes, options).
# Released in package version 0.8.0 (release branch R, #908).
EDITS_080 = {"agr_scene_missing_maps": "scene.missing_maps", "agr_model_triangulate": "model.triangulate",
             "agr_tex_format_fix": "tex.format_fix", "agr_tex_placeholders": "tex.placeholders",
             "agr_ucx_triangulate": "ucx.triangulate", "agr_ucx_rename": "ucx.rename",
             "agr_udim_ids_to_udims": "udim.ids_to_udims", "agr_qa_names_fix": "qa.names_fix",
             "agr_qa_package": "qa.package", "agr_export_geojson_write": "export.geojson_write",
             "agr_export_ground_fbx": "export.ground_fbx", "agr_export_pivot_place": "export.pivot_place",
             "agr_export_zip": "export.zip"}
RUNTIME_080 = "0.8.0"


def _rt():
    from pymxs import runtime
    return runtime


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def _dedupe_own_path():
    here = os.path.dirname(os.path.abspath(__file__))
    seen = False
    for p in list(sys.path):
        if p and _norm(p) == _norm(here):
            if seen:
                sys.path.remove(p)
            seen = True


def _load_runtime(root, expected=EXPECTED_RUNTIME):
    target = os.path.join(root, "runtime.py")
    if not os.path.isfile(target):
        raise FileNotFoundError("AGR Tools runtime.py not installed at " + target)
    mod = sys.modules.get("runtime")
    if mod is not None and _norm(getattr(mod, "__file__", "") or "") != _norm(target):
        raise RuntimeError("another module named runtime is loaded from " + str(getattr(mod, "__file__", None))
                           + "; restart Max or point AGR_TOOLS_ROOT at it")
    if mod is None:
        if not any(p and _norm(p) == _norm(root) for p in sys.path):
            sys.path.insert(0, root)
        mod = importlib.import_module("runtime")
        if _norm(mod.__file__) != _norm(target):
            raise RuntimeError("imported runtime from " + str(mod.__file__) + ", expected " + target)
    if getattr(mod, "VERSION", None) != expected:
        raise RuntimeError("AGR Tools runtime version " + str(getattr(mod, "VERSION", None))
                           + " != " + expected)
    return mod


def _check_scene(rt, scene):
    if scene == "live":
        return
    current = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if str(rt.maxFileName) else ""
    if not current or _norm(scene) != _norm(current):
        raise ValueError("scene mismatch: requested " + scene + ", open document is " + (current or "<untitled>"))


def _nodes(rt, handles):
    if not handles:
        return None
    nodes = []
    for h in handles:
        n = rt.maxOps.getNodeByHandle(int(h))
        if n is None or not rt.isValidNode(n):
            raise ValueError("unknown node handle " + str(h))
        nodes.append(n)
    return nodes


def run(tool, root, args):
    if tool not in FUNCTIONS and tool not in CHECKS_070 and tool not in EDITS_080:
        raise ValueError("unsupported tool " + repr(tool))
    expected = RUNTIME_070 if tool in CHECKS_070 else RUNTIME_080 if tool in EDITS_080 else EXPECTED_RUNTIME
    rt = _rt()
    scene = args.get("scene")
    if not isinstance(scene, str) or not scene:
        raise ValueError("scene is required")
    _check_scene(rt, scene)
    if not root:
        root = os.path.join(str(rt.getDir(rt.name("userScripts"))), "AGRTools-" + expected)
    mod = _load_runtime(root, expected)
    if tool in EDITS_080:
        if not hasattr(mod, "edits_080"):
            raise RuntimeError("AGR Tools runtime at " + str(mod.__file__) + " has no edits_080 (0.8 base, #908)")
        result = mod.edits_080(EDITS_080[tool], args.get("mode", "preview"), args.get("preview"),
                               _nodes(rt, args.get("handles") or []), args.get("options"))
    elif tool in CHECKS_070:
        result = mod.checks_070(CHECKS_070[tool], _nodes(rt, args.get("handles") or []))
    else:
        result = getattr(mod, FUNCTIONS[tool])(_nodes(rt, args.get("handles") or []))
    return result, {"runtime_version": mod.VERSION, "runtime_file": mod.__file__}


def call(tool, root_hex, args_hex):
    try:
        _dedupe_own_path()
        root = bytes.fromhex(str(root_hex)).decode("utf-8")
        args = json.loads(bytes.fromhex(str(args_hex)).decode("utf-8"))
        result, info = run(str(tool), root, args)
        out = {"ok": True, "result": result}
        out.update(info)
        return json.dumps(out, allow_nan=False)
    except Exception as exc:  # noqa: BLE001 - every failure goes back to the client as a named error
        return json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc)})
