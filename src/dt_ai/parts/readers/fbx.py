"""FBX structure facts (`structure.json`) -> draft parts list for gate 1 [D111, D124, D125, D108] (#339).

    python -m dt_ai.parts.readers.fbx <structure.json> <parts.json> [--fbx <model.fbx>] [--object-id ID] [--synthetic]

The facts come from `tools/blender/fbx_structure.py` (headless Blender [D110]). This half is pure Python: one part
per mesh object; a file without structure (one mesh object, no layer, no component) is split per material id
[D111]. Every part starts as `part_class="other"` / `operation="keep"` unless the name table below maps the class;
legend items stay empty for the album match. Contacts become questions "weld or embed?" - joints are decided at
gate 1, never guessed here [D124]. The output is validated with the pydantic `PartsList` and with
`schemas/PartsList.schema.json` before anything is written; any doubt fails closed with no output file.
Pattern: n/a | new-case: FBX structure facts -> draft PartsList, split by material id without structure (#339).
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

from dt_ai.core.io import json_bytes, read_json
from dt_ai.core.models import SourceRef
from dt_ai.parts.model import PartEntry, PartSource, PartsList, Question, TriangleBudget
from dt_ai.parts.readers.geometry import contacts

FORMAT = "fbx_structure/1"
CONTACT_TOLERANCE_M = 0.002
SCHEMA_PATH = Path(__file__).resolve().parents[4] / "schemas" / "PartsList.schema.json"

# Name rules: the first rule whose pattern fully matches one name token sets the part class. Tokens are the
# lower-case runs of letters / digits, so "Swallow" is not a wall. Operation stays "keep" [D108]: every other
# operation needs a decision (build_as, library_ref) the reader does not make.
NAME_RULES = [
    (r"walls?|стен\w*", "wall"),
    (r"slabs?|floors?|плит\w*|перекрыти\w*", "slab"),
    (r"parapets?|парапет\w*", "parapet"),
    (r"windows?|окн\w*|окон\w*", "window"),
    (r"doors?|двер\w*", "door"),
    (r"glass|glazing|стекл\w*|витраж\w*", "glazing"),
    (r"railings?|handrails?|перил\w*|огражд\w*", "railing"),
    (r"fences?|забор\w*", "fence"),
    (r"balcon(?:y|ies)|балкон\w*", "balcony"),
    (r"grilles?|решетк\w*|решётк\w*", "grille"),
    (r"pilasters?|пилястр\w*", "pilaster"),
]


class StructureError(ValueError):
    """The facts file cannot be turned into a parts list without guessing."""


def part_class_for(name: str) -> str:
    tokens = [t for t in re.split(r"[^0-9a-zа-яё]+", name.lower()) if t]
    for pattern, part_class in NAME_RULES:
        if any(re.fullmatch(pattern, t) for t in tokens):
            return part_class
    return "other"


def _hash8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def sanitise(name: str) -> str:
    """A `Name` id: ASCII letters, digits, underscores, starting with a letter."""
    s = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")[:100]
    if not s:
        return "p_" + _hash8(name)
    return s if s[0].isalpha() else "p_" + s


class _Ids:
    def __init__(self):
        self.used = set()

    def take(self, name: str, base: str | None = None) -> str:
        base = base or sanitise(name)
        for candidate in (base, f"{base[:100]}_{_hash8(name)}"):
            if candidate not in self.used:
                self.used.add(candidate)
                return candidate
        raise StructureError(f"duplicate part id {base!r} for {name!r} cannot be disambiguated")


# ---- facts validation ----

def _int(value, what, minimum=0):
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise StructureError(f"{what}: expected an integer >= {minimum}, got {value!r}")
    return value


def _text(value, what):
    if not isinstance(value, str) or not value:
        raise StructureError(f"{what}: expected a non-empty string")
    return value


def _box(value, what):
    if not isinstance(value, dict) or set(value) != {"min", "max"}:
        raise StructureError(f"{what}: bbox must be {{min, max}}")
    out = []
    for key in ("min", "max"):
        v = value[key]
        if not (isinstance(v, list) and len(v) == 3 and all(
                isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in v)):
            raise StructureError(f"{what}: bbox {key} must be three finite numbers")
        out.append([float(c) for c in v])
    if any(lo > hi for lo, hi in zip(*out)):
        raise StructureError(f"{what}: bbox min exceeds max")
    return tuple(out)


def _counts(value, what):
    if not isinstance(value, dict):
        raise StructureError(f"{what}: expected a mapping material index -> count")
    out = {}
    for key, count in value.items():
        if not re.fullmatch(r"0|[1-9][0-9]*", key):
            raise StructureError(f"{what}: material index {key!r} is not a non-negative integer")
        out[int(key)] = _int(count, f"{what}[{key}]")
    return out


def validate_facts(facts) -> dict:
    """Structural check of the facts file; returns {name: object} for mesh objects with triangles."""
    if not isinstance(facts, dict):
        raise StructureError("structure.json must hold a JSON object")
    if "error" in facts:
        raise StructureError(f"the extractor reported an error: {facts['error']}")
    if facts.get("format") != FORMAT:
        raise StructureError(f"format must be {FORMAT!r}, got {facts.get('format')!r}")
    if facts.get("sections") != "not_in_fbx":
        raise StructureError("sections must be 'not_in_fbx': FBX carries no sections")
    source = facts.get("source")
    if not isinstance(source, dict):
        raise StructureError("source must be an object")
    _text(source.get("name"), "source.name")
    if not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
        raise StructureError("source.sha256 must be 64 lower-case hex digits")
    _text(facts.get("blender"), "blender")
    units = facts.get("units")
    scale = units.get("scale_length") if isinstance(units, dict) else None
    if not (isinstance(scale, (int, float)) and not isinstance(scale, bool) and math.isfinite(scale) and scale > 0):
        raise StructureError("units.scale_length must be a finite positive number")
    if facts.get("contact_tolerance_m") != CONTACT_TOLERANCE_M:
        raise StructureError(f"contact_tolerance_m must be {CONTACT_TOLERANCE_M}")
    objects = facts.get("objects")
    if not isinstance(objects, list):
        raise StructureError("objects must be a list")
    for key in ("components", "contacts"):
        if not isinstance(facts.get(key), list):
            raise StructureError(f"{key} must be a list")
    names = set()
    for i, o in enumerate(objects):
        if not isinstance(o, dict):
            raise StructureError(f"objects[{i}] must be an object")
        name = _text(o.get("name"), f"objects[{i}].name")
        if name in names:
            raise StructureError(f"duplicate object name {name!r}: part ids cannot be disambiguated")
        names.add(name)
        _text(o.get("type"), f"{name}.type")
        if o.get("parent") is not None:
            _text(o["parent"], f"{name}.parent")
        if not isinstance(o.get("collections"), list) or not all(isinstance(c, str) and c for c in o["collections"]):
            raise StructureError(f"{name}.collections must be a list of names")
        if o["type"] != "MESH":
            continue
        _text(o.get("mesh"), f"{name}.mesh")
        tris = _int(o.get("triangles"), f"{name}.triangles")
        _int(o.get("polygons"), f"{name}.polygons")
        _int(o.get("connected_components"), f"{name}.connected_components")
        o["_box"] = _box(o.get("bbox"), name)
        slots = o.get("material_slots")
        if not isinstance(slots, list) or not all(s is None or isinstance(s, str) for s in slots):
            raise StructureError(f"{name}.material_slots must be a list of names or nulls")
        _counts(o.get("face_material_counts"), f"{name}.face_material_counts")
        per_mat = _counts(o.get("triangle_material_counts"), f"{name}.triangle_material_counts")
        if sum(per_mat.values()) != tris:
            raise StructureError(f"{name}: triangles per material add up to {sum(per_mat.values())}, not {tris}")
    for o in objects:
        if o.get("parent") is not None and o["parent"] not in names:
            raise StructureError(f"{o['name']}: parent {o['parent']!r} is not in the file")
    meshes = [o for o in objects if o["type"] == "MESH"]
    if not meshes:
        raise StructureError("no mesh objects in the structure")
    if not any(o["triangles"] for o in meshes):
        raise StructureError("every mesh object has zero triangles")
    return {o["name"]: o for o in meshes}


def _components(facts, meshes) -> dict:
    """Mesh data shared by several objects = a component; the facts' list must say the same."""
    users = {}
    for o in meshes.values():
        users.setdefault(o["mesh"], []).append(o["name"])
    derived = {m: sorted(n) for m, n in users.items() if len(n) > 1}
    given = {}
    for c in facts["components"]:
        if not isinstance(c, dict) or not isinstance(c.get("mesh"), str) or not isinstance(c.get("objects"), list):
            raise StructureError("components entries must be {mesh, objects}")
        given[c["mesh"]] = sorted(c["objects"])
    if given != derived:
        raise StructureError(f"components {given} disagree with shared mesh data {derived}")
    return {name: m for m, names in derived.items() for name in names}


def _contacts(facts, meshes) -> list[dict]:
    """Recompute bbox contacts of non-empty meshes and require the extractor's list to agree."""
    boxes = {n: o["_box"] for n, o in meshes.items() if o["triangles"]}
    found = contacts(boxes, CONTACT_TOLERANCE_M)
    given = set()
    for c in facts["contacts"]:
        if not isinstance(c, dict) or not isinstance(c.get("a"), str) or not isinstance(c.get("b"), str):
            raise StructureError("contacts entries must be {a, b, gap_m}")
        given.add(tuple(sorted((c["a"], c["b"]))))
    if given != {(c["a"], c["b"]) for c in found}:
        raise StructureError(f"contacts {sorted(given)} disagree with the bounding boxes "
                             f"{sorted((c['a'], c['b']) for c in found)}")
    return found


def _layer(o, by_name) -> str | None:
    if o["collections"]:
        return o["collections"][0]
    root, seen = o, set()
    while root.get("parent") is not None:
        if root["name"] in seen:
            raise StructureError(f"{o['name']}: parent cycle")
        seen.add(root["name"])
        root = by_name[root["parent"]]
    return root["name"] if root is not o else None


def _material_ref(o, index) -> str:
    slots = o["material_slots"]
    return f"{index}:{slots[index]}" if index < len(slots) and slots[index] else str(index)


def convert(facts, *, synthetic: bool, object_id: str | None = None) -> PartsList:
    meshes = validate_facts(facts)
    by_name = {o["name"]: o for o in facts["objects"]}
    component_of = _components(facts, meshes)
    layer_of = {n: _layer(o, by_name) for n, o in meshes.items()}
    non_empty = [o for o in meshes.values() if o["triangles"]]
    structured = len(meshes) > 1 or bool(component_of) or any(layer_of.values())
    found = _contacts(facts, meshes)

    ids, part_id = _Ids(), {}
    ordered = sorted(non_empty, key=lambda o: (sanitise(o["name"]) != o["name"], o["name"]))
    for o in ordered:
        part_id[o["name"]] = ids.take(o["name"])
    parts = []
    for o in sorted(non_empty, key=lambda o: o["name"]):
        name = o["name"]
        sources = [PartSource(kind="object", reference=name)]
        if layer_of[name]:
            sources.append(PartSource(kind="layer", reference=layer_of[name]))
        if name in component_of:
            sources.append(PartSource(kind="component", reference=component_of[name]))
        per_mat = {i: n for i, n in _counts(o["triangle_material_counts"], name).items() if n}
        part_class = part_class_for(name)
        if not structured and len(per_mat) > 1:  # no structure: split by material id [D111]
            ids.used.discard(part_id[name])
            for index, tris in sorted(per_mat.items()):
                pid = ids.take(f"{name}#m{index}", f"{part_id[name][:100]}_m{index}")
                parts.append(PartEntry(id=pid, part_class=part_class, operation="keep",
                                       sources=[*sources, PartSource(kind="material_id",
                                                                     reference=_material_ref(o, index))],
                                       triangle_budget=TriangleBudget(npm=tris, vpm=tris)))
            continue
        parts.append(PartEntry(id=part_id[name], part_class=part_class, operation="keep", sources=sources,
                               triangle_budget=TriangleBudget(npm=o["triangles"], vpm=o["triangles"])))

    questions = [Question(audience="user", text=(
        f"Joint {part_id[c['a']]} / {part_id[c['b']]}: objects '{c['a']}' and '{c['b']}' touch "
        f"(bbox gap {c['gap_m'] * 1000:.1f} mm <= {CONTACT_TOLERANCE_M * 1000:.0f} mm) - weld or embed "
        f"10-20 mm? [D124]")) for c in found]
    empty = sorted(n for n, o in meshes.items() if not o["triangles"])
    if empty:
        questions.append(Question(audience="user", text=(
            f"Mesh objects with zero triangles were left out of the parts list: {', '.join(empty)}. Needed?")))
    total = sum(p.triangle_budget.npm for p in parts)
    source = facts["source"]
    return PartsList(synthetic=synthetic,
                     object_id=object_id or sanitise(Path(source["name"]).stem),
                     source_tier="B" if structured else "C",
                     sources=[SourceRef(kind="model", reference=source["name"], sha256=source["sha256"])],
                     triangle_budget=TriangleBudget(npm=total, vpm=total), parts=parts, joints=[],
                     questions=questions, status="draft", gate1=None)


# ---- JSON Schema check (the keywords pydantic emits; jsonschema is not a dependency) ----

_ANNOTATIONS = {"title", "description", "default", "$defs"}
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _type_ok(value, kind) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[kind])


def schema_errors(instance, schema, root=None, path="$") -> list[str]:
    """Errors of `instance` against a JSON schema; an unsupported keyword raises (fail closed)."""
    root = root if root is not None else schema
    errors = []
    unknown = set(schema) - _ANNOTATIONS - {"$ref", "anyOf", "type", "const", "enum", "properties", "required",
                                            "additionalProperties", "items", "minItems", "maxItems", "minLength",
                                            "maxLength", "pattern", "minimum", "maximum"}
    if unknown:
        raise ValueError(f"schema keywords not supported: {sorted(unknown)}")
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"unsupported $ref {ref}")
        errors += schema_errors(instance, root["$defs"][ref[len("#/$defs/"):]], root, path)
    if "anyOf" in schema and all(schema_errors(instance, s, root, path) for s in schema["anyOf"]):
        errors.append(f"{path}: matches no anyOf branch")
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(instance, k) for k in kinds):
            return errors + [f"{path}: expected {schema['type']}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']}")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0) or len(instance) > schema.get("maxLength", math.inf):
            errors.append(f"{path}: length out of range")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: does not match {schema['pattern']}")
    if _type_ok(instance, "number"):
        if instance < schema.get("minimum", -math.inf) or instance > schema.get("maximum", math.inf):
            errors.append(f"{path}: {instance} out of range")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0) or len(instance) > schema.get("maxItems", math.inf):
            errors.append(f"{path}: item count out of range")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors += schema_errors(item, schema["items"], root, f"{path}[{i}]")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        errors += [f"{path}: missing {k}" for k in schema.get("required", []) if k not in instance]
        for key, value in instance.items():
            if key in props:
                errors += schema_errors(value, props[key], root, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors += schema_errors(value, schema["additionalProperties"], root, f"{path}.{key}")
    return errors


# ---- CLI ----

def run(structure: Path, output: Path, *, fbx: Path | None, object_id: str | None, synthetic: bool) -> PartsList:
    structure, output = Path(structure), Path(output)
    guarded = [structure] + ([Path(fbx)] if fbx else [])
    if any(output.resolve() == p.resolve() for p in guarded):
        raise StructureError("the output path resolves to an input")
    raw = structure.read_bytes()
    if not raw.strip():
        raise StructureError(f"{structure} is empty")
    try:
        facts = read_json(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise StructureError(f"{structure} is not valid JSON: {exc}") from exc
    if fbx is not None:
        fbx = Path(fbx)
        if not isinstance(facts, dict) or not isinstance(facts.get("source"), dict):
            raise StructureError("structure.json has no source block")
        if fbx.name != facts["source"].get("name"):
            raise StructureError(f"{fbx.name} is not the FBX named in the facts ({facts['source'].get('name')})")
        sha = hashlib.sha256(fbx.read_bytes()).hexdigest()
        if sha != facts["source"].get("sha256"):
            raise StructureError(f"{fbx.name}: sha256 {sha} does not match the facts ({facts['source'].get('sha256')})")
    parts = convert(facts, synthetic=synthetic, object_id=object_id)
    data = json.loads(parts.model_dump_json())
    PartsList.model_validate(data)
    errors = schema_errors(data, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    if errors:
        raise StructureError("PartsList.schema.json: " + "; ".join(errors[:5]))
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".partial")
    tmp.write_bytes(json_bytes(data))
    os.replace(tmp, output)
    return parts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dt_ai.parts.readers.fbx", description=__doc__.splitlines()[0])
    ap.add_argument("structure", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--fbx", type=Path, help="the FBX the facts name; its sha256 must match")
    ap.add_argument("--object-id", help="parts list object id (default: the FBX stem)")
    ap.add_argument("--synthetic", action="store_true", help="the source is a synthetic fixture")
    args = ap.parse_args(argv)
    try:
        parts = run(args.structure, args.output, fbx=args.fbx, object_id=args.object_id, synthetic=args.synthetic)
    except (OSError, ValueError) as exc:  # StructureError and pydantic ValidationError are ValueErrors
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(parts.parts)} parts, tier {parts.source_tier}, {len(parts.questions)} questions, "
          f"{parts.triangle_budget.npm} triangles -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
