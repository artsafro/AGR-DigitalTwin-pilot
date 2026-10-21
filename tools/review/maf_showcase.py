"""new-case: MAF showcase scene: NPM/VPM pairs + spec TEXT per position, rows by MAF type (#487).

Display only. Reads a site MAF set report (``site-maf-set.json``) and a grouping config,
checks every input FBX against the recorded SHA256, then builds one 3ds Max scene through
headless 3dsmaxbatch (``dcc_batch.py``): per position the NPM and the VPM side by side, a
TEXT object to the right with what the agent read from the specification, one row per MAF
type with a row label. A second, fresh 3dsmaxbatch process reopens the saved scene and
counts meshes and text objects (readback). Nothing is remodelled; input files are only read.
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

GROUPS = ("sport", "kids", "landscaping", "benches", "lighting")
GROUP_LABELS = {
    "sport": "Спортивное оборудование",
    "kids": "Детское игровое оборудование",
    "landscaping": "Элементы благоустройства",
    "benches": "Скамьи, лежаки, кресла",
    "lighting": "Освещение",
}
TEXT_SIZE = 0.15
LINE_H = 1.35 * TEXT_SIZE
CHAR_W = 0.6 * TEXT_SIZE
PAIR_GAP = 0.5
TEXT_GAP = 0.4
SLOT_GAP = 1.2
ROW_GAP = 3.0
SCRIPTS = Path(os.environ.get("AGR_KANBAN_SCRIPTS", "C:/Users/artsafro/hermes_kanban/scripts"))


class ShowcaseError(Exception):
    """Fail closed: no scene, no review entry."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _num(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ShowcaseError(f"{what}: not a finite number: {value!r}")
    return float(value)


def _size(values, what, allow_none=False):
    if not isinstance(values, list) or len(values) != 3:
        raise ShowcaseError(f"{what}: expected 3 values")
    out = []
    for v in values:
        if v is None and allow_none:
            out.append(None)
        else:
            out.append(_num(v, what))
    return out


def _fmt(values):
    return " x ".join("—" if v is None else f"{v:.3f}" for v in values)


def _dev(values):
    return " / ".join("—" if v is None else f"{v:.3f}" for v in values)


def review_reasons(pos, exceptions) -> list[str]:
    """Every non-pass status of the position, in text form; empty list = all pass."""
    reasons = []
    sid = pos["set_id"]
    if sid in exceptions:
        note = exceptions[sid]
        notes = [note] if isinstance(note, str) else note
        if not isinstance(notes, list) or not notes or not all(isinstance(n, str) and n.strip() for n in notes):
            raise ShowcaseError(f"{sid}: user exception must be a non-empty string or list of strings")
        reasons += notes
    for prof in ("npm", "vpm"):
        dim = pos[prof]["dimension"]
        if dim.get("verdict") != "pass":
            reasons.append(f"{prof.upper()} размер: {dim.get('verdict')}")
        for name, finding in sorted(pos[prof].get("maf_findings", {}).items()):
            if finding.get("status") != "pass":
                reasons.append(f"{prof.upper()} {name}: {finding.get('status')}")
    return reasons


def text_lines(pos, exceptions) -> list[str]:
    sid = pos["set_id"]
    npm, vpm = pos["npm"], pos["vpm"]
    reasons = review_reasons(pos, exceptions)
    head = sid + ("   !! REVIEW" if reasons else "   pass")
    sched = pos.get("schedule_size_m")
    if not isinstance(sched, list) or len(sched) != 3:
        raise ShowcaseError(f"{sid}: schedule_size_m missing")
    sched = [None if v is None else _num(v, f"{sid} schedule") for v in sched]
    meas = _size(npm["dimension"]["aligned_m"], f"{sid} npm aligned")
    vmeas = _size(vpm["dimension"]["aligned_m"], f"{sid} vpm aligned")
    dev = _size(npm["dimension"]["deviation_m"], f"{sid} npm deviation", allow_none=True)
    height = " (H = плоскость столешницы)" if pos.get("height_rule") == "table_top" else ""
    lines = [
        head,
        f"Спецификация: {pos['schedule']}  {pos['name']}",
        f"СПОЗУ: {pos['spozu_block']} x {pos['spozu_count_568BF']}",
        f"Библиотека: {pos['catalogue_id']}",
        f"Треугольники NPM / VPM: {int(npm['triangles'])} / {int(vpm['triangles'])}",
        f"Замер NPM L/W/H, м: {_fmt(meas)}{height}",
    ]
    if any(abs(a - b) > 0.001 for a, b in zip(meas, vmeas)):
        lines.append(f"Замер VPM L/W/H, м: {_fmt(vmeas)}")
    lines += [f"Спецификация L/W/H, м: {_fmt(sched)}", f"Отклонение, м: {_dev(dev)}"]
    lines += [f"!! REVIEW: {r}" for r in reasons]
    lines.append("Отметка Артёма: принято / переделать")
    for line in lines:
        if "\n" in line or "\r" in line:
            raise ShowcaseError(f"{sid}: multi-line field")
    return lines


def plan(set_report: dict, config: dict, set_root: Path | None = None, check_hashes=True) -> dict:
    positions = set_report.get("positions")
    if not isinstance(positions, list) or not positions:
        raise ShowcaseError("set report has no positions")
    groups = config.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ShowcaseError("config has no groups")
    exceptions = config.get("user_exceptions") or {}
    ids = [p.get("set_id") for p in positions]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ShowcaseError(f"duplicate set ids: {dup}")
    unmapped = [i for i in ids if i not in groups]
    if unmapped:
        raise ShowcaseError(f"set ids without a group: {unmapped}")
    extra = sorted(set(groups) - set(ids))
    if extra:
        raise ShowcaseError(f"config groups name ids not in the set: {extra}")
    extra = sorted(set(exceptions) - set(ids))
    if extra:
        raise ShowcaseError(f"config exceptions name ids not in the set: {extra}")
    bad = sorted({g for g in groups.values() if g not in GROUPS})
    if bad:
        raise ShowcaseError(f"unknown groups: {bad} (allowed {list(GROUPS)})")

    by_group = {g: [] for g in GROUPS}
    for pos in positions:
        by_group[groups[pos["set_id"]]].append(pos)

    rows, slots, y = [], [], 0.0
    files = set()
    for g in GROUPS:
        members = by_group[g]
        depth = 0.0
        x = 0.0
        row_slots = []
        for pos in members:
            sid = pos["set_id"]
            pair = {}
            for prof in ("npm", "vpm"):
                fbx = Path(pos[prof]["fbx"])
                key = os.path.normcase(os.path.abspath(fbx))
                if key in files:
                    raise ShowcaseError(f"{sid} {prof}: FBX used twice: {fbx}")
                files.add(key)
                if check_hashes:
                    if not fbx.is_file():
                        raise ShowcaseError(f"{sid} {prof}: missing FBX {fbx}")
                    got = sha256(fbx)
                    if got != pos[prof]["sha256"]:
                        raise ShowcaseError(f"{sid} {prof}: SHA256 mismatch {fbx}")
                size = _size(pos[prof]["measured_size_m"], f"{sid} {prof} measured")
                if min(size) < 0 or max(size) <= 0:
                    raise ShowcaseError(f"{sid} {prof}: empty size")
                tris = _num(pos[prof]["triangles"], f"{sid} {prof} triangles")
                if tris <= 0 or tris != int(tris):
                    raise ShowcaseError(f"{sid} {prof}: triangles must be a positive integer")
                pair[prof] = dict(fbx=fbx.as_posix(), size=size, triangles=int(tris))
            lines = text_lines(pos, exceptions)
            npm_x = x
            vpm_x = npm_x + pair["npm"]["size"][0] + PAIR_GAP
            text_x = vpm_x + pair["vpm"]["size"][0] + TEXT_GAP
            text_w = max(len(line) for line in lines) * CHAR_W
            depth = max(depth, pair["npm"]["size"][1], pair["vpm"]["size"][1])
            row_slots.append(dict(set_id=sid, group=g, npm_x=npm_x, vpm_x=vpm_x, text_x=text_x,
                                  npm=pair["npm"], vpm=pair["vpm"], lines=lines,
                                  review=bool(review_reasons(pos, exceptions))))
            x = text_x + text_w + SLOT_GAP
        depth = max(depth, 1.0)
        for slot in row_slots:
            slot["y"] = y
        label = f"{GROUP_LABELS[g]}: {len(members)} поз. (в паре: слева NPM, справа VPM)"
        if not members:
            label = f"{GROUP_LABELS[g]}: 0 позиций в наборе v005-set"
        rows.append(dict(group=g, y=y, label=label, count=len(members), width=x))
        slots += row_slots
        y += depth + ROW_GAP
    if len(slots) != len(positions):
        raise ShowcaseError("lost positions in layout")
    return dict(rows=rows, slots=slots, extent=[max(r["width"] for r in rows), y])


def _ms(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _p(path) -> str:
    return _ms(Path(path).resolve().as_posix())


BUILD = r'''(
local ok = false
local problem = ""
local f = undefined
try (
resetMaxFile #noPrompt
units.SystemType = #meters
units.SystemScale = 1.0
backgroundColor = color 235 235 235
FBXImporterSetParam "Mode" "merge"
FBXImporterSetParam "ConvertUnit" "m"
FBXImporterSetParam "ScaleFactor" 1.0
fn placeFbx path prefix tx ty = (
    local before = for o in objects collect o
    if not (importFile path #noPrompt using:FBXIMP) do throw ("FBX import failed: " + path)
    local added = for o in objects where (findItem before o) == 0 collect o
    local geo = for o in added where (superClassOf o) == GeometryClass collect o
    if geo.count != 1 do throw ("expected 1 mesh in " + path + ", got " + (geo.count as string))
    if added.count != 1 do throw ("expected 1 node in " + path + ", got " + (added.count as string))
    local o = geo[1]
    o.name = prefix + o.name
    local bb = nodeGetBoundingBox o (matrix3 1)
    o.pos += [tx - bb[1].x, ty - (bb[1].y + bb[2].y) / 2.0, 0.0 - bb[1].z]
    o
)
fn placeText txt nm tx ty sz = (
    local t = text text:txt size:sz font:"Arial" name:nm leading:(sz * 0.35)
    t.wirecolor = color 10 10 10
    addModifier t (Extrude amount:(sz * 0.05) capStart:true capEnd:true)
    rotate t (angleaxis 90 [1,0,0])
    local bb = nodeGetBoundingBox t (matrix3 1)
    t.pos += [tx - bb[1].x, ty - bb[1].y, 0.05 - bb[1].z]
    t
)
@SLOTS@
@ROWS@
if not (saveMaxFile @OUT@ quiet:true) do throw "save failed"
local cam = Targetcamera name:"Showcase_Camera" fov:50
cam.target = Targetobject name:"Showcase_Target" pos:[@CX@, @CY@, 0.5]
cam.pos = [@CX@, @CY@ - @DIST@, @DIST@ * 0.75]
render camera:cam outputSize:[2400,1350] vfb:false outputfile:@RENDER@
@ROWCAMS@
delete cam
ok = true
) catch (problem = getCurrentException())
f = createFile @REPORT@ encoding:#utf8
local msg = substituteString (substituteString (substituteString (substituteString (problem as string) "\\" "/") "\"" "'") "\n" " ") "\r" " "
if ok then format "{\"ok\":true}" to:f else format "{\"ok\":false,\"error\":\"%\"}" msg to:f
close f
if not ok do format "Showcase failed: %\n" problem
ok
)
'''

READBACK = r'''(
local ok = false
local problem = ""
local rows = #()
try (
resetMaxFile #noPrompt
if not (loadMaxFile @SCENE@ quiet:true useFileUnits:true) do throw "load failed"
for o in objects do (
    local kind = if (classOf o.baseObject) == text then "text" else if (superClassOf o) == GeometryClass then "mesh" else "other"
    local bb = nodeGetBoundingBox o (matrix3 1)
    local tris = if kind == "mesh" then (snapshotAsMesh o).numfaces else 0
    local txt = if kind == "text" then o.baseObject.text else ""
    append rows #(o.name, kind, tris, bb[2] - bb[1], txt)
)
ok = true
) catch (problem = getCurrentException())
local f = createFile @REPORT@ encoding:#utf8
format "{\"ok\":%,\"units\":\"%\",\"scale\":%,\"version\":%,\"objects\":[" ok (units.SystemType as string) units.SystemScale ((maxVersion())[1]) to:f
for i = 1 to rows.count do (
    local r = rows[i]
    local esc = substituteString (substituteString (substituteString r[5] "\\" "\\\\") "\"" "\\\"") "\r" "\\n"
    esc = substituteString esc "\n" "\\n"
    format "%{\"name\":\"%\",\"kind\":\"%\",\"tris\":%,\"size\":[%,%,%],\"text\":\"%\"}" (if i > 1 then "," else "") r[1] r[2] r[3] r[4].x r[4].y r[4].z esc to:f
)
format "]}" to:f
close f
ok
)
'''


def build_script(layout, out_max: Path, render_png: Path, report: Path, row_dir: Path) -> str:
    lines = []
    for s in layout["slots"]:
        sid = s["set_id"]
        lines.append(f'placeFbx {_p(s["npm"]["fbx"])} "NPM__" {s["npm_x"]:.4f} {s["y"]:.4f}')
        lines.append(f'placeFbx {_p(s["vpm"]["fbx"])} "VPM__" {s["vpm_x"]:.4f} {s["y"]:.4f}')
        body = "\\n".join(_ms(line)[1:-1] for line in s["lines"])
        lines.append(f'placeText "{body}" "TXT_{sid}" {s["text_x"]:.4f} {s["y"]:.4f} {TEXT_SIZE}')
    rows = []
    for r in layout["rows"]:
        rows.append(f'placeText {_ms(r["label"])} "ROW_{r["group"]}" -0.5 {r["y"] - 1.6:.4f} 0.3')
    row_cams = []
    for r in layout["rows"]:
        if not r["count"]:
            continue
        cx = r["width"] / 2
        dist = max(r["width"] * 0.55, 6.0)
        png = _p(row_dir / f"row-{r['group']}.png")
        row_cams.append(
            f'(local c = Targetcamera name:"Row_Camera" fov:50; '
            f'c.target = Targetobject pos:[{cx:.3f}, {r["y"]:.3f}, 0.8]; '
            f'c.pos = [{cx:.3f}, {r["y"] - dist:.3f}, {dist * 0.35:.3f}]; '
            f'render camera:c outputSize:[1920,1080] vfb:false outputfile:{png}; delete c)')
    for s in layout["slots"]:
        x0 = s["npm_x"]
        x1 = s["text_x"] + max(map(len, s["lines"])) * CHAR_W
        h = max(len(s["lines"]) * LINE_H, s["npm"]["size"][2], s["vpm"]["size"][2])
        cx = (x0 + x1) / 2
        dist = max((x1 - x0) * 1.15, h * 2.0) / (2 * math.tan(math.radians(25)))
        png = _p(row_dir / f"pos-{s['set_id']}.png")
        row_cams.append(
            f'(local c = Targetcamera name:"Pos_Camera" fov:50; '
            f'c.target = Targetobject pos:[{cx:.3f}, {s["y"]:.3f}, {h / 2:.3f}]; '
            f'c.pos = [{cx:.3f}, {s["y"] - dist:.3f}, {h / 2 + dist * 0.25:.3f}]; '
            f'render camera:c outputSize:[1600,900] vfb:false outputfile:{png}; delete c)')
    w, d = layout["extent"]
    dist = max(w, d) * 0.9
    return (BUILD.replace("@SLOTS@", "\n".join(lines)).replace("@ROWS@", "\n".join(rows))
            .replace("@ROWCAMS@", "\n".join(row_cams)).replace("@OUT@", _p(out_max))
            .replace("@RENDER@", _p(render_png)).replace("@REPORT@", _p(report))
            .replace("@CX@", f"{w / 2:.3f}").replace("@CY@", f"{d / 2:.3f}").replace("@DIST@", f"{dist:.3f}"))


def check_readback(readback: dict, layout: dict, tol=0.002) -> dict:
    """Counts and per-position checks of the fresh-process readback; raises on any miss."""
    if readback.get("ok") is not True:
        raise ShowcaseError("readback job failed")
    if str(readback.get("units")).lstrip("#") != "meters" or readback.get("scale") != 1.0:
        raise ShowcaseError(f"scene units {readback.get('units')} x {readback.get('scale')}")
    objs = readback.get("objects") or []
    names = [o["name"] for o in objs]
    if len(names) != len(set(names)):
        raise ShowcaseError("duplicate node names in scene")
    by = {o["name"]: o for o in objs}
    meshes = [o for o in objs if o["kind"] == "mesh"]
    texts = [o for o in objs if o["kind"] == "text" and o["name"].startswith("TXT_")]
    labels = [o for o in objs if o["kind"] == "text" and o["name"].startswith("ROW_")]
    others = [o["name"] for o in objs if o not in meshes and o not in texts and o not in labels]
    if others:
        raise ShowcaseError(f"unexpected nodes: {others}")
    problems = []
    for s in layout["slots"]:
        sid = s["set_id"]
        for prof, prefix in (("npm", "NPM__"), ("vpm", "VPM__")):
            hits = [o for o in meshes if o["name"].startswith(prefix + sid)]
            if len(hits) != 1:
                problems.append(f"{prefix}{sid}: {len(hits)} meshes")
                continue
            o = hits[0]
            if o["tris"] != s[prof]["triangles"]:
                problems.append(f"{o['name']}: tris {o['tris']} != {s[prof]['triangles']}")
            if any(abs(a - b) > tol for a, b in zip(o["size"], s[prof]["size"])):
                problems.append(f"{o['name']}: size {o['size']} != {s[prof]['size']}")
        t = by.get(f"TXT_{sid}")
        if t is None or t["kind"] != "text":
            problems.append(f"TXT_{sid}: missing")
        elif t["text"].split("\n") != s["lines"]:
            problems.append(f"TXT_{sid}: text differs")
    for r in layout["rows"]:
        if f"ROW_{r['group']}" not in by:
            problems.append(f"ROW_{r['group']}: missing")
    expected = 2 * len(layout["slots"])
    if len(meshes) != expected:
        problems.append(f"meshes {len(meshes)} != {expected}")
    if len(texts) != len(layout["slots"]):
        problems.append(f"texts {len(texts)} != {len(layout['slots'])}")
    if problems:
        raise ShowcaseError("readback: " + "; ".join(problems))
    return dict(meshes=len(meshes), texts=len(texts), row_labels=len(labels),
                triangles=sum(o["tris"] for o in meshes))


def _key(path: Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def check_output(out: Path, inputs) -> None:
    """The output folder is new and never an input, an input's folder or an ancestor of an input."""
    ok = _key(out)
    for item in inputs:
        ik, parent = _key(item), _key(Path(item).parent)
        if ik == ok or ik.startswith(ok + os.sep) or ok == parent or ok.startswith(parent + os.sep):
            raise ShowcaseError(f"output folder overlaps an input: {item}")


def _hash_of(report, sid, prof):
    return next(p[prof]["sha256"] for p in report["positions"] if p["set_id"] == sid)


def _run_job(job: Path, card: str, version="2026"):
    proc = subprocess.run([sys.executable, str(SCRIPTS / "dcc_batch.py"), "max", "--file", str(job),
                           "--card", card, "--timeout", "900", "--wait", "900", "--version", version],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2000)
    return proc


def _load_json(path: Path, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ShowcaseError(f"{what}: {exc}") from exc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the MAF showcase scene (#487)")
    ap.add_argument("--set", required=True, help="site-maf-set.json")
    ap.add_argument("--config", required=True, help="site-maf-showcase.config.json")
    ap.add_argument("--out", required=True, help="new versioned output folder (must not exist)")
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = _load_json(Path(args.set), "set report")
        config = _load_json(Path(args.config), "config")
        layout = plan(report, config)
        out = Path(args.out)
        inputs = [Path(args.set), Path(args.config)] + [Path(s[p]["fbx"]) for s in layout["slots"]
                                                       for p in ("npm", "vpm")]
        if report.get("out_dir"):
            inputs.append(Path(report["out_dir"]) / "site-maf-set.json")  # never write into the set folder
        check_output(out, inputs)
        if out.exists():
            raise ShowcaseError(f"output folder exists (versioned path, never overwritten): {out}")
        if args.plan_only:
            print(json.dumps(layout, ensure_ascii=False, indent=1))
            return 0
        out.mkdir(parents=True)
        (out / "renders").mkdir()
        (out / "plan.json").write_text(json.dumps(layout, ensure_ascii=False, indent=1), encoding="utf-8")
        scene = out / "maf-showcase.max"
        card = os.environ.get("HERMES_KANBAN_TASK", "maf-showcase")
        job = out / "build.ms"
        job.write_text(build_script(layout, scene, out / "renders" / "overview.png", out / "build.json",
                                    out / "renders"), encoding="utf-8-sig")
        proc = _run_job(job, card)
        built = _load_json(out / "build.json", "build report") if (out / "build.json").is_file() else {}
        if proc.returncode != 0 or built.get("ok") is not True:
            raise ShowcaseError("build failed: " + str(built.get("error")) + " " + (proc.stdout + proc.stderr)[-1500:])
        job = out / "readback.ms"
        job.write_text(READBACK.replace("@SCENE@", _p(scene)).replace("@REPORT@", _p(out / "readback.raw.json")),
                       encoding="utf-8-sig")
        proc = _run_job(job, card)
        if proc.returncode != 0:
            raise ShowcaseError("readback process failed: " + (proc.stdout + proc.stderr)[-1500:])
        counts = check_readback(_load_json(out / "readback.raw.json", "readback"), layout)
        changed = [s["set_id"] for s in layout["slots"] for p in ("npm", "vpm")
                   if sha256(Path(s[p]["fbx"])) != _hash_of(report, s["set_id"], p)]
        if changed:
            raise ShowcaseError(f"input FBX changed during the run: {changed}")
        result = dict(scene=scene.resolve().as_posix(), sha256=sha256(scene), readback=counts,
                      renders=sorted(p.resolve().as_posix() for p in (out / "renders").glob("*.png")),
                      set_ids=[s["set_id"] for s in layout["slots"]],
                      review_ids=[s["set_id"] for s in layout["slots"] if s["review"]])
        (out / "showcase.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    except ShowcaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
