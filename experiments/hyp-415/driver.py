"""Reproduce #415: per-file PNG decode isolation A/B, matrix, verify. No production writes.

Arms: A = production ``twinqa.png``; B = ``candidate.py`` (OSError isolation at the
existing ``pixels()`` call sites). All PNGs/ZIPs are synthetic, generated in memory with
the report's chunk technique; real profiles come from ``load_profiles()``.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "qa"))
sys.path.insert(0, str(HERE))
os.chdir(ROOT)
os.environ.setdefault(
    "TWINQA_REGULATION_PDF",
    str((ROOT / "standards" / "source" / "Rasporyajenies19012026trebovaniya(2).pdf").resolve()),
)

from PIL import Image, ImageFile  # noqa: E402

ImageFile.LOAD_TRUNCATED_IMAGES = False

import twinqa.png as png  # noqa: E402
from twinqa.png import SIGNATURE, png_facts  # noqa: E402
from twinqa.profiles import load_profiles  # noqa: E402
import validate_package as vp  # noqa: E402
import candidate as cand  # noqa: E402

PROFILES = load_profiles()
TESTS = ["tests/qa/test_validator.py", "tests/qa/test_png_fixed_field_errors.py",
         "tests/twinqa/test_png_v007_findings.py"]
SOURCES = ["src/twinqa/png.py", "tools/qa/validate_package.py", "src/twinqa/report.py",
           "src/twinqa/profiles.py", "src/twinqa/bundle.py"] + TESTS
BASETEMP = "C:/x/t_e5238ec6"
os.makedirs(BASETEMP, exist_ok=True)


# --------------------------------------------------------------------------- helpers
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def filehash(path) -> str:
    return sha(Path(path).read_bytes())


def chunk(kind: bytes, body: bytes = b"") -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def make_png(side: int, ct: int = 2, transparency: bool = False) -> bytes:
    pixel = {2: b"\x12\x34\x56", 6: b"\x12\x34\x56\x80", 3: b"\x00"}[ct]
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, ct, 0, 0, 0))
    extra = chunk(b"PLTE", b"\x12\x34\x56") if ct == 3 else b""
    if transparency:
        extra += chunk(b"tRNS", b"\x00")
    raw = (b"\x00" + pixel * side) * side
    return SIGNATURE + ihdr + extra + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND")


def corrupt(side: int, variant: str) -> bytes:
    ihdr = make_png(side)[8:33]
    if variant == "ihdr-only":
        return SIGNATURE + ihdr
    if variant == "no-idat":
        return SIGNATURE + ihdr + chunk(b"IEND")
    if variant == "bad-zlib":
        return SIGNATURE + ihdr + chunk(b"IDAT", b"not-zlib") + chunk(b"IEND")
    raise ValueError(variant)


def facts_repr(facts):
    d = asdict(facts)
    d["has_alpha"] = facts.has_alpha
    return d


def findings_repr(fs):
    return [asdict(f) for f in fs]


def sets_repr(sets):
    return {f"{s}/{u}": {k: facts_repr(v) for k, v in sorted(m.items())}
            for (s, u), m in sorted(sets.items())}


def outcome(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        return {"ok": False,
                "exception": type(exc).__module__ + "." + type(exc).__name__,
                "message": re.sub(r"0x[0-9A-Fa-f]+", "<addr>", str(exc))}


def pillow_decode(data):
    try:
        with Image.open(BytesIO(data)) as im:
            im.load()
            return {"ok": True, "mode": im.mode, "size": list(im.size)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False,
                "exception": type(exc).__module__ + "." + type(exc).__name__,
                "message": re.sub(r"0x[0-9A-Fa-f]+", "<addr>", str(exc))}


def run_arm(arm, kind, mapping, prefix=None):
    if arm == "A":
        fn = png.npm_texture_findings if kind == "npm" else png.vpm_texture_findings
    else:
        fn = cand.npm_texture_findings if kind == "npm" else cand.vpm_texture_findings
    profile = PROFILES.npm if kind == "npm" else PROFILES.vpm
    if kind == "npm":
        return fn(mapping, profile)
    return fn(mapping, profile, prefix)


def wrap_arm(arm, kind, mapping, prefix=None):
    def call():
        result = run_arm(arm, kind, mapping, prefix)
        if kind == "npm":
            return {"findings": findings_repr(result), "sets": {}}
        return {"findings": findings_repr(result[0]), "sets": sets_repr(result[1])}
    return outcome(call)


# --------------------------------------------------------------------------- freeze
def collect_inventory():
    env = dict(os.environ, HYP415_MODE="A", HYP415_REPORT=str(HERE / "inventory.json"))
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), str(ROOT), str(ROOT / "src"),
                                         str(ROOT / "tools" / "qa"), env.get("PYTHONPATH", "")])
    cmd = ["env", "-u", "MSYS_NO_PATHCONV", "-u", "MSYS2_ARG_CONV_EXCL",
           "uv", "run", "pytest", "-q", "-p", "no:cacheprovider",
           f"--basetemp={BASETEMP}/inv", "-p", "evidence_plugin", "--collect-only"] + TESTS
    result = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=400)
    with (HERE / "inventory.log").open("w", encoding="utf-8") as f:
        f.write(result.stdout)
    return result.returncode, json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))["nodes"]


def freeze():
    code, nodes = collect_inventory()
    assert code == 0
    predictions = {
        "unchanged_tests": {
            "metric": "3 focused test files unchanged",
            "inputs": TESTS,
            "baseline": "326 passed",
            "rejection_threshold": "0 new failure/skip/deselection/node-id/outcome difference",
            "prediction": "pass (identical)",
        },
        "successful_return_parity": {
            "metric": "complete ordered findings + map facts for successful-return fixtures",
            "baseline": "production output",
            "rejection_threshold": "0 complete-output diff; 0 new 'PNG readable' on controls",
            "prediction": "pass (byte-identical)",
        },
        "decode_error_isolation": {
            "metric": "18 corrupt decode inputs (NPM 128 / VPM 256 / VPM 2048 x 3 variants)",
            "baseline": "escapes OSError (no findings returned)",
            "rejection_threshold": "0 escapes under B; 0 retained maps; 0 lost sibling findings; 0 aggregate pass",
            "prediction": "B returns per-file 'PNG readable' and excludes map from sets",
        },
        "mixed_package_continuation": {
            "metric": "VPM 3 broken roles x 2 insertion orders + NPM broken placeholder + unaffected RGBA sibling",
            "baseline": "escapes OSError (no findings returned)",
            "rejection_threshold": "broken member has filename fail; excluded from sets; sibling findings survive; no pass",
            "prediction": "B isolates broken member and continues",
        },
        "outer_validate": {
            "metric": "outer NPM single-PNG + VPM ZIP validate() x 2 repetitions",
            "baseline": "escapes OSError (no report)",
            "rejection_threshold": "0 missing reports; 0 passed=True; 0 strict-JSON failure",
            "prediction": "B returns report, passed=False, strict JSON",
        },
        "exception_propagation": {
            "metric": "MemoryError / RuntimeError / TypeError injected at pixels() boundary",
            "baseline": "propagates",
            "rejection_threshold": "0 swallowed under B",
            "prediction": "B propagates all three",
        },
    }
    frozen = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "main": subprocess.check_output(["git", "rev-parse", "main"], text=True).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "pillow": Image.__version__,
        "sources": {p: filehash(ROOT / p) for p in SOURCES},
        "profiles_pdf_sha256": PROFILES.pdf_sha256,
        "profiles_pdf_verified": PROFILES.pdf_verified,
        "predictions": predictions,
        "experiment_hashes": {p.name: filehash(p) for p in sorted(HERE.glob("*.py"))},
        "nodes": nodes,
        "frozen_at_unix": time.time(),
    }
    write("frozen.json", frozen)
    print("Frozen", len(nodes or []), "nodes", flush=True)


# --------------------------------------------------------------------------- pytest
def pytest_run(mode, name):
    env = dict(os.environ, HYP415_MODE=mode, HYP415_REPORT=str(HERE / (name + ".json")))
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), str(ROOT), str(ROOT / "src"),
                                         str(ROOT / "tools" / "qa"), env.get("PYTHONPATH", "")])
    cmd = ["env", "-u", "MSYS_NO_PATHCONV", "-u", "MSYS2_ARG_CONV_EXCL",
           "uv", "run", "pytest", "-q", "-p", "no:cacheprovider",
           f"--basetemp={BASETEMP}/{mode.lower()}", "-p", "evidence_plugin"] + TESTS
    result = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=400)
    with (HERE / (name + ".log")).open("w", encoding="utf-8") as f:
        f.write(result.stdout)
    print(result.stdout.splitlines()[-1] if result.stdout else "", flush=True)
    return result.returncode


def run_arm_tests(mode):
    assert pytest_run(mode, "affected-" + mode) == 0


# --------------------------------------------------------------------------- matrix
def decode_cases():
    cases = []
    for variant in ("ihdr-only", "no-idat", "bad-zlib"):
        cases.append({"id": f"npm-128-{variant}", "kind": "npm", "name": "probe.png",
                      "data": corrupt(128, variant)})
        for role in ("Diffuse", "ERM", "Normal"):
            cases.append({"id": f"vpm-256-{role}-{variant}", "kind": "vpm", "role": role,
                          "name": f"T_Probe_{role}_1.1001.png", "data": corrupt(256, variant)})
        cases.append({"id": f"vpm-2048-ERM-{variant}", "kind": "vpm", "role": "ERM",
                      "name": "T_Probe_ERM_1.1001.png", "data": corrupt(2048, variant)})
        cases.append({"id": f"vpm-2048-Normal-{variant}", "kind": "vpm", "role": "Normal",
                      "name": "T_Probe_Normal_1.1001.png", "data": corrupt(2048, variant)})
    return cases


def header_controls():
    return [
        {"id": "npm-256-valid", "kind": "npm", "name": "probe.png", "data": make_png(256)},
        {"id": "npm-2048-valid", "kind": "npm", "name": "probe.png", "data": make_png(2048)},
        {"id": "vpm-diffuse-2048-valid", "kind": "vpm", "role": "Diffuse",
         "name": "T_Probe_Diffuse_1.1001.png", "data": make_png(2048)},
    ]


def success_controls():
    pngs256 = {f"T_Probe_{r}_1.1001.png": make_png(256) for r in ("Diffuse", "ERM", "Normal")}
    pngs2048 = {f"T_Probe_{r}_1.1001.png": make_png(2048) for r in ("Diffuse", "ERM", "Normal")}
    return [
        {"id": "npm-128-valid-placeholder", "kind": "npm", "mapping": {"probe.png": make_png(128)}},
        {"id": "vpm-256-valid-triplet", "kind": "vpm", "mapping": pngs256, "prefix": "T_Probe"},
        {"id": "vpm-2048-valid-triplet", "kind": "vpm", "mapping": pngs2048, "prefix": "T_Probe"},
    ]


def vpm_mixed(role_to_break, variant="bad-zlib"):
    mapping = {
        "T_Probe_Diffuse_1.1001.png": make_png(256),
        "T_Probe_ERM_1.1001.png": make_png(256),
        "T_Probe_Normal_1.1001.png": make_png(256),
        "T_Probe_Diffuse_2.1001.png": make_png(256),
        "T_Probe_ERM_2.1001.png": make_png(256, ct=6),  # unaffected RGBA ERM
        "T_Probe_Normal_2.1001.png": make_png(256),
    }
    mapping[f"T_Probe_{role_to_break}_1.1001.png"] = corrupt(256, variant)
    return mapping


def npm_mixed(variant="bad-zlib"):
    return {"a_broken.png": corrupt(128, variant), "z_good.png": make_png(256, ct=6)}


def matrix():
    rows = []
    for case in decode_cases():
        mapping = {case["name"]: case["data"]}
        before = bytes(case["data"])
        record = {
            "id": case["id"], "kind": case["kind"], "name": case["name"],
            "sha256": sha(case["data"]),
            "facts": outcome(lambda: facts_repr(png_facts(case["name"], case["data"]))),
            "pillow": pillow_decode(case["data"]),
            "A": wrap_arm("A", case["kind"], mapping, "T_Probe"),
            "B": wrap_arm("B", case["kind"], mapping, "T_Probe"),
            "bytes_unchanged": case["data"] == before,
        }
        rows.append(record)

    for case in header_controls():
        mapping = {case["name"]: case["data"]}
        before = bytes(case["data"])
        a = wrap_arm("A", case["kind"], mapping, "T_Probe")
        b = wrap_arm("B", case["kind"], mapping, "T_Probe")
        rows.append({"id": case["id"], "kind": case["kind"], "name": case["name"],
                     "sha256": sha(case["data"]), "A": a, "B": b,
                     "A_equals_B": a == b, "bytes_unchanged": case["data"] == before})

    for case in success_controls():
        mapping = dict(case["mapping"])
        snapshot = {n: bytes(d) for n, d in mapping.items()}
        a = wrap_arm("A", case["kind"], mapping, case.get("prefix", "T_Probe"))
        b = wrap_arm("B", case["kind"], mapping, case.get("prefix", "T_Probe"))
        rows.append({"id": case["id"], "kind": case["kind"], "A": a, "B": b,
                     "A_equals_B": a == b,
                     "bytes_unchanged": all(mapping[n] == snapshot[n] for n in snapshot)})

    for role in ("Diffuse", "ERM", "Normal"):
        mapping = vpm_mixed(role)
        order2 = dict(reversed(list(mapping.items())))
        for order_name, m in (("order1", mapping), ("order2", order2)):
            snapshot = {n: bytes(d) for n, d in m.items()}
            a = wrap_arm("A", "vpm", m, "T_Probe")
            b = wrap_arm("B", "vpm", m, "T_Probe")
            rows.append({"id": f"vpm-mixed-{role}-{order_name}", "kind": "vpm",
                         "broken": f"T_Probe_{role}_1.1001.png", "A": a, "B": b,
                         "bytes_unchanged": all(m[n] == snapshot[n] for n in snapshot)})

    npm_map = npm_mixed()
    npm_map2 = dict(reversed(list(npm_map.items())))
    for order_name, m in (("order1", npm_map), ("order2", npm_map2)):
        snapshot = {n: bytes(d) for n, d in m.items()}
        a = wrap_arm("A", "npm", m)
        b = wrap_arm("B", "npm", m)
        rows.append({"id": f"npm-mixed-{order_name}", "kind": "npm", "A": a, "B": b,
                     "bytes_unchanged": all(m[n] == snapshot[n] for n in snapshot)})

    rows += exception_propagation()
    rows += outer_validate()
    write("matrix.json", {"rows": rows, "count": len(rows),
                          "delivery_passed": False})
    print("matrix rows:", len(rows), flush=True)


def exception_propagation():
    rows = []
    for exc_name, factory in (("MemoryError", lambda: MemoryError("boom")),
                              ("RuntimeError", lambda: RuntimeError("boom")),
                              ("TypeError", lambda: TypeError("boom"))):
        for arm, mod in (("A", png), ("B", cand)):
            original = mod.pixels

            def raiser(data, _factory=factory):
                raise _factory()

            mod.pixels = raiser
            try:
                for kind, mapping, prefix in (("npm", {"probe.png": make_png(128)}, None),
                                              ("vpm", {"T_Probe_Diffuse_1.1001.png": make_png(256)}, "T_Probe")):
                    res = wrap_arm(arm, kind, mapping, prefix)
                    propagated = (not res["ok"]) and res["exception"].endswith("." + exc_name)
                    rows.append({"id": f"exc-{arm}-{kind}-{exc_name}", "arm": arm, "kind": kind,
                                 "exception": exc_name, "propagated": propagated,
                                 "outcome": res})
            finally:
                mod.pixels = original
    return rows


def outer_validate():
    rows = []
    tmp = Path(BASETEMP) / "outer"
    for rep in (1, 2):
        for arm in ("A", "B"):
            cand.install(arm)
            sub = tmp / f"{arm}-{rep}"
            sub.mkdir(parents=True, exist_ok=True)
            npm_path = sub / "probe.png"
            npm_path.write_bytes(corrupt(128, "bad-zlib"))
            rows.append(_outer_one("npm", arm, rep, npm_path, "npm"))

            zip_path = sub / "SM_Probe.zip"
            with zipfile.ZipFile(zip_path, "w") as z:
                for name, data in vpm_mixed("Diffuse").items():
                    z.writestr(name, data)
            rows.append(_outer_one("vpm", arm, rep, zip_path, "vpm"))
    cand.install("A")
    return rows


def _outer_one(kind, arm, rep, path, profile_kind):
    stage_id = "V006" if profile_kind == "npm" else "V007"
    try:
        report = vp.validate(path, profile_kind, PROFILES)
        stage = next(s for s in report.stages if s.id == stage_id)
        payload = report.to_dict()
        json_ok = bool(json.dumps(payload, allow_nan=False))
        return {"id": f"outer-{kind}-{arm}-rep{rep}", "kind": kind, "arm": arm, "rep": rep,
                "report_returned": True, "passed": report.passed,
                "exit_code": report.exit_code, "stage_status": stage.status,
                "stage_findings": findings_repr(stage.findings),
                "json_serializable_strict": json_ok}
    except Exception as exc:  # noqa: BLE001
        return {"id": f"outer-{kind}-{arm}-rep{rep}", "kind": kind, "arm": arm, "rep": rep,
                "report_returned": False,
                "exception": type(exc).__module__ + "." + type(exc).__name__,
                "message": re.sub(r"0x[0-9A-Fa-f]+", "<addr>", str(exc))}


# --------------------------------------------------------------------------- verify
def verify():
    frozen = load("frozen.json")
    assert all(filehash(ROOT / p) == h for p, h in frozen["sources"].items())
    assert all(filehash(HERE / name) == h for name, h in frozen["experiment_hashes"].items())
    a = load("affected-A.json")
    b = load("affected-B.json")
    inventory_ok = a["nodes"] == b["nodes"] == frozen["nodes"]
    tests_ok = a["outcomes"] == b["outcomes"] and a["exitstatus"] == b["exitstatus"] == 0

    rows = load("matrix.json")["rows"]
    decode_rows = [r for r in rows if r.get("facts") is not None]
    parity_rows = [r for r in rows if r.get("A_equals_B") is not None]
    mixed_rows = [r for r in rows if "mixed" in r["id"]]
    outer_rows = [r for r in rows if r.get("id", "").startswith("outer-")]
    exc_rows = [r for r in rows if r.get("id", "").startswith("exc-")]

    # decode isolation: A escapes OSError, B returns PNG readable + no retained map
    decode_violations = []
    for r in decode_rows:
        a_escapes = (not r["A"]["ok"]) and (
            r["A"]["exception"].endswith("OSError")
            or r["A"]["exception"].endswith("UnidentifiedImageError"))
        b_ok = r["B"]["ok"]
        b_findings = r["B"]["value"]["findings"] if b_ok else []
        names = [f["name"] for f in b_findings]
        b_has_readable = "PNG readable" in names
        b_has_pass = any(f["status"] == "pass" for f in b_findings)
        b_sets = r["B"]["value"]["sets"] if b_ok else {}
        b_retained = any(r["name"] in m for m in b_sets.values())
        facts_ok = r["facts"]["ok"]
        if not (a_escapes and b_ok and b_has_readable and not b_has_pass
                and not b_retained and facts_ok and r["bytes_unchanged"]):
            decode_violations.append({"id": r["id"], "a_escapes": a_escapes,
                                      "b_ok": b_ok, "b_has_readable": b_has_readable,
                                      "b_has_pass": b_has_pass, "b_retained": b_retained,
                                      "facts_ok": facts_ok})

    parity_violations = [r["id"] for r in parity_rows if not r["A_equals_B"]]

    mixed_violations = []
    for r in mixed_rows:
        b_ok = r["B"]["ok"]
        if r["kind"] == "npm":
            findings = r["B"]["value"]["findings"] if b_ok else []
            names = [f["name"] for f in findings]
            no_alpha_survives = any(f["name"] == "no alpha" for f in findings)
            readable = [f for f in findings if f["name"] == "PNG readable"]
            pass_present = any(f["status"] == "pass" for f in findings)
            if not (b_ok and len(readable) == 1 and no_alpha_survives and not pass_present):
                mixed_violations.append(r["id"])
        else:
            findings = r["B"]["value"]["findings"] if b_ok else []
            sets = r["B"]["value"]["sets"] if b_ok else {}
            names = [f["name"] for f in findings]
            readable = [f for f in findings if f["name"] == "PNG readable"]
            broken = r["broken"]
            broken_kind = broken.split("_")[2]  # T_Probe_<role>_...
            slot1 = sets.get("1/1001", {})
            retained = broken_kind in slot1
            sibling_alpha = any(f["name"] == "no alpha in ERM/Normal" for f in findings)
            missing_finding = any(f["name"] == "map set" and f"missing ['{broken_kind}']" in f["observed"]
                                  for f in findings)
            pass_present = any(f["status"] == "pass" for f in findings)
            if not (b_ok and len(readable) == 1 and not retained and sibling_alpha
                    and missing_finding and not pass_present and r["bytes_unchanged"]):
                mixed_violations.append(r["id"])

    outer_violations = []
    for r in outer_rows:
        arm = r["arm"]
        if arm == "A":
            if r["report_returned"]:
                outer_violations.append({"id": r["id"], "why": "A should escape"})
        else:
            if not (r["report_returned"] and r["passed"] is False
                    and r["json_serializable_strict"] and r["stage_status"] == "fail"):
                outer_violations.append({"id": r["id"], "why": "B report contract"})
    # two B reports per kind must be identical
    b_outer = [r for r in outer_rows if r["arm"] == "B"]
    by_kind = {}
    for r in b_outer:
        by_kind.setdefault(r["kind"], []).append(
            {"stage_findings": r.get("stage_findings"), "passed": r.get("passed"),
             "exit_code": r.get("exit_code")})
    for kind, reps in by_kind.items():
        if len(set(json.dumps(x, sort_keys=True) for x in reps)) != 1:
            outer_violations.append({"id": f"outer-{kind}", "why": "repetitions differ"})

    exc_violations = [r["id"] for r in exc_rows if not r["propagated"]]

    verdict = "REJECTED"
    if not inventory_ok or not tests_ok:
        verdict = "REJECTED"
    elif decode_violations or parity_violations or mixed_violations or outer_violations or exc_violations:
        verdict = "REJECTED"
    elif (len(decode_rows) != 18 or len(mixed_rows) != 8 or len(outer_rows) != 8
          or len(exc_rows) != 12):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "CONFIRMED"

    result = {
        "verdict": verdict,
        "delivery_passed": False,
        "inventory_unchanged": inventory_ok,
        "focused_tests_identical": tests_ok,
        "node_count": len(a["nodes"]),
        "decode_rows": len(decode_rows), "decode_violations": decode_violations,
        "parity_violations": parity_violations,
        "mixed_rows": len(mixed_rows), "mixed_violations": mixed_violations,
        "outer_rows": len(outer_rows), "outer_violations": outer_violations,
        "exc_rows": len(exc_rows), "exc_violations": exc_violations,
        "rejection_criteria_1_inventory_ok": inventory_ok,
        "rejection_criteria_2_parity_ok": not parity_violations,
        "rejection_criteria_3_decode_ok": not decode_violations and not mixed_violations,
        "rejection_criteria_4_outer_ok": not outer_violations,
        "rejection_criteria_5_exc_ok": not exc_violations,
    }
    write("verdict.json", result)
    print(verdict, flush=True)


# --------------------------------------------------------------------------- io
def write(name, value):
    path = HERE / name
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["freeze", "A", "B", "matrix", "verify"])
    args = parser.parse_args()
    if args.stage == "freeze":
        freeze()
    elif args.stage in ("A", "B"):
        freeze() if not (HERE / "frozen.json").exists() else None
        run_arm_tests(args.stage)
    elif args.stage == "matrix":
        matrix()
    else:
        verify()
