"""Pre-export hygiene check: custom attributes, user-defined properties, map channel names (#547).

Pattern: new-case: pre-export scene-dump check derived from the team script
ClearCustomAttributesAndObjProp_010.ms (team-scripts audit #537); no entry in docs/domain/patterns/INDEX.md.

The team sweeps every node before export: it strips custom attributes (base object, node, modifiers,
materials) and User Defined properties, deletes map channels 2+ and renames map channel 1 to `UV`.
3ds Max keeps map channel names in the User Defined buffer as `MapChannel:N = name` lines (the lines
Tools > Channel Info reads), so the sweep keeps those lines when it clears the UDP.

This module only CHECKS a scene dump and reports findings; it never edits the scene or the dump.
`repair_plan` (CLI `--repair-out`, off by default) writes a separate cleanup plan for the scene side.

Scene dump (JSON): {"objects": [{"name": str,
    "custom_attributes": {"base": [str], "node": [str], "modifiers": [str], "materials": [str]},
    "user_props": str,            # getUserPropBuffer text
    "map_channels": [int]}]}      # supported map channels 1..99 (vertex channels 0, -1, -2 excluded)
Anything else (missing, extra or mistyped keys, duplicate names or channels) is an InputError.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path

from twinqa.report import Finding

ORIGIN = "team script ClearCustomAttributesAndObjProp_010.ms (team-scripts audit #537)"
UV_NAME = "UV"
CA_OWNERS = ("base", "node", "modifiers", "materials")
OBJECT_KEYS = ("name", "custom_attributes", "user_props", "map_channels")
MAX_MAP_CHANNEL = 99
CHECK_NAMES = ("no custom attributes", "no user-defined properties", "map channel 1 named UV",
               "no map channels 2+")
# Max matchPattern "MapChannel:*" plus an integer index, as udpMapChannelIndex in the team script.
_MAP_LINE = re.compile(r"^MapChannel:\s*(\d+)\s*=(.*)$", re.IGNORECASE)


class InputError(ValueError):
    """The scene dump is empty, partial or malformed; no verdict is possible."""


def parse_udp(buffer: str) -> tuple[dict[int, list[str]], list[str]]:
    """Split a UDP buffer into map channel names (every value per index, in order) and other lines."""
    names: dict[int, list[str]] = {}
    other: list[str] = []
    for raw in buffer.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _MAP_LINE.match(line)
        if m:
            names.setdefault(int(m.group(1)), []).append(m.group(2).strip())
        else:
            other.append(line)
    return names, other


def _validate(objects) -> None:
    if not isinstance(objects, list):
        raise InputError("scene objects must be a list")
    if not objects:
        raise InputError("scene dump has no objects")
    seen: set[str] = set()
    for i, obj in enumerate(objects):
        where = f"object #{i}"
        if not isinstance(obj, dict):
            raise InputError(f"{where} is not a mapping")
        missing = [k for k in OBJECT_KEYS if k not in obj]
        extra = sorted(set(obj) - set(OBJECT_KEYS))
        if missing or extra:
            raise InputError(f"{where}: missing keys {missing}, unsupported keys {extra}")
        name = obj["name"]
        if not isinstance(name, str) or not name.strip():
            raise InputError(f"{where}: name must be a non-empty string")
        if name in seen:
            raise InputError(f"duplicate object name {name!r}")
        seen.add(name)
        where = f"object {name!r}"
        ca = obj["custom_attributes"]
        if not isinstance(ca, dict) or set(ca) != set(CA_OWNERS):
            got = sorted(ca) if isinstance(ca, dict) else type(ca).__name__
            raise InputError(f"{where}: custom_attributes needs exactly {list(CA_OWNERS)}, got {got}")
        for owner in CA_OWNERS:
            if not isinstance(ca[owner], list) or not all(isinstance(n, str) for n in ca[owner]):
                raise InputError(f"{where}: custom_attributes.{owner} must be a list of strings")
        if not isinstance(obj["user_props"], str):
            raise InputError(f"{where}: user_props must be a string")
        chans = obj["map_channels"]
        if not isinstance(chans, list):
            raise InputError(f"{where}: map_channels must be a list")
        for ch in chans:
            if type(ch) is not int or not 1 <= ch <= MAX_MAP_CHANNEL:
                raise InputError(f"{where}: map channel {ch!r} is not an integer 1..{MAX_MAP_CHANNEL}")
        if len(set(chans)) != len(chans):
            raise InputError(f"{where}: duplicate map channels {chans}")


def _channel1_problem(obj: dict, names: dict[int, list[str]]) -> str | None:
    if 1 not in obj["map_channels"]:
        return "map channel 1 missing"
    values = names.get(1, [])
    if not values:
        return "unnamed (Max default '1:map')"
    if len(set(values)) > 1:
        return f"ambiguous names {values}"
    return None if values[0] == UV_NAME else repr(values[0])


def _extra_channels(obj: dict, names: dict[int, list[str]]) -> dict:
    chans = sorted(ch for ch in obj["map_channels"] if ch >= 2)
    extra_names = {str(ch): vals[-1] for ch, vals in sorted(names.items()) if ch >= 2}
    return {"channels": chans, "names": extra_names} if chans or extra_names else {}


def _finding(name, bad: dict, lines: list[str], expected: str, src: str) -> Finding:
    status = "fail" if bad else "pass"
    observed = f"{src}: " + ("; ".join(lines) if bad else "all objects clean")
    return Finding(name, status, observed, expected, [], f"{src}; rule origin: {ORIGIN}",
                   data={"objects": bad})


def hygiene_findings(objects: list[dict], src: str) -> list[Finding]:
    """Four findings over all objects (order = CHECK_NAMES). Never modifies `objects`."""
    _validate(objects)
    ca_bad, udp_bad, ch1_bad, extra_bad = {}, {}, {}, {}
    ca_lines, udp_lines, ch1_lines, extra_lines = [], [], [], []
    for obj in objects:
        name = obj["name"]
        names, other = parse_udp(obj["user_props"])
        owners = {o: list(obj["custom_attributes"][o]) for o in CA_OWNERS if obj["custom_attributes"][o]}
        if owners:
            ca_bad[name] = owners
            ca_lines += [f"{name}.{o}: {', '.join(v)}" for o, v in owners.items()]
        if other:
            udp_bad[name] = other
            udp_lines.append(f"{name}: {other}")
        problem = _channel1_problem(obj, names)
        if problem:
            ch1_bad[name] = problem
            ch1_lines.append(f"{name}: {problem}")
        extra = _extra_channels(obj, names)
        if extra:
            extra_bad[name] = extra
            orphans = {int(k): v for k, v in extra["names"].items() if int(k) not in extra["channels"]}
            parts = [f"channels {extra['channels']}"] if extra["channels"] else []
            parts += [f"orphan names {orphans}"] if orphans else []
            extra_lines.append(f"{name}: {', '.join(parts)}")
    return [
        _finding(CHECK_NAMES[0], ca_bad, ca_lines,
                 "no custom attributes on base object, node, modifiers or materials", src),
        _finding(CHECK_NAMES[1], udp_bad, udp_lines,
                 "User Defined buffer holds only MapChannel:N name lines", src),
        _finding(CHECK_NAMES[2], ch1_bad, ch1_lines, "map channel 1 present and named 'UV'", src),
        _finding(CHECK_NAMES[3], extra_bad, extra_lines,
                 "only map channel 1 (one UV channel, reg p.31 §2.1.1); no names for channels 2+", src),
    ]


def repair_plan(objects: list[dict]) -> dict:
    """Scene-side cleanup recipe per object plus the expected cleaned dump. Never modifies `objects`."""
    _validate(objects)
    entries = []
    for obj in objects:
        cleaned = copy.deepcopy(obj)
        names, other = parse_udp(obj["user_props"])
        actions, unrepairable = [], []
        for owner in CA_OWNERS:
            if obj["custom_attributes"][owner]:
                actions.append({"action": "remove_custom_attributes", "owner": owner,
                                "names": list(obj["custom_attributes"][owner])})
                cleaned["custom_attributes"][owner] = []
        if other:
            actions.append({"action": "clear_user_defined_lines", "lines": other})
        extra = _extra_channels(obj, names)
        if extra:
            actions.append({"action": "delete_map_channels", **copy.deepcopy(extra)})
            cleaned["map_channels"] = [ch for ch in obj["map_channels"] if ch < 2]
        problem = _channel1_problem(obj, names)
        kept = names.get(1, [])
        if problem == "map channel 1 missing":
            unrepairable.append("map channel 1 missing: no UV to rename")
        elif problem:
            actions.append({"action": "rename_map_channel_1", "from": kept[-1] if kept else None, "to": UV_NAME})
            kept = [UV_NAME]
        cleaned["user_props"] = "".join(f"MapChannel:1 = {v}\r\n" for v in kept[-1:])
        entries.append({"name": obj["name"], "actions": actions, "unrepairable": unrepairable,
                        "cleaned": cleaned})
    return {"origin": ORIGIN, "objects": entries}


def load_scene(path: Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read scene dump {path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"objects"}:
        raise InputError(f"{path}: expected exactly {{'objects': [...]}}")
    _validate(data["objects"])
    return data["objects"]


def _same(a: Path, b: Path) -> bool:
    if os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b)):
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def _write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".partial")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m twinqa.export_hygiene", description="Pre-export hygiene check (#547)")
    ap.add_argument("scene", type=Path, help="scene dump JSON")
    ap.add_argument("--report", type=Path, help="write findings JSON here")
    ap.add_argument("--repair-out", type=Path,
                    help="opt-in: write the scene-side cleanup plan here (the check itself never repairs)")
    args = ap.parse_args(argv)
    outputs = [p for p in (args.report, args.repair_out) if p is not None]
    files = [args.scene, *outputs]
    files += [p.with_name(p.name + ".partial") for p in outputs]
    for i, a in enumerate(files):
        for b in files[i + 1:]:
            if _same(a, b):
                print(f"error: {a} and {b} are the same file", file=sys.stderr)
                return 2
    try:
        objects = load_scene(args.scene)
        findings = hygiene_findings(objects, str(args.scene))
        plan = repair_plan(objects) if args.repair_out else None
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for f in findings:
        print(f"{f.status:5} {f.name}: {f.observed}")
    if args.report:
        _write(args.report, {"source": str(args.scene), "origin": ORIGIN,
                             "findings": [asdict(f) for f in findings]})
    if plan is not None:
        _write(args.repair_out, {"source": str(args.scene), **plan})
    return 1 if any(f.status != "pass" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
