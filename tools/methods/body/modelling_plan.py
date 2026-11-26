"""new-case: offline Step 3 OKS planning sheet, not scene processing or approval."""

import argparse
from collections import defaultdict
from hashlib import file_digest, sha256
from io import BytesIO
import json
from pathlib import Path
import sys
from typing import Annotated, Literal

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Key = Annotated[str, StringConstraints(min_length=1, max_length=250, pattern=r"^\S(?:[^\r\n]*\S)?$")]
Digest = Annotated[str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
Mode = Literal["geometry", "inset", "texture", "not_shown"]
MODES = {
    "geometry": ("Геометрия", "#245c7a"), "inset": ("Вставка", "#16634c"),
    "texture": ("Текстура", "#703f86"), "not_shown": ("Не показывать", "#67605b"),
}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class Element(Input):
    name: Key
    layer: Key
    family: Key


class Split(Input):
    schema_id: Literal["agr-oks-split/1"] = Field(alias="schema")
    status: Literal["accepted", "proposed"]
    object: Key
    scene_sha256: Digest
    approval_ref: Text | None
    layers: Annotated[list[Key], Field(min_length=1)]
    objects: Annotated[list[Element], Field(min_length=1)]


class Decision(Input):
    layer: Key
    family: Key
    representation: Mode
    reason: Text


class Recipe(Input):
    schema_id: Literal["agr-oks-modelling-recipe/1"] = Field(alias="schema")
    split_sha256: Digest
    profile: Literal["npm", "vpm"]
    simplification_cm: Annotated[float, Field(ge=5, le=10, allow_inf_nan=False)]
    simplification: Text
    typical_floors: Text
    expected_triangles: Annotated[int, Field(gt=0)]
    planning_ceiling_triangles: Annotated[int, Field(gt=0, le=150000)]  # Project target [D010].
    comparison: Text
    rows: Annotated[list[Decision], Field(min_length=1)]


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _nonfinite(token):
    raise ValueError(f"unsupported JSON number: {token}")


def _parse(model, data):
    return model.model_validate(json.loads(data, object_pairs_hook=_unique_keys, parse_constant=_nonfinite))


def _hash_file(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _rows(split, recipe):
    layers = set(split.layers)
    if len(layers) != len(split.layers):
        raise ValueError("duplicate split layer")
    names = set()
    groups = defaultdict(list)
    for obj in split.objects:
        if obj.layer not in layers:
            raise ValueError(f"unmapped layer: {obj.layer} ({obj.name})")
        if obj.layer.startswith("00_"):
            raise ValueError(f"unresolved layer: {obj.layer} ({obj.name})")
        if obj.name in names:
            raise ValueError(f"duplicate split object: {obj.name}")
        names.add(obj.name)
        groups[obj.layer, obj.family].append(obj.name)
    decisions = {}
    for row in recipe.rows:
        key = (row.layer, row.family)
        if key in decisions:
            raise ValueError(f"duplicate recipe row: {key}")
        if key not in groups:
            raise ValueError(f"unmapped recipe row: {key}")
        decisions[key] = row
    if missing := groups.keys() - decisions.keys():
        raise ValueError(f"missing recipe rows: {sorted(missing)}")
    order = {layer: i for i, layer in enumerate(split.layers)}
    return [dict(decisions[k].model_dump(), objects=sorted(groups[k]))
            for k in sorted(groups, key=lambda key: (order[key[0]], key[1]))]


def _wrap(text, font, width):
    for paragraph in text.splitlines():
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}" if line else word
            if font.getlength(candidate) <= width:
                line = candidate
            else:
                if line:
                    yield line
                line = ""
                for char in word:
                    if font.getlength(line + char) > width:
                        yield line
                        line = ""
                    line += char
        yield line


def render_sheet(plan, font_data, photos):
    """Draw one sheet with a complete layer/family table and visible gate status."""
    title, heading, normal, small = [ImageFont.truetype(BytesIO(font_data), size)
                                     for size in (44, 28, 23, 20)]
    commands = []
    y = 24

    def text(value, x, top, font=normal, fill="#142a3b", width=1704):
        lines = list(_wrap(value, font, width))
        step = font.size + 7
        for i, line in enumerate(lines):
            commands.append(("text", ((x, top + i * step), line), {"font": font, "fill": fill}))
        return top + step * len(lines)

    def rect(y1, y2, fill):
        commands.append(("rectangle", ((0, y1, 1799, y2),), {"fill": fill}))

    y = text(f"План моделирования ОКС · {plan['object']}", 48, y, title)
    status = ("ЧЕРНОВИК · разбиение не принято · не начинать моделирование"
              if plan["status"] == "draft_unaccepted_split" else
              "НА ПРИЁМКУ · разбиение принято, план не принят · не начинать моделирование")
    y = text(status, 48, y + 5, heading, "#a03421")
    sections = [
        ("Бюджет", (f"{plan['profile'].upper()}: ожидается {plan['expected_triangles']:,} треуг.; "
                    f"потолок планирования {plan['planning_ceiling_triangles']:,} треуг. "
                    "Это оценка, не результат экспорта.").replace(",", " ")),
        ("Упрощение", f"{plan['simplification_cm']:g} см — {plan['simplification']}"),
        ("Типовые этажи", plan["typical_floors"]),
        ("Сравнение с референсом", plan["comparison"]),
    ]
    for label, value in sections:
        y = text(f"{label}: {value}", 48, y + 5)
    panels = []
    if photos:
        y += 12
        for x, (label, image) in zip((48, 924), photos, strict=True):
            image.thumbnail((828, 410))
            image_top = text(label, x, y, heading, width=828)
            panels.append((image, (x + (828 - image.width) // 2, image_top + 4)))
        y = max(top + im.height for im, (_, top) in panels)
    totals = defaultdict(int)
    by_layer = defaultdict(list)
    for row in plan["rows"]:
        totals[row["representation"]] += len(row["objects"])
        by_layer[row["layer"]].append(row)
    y = text("Объекты: " + "   ·   ".join(f"{label}: {totals[k]}" for k, (label, _) in MODES.items()),
             48, y + 18, heading) + 5
    for layer in plan["layers"]:
        rows = by_layer[layer]
        rect(y, y + 40, "#d9e8ef")
        y = text(f"{layer}   ·   {sum(len(r['objects']) for r in rows)} объектов", 48, y + 4, heading) + 7
        for i, row in enumerate(rows):
            label, color = MODES[row["representation"]]
            reason = row["reason"]
            h = max(len(list(_wrap(reason, small, 816))),
                    len(list(_wrap(row["family"], small, 590)))) * (small.size + 7) + 6
            if i % 2 == 0:
                rect(y, y + h, "#f0f5f7")
            text(row["family"], 48, y + 2, small, width=590)
            text(str(len(row["objects"])), 656, y + 2, small, width=64)
            text(label, 741, y + 2, small, color, width=178)
            text(reason, 936, y + 2, small, width=816)
            y += h
    y = text(f"Разбиение SHA-256: {plan['inputs']['split']['sha256']}", 48, y + 12, small)
    image = Image.new("RGB", (1800, max(500, y + 18)), "#ffffff")
    draw = ImageDraw.Draw(image)
    for operation, args, kwargs in commands:
        getattr(draw, operation)(*args, **kwargs)
    for panel, pos in panels:
        image.paste(panel, pos)
    png = BytesIO()
    image.save(png, format="PNG")
    return png.getvalue()


def generate(split_path, scene, recipe_path, out, *, font, evidence=None, preview=False,
             split_image=None, reference_image=None):
    """Prepare bytes privately, recheck inputs, then write into a new directory only."""
    paths = {"split": split_path, "scene": scene, "recipe": recipe_path, "font": font}
    if evidence is not None:
        paths["evidence"] = evidence
    if (split_image is None) != (reference_image is None):
        raise ValueError("supply both split and reference images, or neither")
    if split_image is not None:
        paths.update(split_image=split_image, reference_image=reference_image)
    paths = {role: Path(path).absolute() for role, path in paths.items()}
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError(f"output must be a new directory: {out}")
    if len({(st.st_dev, st.st_ino) for st in (path.stat() for path in paths.values())}) != len(paths):
        raise ValueError("duplicate input files (including path aliases)")
    blobs = {role: path.read_bytes() for role, path in paths.items() if role != "scene"}
    hashes = {role: sha256(data).hexdigest() for role, data in blobs.items()}
    hashes["scene"] = _hash_file(paths["scene"])
    split = _parse(Split, blobs["split"])
    recipe = _parse(Recipe, blobs["recipe"])
    if preview:
        if split.status != "proposed" or split.approval_ref is not None:
            raise ValueError("--preview requires proposed status and null approval_ref")
    elif split.status != "accepted" or split.approval_ref is None:
        raise ValueError("accepted split and approval_ref required (proposals require --preview)")
    if split.scene_sha256 != hashes["scene"]:
        raise ValueError("stale split: scene_sha256 mismatch")
    if recipe.split_sha256 != hashes["split"]:
        raise ValueError("stale recipe: split_sha256 mismatch")
    if recipe.expected_triangles >= recipe.planning_ceiling_triangles:
        raise ValueError("expected_triangles must be below the planning ceiling (leave headroom)")
    plan = {
        "schema": "agr-oks-modelling-plan/1",
        "status": "draft_unaccepted_split" if preview else "pending_picture_acceptance",
        "object": split.object, "split_status": split.status, "approval_ref": split.approval_ref,
        "inputs": {role: {"name": path.name, "sha256": hashes[role]} for role, path in paths.items()},
        "layers": split.layers, **recipe.model_dump(exclude={"schema_id", "split_sha256", "rows"}),
        "rows": _rows(split, recipe),
    }
    photos = []
    if split_image is not None:
        for label, role in [("Разбиение исходника", "split_image"), ("Исторический референс", "reference_image")]:
            with Image.open(BytesIO(blobs[role])) as image:
                photos.append((label, image.convert("RGB")))
    png = render_sheet(plan, blobs["font"], photos)
    plan["sheet_sha256"] = sha256(png).hexdigest()
    data = (json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    for role, path in paths.items():
        if _hash_file(path) != hashes[role]:
            raise ValueError(f"input changed before publication: {role} ({path})")
    out.mkdir()
    # Write the PNG first; the manifest records its exact bytes. Neither name can clobber a file.
    with (out / "modelling_plan.png").open("xb") as stream:
        stream.write(png)
    with (out / "modelling_plan.json").open("xb") as stream:
        stream.write(data)
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("split", "scene", "recipe", "out"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--font", type=Path, required=True, help="TrueType font with Cyrillic glyphs")
    parser.add_argument("--evidence", type=Path, help="optional evidence manifest to hash alongside the recipe")
    parser.add_argument("--preview", action="store_true", help="watermark a proposed split, never certify it")
    parser.add_argument("--split-image", type=Path)
    parser.add_argument("--reference-image", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = generate(args.split, args.scene, args.recipe, args.out, font=args.font,
                        evidence=args.evidence, preview=args.preview, split_image=args.split_image,
                        reference_image=args.reference_image)
    except (ValueError, OSError, Image.DecompressionBombError) as exc:
        print(f"modelling plan: {exc}", file=sys.stderr)
        return 2
    print(f"{plan['status']}: {len(plan['rows'])} layer/family rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
