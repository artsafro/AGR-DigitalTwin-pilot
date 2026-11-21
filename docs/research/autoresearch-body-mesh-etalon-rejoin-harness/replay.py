"""Replay standing #26 on recorded #1618 raw/rejoin pairs, not live scenes."""
import hashlib
import json
from pathlib import Path
from runpy import run_path
from statistics import median
import sys

import numpy as np


FIXTURE = (
    ("01", 1, "r2", 262.64, 7733, "e7bb542f36ba390dc409145c04539b63785d0c0d26bc7ee67d20d79ba4ab5fbb", "413515339be03d1aa8eb88d23c487ce81f1605eced51d3b822d2919141acefb1"),
    ("02", 2, "r4", 244.64, 1589, "79838f9ebf6783af3d22e3fb68a0b3f28a383ccc300d3e148493646ace28b802", "50df5fb7252078a3fc1edc9076b9e0043051f897bb3aa363b2014b404e6f8d0d"),
    ("02", 3, "r1", 262.64, 1873, "2a42c8a80967df071bb8e237b5d729b7051b87a0a7c4abe888c8d6d6bad04a9c", "dc389b008673016871591e1cb42f151379b63aa2ffe271590c52b3009a7d4a13"),
)
LOW = 217.64
TARGET = 0.10


def require_hash(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"input hash mismatch: {path}: {actual} != {expected}")


def measure(npz_root, json_root):
    faces_of = run_path(str(Path(__file__).resolve().parents[1] / "body-training-1619/band_compare.py"))["faces_of"]
    rows = {}
    for group, k, revision, high, known_tris, npz_hash, band_hash in FIXTURE:
        source = npz_root / f"g22_{group}/SM_Garibaldi_22_{k:03}_Main.npz"
        band = json_root / f"{revision}/etalon_k{k}.mq.json"
        require_hash(source, npz_hash)
        require_hash(band, band_hash)
        expected = json.loads(band.read_bytes())["objects"][0]
        pairs = []
        for _ in range(3):
            with np.load(source, allow_pickle=False) as dump:
                cropped = []
                for vk, nk, ik in (("verts", "fn", "fi"), ("jverts", "jn", "ji")):
                    verts = dump[vk]
                    in_band = (LOW - 0.01 <= verts[:, 2]) & (verts[:, 2] <= high + 0.01)
                    faces = [f for f in faces_of({"jn": dump[nk], "ji": dump[ik]}) if in_band[f].all()]
                    cropped.append((verts, faces))
                (_, raw), (verts, joined) = cropped
                used = sorted({i for f in joined for i in f})
                remap = {old: new for new, old in enumerate(used)}
                if (verts[used].round(6).tolist() != expected["verts"] or
                        [[remap[i] for i in f] for f in joined] != expected["faces"]):
                    raise ValueError(f"#25 geometry parity failure: k{k}")
                tri = sum(len(f) == 3 for f in joined)
                if not raw or any(len(f) != 3 for f in raw) or tri != known_tris:
                    raise ValueError(f"raw/rejoin triangle parity failure: k{k}")
                pairs.append({"raw_triangles": len(raw), "rejoined_triangles": tri, "ratio": tri / len(raw)})
        require_hash(source, npz_hash)
        require_hash(band, band_hash)
        ratios = [row["ratio"] for row in pairs]
        spread = max(ratios) - min(ratios)
        if spread != 0 or pairs.count(pairs[0]) != 3:
            raise ValueError(f"non-repeatable pairs: k{k}")
        rows[f"k{k}"] = {"npz": source.relative_to(npz_root).as_posix(), "npz_sha256": npz_hash,
                         "band": band.relative_to(json_root).as_posix(), "band_sha256": band_hash,
                         "z_m": [LOW, high], "pairs": pairs, "median_ratio": median(ratios), "paired_spread": spread}
    worst = max(row["median_ratio"] for row in rows.values())
    return {"variant": "#1618 cached rejoin ON vs OFF, cropped separately with #1619 band",
            "worst_median_ratio": worst, "diagnostic_target": TARGET, "meets_target": worst <= TARGET,
            "keep": False, "rows": rows}


if __name__ == "__main__":
    root, bands, out = map(Path, sys.argv[1:])
    result = measure(root, bands)
    with out.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(result["worst_median_ratio"])
