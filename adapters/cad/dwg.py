"""DWG -> DXF through the AutoCAD 2025 core console (DXFOUT), always on a copy.

Pattern: n/a | new-case: SPOZU DWG intake for adapters/cad (issue #195); core-console DXFOUT on a
hashed copy, the source DWG is never opened by AutoCAD.

The core console is driven by the workstation wrapper ``dcc_batch.py acad`` (session lock, log
capture). Its path comes from ``DT_DCC_BATCH`` or the pilot default below. ODA is not used.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DCC_BATCH = "C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py"


class ConversionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Conversion:
    source: Path
    source_sha256: str
    copy: Path
    dxf: Path
    log: Path
    seconds: float | None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dcc_batch_path() -> Path:
    return Path(os.environ.get("DT_DCC_BATCH", DEFAULT_DCC_BATCH))


def dxfout_script(dxf: Path, version: str = "2018", precision: int = 16) -> str:
    """AutoCAD script: report units, then DXFOUT the open drawing to ``dxf``."""
    target = dxf.as_posix()
    return (
        '(setvar "FILEDIA" 0)\n'
        '(setvar "CMDECHO" 1)\n'
        '(princ (strcat "AGR INSUNITS=" (itoa (getvar "INSUNITS")) " ACADVER=" (getvar "ACADVER")))\n'
        f'(command "_.DXFOUT" "{target}" "_V" "{version}" "{precision}")\n'
    )


def dwg_to_dxf(source: str | Path, workdir: str | Path, *, timeout: float = 900) -> Conversion:
    """Copy ``source`` into ``workdir``, DXFOUT the copy, verify the source is unchanged.

    Raises ConversionError when the wrapper is missing, the console fails, no DXF appears or the
    source hash changed during the run.
    """
    source = Path(source)
    workdir = Path(workdir)
    if source.suffix.lower() != ".dwg":
        raise ConversionError(f"{source}: not a .dwg")
    workdir.mkdir(parents=True, exist_ok=True)
    before = sha256(source)
    copy = workdir / f"{source.stem}.copy.dwg"
    if copy.resolve() == source.resolve():
        raise ConversionError("workdir copy would overwrite the source")
    shutil.copy2(source, copy)
    if sha256(copy) != before:
        raise ConversionError(f"{copy}: copy hash differs from the source")
    dxf = workdir / f"{source.stem}.dxf"
    if dxf.exists():
        dxf.unlink()
    scr = workdir / f"{source.stem}.dxfout.scr"
    scr.write_text(dxfout_script(dxf), encoding="utf-8")
    log = workdir / f"{source.stem}.acad.json"
    batch = dcc_batch_path()
    if not batch.exists():
        raise ConversionError(f"dcc_batch wrapper not found: {batch} (set DT_DCC_BATCH)")
    cmd = [sys.executable, str(batch), "acad", "--file", str(scr), "--dwg", str(copy), "--out", str(log),
           "--timeout", str(timeout)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    seconds = None
    try:
        res = json.loads(log.read_text(encoding="utf-8"))
        seconds = res.get("seconds")
        status = res.get("status")
    except (OSError, ValueError):
        status = None
    after = sha256(source)
    if after != before:
        raise ConversionError(f"{source}: source hash changed during conversion")
    if proc.returncode != 0 or status != "ok":
        raise ConversionError(f"core console failed (exit {proc.returncode}, status {status}): {proc.stdout[-2000:]}")
    if not dxf.exists() or dxf.stat().st_size == 0:
        raise ConversionError(f"DXFOUT produced no file: {dxf}")
    return Conversion(source=source, source_sha256=before, copy=copy, dxf=dxf, log=log, seconds=seconds)


def make_dwg_from_dxf(dxf: str | Path, dwg: str | Path, *, timeout: float = 300) -> Path:
    """Test helper: DXFIN a (synthetic) DXF into a blank core-console drawing and SAVEAS DWG 2018."""
    dxf, dwg = Path(dxf), Path(dwg)
    scr = dwg.with_suffix(".dxfin.scr")
    scr.write_text(
        '(setvar "FILEDIA" 0)\n'
        f'(command "_.DXFIN" "{dxf.as_posix()}")\n'
        f'(command "_.SAVEAS" "2018" "{dwg.as_posix()}")\n',
        encoding="utf-8",
    )
    log = dwg.with_suffix(".acad.json")
    cmd = [sys.executable, str(dcc_batch_path()), "acad", "--file", str(scr), "--out", str(log), "--timeout", str(timeout)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not dwg.exists():
        raise ConversionError(f"DXFIN/SAVEAS failed (exit {proc.returncode}): {proc.stdout[-2000:]}")
    return dwg
