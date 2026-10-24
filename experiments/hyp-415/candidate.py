"""Experiment-local copy of ``twinqa.png``: per-file Pillow decode-error isolation.

Change versus production (``src/twinqa/png.py``): the two wrappers catch only the
``OSError`` raised by the existing ``pixels()`` decode calls (Pillow
``UnidentifiedImageError`` and truncated/broken-stream ``OSError`` are included by
inheritance), emit one ``fail / PNG readable`` per failed file, and (VPM) exclude that
file from the returned map ``sets`` before continuing with the next member.

No eager decoding of header-only paths, no blanket catch, no structural scanner, no
image repair, no resource policy. Successful-return behaviour is unchanged: for every
input where ``pixels()`` succeeds, the produced findings and sets are identical to
production, because the only added code is the ``try/except OSError`` around the decode
step and the set-pop on failure.
"""
from twinqa.bundle import size_status
from twinqa.png import (
    NPM_PLACEHOLDER_PX,
    VPM_NAME,
    _f,
    normal_convention,
    pixels,
    png_facts,
)


def vpm_texture_findings(pngs, profile, prefix):
    tex = profile["textures"]
    sizes = tex["allowed_square_sizes_px"]
    placeholder = tex["flat_placeholder"]["size_px"]
    out, sets = [], {}
    for name, data in sorted(pngs.items()):
        m = VPM_NAME.match(name)
        if not m:
            out.append(_f("fail", "texture name", name,
                          "T_{Address}_{Diffuse|ERM|Normal}_{Slot}.{UDIM}.png", [34, 35], name))
            continue
        if prefix and not name.startswith(prefix + "_"):
            out.append(_f("fail", "texture address", name, f"{prefix}_...", [33, 34], name))
        try:
            facts = png_facts(name, data)
        except ValueError as exc:
            out.append(_f("fail", "PNG readable", f"{name}: {exc}", "valid PNG", [30], name))
            continue
        kind, udim = m["map"], int(m["udim"])
        key = (int(m["slot"]), udim)
        sets.setdefault(key, {})[kind] = facts
        if facts.bit_depth != 8 or facts.color_type not in (2, 6):
            out.append(_f("fail", "8-bit RGB/RGBA",
                          f"{name}: bit depth {facts.bit_depth}, colour type {facts.color_type}",
                          "8 bit per channel, RGB or RGBA", [30], name))
        if facts.width != facts.height or facts.width not in sizes + [placeholder]:
            out.append(_f("fail", "map size", f"{name}: {facts.width}x{facts.height}",
                          f"square {sizes} or {placeholder} placeholder", [30, 31], name))
        if kind in ("ERM", "Normal") and facts.has_alpha:
            out.append(_f("fail", "no alpha in ERM/Normal", f"{name}: alpha present",
                          "RGB without alpha", [30], name))
        try:
            if facts.width == placeholder:
                px = pixels(data)
                if facts.has_alpha or (px != px[0, 0]).any():
                    out.append(_f("fail", "flat placeholder",
                                  f"{name}: alpha or more than one colour",
                                  "256x256, one colour, no alpha", [22, 31], name, [5]))
            elif kind == "ERM":
                px = pixels(data)
                lit = float((px[..., 0] > 0).mean())
                if lit >= 0.95:
                    out.append(_f("review", "ERM channel order",
                                  f"{name}: R (emissive) non-zero on {lit:.0%} of pixels",
                                  "R=Emissive (black where nothing glows), G=Roughness, B=Metallic",
                                  [23, 37], name))
            elif kind == "Normal":
                convention, corr = normal_convention(pixels(data))
                if convention == "opengl":
                    out.append(_f("fail", "DirectX normal",
                                  f"{name}: green channel is OpenGL (+Y), curl correlation {corr:.2f}",
                                  "DirectX (Y +1..-1 -> G 0..255)", [23, 30], name, [6]))
                elif convention == "undecided":
                    out.append(_f("review", "DirectX normal",
                                  f"{name}: convention undecidable, correlation {corr:.2f}",
                                  "DirectX", [23, 30], name, [6]))
        except OSError as exc:
            maps = sets.get(key)
            if maps is not None:
                maps.pop(kind, None)
                if not maps:
                    del sets[key]
            out.append(_f("fail", "PNG readable", f"{name}: {exc}", "valid PNG", [30], name))
    for (slot, udim), maps in sorted(sets.items()):
        missing = sorted({"Diffuse", "ERM", "Normal"} - set(maps))
        if missing:
            out.append(_f("fail", "map set", f"slot {slot} UDIM {udim}: missing {missing}",
                          "Diffuse + ERM + Normal for every used UDIM", [30], f"slot {slot}"))
        d = maps.get("Diffuse")
        for other in ("ERM", "Normal"):
            o = maps.get(other)
            if d and o and d.width < o.width:
                status = "review" if d.width == placeholder else "fail"
                out.append(_f(status, "Diffuse >= ERM/Normal",
                              f"slot {slot} UDIM {udim}: Diffuse {d.width} < {other} {o.width}",
                              "Diffuse resolution >= ERM and Normal", [30], d.name))
    if not out:
        out.append(_f("pass", "VPM maps",
                      f"{len(pngs)} PNG: names, 8-bit, sizes, alpha rules, sets, ERM order, DirectX green",
                      "reg p.30-31", [23, 30, 31], "ZIP root"))
    return out, sets


def npm_texture_findings(images, profile):
    tex = profile["textures"]
    out = []
    for name, data in sorted(images.items()):
        try:
            facts = png_facts(name, data)
        except ValueError as exc:
            out.append(_f("fail", "PNG readable", f"{name}: {exc}", "PNG atlas", [9], name))
            continue
        if facts.width == facts.height == NPM_PLACEHOLDER_PX:
            try:
                px = pixels(data)
            except OSError as exc:
                out.append(_f("fail", "PNG readable", f"{name}: {exc}", "PNG atlas", [9], name))
                continue
            if facts.has_alpha or (px != px[0, 0]).any():
                out.append(_f("fail", "flat placeholder", f"{name}: alpha or more than one colour",
                              "128x128, one colour, no alpha", [3, 4], name))
        elif facts.width != facts.height or facts.width not in tex["allowed_square_sizes_px"]:
            out.append(_f("fail", "atlas size", f"{name}: {facts.width}x{facts.height}",
                          f"square {tex['allowed_square_sizes_px']} or {NPM_PLACEHOLDER_PX} placeholder",
                          [9], name))
        status, observed = size_status(facts.size_bytes, tex["max_file_bytes"])
        if status != "pass":
            out.append(_f(status, "atlas file size", f"{name}: {observed}", "<= 3 MiB", [9], name))
        if facts.has_alpha:
            out.append(_f("fail", "no alpha", f"{name}: alpha channel present",
                          "RGB only; opacity as a separate _o_ map", [9], name))
        if facts.bit_depth != 8:
            out.append(_f("fail", "8-bit", f"{name}: bit depth {facts.bit_depth}",
                          "8 bit per channel", [3, 9], name))
    if images and not out:
        out.append(_f("pass", "NPM atlases", f"{len(images)} images: sizes, <= 3 MB, no alpha, 8-bit",
                      "reg p.9", [9], "embedded"))
    return out


import twinqa.png as _png  # noqa: E402

_BASE_NPM = _png.npm_texture_findings
_BASE_VPM = _png.vpm_texture_findings


def install(mode):
    """Patch ``twinqa.png`` and (if imported) ``validate_package`` with arm A or B."""
    if mode not in ("A", "B"):
        raise ValueError(f"Unknown implementation: {mode}")
    npm = {"A": _BASE_NPM, "B": npm_texture_findings}[mode]
    vpm = {"A": _BASE_VPM, "B": vpm_texture_findings}[mode]
    _png.npm_texture_findings = npm
    _png.vpm_texture_findings = vpm
    import sys
    vp = sys.modules.get("validate_package")
    if vp is not None:
        vp.npm_texture_findings = npm
        vp.vpm_texture_findings = vpm
