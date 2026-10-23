"""Optional corner audit of the TOW02 face-diff centroid/normal matcher (hypothesis #603, adopted).

new-case: independent per-triangle corner check of the faces that pass 1 of face_diff.py calls "unchanged".
Pattern: none in docs/domain/patterns/INDEX.md (research helper, not a modelling pattern).

For each accepted face the selected diagonal's triangles are compared with their matched target triangles by the
six-permutation corner bottleneck: min over the 6 vertex permutations of max_k dist(a[k], b[perm[k]]) in raw local
metres. A triangle passes at <= limit (default 0.001 m, exactly 1 mm passes); a face passes only if all its
triangles pass. NOT a production or delivery gate (delivery_passed is always false).

Usage: python audit_correspondence.py SOURCE.fbx TARGET.fbx OUT.json [--limit 0.001] [--fraction 0.99]
Exit 0: computed and pass fraction >= --fraction; 1: computed but below --fraction; 2: bad input/arguments.
Inputs are read only and hashed before and after; OUT may not resolve to an input; written via OUT.partial.
"""
import argparse, hashlib, importlib.util, itertools, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("face_diff", os.path.join(HERE, "face_diff.py"))
fd = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fd)  # main() is guarded, not executed

LIMIT, FRACTION = 0.001, 0.99
PERMS = tuple(itertools.permutations(range(3)))


class AuditError(ValueError):
    """Unsupported or malformed input; never reported as a pass."""


def _points(tri, name):
    pts = [tuple(p) for p in tri]
    if len(pts) != 3 or any(len(p) != 3 for p in pts):
        raise AuditError("%s: expected 3 points of 3 coordinates, got %r" % (name, tri))
    if not all(math.isfinite(x) for p in pts for x in p):
        raise AuditError("%s: non-finite coordinate in %r" % (name, tri))
    return pts


def bottleneck(a, b):
    """min over the 6 vertex permutations of the max corner distance between triangles a and b (metres)."""
    a, b = _points(a, "a"), _points(b, "b")
    return min(max(math.dist(a[k], b[perm[k]]) for k in range(3)) for perm in PERMS)


def triangle_passes(a, b, limit=LIMIT):
    if not (isinstance(limit, (int, float)) and math.isfinite(limit) and limit >= 0):
        raise AuditError("limit must be a finite non-negative number, got %r" % (limit,))
    return bottleneck(a, b) <= limit


def face_audit(pairs, limit=LIMIT):
    """pairs: [(source_triangle_points, target_triangle_points)] of one face -> (passes, worst_m, worst_index)."""
    pairs = list(pairs)
    if not pairs:
        raise AuditError("face has no triangle pairs")
    ds = [bottleneck(a, b) for a, b in pairs]
    if not (isinstance(limit, (int, float)) and math.isfinite(limit) and limit >= 0):
        raise AuditError("limit must be a finite non-negative number, got %r" % (limit,))
    worst = max(range(len(ds)), key=lambda i: ds[i])
    return all(d <= limit for d in ds), ds[worst], worst


def replay_pass1(AV, AP, BV, BP):
    """Pass 1 of face_diff.main (same Grid, limits, order, diagonals, used flags) with the selection recorded.

    Returns [(face_index, diagonal_index, [(source_vertex_ids, target_triangle_index)])].
    """
    if any(len(p) != 3 for p in BP):
        raise AuditError("target mesh must be fully triangulated")
    bad = [i for i, p in enumerate(AP) if len(p) not in (3, 4)]
    if bad:
        raise AuditError("unsupported source polygon size at faces %s" % bad[:10])
    B = [fd.tri(BV, p) for p in BP]
    gB = fd.Grid(B, 0.05); used = [False] * len(B)

    def find(t, r, dmin, taken):
        best, bd = None, r
        for j in gB.near(t[0], r):
            if used[j] or j in taken:
                continue
            d = math.dist(t[0], B[j][0])
            if d <= bd and fd.dot(t[1], B[j][1]) >= dmin:
                best, bd = j, d
        return best, bd

    out = []
    for fi, p in enumerate(AP):
        diags = [[(p[0], p[1], p[2])]] if len(p) == 3 else \
            [[(p[0], p[1], p[2]), (p[0], p[2], p[3])], [(p[1], p[2], p[3]), (p[1], p[3], p[0])]]
        for di, d in enumerate(diags):
            got = []
            for t in d:
                tt = fd.tri(AV, t)
                j, _ = find(tt, fd.TOL_SAME, fd.DOT_SAME, got)
                if j is None or tt[2] < 1e-9:
                    break
                got.append(j)
            if len(got) == len(d):
                for j in got:
                    used[j] = True
                out.append((fi, di, [(d[k], got[k]) for k in range(len(d))]))
                break
    return out


def audit_meshes(AV, AP, BV, BP, limit=LIMIT, fraction=FRACTION):
    """Replay pass 1 and corner-audit every accepted face; returns a JSON-ready summary."""
    if not AP or not BP:
        raise AuditError("empty mesh: %d source faces, %d target triangles" % (len(AP), len(BP)))
    acc = replay_pass1(AV, AP, BV, BP)
    rows = []
    for fi, di, sel in acc:
        ok, worst, wi = face_audit([([AV[i] for i in s], [BV[i] for i in BP[j]]) for s, j in sel], limit)
        rows.append(dict(face=fi, diag=di, target_tri=sel[wi][1], bottleneck_m=worst, passes=ok))
    n = len(rows); over = [r for r in rows if not r["passes"]]
    frac = (n - len(over)) / n if n else None
    return dict(delivery_passed=False, limit_m=limit, fraction_required=fraction, source_faces=len(AP),
                target_tris=len(BP), accepted=n, over_limit=len(over), pass_fraction=frac,
                passes_fraction=bool(n and frac >= fraction),
                worst_m=max((r["bottleneck_m"] for r in rows), default=None),
                over_limit_faces=sorted(over, key=lambda r: -r["bottleneck_m"]),
                worst10=sorted(rows, key=lambda r: -r["bottleneck_m"])[:10])


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source"); ap.add_argument("target"); ap.add_argument("out")
    ap.add_argument("--object", default=fd.OBJ)
    ap.add_argument("--limit", type=float, default=LIMIT); ap.add_argument("--fraction", type=float, default=FRACTION)
    a = ap.parse_args(argv)
    try:
        for p in (a.source, a.target):
            if not os.path.isfile(p):
                raise AuditError("input not found: %s" % p)
        partial = a.out + ".partial"
        for p in (a.out, partial):
            for q in (a.source, a.target):
                if _same(p, q):
                    raise AuditError("output path %s resolves to input %s" % (p, q))
        if not (math.isfinite(a.limit) and a.limit >= 0 and math.isfinite(a.fraction) and 0 < a.fraction <= 1):
            raise AuditError("bad --limit %r or --fraction %r" % (a.limit, a.fraction))
        before = {p: _sha(p) for p in (a.source, a.target)}
        AV, AP, _, _ = fd.mesh(a.source, a.object)
        BV, BP, _, _ = fd.mesh(a.target, a.object)
        res = audit_meshes(AV, AP, BV, BP, a.limit, a.fraction)
        if {p: _sha(p) for p in before} != before:
            raise AuditError("input changed during the run")
    except (AuditError, StopIteration, AssertionError, IndexError, ValueError, OSError) as e:
        print("ERROR: %s" % (e or type(e).__name__), file=sys.stderr)
        return 2
    res["inputs"] = {"source": a.source, "target": a.target, "object": a.object, "sha256": before}
    with open(partial, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    os.replace(partial, a.out)
    print(json.dumps({k: res[k] for k in ("accepted", "over_limit", "pass_fraction", "worst_m", "passes_fraction")}))
    return 0 if res["passes_fraction"] else 1


if __name__ == "__main__":
    sys.exit(main())
