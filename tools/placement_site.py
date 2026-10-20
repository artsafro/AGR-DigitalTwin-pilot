"""Site placement wrapper: SPOZU points + libraries -> #316 engine -> DCC instance plan -> scene check (#296).

Pattern: none (new-case: DCC instancing wrapper around ``dt_ai.placement.engine``; no second implementation
of pivots, sinking, rotation, scale or bottom-face proof).

Pure Python. The engine computes every instance; this module only
- selects the engine points (boundary + library assignment) and lists every excluded point with its reason;
- builds engine library entries from DCC facts (``tools/blender/placement_instance.py facts``);
- turns the engine report into a scene plan (matrix shifted by the scene origin offset, polygon indices of the
  bottom faces the engine marked ``delete``) and STOPS on any engine failure or error finding;
- compares the scene readback with the engine report (count per library id; pivot, rot_z, scale, matrix per
  instance; deleted polygons) and measures the sinking at every pivot from the scene.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any

from dt_ai.placement import engine

FLORA_BAND_TOL = engine.BAND_TOL     # [D099]
BAND_MARGIN = 1e-4                   # base scale targets just inside the band edge
SINK_TOL_M = 0.01                    # acceptance: 10 cm +- 1 cm


class PlacementStopped(RuntimeError):
    """The engine reported a failure or an error finding: nothing is instanced."""

    def __init__(self, reasons: list[str]):
        super().__init__("placement stopped: " + "; ".join(reasons[:20]) + (" ..." if len(reasons) > 20 else ""))
        self.reasons = reasons


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ----------------------------------------------------------------------------- points
def select_points(points: list[dict], assign: dict[str, str | None]) -> tuple[list[dict], list[dict]]:
    """-> (engine points, excluded). Excluded reasons: ``outside_boundary`` (inside is not True, gate-1 Q2a)
    or ``no_library_model`` (label unassigned or assigned None, gate-1 F1 / #313 Q1-Q5). Nothing is dropped:
    len(engine points) + len(excluded) == len(points)."""
    keep, excl = [], []
    for p in points:
        lab = p.get("label")
        lid = assign.get(lab) if lab in assign else None
        if p.get("inside") is not True:
            excl.append({"handle": p.get("handle"), "label": lab, "library_id": lid, "reason": "outside_boundary"})
        elif lid is None:
            excl.append({"handle": p.get("handle"), "label": lab, "library_id": None, "reason": "no_library_model"})
        else:
            keep.append(dict(p))
    assert len(keep) + len(excl) == len(points)
    return keep, excl


# ----------------------------------------------------------------------------- library entries
def flora_base_scale(model_h: float, sched_h_m: tuple[float, float]) -> float:
    """Uniform base scale bringing the model height into the schedule band +-20 % (model-flora step 4); 1.0
    when already inside. Raises on non-finite or non-positive input."""
    lo, hi = sched_h_m
    if not all(_finite(v) and v > 0 for v in (model_h, lo, hi)) or hi < lo:
        raise ValueError(f"bad height input model={model_h!r} schedule={sched_h_m!r}")
    blo, bhi = (1 - FLORA_BAND_TOL) * lo, (1 + FLORA_BAND_TOL) * hi
    if model_h < blo:
        return blo * (1 + BAND_MARGIN) / model_h
    if model_h > bhi:
        return bhi * (1 - BAND_MARGIN) / model_h
    return 1.0


def flora_entry(lid: str, facts: dict, sched_h_m: tuple[float, float]) -> dict:
    """Engine entry for a Flora object whose facts were measured AFTER the base scale bake. Schedule height =
    model height clamped to the schedule range, so the engine's +-20 % check equals the band
    [0.8 lo, 1.2 hi] of the parts list. The schedule has no crown (gate-1 F3): crown input = model crown
    (neutral for the engine), crown is reported as ``review``."""
    lo, hi = facts["bbox_min"], facts["bbox_max"]
    h = hi[2] - lo[2]
    crown = max(hi[0] - lo[0], hi[1] - lo[1])
    return {"id": lid, "kind": "flora", "bbox_min": lo, "bbox_max": hi,
            "schedule_height_m": min(max(h, sched_h_m[0]), sched_h_m[1]), "schedule_crown_m": crown}


def maf_entry(lid: str, facts: dict, spec_dims_m: list[float] | None) -> dict:
    e = {"id": lid, "kind": "maf", "bbox_min": facts["bbox_min"], "bbox_max": facts["bbox_max"],
         "bottom_faces": [f["points"] for f in facts["bottom_faces"]]}
    if spec_dims_m is not None:
        e["spec_dims_m"] = list(spec_dims_m)
    return e


# ----------------------------------------------------------------------------- plan
def stop_reasons(report: dict) -> list[str]:
    """Every engine failure / error finding; empty only when the run may be instanced."""
    out = [f"failed {f.get('handle')} {f.get('library_id')}: {f.get('code')}" for f in report.get("failed", [])]
    out += [f"finding {f['code']} {f.get('handle')} {f.get('library_id')}: {f.get('detail')}"
            for f in report.get("findings", []) if f.get("severity") == engine.ERROR]
    if report.get("status") not in ("pass", "review"):
        out.append(f"engine status {report.get('status')!r}")
    if not report.get("instances"):
        out.append("no instances")
    return out


def _shift(M: list[list[float]], offset: list[float]) -> list[list[float]]:
    R = [list(map(float, r)) for r in M]
    for i in range(3):
        R[i][3] -= offset[i]
    return R


def make_plan(report: dict, facts: dict[str, dict], offset: list[float]) -> dict:
    """Engine report -> scene plan. Raises PlacementStopped on any failure (fail-closed)."""
    reasons = stop_reasons(report)
    if reasons:
        raise PlacementStopped(reasons)
    if len(offset) != 3 or not all(_finite(v) for v in offset):
        raise PlacementStopped([f"bad origin offset {offset!r}"])
    out = []
    for it in report["instances"]:
        lid = it["library_id"]
        if lid not in facts:
            raise PlacementStopped([f"no DCC facts for library id {lid}"])
        dele = []
        for v in it.get("bottom_faces", []):
            if v["action"] == "delete":
                dele.append(facts[lid]["bottom_faces"][v["face"]]["index"])
        out.append({"name": f"{lid}__{it['handle']}", "handle": it["handle"], "library_id": lid,
                    "matrix": _shift(it["matrix"], offset),
                    "scene_pivot": [it["pivot_x"] - offset[0], it["pivot_y"] - offset[1], it["pivot_z"] - offset[2]],
                    "delete_polygons": sorted(dele)})
    return {"seed": report["seed"], "engine_schema": report["schema"], "offset": list(offset), "instances": out}


def report_sha256(report: dict) -> str:
    return hashlib.sha256(engine.report_json(report).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------- scene check
def _apply(M, p):
    return [sum(M[i][j] * p[j] for j in range(3)) + M[i][3] for i in range(3)]


def decompose(M: list[list[float]]) -> tuple[float, float]:
    """-> (rot_z_deg in [0, 360), uniform scale) of a Z-rotation x uniform-scale matrix."""
    s = math.hypot(M[0][0], M[1][0])
    rot = math.degrees(math.atan2(M[1][0], M[0][0])) % 360.0
    return rot, s


def compare_scene(report: dict, readback: dict, facts: dict[str, dict], offset: list[float],
                  tol: float = 1e-4) -> list[str]:
    """Mismatches between engine output and the scene; [] when the scene equals the engine output."""
    bad: list[str] = []
    eng = {i["handle"]: i for i in report["instances"]}
    scn: dict[str, dict] = {}
    for r in readback.get("instances", []):
        if r["handle"] in scn:
            bad.append(f"duplicate scene instance {r['handle']}")
        scn[r["handle"]] = r
    ce = Counter(i["library_id"] for i in report["instances"])
    cs = Counter(r["library_id"] for r in readback.get("instances", []))
    for lid in sorted(set(ce) | set(cs)):
        if ce[lid] != cs[lid]:
            bad.append(f"count {lid}: engine {ce[lid]} scene {cs[lid]}")
    if readback.get("seed") != report.get("seed"):
        bad.append(f"seed: engine {report.get('seed')} scene {readback.get('seed')}")
    for h in sorted(set(eng) - set(scn)):
        bad.append(f"missing in scene {h}")
    for h in sorted(set(scn) - set(eng)):
        bad.append(f"extra in scene {h}")
    for h in sorted(set(eng) & set(scn)):
        e, r = eng[h], scn[h]
        if e["library_id"] != r["library_id"]:
            bad.append(f"{h}: library {e['library_id']} vs {r['library_id']}")
            continue
        M = r["matrix"]
        if not all(_finite(v) for row in M for v in row):
            bad.append(f"{h}: non-finite scene matrix")
            continue
        piv = _apply(M, e["anchor_local"])
        want = [e["pivot_x"] - offset[0], e["pivot_y"] - offset[1], e["pivot_z"] - offset[2]]
        if max(abs(a - b) for a, b in zip(piv, want)) > tol:
            bad.append(f"{h}: pivot {piv} vs {want}")
        rot, s = decompose(M)
        d = abs((rot - e["rot_z_deg"] + 180.0) % 360.0 - 180.0)
        if d > 1e-3:
            bad.append(f"{h}: rot_z {rot} vs {e['rot_z_deg']}")
        if abs(s - e["scale"]) > 1e-6 or abs(M[2][2] - e["scale"]) > 1e-6:
            bad.append(f"{h}: scale {s}/{M[2][2]} vs {e['scale']}")
        W = _shift(e["matrix"], offset)
        if max(abs(M[i][j] - W[i][j]) for i in range(4) for j in range(4)) > tol:
            bad.append(f"{h}: matrix differs")
        lib_polys = readback.get("library_polygons", {}).get(e["library_id"])
        n_del = sum(v["action"] == "delete" for v in e.get("bottom_faces", []))
        if lib_polys is not None and r.get("polygons") != lib_polys - n_del:
            bad.append(f"{h}: polygons {r.get('polygons')} vs {lib_polys} - {n_del} deleted")
    return bad


def sinking(readback: dict, target: float = engine.SINK_M, tol: float = SINK_TOL_M,
            kind_of: dict[str, str] | None = None) -> dict:
    """Sinking measured in the scene at every pivot: Ground z under the pivot (ray) - lowest instance z.
    A missing / non-finite measurement counts as out of tolerance (fail-closed)."""
    per: dict[str, list[float]] = {}
    bad = []
    for r in readback.get("instances", []):
        g, low = r.get("ground_z_at_pivot"), r.get("lowest_z")
        k = (kind_of or {}).get(r["library_id"], "all")
        if not (_finite(g) and _finite(low)):
            bad.append({"handle": r["handle"], "library_id": r["library_id"], "sink_m": None})
            continue
        s = g - low
        per.setdefault(k, []).append(s)
        if abs(s - target) > tol:
            bad.append({"handle": r["handle"], "library_id": r["library_id"], "sink_m": s})
    n = len(readback.get("instances", []))
    return {"n": n, "measured": sum(len(v) for v in per.values()),
            "per_kind": {k: {"n": len(v), "min_m": min(v), "max_m": max(v)} for k, v in sorted(per.items())},
            "out_of_tol": bad, "ok": n > 0 and not bad}


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
