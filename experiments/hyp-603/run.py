"""Hypothesis #603: centroid/normal 'unchanged' faces keep triangle corners within 1 mm (six-permutation bottleneck).

Replays pass 1 of experiments/tow02-hand-finish-face-diff/face_diff.py (Grid, find, used, limits, order, both quad
diagonals unchanged); adds only a record of the selected diagonal and target triangle IDs. delivery_passed=false.
Usage: python run.py [work_dir]   (inputs are copied to work_dir, default $TMPDIR/agr-hyp-t_39eeb4e2)
"""
import hashlib, importlib.util, itertools, json, math, os, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FD = os.path.join(ROOT, "experiments", "tow02-hand-finish-face-diff", "face_diff.py")
SHA = {"v5": "ff8994dc4b7c05560eedd2b5af0827c03a919ba513b71ef8f60d2788fe28080a",
       "user": "2fd800812c53d70f77960c0d08b91790510a285a59370ca6fcac43856271da68"}
LIMIT, FRACTION, BASELINE = 0.001, 0.99, 33256
spec = importlib.util.spec_from_file_location("face_diff", FD)
fd = importlib.util.module_from_spec(spec); spec.loader.exec_module(fd)  # main() is guarded, not executed


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def replay(AV, AP, BV, BP):
    """Pass 1 exactly as face_diff.main; returns accepted [(face, diag_idx, [(src_ids, target_j)])]."""
    B = [fd.tri(BV, p) for p in BP]
    gB = fd.Grid(B, 0.05); used = [False] * len(B)

    def find(t, r, dmin, taken):
        best, bd = None, r
        for j in gB.near(t[0], r):
            if used[j] or j in taken: continue
            d = math.dist(t[0], B[j][0])
            if d <= bd and fd.dot(t[1], B[j][1]) >= dmin: best, bd = j, d
        return best, bd

    out = []
    for fi, p in enumerate(AP):
        ids = [[(p[0], p[1], p[2])]] if len(p) == 3 else \
            [[(p[0], p[1], p[2]), (p[0], p[2], p[3])], [(p[1], p[2], p[3]), (p[1], p[3], p[0])]]
        for di, d in enumerate(ids):
            got = []
            for t in d:
                j, _ = find(fd.tri(AV, t), fd.TOL_SAME, fd.DOT_SAME, got)
                if j is None or fd.tri(AV, t)[2] < 1e-9: break
                got.append(j)
            if len(got) == len(d):
                for j in got: used[j] = True
                out.append((fi, di, [(d[k], got[k]) for k in range(len(d))])); break
    return out


def bottleneck(a, b):
    return min(max(math.dist(a[k], b[perm[k]]) for k in range(3)) for perm in itertools.permutations(range(3)))


def audit(AV, BV, BP, acc):
    rows = []
    for fi, di, pairs in acc:
        worst, wit = 0.0, None
        for sids, j in pairs:
            d = bottleneck([AV[i] for i in sids], [BV[i] for i in BP[j]])
            if d > worst or wit is None: worst, wit = d, (sids, j)
        rows.append((fi, di, worst, wit[1]))
    return rows


def arms(v5, user):
    AV, AP, _, _ = fd.mesh(v5, fd.OBJ)
    UV_, UP, _, _ = fd.mesh(user, fd.OBJ)
    first = [t for p in AP for t in ([(p[0], p[1], p[2])] if len(p) == 3 else [(p[0], p[1], p[2]), (p[0], p[2], p[3])])]
    return {"v5_vs_user": (AV, AP, UV_, UP), "v5_self": (AV, AP, AV, first), "user_self": (UV_, UP, UV_, UP)}


def run(v5, user):
    res = {}
    for name, (AV, AP, BV, BP) in arms(v5, user).items():
        acc = replay(AV, AP, BV, BP)
        rows = audit(AV, BV, BP, acc)
        res[name] = dict(faces=len(AP), acc=[(a[0], a[1], [(list(s), j) for s, j in a[2]]) for a in acc], rows=rows)
    return res


def main(work):
    os.makedirs(work, exist_ok=True)
    src = {"v5": fd.V5, "user": fd.USER}; cp = {}
    for k, s in src.items():
        assert sha(s) == SHA[k], "source hash mismatch " + k
        cp[k] = os.path.join(work, k + ".fbx"); shutil.copyfile(s, cp[k]); assert sha(cp[k]) == SHA[k]
    runs = []
    for r in range(3):
        t = time.time(); runs.append(run(cp["v5"], cp["user"])); print("repeat", r, round(time.time() - t, 1), "s", flush=True)
    assert all(sha(cp[k]) == SHA[k] and sha(src[k]) == SHA[k] for k in cp), "input mutated"
    identical = all(runs[0] == x for x in runs[1:])
    summary = {"delivery_passed": False, "script_blob": subprocess.run(["git", "hash-object", FD], capture_output=True, text=True).stdout.strip(),
               "head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
               "inputs_sha256": SHA, "repeats_identical": identical, "inputs_unchanged": True, "arms": {}}
    for name, a in runs[0].items():
        rows = a["rows"]; n = len(rows)
        bad = [r for r in rows if r[2] > LIMIT]
        frac = (n - len(bad)) / n if n else None
        worst = sorted(rows, key=lambda r: -r[2])[:10]
        summary["arms"][name] = dict(source_faces=a["faces"], accepted=n, over_1mm=len(bad), pass_fraction=frac,
                                     passes_99=bool(n and frac >= FRACTION), worst=max((r[2] for r in rows), default=None),
                                     worst10=[dict(face=r[0], diag=r[1], target_tri=r[3], bottleneck_m=r[2]) for r in worst])
    arms_ = summary["arms"]
    if not identical or arms_["v5_vs_user"]["accepted"] != BASELINE or any(a["accepted"] == 0 for a in arms_.values()):
        summary["verdict"] = "INCONCLUSIVE" if identical else "REJECTED"
    else:
        summary["verdict"] = "CONFIRMED" if all(a["passes_99"] for a in arms_.values()) else "REJECTED"
    with open(os.path.join(work, "results.json"), "w") as f: json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("TMPDIR", tempfile.gettempdir()), "agr-hyp-t_39eeb4e2"))
