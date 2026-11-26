"""new-case: skeleton cell `library-publish` (#1743, [D372], [D368]-[D371]): put agent-made MAF / Flora / windows / roof
equipment into the AGR library as immutable `draft` versions; Artem's word flips them to `accepted`.

    agr library publish BATCH [--kind maf] [--identity IDS.json] [--assets-root ROOT] [--catalogue CAT.json]
                              [--evidence DIR] [--issue N] [--blender EXE]
    agr library accept NAME[@vNNN] ... --words "<Artem's words>" [--despite-qa]
    agr library reject NAME[@vNNN] --words "<Artem's words>" --inbox-root G:/Мой диск/AGR-assets/_inbox
    agr library reindex [--a101-root DIR]              rebuild the MAF search index now [D421]
    agr library check-job jobs/<ID> [--outputs DIR]    close-out guard: no unpublished MAF master [D421]

Stages (docs/agents/skeletons.json, cell library-publish), each on its existing owner:
  intake    list the objects of a batch COPY (A101 zips, object folders); every file is an object file, a work
            file superseded by an A101 zip, or a drop with its reason. Nothing is written into the batch.
  identify  unified library (library/assets/maf_unified.json = A101 + legacy, assets_library article/maker keys,
            intake_identify.dims_check +-10 %) and the publish catalogue: duplicate / variant / new.
  name      [D369] Manufacturer_NameLatin_Article (assets_library.propose_maf_name, translit, ё=е);
            without a manufacturer AGR_<kind>_<Name>_<NNN>.
  qa        VPM (`_high`) and NPM (`_low`) FBX read back by tools/blender/fbx_readback.py (blender_runner);
            ngons, triangles, materials + maps, pivot/seating per kind, twinqa.maf_checks smoothing/flips.
  register  files to <assets-root>/<kind>/<name>/vNNN/ (new version, written as vNNN.partial then renamed,
            never overwritten [D370]), record `draft` in library/published/catalogue.json [D371].
  sheet     one preview sheet per batch (sheet.md + sheet.html + previews + SHA256SUMS.txt) for Artem.

Exit codes: 0 done, 1 an object failed QA / a command refused a record, 2 invalid input. QA failure does not
stop the draft (Artem sees it on the sheet); `accept` refuses a QA-failed record unless --despite-qa.
Read path [D421]: `available()` and the search index library/assets/maf_unified.json (rebuilt at the end of every
publish / accept / reject) offer `accepted` AND `draft` versions, each with its `status`; an agent prefers accepted
and says so in its report when it reuses a draft. The frozen AGR Tools assets browser (assets_core.scan_maf) stays
accepted-only [D371].
Close-out guard: `agr library check-job jobs/<ID> [--outputs DIR]` fails while a MAF master in the job outputs has no
library entry.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "agr-library-publish/1"
CATALOGUE = ROOT / "library/published/catalogue.json"
KINDS = ("maf", "flora", "windows", "roof_equipment")  # [D372]; materials later
STATUSES = ("draft", "accepted", "rejected")
VERSION_RE = re.compile(r"^v(\d{3})$")
SKIP_FILES = {"desktop.ini", "sha256sums.txt", "thumbs.db"}
FBX_ROLES = {"vpm": "_high", "npm": "_low"}
TOL_M = 0.01      # pivot centring tolerance, m
SINK_M = 0.10     # [D100] Flora: lowest vertex 0.1 m below the pivot (TEMPLATE flora-bbox-plus-0.1)
SEAT_TOL_M = 0.005
# A101 library standard (library/assets/INTAKE.md step 5, docs/library/TEMPLATE.md): MAF and roof equipment pivot at
# the XY centre at ground level (bottom-center, base Z=0); the [D095] 0.1 m sink is placement in a delivery scene.
PIVOT = {"maf": ("center", 0.0), "flora": ("center", -SINK_M), "roof_equipment": ("center", 0.0),
         "windows": ("min", 0.0)}


class PublishError(ValueError):
    """Invalid input or a refused write; the message names the offending item."""


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lib = _load("agr_tools_assets_library", "adapters/max/agr_tools/assets_library.py")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso():
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


# ---- catalogue -------------------------------------------------------------------------------------------------
def empty_catalogue():
    return {"schema": SCHEMA, "records": []}


def load_catalogue(path):
    p = Path(path)
    if not p.is_file():
        raise PublishError(f"catalogue {p} does not exist")
    data = json.loads(p.read_text(encoding="utf-8"))
    problems = catalogue_problems(data)
    if problems:
        raise PublishError(f"catalogue {p}: " + "; ".join(problems))
    return data


def catalogue_problems(data):
    """Semantic check beside schemas/library_published.schema.json (stdlib, no jsonschema dependency)."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("records"), list):
        return [f"not an {SCHEMA} catalogue"]
    out, seen = [], set()
    for i, r in enumerate(data["records"]):
        tag = f"record {i}"
        if not isinstance(r, dict):
            out.append(f"{tag}: not an object")
            continue
        key = (str(r.get("name", "")).lower(), r.get("version"))
        if key in seen:
            out.append(f"{tag}: duplicate {r.get('name')}@{r.get('version')}")
        seen.add(key)
        if r.get("status") not in STATUSES:
            out.append(f"{tag}: status {r.get('status')!r} not in {STATUSES}")
        if r.get("kind") not in KINDS:
            out.append(f"{tag}: kind {r.get('kind')!r} not in {KINDS}")
        if not VERSION_RE.match(str(r.get("version", ""))):
            out.append(f"{tag}: version {r.get('version')!r} is not vNNN")
        if r.get("status") == "accepted" and not (r.get("accepted") or {}).get("words"):
            out.append(f"{tag}: accepted without Artem's words")
        for f in r.get("files") or []:
            if not re.fullmatch(r"[0-9a-f]{64}", str(f.get("sha256", ""))):
                out.append(f"{tag}: file {f.get('path')} has no SHA-256")
    return out


def write_json_atomic(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".partial", dir=str(p.parent))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, p)


def available(catalogue, kind=None, drafts=True):
    """The agents' read path [D421]: `accepted` AND `draft` versions, accepted first; every record keeps its `status`.
    An agent prefers an accepted record, may reuse a draft and says so in its report; rejected is never offered.
    drafts=False: accepted only (the frozen AGR Tools assets browser gate, [D371])."""
    ok = ("accepted", "draft") if drafts else ("accepted",)
    recs = [r for r in catalogue.get("records", []) if r.get("status") in ok
            and (kind is None or r.get("kind") == kind)]
    return sorted(recs, key=lambda r: r["status"] != "accepted")


def accepted_paths(catalogue):
    """`<kind>/<name>/vNNN` folders the assets browser may show (assets_core.scan_maf filter): accepted only."""
    return {"{}/{}/{}".format(r["kind"], r["name"], r["version"]).lower()
            for r in available(catalogue, drafts=False)}


# ---- search index (library/assets/maf_unified.json) [D421] ----------------------------------------------------
UNIFIED = ROOT / "library/assets/maf_unified.json"
DEFAULT_A101 = "G:/Мой диск/AGR-assets/maf/a101"
INDEX_CACHE = Path.home() / ".cache" / "agr-library-index"


def index_path(catalogue_path, index=None):
    """Where `publish|accept|reject` rebuild the search index: --index, else the repo index for the repo catalogue,
    else `maf_unified.json` next to the given catalogue (a test or scratch catalogue never rewrites the repo index)."""
    if index:
        return Path(index)
    if Path(catalogue_path).resolve() == CATALOGUE.resolve():
        return UNIFIED
    return Path(catalogue_path).with_name("maf_unified.json")


def index_record(r):
    card = r.get("card") or {}
    size = card.get("size_m")
    return {"id": "{}_published:{}@{}".format(r["kind"], r["name"], r["version"]), "source": "published",
            "name": r["name"], "version": r["version"], "status": r["status"],
            "manufacturer": card.get("manufacturer"), "title_ru": card.get("title_ru"), "article": card.get("article"),
            "bbox_mm": {"high": dict(zip("xyz", [round(v * 1000, 1) for v in size]))} if size else {},
            "tris": card.get("tris"), "path": "{}/{}/{}".format(r["kind"], r["name"], r["version"]),
            "preview": r.get("preview"), "qa": (r.get("qa") or {}).get("verdict"), "origin": r.get("origin")}


def scan_a101(a101_root, cache=None, legacy=None):
    """Rescan the A101 MAF archives (headless assets_core.scan_maf; unchanged zips reuse the cached scan) and unify
    them with the legacy catalogue, as tools/assets/build_unified_library.py does."""
    core = _load("agr_tools_assets_core", "adapters/max/agr_tools/assets_core.py")
    cache = Path(cache or INDEX_CACHE)
    cache.mkdir(parents=True, exist_ok=True)
    old_p = cache / "maf_assets_index.json"
    old = json.loads(old_p.read_text(encoding="utf-8")) if old_p.is_file() else None
    root = Path(a101_root).as_posix()
    idx = core.scan_maf(root, str(cache), lib="maf", old_index=old, published=set())
    write_json_atomic(old_p, idx)
    measured_p = ROOT / "library/assets/maf_measured.json"
    unknown = []
    if measured_p.is_file():
        idx, unknown = lib.attach_measured(idx, json.loads(measured_p.read_text(encoding="utf-8"))["measured"])
    if legacy is None:
        legacy = json.loads((ROOT / "library/maf/catalogue.json").read_text(encoding="utf-8"))
    mf = lib.unify_maf(idx, legacy)
    mf["sources"] = {"a101_root": root, "catalogue": "library/maf/catalogue.json",
                     "measured": "library/assets/maf_measured.json", "measured_unknown": unknown}
    mf["audit"] = lib.audit_maf(idx)
    mf["scan_problems"] = idx.get("report", {}).get("problems", [])
    return mf


def rebuild_index(catalogue, path, a101_root=None, cache=None, legacy=None, catalogue_path=None):
    """Rebuild the MAF search index at `path` [D421]: the A101 + legacy part (rescanned when `a101_root` is given,
    else kept from the file) + every draft / accepted published MAF record with its `status`. Atomic, idempotent."""
    path = Path(path)
    if catalogue_path and path.resolve() == Path(catalogue_path).resolve():
        raise PublishError(f"index {path} is the catalogue itself")
    if a101_root:
        data = scan_a101(a101_root, cache, legacy)
    elif path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"schema": lib.UNIFIED_SCHEMA, "kind": "maf", "truth": "a101", "records": [], "counts": {},
                "sources": {}}
    if data.get("schema") != lib.UNIFIED_SCHEMA:
        raise PublishError(f"index {path} is not an {lib.UNIFIED_SCHEMA} file")
    pubs = [index_record(r) for r in available(catalogue, kind="maf")]
    data["records"] = [r for r in data.get("records", []) if r.get("source") != "published"] + pubs
    data.setdefault("counts", {}).update(
        published_draft=sum(r["status"] == "draft" for r in pubs),
        published_accepted=sum(r["status"] == "accepted" for r in pubs))
    data.setdefault("sources", {})["published"] = "library/published/catalogue.json"
    write_json_atomic(path, data)
    return data


def _refresh_index(a, cat):
    """End of every publish / accept / reject: rebuild the search index (A101 rescan for the repo index)."""
    path = index_path(a.catalogue, getattr(a, "index", None))
    a101 = getattr(a, "a101_root", None)
    if a101 is None and path.resolve() == UNIFIED.resolve():
        a101 = DEFAULT_A101
    if a101 and not Path(a101).is_dir():
        print(f"index: A101 root {a101} not reachable; A101 part kept as it was", file=sys.stderr)
        a101 = None
    data = rebuild_index(cat, path, a101_root=a101, catalogue_path=a.catalogue)
    c = data["counts"]
    print(f"index: {path} rebuilt (a101 {c.get('a101', 0)}, published draft {c['published_draft']}, "
          f"accepted {c['published_accepted']})")


# ---- job close-out guard [D421] ---------------------------------------------------------------------------------
MASTER_RE = re.compile(r"^(?P<key>.+?)(_groundel.*|_high|_low)$", re.I)


def maf_masters(paths):
    """MAF master files among job outputs: an object FBX/MAX `<key>_GroundEl*` or `<key>_high|_low`, or an A101
    archive with a `_high.fbx` member. A delivery package object (`SM_<Address>_...`, docs/domain/geometry.md) is
    not a library master."""
    out = []
    for base in paths:
        base = Path(base)
        files = sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else [base] if base.is_file() else []
        for p in files:
            ext, stem = p.suffix.lower(), p.stem
            if stem.lower().startswith("sm_") or "source" in [x.lower() for x in p.parts[-3:-1]]:
                continue
            if ext in (".fbx", ".max"):
                m = MASTER_RE.match(stem)
                if m:
                    out.append({"path": str(p), "key": m.group("key")})
            elif ext == ".zip":
                try:
                    with zipfile.ZipFile(p) as zf:
                        if any(n.lower().endswith("_high.fbx") for n in zf.namelist()):
                            out.append({"path": str(p), "key": stem})
                except zipfile.BadZipFile:
                    continue
    return out


def unpublished_maf(paths, catalogue, unified):
    """MAF masters with no library entry: no catalogue record (any status) by file SHA-256, name or origin object,
    and no A101 / indexed record of that name. Empty list = the job may close."""
    shas = {f.get("sha256") for r in catalogue.get("records", []) for f in r.get("files") or []}
    names = {str(r.get("name", "")).lower() for r in catalogue.get("records", [])}
    names |= {str((r.get("origin") or {}).get("object", "")).lower() for r in catalogue.get("records", [])}
    names |= {str(r.get("name") or "").lower() for r in (unified or {}).get("records", [])
              if r.get("source") in ("a101", "published")}
    miss = []
    for m in maf_masters(paths):
        if m["key"].lower() in names or Path(m["path"]).stem.lower() in names:
            continue
        if sha256_file(m["path"]) in shas:
            continue
        miss.append(dict(m, reason="no library entry: run `agr library publish` (draft) before closing the job"))
    return miss


def job_artifacts(job_dir):
    """Artifact paths a job declares in job.yaml (`artifacts[].path`, repo-relative or absolute)."""
    import yaml
    y = Path(job_dir) / "job.yaml"
    if not y.is_file():
        return []
    data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
    out = []
    for a in data.get("artifacts") or []:
        p = Path(str((a or {}).get("path", "")))
        out.append(p if p.is_absolute() else ROOT / p)
    return out


# ---- 1 intake --------------------------------------------------------------------------------------------------
def _zip_object(path):
    """An A101-format archive <Name>.zip with <Name>_high.fbx / _low.fbx (+ .max, .png, .json sidecar)."""
    base = path.stem
    with zipfile.ZipFile(path) as zf:
        names = {Path(n.replace("\\", "/")).name.lower(): n for n in zf.namelist()}
        roles = {role: names[(base + suffix + ".fbx").lower()] for role, suffix in FBX_ROLES.items()
                 if (base + suffix + ".fbx").lower() in names}
        if not roles:
            return None
        meta = None
        if (base + ".json").lower() in names:
            try:
                meta = json.loads(zf.read(names[(base + ".json").lower()]).decode("utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise PublishError(f"{path}: unreadable sidecar json: {exc}") from exc
        preview = names.get((base + ".png").lower())
    ident = (meta or {}).get("identity") or {}
    return {"key": base, "source": "a101_zip", "archive": str(path), "members": roles, "preview_member": preview,
            "meta": meta, "identity": {"manufacturer": ident.get("manufacturer"), "object_latin":
                                       ident.get("object_name"), "article": ident.get("article"),
                                       "title_ru": (meta or {}).get("title")}}


def _akey(text):
    return lib._article_key(text)


def intake_batch(batch, kind="maf"):
    """Objects of a batch copy + every other file in `drops` with a reason. Read-only."""
    if kind not in KINDS:
        raise PublishError(f"kind {kind!r} is not a library kind {KINDS} (materials later [D372])")
    root = Path(batch)
    if not root.is_dir():
        raise PublishError(f"batch {root} is not a folder")
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name.lower() not in SKIP_FILES)
    if not files:
        raise PublishError(f"batch {root} is empty")
    objects, used, drops = [], set(), []
    for p in files:
        if p.suffix.lower() == ".zip":
            try:
                obj = _zip_object(p)
            except zipfile.BadZipFile as exc:
                drops.append({"path": p.relative_to(root).as_posix(), "reason": f"bad zip: {exc}"})
                used.add(p)
                continue
            if obj:
                obj["files"] = [p]
                objects.append(obj)
                used.add(p)
    zip_keys = {_akey((o["identity"].get("article") or o["key"])): o["key"] for o in objects}
    folders = [root] + sorted(d for d in root.iterdir() if d.is_dir())
    for d in folders:
        own = [p for p in files if p not in used and (p.parent == d if d == root else d in p.parents)]
        fbx = [p for p in own if p.suffix.lower() == ".fbx" and (kind != "maf" or "_groundel" in p.stem.lower())]
        if not fbx:
            continue
        key = d.name if d != root else re.sub(r"_GroundEl.*$", "", fbx[0].stem, flags=re.I)
        k = _akey(key)
        sup = [zk for zk, zname in zip_keys.items() if len(k) >= 4 and len(zk) >= 4 and (k in zk or zk in k)]
        if sup:
            for p in own:
                drops.append({"path": p.relative_to(root).as_posix(),
                              "reason": f"work file, superseded by archive {zip_keys[sup[0]]}"})
                used.add(p)
            continue
        members = {}
        base_stems = set()
        for p in fbx:
            stem = p.stem.lower()
            role = next((role for role, suffix in FBX_ROLES.items() if stem.endswith(suffix)), None)
            if role is not None:
                members[role] = str(p)
                base_stems.add(stem.removesuffix(FBX_ROLES[role]))
            elif len(fbx) == 1:
                members["vpm"] = str(p)  # Legacy single export without a profile suffix.
        # Multiple exports must be in an object subfolder and share a base stem, as in an A101 zip.
        if len(members) != len(fbx) or len(base_stems) > 1 or (d == root and len(fbx) > 1):
            raise PublishError(f"{d}: ambiguous object, {len(fbx)} FBX files: {[p.name for p in fbx]}")
        pngs = [p for p in own if p.suffix.lower() == ".png" and "source" not in p.parts]
        objects.append({"key": key, "source": "folder", "folder": str(d), "members": members,
                        "preview_file": str(pngs[0]) if pngs else None, "meta": None,
                        "identity": {}, "files": own})
        used.update(own)
    for p in files:
        if p not in used:
            ext = p.suffix.lower()
            reason = ("texture/image: materials library is later [D372]" if ext in (".png", ".jpg", ".jpeg", ".tga")
                      else "build script, not a library file" if ext in (".py", ".ms", ".mjs")
                      else "not a library object file (no A101 zip / object FBX)")
            drops.append({"path": p.relative_to(root).as_posix(), "reason": reason})
    keys = [o["key"].lower() for o in objects]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise PublishError(f"batch {root}: objects listed twice: {dup}")
    return {"batch": root.name, "path": str(root), "kind": kind, "objects": objects, "drops": drops,
            "files": len(files)}


# ---- 2 identify ------------------------------------------------------------------------------------------------
def _size_mm(obj):
    geo = ((obj.get("meta") or {}).get("geometry") or {}).get("high") or {}
    bb = geo.get("bbox")
    if isinstance(bb, dict) and all(isinstance(bb.get(a), (int, float)) for a in "xyz"):
        return {a: float(bb[a]) for a in "xyz"}
    return None


def identify_object(obj, unified, catalogue, kind="maf", name=None):
    """duplicate (same maker + article, size within 10 %) / variant (same article, other maker or size) / new.
    Published versions of the SAME library name are not a duplicate: publishing again makes vNNN+1 [D370]."""
    ident = obj.get("identity") or {}
    art = _akey(ident.get("article") or "")
    mk = lib.maker_key(ident.get("manufacturer") or "")
    size = obj.get("size_mm") or _size_mm(obj)
    pool = [dict(r, _from=r.get("source", "unified")) for r in (unified or {}).get("records", [])
            if r.get("source") != "published"]  # the catalogue below is the authority on published records
    pool += [{"name": r["name"], "manufacturer": r["card"].get("manufacturer"), "article": r["card"].get("article"),
              "bbox_mm": {"high": dict(zip("xyz", [v * 1000 for v in r["card"]["size_m"]]))}
              if r["card"].get("size_m") else None, "_from": "published:" + r["status"]}
             for r in catalogue.get("records", []) if r.get("kind") == kind and r.get("status") != "rejected"
             and (name is None or r["name"].lower() != name.lower())]
    hits = [r for r in pool if art and len(art) >= 3 and _akey(r.get("article") or "") == art]
    if not hits:
        return {"result": "new", "of": [], "reason": "no library record with article {!r}".format(
            ident.get("article")) if art else "no article: nothing to match by article"}
    dup, var = [], []
    for r in hits:
        same_maker = mk and lib.maker_key(r.get("manufacturer") or "") == mk
        bb = (r.get("bbox_mm") or {}).get("high")
        dims = None
        if size and bb:
            from_identify = _intake_identify()
            dims = from_identify.dims_check((size["x"], size["y"], size["z"]), bb)
        (dup if same_maker and dims and dims["ok"] else var).append(
            {"name": r["name"], "from": r["_from"], "same_maker": bool(same_maker), "dims": dims})
    if dup:
        return {"result": "duplicate", "of": dup, "reason": "same maker and article, size within 10 %"}
    return {"result": "variant", "of": var, "reason": "same article; maker or size differs (or size unknown)"}


_II = None


def _intake_identify():
    global _II
    if _II is None:
        _II = _load("tools_assets_intake_identify", "tools/assets/intake_identify.py")
    return _II


# ---- 3 name ----------------------------------------------------------------------------------------------------
def _camel(text):
    return "".join(w.capitalize() for w in re.findall(r"[a-z0-9]+", lib.translit(str(text).lower())))[:60]


def library_name(kind, identity, catalogue, key):
    """[D369] Manufacturer_NameLatin_Article; without a manufacturer AGR_<kind>_<Name>_<NNN>. ё=е, translit."""
    if kind not in KINDS:
        raise PublishError(f"kind {kind!r} is not a library kind {KINDS}")
    ident = identity or {}
    maker = (ident.get("manufacturer") or "").strip()
    title = ident.get("object_latin") or ident.get("title_ru") or ""
    art = (ident.get("article") or "").strip()
    if maker:
        if not art:
            raise PublishError(f"{key}: manufacturer {maker!r} without an article; give the article or drop the maker")
        if ident.get("object_latin"):
            obj = re.sub(r"[^0-9A-Za-z]", "", ident["object_latin"])
            mk = maker if re.fullmatch(r"[A-Za-z0-9]+", maker) else lib.propose_maf_name(maker, "x", "0").split("_")[0]
            artn = lib.propose_maf_name("x", "x", art).split("_")[-1]
            name = f"{mk}_{obj}_{artn}"
        else:
            if not title:
                raise PublishError(f"{key}: manufacturer {maker!r} without an object name")
            name = lib.propose_maf_name(maker, title, art)
    else:
        stem = _camel(title or key)
        if not stem:
            raise PublishError(f"{key}: no name to transliterate")
        prefix = f"AGR_{kind}_{stem}_"
        used = [int(r["name"][len(prefix):]) for r in catalogue.get("records", [])
                if r["name"].startswith(prefix) and r["name"][len(prefix):].isdigit()]
        same = [r for r in catalogue.get("records", []) if r.get("origin", {}).get("object") == key
                and r["name"].startswith(prefix)]
        name = same[0]["name"] if same else prefix + "{:03d}".format(max(used, default=0) + 1)
    if not re.fullmatch(r"[A-Za-z0-9]+_[A-Za-z0-9_]+_[A-Za-z0-9.\-]+", name):
        raise PublishError(f"{key}: library name {name!r} is not Manufacturer_Name_Article")
    return name


# ---- 4 qa ------------------------------------------------------------------------------------------------------
def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def qa_profile(report, kind, profile):
    """Checks on one fbx_readback report. Returns {'verdict', 'tris', 'size_m', 'materials', 'findings'}."""
    f = []
    meshes = (report or {}).get("meshes") or []
    if not report or not report.get("readback_ok") or not meshes:
        return {"verdict": "fail", "tris": None, "size_m": None, "materials": [], "findings": [
            f"{profile}: readback has no non-empty mesh"]}
    tris = sum(int(m.get("triangles") or 0) for m in meshes)
    ngons = sum(int(v) for m in meshes for d, v in (m.get("polygon_degrees") or {}).items() if int(d) > 4)
    if tris <= 0:
        f.append(f"{profile}: 0 triangles")
    if ngons:
        f.append(f"{profile}: {ngons} n-gons")
    for m in meshes:
        topo = m.get("topology") or {}
        if "error" in topo:
            f.append(f"{profile}: {m['name']} topology not measured: {topo['error']}")
        if not [s for s in m.get("materials") or [] if s]:
            f.append(f"{profile}: {m['name']} has no material")
    bounds = [m.get("bounds_m") for m in meshes]
    if not all(b and all(_finite(c) for p in b for c in p) for b in bounds):
        f.append(f"{profile}: bounds missing or not finite")
        size = None
    else:
        lo = [min(b[0][i] for b in bounds) for i in range(3)]
        hi = [max(b[1][i] for b in bounds) for i in range(3)]
        size = [round(hi[i] - lo[i], 4) for i in range(3)]
        mode, z0 = PIVOT[kind]
        if mode == "center":
            for i, ax in ((0, "X"), (1, "Y")):
                c = (lo[i] + hi[i]) / 2
                if abs(c) > TOL_M:
                    f.append(f"{profile}: pivot not centred on {ax} ({c:+.3f} m)")
            if abs(lo[2] - z0) > SEAT_TOL_M:
                f.append(f"{profile}: lowest point {lo[2]:+.3f} m, expected {z0:+.3f} m (pivot/seating)")
        elif any(abs(lo[i]) > SEAT_TOL_M for i in range(3)):
            f.append(f"{profile}: bounds start at {lo}, expected [0,0,0] (window bottom-left/front)")
    used = sorted({s for m in meshes for s in (m.get("materials") or []) if s})
    mats = {m.get("name"): m for m in report.get("materials") or []}
    nomap = [n for n in used if not (mats.get(n) or {}).get("maps")]
    if nomap:
        f.append(f"{profile}: materials without texture maps: {nomap}")
    if kind == "maf":
        try:
            twinqa = _twinqa_maf()
            for x in twinqa.maf_findings(meshes, "ground", profile):
                if getattr(x, "status", None) != "pass":
                    f.append(f"{profile}: {x.name}: {x.status}: {x.observed}")
        except Exception as exc:  # recorded, never a pass
            f.append(f"{profile}: maf_findings not run: {type(exc).__name__}: {exc}")
    return {"verdict": "pass" if not f else "fail", "tris": tris, "size_m": size, "materials": used, "findings": f}


def _twinqa_maf():
    sys.path.insert(0, str(ROOT / "src"))
    from twinqa import maf_checks
    return maf_checks


def qa_object(obj, kind, readbacks):
    """readbacks: {'vpm': report|None, 'npm': report|None}. A missing profile is a failing check [D370]."""
    out = {}
    for profile in ("vpm", "npm"):
        rep = readbacks.get(profile)
        out[profile] = qa_profile(rep, kind, profile) if rep is not None else {
            "verdict": "fail", "tris": None, "size_m": None, "materials": [],
            "findings": [f"{profile}: no {profile.upper()} version in the object"]}
    findings = out["vpm"]["findings"] + out["npm"]["findings"]
    return {"verdict": "pass" if not findings else "fail", "vpm": out["vpm"], "npm": out["npm"],
            "findings": findings}


def blender_readback(fbx, out_json, blender=None):
    sys.path.insert(0, str(ROOT / "src"))
    from dt_ai.core.blender_runner import run_blender, BlenderRunError
    try:
        return run_blender(ROOT / "tools/blender/fbx_readback.py", [str(fbx), str(out_json)], executable=blender,
                           output_json=str(out_json), log_path=str(Path(out_json).with_suffix(".log")))
    except BlenderRunError as exc:
        return {"readback_ok": False, "meshes": [], "error": str(exc)}


def extract_members(obj, work):
    """FBX of each profile as a file path (zip members extracted into work/, never into the batch)."""
    out = {}
    for role, member in obj["members"].items():
        if obj["source"] == "a101_zip":
            dest = Path(work) / Path(member).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(obj["archive"]) as zf, open(dest, "wb") as f:
                f.write(zf.read(member))
            out[role] = dest
        else:
            out[role] = Path(member)
    return out


# ---- 5 register ------------------------------------------------------------------------------------------------
def _inside(a, b):
    """a is b or lies inside b; resolved, case-folded on Windows (path aliases: case, `..`, symlinks)."""
    a, b = (Path(os.path.normcase(str(Path(x).resolve()))) for x in (a, b))
    return a == b or b in a.parents


def next_version(target_dir, catalogue, name):
    nums = [int(m.group(1)) for p in (Path(target_dir).iterdir() if Path(target_dir).is_dir() else [])
            for m in [VERSION_RE.match(p.name.split(".")[0])] if m]
    nums += [int(r["version"][1:]) for r in catalogue.get("records", []) if r["name"].lower() == name.lower()]
    return "v{:03d}".format(max(nums, default=0) + 1)


def _check_overlaps(root, srcs, batch):
    for src in srcs:
        if _inside(root, src) or _inside(src, root):
            raise PublishError(f"assets root {root} overlaps the input {src}")
    if _inside(root, batch) or _inside(batch, root):
        raise PublishError(f"assets root {root} overlaps the batch {batch}")


def plan_version(obj, name, kind, qa_result, ident, catalogue, assets_root, batch, issue=None, preview=None):
    """Every refusal of one version that is known before writing; returns the plan and writes NOTHING [#1755].
    `catalogue` may be a shadow copy holding the batch's earlier planned records (counter names, vNNN)."""
    root = Path(assets_root)
    _check_overlaps(root, obj["files"], batch)
    base = root / kind / name
    version = next_version(base, catalogue, name)
    final, partial = base / version, base / (version + ".partial")
    if final.exists() or partial.exists():
        raise PublishError(f"{final} already exists; a version is never overwritten")
    copies, files, seen = [], [], set()
    srcs = list(obj["files"])
    if preview and Path(preview) not in srcs:
        srcs.append(Path(preview))
    for src in srcs:
        rel = Path(src).name if obj["source"] == "a101_zip" else Path(src).relative_to(obj["folder"]).as_posix()
        if src == preview and obj["source"] == "a101_zip":
            rel = "preview_" + Path(src).name
        if os.path.normcase(rel) in seen:
            raise PublishError(f"two inputs map to {partial / rel}")
        seen.add(os.path.normcase(rel))
        h = sha256_file(src)
        suffix = Path(rel).suffix.lower()
        role = ("archive" if suffix == ".zip" else
                next((r for r, m in obj["members"].items() if Path(m) == Path(src)), None) or
                {".max": "max", ".blend": "blend", ".png": "preview", ".jpg": "source", ".dwg": "source"}.get(
                    suffix, "other"))
        copies.append((Path(src), rel, h))
        files.append({"path": f"{kind}/{name}/{version}/{rel}", "sha256": h, "role": role})
    card = {"manufacturer": (obj.get("identity") or {}).get("manufacturer"),
            "title_ru": (obj.get("identity") or {}).get("title_ru"),
            "article": (obj.get("identity") or {}).get("article"),
            "size_m": qa_result["vpm"]["size_m"] or qa_result["npm"]["size_m"],
            "tris": {"vpm": qa_result["vpm"]["tris"], "npm": qa_result["npm"]["tris"]},
            "materials": {"vpm": qa_result["vpm"]["materials"], "npm": qa_result["npm"]["materials"]}}
    preview_path = next((f["path"] for f in files if f["role"] == "preview"), None)
    if obj["source"] == "a101_zip" and obj.get("preview_member"):
        preview_path = f"{files[0]['path']}#{obj['preview_member']}"  # the A101 archive keeps its own preview
    record = {"name": name, "kind": kind, "version": version, "status": "draft", "published": now_iso(),
              "origin": {"batch": Path(batch).name, "object": obj["key"], "issue": issue},
              "identify": ident, "card": card, "preview": preview_path, "files": files,
              "qa": {"verdict": qa_result["verdict"], "findings": qa_result["findings"]},
              "accepted": None, "rejected": None}
    return {"record": record, "copies": copies, "final": final, "partial": partial, "root": root, "batch": batch}


def write_version(plan, catalogue):
    """Copy a planned version into <kind>/<name>/vNNN.partial, verify hashes, rename to vNNN, append the record."""
    final, partial, record = plan["final"], plan["partial"], plan["record"]
    _check_overlaps(plan["root"], [c[0] for c in plan["copies"]], plan["batch"])
    if final.exists() or partial.exists():
        raise PublishError(f"{final} already exists; a version is never overwritten")
    partial.mkdir(parents=True)
    for src, rel, h in plan["copies"]:
        dest = partial / rel
        if dest.exists():
            raise PublishError(f"two inputs map to {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        if sha256_file(dest) != h or sha256_file(src) != h:
            raise PublishError(f"copy of {src} does not match its source")
    (partial / "RECORD.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (partial / "SHA256SUMS.txt").write_text("".join(
        f"{f['sha256']} *{f['path'].split('/', 3)[3]}\n" for f in record["files"]), encoding="utf-8")
    if final.exists():
        raise PublishError(f"{final} appeared during the run; {partial} kept, nothing overwritten")
    try:
        os.rename(partial, final)
    except OSError as exc:
        raise PublishError(f"{final} already exists ({exc}); {partial} kept, nothing overwritten") from exc
    catalogue["records"].append(record)
    return record


def register_version(obj, name, kind, qa_result, ident, catalogue, assets_root, batch, issue=None, preview=None):
    """Copy the object's files into a NEW <kind>/<name>/vNNN/ and append a `draft` record. Never overwrites."""
    return write_version(plan_version(obj, name, kind, qa_result, ident, catalogue, assets_root, batch, issue,
                                      preview), catalogue)


# ---- 6 sheet ---------------------------------------------------------------------------------------------------
def check_sheet_folder(out_dir):
    out = Path(out_dir)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise PublishError(f"sheet folder {out} is not empty; a sheet is never overwritten")
    return out


def write_sheet(out_dir, batch_name, rows, drops, assets_root):
    out = check_sheet_folder(out_dir)
    (out / "previews").mkdir(parents=True, exist_ok=True)
    md = [f"# Library publish — {batch_name}", "",
          "Проверка Артёму: «ок» → `agr library accept <имена> --words \"...\"`; отказ → "
          "`agr library reject <имя> --words \"...\"` (запись в `_inbox/<batch>/REJECTED.md`).", "",
          "| Object | Identify | Library name | Version | QA | Main findings | Preview |", "|---|---|---|---|---|---|---|"]
    cells = []
    for r in rows:
        prev = ""
        if r.get("preview_src"):
            dst = out / "previews" / (r["name"] + Path(r["preview_src"]).suffix.lower())
            shutil.copyfile(r["preview_src"], dst)
            prev = "previews/" + dst.name
        of = ", ".join(o["name"] for o in r["identify"]["of"][:2])
        ident = r["identify"]["result"] + (f" of {of}" if of else "")
        fnd = "; ".join(r["qa"]["findings"][:3]) if r.get("qa") else r.get("skip", "")
        md.append(f"| {r['object']} | {ident} | `{r['name']}` | {r.get('version') or '—'} | "
                  f"{(r.get('qa') or {}).get('verdict', 'not registered')} | {fnd} | "
                  f"{'![](' + prev + ')' if prev else '—'} |")
        cells.append(f"<div class='c'><img src='{html.escape(prev)}'><b>{html.escape(r['name'])}</b> "
                     f"{html.escape(r.get('version') or '')}<br>{html.escape(ident)}<br>QA: "
                     f"{html.escape((r.get('qa') or {}).get('verdict', 'not registered'))}</div>")
    md += ["", f"Dropped / not library files: {len(drops)}", ""] + [f"- `{d['path']}` — {d['reason']}" for d in drops]
    (out / "sheet.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out / "sheet.html").write_text("<html><meta charset='utf-8'><style>.c{display:inline-block;width:320px;"
                                    "margin:6px;vertical-align:top;font:13px sans-serif}.c img{width:320px}</style>"
                                    f"<h2>{html.escape(batch_name)}</h2>" + "".join(cells) + "</html>\n",
                                    encoding="utf-8")
    sums = [f"{sha256_file(p)} *{p.relative_to(out).as_posix()}\n" for p in sorted(out.rglob("*")) if p.is_file()]
    (out / "SHA256SUMS.txt").write_text("".join(sums), encoding="utf-8")
    return out / "sheet.md"


# ---- publish / accept / reject ---------------------------------------------------------------------------------
class OrphanVersions(PublishError):
    """A failure after some versions were written; `registered` holds their records (already in the catalogue)."""

    def __init__(self, msg, registered):
        super().__init__(msg)
        self.registered = registered


def publish(batch, kind, catalogue, unified, assets_root, evidence, identities=None, issue=None, readback=None,
            work=None):
    """Stages 1-6 for one batch. readback(fbx_path, out_json) -> report (Blender by default).
    Plan pass first: every refusal known before writing (overlaps, sheet folder, identities, names, versions) for
    ALL objects; only then does the write pass touch the assets root [#1755]. A failure in the write pass raises
    OrphanVersions naming the versions already made by path; their draft records are in `catalogue`."""
    inv = intake_batch(batch, kind)
    readback = readback or blender_readback
    work = Path(work or Path(evidence).parent / "work" / inv["batch"])
    for p in (work, evidence):
        if _inside(p, batch) or _inside(batch, p):
            raise PublishError(f"{p} overlaps the batch {batch}")
    _check_overlaps(Path(assets_root), [f for o in inv["objects"] for f in o["files"]], batch)
    check_sheet_folder(evidence)
    identities = identities or {}
    unknown = sorted(set(identities) - {o["key"] for o in inv["objects"]})
    if unknown:
        raise PublishError(f"identity file names objects not in the batch: {unknown}")
    for obj in inv["objects"]:
        if obj["key"] in identities:
            obj["identity"] = dict(obj["identity"], **identities[obj["key"]])
        library_name(kind, obj["identity"], catalogue, obj["key"])  # identity refusals before any readback
    shadow = dict(catalogue, records=list(catalogue["records"]))  # planned records: counters and vNNN in order
    rows, plans = [], []
    for obj in inv["objects"]:
        fbx = extract_members(obj, work / obj["key"])
        reps = {role: readback(path, work / obj["key"] / f"readback_{role}.json") for role, path in fbx.items()}
        q = qa_object(obj, kind, reps)
        if q["vpm"]["size_m"]:
            obj["size_mm"] = dict(zip("xyz", [v * 1000 for v in q["vpm"]["size_m"]]))
        name = library_name(kind, obj["identity"], shadow, obj["key"])
        ident = identify_object(obj, unified, shadow, kind, name)
        preview = obj.get("preview_file")
        if obj["source"] == "a101_zip" and obj.get("preview_member"):
            preview = work / obj["key"] / Path(obj["preview_member"]).name
            with zipfile.ZipFile(obj["archive"]) as zf:
                preview.write_bytes(zf.read(obj["preview_member"]))
        row = {"object": obj["key"], "name": name, "identify": ident, "preview_src": str(preview) if preview else None}
        if ident["result"] == "duplicate":
            row["skip"] = "duplicate: not registered, use " + ident["of"][0]["name"]
        else:
            plan = plan_version(obj, name, kind, q, ident, shadow, assets_root, batch, issue,
                                preview=obj.get("preview_file"))
            shadow["records"].append(plan["record"])
            plans.append((row, plan))
        rows.append(row)
    check_sheet_folder(evidence)
    made = []
    try:
        for row, plan in plans:
            rec = write_version(plan, catalogue)
            made.append(rec)
            row.update(version=rec["version"], qa=rec["qa"])
        sheet = write_sheet(Path(evidence), inv["batch"], rows, inv["drops"], assets_root)
        summary = {"batch": inv["batch"], "files": inv["files"], "objects": len(inv["objects"]),
                   "drops": inv["drops"], "rows": rows, "sheet": str(sheet)}
        write_json_atomic(Path(evidence) / "publish.json", summary)
    except (PublishError, OSError) as exc:
        if not made:
            raise
        paths = [str(Path(assets_root) / kind / r["name"] / r["version"]) for r in made]
        raise OrphanVersions(f"{exc}; versions already written (draft records kept in the catalogue): "
                             + ", ".join(paths), made) from exc
    return summary


def _select(catalogue, refs):
    out = []
    for ref in refs:
        name, _, ver = ref.partition("@")
        hits = [r for r in catalogue["records"] if r["name"] == name and (not ver or r["version"] == ver)]
        if not ver:
            hits = [r for r in hits if r["status"] == "draft"]
        if len(hits) != 1:
            raise PublishError(f"{ref}: {len(hits)} matching draft records (give NAME@vNNN)")
        out.append(hits[0])
    return out


def accept_records(catalogue, refs, words, despite_qa=False):
    """Artem's «ок»: draft -> accepted. Refuses non-draft, QA-failed (unless despite_qa) and empty words."""
    if not str(words or "").strip():
        raise PublishError("accept needs Artem's words (--words)")
    recs = _select(catalogue, refs)
    bad = [f"{r['name']}@{r['version']}: status {r['status']}" for r in recs if r["status"] != "draft"]
    bad += [f"{r['name']}@{r['version']}: QA {r['qa']['verdict']}" for r in recs
            if r["qa"]["verdict"] != "pass" and not despite_qa]
    if bad:
        raise PublishError("not accepted: " + "; ".join(bad))
    for r in recs:
        r["status"] = "accepted"
        r["accepted"] = {"date": now_iso(), "by": "Artem", "words": words, "despite_qa": bool(despite_qa)}
    return recs


def reject_record(catalogue, ref, words, inbox_root):
    if not str(words or "").strip():
        raise PublishError("reject needs Artem's words (--words)")
    (r,) = _select(catalogue, [ref])
    if r["status"] != "draft":
        raise PublishError(f"{ref}: status {r['status']}, only a draft can be rejected")
    batch_dir = Path(inbox_root) / r["origin"]["batch"]
    if not batch_dir.is_dir():
        raise PublishError(f"origin batch {batch_dir} not found")
    r["status"] = "rejected"
    r["rejected"] = {"date": now_iso(), "by": "Artem", "words": words}
    with open(batch_dir / "REJECTED.md", "a", encoding="utf-8") as f:
        f.write(f"- {r['rejected']['date']} `{r['name']}` {r['version']} (object {r['origin']['object']}): {words}\n")
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agr library", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish")
    p.add_argument("batch")
    p.add_argument("--kind", default="maf", choices=KINDS)
    p.add_argument("--identity", help="JSON {object key: {manufacturer, title_ru, article}} with sources")
    p.add_argument("--assets-root", default="G:/Мой диск/AGR-assets")
    p.add_argument("--catalogue", default=str(CATALOGUE))
    p.add_argument("--unified", default=str(ROOT / "library/assets/maf_unified.json"))
    p.add_argument("--evidence", required=True, help="new folder for the sheet (AGR-evidence/<issue>/<batch>)")
    p.add_argument("--issue")
    p.add_argument("--blender")
    for c in ("accept", "reject"):
        q = sub.add_parser(c)
        q.add_argument("refs", nargs="+" if c == "accept" else 1)
        q.add_argument("--words", required=True)
        q.add_argument("--catalogue", default=str(CATALOGUE))
        if c == "accept":
            q.add_argument("--despite-qa", action="store_true")
        else:
            q.add_argument("--inbox-root", default="G:/Мой диск/AGR-assets/_inbox")
    q = sub.add_parser("reindex", help="rebuild the MAF search index now (A101 rescan + published records)")
    q.add_argument("--catalogue", default=str(CATALOGUE))
    j = sub.add_parser("check-job", help="close-out guard: every MAF master in the job outputs has a library entry")
    j.add_argument("job", help="jobs/<ID> folder (reads job.yaml artifacts)")
    j.add_argument("--outputs", action="append", default=[], help="output folder to scan as well (repeatable)")
    j.add_argument("--catalogue", default=str(CATALOGUE))
    for q in (p, sub.choices["accept"], sub.choices["reject"], sub.choices["reindex"], j):
        q.add_argument("--index", help="search index to rebuild / read (default: the repo index for the repo "
                                       "catalogue, else maf_unified.json next to --catalogue)")
        if q is not j:
            q.add_argument("--a101-root", help=f"rescan these A101 archives (default {DEFAULT_A101} for the repo index)")
    a = ap.parse_args(argv)
    try:
        cat = load_catalogue(a.catalogue)
        if a.cmd == "reindex":
            _refresh_index(a, cat)
            return 0
        if a.cmd == "check-job":
            ip = index_path(a.catalogue, a.index)
            unified = json.loads(ip.read_text(encoding="utf-8")) if ip.is_file() else {"records": []}
            paths = job_artifacts(a.job) + [Path(o) for o in a.outputs]
            if not paths:
                print(f"check-job {a.job}: REFUSED: nothing to check: no job.yaml artifacts and no --outputs",
                      file=sys.stderr)
                return 2
            gone = [p for p in paths if not p.exists()]
            if gone:
                for p in gone:
                    print(f"check-job {a.job}: REFUSED: output path not found: {p}", file=sys.stderr)
                return 2
            n_files = sum(1 for b in paths for p in ([b] if b.is_file() else b.rglob("*")) if p.is_file())
            n_masters = len(maf_masters(paths))
            miss = unpublished_maf(paths, cat, unified)
            for m in miss:
                print(f"UNPUBLISHED MAF: {m['path']} (object {m['key']}): {m['reason']}", file=sys.stderr)
            print(f"check-job {a.job}: scanned {n_files} file(s), {n_masters} MAF master(s), "
                  f"{len(miss)} unpublished MAF master(s)")
            return 1 if miss else 0
        if a.cmd == "publish":
            if _inside(a.catalogue, a.batch):
                raise PublishError("catalogue lies inside the batch")
            unified = json.loads(Path(a.unified).read_text(encoding="utf-8")) if a.kind == "maf" else {"records": []}
            ids = json.loads(Path(a.identity).read_text(encoding="utf-8")) if a.identity else {}
            ids = {k: v for k, v in ids.items() if not k.startswith("_")}
            rb = (lambda f, o: blender_readback(f, o, a.blender))
            if a.a101_root is None and index_path(a.catalogue, a.index).resolve() == UNIFIED.resolve():
                a.a101_root = str(Path(a.assets_root) / "maf" / "a101")
            res = publish(a.batch, a.kind, cat, unified, a.assets_root, a.evidence, ids, a.issue, rb)
            write_json_atomic(a.catalogue, cat)
            _refresh_index(a, cat)
            for r in res["rows"]:
                print(f"{r['object']}: {r['identify']['result']} -> {r['name']} {r.get('version', '-')} "
                      f"QA {(r.get('qa') or {}).get('verdict', r.get('skip'))}")
            print(f"sheet: {res['sheet']}; drops {len(res['drops'])}")
            if not res["rows"]:
                print("ERROR: no library object in the batch; every file is in the drop list", file=sys.stderr)
                return 1
            return 0 if all((r.get("qa") or {}).get("verdict", "pass") == "pass" for r in res["rows"]) else 1
        if a.cmd == "accept":
            recs = accept_records(cat, a.refs, a.words, a.despite_qa)
        else:
            recs = [reject_record(cat, a.refs[0], a.words, a.inbox_root)]
        write_json_atomic(a.catalogue, cat)
        _refresh_index(a, cat)
        for r in recs:
            print(f"{r['name']}@{r['version']}: {r['status']}")
        return 0
    except PublishError as exc:
        if getattr(exc, "registered", None):
            write_json_atomic(a.catalogue, cat)  # describe the versions already made; never leave them orphan
            try:
                _refresh_index(a, cat)  # the orphan drafts are visible too [D421]
            except (PublishError, OSError, ValueError) as idx_exc:
                print(f"ERROR: index not rebuilt: {idx_exc}", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1 if a.cmd in ("accept", "reject") and "not accepted" in str(exc) else 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
