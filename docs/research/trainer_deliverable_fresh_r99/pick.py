"""OBSERVE #99 scorer selection rule (candidate, NOT in tools/trainer): the --built path a run is scored with.

Pattern: new-case: docs/research/trainer_deliverable_fresh_r99 - OBSERVE #99 trainer practice series (research only).

Arm C (current behaviour): the `built/` directory (trainer.py refuses several FBX).
Arm D (H99): `built/deliverable.fbx` when that exact root file name exists, otherwise the `built/` directory.
"""
from pathlib import Path

NAME = "deliverable.fbx"


def built_arg(run_dir, arm):
    built = Path(run_dir) / "built"
    if arm == "D" and built.is_dir() and NAME in {p.name for p in built.iterdir() if p.is_file()}:
        return str(built / NAME)
    return str(built)
