"""new-case: code that agr-mcp runs INSIDE 3ds Max's Python, reached over the 3dsmax-mcp pipe.

The server sends one MAXScript expression that puts this file's folder on sys.path, imports this module and
calls `call(tool, root_hex, args_hex)`. Arguments travel hex-encoded so no MAXScript string escaping is needed.
`call` imports the INSTALLED AGR Tools `runtime.py` from `root` (default: userScripts/AGRTools-0.5.0),
resolves `handles` to nodes and calls exactly one `runtime.*` function: read-only, or a 0.8 edit
(`edits_080`: preview, or apply of that preview on export copies / new files, #908), or a 0.9 row preview
(`edits_090`, #979: mode=preview only, changes nothing), or a phase-2 edit on copies (`PHASE2`, #1021: explicit
targets, selection restored, preview kept here, new nodes checked against the reported copies). Apart from new
files written by a 0.8 apply or a phase-2 apply/commit, it never opens, saves,
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
# AGR MCP phase 2 (#1021, plan section 5 "mutations on copies"): preview -> apply on new export copies / one new
# FBX. tool -> (runtime function, preview family, kind). Targets are explicit: handles, or scope="selection"
# resolved here into a node list; runtime._targets(None) is never reached. The selection is saved before and
# restored after every call; a different selection afterwards is the error selection_changed.
PHASE2 = {"agr_cleanup_preview": ("cleanup_preview", "cleanup", "preview"),
          "agr_cleanup_apply": ("cleanup_apply", "cleanup", "apply"),
          "agr_uv_nudge_preview": ("nudge_preview", "nudge", "preview"),
          "agr_uv_nudge_apply": ("nudge_apply", "nudge", "apply"),
          "agr_atlas_preview": ("atlas_preview", "atlas", "preview"),
          "agr_atlas_apply": ("atlas_apply", "atlas", "apply"),
          "agr_ucx_preview": ("ucx_preview", "ucx", "preview"),
          "agr_ucx_apply": ("ucx_apply", "ucx", "apply"),
          "agr_export_preview": ("export_preview", "export", "preview"),
          "agr_export_commit": ("export_commit", "export", "apply")}
RUNTIME_PHASE2 = "0.9.0"
PREVIEW_KEEP = 8  # previews kept per family; older ones must be re-run
# family -> {sha256 of the canonical JSON: native preview}. Kept across the importlib.reload the pipe script does,
# so apply gets the runtime's own object back (tuples stay tuples), and only a preview this bridge produced.
_PREVIEWS = globals().get("_PREVIEWS", {})


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


def _handle(n):
    return int(n.handle)


def _json_default(o):
    """bytes (atlas preview images) -> length + sha256; the native bytes stay in the stored preview."""
    if isinstance(o, (bytes, bytearray)):
        import hashlib
        return {"bytes": len(o), "sha256": hashlib.sha256(bytes(o)).hexdigest()}
    raise TypeError("not JSON-serializable: " + type(o).__name__)


def _canonical(value):
    """The JSON form a client sees, and the sha256 of its canonical text (sorted keys, no NaN)."""
    text = json.dumps(value, allow_nan=False, sort_keys=True, default=_json_default)
    import hashlib
    return json.loads(text), hashlib.sha256(text.encode("utf-8")).hexdigest()


def _phase2_targets(rt, args):
    """Selection contract (plan section 2): non-empty handles XOR scope='selection'; never None."""
    handles = args.get("handles") or []
    scope = args.get("scope")
    if handles and scope is not None:
        raise ValueError("two target sources: handles and scope=" + repr(scope))
    if scope is not None and scope != "selection":
        raise ValueError("unsupported scope " + repr(scope))
    if not handles and scope is None:
        raise ValueError("handles_required: give non-empty handles or scope='selection'")
    if scope == "selection":
        nodes = list(rt.selection)
        if not nodes:
            raise ValueError("scope=selection but the selection is empty")
        return nodes, [_handle(n) for n in nodes]
    if len(set(int(h) for h in handles)) != len(handles):
        raise ValueError("duplicate handle in " + repr(handles))
    return _nodes(rt, handles), [int(h) for h in handles]


def _restore_selection(rt, saved):
    rt.clearSelection()
    alive = [n for n in saved if rt.isValidNode(n)]
    if alive:
        rt.select(alive)


def _store_preview(family, preview):
    shown, sha = _canonical(preview)
    store = _PREVIEWS.setdefault(family, {})
    store.pop(sha, None)
    store[sha] = preview
    while len(store) > PREVIEW_KEEP:
        store.pop(next(iter(store)))
    return shown


def _take_preview(family, preview):
    if not isinstance(preview, dict):
        raise ValueError("preview must be the object returned by the preview tool")
    _shown, sha = _canonical(preview)
    native = _PREVIEWS.get(family, {}).pop(sha, None)  # single use, as the panel drops it after any apply
    if native is None:
        raise ValueError("unknown or altered " + family + " preview (sha256 " + sha[:12]
                         + "); run the preview tool again")
    return native


def _copies(rt, nodes):
    return [{"handle": _handle(n), "name": str(n.name)} for n in nodes if rt.isValidNode(n)]


def run_phase2(tool, mod, rt, args):
    fn_name, family, kind = PHASE2[tool]
    nodes, handles = _phase2_targets(rt, args)
    fn = getattr(mod, fn_name, None)
    if fn is None:
        raise RuntimeError("AGR Tools runtime at " + str(mod.__file__) + " has no " + fn_name)
    saved = list(rt.selection)
    before_sel = sorted(_handle(n) for n in saved)
    before = set(_handle(n) for n in rt.objects)
    try:
        if family == "cleanup" and kind == "preview":
            raw = fn(nodes, args.get("options"))
        elif family == "export" and kind == "preview":
            raw = fn(nodes, args["target"])
        elif family == "export":
            raw = fn(nodes, _take_preview(family, args.get("preview")), args["target"])
        elif kind == "apply":
            raw = fn(nodes, _take_preview(family, args.get("preview")))
        else:
            raw = fn(nodes)
    finally:
        _restore_selection(rt, saved)
    after_sel = sorted(_handle(n) for n in rt.selection)
    if after_sel != before_sel:
        raise RuntimeError("selection_changed: before " + repr(before_sel) + ", after " + repr(after_sel))
    after = set(_handle(n) for n in rt.objects)
    removed = sorted(before - after)
    if removed:
        raise RuntimeError("source nodes deleted: " + repr(removed))
    created = sorted(after - before)
    if kind == "preview" or family == "export":
        if created:
            raise RuntimeError(tool + " left new nodes " + repr(created))
        result = _store_preview(family, raw) if kind == "preview" else _canonical(raw)[0]
    else:
        copies, report = raw
        out = _copies(rt, copies)
        if sorted(c["handle"] for c in out) != created:
            raise RuntimeError("new nodes " + repr(created) + " != reported copies "
                               + repr([c["handle"] for c in out]))
        result = {"copies": out, "report": _canonical(report)[0]}
    return result, {"handles": handles, "scope": args.get("scope")}


def run(tool, root, args):
    if tool not in FUNCTIONS and tool not in CHECKS_070 and tool not in EDITS_080 and tool not in EDITS_090 \
            and tool not in PHASE2:
        raise ValueError("unsupported tool " + repr(tool))
    if tool in EDITS_090 and (args.get("mode", "preview") != "preview" or args.get("preview") is not None):
        raise ValueError(tool + ": 0.9 rows take only mode=preview over MCP (#979)")
    expected = (RUNTIME_070 if tool in CHECKS_070 else RUNTIME_080 if tool in EDITS_080
                else RUNTIME_090 if tool in EDITS_090 else RUNTIME_PHASE2 if tool in PHASE2 else EXPECTED_RUNTIME)
    rt = _rt()
    scene = args.get("scene")
    if not isinstance(scene, str) or not scene:
        raise ValueError("scene is required")
    _check_scene(rt, scene)
    if not root:
        root = os.path.join(str(rt.getDir(rt.name("userScripts"))), "AGRTools-" + expected)
    if tool in PHASE2:
        _phase2_targets(rt, args)  # contract errors before the runtime is even imported
    mod = _load_runtime(root, expected)
    if tool in PHASE2:
        result, info = run_phase2(tool, mod, rt, args)
        info.update(runtime_version=mod.VERSION, runtime_file=mod.__file__)
        return result, info
    if tool in EDITS_080:
        if not hasattr(mod, "edits_080"):
            raise RuntimeError("AGR Tools runtime at " + str(mod.__file__) + " has no edits_080 (0.8 base, #908)")
        result = mod.edits_080(EDITS_080[tool], args.get("mode", "preview"), args.get("preview"),
                               _nodes(rt, args.get("handles") or []), args.get("options"))
    elif tool in EDITS_090:
        if not hasattr(mod, "edits_090"):
            raise RuntimeError("AGR Tools runtime at " + str(mod.__file__) + " has no edits_090 (0.9 base, #979)")
        result = mod.edits_090(EDITS_090[tool], "preview", None, _nodes(rt, args.get("handles") or []),
                               args.get("options"))
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
