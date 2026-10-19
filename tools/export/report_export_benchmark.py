"""Render a Markdown report from tools/export/benchmark_export_max.py output."""
from __future__ import annotations

import json
import sys

import batch_export_plan as plan


def _format_projection(seconds: float) -> str:
    total = int(round(float(seconds)))
    minutes, secs = divmod(total, 60)
    return "%dm %ds / %ds" % (minutes, secs, total)


def _number(value) -> str:
    if value is None:
        return ""
    return str(value)


def _fastest(bench: dict) -> str | None:
    """Route whose readbacks were all ok, ranked by median seconds at its largest N."""
    best = None
    summary = bench.get("summary") or {}
    for route in sorted(summary):
        blocks = summary[route]
        if not isinstance(blocks, dict) or not blocks:
            continue
        scored = []
        all_ok = True
        for key, block in blocks.items():
            ok = int(block.get("ok") or 0)
            failed = int(block.get("failed") or 0)
            if failed or block.get("budget_hit") or ok <= 0:
                all_ok = False
                break
            median = (block.get("seconds") or {}).get("median")
            if median is None:
                all_ok = False
                break
            try:
                size = int(key)
            except (TypeError, ValueError):
                size = 0
            scored.append((size, float(median)))
        if not all_ok or not scored:
            continue
        scored.sort()
        score = scored[-1][1]
        if best is None or score < best[0] or (score == best[0] and route < best[1]):
            best = (score, route)
    if best is None:
        return None
    return best[1]


def render(bench: dict, flora: int = 136, maf: int = 931) -> str:
    """Markdown table plus the d_* extras and the fastest all-ok route."""
    header = (
        "| route | N | objects ok/total | median s | p90 s | median export-only s | projected %d Flora | projected %d MAF |"
        % (flora, maf)
    )
    lines = [header, "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    summary = bench.get("summary") or {}
    entries = []
    for route in summary:
        blocks = summary[route]
        if not isinstance(blocks, dict):
            continue
        for key, block in blocks.items():
            try:
                size = int(key)
            except (TypeError, ValueError):
                size = key
            entries.append((str(route), size, key, block))
    entries.sort(key=lambda item: (item[0], item[1] if isinstance(item[1], int) else 0))
    for route, _size, key, block in entries:
        seconds = block.get("seconds") or {}
        export_s = block.get("export_s") or {}
        ok = int(block.get("ok") or 0)
        failed = int(block.get("failed") or 0)
        median = seconds.get("median")
        flora_text = ""
        maf_text = ""
        if median is not None:
            flora_text = _format_projection(plan.projection(median, flora))
            maf_text = _format_projection(plan.projection(median, maf))
        lines.append("| %s | %s | %d/%d | %s | %s | %s | %s | %s |" % (
            route,
            key,
            ok,
            ok + failed,
            _number(median),
            _number(seconds.get("p90")),
            _number(export_s.get("median")),
            flora_text,
            maf_text,
        ))
    lines.append("")
    lines.append("## extras")
    extras = bench.get("extras") or {}
    if not extras:
        lines.append("(none)")
    for key in sorted(extras):
        lines.append("- %s: %s" % (key, json.dumps(extras[key], ensure_ascii=False, sort_keys=True)))
    fastest = _fastest(bench)
    lines.append("")
    lines.append("fastest all-ok route: %s" % (fastest if fastest else "none"))
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    flora = 136
    maf = 931
    paths = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--flora":
            flora = int(argv[index + 1])
            index += 2
            continue
        if token == "--maf":
            maf = int(argv[index + 1])
            index += 2
            continue
        paths.append(token)
        index += 1
    if len(paths) != 1:
        print("usage: report_export_benchmark.py <benchmark.json> [--flora 136] [--maf 931]", file=sys.stderr)
        return 2
    with open(paths[0], encoding="utf-8") as handle:
        bench = json.load(handle)
    sys.stdout.write(render(bench, flora=flora, maf=maf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
