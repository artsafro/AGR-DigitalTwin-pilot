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
version_mismatch, runtime_missing, unsupported_tool, selection_changed, stale_preview, needs_human.

v2 (#1024 branch 0): plan rows are routed by id (ROUTES) for three bridge tools of the v2 catalogue:
`agr_check_run` (read/select rows, one Max call for many checks), `agr_op_preview` (an editing row, mode=preview;
the 1.0 stage buttons too) and `agr_op_apply` (apply of a server-held preview; only the 0.8 rows in APPLY_OVER_MCP,
anything else is `needs_human`). Every runtime.edits_080/090/100 call passes actor='mcp' when the installed runtime
accepts `actor` (then the runtime journals the call and the answer says `journaled: true`).
Returns a JSON string: {"ok": true, "result": ..., "runtime_version": ..., "runtime_file": ..., "selection": ...,
"doc": ..., "journaled": ...} or {"ok": false, "error": "...", "journaled": ...}.
"""
import importlib
import inspect
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
# 0.5.0 diagnostics: runtime.checks_050(<key>, nodes, path) (plan rows of version 0.5, all read).
ROWS_050 = {"qa.names": "names", "qa.tris": "tris", "tex.check": "textures", "qa.pivot": "pivot",
            "qa.geojson": "geojson"}
RUNTIME_050 = "0.5.0"
# 0.1 / 0.3 read rows served by one runtime function each (FUNCTIONS above).
ROWS_FN = {"qa.xview": "xview", "qa.matid": "matid", "udim.texel": "texel_preview"}
ROWS_070 = {"scene.census": "census", "scene.units": "units", "model.perimeter_drop": "perimeter_drop",
            "tex.material_type": "material_type", "ucx.audit": "ucx_audit", "atlas.sets_count": "sets_count",
            "qa.fbx_split": "fbx_split", "qa.glass": "glass", "qa.preflight": "preflight",
            "qa.scene_hygiene": "scene_hygiene", "qa.xform": "xform", "qa.zero_area": "zero_area"}
READ_080 = ("scene.missing_maps", "qa.package")
READ_090 = ("tex.erm_normal_check", "udim.slots", "place.maf_checks", "qa.address", "qa.facade_compare",
            "qa.normals", "qa.sintez", "scene.maps_usage", "light.check", "qa.procedural_objects")
# AGR Tools 1.0 conveyor (#1024): runtime.edits_100(<row>, "preview", None, nodes, options, actor="mcp").
# The same 33 ids as runtime.EDITS_100 (a test pins the equality). Over MCP only preview; apply of a 1.0 row is a
# panel/dock press (owner answers 06.11.2026), so agr_op_apply answers needs_human for them.
ROWS_100 = ("project.passport", "source.intake", "scene.source_class", "body.prepare", "model.attach_by_material",
            "model.move_apart", "model.grid_cleanup", "scene.small_parts", "win.place", "win.generate",
            "model.glass_planes", "body.capsules", "body.roof", "mat.table", "mat.tiles", "tex.plug_colour",
            "vpm.build", "udim.rescale", "udim.distortion", "tex.dilate", "udim.plugs", "npm.build",
            "atlas.facade_strip", "npm.to_vpm", "udim.udims_to_ids", "pack.deliver", "ucx.gap", "ucx.stairs",
            "light.export", "qa.omk_te", "export.place_by_passport", "agent.request", "agent.accept")
READ_100 = ("scene.source_class", "tex.plug_colour", "udim.distortion", "udim.udims_to_ids", "ucx.stairs",
            "qa.omk_te")
# Released in package version 1.0.0 (release branch R, #1024); the entry function is the real gate
# (check_runtime), the minimum refuses older installs.
RUNTIME_100 = "1.0.1"
# row -> (group, key, minimum runtime, entry function)
ROUTES = {}
ROUTES.update({r: ("fn", k, EXPECTED_RUNTIME, k) for r, k in ROWS_FN.items()})
ROUTES.update({r: ("c050", k, RUNTIME_050, "checks_050") for r, k in ROWS_050.items()})
ROUTES.update({r: ("c070", k, RUNTIME_070, "checks_070") for r, k in ROWS_070.items()})
ROUTES.update({r: ("e080", r, RUNTIME_080, "edits_080") for r in EDITS_080.values()})
ROUTES.update({r: ("e090", r, RUNTIME_090, "edits_090") for r in EDITS_090.values()})
ROUTES.update({r: ("e100", r, RUNTIME_100, "edits_100") for r in ROWS_100})
READ_ROWS = frozenset(ROWS_FN) | frozenset(ROWS_050) | frozenset(ROWS_070) | frozenset(READ_080) \
    | frozenset(READ_090) | frozenset(READ_100)
EDIT_ROWS = frozenset(ROUTES) - READ_ROWS
# apply allowed over MCP today: the 0.8 additive / rename rows (export copies, new files, one undo record).
APPLY_OVER_MCP = frozenset(r for r in EDITS_080.values() if r not in READ_080)
V2_TOOLS = ("agr_check_run", "agr_op_preview", "agr_op_apply")
_STATE = {"journaled": []}


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
    """Anim handle (getHandleByAnim, as runtime's selection hash); NOT the node handle of maxOps.getNodeByHandle."""
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
    """Put the selection back to `before` (anim handles); returns the anim handles selected afterwards."""
    live = [rt.getAnimByHandle(h) for h in before]
    live = [n for n in live if n is not None and rt.isValidNode(n)]
    rt.clearSelection()
    if live:
        rt.select(live)
    return sorted(_handle(rt, n) for n in _selection(rt))


def _doc(rt):
    """The open document: full path, or 'untitled' (ObjRef doc, journal doc, preview binding)."""
    return os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if str(rt.maxFileName) else "untitled"


def accepts_actor(fn):
    """True when a runtime dispatcher takes `actor` (runtime >= the #1024 base); old runtimes are called without."""
    try:
        return "actor" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _edit(mod, function, row, mode, preview, nodes, options):
    fn = getattr(mod, function)
    if accepts_actor(fn):
        _STATE["journaled"].append(row)  # the runtime journals in a finally, also when it raises
        return fn(row, mode, preview, nodes, options, actor="mcp")
    return fn(row, mode, preview, nodes, options)


def _guarded(rt, args, body):
    """Run body() and keep the user's selection: restore it, or fail selection_changed."""
    before = sorted(_handle(rt, n) for n in _selection(rt))
    result = body()
    after = sorted(_handle(rt, n) for n in _selection(rt))
    restored = False
    if after != before:
        after = _restore_selection(rt, before)
        restored = True
        if after != before:
            raise BridgeError("selection_changed", "selection before " + str(before) + ", after restore "
                              + str(after))
    return result, {"before_count": len(before), "restored": restored, "scope": args.get("scope") or "handles"}


def run(tool, root, args):
    if tool in V2_TOOLS:
        return run_v2(tool, root, args)
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

    def body():
        if tool in EDITS_080:
            return _edit(mod, "edits_080", EDITS_080[tool], args.get("mode", "preview"), args.get("preview"), nodes,
                         args.get("options"))
        if tool in EDITS_090:
            return _edit(mod, "edits_090", EDITS_090[tool], "preview", None, nodes, args.get("options"))
        if tool in CHECKS_070:
            return mod.checks_070(CHECKS_070[tool], nodes, select=False)
        return getattr(mod, function)(nodes)
    result, selection = _guarded(rt, args, body)
    return result, {"runtime_version": mod.VERSION, "runtime_file": mod.__file__, "selection": selection,
                    "doc": _doc(rt)}


def _row(row, allowed, what):
    if not isinstance(row, str) or row not in ROUTES:
        raise BridgeError("unsupported_tool", "unknown plan row " + repr(row))
    if row not in allowed:
        raise BridgeError("unsupported_tool", repr(row) + " is not " + what)
    return ROUTES[row]


def _call_row(mod, row, mode, preview, nodes, options):
    group, key, _minimum, function = ROUTES[row]
    if group == "fn":
        return getattr(mod, key)(nodes)
    if group == "c050":
        return mod.checks_050(key, nodes, path=(options or {}).get("path"))
    if group == "c070":
        return mod.checks_070(key, nodes, select=False)
    return _edit(mod, function, row, mode, preview, nodes, options)


def run_v2(tool, root, args):
    """agr_check_run / agr_op_preview / agr_op_apply: plan rows by id (ROUTES), one Max call."""
    if tool == "agr_check_run":
        rows = list(args.get("check_ids") or ())
        if not rows:
            raise ValueError("check_ids is empty")
        routes = [_row(r, READ_ROWS, "a read/select row (agr_check_run)") for r in rows]
        mode = "preview"
    else:
        rows = [args.get("op")]
        routes = [_row(rows[0], EDIT_ROWS, "an editing row (agr_op_preview/agr_op_apply)")]
        mode = "apply" if tool == "agr_op_apply" else "preview"
        if mode == "apply" and rows[0] not in APPLY_OVER_MCP:
            raise BridgeError("needs_human", "apply of " + rows[0] + " is confirmed only by a button in the "
                              "AGR Tools panel/dock")
        if mode == "apply" and not isinstance(args.get("preview"), dict):
            raise BridgeError("stale_preview", "apply needs the server-held preview report")
    rt = _rt()
    scene = args.get("scene")
    if not isinstance(scene, str) or not scene:
        raise ValueError("scene is required")
    _check_scene(rt, scene)
    expect = args.get("expect") or {}
    if expect.get("doc") is not None and expect["doc"] != _doc(rt):
        raise BridgeError("stale_preview", "document changed since the preview: " + str(expect["doc"]) + " -> "
                          + _doc(rt))
    nodes = _targets(rt, args)
    minimum = max((r[2] for r in routes), key=version_key)
    mod = _load_runtime(_resolve_root(rt, root, minimum), minimum, None)
    for _group, _key, row_min, function in routes:
        check_runtime(mod, row_min, function)
    if expect.get("runtime_version") is not None and expect["runtime_version"] != mod.VERSION:
        raise BridgeError("stale_preview", "AGR Tools runtime changed since the preview: "
                          + str(expect["runtime_version"]) + " -> " + str(mod.VERSION))
    options = args.get("options")

    def body():
        if tool == "agr_check_run":
            return {"checks": {r: _call_row(mod, r, "preview", None, nodes, options) for r in rows}}
        return _call_row(mod, rows[0], mode, args.get("preview") if mode == "apply" else None, nodes,
                         None if mode == "apply" else options)
    result, selection = _guarded(rt, args, body)
    return result, {"runtime_version": mod.VERSION, "runtime_file": mod.__file__, "selection": selection,
                    "doc": _doc(rt)}


def call(tool, root_hex, args_hex):
    _STATE["journaled"] = []
    try:
        _dedupe_own_path()
        root = bytes.fromhex(str(root_hex)).decode("utf-8")
        args = json.loads(bytes.fromhex(str(args_hex)).decode("utf-8"))
        result, info = run(str(tool), root, args)
        out = {"ok": True, "result": result, "journaled": bool(_STATE["journaled"]),
               "journaled_rows": list(_STATE["journaled"])}
        out.update(info)
        return json.dumps(out, allow_nan=False)
    except Exception as exc:  # noqa: BLE001 - every failure goes back to the client as a named error
        return json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc),
                           "journaled": bool(_STATE["journaled"]), "journaled_rows": list(_STATE["journaled"])})
