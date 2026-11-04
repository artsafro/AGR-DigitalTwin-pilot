"""new-case: code that agr-mcp runs INSIDE 3ds Max's Python, reached over the 3dsmax-mcp pipe.

The server sends one MAXScript expression that puts this file's folder on sys.path, imports this module and
calls `call(tool, root_hex, args_hex)`. Arguments travel hex-encoded so no MAXScript string escaping is needed.
`call` imports the INSTALLED AGR Tools `runtime.py` from `root` (default: userScripts/AGRTools-0.5.0),
resolves `handles` to nodes and calls exactly one read-only `runtime.*` function. It never opens, saves,
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


def _load_runtime(root):
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
    if getattr(mod, "VERSION", None) != EXPECTED_RUNTIME:
        raise RuntimeError("AGR Tools runtime version " + str(getattr(mod, "VERSION", None))
                           + " != " + EXPECTED_RUNTIME)
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
    if tool not in FUNCTIONS:
        raise ValueError("unsupported tool " + repr(tool))
    rt = _rt()
    scene = args.get("scene")
    if not isinstance(scene, str) or not scene:
        raise ValueError("scene is required")
    _check_scene(rt, scene)
    if not root:
        root = os.path.join(str(rt.getDir(rt.name("userScripts"))), "AGRTools-" + EXPECTED_RUNTIME)
    mod = _load_runtime(root)
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
