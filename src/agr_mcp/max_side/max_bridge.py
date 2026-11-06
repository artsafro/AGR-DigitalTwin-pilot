"""new-case: code that agr-mcp runs INSIDE 3ds Max's Python, reached over the 3dsmax-mcp pipe.

The server sends one MAXScript expression that puts this file's folder on sys.path, imports this module and
calls `call(tool, root_hex, args_hex)`. Arguments travel hex-encoded so no MAXScript string escaping is needed.
`call` imports the INSTALLED AGR Tools `runtime.py` from `root` (default: the newest userScripts/AGRTools-<x.y.z>
with a runtime.py), resolves `handles` to nodes and calls exactly one `runtime.*` function: read-only, or a 0.8 edit
(`edits_080`: preview, or apply of that preview on export copies / new files, #908), or a 0.9 row preview
(`edits_090`, #979: mode=preview only, changes nothing). Apart from new files written by a 0.8 apply, it never
opens, saves, imports or exports a file.

Runtime pin (#1024, mcp-review §2.4.1): a tool group needs a MINIMUM runtime version and its entry function, not
an exact version, so one installed runtime (0.9.0 and later) serves every group of the catalogue.

Selection contract (docs/plans/agr-mcp.md "Контракт выделения"): empty `handles` without `scope` is the error
`handles_required` (the runtime is never handed nodes=None, which would mean the user's selection or all geometry);
`scope: "selection"` takes the current selection explicitly; `checks_070` runs with select=False; the selection
before the call is restored after it, and a selection that still differs is the error `selection_changed`.
Errors start with a machine code: handles_required, target_conflict, unknown_handle, scene_mismatch,
version_mismatch, runtime_missing, unsupported_tool, selection_changed.
Returns a JSON string: {"ok": true, "result": ..., "runtime_version": ..., "runtime_file": ..., "selection": ...}
or {"ok": false, "error": "..."}.
"""
import importlib
import json
import os
import sys

FUNCTIONS = {"agr_xview_check": "xview", "agr_matid_check": "matid", "agr_texel_readout": "texel_preview"}
EXPECTED_RUNTIME = "0.5.0"  # minimum runtime of FUNCTIONS (the group pins below are minimums too)
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
# AGR Tools 0.9 rows (#979): runtime.edits_090(<plan row id>, "preview", None, nodes, options). Only preview: an
# editing 0.9 row is never applied over MCP in the base, and a `select` row (light.check) selects nothing here.
# Released in package version 0.9.0 (release branch R, #979).
EDITS_090 = {"agr_tex_erm_normal_check": "tex.erm_normal_check", "agr_tex_finish_map": "tex.finish_map",
             "agr_udim_matid_unwrap": "udim.matid_unwrap", "agr_udim_slots": "udim.slots",
             "agr_atlas_flora": "atlas.flora", "agr_atlas_groundel": "atlas.groundel",
             "agr_place_flora_repair": "place.flora_repair", "agr_place_maf_checks": "place.maf_checks",
             "agr_place_replace": "place.replace", "agr_place_schedule": "place.schedule",
             "agr_place_drop_to_ground": "place.drop_to_ground", "agr_qa_address": "qa.address",
             "agr_qa_facade_compare": "qa.facade_compare", "agr_qa_normals": "qa.normals",
             "agr_qa_sintez": "qa.sintez", "agr_export_batch": "export.batch",
             "agr_scene_maps_usage": "scene.maps_usage", "agr_light_check": "light.check",
             "agr_qa_procedural_objects": "qa.procedural_objects"}
RUNTIME_090 = "0.9.0"


class BridgeError(Exception):
    """An error with a machine code: str(exc) == '<code>: <text>'."""

    def __init__(self, code, text):
        super().__init__(code + ": " + text)
        self.code = code


def requirement(tool):
    """(minimum runtime version, entry function) a tool needs from the installed runtime."""
    if tool in CHECKS_070:
        return RUNTIME_070, "checks_070"
    if tool in EDITS_080:
        return RUNTIME_080, "edits_080"
    if tool in EDITS_090:
        return RUNTIME_090, "edits_090"
    if tool in FUNCTIONS:
        return EXPECTED_RUNTIME, FUNCTIONS[tool]
    raise BridgeError("unsupported_tool", repr(tool))


def version_key(text):
    """'0.9.0' -> (0, 9, 0); anything else -> None (never compared as a string)."""
    parts = str(text).split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def check_runtime(mod, minimum, function):
    """The loaded runtime is at least `minimum` and has `function`; else version_mismatch."""
    found = getattr(mod, "VERSION", None)
    key = version_key(found)
    if key is None or key < version_key(minimum):
        raise BridgeError("version_mismatch", "AGR Tools runtime version " + str(found) + " < minimum " + minimum
                          + " (" + str(getattr(mod, "__file__", None)) + ")")
    if function and not callable(getattr(mod, function, None)):
        raise BridgeError("version_mismatch", "AGR Tools runtime " + str(found) + " at "
                          + str(getattr(mod, "__file__", None)) + " has no " + function)


def default_root(scripts_dir, minimum):
    """Newest <scripts_dir>/AGRTools-<x.y.z> holding a runtime.py with a version >= minimum, else None."""
    best = None
    try:
        names = os.listdir(scripts_dir)
    except OSError:
        return None
    for name in names:
        if not name.startswith("AGRTools-"):
            continue
        key = version_key(name[len("AGRTools-"):])
        path = os.path.join(scripts_dir, name)
        if key is None or key < version_key(minimum) or not os.path.isfile(os.path.join(path, "runtime.py")):
            continue
        if best is None or key > best[0]:
            best = (key, path)
    return best[1] if best else None


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


def _load_runtime(root, minimum=EXPECTED_RUNTIME, function=None):
    target = os.path.join(root, "runtime.py")
    if not os.path.isfile(target):
        raise BridgeError("runtime_missing", "AGR Tools runtime.py not installed at " + target)
    mod = sys.modules.get("runtime")
    if mod is not None and _norm(getattr(mod, "__file__", "") or "") != _norm(target):
        raise BridgeError("version_mismatch", "another module named runtime is loaded from "
                          + str(getattr(mod, "__file__", None)) + "; restart Max or point AGR_TOOLS_ROOT at it")
    if mod is None:
        if not any(p and _norm(p) == _norm(root) for p in sys.path):
            sys.path.insert(0, root)
        mod = importlib.import_module("runtime")
        if _norm(mod.__file__) != _norm(target):
            raise BridgeError("version_mismatch", "imported runtime from " + str(mod.__file__) + ", expected " + target)
    check_runtime(mod, minimum, function)
    return mod


def _resolve_root(rt, root, minimum):
    """AGR_TOOLS_ROOT when given; else the folder of an already loaded AGR Tools runtime; else the newest install."""
    if root:
        return root
    mod = sys.modules.get("runtime")
    loaded = os.path.dirname(getattr(mod, "__file__", "") or "") if mod is not None else ""
    if loaded and os.path.basename(loaded).startswith("AGRTools-"):
        return loaded
    scripts = str(rt.getDir(rt.name("userScripts")))
    found = default_root(scripts, minimum)
    if not found:
        raise BridgeError("runtime_missing", "no AGR Tools >= " + minimum + " installed under " + scripts
                          + " (AGRTools-<x.y.z>/runtime.py); set AGR_TOOLS_ROOT")
    return found


def _check_scene(rt, scene):
    if scene == "live":
        return
    current = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if str(rt.maxFileName) else ""
    if not current or _norm(scene) != _norm(current):
        raise BridgeError("scene_mismatch", "requested " + scene + ", open document is " + (current or "<untitled>"))


def _selection(rt):
    return [n for n in rt.selection]


def _handle(rt, node):
    return int(rt.getHandleByAnim(node))


def _targets(rt, args):
    """Explicit node list for the runtime, never None (plan: Контракт выделения)."""
    handles = list(args.get("handles") or [])
    scope = args.get("scope")
    if handles and scope:
        raise BridgeError("target_conflict", "handles and scope=" + str(scope) + " are two target sources")
    if scope == "selection":
        nodes = _selection(rt)
        if not nodes:
            raise BridgeError("handles_required", "scope=selection but nothing is selected")
        return nodes
    if scope is not None:
        raise BridgeError("target_conflict", "unknown scope " + repr(scope))
    if not handles:
        raise BridgeError("handles_required", "pass node handles (or scope=selection); an empty target set "
                          "would take the user's selection or all geometry")
    nodes = []
    for h in handles:
        n = rt.maxOps.getNodeByHandle(int(h))
        if n is None or not rt.isValidNode(n):
            raise BridgeError("unknown_handle", "unknown node handle " + str(h))
        nodes.append(n)
    return nodes


def _restore_selection(rt, before):
    """Put the selection back to `before` (list of handles); returns the handles selected afterwards."""
    live = [rt.maxOps.getNodeByHandle(h) for h in before]
    live = [n for n in live if n is not None and rt.isValidNode(n)]
    rt.clearSelection()
    if live:
        rt.select(live)
    return sorted(_handle(rt, n) for n in _selection(rt))


def run(tool, root, args):
    minimum, function = requirement(tool)
    if tool in EDITS_090 and (args.get("mode", "preview") != "preview" or args.get("preview") is not None):
        raise ValueError(tool + ": 0.9 rows take only mode=preview over MCP (#979)")
    rt = _rt()
    scene = args.get("scene")
    if not isinstance(scene, str) or not scene:
        raise ValueError("scene is required")
    _check_scene(rt, scene)
    nodes = _targets(rt, args)
    mod = _load_runtime(_resolve_root(rt, root, minimum), minimum, function)
    before = sorted(_handle(rt, n) for n in _selection(rt))
    if tool in EDITS_080:
        result = mod.edits_080(EDITS_080[tool], args.get("mode", "preview"), args.get("preview"), nodes,
                               args.get("options"))
    elif tool in EDITS_090:
        result = mod.edits_090(EDITS_090[tool], "preview", None, nodes, args.get("options"))
    elif tool in CHECKS_070:
        result = mod.checks_070(CHECKS_070[tool], nodes, select=False)
    else:
        result = getattr(mod, function)(nodes)
    after = sorted(_handle(rt, n) for n in _selection(rt))
    restored = False
    if after != before:
        after = _restore_selection(rt, before)
        restored = True
        if after != before:
            raise BridgeError("selection_changed", "selection before " + str(before) + ", after restore "
                              + str(after))
    return result, {"runtime_version": mod.VERSION, "runtime_file": mod.__file__,
                    "selection": {"before_count": len(before), "restored": restored,
                                  "scope": args.get("scope") or "handles"}}


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
