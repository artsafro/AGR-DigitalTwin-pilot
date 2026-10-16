"""Shared, resumable per-object export plan.

new-case: #224 resumable per-object MAX/FBX export from one headless Max session

Pure Python (stdlib only). Imported by tests and by the 3ds Max job. The Max
session itself lives in ``batch_export_max.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

FORMATS = ("max", "fbx")


def truth(value) -> bool:
    """False for None, False, 0, "" and the strings false/undefined/none."""
    if value is None:
        return False
    text = str(value).strip().lower()
    return text not in ("false", "undefined", "none", "0", "")


def parse_triple(value) -> tuple[bool, int, int]:
    """Read #(ok, tris, mats). Any iterable is taken 0-based, the way pymxs Arrays iterate."""
    seq = list(value)
    if len(seq) < 3:
        raise TypeError("expected #(ok, tris, mats)")
    return truth(seq[0]), int(seq[1]), int(seq[2])

_FORBIDDEN = set('<>:"/\\|?*')
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DCC = "C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py"


def safe_stem(name: str) -> str:
    """File-system-safe stem: forbidden characters, controls and whitespace runs become '_'."""
    text = "" if name is None else str(name)
    parts: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            while index < len(text) and text[index].isspace():
                index += 1
            parts.append("_")
            continue
        code = ord(char)
        if char in _FORBIDDEN or code < 32 or code == 127:
            parts.append("_")
        else:
            parts.append(char)
        index += 1
    stem = "".join(parts).strip(" .")
    if not stem:
        stem = "node"
    return stem[:120]


def plan_outputs(nodes: list[str], out_dir: str, fmt: str) -> list[dict]:
    """One output row per node, in input order. Stems collide case-insensitively."""
    if fmt not in FORMATS:
        raise ValueError("unknown format: %s" % fmt)
    if not isinstance(nodes, list):
        raise ValueError("nodes must be a list of strings")
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, str) or node == "":
            raise ValueError("empty node name")
        if node in seen:
            raise ValueError("duplicate node name: %s" % node)
        seen.add(node)
    directory = str(out_dir).replace("\\", "/")
    if len(directory) > 1:
        directory = directory.rstrip("/")
    claimed: set[str] = set()
    rows: list[dict] = []
    for node in nodes:
        base = safe_stem(node)
        candidate = base
        suffix = 2
        while candidate.casefold() in claimed:
            candidate = "%s__%d" % (base, suffix)
            suffix += 1
        claimed.add(candidate.casefold())
        rows.append({
            "node": node,
            "output": "%s/%s.%s" % (directory, candidate, fmt),
            "format": fmt,
        })
    return rows


def path_key(path) -> str:
    """Absolute, slash-separated, case-folded key. Windows aliases share one key."""
    text = os.path.normcase(os.path.abspath(str(path))).replace("\\", "/")
    return text.casefold()


def file_sha256(path) -> str | None:
    """Hex SHA-256 of the file bytes, or None when the file is missing or unreadable."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def read_log(path) -> dict[str, dict]:
    """Last JSONL row per output path key. A missing file is an empty log; bad lines are skipped."""
    if not path or not os.path.exists(path):
        return {}
    found: dict[str, dict] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except (ValueError, TypeError):
                continue
            if isinstance(row, dict) and "output" in row:
                found[path_key(row["output"])] = row
    return found


def append_log(path, row: dict) -> None:
    """Append one JSON line and flush it to disk."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = json.dumps(row, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def decide(task: dict, log: dict, expected_tris, expected_mats) -> str:
    """``verify`` only when the receipt is this node, these counts, and these file bytes.

    A skip is not decided here. The Max job skips only after ``verify`` and a fresh
    readback of the current file against the live node.
    """
    output = task["output"]
    try:
        exists = os.path.exists(output)
    except OSError:
        return "export"
    if not exists:
        return "export"
    row = log.get(path_key(output))
    if not isinstance(row, dict) or row.get("status") != "ok":
        return "export"
    if row.get("node") != task.get("node") or row.get("format") != task.get("format"):
        return "export"
    if not _is_int(expected_tris) or not _is_int(expected_mats):
        return "export"
    if not _is_int(row.get("triangles")) or row.get("triangles") != expected_tris:
        return "export"
    if not _is_int(row.get("materials")) or row.get("materials") != expected_mats:
        return "export"
    digest = row.get("sha256")
    actual = file_sha256(output)
    if not isinstance(digest, str) or actual is None or digest != actual:
        return "export"
    try:
        size = os.path.getsize(output)
    except OSError:
        return "export"
    if row.get("bytes") != size:
        return "export"
    return "verify"


def preflight(tasks, protected: list[str], log_path: str) -> None:
    """Raise ValueError before any write when an output could replace a protected file or the log."""
    seen: dict[str, str] = {}
    outputs: list[str] = []
    for task in tasks:
        output = task["output"]
        key = path_key(output)
        if key in seen:
            raise ValueError("colliding path: %s" % output)
        seen[key] = output
        outputs.append(output)
    protected_paths: list[str] = []
    for item in protected:
        if item is None:
            continue
        text = str(item)
        if text == "":
            continue
        protected_paths.append(text)
    log_text = "" if log_path is None else str(log_path)
    log_key = path_key(log_text) if log_text else None
    for output in outputs:
        out_key = path_key(output)
        if log_key is not None and out_key == log_key:
            raise ValueError("colliding path: %s" % output)
        for prot in protected_paths:
            if out_key == path_key(prot):
                raise ValueError("colliding path: %s" % output)
            if os.path.exists(output) and os.path.exists(prot):
                try:
                    same = os.path.samefile(output, prot)
                except OSError:
                    same = False
                if same:
                    raise ValueError("colliding path: %s" % output)
    if log_key is not None:
        for prot in protected_paths:
            if log_key == path_key(prot):
                raise ValueError("colliding path: %s" % log_text)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def readback_verdict(expected_tris, got_tris, expected_mats, got_mats, exists, error=None):
    """``ok`` only when the file exists and the triangle and material counts match."""
    if exists is not True:
        return ("failed", "missing file")
    if error:
        return ("failed", "readback error")
    counts = (expected_tris, got_tris, expected_mats, got_mats)
    if not all(_is_int(value) for value in counts):
        return ("failed", "counts not ints")
    if expected_tris <= 0:
        return ("failed", "zero tris")
    if got_tris != expected_tris:
        return ("failed", "triangle mismatch")
    if got_mats != expected_mats:
        return ("failed", "material mismatch")
    return ("ok", None)


def make_row(task, status, seconds, triangles, materials, readback_triangles,
             readback_materials, bytes_, error=None, resumed=False, timings=None,
             sha256=None) -> dict:
    """One per-object JSONL row."""
    return {
        "node": task["node"],
        "output": task["output"],
        "format": task["format"],
        "status": status,
        "seconds": seconds,
        "triangles": triangles,
        "materials": materials,
        "readback_triangles": readback_triangles,
        "readback_materials": readback_materials,
        "bytes": bytes_,
        "sha256": sha256,
        "error": error,
        "resumed": resumed,
        "timings": {} if timings is None else timings,
    }


def stats(values: list[float]) -> dict:
    """n, median, nearest-rank p90, min, max, total. Empty input leaves the measures as None."""
    if not values:
        return {"n": 0, "median": None, "p90": None, "min": None, "max": None, "total": None}
    ordered = sorted(float(value) for value in values)
    count = len(ordered)
    if count % 2:
        median = ordered[count // 2]
    else:
        median = (ordered[count // 2 - 1] + ordered[count // 2]) / 2.0
    p90 = ordered[math.ceil(0.9 * count) - 1]

    def rounded(value: float) -> float:
        return round(float(value), 4)

    return {
        "n": count,
        "median": rounded(median),
        "p90": rounded(p90),
        "min": rounded(ordered[0]),
        "max": rounded(ordered[-1]),
        "total": rounded(sum(ordered)),
    }


def projection(median_s: float, count: int) -> float:
    """Seconds to export ``count`` objects at the measured median (Flora 136, MAF 931)."""
    return float(median_s) * int(count)


def _validate_request(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")
    fmt = data.get("format")
    if fmt not in FORMATS:
        raise ValueError("unknown format: %s" % fmt)
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
        raise ValueError("nodes must be a list of strings")
    for key in ("out_dir", "log_path"):
        if not isinstance(data.get(key), str) or data.get(key) == "":
            raise ValueError("%s must be a string" % key)
    scene = data.get("scene", None)
    if scene is not None and not isinstance(scene, str):
        raise ValueError("scene must be a string or null")
    for key in ("request_path", "result_path"):
        if key not in data or data[key] is None:
            continue
        if not isinstance(data[key], str):
            raise ValueError("%s must be a string or null" % key)
    return data


def write_request(path, scene, nodes, out_dir, fmt, log_path, request_path=None, result_path=None) -> None:
    """Write the JSON request the headless Max job reads."""
    payload = {
        "scene": scene,
        "nodes": list(nodes),
        "out_dir": out_dir,
        "format": fmt,
        "log_path": log_path,
    }
    if request_path is not None:
        payload["request_path"] = request_path
    if result_path is not None:
        payload["result_path"] = result_path
    _validate_request(payload)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


def load_request(path) -> dict:
    """Load a request JSON and reject a malformed one."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return _validate_request(data)


def inside_repo(path) -> bool:
    """True when ``path`` resolves to the repository root or a directory inside it."""
    try:
        target = str(Path(path).resolve())
        common = os.path.commonpath([str(_REPO_ROOT), target])
    except (OSError, ValueError):
        return False
    return common.casefold() == str(_REPO_ROOT).casefold()


def _slash(path: str) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def _parse_nodes(text: str) -> list[str]:
    candidate = Path(text)
    if candidate.suffix.lower() == ".json" and candidate.is_file():
        data = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError("nodes json must be a list of strings")
        return data
    return [part for part in text.split(",") if part != ""]


def _print_summary(log_path: str) -> None:
    found = read_log(log_path)
    counts: dict[str, int] = {}
    seconds: list[float] = []
    for row in found.values():
        status = str(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
        seconds_value = row.get("seconds")
        if status == "ok" and isinstance(seconds_value, (int, float)) and not isinstance(seconds_value, bool):
            seconds.append(float(seconds_value))
    print("summary " + json.dumps({"counts": counts, "seconds": stats(seconds)}, ensure_ascii=False))


def main(argv=None) -> int:
    """CLI: write a request and, unless ``--dry-run``, run it in one headless Max session."""
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(prog="batch_export_plan")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--scene", default=None)
    run.add_argument("--nodes", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--format", required=True)
    run.add_argument("--log", default=None)
    run.add_argument("--timeout", type=int, default=3600)
    run.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.format not in FORMATS:
        print("unknown format: %s" % args.format, file=sys.stderr)
        return 2
    out_dir = _slash(args.out)
    log_path = _slash(args.log) if args.log else out_dir + "/batch_export.jsonl"
    if inside_repo(out_dir) or inside_repo(log_path):
        print("refusing output inside the repository", file=sys.stderr)
        return 2
    try:
        nodes = _parse_nodes(args.nodes)
        tasks = plan_outputs(nodes, out_dir, args.format)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    scene = _slash(args.scene) if args.scene else None
    request_path = str(Path(log_path).with_name("batch_export_request.json")).replace("\\", "/")
    result_path = str(Path(log_path).with_name("dcc_batch_result.json")).replace("\\", "/")
    try:
        preflight(tasks, [scene, request_path, result_path], log_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_request(
        request_path, scene, nodes, out_dir, args.format, log_path,
        request_path=request_path, result_path=result_path,
    )
    if args.dry_run:
        found = read_log(log_path)
        print("DRY-RUN")
        for task in tasks:
            row = found.get(path_key(task["output"]))
            if isinstance(row, dict):
                expected_tris = row.get("triangles")
                expected_mats = row.get("materials")
            else:
                expected_tris = None
                expected_mats = None
            print("%s\t%s\t%s" % (
                decide(task, found, expected_tris, expected_mats), task["node"], task["output"],
            ))
        return 0
    dcc = os.environ.get("AGR_DCC_BATCH", _DEFAULT_DCC)
    job = Path(__file__).resolve().with_name("batch_export_max.py")
    cmd = [
        sys.executable,
        dcc,
        "max",
        "--file",
        str(job),
        "--timeout",
        str(args.timeout),
        "--out",
        result_path,
    ]
    env = os.environ.copy()
    env["AGR_BATCH_EXPORT_REQUEST"] = request_path
    completed = subprocess.run(cmd, env=env)
    _print_summary(log_path)
    return int(completed.returncode)


if __name__ == "__main__":
    sys.exit(main())
