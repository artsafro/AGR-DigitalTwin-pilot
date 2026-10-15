"""Flora checks on a Ground FBX readback (tools/blender/fbx_readback.py), merged by twinqa.scene.

Pattern: none — delivery validator findings for Flora (REVIEW_CHECKLIST Q1: new-case).

- V015 "Flora dimensions" (both profiles): per placed plant with an expected height / crown diameter
  from the planting schedule, fail when the readback bounding box differs by more than 20 % [D099];
  the bbox height includes the 10 cm the plant sinks into the Ground [D100], so 0.10 m is subtracted.
  Crown diameter = the larger horizontal bbox side (world axes; a non-round crown rotated about Z
  reads larger than its true diameter, up to x1.41 for a square).
- V005 "Flora maps" (NPM): every Flora material carries the diffuse map and a separate opacity map,
  no other map (reg p.10 §5.13 "exclusively"). A diffuse alpha channel wired to Alpha fails
  (reg p.9 §5.5, [D020]); other maps or no diffuse fail. A missing opacity map is `review` with
  conflict 18 (open: regulation "if needed" vs the project star technique that always uses it).
- V003 "Flora triangle share" (NPM): Flora triangles vs the project share, default 70 000, and the
  Ground total vs the regulation 180 000 (reg p.7 §3.6, split [D097]). The share is a planning
  target: above it -> review, never fail; the Ground total keeps its own V003 "triangle count" fail.

Flora meshes and materials are recognised by the `Flora` name token (`SM_{Address}_Flora`,
`M_{Address}_Flora_1`, reg p.12-13), Blender duplicate suffixes `.001` tolerated: an exact schedule
name always wins; a sole `.001` alias is used only when the exact mesh is absent (several -> review).
V005 also fails every Flora mesh with no material or an empty slot, independent of its neighbours.
"""
import re

from twinqa.report import Finding

DIM_TOL, SINK_M, FLORA_SHARE, EPS = 0.20, 0.10, 70_000, 1e-9
FLORA_TOKEN = re.compile(r"(?:^|_)Flora(?:_|$)")
DIFFUSE, OPACITY = "Base Color", "Alpha"


def _base(name: str) -> str:
    return re.sub(r"\.\d{3}$", "", name or "")


def is_flora(name: str | None) -> bool:
    return bool(name) and bool(FLORA_TOKEN.search(_base(name)))


def _f(status, name, observed, expected, pages, evidence, conflicts=()):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts))


def deviation(measured: float, expected: float) -> float:
    return abs(measured / expected - 1)


def plant_size(bounds) -> tuple[float, float]:
    """(height above the Ground, crown diameter) from world bounds; height minus the 10 cm sinking."""
    lo, hi = bounds
    return (hi[2] - lo[2]) - SINK_M, max(hi[0] - lo[0], hi[1] - lo[1])


def dimension_findings(meshes: list[dict], schedule: dict | None, src: str) -> list[Finding]:
    """schedule: {mesh name: {"height_m": h, "crown_m": d}} for each placed plant."""
    if schedule is None:
        if any(is_flora(m["name"]) for m in meshes):
            return [_f("not_run", "Flora dimensions", f"{src}: no planting schedule supplied",
                       "height and crown within 20 % of the schedule [D099]", [4, 24], src)]
        return []
    exact, aliases = {}, {}
    for m in meshes:
        exact.setdefault(m["name"], m)
        if _base(m["name"]) != m["name"]:
            aliases.setdefault(_base(m["name"]), []).append(m)
    out = []
    for plant, want in sorted(schedule.items()):
        name = f"Flora dimensions: {plant}"
        expected_h, expected_d = want.get("height_m"), want.get("crown_m")
        if not all(isinstance(v, (int, float)) and v > 0 for v in (expected_h, expected_d)):
            out.append(_f("review", name, f"{src}: schedule entry {want}", "height_m > 0 and crown_m > 0",
                          [4, 24], src))
            continue
        # exact name first; a Blender `.001` alias only when it is the sole candidate
        candidates = [exact[plant]] if plant in exact else aliases.get(plant, [])
        if len(candidates) > 1:
            out.append(_f("review", name, f"{src}: no mesh named {plant}; ambiguous aliases "
                          f"{sorted(c['name'] for c in candidates)}", "one mesh per placed plant in the checked FBX",
                          [4, 24], src))
            continue
        mesh = candidates[0] if candidates else None
        if mesh is None or not mesh.get("bounds_m"):
            out.append(_f("review", name, f"{src}: no mesh named {plant} with bounds",
                          "one mesh per placed plant in the checked FBX", [4, 24], src))
            continue
        h, d = plant_size(mesh["bounds_m"])
        dh, dd = deviation(h, expected_h), deviation(d, expected_d)
        bad = dh > DIM_TOL + EPS or dd > DIM_TOL + EPS
        out.append(_f("fail" if bad else "pass", name,
                      f"{src}: height {h:.3f} m ({(h / expected_h - 1) * 100:+.1f} %), "
                      f"crown {d:.3f} m ({(d / expected_d - 1) * 100:+.1f} %); "
                      f"bbox height minus {SINK_M} m sinking",
                      f"height {expected_h} m, crown {expected_d} m, each within 20 % [D099, D100]", [4, 24], src))
    return out


def map_findings(rb: dict, flora_meshes: list[dict], src: str) -> list[Finding]:
    """NPM: each Flora material = diffuse (Base Color) + separate opacity (Alpha), nothing else."""
    names = {n for m in flora_meshes for n in m.get("materials", []) if n}
    facts = rb.get("materials")
    if facts is None:
        if not flora_meshes:
            return []
        return [_f("not_run", "Flora maps", f"{src}: readback has no material map facts",
                   "diffuse + opacity map only (reg p.10 §5.13)", [9, 10], src)]
    materials = [m for m in facts if m["name"] in names or is_flora(m["name"])]
    out = []
    # coverage per Flora mesh: a good neighbour must not hide a plant with no / empty material slots
    for m in sorted(flora_meshes, key=lambda m: m["name"]):
        slots = m.get("materials") or []
        if not slots or not all(slots):
            out.append(_f("fail", f"Flora maps: {m['name']}",
                          f"{src}: {m['name']} has no material in {'all slots' if not any(slots) else 'some slots'} "
                          f"({slots})", "every Flora mesh slot carries a diffuse + opacity material "
                          "(reg p.10 §5.13)", [9, 10], src))
    for mat in sorted(materials, key=lambda m: m["name"]):
        maps = mat.get("maps", [])
        diffuse = {m["image"] for m in maps if m["socket"] == DIFFUSE}
        opacity = {m["image"] for m in maps if m["socket"] == OPACITY}
        other = sorted({m["socket"] for m in maps if m["socket"] not in (DIFFUSE, OPACITY)})
        separate, alpha_channel = opacity - diffuse, opacity & diffuse
        fails = (["no diffuse map"] if not diffuse else []) + (["diffuse alpha channel wired to Alpha"]
                                                                 if alpha_channel else [])
        fails += [f"other maps on {other}"] if other else []
        missing = [] if separate else ["no separate opacity map"]
        # C18 open: the regulation says opacity "if needed"; the project star technique always uses it
        status = "fail" if fails else "review" if missing else "pass"
        out.append(_f(status, f"Flora maps: {mat['name']}",
                      f"{src}: {'; '.join(fails + missing) or 'diffuse + opacity'}",
                      "diffuse map + separate opacity map only (reg p.10 §5.13; no alpha in NPM images, "
                      "reg p.9 §5.5 [D020])", [9, 10], src, [18] if missing else []))
    return out


def budget_finding(meshes: list[dict], ground_total: int, ground_limit: int, share: int, src: str) -> Finding:
    flora = sum(m["triangles"] for m in meshes if is_flora(m["name"]))
    over_ground = "over" if ground_total > ground_limit else "within"
    return _f("review" if flora > share else "pass", "Flora triangle share",
              f"{src}: Flora {flora} of share {share}; Ground total {ground_total} of {ground_limit} ({over_ground})",
              f"Flora <= {share} project share [D097] (planning target); Ground total <= {ground_limit} "
              f"(reg p.7 §3.6, V003 triangle count)", [7], src)


def flora_findings(rb: dict, kind: str, meshes: list[dict], ground_total: int, profile: dict,
                   schedule: dict | None = None, share: int = FLORA_SHARE) -> dict[str, list[Finding]]:
    """Ground FBX only (the caller passes role='ground' readbacks); UCX meshes already removed."""
    src = rb["source"].replace("\\", "/").rsplit("/", 1)[-1]
    out = {"V015": dimension_findings(meshes, schedule, src), "V005": [], "V003": []}
    if kind == "npm":
        flora = [m for m in meshes if is_flora(m["name"])]
        out["V005"] = map_findings(rb, flora, src)
        out["V003"] = [budget_finding(meshes, ground_total, profile["geometry"]["ground_triangles_total_max"],
                                      share, src)]
    return {k: v for k, v in out.items() if v}
