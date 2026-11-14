"""Static research inventory, never imports or executes inventoried scripts.

Pattern: n/a | new-case: reproducible source-bound reuse census for #1296.
"""
from pathlib import PurePosixPath

SCRIPT_SUFFIXES = {".py", ".ms", ".mcr", ".sh", ".ps1", ".mjs", ".js", ".cs", ".run"}


def select_paths(paths, texts):
    selected = []
    for p in paths:
        if (PurePosixPath(p).suffix.lower() not in SCRIPT_SUFFIXES
                and not texts.get(p, "").startswith("#!")):
            continue
        if (p.startswith("tools/") or p.startswith("adapters/max/agr_tools/")
                or (p.startswith("jobs/") and len(p.split("/")) > 3 and p.split("/")[2] == "scripts")
                or (p.startswith("src/dt_ai/") and
                    (p.startswith("src/dt_ai/cli/") or "__main__" in texts.get(p, "")))):
            selected.append(p)
    return selected


def name_key(path):
    import re
    return re.sub(r"(?:[_-](?:v\d+|\d{3,}))+$", "", PurePosixPath(path).stem.lower())


def shingles(text):
    import re
    # Keep identifiers; normalize quoted literals/numbers, drop comments/whitespace.
    text = re.sub(r"(?m)#.*$|//[^\n]*$", "", text)
    text = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", " LITERAL ", text)
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s\w]", text)
    tokens = ["NUMBER" if re.fullmatch(r"\d+(?:\.\d+)?", t) else t for t in tokens]
    return {tuple(tokens[i:i + 5]) for i in range(len(tokens) - 4)}


def duplicate_pairs(texts, threshold=0.65):
    import hashlib
    import math
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("threshold must be finite in (0, 1]")
    paths = sorted(texts)
    sets = {p: shingles(texts[p]) for p in paths}
    hashes = {p: hashlib.sha256(texts[p].encode()).hexdigest() for p in paths}
    out = []
    for i, left in enumerate(paths):
        for right in paths[i + 1:]:
            a, b = sets[left], sets[right]
            exact = bool(texts[left].strip()) and hashes[left] == hashes[right]
            same_name = name_key(left) == name_key(right)
            score = len(a & b) / len(a | b) if a and b else 0.0
            # Small boilerplate is not a near-duplicate algorithm.
            if exact or same_name or (min(len(a), len(b)) >= 40 and score >= threshold):
                kind = "exact" if exact else "content" if min(len(a), len(b)) >= 40 and score >= threshold else "name"
                out.append({"left": left, "right": right, "kind": kind,
                            "same_name": str(same_name).lower(), "similarity": round(score, 6)})
    return out


def facts(path, text):
    import ast
    import re
    lines = text.splitlines()
    doc, imports, definitions = "", [], []
    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
            doc = ast.get_docstring(tree) or ""
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "(relative)")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    definitions.append(node.name)
        except SyntaxError:
            doc = "AST unsupported; inspect source"
    if not doc:
        comments = [s.strip().lstrip("#/- ") for s in lines[:25] if s.strip().startswith(("#", "--", "//"))]
        doc = " ".join(comments)
    purpose = " ".join(doc.split())[:360] if doc else "Name-derived (unverified): " + PurePosixPath(path).stem.replace("_", " ")
    overrides = {
        "jobs/skug26-k5-ac/scripts/phase.py": "Measure perforation-hole lattice phase/margins from per-element vertex CSVs and an element-normal table; prints component counts and bounds (scipy).",
        "jobs/skug26-k5-ac/scripts/uvdump.ms": "Dump Object004/Object005 face material IDs and channel-1 UV corners to hard-coded uv_faces.csv in Max; job-local output path must be parameterized.",
        "jobs/skug26-k5-ac/scripts/uvverify.py": "Compare dumped face UVs with alpha-hole centroids in a texture; print per-object hole/UDIM counts and save a 1024px polygon overlay.",
        "src/dt_ai/cli/main.py": "dt console entry point: profiles/schemas/inspect/index-pdf/registry/spec/from-source/intake/evals/qa/derive/ground/build/validate (development bundles, not delivery certificates).",
        "src/dt_ai/cli/__init__.py": "Package marker for the dt CLI; no executable behavior.",
        "adapters/max/agr_tools/mzp.run": "Max MZP install manifest: dispatch bundled setup/bootstrap commands; not a modelling algorithm.",
    }
    purpose = overrides.get(path, purpose)
    params = sorted(set(re.findall(r"[\"'](--[a-zA-Z][\w-]*)[\"']", text)))
    def excerpts(pattern):
        hits = [f"L{i}: {' '.join(s.split())[:220]}" for i, s in enumerate(lines, 1) if re.search(pattern, s, re.I)]
        return " | ".join(hits[:8]) + (f" | +{len(hits)-8} further source lines" if len(hits) > 8 else "") if hits else "not declared statically"
    dcc = []
    if re.search(r"\b(bpy|bmesh|blender)\b", text, re.I):
        dcc.append("Blender (static reference)")
    if re.search(r"\b(pymxs|3dsmax|MAXScript)\b", text, re.I) or PurePosixPath(path).suffix in {".ms", ".mcr"}:
        dcc.append("3ds Max (static reference)")
    if re.search(r"\b(revit|RevitBridge)\b", text, re.I):
        dcc.append("Revit (static reference)")
    if re.search(r"\b(autocad|accoreconsole)\b", text, re.I):
        dcc.append("AutoCAD (static reference)")
    return {"purpose": purpose, "inputs": excerpts(r"read_|read\(|json.load|import_scene|open_mainfile|loadMaxFile|fileIn|--source|--input|sys.argv"),
            "outputs": excerpts(r"write_|write\(|json.dump|\.save\(|save_as|saveMaxFile|export_scene|exportFile|createFile|--out"),
            "parameters": " | ".join(params) or "no named flags; inspect positional arguments/API",
            "dcc": " | ".join(dcc) or "none detected (host-independent or indirect host dependency)",
            "imports": " | ".join(sorted(set(imports))), "definitions": " | ".join(definitions[:30])}


# These are routing candidates, NOT demonstrated semantic replacements.
COVERAGE = [
    (("export_npm", "make_npm_atlas", "npm_atlas"), "tools/derive/export_npm.py | tools/derive/npm_atlas.py | src/dt_ai/cli/shared_tools.py"),
    (("package_vpm",), "tools/derive/package_vpm.py | adapters/max/agr_tools/package_core.py"),
    (("ucx",), "tools/blender/ucx_build.py | adapters/max/agr_tools/ucx_core.py | adapters/max/agr_tools/ucx10_core.py"),
    (("unwrap", "vpm_uv", "atlas"), "tools/materials/npm_atlas_udim.py | adapters/max/agr_tools/atlas_core.py | adapters/max/agr_tools/uvlayout_core.py"),
    (("delivery_export", "export_vpm"), "adapters/max/agr_tools/export_core.py | adapters/max/agr_tools/deliver_core.py"),
    (("qa_", "check", "readback"), "tools/qa/validate_package.py | src/twinqa/scene.py"),
    (("make_textures", "finish_map"), "tools/derive/npm_atlas.py | adapters/max/agr_tools/vpmmaps_core.py"),
    (("open_view",), "adapters/max/agr_tools/handoff_core.py (planning only; Max open glue still job-local)"),
    (("contact", "render"), "tools/qa/render_qa.py (numerical preview only; no shared contact-sheet producer identified)"),
    (("build_full", "build_kpp", "build_"), "src/dt_ai/core/build.py | adapters/max/agr_tools/body_core.py"),
]


def snapshot(root, ref):
    import subprocess
    roots = ["jobs", "tools", "src/dt_ai", "adapters/max/agr_tools", "pyproject.toml"]
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "-z", ref, "--", *roots], cwd=root)
    paths = [p.decode("utf-8") for p in names.split(b"\0") if p]
    if any("\n" in p or "\r" in p for p in paths):
        raise ValueError("newline-bearing Git path unsupported by batch census")
    # git archive applies eol attributes on this repository: it is NOT a raw-blob oracle.
    data = subprocess.check_output(["git", "cat-file", "--batch"], cwd=root,
                                   input="".join(f"{ref}:{p}\n" for p in paths).encode())
    raw, offset = {}, 0
    for p in paths:
        end = data.index(b"\n", offset)
        header = data[offset:end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError(f"not a source blob: {p}")
        size = int(header[2])
        raw[p] = data[end + 1:end + 1 + size]
        if len(raw[p]) != size or data[end + 1 + size:end + 2 + size] != b"\n":
            raise ValueError(f"partial source blob: {p}")
        offset = end + 2 + size
    if offset != len(data):
        raise ValueError("unexpected trailing batch data")
    return raw


def research(root, ref):
    import hashlib
    from collections import Counter, defaultdict
    raw = snapshot(root, ref)
    texts = {p: b.decode("utf-8-sig", errors="replace") for p, b in raw.items()
             if PurePosixPath(p).suffix.lower() in SCRIPT_SUFFIXES | {".md", ".json", ".yaml", ".toml"} or b.startswith(b"#!")}
    selected = sorted(select_paths(sorted(raw), texts))
    pairs = duplicate_pairs({p: texts[p] for p in selected})
    near_shared = defaultdict(set)
    for pair in pairs:
        if pair["kind"] in {"content", "exact"}:
            for a, b in [(pair["left"], pair["right"]), (pair["right"], pair["left"])]:
                if a.startswith("jobs/") and not b.startswith("jobs/"):
                    near_shared[a].add(b)
    rows = []
    for p in selected:
        row = {"path": p, "sha256": hashlib.sha256(raw[p]).hexdigest(), "lines": len(texts[p].splitlines()),
               "scope": "job" if p.startswith("jobs/") else "dt-entry" if p.startswith("src/") else "max-adapter" if p.startswith("adapters/") else "tool",
               "owner_job": p.split("/")[1] if p.startswith("jobs/") else "shared", **facts(p, texts[p])}
        # Exact path or basename mentions are references, not proof of runtime use.
        refs = sorted({q.split("/")[1] for q, t in texts.items() if q.startswith("jobs/")
                       and q != p and (p in t or PurePosixPath(p).name in t)})
        row["job_references"] = " | ".join(refs) or "none found (dynamic callers may be missed)"
        candidates = next((v for keys, v in COVERAGE if any(k in name_key(p) for k in keys)), "none identified")
        row["shared_coverage"] = "self/shared implementation; callers and host dependencies require review" if not p.startswith("jobs/") else "candidate, not parity-proven: " + candidates
        row["content_shared_candidates"] = " | ".join(sorted(near_shared[p])) or "none above threshold"
        rows.append(row)
    excluded = sorted(p for p in raw if (p.startswith("tools/") or p.startswith("adapters/max/agr_tools/") or
                       (p.startswith("jobs/") and len(p.split("/")) > 3 and p.split("/")[2] == "scripts")) and p not in selected)
    meta = {"source_ref": ref, "method": "tracked Git blobs, no DCC execution; static reference evidence only",
            "rows": len(rows), "scopes": dict(Counter(r["scope"] for r in rows)),
            "job_counts": dict(sorted(Counter(r["owner_job"] for r in rows if r["scope"] == "job").items())),
            "duplicate_pairs": len(pairs), "pair_kinds": dict(Counter(p["kind"] for p in pairs)),
            "content_threshold": 0.65, "minimum_distinct_shingles": 40,
            "excluded_non_scripts": excluded}
    return rows, pairs, meta


def serialize(rows, pairs, meta):
    import csv
    import io
    import json
    def csv_text(items, fields):
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(items)
        return out.getvalue().encode()
    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        groups[name_key(r["path"])].append(r["path"])
    doc = ["# Duplicate groups — static candidates, not semantic equivalence", "",
           "Source: `" + meta["source_ref"] + "`. See report.md for method and limits.", "",
           "`duplicates.csv` contains every qualifying pair and score (including differently named content).",
           "Below: normalized-name groups. Versions remain independent evidence; never delete them from this census.", ""]
    for name, paths in sorted(groups.items()):
        if len(paths) > 1:
            doc.extend([f"## {name} ({len(paths)})", "", *["- `" + p + "`" for p in paths], ""])
    return {"inventory.csv": csv_text(rows, list(rows[0]) if rows else ["path"]),
            "duplicates.csv": csv_text(pairs, ["left", "right", "kind", "same_name", "similarity"]),
            "snapshot.json": (json.dumps(meta, indent=2, ensure_ascii=False) + "\n").encode(),
            "duplicate-groups.md": ("\n".join(doc).rstrip() + "\n").encode()}


def main():
    import argparse
    import subprocess
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", required=True, help="immutable source commit")
    ap.add_argument("--out", type=Path, required=True, help="new directory, or existing with --check")
    ap.add_argument("--check", action="store_true", help="read-only comparison; no output writes")
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[3]
    ref = subprocess.check_output(["git", "rev-parse", a.ref + "^{commit}"], cwd=root, text=True).strip()
    if a.out.resolve().is_relative_to(root / "jobs"):
        ap.error("research output must not be a job/source directory")
    if not a.check and a.out.exists():
        ap.error("output exists; choose a new directory or read-only --check")
    result = serialize(*research(root, ref))
    if a.check:
        different = [name for name, data in result.items() if not (a.out / name).is_file() or (a.out / name).read_bytes() != data]
        if different:
            print("stale/missing research artifacts: " + ", ".join(different))
            return 1
    else:
        a.out.mkdir(parents=True, exist_ok=False)
        for name, data in result.items():
            with (a.out / name).open("xb") as f:
                f.write(data)
    print("research inventory: " + str(len(result)) + " artifacts " + ("verified" if a.check else "written"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
