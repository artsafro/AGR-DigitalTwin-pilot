"""new-case: the v2 MCP catalogue generated from docs/plans/agr-tools-suite.json (#1024 branch 0, mcp-review 3.2).

Rules (the plan is the source; a row without a bridge route fails the catalogue build, never a silent gap):
* stage tools: one tool per new 1.0 stage button = rows with version 1.0, fate `stage`, mcp yes, whose id prefix is
  not one of the ten plan blocks (project, source, body, win, mat, vpm, npm, pack, agent: the 15 new buttons of
  SPLIT.md item 2). Name agr_<prefix>_<name> (agr_project_passport, agr_win_place). Over MCP preview only, through
  runtime.edits_100(row, "preview", actor="mcp"); the preview is held by the server (preview_id);
* `agr_check_run(check_ids[], scene, handles|scope|refs)`: check_ids = read/select rows with mcp yes of the released
  versions (plan `versions[].status == done`) + the read rows of 1.0 (fate stage);
* `agr_op_preview(op, scene, handles|scope|refs, options)`: op = editing rows (copy/undo/file/agent) with mcp yes of
  the edit-contract versions 0.8 / 0.9 and the 1.0 stage rows that are not stage tools; returns preview_id;
* `agr_op_apply(preview_id, idempotency_key?)`: only rows of APPLY (0.8 editing rows: export copies, new files, the
  one-undo UCX rename; 1.1: handoff.export / handoff.import). Any other row answers `needs_human` (owner answers
  06.11.2026: apply only by a button).
* 1.1 handoff Max <-> Blender (mcp-review 3.2 / 3.12): `agr_handoff_export` (file class: a NEW bundle folder),
  `agr_handoff_import` (markup class: only the layer AGENT_<req>; agent.accept stays the button) - both
  preview -> apply in two calls of the same tool (the second with preview_id) - and `agr_handoff_verify` (read).
  «Восстановить материалы» (handoff.restore_materials, undo in place) is an op of agr_op_preview; its apply is the
  panel/dock button (profile modeller, confirmed by a person).
Editing rows of 0.1-0.4 (udim.nudge, atlas.npm, ucx.build, export.checked, export.cleanup) predate the edit contract
and have no bridge route; they are not in the op enum (gap named in docs/plans/agr-mcp.md).
ObjRef ({host, doc, handle, name}, adapters/max/agr_tools/contract_core.py) is accepted as `refs` and returned as
`ref` on each finding of findings_top; the v1 schemas do not change.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

from . import max_pipe
from .max_side import max_bridge
from .preview_store import PreviewStore, current_instance
from .spec import Outcome, Spec

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs" / "plans" / "agr-tools-suite.json"
CONTRACT = ROOT / "adapters" / "max" / "agr_tools" / "contract_core.py"
EDIT_MODES = ("copy", "undo", "file", "agent")
READ_MODES = ("read", "select")
EDIT_CONTRACT_VERSIONS = ("0.8", "0.9")
STAGE_VERSIONS = ("1.0", "1.1")  # versions with rows on the stage rail (roadmap.STAGE_VERSIONS)
HANDOFF_TOOLS = ("agr_handoff_export", "agr_handoff_import", "agr_handoff_verify")
HANDOFF_ROWS = {"agr_handoff_export": "handoff.export", "agr_handoff_import": "handoff.import",
                "agr_handoff_verify": "handoff.verify"}
MCP_APPLY_STAGE = ("handoff.export", "handoff.import")  # runtime.MCP_APPLY_100
MAX_TIMEOUT = float(os.environ.get("AGR_MCP_MAX_TIMEOUT", "600"))


def load_plan(path: Path | None = None) -> dict:
    return json.loads(Path(path or PLAN).read_text(encoding="utf-8"))


def _rows(plan: dict) -> list[dict]:
    return plan["rows"]


def released(plan: dict) -> set[str]:
    return {v["version"] for v in plan["versions"] if v.get("status") == "done"}


def tool_name(row_id: str) -> str:
    return "agr_" + row_id.replace(".", "_")


def stage_rows(plan: dict) -> list[dict]:
    """The new 1.0 stage buttons in stage order (stage, then its row order)."""
    blocks = {b["id"] for b in plan["blocks"]}
    order = {}
    for st in sorted(plan["stages"], key=lambda s: s["order"]):
        for r in st["rows"]:
            order.setdefault(r, (st["order"], len(order)))
    rows = [r for r in _rows(plan) if r["version"] == "1.0" and r["fate"] == "stage" and r["mcp"] == "yes"
            and r["id"].split(".", 1)[0] not in blocks]
    return sorted(rows, key=lambda r: order.get(r["id"], (99, 0)))


def check_ids(plan: dict) -> list[str]:
    rel = released(plan)
    return [r["id"] for r in _rows(plan) if r["mcp"] == "yes" and r["mode"] in READ_MODES
            and (r["version"] in rel or (r["version"] in STAGE_VERSIONS and r["fate"] == "stage"))]


def op_ids(plan: dict) -> list[str]:
    rel = released(plan)
    stage = {r["id"] for r in stage_rows(plan)}
    return [r["id"] for r in _rows(plan) if r["mcp"] == "yes" and r["mode"] in EDIT_MODES and r["id"] not in stage
            and ((r["version"] in rel and r["version"] in EDIT_CONTRACT_VERSIONS)
                 or (r["version"] in STAGE_VERSIONS and r["fate"] == "stage"))]


def apply_ids(plan: dict) -> list[str]:
    return [r["id"] for r in _rows(plan) if r["mcp"] == "yes" and r["mode"] in EDIT_MODES
            and (r["version"] == "0.8" or r["id"] in MCP_APPLY_STAGE)]


def check_routes(plan: dict) -> None:
    """Every row the catalogue offers has a bridge route of the right kind; else the build fails."""
    missing = [r for r in check_ids(plan) if r not in max_bridge.READ_ROWS]
    missing += [r for r in op_ids(plan) + [x["id"] for x in stage_rows(plan)] if r not in max_bridge.EDIT_ROWS]
    missing += [r for r in apply_ids(plan) if r not in max_bridge.APPLY_OVER_MCP]
    if missing:
        raise RuntimeError("plan rows without a bridge route: " + ", ".join(missing))


# ---- ObjRef ------------------------------------------------------------------------------------------------------
def contract():
    key = "agr_mcp_contract_core"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, CONTRACT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules[key] = mod
    return sys.modules[key]


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def targets(args: dict) -> dict:
    """Bridge arguments from scene + exactly one of handles / scope / refs (refs -> handles, doc -> scene)."""
    sources = [k for k in ("handles", "scope", "refs") if args.get(k)]
    if len(sources) > 1:
        raise ValueError("target_conflict: pass exactly one of handles, scope, refs (got {})".format(sources))
    out = {"scene": args["scene"]}
    if args.get("refs"):
        cc = contract()
        refs = []
        for ref in args["refs"]:
            try:
                refs.append(cc.check_ref(ref))
            except ValueError as exc:
                raise ValueError("invalid input: " + str(exc)) from None
        hosts = {r["host"] for r in refs}
        if hosts != {"max"}:
            raise ValueError("target_conflict: ObjRef host {} cannot be served by the Max bridge".format(sorted(hosts)))
        docs = {r["doc"] for r in refs}
        if len(docs) > 1:
            raise ValueError("target_conflict: refs of several documents {}".format(sorted(docs)))
        doc = docs.pop()
        if doc != "untitled":
            if args["scene"] == "live":
                out["scene"] = doc  # the bridge then refuses another open document (scene_mismatch)
            elif _norm(args["scene"]) != _norm(doc):
                raise ValueError("scene_mismatch: refs are of {}, scene is {}".format(doc, args["scene"]))
        handles = [r["handle"] for r in refs]
        if len(set(handles)) != len(handles):
            raise ValueError("invalid input: duplicate ObjRef handle")
        out["handles"] = handles
    elif args.get("scope"):
        out["scope"] = args["scope"]
    elif args.get("handles"):
        out["handles"] = list(args["handles"])
    else:
        raise ValueError("handles_required: pass handles, refs or scope=selection; an empty target set would take "
                         "the user's selection or all geometry")
    return out


# ---- schemas -----------------------------------------------------------------------------------------------------
REF = {"type": "object", "required": ["host", "doc", "handle", "name"], "additionalProperties": False,
       "properties": {"host": {"enum": ["max", "blender", "offline"]}, "doc": {"type": "string", "minLength": 1},
                      "handle": {"type": "integer", "minimum": 1}, "name": {"type": "string"}}}
TARGET = {"scene": {"type": "string", "minLength": 1,
                    "description": "'live' (the pinned open Max document) or its exact path"},
          "handles": {"type": "array", "uniqueItems": True, "items": {"type": "integer", "minimum": 1},
                      "description": "node handles; exactly one of handles / refs / scope"},
          "refs": {"type": "array", "items": REF,
                   "description": "ObjRef {host:'max', doc, handle, name}; doc must be the open document"},
          "scope": {"enum": ["selection"], "description": "the current Max selection, taken explicitly"},
          "options": {"type": "object", "description": "row options (paths, profile); recorded in the preview"}}
REPORT = {"type": "object"}  # the runtime's edit report (edit_core contract) or {checks: {row: report}}


def _input(extra: dict, required: list[str]) -> dict:
    return {"type": "object", "required": ["scene"] + required, "additionalProperties": False,
            "properties": dict(TARGET, **extra)}


# ---- handlers ----------------------------------------------------------------------------------------------------
def _meta(payload: dict, **more) -> dict:
    meta = {k: payload.get(k) for k in ("runtime_version", "runtime_file", "doc", "selection", "journaled",
                                        "journaled_rows")}
    meta.update(more)
    return meta


class Catalogue:
    """v2 handlers sharing one preview store and Max transport."""

    def __init__(self, plan: dict, store: PreviewStore, transport=None):
        self.plan, self.store, self.transport = plan, store, transport
        self.labels = {r["id"]: r.get("label_ru") or r["id"] for r in _rows(plan)}
        self.apply = frozenset(apply_ids(plan))

    def bridge(self, tool: str, args: dict) -> dict:
        return max_pipe.call_bridge(tool, args, MAX_TIMEOUT, transport=self.transport)

    def preview(self, row: str, args: dict) -> Outcome:
        bargs = targets(args)
        bargs["op"] = row
        if args.get("options") is not None:
            bargs["options"] = args["options"]
        payload = self.bridge("agr_op_preview", bargs)
        report = payload["result"]
        meta = _meta(payload, row=row, mode="preview")
        plan = report.get("plan") if isinstance(report, dict) else None
        if isinstance(report, dict) and report.get("status") == "not_implemented":
            meta["next_actions"] = ["not_implemented: {} is a stub until its branch lands (#1024)".format(row)]
        elif isinstance(plan, dict) and plan.get("hash"):
            binding = {"host": "max-live", "instance": current_instance(), "doc": payload.get("doc"),
                       "runtime_version": payload.get("runtime_version"), "state_hash": plan.get("state_hash"),
                       "op": row}
            keep = {k: bargs[k] for k in ("scene", "handles", "scope") if k in bargs}
            pid = self.store.put(report, binding, keep)
            meta["preview_id"] = pid
            if row in HANDOFF_ROWS.values():
                meta["next_actions"] = ["{}(scene, preview_id='{}') applies it".format(
                    {v: k for k, v in HANDOFF_ROWS.items()}[row], pid)]
            elif row in self.apply:
                meta["next_actions"] = ["agr_op_apply(preview_id='{}')".format(pid)]
            else:
                meta["next_actions"] = ["needs_human: ask the user to apply '{}' ({}) with its button in the AGR "
                                        "Tools panel/dock".format(row, self.labels.get(row, row))]
        return Outcome(report, meta)

    def op_preview(self, args: dict) -> Outcome:
        return self.preview(args["op"], args)

    def handoff(self, tool: str, args: dict) -> Outcome:
        """agr_handoff_export / agr_handoff_import: without preview_id a preview (nothing written; the answer holds
        preview_id), with preview_id the apply of that held preview. agr_handoff_verify: read only."""
        row = HANDOFF_ROWS[tool]
        if args.get("preview_id"):
            if tool == "agr_handoff_verify":
                raise ValueError("invalid input: agr_handoff_verify is read-only, it takes no preview_id")
            held = self.store.get(args["preview_id"], {})
            if held.binding.get("op") != row:
                raise ValueError("stale_preview: preview {} is of {}, not {}".format(
                    args["preview_id"], held.binding.get("op"), row))
            out = self.op_apply({"preview_id": args["preview_id"], "idempotency_key": args.get("idempotency_key")})
            if row == "handoff.import":
                out.meta["next_actions"] = ["needs_human: the user accepts the layer with the button agent.accept "
                                            "(Приём от агента) and options.request = plan.request of this answer"]
            return out
        opts = {k: args[k] for k in HANDOFF_OPTIONS[tool] if args.get(k) is not None}
        opts.update(args.get("options") or {})
        call = dict(args, options=opts or None)
        if not any(call.get(k) for k in ("handles", "scope", "refs")):
            if tool == "agr_handoff_export":
                raise ValueError("handles_required: agr_handoff_export sends the given objects; pass handles, refs "
                                 "or scope=selection")
            bargs = {"scene": call["scene"], "op": row}
            if call.get("options"):
                bargs["options"] = call["options"]
            return self._preview_with(row, bargs, call)
        return self.preview(row, call) if tool != "agr_handoff_verify" else self.check_one(row, call)

    def _preview_with(self, row: str, bargs: dict, args: dict) -> Outcome:
        if row == "handoff.verify":
            bargs = dict(bargs, check_ids=[row])
            bargs.pop("op", None)
            payload = self.bridge("agr_check_run", bargs)
            return Outcome(payload["result"]["checks"][row], _meta(payload, row=row, mode="check"))
        payload = self.bridge("agr_op_preview", bargs)
        return self._held(row, payload, bargs)

    def check_one(self, row: str, args: dict) -> Outcome:
        bargs = targets(args)
        bargs["check_ids"] = [row]
        if args.get("options") is not None:
            bargs["options"] = args["options"]
        payload = self.bridge("agr_check_run", bargs)
        return Outcome(payload["result"]["checks"][row], _meta(payload, row=row, mode="check"))

    def _held(self, row: str, payload: dict, bargs: dict) -> Outcome:
        report = payload["result"]
        meta = _meta(payload, row=row, mode="preview")
        plan = report.get("plan") if isinstance(report, dict) else None
        if isinstance(plan, dict) and plan.get("hash"):
            binding = {"host": "max-live", "instance": current_instance(), "doc": payload.get("doc"),
                       "runtime_version": payload.get("runtime_version"), "state_hash": plan.get("state_hash"),
                       "op": row}
            keep = {k: bargs[k] for k in ("scene", "handles", "scope") if k in bargs}
            pid = self.store.put(report, binding, keep)
            meta["preview_id"] = pid
            meta["next_actions"] = ["{}(scene, preview_id='{}') applies it".format(
                {v: k for k, v in HANDOFF_ROWS.items()}[row], pid)]
        return Outcome(report, meta)

    def check_run(self, args: dict) -> Outcome:
        bargs = targets(args)
        bargs["check_ids"] = list(args["check_ids"])
        if args.get("options") is not None:
            bargs["options"] = args["options"]
        payload = self.bridge("agr_check_run", bargs)
        return Outcome(payload["result"], _meta(payload, mode="check"))

    def op_apply(self, args: dict) -> Outcome:
        pid, key = args["preview_id"], args.get("idempotency_key")
        done = self.store.replay(key, pid)
        if done is not None:
            return Outcome(done.result, dict(done.meta, replay=True))
        held = self.store.get(pid, {})
        row = held.binding["op"]
        if row not in self.apply:
            raise ValueError("needs_human: apply of {} ({}) is confirmed only by a button in the AGR Tools "
                             "panel/dock".format(row, self.labels.get(row, row)))
        held = self.store.get(pid, {"host": "max-live", "instance": current_instance()})
        bargs = dict(held.targets, op=row, preview=held.report,
                     expect={"doc": held.binding["doc"], "runtime_version": held.binding["runtime_version"]})
        payload = self.bridge("agr_op_apply", bargs)
        self.store.mark_applied(pid)
        out = Outcome(payload["result"], _meta(payload, row=row, mode="apply", preview_id=pid))
        self.store.remember(key, pid, out)
        return out


HANDOFF_OPTIONS = {"agr_handoff_export": ("job_dir", "seq"),
                   "agr_handoff_import": ("bundle", "fbx", "request_id"),
                   "agr_handoff_verify": ("bundle", "layer", "blender_readback")}
_HANDOFF_FIELDS = {"job_dir": {"type": "string", "minLength": 1, "description": "project folder jobs/<ID>; default: "
                                                                                 "the folder of the scene passport"},
                   "seq": {"type": "string", "pattern": "^[0-9]{3}$", "description": "bundle number; default next"},
                   "bundle": {"type": "string", "minLength": 1, "description": "bundle folder handoff/<seq>"},
                   "fbx": {"type": "string", "minLength": 1, "description": "FBX from Blender; default model.fbx"},
                   "request_id": {"type": "string", "pattern": "^[A-Za-z0-9-]{1,64}$",
                                  "description": "agent layer AGENT_<request_id>; default bh<seq>"},
                   "layer": {"type": "string", "minLength": 1, "description": "layer to verify (AGENT_<req>)"},
                   "blender_readback": {"type": "string", "minLength": 1,
                                        "description": "readback JSON of the Blender side (optional)"},
                   "preview_id": {"type": "string", "pattern": "^[0-9a-f]{64}$",
                                  "description": "apply the held preview of this tool"},
                   "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 200}}


def _handoff_input(tool: str) -> dict:
    extra = {k: _HANDOFF_FIELDS[k] for k in HANDOFF_OPTIONS[tool]}
    if tool != "agr_handoff_verify":
        extra.update(preview_id=_HANDOFF_FIELDS["preview_id"], idempotency_key=_HANDOFF_FIELDS["idempotency_key"])
    return _input(extra, [])


def _max(_args: dict) -> str:
    return "max-live"


def _timeout(_args: dict) -> float:
    return MAX_TIMEOUT


def specs(plan: dict | None = None, store: PreviewStore | None = None, transport=None) -> list[Spec]:
    plan = plan or load_plan()
    check_routes(plan)
    cat = Catalogue(plan, store or PreviewStore(), transport)
    out = []
    for r in stage_rows(plan):
        row = r["id"]
        out.append(Spec(
            tool_name(row),
            "AGR Tools 1.0 stage button '{}' ({}, stage {}): {}. Over MCP preview only through "
            "runtime.edits_100(actor='mcp'): nothing changes; the answer holds preview_id. Apply is a button in "
            "the AGR Tools panel/dock (agr_op_apply answers needs_human). A stub answers status not_implemented "
            "(#1024).".format(row, r.get("label_ru"), r["stage"], r.get("does_ru")),
            _input({}, []), REPORT, (lambda a, row=row: cat.preview(row, a)), _max, timeout=_timeout, schema=2,
            row=row))
    out.append(Spec(
        "agr_check_run", "Run read/select checks of the AGR Tools plan in the pinned open 3ds Max in one call: "
        "released rows (0.1-0.9) and the 1.0 read rows. Read-only; the selection is restored. Answer: envelope v2 "
        "with findings_top (ref = ObjRef) and result {checks: {row: report}}.",
        _input({"check_ids": {"type": "array", "minItems": 1, "uniqueItems": True,
                              "items": {"enum": check_ids(plan)}}}, ["check_ids"]),
        REPORT, cat.check_run, _max, timeout=_timeout, schema=2))
    out.append(Spec(
        "agr_op_preview", "Preview one editing row of the AGR Tools plan (0.8 / 0.9 / 1.0 small rows) in the pinned "
        "open 3ds Max: nothing changes. The server holds the preview and answers preview_id (bound to host, Max pid, "
        "document, runtime version and plan.state_hash; TTL). next_actions says whether agr_op_apply may apply it "
        "(0.8 rows) or a human must press the button (needs_human).",
        _input({"op": {"enum": op_ids(plan)}}, ["op"]), REPORT, cat.op_preview, _max, timeout=_timeout, schema=2))
    out.append(Spec(
        "agr_op_apply", "Apply a server-held preview by preview_id (+ optional idempotency_key). Only the 0.8 rows "
        "(export copies, new files, UCX rename in one undo record); any other row answers needs_human. A preview "
        "that is unknown, expired, already applied or bound to another Max/document/runtime/scene state answers "
        "stale_preview.",
        {"type": "object", "required": ["preview_id"], "additionalProperties": False,
         "properties": {"preview_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 200}}},
        REPORT, cat.op_apply, _max, read_only=False, destructive=True, timeout=_timeout, schema=2))
    out.append(Spec(
        "agr_handoff_export", "AGR Tools 1.1 handoff Max -> Blender (handoff.export): the given objects -> a NEW "
        "bundle folder jobs/<ID>/handoff/<seq>/ (model.fbx with quads/n-gons, metres, Z up; manifest, sidecar with "
        "roles and OPEN_*/LEVEL_* markers, materials.json, readback_max.json). Without preview_id: preview, nothing "
        "is written, the answer holds preview_id; with preview_id: writes that bundle (never overwrites).",
        _handoff_input("agr_handoff_export"), REPORT, (lambda a: cat.handoff("agr_handoff_export", a)), _max,
        read_only=False, destructive=False, timeout=_timeout, schema=2, row="handoff.export"))
    out.append(Spec(
        "agr_handoff_import", "AGR Tools 1.1 handoff Blender -> Max (handoff.import): the FBX of a bundle -> new "
        "objects ONLY in the layer AGENT_<request_id> (names, user props, matIDs and instances from the manifest) plus "
        "request.json + baseline.json for the gate. Without preview_id: preview; with preview_id: the import. The "
        "transfer to the role layers is the button agent.accept (Приём от агента) in the panel/dock [D213].",
        _handoff_input("agr_handoff_import"), REPORT, (lambda a: cat.handoff("agr_handoff_import", a)), _max,
        read_only=False, destructive=False, timeout=_timeout, schema=2, row="handoff.import"))
    out.append(Spec(
        "agr_handoff_verify", "AGR Tools 1.1 handoff round-trip check (handoff.verify, read-only): objects of a layer "
        "or the given handles vs readback_max.json of the bundle by the table of mcp-review 3.12 (names and roles, "
        "matID <-> slots, UV/UDIM, normals, units, transforms, topology, instances); discrepancies are findings.",
        _handoff_input("agr_handoff_verify"), REPORT, (lambda a: cat.handoff("agr_handoff_verify", a)), _max,
        timeout=_timeout, schema=2, row="handoff.verify"))
    return out
