"""Per-band diff of a cached z0-snapped contour set against the shipped ``contours.snap_band_z0`` (#880).

Pattern: new-case: explain a cached snapped-contours file against the shipped z0 snap (report only, no writer change).

The cached TOW02 file ``snapped_contours.json`` (SHA-256 ``21bbc3e2...``, evidence
``G:/Мой диск/AGR-evidence/t_ad9bc345-body-gn-z0-snap/``) was written by the scratch probe
``C:/x/t_ad9bc345/snap.py`` (SHA-256 ``419f86fd...``), not by any revision of ``snap_band_z0``. That probe read
each lower band's top z in Blender (face-domain extrude) on the UNSNAPPED contours, in one pass, and skipped an
upper band when the lower top had more than one float32 z. The shipped function computes the point-domain top
``f32(f32(z0) + f32(z1 - z0))`` and walks the bands lower-first, so a snapped lower z0 feeds the upper band.

Each band gets one reason:

- ``equal``: cached z0 is the shipped z0.
- ``probe_kept_nominal``: cached z0 is the source z0; the shipped snap moved it (the probe skipped the band).
- ``probe_single_pass``: cached z0 is the point-domain top of the lower band's SOURCE z0, while the shipped
  snap moved that lower z0 first.
- ``unexplained``: none of the above.

Parent ids, z1, polygons and vertex counts must be equal in all three sets; a difference there, a band-count
mismatch or a non-finite z0 raises ValueError naming the band. CLI exit codes: 0 every difference explained,
3 an ``unexplained`` band (report still written), 2 usage, 4 refused output path, 5 invalid input (nothing written).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _contours_module():
    spec = importlib.util.spec_from_file_location("body_contours_for_snap_diff", HERE / "contours.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _vertex_count(band: dict) -> int:
    return sum(len(p["exterior"]) + sum(len(h) for h in p["holes"]) for p in band.get("polygons", []))


def _finite(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{where} is not a finite number: {value!r}")
    return float(value)


def diff_snapped(source: dict, cached: dict) -> dict:
    """Diff ``cached`` (a snapped copy of ``source``) against ``snap_band_z0(source)``, band by band."""
    mod = _contours_module()
    shipped = mod.snap_band_z0(source)  # ValueError on empty / non-finite source bands
    if not isinstance(cached, dict) or not isinstance(cached.get("bands"), list):
        raise ValueError("cached contours have no bands list")
    src_b, cac_b, shp_b = source["bands"], cached["bands"], shipped["bands"]
    if len(cac_b) != len(src_b):
        raise ValueError(f"band count differs: source {len(src_b)}, cached {len(cac_b)}")
    parents = mod._snap_parents(src_b)
    rows = []
    for i, (s, c, p) in enumerate(zip(src_b, cac_b, shp_b)):
        if not isinstance(c, dict):
            raise ValueError(f"cached band {i} is not an object")
        c_z0 = _finite(c.get("z0"), f"cached band {i} z0")
        _finite(c.get("z1"), f"cached band {i} z1")
        if float(c["z1"]) != float(s["z1"]):
            raise ValueError(f"band {i}: z1 differs (source {s['z1']!r}, cached {c['z1']!r})")
        if c.get("polygons") != s.get("polygons"):
            raise ValueError(f"band {i}: polygons differ between source and cached")
        s_z0, p_z0 = float(s["z0"]), float(p["z0"])
        parent = parents.get(i)
        # the cached snap must not change which band is the single lower one: compare against the source parents
        lowers = [j for j, b in enumerate(cac_b) if j != i and float(b["z1"]) == float(s["z0"])]
        if parent is not None and lowers != [parent]:
            raise ValueError(f"band {i}: parent differs (shipped {parent}, cached lowers {lowers})")
        if c_z0 == p_z0:
            reason = "equal"
        elif parent is None:
            reason = "unexplained"
        elif c_z0 == s_z0:
            reason = "probe_kept_nominal"
        elif (c_z0 == mod._point_domain_top(float(src_b[parent]["z0"]), float(src_b[parent]["z1"]))
              and float(shp_b[parent]["z0"]) != float(src_b[parent]["z0"])):
            reason = "probe_single_pass"
        else:
            reason = "unexplained"
        rows.append({"band": i, "parent": parent, "z1": float(s["z1"]),
                     "vertices": _vertex_count(s), "source_z0": s_z0, "cached_z0": c_z0, "shipped_z0": p_z0,
                     "cached_z0_hex": c_z0.hex(), "shipped_z0_hex": p_z0.hex(), "reason": reason})
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["reason"]] = counts.get(r["reason"], 0) + 1
    return {"schema": "body-snap-diff/1", "bands": rows, "counts": counts,
            "differing_bands": [r["band"] for r in rows if r["reason"] != "equal"],
            "unexplained": [r["band"] for r in rows if r["reason"] == "unexplained"]}


def main(argv=None) -> int:
    sys.path.insert(0, str(HERE.parent))
    from safe_write import Refused, guard_cli, publish_text, same_file

    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print("usage: snap_diff.py <source contours .json> <cached snapped .json> <report .json>", file=sys.stderr)
        return 2
    src, cac, out = (Path(a) for a in argv)
    try:
        if same_file(src, cac):
            raise Refused(f"source and cached are the same file: {src} and {cac}; nothing written")
        guard_cli([src, cac], [out])
    except Refused as exc:
        print(f"SNAP_DIFF refused: {exc}", file=sys.stderr)
        return 4
    try:
        report = diff_snapped(json.loads(src.read_text(encoding="utf-8")), json.loads(cac.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"SNAP_DIFF invalid input: {exc!r}", file=sys.stderr)
        return 5
    publish_text(out, json.dumps(report, indent=1))
    print(json.dumps({"counts": report["counts"], "differing_bands": report["differing_bands"],
                      "unexplained": report["unexplained"]}))
    return 3 if report["unexplained"] else 0


if __name__ == "__main__":
    sys.exit(main())
