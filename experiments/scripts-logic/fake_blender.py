"""Fake Blender for failure-mode probes (synthetic). Mode from FAKE_BLENDER_MODE:
ok | valid_exit7 | no_output | malformed | empty | hang.
Writes the promised output: last arg if it ends with .json (readback/faces), or request["result"]
when the last arg is a request.json (dt_ai build bridge)."""
import json
import os
import sys
import time
from pathlib import Path

mode = os.environ.get("FAKE_BLENDER_MODE", "ok")
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
target = None
if args:
    last = Path(args[-1])
    if last.name == "request.json" and last.is_file():
        target = Path(json.loads(last.read_text(encoding="utf-8"))["result"])
    elif last.suffix == ".json":
        target = last
body = json.dumps({"fake": True, "meshes": [], "faces": []})
if mode == "hang":
    time.sleep(120)
if target is not None and mode != "no_output":
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text({"malformed": "{not json", "empty": ""}.get(mode, body), encoding="utf-8")
print("fake blender", mode, file=sys.stderr)
sys.exit(7 if mode == "valid_exit7" else 0)
