"""Blender-only ``sources-dwg`` intake: verify a hash-bound DXF derivative of a DWG source (#1857).

Pattern: new-case: Autodesk-free DWG intake that accepts only a hash-bound DXF derivative and reads it back.

The trainer lane (#1855) runs ``oks-vpm`` without AutoCAD or Max. A DWG cannot be read there, so the
one supported forward path is an *intake derivative*: a DXF produced earlier by the unchanged AutoCAD
lane (``dwg_to_dxf.py``, receipt schema ``dwg-to-dxf/1``) and bound to the DWG by SHA-256. This tool
launches no process; it hashes, reads the DXF with ezdxf and hands it to ``plan_from_dxf.py``.

Shared command (skeleton ``sources-dwg``)::

    uv run python tools/methods/body/dxf_intake.py <source.dwg> <derivative.dxf> <provenance.json> <intake.json>
    uv run python tools/methods/body/plan_from_dxf.py extract <derivative.dxf> <plan.json> <report.json> ...

Provenance forms:
- ``dwg-to-dxf/1`` receipt with ``status: pass``: accepted when its ``source.sha256`` equals the DWG
  given now and its ``dxf.sha256`` equals the DXF given now (paths may differ; hashes bind).
- ``dxf-derivative/1`` manifest from a non-AutoCAD converter: accepted only when ``converter.name`` is
  in ``APPROVED_CONVERTERS``. The list is empty: no converter is approved yet, so such output is
  unverifiable and fails closed (an approval is a user decision).
- Anything else is unverifiable and fails.

Guarantees (each has a test in tests/methods/test_dxf_intake_1857.py):
- ``status`` is ``pass`` only when the provenance binds both current hashes, the DWG starts with the
  ``AC10`` magic, the ASCII DXF ends in ENDSEC/EOF, parses, did not change while read, has ``$INSUNITS`` = 4 (millimetres, what
  ``plan_from_dxf.py`` assumes) and a non-empty model space. Otherwise ``fail`` with ``reason`` and
  ``action`` (exit 3); a fail receipt has no ``inputs``, plan or body. Never a pass by default.
  ``passed`` is always ``false``: the intake is one gate, never a stage or model verdict.
- ``parity`` with the DWG is never claimed: it is ``not measured`` with the reason.
- The intake records the DWG and DXF SHA-256, units, ``$ACADVER``, the provenance SHA-256 and the
  measured plan/opening inputs (model-space layer and type counts, INSERT block names, block names
  that ``plan_from_dxf`` parses as opening symbols) plus the next ``plan_from_dxf.py`` command.
- A missing DWG, DXF or provenance, a wrong suffix, or unreadable provenance JSON is an error naming
  it and the forward path (exit 2, nothing written).
- The output must not exist and must not be any input (exit 4, nothing written). Inputs are never
  modified or deleted. No subprocess is started.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_BODY = Path(__file__).resolve().parent
if str(_BODY.parent) not in sys.path:
    sys.path.insert(0, str(_BODY.parent))
if str(_BODY) not in sys.path:
    sys.path.insert(0, str(_BODY))
from safe_write import Refused, guard_cli, publish_text  # noqa: E402

SCHEMA = "dxf-intake/1"
TOOL_REL = "tools/methods/body/dxf_intake.py"
RECEIPT_SCHEMA = "dwg-to-dxf/1"
DERIVATIVE_SCHEMA = "dxf-derivative/1"
APPROVED_CONVERTERS: frozenset[str] = frozenset()  # user decision required before adding one (#1857)
INSUNITS_MM = 4
DWG_MAGIC = b"AC10"
FORWARD_PATH = ("supply a DXF derivative made by the AutoCAD lane: uv run python tools/methods/body/dwg_to_dxf.py "
                "<source.dwg> <out.dxf> <receipt.json> (outside the trainer lane), then pass that DXF and receipt here")
__all__ = ["verify_dxf_derivative", "main", "APPROVED_CONVERTERS"]


class InputError(ValueError):
    pass


class Unverified(ValueError):
    def __init__(self, reason: str, action: str):
        super().__init__(reason)
        self.reason, self.action = reason, action


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_inputs(source: Path, dxf: Path, provenance: Path) -> None:
    for what, path, suffix in (("source DWG", source, ".dwg"), ("DXF derivative", dxf, ".dxf"),
                               ("provenance", provenance, ".json")):
        if not path.is_file():
            raise InputError(f"{what} {path} is missing; {FORWARD_PATH}")
        if path.suffix.lower() != suffix:
            raise InputError(f"{what} {path} is not {suffix}")


def _load_provenance(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"provenance {path} is not readable JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise InputError(f"provenance {path} is not a JSON object")
    return data


def _bind(prov: dict, dwg_sha: str, dxf_sha: str) -> dict:
    """Check the provenance binds the current DWG and DXF. Returns the provenance facts or raises Unverified."""
    kind = prov.get("receipt") or prov.get("schema")
    if kind == RECEIPT_SCHEMA:
        if prov.get("status") != "pass" or prov.get("returncode") != 0:
            raise Unverified(f"dwg-to-dxf receipt status is {prov.get('status')!r} "
                             f"(returncode {prov.get('returncode')!r}, reason {prov.get('reason')!r}), not pass",
                             FORWARD_PATH)
        src = (prov.get("source") or {}).get("sha256")
        after = prov.get("source_sha256_after")
        out = (prov.get("dxf") or {}).get("sha256")
        if not (isinstance(src, str) and isinstance(out, str)):
            raise Unverified("dwg-to-dxf receipt lacks source.sha256 or dxf.sha256", FORWARD_PATH)
        if after is not None and after != src:
            raise Unverified(f"dwg-to-dxf receipt source changed during conversion ({src} -> {after})", FORWARD_PATH)
        if src != dwg_sha:
            raise Unverified(f"stale DXF: derived from DWG sha256 {src}, the source given now is {dwg_sha}",
                             "re-run the AutoCAD lane on the current DWG: " + FORWARD_PATH)
        if out != dxf_sha:
            raise Unverified(f"DXF changed since conversion: receipt dxf sha256 {out}, file now {dxf_sha}",
                             "use the DXF the receipt names, unmodified, or " + FORWARD_PATH)
        return {"kind": RECEIPT_SCHEMA, "producer": "autocad-dxfout (dwg_to_dxf.py)",
                "command": prov.get("command"), "source_sha256": src, "dxf_sha256": out}
    if kind == DERIVATIVE_SCHEMA:
        name = (prov.get("converter") or {}).get("name") if isinstance(prov.get("converter"), dict) else None
        if name not in APPROVED_CONVERTERS:
            raise Unverified(f"unverifiable converter output: converter {name!r} is not approved "
                             f"(approved: {sorted(APPROVED_CONVERTERS) or 'none'})",
                             "ask Artem to approve the converter for sources-dwg, or " + FORWARD_PATH)
        src = (prov.get("source") or {}).get("sha256")
        out = (prov.get("dxf") or {}).get("sha256")
        if src != dwg_sha or out != dxf_sha:
            raise Unverified(f"derivative manifest hashes ({src}, {out}) do not match the DWG/DXF given now "
                             f"({dwg_sha}, {dxf_sha})", FORWARD_PATH)
        return {"kind": DERIVATIVE_SCHEMA, "producer": name, "source_sha256": src, "dxf_sha256": out}
    raise Unverified(f"unverifiable provenance: schema {kind!r} is neither {RECEIPT_SCHEMA} nor {DERIVATIVE_SCHEMA}",
                     FORWARD_PATH)


def _inputs(doc) -> dict:
    """Measured plan/opening inputs from model space (counts only; nothing is inferred)."""
    from plan_from_dxf import _parse_symbol, sheet_census

    census = sheet_census(doc)
    types: dict[str, int] = {}
    inserts: dict[str, int] = {}
    for entity in doc.modelspace():
        types[entity.dxftype()] = types.get(entity.dxftype(), 0) + 1
        if entity.dxftype() == "INSERT":
            inserts[entity.dxf.name] = inserts.get(entity.dxf.name, 0) + 1
    symbols = {name: n for name, n in inserts.items() if _parse_symbol(name) is not None}
    return {"model_entities": census["model_entities"], "model_layers": census["model_layers"],
            "entity_types": types, "layouts": census["layouts"], "viewports": len(census["viewports"]),
            "insert_blocks": inserts, "opening_symbol_blocks": symbols,
            "opening_symbol_inserts": sum(symbols.values())}


def verify_dxf_derivative(source: Path, dxf: Path, provenance: Path) -> dict:
    """Return the intake record (status pass/fail). Raises InputError for missing/wrong inputs."""
    source, dxf, provenance = Path(source), Path(dxf), Path(provenance)
    _check_inputs(source, dxf, provenance)
    prov = _load_provenance(provenance)
    dwg_sha, dxf_sha = _sha256(source), _sha256(dxf)
    record = {"schema": SCHEMA, "tool": TOOL_REL, "stage": "sources-dwg", "status": "fail", "passed": False,
              "source": {"path": str(source), "sha256": dwg_sha},
              "dxf": {"path": str(dxf), "sha256": dxf_sha},
              "provenance": {"path": str(provenance), "sha256": _sha256(provenance)},
              "parity": {"status": "not measured",
                         "reason": "a DWG cannot be read without Autodesk; parity is not inferred from an exit code"},
              "autodesk_launched": False}
    try:
        with open(source, "rb") as f:
            if f.read(4) != DWG_MAGIC:
                raise Unverified(f"{source} does not start with the DWG magic {DWG_MAGIC!r}", "supply the original DWG")
        record["provenance"].update(_bind(prov, dwg_sha, dxf_sha))
        import ezdxf
        try:
            # ezdxf can read a file with complete sections but a missing EOF marker.
            # The authorized DXFOUT lane emits ASCII, with both closing tags on their own lines.
            with dxf.open("rb") as f:
                f.seek(max(0, f.seek(0, 2) - 256))
                tail = f.read().rstrip().splitlines()
            if [line.strip() for line in tail[-4:]] != [b"0", b"ENDSEC", b"0", b"EOF"]:
                raise Unverified(f"DXF {dxf} does not parse as a complete DXF: missing terminal 0/EOF or ENDSEC",
                                 FORWARD_PATH)
            doc = ezdxf.readfile(dxf)
        except (OSError, ezdxf.DXFError, UnicodeDecodeError) as exc:
            raise Unverified(f"DXF {dxf} does not parse: {exc}"[:400], FORWARD_PATH) from exc
        if _sha256(dxf) != dxf_sha or _sha256(source) != dwg_sha:
            raise Unverified("an input changed while it was read", "re-run on a stable copy")
        header = doc.header
        units = header["$INSUNITS"] if "$INSUNITS" in header else None
        record["units"] = {"insunits": units, "measurement": header.get("$MEASUREMENT"),
                           "acadver": header.get("$ACADVER")}
        if units != INSUNITS_MM:
            raise Unverified(f"DXF $INSUNITS is {units!r}, plan_from_dxf.py needs {INSUNITS_MM} (millimetres)",
                             "supply a millimetre DXF; no unit is assumed")
        record["units"]["name"] = "mm"
        measured = _inputs(doc)
        if measured["model_entities"] == 0:
            raise Unverified("DXF model space is empty", FORWARD_PATH)
        record["inputs"] = measured
    except Unverified as exc:
        record.update(reason=exc.reason, action=exc.action)
        return record
    record.update(status="pass", reason=None,
                  next={"tool": "tools/methods/body/plan_from_dxf.py",
                        "command": ["uv", "run", "python", "tools/methods/body/plan_from_dxf.py", "extract", str(dxf),
                                    "<plan.json>", "<report.json>", "--map-file", "<layers.txt>", "--levels",
                                    "<z0,z1,...>", "--opening-insert", "centre"]})
    # ``passed`` stays False: intake is one gate, never the stage verdict of the body.
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("dxf", type=Path)
    parser.add_argument("provenance", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    try:
        guard_cli([args.source, args.dxf, args.provenance], [args.out])
        if args.out.exists():
            raise Refused(f"{args.out} exists; write to a new versioned path")
        record = verify_dxf_derivative(args.source, args.dxf, args.provenance)
    except Refused as exc:
        print(f"DXF_INTAKE refused: {exc}", file=sys.stderr)
        return 4
    except InputError as exc:
        print(f"DXF_INTAKE sources-dwg stop: {exc}", file=sys.stderr)
        return 2
    publish_text(args.out, json.dumps(record, ensure_ascii=False, indent=1))
    if record["status"] != "pass":
        print(f"DXF_INTAKE sources-dwg stop: {record['reason']}; action: {record['action']}", file=sys.stderr)
        return 3
    print(json.dumps({"status": "pass", "dwg_sha256": record["source"]["sha256"],
                      "dxf_sha256": record["dxf"]["sha256"], "units": record["units"]["name"],
                      "model_entities": record["inputs"]["model_entities"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
