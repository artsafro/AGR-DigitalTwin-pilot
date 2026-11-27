"""Replay #128 unchanged except for selecting the v006 rejection manifest."""
import json
from pathlib import Path
import subprocess
import sys

R128 = "5c15100ee5631e2f5d75e697e14e1977a6361f3d"
ADAPTER = "docs/research/autoresearch-npm-vpm-render-diff-r128/replay.py"
REJECT = {"drive_zip_sha256": {
    "0000_Nku_1.zip": "518b0b5e4e3ed49967a1d79b1731b7db06e2c17f658773e6c5c56c371589bd7e",
    "SM_Nku_1.zip": "1adaaa707234078a5b887756608bf05432458cf6ee3bcd6cd1f2764301376988",
}}


def main(out):
    pinned = subprocess.check_output(["git", "show", f"{R128}:{ADAPTER}"])
    ns = {"__name__": "r128_replay"}
    exec(compile(pinned, ADAPTER, "exec"), ns)
    git_blob = ns["git_blob"]

    def with_holdout(revision, path):
        blob = git_blob(revision, path)
        if (revision, path) != (ns["R127"], ns["RECEIPT"]):
            return blob
        reference = json.loads(blob)["packages"]["pilot-v010"]
        return json.dumps({"packages": {"pilot-v006": REJECT, "pilot-v010": reference}}).encode()

    ns["git_blob"] = with_holdout
    ns["main"](out)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
