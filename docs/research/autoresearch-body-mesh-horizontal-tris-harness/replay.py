"""Standing #27: horizontal-triangle area share, accepted vs rejected bodies (OBSERVE, no penalty)."""
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import sys

COS1, SIN1 = math.cos(math.radians(1.0)), math.sin(math.radians(1.0))
ETALON_TRIS = {"G22-etalon-k1": 7733, "G22-etalon-k2": 1589, "G22-etalon-k3": 1873}
FIXTURE = (
    ("63B-v001", "rejected", "ar15/r1/tmp/63B-v001.1/dump.json", "d98a129ee2035c1436763a5c47c0705edd39a5c4ccf7675584d87b4f0a3a6f57"),
    ("63B-v002", "rejected", "ar15/r1/tmp/63B-v002.1/dump.json", "b1d2098f34e97a07578adf06b4c83f96279f70564c4383f66f9221ee09979981"),
    ("63B-v003", "rejected", "ar15/r1/tmp/63B-v003.1/dump.json", "1263be647aa9fd3b09714c6763d46676c735a13939dff587ccd342cb498b2a3d"),
    ("63B-v004", "rejected", "ar15/r1/tmp/63B-v004.1/dump.json", "bf115523c6dde6387a8c929342cf501fd179c8b22df1810ba6784280497ff30b"),
    ("63B-v005", "rejected", "ar15/r1/tmp/63B-v005.1/dump.json", "03db41df0ce700bad640633246590cf08a33d85a551e9a8391d45bbc785d9554"),
    ("63B-v006", "rejected", "ar15/r1/tmp/63B-v006.1/dump.json", "fc41ff9ef238e5adceb114b7198f75bec2d08ebca12564bba925f02aca91fa04"),
    ("63C-v001", "rejected", "ar15/r1/tmp/63C-v001.1/dump.json", "d8e64e2a54a66b2b1b377ae4e9c1b2f21ac3e53deadd26e25f361631e88197a7"),
    ("KPP1-v003-corners", "rejected", "ar15/r1/tmp/KPP1-v003-corners.1/dump.json", "4565eabf45a333868ea410358aa240a8c89dcac56175d67a697a098c36867596"),
    ("63B-v007", "accepted", "ar15/r1/tmp/63B-v007.1/dump.json", "c8d65372d76148d38ffeb6a14e0dbc0c3449536f2ddb627bbd7a3c24ff6ca416"),
    ("63C-v002", "accepted", "ar15/r1/tmp/63C-v002.1/dump.json", "19ee7c2046e37a5eeff76522a4b62a3f468f4fb02f1fd210cf912a8b2274ae7e"),
    ("63A-v005", "accepted", "ev_t_f55bc192/63A.dump.json", "3960fbdbc38f86d3f167128c1e7761928802d10a1f0d5726514a9afc2aa02b32"),
    ("G22-k2-v002r1", "accepted", "ev_1619/r7/k2_v002r1.mq.json", "2e922754e8b77f854627267fc75b1ba9c22c41a7c4713333fc34ba0ffaff431b"),
    ("G22-etalon-k1", "accepted", "ev_1619/r2/etalon_k1.mq.json", "413515339be03d1aa8eb88d23c487ce81f1605eced51d3b822d2919141acefb1"),
    ("G22-etalon-k2", "accepted", "ev_1619/r4/etalon_k2.mq.json", "50df5fb7252078a3fc1edc9076b9e0043051f897bb3aa363b2014b404e6f8d0d"),
    ("G22-etalon-k3", "accepted", "ev_1619/r1/etalon_k3.mq.json", "dc389b008673016871591e1cb42f151379b63aa2ffe271590c52b3009a7d4a13"),
)


def require_hash(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"input hash mismatch: {path}: {actual} != {expected}")


def newell(pts):
    nx = ny = nz = 0.0
    for (x0, y0, z0), (x1, y1, z1) in zip(pts, pts[1:] + pts[:1]):
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def read(path):
    """Area sums by class over all objects of one dump: (horizontal, horizontal tris, vertical, vertical tris, tris)."""
    data = json.loads(path.read_bytes())
    acc = {"h_area": 0.0, "h_tri_area": 0.0, "v_area": 0.0, "v_tri_area": 0.0, "tris": 0, "faces": 0}
    for obj in data["objects"]:
        verts = obj["verts"]
        for face in obj["faces"]:
            nx, ny, nz = newell([verts[i] for i in face])
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            acc["faces"] += 1
            tri = len(face) == 3
            acc["tris"] += tri
            if length == 0.0:
                continue
            area, c = length / 2.0, abs(nz) / length
            if c >= COS1:
                acc["h_area"] += area
                acc["h_tri_area"] += area * tri
            elif c <= SIN1:
                acc["v_area"] += area
                acc["v_tri_area"] += area * tri
    return acc


def margin(rows, skip=()):
    rej = [r["H"] for k, r in rows.items() if r["label"] == "rejected" and k not in skip]
    acc = [r["H"] for k, r in rows.items() if r["label"] == "accepted"]
    return min(rej) - max(acc)


def measure(root, fixture=FIXTURE):
    rows = {}
    for name, label, rel, digest in fixture:
        path = root / rel
        require_hash(path, digest)
        reads = [read(path) for _ in range(3)]
        require_hash(path, digest)
        if any(r != reads[0] for r in reads):
            raise ValueError(f"non-repeatable reads: {name}")
        r = reads[0]
        if r["h_area"] <= 0.0:
            raise ValueError(f"no horizontal area: {name}")
        if name in ETALON_TRIS and r["tris"] != ETALON_TRIS[name]:
            raise ValueError(f"etalon triangle parity failure: {name} {r['tris']}")
        hs = [x["h_tri_area"] / x["h_area"] for x in reads]
        rows[name] = {"label": label, "file": rel, "sha256": digest, "faces": r["faces"], "triangles": r["tris"],
                      "h_area": round(r["h_area"], 4), "h_tri_area": round(r["h_tri_area"], 4),
                      "v_area": round(r["v_area"], 4), "v_tri_area": round(r["v_tri_area"], 4),
                      "H": median(hs), "paired_spread": max(hs) - min(hs),
                      "V": r["v_tri_area"] / r["v_area"] if r["v_area"] else None}
    m = margin(rows)
    return {"variant": "baseline feature read, |n_z|>=cos1deg Newell, no clipping", "metric": "min(H rejected)-max(H accepted)",
            "M": m, "M_without_63B_v006": margin(rows, skip=("63B-v006",)), "separates": m > 0, "keep": False, "rows": rows}


if __name__ == "__main__":
    root, out = map(Path, sys.argv[1:])
    result = measure(root)
    with out.open("x", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")
    print(result["M"], result["M_without_63B_v006"])
