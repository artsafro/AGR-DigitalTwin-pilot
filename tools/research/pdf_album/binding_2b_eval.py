"""new-case: source-DWG DIMENSION oracle and one-to-one semantic-binding scoring (#1254).

Read-only research comparator, not a calibration or delivery certificate. Grid labels
are manually transcribed from the independent DWG and bound to entity handles in
its native DXFOUT. All modelspace DIMENSION entities remain in the denominator,
including ones the binder cannot bind. No positive prediction is silently excluded.
CLI prints JSON to stdout only; it never opens any input path for writing.

Usage: uv run --extra pdf-review --with ezdxf python -m
 tools.research.pdf_album.binding_2b_eval source.dxf grids.json plotted.pdf
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def dimension_oracle(dxf: Path, grids: list[dict]) -> dict:
    """Read actual dimensions and match projected extension ends to source axes."""
    import ezdxf

    source_sha = hashlib.sha256(dxf.read_bytes()).hexdigest()
    doc = ezdxf.readfile(dxf)
    if hashlib.sha256(dxf.read_bytes()).hexdigest() != source_sha:
        raise ValueError("DXF source changed while extracting oracle")
    axes = []
    seen = set()
    for grid in grids:
        label = grid["label"]
        orientation = grid["orientation"]
        if label in seen or orientation not in ("vertical", "horizontal"):
            raise ValueError(f"duplicate or unsupported grid: {label}")
        seen.add(label)
        entity = doc.entitydb.get(grid["handle"])
        if entity is None or entity.dxftype() not in ("LINE", "CIRCLE"):
            raise ValueError(
                f"unsupported/missing grid entity: {label}: {grid['handle']}"
            )
        coord = 0 if orientation == "vertical" else 1
        if entity.dxftype() == "LINE":
            if abs(entity.dxf.start[coord] - entity.dxf.end[coord]) > 0.001:
                raise ValueError(f"non-cardinal grid: {label}")
            position = entity.dxf.start[coord]
        else:
            position = entity.dxf.center[coord]
        if not math.isfinite(position):
            raise ValueError(f"nonfinite grid: {label}")
        axes.append({**grid, "position_mm": position})
    rows = []
    for entity in doc.modelspace().query("DIMENSION"):
        value = float(entity.get_measurement())
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"unmeasurable DIMENSION: {entity.dxf.handle}")
        angle = entity.dxf.get("angle", 0) % 180
        coord = (
            0
            if min(angle, 180 - angle) < 0.001
            else 1
            if abs(angle - 90) < 0.001
            else None
        )
        ends = [entity.dxf.get("defpoint2"), entity.dxf.get("defpoint3")]
        labels = []
        reason = "ends_not_on_source_axes"
        if (
            (entity.dxf.dimtype & 15) != 0
            or coord is None
            or any(p is None for p in ends)
        ):
            reason = "unsupported_dimension_type_or_angle"
        else:
            orientation = "vertical" if coord == 0 else "horizontal"
            for point in ends:
                hits = [
                    a["label"]
                    for a in axes
                    if a["orientation"] == orientation
                    and abs(a["position_mm"] - point[coord]) < 1.0
                ]
                labels.append(hits[0] if len(hits) == 1 else None)
        pair = (
            labels
            if len(labels) == 2 and all(labels) and labels[0] != labels[1]
            else None
        )
        rows.append(
            {
                "handle": entity.dxf.handle,
                "value_mm": value,
                "axes": pair,
                "reason": None if pair else reason,
                "extension_points_mm": [
                    list(p) if p is not None else None for p in ends
                ],
            }
        )
    return {
        "source": {"path": str(dxf), "sha256": source_sha},
        "grids": axes,
        "dimensions": rows,
    }


def score_dimensions(values: list[dict], truth: list[dict]) -> dict:
    """Strict positive semantic bindings; one source entity can earn one hit only."""
    if len({r["handle"] for r in truth}) != len(truth):
        raise ValueError("duplicate oracle handle")
    predictions = [
        v
        for v in values
        if v["kind"] == "dimension" and v["binding"]["type"] != "unbound"
    ]
    used = set()
    for value in predictions:
        binding = value["binding"]
        number = value.get("value")
        if (
            binding["type"] != "axis_pair"
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
        ):
            continue
        hits = [
            t
            for t in truth
            if t["handle"] not in used
            and t.get("axes")
            and set(t["axes"]) == set(binding["axes"])
            and math.isfinite(t["value_mm"])
            and abs(t["value_mm"] - number) < 0.5
        ]
        if len(hits) == 1:
            used.add(hits[0]["handle"])
    found, correct, total = len(predictions), len(used), len(truth)
    return {
        "found": found,
        "correct": correct,
        "wrong": found - correct,
        "missed": total - correct,
        "truth": total,
        "precision": correct / found if found else None,
        "recall": correct / total if total else None,
    }


def main(argv: list[str]) -> int:
    from dt_ai.album.binding import bind_album

    dxf, grid_path, pdf = map(Path, argv)
    oracle = dimension_oracle(dxf, json.loads(grid_path.read_text(encoding="utf-8")))
    result = bind_album(pdf)
    print(
        json.dumps(
            {
                "oracle": oracle,
                "pdf": result["source"],
                "dimensions": score_dimensions(result["values"], oracle["dimensions"]),
                "passed": False,
                "scope": "semantic axis-pair bindings; no calibrated geometry",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
