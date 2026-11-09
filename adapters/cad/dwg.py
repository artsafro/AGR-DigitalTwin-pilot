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


ACAD_REG_ROOT = r"Software\Autodesk\AutoCAD"


def user_filedia() -> int | None:
    """FILEDIA as the user's AutoCAD stores it (HKCU, current release and product, ``FileDialog``).

    Read before a core-console run because the console itself starts with FILEDIA=0 whatever the
    registry holds, and writes its session value back on exit (#1026, measured on AutoCAD 2025).
    Returns None when the value cannot be read or is not 0/1.
    """
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ACAD_REG_ROOT) as k:
            release = winreg.QueryValueEx(k, "CurVer")[0]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{ACAD_REG_ROOT}\{release}") as k:
            product = winreg.QueryValueEx(k, "CurVer")[0]
        key = rf"{ACAD_REG_ROOT}\{release}\{product}\FixedProfile\General Configuration"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            value = winreg.QueryValueEx(k, "FileDialog")[0]
    except OSError:
        return None
    return value if type(value) is int and value in (0, 1) else None


def filedia_guarded(body: str, filedia: int | None = None) -> str:
    """Wrap script ``body`` so ``FILEDIA`` is 0 while it runs and the user's value comes back after.

    ``FILEDIA`` is a user registry setting shared with the interactive AutoCAD: a core-console run
    that leaves it at 0 makes SAVE/SAVEAS in the user's AutoCAD ask on the command line instead of
    opening the file dialog (#1026). ``filedia`` is the user's value read before the run
    (``user_filedia()``); None falls back to the session value. It is restored after the body and by
    a temporary ``*error*`` handler when a command fails or is cancelled.
    """
    if filedia is not None and (type(filedia) is not int or filedia not in (0, 1)):
        raise ValueError(f"FILEDIA must be 0 or 1, got {filedia!r}")
    if not body.endswith("\n"):
        body += "\n"
    saved = '(getvar "FILEDIA")' if filedia is None else str(filedia)
    return (
        f"(setq agr-filedia {saved})\n"
        '(defun agr-restore-filedia () (if agr-filedia (setvar "FILEDIA" agr-filedia)) (princ '
        '(strcat "\\nAGR FILEDIA=" (itoa (getvar "FILEDIA")))) (princ))\n'
        "(setq agr-olderr *error*)\n"
        "(defun *error* (msg) (agr-restore-filedia) (setq *error* agr-olderr) "
        '(princ (strcat "\\nAGR ERROR: " msg)) (princ))\n'
        '(princ (strcat "\\nAGR FILEDIA_SESSION=" (itoa (getvar "FILEDIA")) " RESTORE=" (itoa agr-filedia)))\n'
        '(setvar "FILEDIA" 0)\n'
        + body
        + "(agr-restore-filedia)\n"
        "(setq *error* agr-olderr)\n"
    )


def dxfout_script(dxf: Path, version: str = "2018", precision: int = 16, filedia: int | None = None) -> str:
    """AutoCAD script: report units, then DXFOUT the open drawing to ``dxf``; FILEDIA is restored."""
    target = dxf.as_posix()
    return filedia_guarded(
        '(setvar "CMDECHO" 1)\n'
        '(princ (strcat "AGR INSUNITS=" (itoa (getvar "INSUNITS")) " ACADVER=" (getvar "ACADVER")))\n'
        f'(command "_.DXFOUT" "{target}" "_V" "{version}" "{precision}")\n',
        filedia,
    )


def dxfin_script(dxf: Path, dwg: Path, filedia: int | None = None) -> str:
    """AutoCAD script: DXFIN ``dxf`` into the blank drawing and SAVEAS DWG 2018; FILEDIA is restored."""
    return filedia_guarded(
        f'(command "_.DXFIN" "{dxf.as_posix()}")\n'
        f'(command "_.SAVEAS" "2018" "{dwg.as_posix()}")\n',
        filedia,
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
    scr.write_text(dxfout_script(dxf, filedia=user_filedia()), encoding="utf-8")
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
    scr.write_text(dxfin_script(dxf, dwg, filedia=user_filedia()), encoding="utf-8")
    log = dwg.with_suffix(".acad.json")
    cmd = [sys.executable, str(dcc_batch_path()), "acad", "--file", str(scr), "--out", str(log), "--timeout", str(timeout)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not dwg.exists():
        raise ConversionError(f"DXFIN/SAVEAS failed (exit {proc.returncode}): {proc.stdout[-2000:]}")
    return dwg
