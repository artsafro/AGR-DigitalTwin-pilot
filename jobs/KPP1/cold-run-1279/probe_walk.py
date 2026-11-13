"""Fail-closed probes of the walker on the cold-run-1279 checklist (#1279).

Pattern: new-case: measurement probe for a cold-run job.yaml (mutate one field, walk, expect not-pass + error).
Usage: uv run python jobs/KPP1/cold-run-1279/probe_walk.py . <new output dir>
"""
import json, subprocess, sys
from pathlib import Path

root = Path(sys.argv[1])
job = root / "jobs/KPP1/cold-run-1279/job.yaml"
src = job.read_text(encoding="utf-8")
H = "4d36ed15d2b74f2fb2efa3f6434db08f9b3c9b3f6e013bcac38ad96ba5dafb32"
cases = {
    "parts hash off by one nibble": src.replace(H, H[:-1] + "3"),
    "parts claimed pass without gate1": src.replace("    status: review\n    waits: user", "    status: pass"),
    "duplicated sources manifest row": src.replace(
        "- path: jobs/KPP1/sources.json\n", "- path: jobs/KPP1/sources.json\n  sha256: e772b3ff52b170a8fa86eff0013b3280a0aefce3906a0ce7842eeffc7c18ac9a\n  manifest: external-inputs/1\n- path: jobs/KPP1/sources.json\n", 1),
    "waits on a pass gate": src.replace("    status: pass\n    note: \"Cold run", "    status: pass\n    waits: user\n    note: \"Cold run"),
    "unknown waits value": src.replace("    waits: user", "    waits: someone"),
}
# F20 (RUN-LOG): a duplicated `inputs` row is accepted today; this probe is expected to print FAIL until fixed.
cases = {k: v for k, v in cases.items() if v is not None and v != src}
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
ok = 0
for i, (name, text) in enumerate(cases.items()):
    p = job.with_name(f"probe-{i}.yaml")
    p.write_text(text, encoding="utf-8", newline="\n")
    try:
        r = subprocess.run([sys.executable, "-m", "dt_ai.procedure", str(p.relative_to(root)).replace("\\", "/"), "--root", ".",
                            "--output", str(out / f"w{i}.json")], cwd=root, capture_output=True, text=True)
    finally:
        p.unlink()
    w = json.loads((out / f"w{i}.json").read_text(encoding="utf-8")) if (out / f"w{i}.json").exists() else None
    errs = [] if w is None else (w["errors"] + [e for g in w["gates"][:2] for e in g["errors"]])
    good = bool(r.returncode != 0 and (w is None or (not w["passed"] and errs)))
    ok += good
    print(f"{name}: rc={r.returncode} passed={None if w is None else w['passed']} errors={str(errs)[:110]} -> {'OK' if good else 'FAIL'}")
print(f"{ok}/{len(cases)}")
