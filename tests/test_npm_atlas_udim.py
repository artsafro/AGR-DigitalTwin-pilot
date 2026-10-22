"""Tests for the NPM atlas packer from a UDIM mesh (tools/materials/npm_atlas_udim.py, #546)."""

import hashlib
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "tools" / "materials" / "npm_atlas_udim.py"
    spec = importlib.util.spec_from_file_location("npm_atlas_udim", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve the module by name
    spec.loader.exec_module(mod)
    return mod


na = _load()


# ---------------------------------------------------------------- synthetic Multi/Sub fixture (SYNTHETIC data)
def _gradient(w, h, seed):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    img = np.stack([(x * 255 // max(w - 1, 1)), (y * 255 // max(h - 1, 1)),
                    ((x + y) * 127 // max(w + h - 2, 1)) + rng.integers(0, 2, (h, w))], -1)
    return img.astype(np.uint8)


def _grid(x0, y0, sx, sy, nx, ny, tile_u, uv_rect):
    """Plane grid on Z=0 with UVs mapped linearly into uv_rect (u0, v0, u1, v1) of UDIM column tile_u."""
    verts, uvs, faces = [], [], []
    u0, v0, u1, v1 = uv_rect
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append((x0 + sx * i / nx, y0 + sy * j / ny, 0.0))
            uvs.append((tile_u + u0 + (u1 - u0) * i / nx, v0 + (v1 - v0) * j / ny))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    return verts, uvs, faces


def write_fixture(d: Path, *, curb_map=None, extra=None):
    """3-material Multi/Sub ground (SYNTHETIC): Grass texture (1001), Paving RGBA texture (1002), Curb flat (1003)."""
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_gradient(1024, 1024, 1), "RGB").save(d / "T_Syn_Grass.1001.png")
    pav = np.dstack([_gradient(512, 512, 2), np.full((512, 512), 255, np.uint8)])
    pav[:, :128, 3] = 0  # left quarter transparent
    Image.fromarray(pav, "RGBA").save(d / "T_Syn_Paving.1002.png")
    parts = [("Grass", _grid(0, 0, 40, 30, 4, 3, 0, (0.1, 0.1, 0.9, 0.7))),
             ("Paving", _grid(40, 0, 20, 15, 4, 3, 1, (0.05, 0.05, 0.95, 0.72))),
             ("Curb", _grid(0, 30, 60, 0.5, 6, 1, 2, (0.1, 0.1, 0.9, 0.1 + 0.8 * 0.5 / 60)))]
    if extra:
        parts += extra
    lines, vo, to = ["mtllib syn.mtl", "o SYN_Ground"], 0, 0
    for name, (v, t, f) in parts:
        lines += [f"v {a} {b} {c}" for a, b, c in v] + [f"vt {a} {b}" for a, b in t] + [f"usemtl {name}"]
        lines += ["f " + " ".join(f"{vo + i + 1}/{to + i + 1}" for i in face) for face in f]
        vo, to = vo + len(v), to + len(t)
    (d / "syn.obj").write_text("\n".join(lines) + "\n", encoding="utf-8")
    mtl = ["newmtl Grass", "Kd 1 1 1", "map_Kd T_Syn_Grass.<UDIM>.png",
           "newmtl Paving", "Kd 1 1 1", "map_Kd T_Syn_Paving.<UDIM>.png",
           "newmtl Curb", "Kd 0.6 0.6 0.62"]
    if curb_map:
        mtl.append(f"map_Kd {curb_map}")
    for name, _ in extra or []:
        mtl += [f"newmtl {name}", "Kd 0.2 0.4 0.2"]
    (d / "syn.mtl").write_text("\n".join(mtl) + "\n", encoding="utf-8")
    return d / "syn.obj"


def _hashes(d: Path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}


def _bilinear(img, x, y):
    h, w = img.shape[:2]
    x, y = x - 0.5, y - 0.5
    x0, y0 = int(math.floor(x)) % w, int(math.floor(y)) % h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    fx, fy = x - math.floor(x), y - math.floor(y)
    top = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    bot = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return top * (1 - fy) + bot * fy


# ---------------------------------------------------------------- acceptance
@pytest.fixture()
def packed(tmp_path):
    src = write_fixture(tmp_path / "src")
    before = _hashes(src.parent)
    out = tmp_path / "out-v001"
    rc = na.main([str(src), "--out-dir", str(out), "--overlay", str(tmp_path / "overlay.png")])
    return src, out, before, rc


def test_synthetic_multisub_atlas_readback(packed):
    src, out, before, rc = packed
    assert rc == 0
    assert _hashes(src.parent) == before  # source mesh and maps unchanged
    rep = json.loads((out / "T_syn_NPM_report.json").read_text(encoding="utf-8"))
    assert rep["passed"] is True and rep["atlas_size"] == 2048 and rep["opacity_map"] is True
    assert set(rep["materials"]) == {"Grass", "Paving", "Curb"}
    with Image.open(out / "T_syn_NPM_d.png") as im:
        assert im.mode == "RGB" and im.size == (2048, 2048)
    with Image.open(out / "T_syn_NPM_o.png") as im:
        assert im.mode == "L" and im.size == (2048, 2048)
    mesh, _ = na.read_obj(src)
    back, mats = na.read_obj(out / "T_syn_NPM.obj")
    assert set(mats) == {"T_syn_NPM"} and set(back.face_materials) == {"T_syn_NPM"}
    assert back.faces == mesh.faces and np.array_equal(back.vertices, mesh.vertices)
    cells = {m: r["cell_px"] for m, r in rep["materials"].items()}
    probe = na.UdimMesh(back.vertices, back.uvs, back.faces, back.face_uvs, mesh.face_materials)
    meas = na.measure(probe, back.uvs, back.face_uvs, cells, 2048, mode="ground", pad_min=8)
    assert meas["passed"]
    for m, row in meas["materials"].items():
        assert row["uv_outside_cell"] == 0 and row["uv_outside_01"] == 0, m
        assert row["padding_px"] >= 8, m
        assert 10 <= row["texel_min"] <= row["texel_max"] <= 40, m
    assert meas["min_island_gap_px"] >= 16
    assert rep["materials"]["Curb"]["kind"] == "plug"
    assert abs(rep["materials"]["Curb"]["texel_min"] - 12.5) < 1e-6
    assert (Path(str(out)).parent / "overlay.png").is_file()


def test_atlas_pixels_follow_the_affine_uv(packed):
    """Sample source and atlas at the same face centroids: the remapped UV points to the same colour."""
    src, out, _, _ = packed
    mesh, _ = na.read_obj(src)
    back, _ = na.read_obj(out / "T_syn_NPM.obj")
    atlas = np.asarray(Image.open(out / "T_syn_NPM_d.png")).astype(float)
    opac = np.asarray(Image.open(out / "T_syn_NPM_o.png")).astype(float)
    maps = {"Grass": np.asarray(Image.open(src.parent / "T_Syn_Grass.1001.png").convert("RGBA")).astype(float),
            "Paving": np.asarray(Image.open(src.parent / "T_Syn_Paving.1002.png").convert("RGBA")).astype(float)}
    checked = 0
    for f, m in enumerate(mesh.face_materials):
        if m not in maps:
            assert np.allclose(_bilinear(atlas, *(back.uvs[list(back.face_uvs[f])].mean(0) * [2048, -2048]
                                                + [0, 2048])), [153, 153, 158], atol=1)
            continue
        img = maps[m]
        su, sv = mesh.uvs[list(mesh.face_uvs[f])].mean(0)
        tu = math.floor(su)
        sx, sy = (su - tu) * img.shape[1], (1 - sv) * img.shape[0]
        au, av = back.uvs[list(back.face_uvs[f])].mean(0)
        ax, ay = au * 2048, (1 - av) * 2048
        assert np.allclose(_bilinear(img, sx, sy)[:3], _bilinear(atlas, ax, ay), atol=6), (m, f)
        if m == "Paving":
            want = _bilinear(img, sx, sy)[3]
            assert abs(want - _bilinear(opac[..., None], ax, ay)[0]) <= 8, f
        checked += 1
    assert checked == 12 + 12


def test_texture_findings_pass_on_written_pngs(packed):
    from twinqa.png import npm_texture_findings

    _, out, _, _ = packed
    profile = yaml.safe_load((ROOT / "standards" / "NPM_STANDARD.yaml").read_text(encoding="utf-8"))
    images = {p.name: p.read_bytes() for p in out.glob("*.png")}
    found = npm_texture_findings(images, profile)
    assert [f.status if hasattr(f, "status") else f["status"] for f in found] == ["pass"], found


def test_1024_atlas_and_no_opacity_without_alpha(tmp_path):
    src = write_fixture(tmp_path / "src")
    # replace Paving by an opaque RGB map: no opacity map may be written
    Image.fromarray(_gradient(512, 512, 2), "RGB").save(src.parent / "T_Syn_Paving.1002.png")
    out = tmp_path / "o"
    assert na.main([str(src), "--out-dir", str(out), "--size", "1024"]) == 0
    assert not (out / "T_syn_NPM_o.png").exists()
    rep = json.loads((out / "T_syn_NPM_report.json").read_text(encoding="utf-8"))
    assert rep["atlas_size"] == 1024 and rep["passed"] and rep["opacity_map"] is False
    assert "map_d" not in (out / "T_syn_NPM.mtl").read_text(encoding="utf-8")


def test_plug_rule_one_colour_map_is_plug_small_pattern_is_texture(tmp_path):
    """Pilot rule: a one-colour map is a plug; a small PATTERNED map stays a texture (script: <= 512 px -> plug)."""
    d = tmp_path / "a"
    d.mkdir()
    Image.fromarray(np.full((256, 256, 3), 77, np.uint8)).save(d / "flat.png")
    rep = na.pack(*na.read_obj(write_fixture(d, curb_map="flat.png")))["report"]
    assert rep["materials"]["Curb"]["kind"] == "plug"
    d2 = tmp_path / "b"
    d2.mkdir()
    Image.fromarray(_gradient(256, 256, 5)).save(d2 / "small.png")
    rep2 = na.pack(*na.read_obj(write_fixture(d2, curb_map="small.png")))["report"]
    assert rep2["materials"]["Curb"]["kind"] == "texture"
    assert rep["materials"]["Paving"]["kind"] == "texture"  # 512 px patterned: texture, not a plug


def test_oks_mode_scale_at_most_one(tmp_path):
    rep = na.pack(*na.read_obj(write_fixture(tmp_path)), mode="oks")["report"]
    assert rep["passed"] and rep["used"] <= 1.0
    assert all(r["texel_in_band"] is None for r in rep["materials"].values())
    assert rep["materials"]["Grass"]["scale_k"] <= 1.0


# ---------------------------------------------------------------- fail-closed
def _err(argv):
    return na.main(argv)


def test_fbx_and_unsupported_input_refused(tmp_path, capsys):
    (tmp_path / "m.fbx").write_bytes(b"x")
    assert _err([str(tmp_path / "m.fbx"), "--out-dir", str(tmp_path / "o")]) == 2
    assert "FBX" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


@pytest.mark.parametrize("mutate,needle", [
    (lambda t: t.replace("usemtl Curb", "usemtl Missing"), "Missing"),
    (lambda t: t.replace("vt 0.1 0.1", "vt nan 0.1", 1), "non-finite"),
    (lambda t: "\n".join(ln for ln in t.splitlines() if not ln.startswith("f ")), "no faces"),
    (lambda t: t.replace("usemtl Grass", "l 1 2\nusemtl Grass"), "unsupported"),
])
def test_bad_obj_is_an_error_naming_it(tmp_path, capsys, mutate, needle):
    src = write_fixture(tmp_path / "s")
    src.write_text(mutate(src.read_text(encoding="utf-8")), encoding="utf-8")
    assert _err([str(src), "--out-dir", str(tmp_path / "o")]) == 2
    assert needle in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


def test_tile_crossing_and_shared_uv_refused(tmp_path):
    mesh, mats = na.read_obj(write_fixture(tmp_path))
    uvs = mesh.uvs.copy()
    uvs[0] = (1.05, 0.1)  # Grass vertex pulled into tile 1002
    with pytest.raises(na.AtlasError, match="Grass.*crosses"):
        na.pack(na.UdimMesh(mesh.vertices, uvs, mesh.faces, mesh.face_uvs, mesh.face_materials), mats)
    fuv = list(mesh.face_uvs)
    last = len(fuv) - 1  # a Curb face takes a Grass UV vertex
    fuv[last] = (0,) + fuv[last][1:]
    with pytest.raises(na.AtlasError, match="shared"):
        na.pack(na.UdimMesh(mesh.vertices, mesh.uvs, mesh.faces, tuple(fuv), mesh.face_materials), mats)


@pytest.mark.parametrize("kw,needle", [({"pad": 7}, "padding"), ({"size": 4096}, "atlas size"),
                                       ({"target": 41.0}, "target"), ({"target": float("nan")}, "target"),
                                       ({"unit_m": float("inf")}, "unit_m"), ({"mode": "vpm"}, "mode")])
def test_bad_parameters_refused(tmp_path, kw, needle):
    with pytest.raises(na.AtlasError, match=needle):
        na.pack(*na.read_obj(write_fixture(tmp_path)), **kw)


def test_texel_spread_that_cannot_fit_the_band_is_an_error(tmp_path):
    # Grass UV squeezed on one face row: 40x30 m with one strip 10x denser -> no uniform scale keeps 10..40
    mesh, mats = na.read_obj(write_fixture(tmp_path))
    uvs = mesh.uvs.copy()
    uvs[:5, 1] = 0.1
    uvs[5:10, 1] = 0.6  # first face row: 10 m tall -> 0.5 UV; others 0.1 / 2 rows
    uvs[10:15, 1] = 0.605
    uvs[15:20, 1] = 0.61
    with pytest.raises(na.AtlasError, match="Grass.*spread"):
        na.pack(na.UdimMesh(mesh.vertices, uvs, mesh.faces, mesh.face_uvs, mesh.face_materials), mats)


def test_does_not_fit_is_an_error(tmp_path):
    big = [("Field", _grid(0, -500, 500, 500, 2, 2, 3, (0.1, 0.1, 0.9, 0.9)))]
    d = tmp_path
    src = write_fixture(d, extra=big)
    mtl = (d / "syn.mtl").read_text(encoding="utf-8").replace("newmtl Field\nKd 0.2 0.4 0.2",
                                                              "newmtl Field\nmap_Kd field.png")
    (d / "syn.mtl").write_text(mtl, encoding="utf-8")
    Image.fromarray(_gradient(1024, 1024, 9)).save(d / "field.png")
    with pytest.raises(na.AtlasError, match="do not fit"):
        na.pack(*na.read_obj(src))


def test_output_aliasing_input_writes_nothing(tmp_path, capsys):
    src = write_fixture(tmp_path / "s")
    before = _hashes(src.parent)
    # base 'syn' in the source folder -> syn.obj / syn.mtl would overwrite the inputs
    assert _err([str(src), "--out-dir", str(src.parent), "--base", "syn"]) == 2
    assert "resolves to input" in capsys.readouterr().err
    assert _hashes(src.parent) == before
    # case-only / dotted alias of the same folder
    alias = str(src.parent / ".." / "s").upper() if Path(str(src.parent).upper()).exists() else str(src.parent)
    assert _err([str(src), "--out-dir", alias, "--base", "syn"]) == 2
    assert _hashes(src.parent) == before


def test_existing_output_refused_and_kept(tmp_path, capsys):
    src = write_fixture(tmp_path / "s")
    out = tmp_path / "o"
    assert na.main([str(src), "--out-dir", str(out)]) == 0
    snap = _hashes(out)
    assert na.main([str(src), "--out-dir", str(out)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert _hashes(out) == snap
    assert not list(out.glob("*.partial"))


def test_threshold_measure_inclusive_band_and_padding():
    """reg p.10 §6.1 '>= 10 and <= 40' and reg p.9 §5.4 '>= 8 px': exact bounds pass, just outside fails."""
    def one(density, pad_px):
        side = 1.0  # 1 m square face
        uv_side = density * side / 100.0  # atlas 100 px for the probe
        x0 = (pad_px) / 100.0
        verts = np.array([(0, 0, 0), (side, 0, 0), (side, side, 0), (0, side, 0)], float)
        uvs = np.array([(x0, 1 - x0 - uv_side), (x0 + uv_side, 1 - x0 - uv_side), (x0 + uv_side, 1 - x0),
                        (x0, 1 - x0)])
        mesh = na.UdimMesh(verts, uvs, ((0, 1, 2, 3),), ((0, 1, 2, 3),), ("M",))
        cell = [0, 0, int(round(2 * pad_px + density)), int(round(2 * pad_px + density))]
        return na.measure(mesh, uvs, mesh.face_uvs, {"M": cell}, 100, mode="ground", pad_min=8)["passed"]
    assert one(10.0, 8.0) and one(40.0, 8.0)
    assert not one(9.99, 8.0) and not one(40.01, 8.0) and not one(10.0, 7.99)


def test_measure_unmapped_material_and_empty_fail():
    mesh = na.UdimMesh(np.zeros((3, 3)), np.zeros((3, 2)), ((0, 1, 2),), ((0, 1, 2),), ("X",))
    with pytest.raises(na.AtlasError, match="'X'"):
        na.measure(mesh, mesh.uvs, mesh.face_uvs, {}, 2048, mode="ground", pad_min=8)
    empty = na.UdimMesh(np.zeros((0, 3)), np.zeros((0, 2)), (), (), ())
    assert na.measure(empty, empty.uvs, (), {}, 2048, mode="ground", pad_min=8)["passed"] is False
    with pytest.raises(na.AtlasError, match="no faces"):
        na.pack(empty, {})
    # zero-area (degenerate) face never passes the Ground band
    deg = na.UdimMesh(np.zeros((3, 3)), np.array([(0.5, 0.5)] * 3), ((0, 1, 2),), ((0, 1, 2),), ("X",))
    assert na.measure(deg, deg.uvs, deg.face_uvs, {"X": [0, 0, 2048, 2048]}, 2048, mode="ground",
                      pad_min=8)["passed"] is False


# ---------------------------------------------------------------- generated probe
def test_probe_random_layouts_keep_invariants(tmp_path):
    """Seeded random Multi/Sub grounds: every passing pack keeps padding >= 8, UV in cell, band 10..40,
    non-overlapping cells, every face mapped once; failures are AtlasError (never a silent pass)."""
    rng = random.Random(546)
    n_pass = n_err = 0
    textures = {}
    for size in (256, 512, 1024, 2048):
        p = tmp_path / f"t{size}.png"
        Image.fromarray(_gradient(size, size, size)).save(p)
        textures[size] = p
    for trial in range(40):
        verts, uvs, faces, fuv, fmat, mats = [], [], [], [], [], {}
        for m in range(rng.randint(1, 5)):
            name = f"M{m}"
            sx, sy = rng.uniform(0.3, 60), rng.uniform(0.3, 40)
            u0, v0 = rng.uniform(0, 0.4), rng.uniform(0, 0.4)
            u1, v1 = rng.uniform(u0 + 0.05, 1), rng.uniform(v0 + 0.05, 1)
            v, t, f = _grid(rng.uniform(-100, 100), rng.uniform(-100, 100), sx, sy, rng.randint(1, 4),
                            rng.randint(1, 4), m, (u0, v0, u1, v1))
            o, q = len(verts), len(uvs)
            verts += v
            uvs += t
            faces += [tuple(o + i for i in face) for face in f]
            fuv += [tuple(q + i for i in face) for face in f]
            fmat += [name] * len(f)
            if rng.random() < 0.3:
                mats[name] = na.MaterialSource(name, color=(rng.randrange(256), 0, 0))
            else:
                mats[name] = na.MaterialSource(name, diffuse=textures[rng.choice([256, 512, 1024, 2048])])
        mesh = na.UdimMesh(np.array(verts, float), np.array(uvs, float), tuple(faces), tuple(fuv), tuple(fmat))
        size = rng.choice([1024, 2048])
        try:
            res = na.pack(mesh, mats, size=size, pad=rng.choice([8, 10, 16]))
        except na.AtlasError:
            n_err += 1
            continue
        rep = res["report"]
        pad = rep["padding_px"]
        assert rep["passed"], trial
        assert len(res["face_uvs"]) == len(mesh.faces)
        assert sum(r["faces"] for r in rep["materials"].values()) == len(mesh.faces)
        cells = list(res["cells"].values())
        for i, (x, y, w, h) in enumerate(cells):
            assert x >= 0 and y >= 0 and x + w <= size and y + h <= size
            for (x2, y2, w2, h2) in cells[i + 1:]:
                assert x + w <= x2 or x2 + w2 <= x or y + h <= y2 or y2 + h2 <= y
        for row in rep["materials"].values():
            assert row["padding_px"] >= pad and 10 <= row["texel_min"] <= row["texel_max"] <= 40
        n_pass += 1
    print(f"probe seed 546: {n_pass} packed with invariants held, {n_err} AtlasError, of 40")
    assert n_pass >= 20 and n_pass + n_err == 40


# ---------------------------------------------------------------- hostile self-review witnesses
def test_overlay_aliasing_an_output_or_input_writes_nothing(tmp_path, capsys):
    src = write_fixture(tmp_path / "s")
    out = tmp_path / "o"
    for overlay in (out / "T_syn_NPM_d.png", src.parent / "T_Syn_Grass.1001.png", src):
        before = _hashes(src.parent)
        assert na.main([str(src), "--out-dir", str(out), "--overlay", str(overlay)]) == 2
        assert "resolves to input or output" in capsys.readouterr().err
        assert not out.exists() and _hashes(src.parent) == before


def test_duplicate_material_definition_refused(tmp_path):
    src = write_fixture(tmp_path)
    mtl = tmp_path / "syn.mtl"
    mtl.write_text(mtl.read_text(encoding="utf-8") + "newmtl Grass\nKd 0 0 0\n", encoding="utf-8")
    with pytest.raises(na.AtlasError, match="'Grass' defined twice"):
        na.read_obj(src)


def test_separate_map_d_opacity_and_conflicting_alpha(tmp_path):
    src = write_fixture(tmp_path)
    op = np.full((1024, 1024), 255, np.uint8)
    op[:, :100] = 0
    Image.fromarray(op, "L").save(tmp_path / "grass_o.png")
    mtl = tmp_path / "syn.mtl"
    text = mtl.read_text(encoding="utf-8")
    mtl.write_text(text.replace("map_Kd T_Syn_Grass.<UDIM>.png", "map_Kd T_Syn_Grass.<UDIM>.png\nmap_d grass_o.png"),
                   encoding="utf-8")
    rep = na.pack(*na.read_obj(src))["report"]
    assert rep["materials"]["Grass"]["opacity"] == "map" and rep["opacity_map"]
    mtl.write_text(text.replace("map_Kd T_Syn_Paving.<UDIM>.png", "map_Kd T_Syn_Paving.<UDIM>.png\nmap_d grass_o.png"),
                   encoding="utf-8")
    with pytest.raises(na.AtlasError, match="Paving.*both diffuse alpha and map_d"):
        na.pack(*na.read_obj(src))


def test_fresh_process_cli(tmp_path):
    import subprocess

    src = write_fixture(tmp_path / "s")
    out = tmp_path / "o"
    tool = ROOT / "tools" / "materials" / "npm_atlas_udim.py"
    ok = subprocess.run([sys.executable, str(tool), str(src), "--out-dir", str(out)], capture_output=True, text=True)
    assert ok.returncode == 0 and ok.stdout.startswith("ok:"), ok.stderr
    again = subprocess.run([sys.executable, str(tool), str(src), "--out-dir", str(out)], capture_output=True, text=True)
    assert again.returncode == 2 and "already exists" in again.stderr
