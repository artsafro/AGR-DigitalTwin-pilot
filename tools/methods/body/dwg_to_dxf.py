"""Headless DWG -> DXF readback through the AutoCAD core console, on a copy of the drawing (#1203).

Pattern: new-case: headless AutoCAD DWG->DXF readback (accoreconsole DXFOUT on a hashed copy).

This is the step the KPP1 cold run (#1172, RUN-LOG G4) executed by hand:
``accoreconsole.exe /i <copy.dwg> /s <script>`` with the script
``_.DXFOUT <path> _V _2018 16 _.QUIT _Y`` (one token per line). The DXF then goes to
``plan_from_dxf.py extract``.

Usage::

    uv run python tools/methods/body/dwg_to_dxf.py <source.dwg> <out.dxf> <receipt.json>
        [--workdir C:/x/kpp1] [--copy-name L03.dwg] [--accoreconsole <exe>] [--timeout 600] [--dry-run]

Guarantees (each has a test in tests/methods/test_dwg_to_dxf.py):
- AutoCAD never gets the original: the source is copied into ``--workdir`` and only the copy path
  goes into the command and the script. The source is hashed before the copy and after the run;
  a copy whose SHA-256 differs from the source, or a source that changed, is a failure.
- The receipt records the source, the copy and the DXF (path, SHA-256), the command, the script,
  the return code and the console log path. ``status`` is ``pass`` only when the return code is 0,
  the DXF exists, starts with a DXF ``SECTION`` header, the copy and the source are unchanged.
  Anything else is ``fail`` with the reason and exit 3; never a pass.
- Nothing is overwritten: the DXF, the copy, the script and the log must not exist (exit 4, nothing
  written). No two of source, copy, script, log, DXF and receipt are the same file (exit 4).
- A missing source, a source that is not ``.dwg``, an output that is not ``.dxf``, a missing
  accoreconsole (outside ``--dry-run``), a non-finite or non-positive timeout, and a path AutoCAD
  would read from the script that is not plain ASCII without spaces or ``;"`` are errors naming them
  (exit 2, nothing written). The source path itself may be anything; AutoCAD never reads it.
- ``--dry-run`` validates and prints the plan (hashes, command, script) as JSON; it writes nothing,
  creates no folder and needs no AutoCAD.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from safe_write import Refused, guard_cli, publish_text, same_file  # noqa: E402

DEFAULT_ACCORECONSOLE = Path("C:/Program Files/Autodesk/AutoCAD 2025/accoreconsole.exe")
DXF_VERSION = "_2018"
DXF_PRECISION = 16
SAFE_SCRIPT_PATH = re.compile(r"[A-Za-z0-9_:/.\\-]+")
__all__ = ["build_script", "plan", "run", "main", "same_file"]


class InputError(ValueError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _script_path(path: Path, what: str) -> str:
    text = path.as_posix()
    if not text.isascii() or not SAFE_SCRIPT_PATH.fullmatch(text):
        raise InputError(f"{what} path {text!r} is not plain ASCII without spaces or ;\" "
                         "(an AutoCAD script reads a space as Enter)")
    return text


def build_script(dxf: Path) -> str:
    """The cold-run DXFOUT script: one token per line, CRLF, ASCII."""
    lines = ["_.DXFOUT", _script_path(Path(dxf), "dxf"), "_V", DXF_VERSION, str(DXF_PRECISION), "_.QUIT", "_Y"]
    return "\r\n".join(lines) + "\r\n"


def plan(source: Path, dxf: Path, receipt: Path, workdir: Path, accoreconsole: Path,
         copy_name: str | None = None, timeout: float = 600.0, dry_run: bool = False) -> dict:
    """Validate everything and return the plan. No side effect."""
    source, dxf, receipt = Path(source).absolute(), Path(dxf).absolute(), Path(receipt).absolute()
    workdir, accoreconsole = Path(workdir).absolute(), Path(accoreconsole)
    if not source.is_file():
        raise InputError(f"source {source} does not exist or is not a file")
    name = copy_name if copy_name is not None else f"{dxf.stem}.dwg"
    if Path(name).name != name:
        raise InputError(f"copy name {name!r} must be a bare file name")
    copy = workdir / name
    script = workdir / f"{dxf.stem}.dxfout.scr"
    log = workdir / f"{dxf.stem}.accoreconsole.log"
    outputs = [copy, script, log, dxf, receipt]
    guard_cli([source], outputs)  # aliases first: an output that is the source is a refusal
    if source.suffix.lower() != ".dwg":
        raise InputError(f"source {source.name} is not a .dwg")
    if dxf.suffix.lower() != ".dxf":
        raise InputError(f"output {dxf.name} is not a .dxf")
    if Path(name).suffix.lower() != ".dwg":
        raise InputError(f"copy name {name!r} does not end in .dwg")
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise InputError(f"timeout {timeout!r} is not a finite positive number of seconds")
    build_script(dxf)
    _script_path(copy, "copy")
    _script_path(script, "script")
    acc_found = accoreconsole.is_file()
    if not acc_found and not dry_run:
        raise InputError(f"accoreconsole {accoreconsole} not found")
    for p in (copy, script, log, dxf):
        if p.exists():
            raise Refused(f"{p} already exists; a readback never overwrites (use a new versioned path)")
    return {"source": {"path": str(source), "sha256": _sha256(source)},
            "copy": str(copy), "script_path": str(script), "log": str(log), "dxf": str(dxf),
            "receipt": str(receipt), "accoreconsole": str(accoreconsole), "accoreconsole_found": acc_found,
            "command": [str(accoreconsole), "/i", str(copy), "/s", str(script)],
            "script": build_script(dxf), "timeout_s": timeout}


def _decode(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    for enc in ("utf-16-le", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _is_dxf(path: Path) -> bool:
    with open(path, "rb") as f:
        head = f.read(64)
    tokens = head.decode("ascii", "replace").split()
    return tokens[:2] == ["0", "SECTION"]


def run(p: dict, runner=subprocess.run) -> dict:
    """Copy, check the copy hash, write the script, run the console, check and hash the DXF."""
    source, copy, script, log, dxf = (Path(p["source"]["path"]), Path(p["copy"]), Path(p["script_path"]),
                                      Path(p["log"]), Path(p["dxf"]))
    receipt = {"receipt": "dwg-to-dxf/1", "tool": "tools/methods/body/dwg_to_dxf.py",
               "source": dict(p["source"]), "command": p["command"], "script": p["script"],
               "log": str(log), "status": "fail", "reason": None}
    copy.parent.mkdir(parents=True, exist_ok=True)
    dxf.parent.mkdir(parents=True, exist_ok=True)
    with open(source, "rb") as fin, open(copy, "xb") as fout:
        shutil.copyfileobj(fin, fout)
    copy_sha = _sha256(copy)
    receipt["copy"] = {"path": str(copy), "sha256": copy_sha}
    if copy_sha != p["source"]["sha256"]:
        receipt["reason"] = "copy SHA-256 differs from the source"
        return receipt
    with open(script, "x", encoding="ascii", newline="") as f:
        f.write(p["script"])
    try:
        proc = runner(p["command"], capture_output=True, timeout=p["timeout_s"], check=False)
    except subprocess.TimeoutExpired:
        receipt["reason"] = f"accoreconsole timed out after {p['timeout_s']} s"
        return receipt
    with open(log, "x", encoding="utf-8", newline="\n") as f:
        f.write(_decode(proc.stdout) + "\n--- stderr ---\n" + _decode(proc.stderr))
    receipt["returncode"] = proc.returncode
    after = _sha256(source)
    receipt["source_sha256_after"] = after
    copy_after = _sha256(copy)
    receipt["copy"]["sha256_after"] = copy_after
    problems = []
    if proc.returncode != 0:
        problems.append(f"accoreconsole exit code {proc.returncode}")
    if after != p["source"]["sha256"]:
        problems.append("the source changed during the run")
    if copy_after != copy_sha:
        problems.append("the copy changed during the run")
    if not dxf.is_file() or dxf.stat().st_size == 0:
        problems.append(f"no DXF written at {dxf}")
    else:
        receipt["dxf"] = {"path": str(dxf), "sha256": _sha256(dxf), "bytes": dxf.stat().st_size}
        if not _is_dxf(dxf):
            problems.append(f"{dxf.name} does not start with a DXF SECTION header")
    if problems:
        receipt["reason"] = "; ".join(problems)
    else:
        receipt["status"] = "pass"
    return receipt


def main(argv=None, runner=subprocess.run) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("dxf", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--workdir", type=Path, default=Path("C:/x/kpp1"))
    parser.add_argument("--copy-name", default=None)
    parser.add_argument("--accoreconsole", type=Path, default=DEFAULT_ACCORECONSOLE)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        p = plan(args.source, args.dxf, args.receipt, args.workdir, args.accoreconsole,
                 copy_name=args.copy_name, timeout=args.timeout, dry_run=args.dry_run)
    except Refused as exc:
        print(f"DWG_TO_DXF refused: {exc}", file=sys.stderr)
        return 4
    except (InputError, OSError) as exc:
        print(f"DWG_TO_DXF error: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(json.dumps({"dry_run": True, **p}, ensure_ascii=False, indent=1))
        return 0
    try:
        receipt = run(p, runner=runner)
    except OSError as exc:  # e.g. a copy/script created by someone else between plan and run
        print(f"DWG_TO_DXF error: {exc}", file=sys.stderr)
        return 2
    publish_text(Path(p["receipt"]), json.dumps(receipt, ensure_ascii=False, indent=1))
    if receipt["status"] != "pass":
        print(f"DWG_TO_DXF fail: {receipt['reason']}", file=sys.stderr)
        return 3
    print(json.dumps({"status": "pass", "dxf": receipt["dxf"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
