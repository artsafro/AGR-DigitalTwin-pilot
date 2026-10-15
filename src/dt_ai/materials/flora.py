"""Flora image handoff, white cut-out, review and approved per-species maps.

Pattern / new-case: explicit external generation handoff, content-addressed
candidates, and an all-or-nothing human approval gate before library publication.
No image generation or approval is simulated. Generation is an external manual
handoff. Approval records are user attestations, not an authentication mechanism.
The issue #190 Codex 1254 -> 2048 exception is explicit and records LANCZOS
provenance; it adds no native detail and never grants texture approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
from io import BytesIO
from html import escape
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 2048

REPO = Path(__file__).resolve().parents[3]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_bytes(canonical(value))


def external_destination(path):
    """Reject repository binary output and reuse, including symlink targets."""
    path = Path(path).resolve()
    if path.is_relative_to(REPO):
        raise ValueError("Binary output must be outside the repository")
    if path.exists():
        raise FileExistsError(path)
    return path


def make_plan(species):
    if not species:
        raise ValueError("Species list is empty")
    result = []
    names = set()
    for item in species:
        name = item["species"].strip()
        if not name or name in names:
            raise ValueError("Species names must be nonempty and unique")
        names.add(name)
        reference = item.get("reference", "")
        result.append({
            "species": name, "reference": reference,
            "prompt": (
                f"Botanical texture of {name}. One complete plant, front view, "
                "2048 x 2048 pixels (2K), white background, no shadows, "
                "no ground, no pot, no text, no cropping; neutral diffuse light. "
                "Preserve species identity, natural proportions and foliage detail."
                + (f" Match the supplied reference: {reference}" if reference else "")
            ),
        })
    return {"schema": 1, "status": "awaiting_image_generation", "species": result}


def cutout(image: Image.Image, threshold=245):
    """Return RGB diffuse and strictly binary L opacity, without alpha.

    Near-white pixels (all channels >= threshold) become transparent, including
    holes in foliage. Pale petals can be lost: human review is mandatory.
    """
    if not isinstance(threshold, int) or not 1 <= threshold <= 255:
        raise ValueError("Threshold must be an integer in 1..255")
    if image.mode != "RGB":
        raise ValueError("Expected RGB white-background input without alpha")
    rgb = np.asarray(image)
    mask = np.where(np.all(rgb >= threshold, axis=2), 0, 255).astype(np.uint8)
    if not np.any(mask) or np.all(mask):
        raise ValueError("Expected both plant and white background")
    diffuse = image.copy()
    # RGB PNGs may still carry tRNS color-key transparency. Keep all opacity
    # exclusively in the separate mask, including after PNG serialization.
    diffuse.info.pop("transparency", None)
    return diffuse, Image.fromarray(mask)


def upscale(source, output, authorization):
    """Explicit opt-in for the user-authorized Codex 1254 -> 2048 exception.

    This technical conversion adds no detail and does not approve a texture.
    Keep the original unchanged; bind the conversion receipt to both files.
    """
    if not isinstance(authorization, str) or not authorization.strip():
        raise ValueError("Explicit user authorization for upscaling is required")
    output = external_destination(output)
    source = Path(source)
    original = source.read_bytes()
    with Image.open(BytesIO(original)) as image:
        if image.mode != "RGB" or image.size != (1254, 1254):
            raise ValueError("Authorized exception requires RGB 1254x1254 input")
        result = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
        result.info.pop("transparency", None)
    buffer = BytesIO()
    result.save(buffer, format="PNG")
    record = {"source_size": [1254, 1254], "output_size": [SIZE, SIZE],
              "source_sha256": digest(original), "output_sha256": digest(buffer.getvalue()),
              "method": "Pillow LANCZOS", "authorization": str(authorization),
              "status": "upscaled_not_texture_approved"}
    output.mkdir(parents=True)
    (output / "source-2048.png").write_bytes(buffer.getvalue())
    write_json(output / "upscale.json", record)
    return record


def prepare(plan, incoming, output, threshold=245):
    """incoming maps species to image, model, generation_id, optional reference_image."""
    output = external_destination(output)
    entries = []
    images = []
    for i, item in enumerate(plan["species"]):
        source = incoming[item["species"]]
        if not source.get("model", "").strip() or not source.get("generation_id", "").strip():
            raise ValueError("Actual model and generation_id are required")
        with Image.open(source["image"]) as image:
            image.load()
            if image.size != (SIZE, SIZE):
                raise ValueError("Prepared image must be exactly 2048x2048; no silent upscale")
            diffuse, opacity = cutout(image, threshold)
        ref = None
        if source.get("reference_image"):
            with Image.open(source["reference_image"]) as original:
                ref = original.convert("RGB")
        entry = {**item, "model": source["model"],
                 "generation_id": source["generation_id"], "threshold": threshold,
                 "source_sha256": digest(Path(source["image"]).read_bytes()),
                 "diffuse": f"{i}_d.png", "opacity": f"{i}_o.png",
                 "reference_image": f"{i}_ref.png" if ref else None}
        if source.get("upscale_record"):
            record = read_json(source["upscale_record"])
            if record.get("output_sha256") != entry["source_sha256"]:
                raise ValueError("Upscale receipt does not match input image")
            entry["upscale"] = record
        entries.append(entry)
        images.append((diffuse, opacity, ref))
    if not entries or len({e["species"] for e in entries}) != len(entries):
        raise ValueError("Expected nonempty unique species")
    output.mkdir(parents=True)
    rows = []
    for entry, (diffuse, opacity, ref) in zip(entries, images):
        diffuse.save(output / entry["diffuse"])
        opacity.save(output / entry["opacity"])
        files = [entry["diffuse"], entry["opacity"]]
        if ref:
            ref.save(output / entry["reference_image"])
            files.append(entry["reference_image"])
        entry["files_sha256"] = {f: digest((output / f).read_bytes()) for f in files}
        entry["candidate_id"] = digest(canonical(entry))
        reference = escape(str(entry["reference"])) or "No reference supplied (test list)"
        reference_picture = (f'<img src="{entry["reference_image"]}" width="256">' if ref else "")
        provenance = escape(json.dumps(entry.get("upscale", {"method": "native 2048"}), ensure_ascii=False))
        rows.append(
            f'<tr><td>{escape(entry["species"])}<p>{reference}</p>{reference_picture}</td>'
            f'<td><img src="{entry["diffuse"]}" width="256"></td>'
            f'<td><img src="{entry["opacity"]}" width="256"></td>'
            f'<td><code>{entry["candidate_id"]}</code><pre>{escape(entry["prompt"])}</pre><pre>{provenance}</pre></td></tr>'
        )
    html = ('<!doctype html><meta charset="utf-8"><title>Flora review</title>'
            '<h1>Pending Artem review — NOT approved, NOT an atlas</h1>'
            '<p>Check species identity, silhouette, scale/proportions, pale foliage, halos and shadows.</p>'
            '<table><tr><th>Reference</th><th>2K result / diffuse</th><th>Opacity</th><th>Candidate / prompt</th></tr>'
            + "".join(rows) + '</table>')
    (output / "review.html").write_text(html, encoding="utf-8")
    manifest = {"schema": 1, "status": "pending_user_review", "entries": entries,
                "review_sha256": digest((output / "review.html").read_bytes())}
    write_json(output / "candidates.json", manifest)
    return manifest


def load_approved(review, approvals):
    """Validate the entire batch before publishing per-species library maps."""
    review = Path(review)
    manifest = read_json(review / "candidates.json")
    review_hash = digest((review / "review.html").read_bytes())
    if review_hash != manifest["review_sha256"]:
        raise ValueError("Review sheet changed")
    entries = manifest["entries"]
    if not entries or len({e["species"] for e in entries}) != len(entries):
        raise ValueError("Expected nonempty unique species")
    records = approvals.get("approvals", [])
    if len({a.get("candidate_id") for a in records}) != len(records):
        raise ValueError("Duplicate approval")
    approved = {a.get("candidate_id"): a for a in records}
    loaded = []
    for entry in entries:
        candidate = dict(entry)
        candidate_id = candidate.pop("candidate_id")
        if digest(canonical(candidate)) != candidate_id:
            raise ValueError("Candidate changed")
        approval = approved.get(candidate_id, {})
        if (approval.get("decision") != "approved" or approval.get("reviewed_by") != "Artem"
                or approval.get("review_sha256") != review_hash
                or not str(approval.get("evidence", "")).strip()):
            raise ValueError(f"Explicit Artem approval required: {entry['species']}")
        try:
            datetime.fromisoformat(approval["reviewed_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Approval requires an ISO reviewed_at timestamp") from exc
        required = {entry["diffuse"], entry["opacity"]}
        if entry["reference_image"]:
            required.add(entry["reference_image"])
        if set(entry["files_sha256"]) != required:
            raise ValueError("Incomplete candidate hashes")
        for filename, expected in entry["files_sha256"].items():
            path = (review / filename).resolve()
            if path.parent != review.resolve() or digest(path.read_bytes()) != expected:
                raise ValueError("Reviewed image changed or unsafe path")
        with Image.open(review / entry["diffuse"]) as d, Image.open(review / entry["opacity"]) as o:
            if (d.mode != "RGB" or o.mode != "L" or d.size != (SIZE, SIZE)
                    or o.size != d.size or not set(np.unique(np.asarray(o))).issubset({0, 255}) or not o.getbbox()):
                raise ValueError("Invalid diffuse/opacity pair")
            loaded.append((entry, d.copy(), o.copy()))
    return loaded


def publish_library(review, approvals, output):
    """Copy approved maps byte-for-byte; never make an atlas or overwrite assets."""
    output = Path(output).resolve()
    if output.is_relative_to(REPO):
        raise ValueError("Binary output must be outside the repository")
    loaded = load_approved(review, approvals)
    manifest_path = external_destination(output / "library-v001.json")
    payloads = []
    entries = []
    seen = set()
    for entry, _, _ in loaded:
        slug = re.sub(r"[^a-z0-9]+", "-", entry["species"].lower()).strip("-")
        if not slug or slug in seen:
            raise ValueError("Species must have unique nonempty library folder names")
        seen.add(slug)
        item = {"species": entry["species"], "candidate_id": entry["candidate_id"],
                "files_sha256": {}}
        for key in ("diffuse", "opacity"):
            relative = f"{slug}/{key}-v001.png"
            target = external_destination(output / relative)
            content = (Path(review) / entry[key]).read_bytes()
            if digest(content) != entry["files_sha256"][entry[key]]:
                raise ValueError("Reviewed image changed before publication")
            payloads.append((target, content))
            item[key] = relative
            item["files_sha256"][relative] = digest(content)
        entries.append(item)
    result = {"schema": 1, "status": "user_approved_species_maps_not_delivery_validated",
              "species": entries, "approvals": approvals}
    # Validate all destinations before the first write, including existing species folders.
    for target, content in payloads:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
    with manifest_path.open("xb") as stream:
        stream.write(canonical(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--species", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("upscale")
    p.add_argument("--source", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--authorization", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--plan", required=True)
    p.add_argument("--incoming", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--threshold", type=int, default=245)
    p = sub.add_parser("library")
    p.add_argument("--review", required=True)
    p.add_argument("--approvals", required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        out = Path(args.out)
        with out.open("xb") as stream:
            stream.write(canonical(make_plan(read_json(args.species))))
    elif args.command == "upscale":
        upscale(args.source, args.out, args.authorization)
    elif args.command == "prepare":
        prepare(read_json(args.plan), read_json(args.incoming), args.out, args.threshold)
    else:
        publish_library(args.review, read_json(args.approvals), args.out)


if __name__ == "__main__":
    main()
