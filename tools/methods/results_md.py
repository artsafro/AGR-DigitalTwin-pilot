"""Generate docs/methods/<class>/RESULTS.md from its results.jsonl (methods catalog, #706).

Pattern: new-case: RESULTS.md table generated from measured rows (never edited by hand).

    uv run python tools/methods/results_md.py docs/methods/<class>/results.jsonl

One table row per JSON row, in file order; the row id (R1, R2, ...) is what WHEN.md cites. A null
metric shows as "-" and its reason is listed under the table; nothing is filled in.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_write import check_target, publish_text, refuse_aliases  # noqa: E402

HEAD = ("| Row | Object | Variant | Build s | Model tris | UCX pcs / tris / limit | UCX check | Failed / open checks "
        "| Closed convex | Model->UCX max / p95 m | UCX outside model | Envelope uncovered | xView V / F | Texel min / median px/m "
        "| MatID | File KB | Render SSIM |")


WIN_HEAD = " Glass objs | Glass tris (share) | Frame comps | Frame depth min / median / max m |"


def _win_cells(r: dict) -> str:
    w = (r.get("class_metrics") or {}).get("windows") or {}
    share = w.get("glass_triangle_share")
    depth = w.get("frame_depth_m")
    return " " + " | ".join([
        _v(w.get("glass_objects")),
        f"{_v(w.get('glass_triangles'))} ({'-' if share is None else f'{share:.1%}'})",
        _v(w.get("frame_components")),
        "-" if not depth else f"{depth['min']} / {depth['median']} / {depth['max']}",
    ]) + " |"


GROUND_HEAD = (" Input | Ground tris (ref) | dz max / p95 m | Samples both / missing / extra | Holes / ref (matched) "
               "| Boundary m (diff) | UV |")


def _ground_cells(r: dict) -> str:
    g = (r.get("class_metrics") or {}).get("ground") or {}
    inp = r.get("input") or {}
    diff = g.get("boundary_diff_m")
    return " " + " | ".join([
        str(inp.get("kind", "-")),
        f"{_v(g.get('triangles'))} ({_v(g.get('reference_triangles'))})",
        f"{_v(g.get('dz_max_m'))} / {_v(g.get('dz_p95_m'))}",
        f"{_v(g.get('samples_both'))} / {_v(g.get('samples_missing'))} / {_v(g.get('samples_extra'))}",
        f"{_v(g.get('holes'))} / {_v(g.get('reference_holes'))} ({_v(g.get('holes_matched'))})",
        f"{_v(g.get('boundary_m'))} ({'-' if diff is None else f'{diff:+}'})",
        {True: "yes", False: "no", None: "-"}[g.get("uv_present")],
    ]) + " |"


BODY_HEAD = " Deviation src->variant max / p95 m | Closed shells (share) | Tris / budget |"


def _body_cells(r: dict) -> str:
    b = (r.get("class_metrics") or {}).get("body") or {}
    share = b.get("closed_shell_share")
    budget = b.get("budget_share")
    return " " + " | ".join([
        f"{_v(b.get('deviation_max_m'))} / {_v(b.get('deviation_p95_m'))}",
        f"{_v(b.get('closed_components'))}/{_v(b.get('components'))} ({'-' if share is None else f'{share:.1%}'})",
        f"{_v(b.get('triangles'))} / {_v(b.get('triangle_budget'))} ({'-' if budget is None else f'{budget:.1%}'})",
    ]) + " |"


def _v(x, fmt="{}"):
    return "-" if x is None else fmt.format(x)


def _row(r: dict) -> str:
    ucx = r.get("ucx") or {}
    fit = (r.get("class_metrics") or {}).get("ucx_fit") or {}
    x, tex, mat, rs = r.get("xview") or {}, r.get("texel") or {}, r.get("matid") or {}, r.get("render_score") or {}
    tris = r.get("triangles") or {}
    checks = ucx.get("checks") or {}
    bad = [f"{k}: {v}" for k, v in checks.items() if v != "pass" and "advisory" not in k]
    if r.get("build_error"):
        bad = [f"build: {r['build_error'][:80]}"]
    pcs = f"{_v(ucx.get('pieces'))} / {_v(ucx.get('triangles'))} / {_v(ucx.get('limit_triangles'))}"
    size = None if r.get("file_size_bytes") is None else round(r["file_size_bytes"] / 1024)
    out_share = fit.get("ucx_outside_share")
    variant = r["variant"]
    if r.get("methods_only") is not None:
        if (r["methods_only"] or {}).get("delivery") is not False:
            raise ValueError(f"{r['row']}: a methods_only row must say delivery=false, got {r['methods_only']!r}")
        variant += " [METHODS-ONLY, not a delivery]"
    return "| " + " | ".join([
        r["row"], r["benchmark"], variant, _v(r.get("wall_time_s"), "{:.2f}"), _v(tris.get("model")), pcs,
        str(ucx.get("status", "-")), "; ".join(bad) or "-",
        f"{_v(ucx.get('closed_convex'))}/{_v(ucx.get('pieces'))}",
        f"{_v(fit.get('model_to_ucx_max_m'))} / {_v(fit.get('model_to_ucx_p95_m'))}",
        "-" if out_share is None else f"{out_share:.1%} ({fit.get('ucx_outside_model_m3')} m3)",
        "-" if fit.get("envelope_uncovered_share") is None else f"{fit['envelope_uncovered_share']:.1%}",
        f"{_v(x.get('overlapping_vertices'))} / {_v(x.get('overlapping_faces'))}",
        f"{_v(tex.get('min_px_m'))} / {_v(tex.get('median_px_m'))}",
        {True: "pass", False: "fail", None: "-"}[mat.get("passed")],
        _v(size), _v(rs.get("value")),
    ]) + " |"


def render(rows: list[dict], cls: str) -> str:
    windows, ground, body = cls == "windows-glazing", cls == "ground-terrain", cls == "building-body"
    head = HEAD + (WIN_HEAD if windows else GROUND_HEAD if ground else BODY_HEAD if body else "")
    lines = [f"# {cls} - measured results", "",
             f"Generated by `tools/methods/results_md.py` from `results.jsonl` ({len(rows)} rows); do not edit by hand.",
             "Row ids are cited by WHEN.md. Field meanings: docs/methods/README.md#row-fields.", "", head,
             "|" + "---|" * (head.count("|") - 1)]
    reasons, synthetic = {}, {}
    for r in rows:
        if _synthetic_flag(r):
            synthetic.setdefault(r.get("synthetic_reason") or "no reason recorded", []).append(r["row"])
        lines.append(_row(r) + (_win_cells(r) if windows else _ground_cells(r) if ground
                                else _body_cells(r) if body else ""))
        if ground:
            g = (r.get("class_metrics") or {}).get("ground") or {}
            for key, label in (("dz_reason", "dz"), ("footprint_reason", "footprint"), ("uv_reason", "uv")):
                if g.get(key):
                    reasons.setdefault(f"ground {label}: {g[key]}", []).append(r["row"])
        if body:
            b = (r.get("class_metrics") or {}).get("body") or {}
            for key in ("deviation_reason", "shell_reason"):
                if b.get(key):
                    reasons.setdefault(f"body {key.split('_')[0]}: {b[key]}", []).append(r["row"])
        if windows:
            w = (r.get("class_metrics") or {}).get("windows") or {}
            for key in ("glass_share_reason", "frame_reason"):
                if w.get(key):
                    reasons.setdefault(f"windows {key.split('_')[0]}: {w[key]}", []).append(r["row"])
        for key in ("texel", "render_score", "matid"):
            reason = (r.get(key) or {}).get("reason")
            if reason:
                reasons.setdefault(f"{key}: {reason}", []).append(r["row"])
        if r.get("wall_time_reason"):
            reasons.setdefault(f"wall time: {r['wall_time_reason']}", []).append(r["row"])
    methods_only = [r for r in rows if r.get("methods_only") is not None]
    if methods_only:
        lines += ["", "Methods-only rows (quality gate skipped by user decision, never a delivery):", ""]
        lines += [f"- {r['row']}: Ground gate skipped, failed gates: {', '.join(r['methods_only']['failed_gates']) or 'none'}"
                  for r in methods_only]
    if reasons:
        lines += ["", "Null metrics and why:", ""]
        lines += [f"- {k} ({', '.join(v)})" for k, v in sorted(reasons.items())]
    if synthetic:
        lines += ["", "Synthetic inputs and why:", ""]
        lines += [f"- {k} ({', '.join(v)})" for k, v in sorted(synthetic.items())]
    if body:
        lines += _comparison(rows)
    return "\n".join(lines) + "\n"


CMP_HEAD = ("| Object | Variant | Rows synthetic / drawing | Model tris | Deviation max m | Deviation p95 m "
            "| Closed shells | Drawing |")


def _synthetic_flag(r: dict) -> bool:
    """True / False / absent (= drawing-backed); any other value is an error naming the row (#735)."""
    flag = r.get("synthetic", False)
    if flag is not True and flag is not False:
        raise ValueError(f"{r['row']}: synthetic must be true, false or absent, got {flag!r}")
    return flag


def _comparison(rows: list[dict]) -> list[str]:
    """Synthetic vs drawing, side by side per (object, variant) (#735). Empty when no row is synthetic.

    Every row lands in exactly one line; two synthetic (or two drawing) rows for one object and variant are an
    error naming them, never a silent pick. A missing counterpart shows "-" and the reason, never a number.
    """
    pairs: dict[tuple[str, str], dict[bool, dict]] = {}
    for r in rows:
        slot = pairs.setdefault((r["benchmark"], r["variant"]), {})
        flag = _synthetic_flag(r)
        if flag in slot:
            kind = "synthetic" if flag else "drawing"
            raise ValueError(f"{slot[flag]['row']}, {r['row']}: two {kind} rows for {r['benchmark']} / {r['variant']}")
        slot[flag] = r
    if not any(True in slot for slot in pairs.values()):
        return []

    def body(r, key):
        return None if r is None else ((r.get("class_metrics") or {}).get("body") or {}).get(key)

    lines = ["", "Synthetic vs drawing (same object and variant; drawing = row without the synthetic marker):", "",
             CMP_HEAD, "|" + "---|" * (CMP_HEAD.count("|") - 1)]
    for (bench, variant), slot in pairs.items():
        syn, drw = slot.get(True), slot.get(False)

        def both(f):
            return f"{f(syn)} / {f(drw)}"

        status = ("measured" if syn and drw else "not measured: no drawing row in results.jsonl" if syn
                  else "no synthetic row")
        lines.append("| " + " | ".join([
            bench, variant, both(lambda r: "-" if r is None else r["row"]),
            both(lambda r: _v(None if r is None else (r.get("triangles") or {}).get("model"))),
            both(lambda r: _v(body(r, "deviation_max_m"))), both(lambda r: _v(body(r, "deviation_p95_m"))),
            both(lambda r: "-" if r is None else f"{_v(body(r, 'closed_components'))}/{_v(body(r, 'components'))}"),
            status]) + " |")
    return lines


def read_rows(results: Path) -> list[dict]:
    rows = [json.loads(ln) for ln in results.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ids = [r.get("row") for r in rows]
    want = [f"R{i}" for i in range(1, len(rows) + 1)]
    if ids != want:
        raise ValueError(f"{results}: row ids {ids[:5]}... are not R1..R{len(rows)} in order")
    classes = {r["class"] for r in rows}
    if len(classes) > 1:
        raise ValueError(f"{results}: mixed classes {sorted(classes)}")
    return rows


def write(results: Path) -> Path:
    out = results.with_name("RESULTS.md")
    refuse_aliases([out], [results])
    check_target(out)
    rows = read_rows(results)
    cls = rows[0]["class"] if rows else results.parent.name
    return publish_text(out, render(rows, cls))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: results_md.py <results.jsonl>")
    print(write(Path(sys.argv[1])))
