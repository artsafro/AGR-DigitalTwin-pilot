"""Quad master (work FBX) checks from a Blender readback: DER-03, [D021], [D198].

Generalises the quad and quad-size part of the job-local `jobs/KPP1/scripts/qa_master.py`:
- master quads: every polygon of every non-UCX mesh has 4 corners (the master stays quad; only the derived
  export copy is triangulated; DER-03, reg p.8 §3.11, p.29 §3.17);
- master quad size (VPM only): no face side longer than one 4096 px tile at 1024 px/m = 4.0 m, faces between
  the padded side 3.9375 m and 4.0 m are `review` ([D021] "cut VPM quads to about 4 x 4 m"). The limits come from
  `dt_ai.ops.inv_texel.VPM` (the kernel invariant texel_ready), never typed in here; its aspect ratio
  default (orchestrator default, no decision) is not applied. Degenerate faces fail: they cannot be unwrapped.
NPM has no size gate (inv_texel NPM-OKS is report-only); only the quad rule applies.
Findings go to stage V003 (DER-03 is listed there). Pure Python + numpy, no Blender.
"""
from twinqa.report import Finding, signed_margin

PAGES = [8, 29]
EVIDENCE = "DER-03, [D021], dt_ai.ops.inv_texel"


def _f(status, name, observed, expected, src, data=None):
    return Finding(name, status, observed, expected, list(PAGES), f"{src}; {EVIDENCE}", [], data=dict(data or {}))


def master_findings(rb: dict, kind: str) -> list[Finding]:
    """V003 findings for a master/work FBX readback (tools/blender/fbx_readback.py format)."""
    from dt_ai.ops.inv_texel import VPM, face_metrics
    import numpy as np

    src = rb.get("source", "master.fbx").replace("\\", "/").rsplit("/", 1)[-1]
    if not rb.get("readback_ok"):
        return [_f("fail", "master quads", f"{src}: {rb.get('error', 'readback failed')}",
                   "readable quad master FBX", src)]
    meshes = [m for m in rb.get("meshes", []) if not m["name"].upper().startswith("UCX_")]
    if not meshes:
        return [_f("fail", "master quads", f"{src}: no render mesh", "quad master meshes", src)]
    non_quads = {}
    for m in meshes:
        degrees = {int(k): v for k, v in (m.get("polygon_degrees") or {}).items()}
        bad = sum(v for k, v in degrees.items() if k != 4)
        if bad or not degrees:
            non_quads[m["name"]] = bad if degrees else "no polygons"
    out = [_f("fail" if non_quads else "pass", "master quads",
              f"{src}: {dict(list(non_quads.items())[:5]) or 'all quads'}", "every master polygon is a quad", src,
              {"non_quads": non_quads})]
    if kind != "vpm":
        return out
    hard, soft = VPM.hard_side_m, VPM.review_side_m
    over, review, degenerate, missing, longest = [], [], [], [], 0.0
    for m in meshes:
        shape = m.get("face_geometry") or {}
        verts, polys = shape.get("vertices"), shape.get("polygons")
        if not isinstance(verts, list) or not isinstance(polys, list):
            missing.append(m["name"])
            continue
        v = np.asarray(verts, dtype=float)
        for i, poly in enumerate(polys):
            metrics = face_metrics(v[list(poly)])
            tag = f"{m['name']}#{i}"
            if metrics.degenerate:
                degenerate.append(tag)
                continue
            longest = max(longest, metrics.max_edge_m)
            if metrics.max_edge_m > hard:
                over.append(f"{tag} {metrics.max_edge_m:.3f} m")
            elif metrics.max_edge_m > soft:
                review.append(f"{tag} {metrics.max_edge_m:.3f} m")
    if missing:
        out.append(_f("not_run", "master quad size", f"{src}: no face geometry for {missing[:5]}",
                      f"face side <= {hard:g} m", src))
        return out
    status = "fail" if over or degenerate else "review" if review else "pass"
    shown = (over or degenerate or review)[:5]
    observed = (f"{src}: {len(over)} face(s) > {hard:g} m, {len(degenerate)} degenerate, {len(review)} in "
                f"({soft:g}, {hard:g}] m; longest {longest:.3f} m" + (f"; e.g. {shown}" if shown else ""))
    out.append(Finding("master quad size", status, observed, f"face side <= {hard:g} m (review above {soft:g} m)",
                       list(PAGES), f"{src}; {EVIDENCE}", [], longest, hard, signed_margin(longest, hard, "max"),
                       {"over": over, "degenerate": degenerate, "review": review}))
    return out
