"""V012 internal mesh-name grammar on the FBX readback (#163; UCX R08, MAF-11).

Rule sources: VPM objects and collision reg p.33-34 §4.2, NPM objects reg p.11-12 §3.3,
name length and characters reg p.11 §10.1-10.2. Readbacks below are synthetic.
"""
import random
import string
import subprocess
from pathlib import Path

import pytest

import validate_package as vp
from test_scene import mesh, statuses
from test_validator import PROFILES
from twinqa.naming import address_from_fbx, mesh_name_violation
from twinqa.scene import find_blender, scene_findings


def rb_from(source, *names):
    return {"source": f"C:/x/{source}", "readback_ok": True, "meshes": [mesh(name=n) for n in names],
            "other_objects": [], "images": []}


def v012(source, kind, role, *names):
    found = scene_findings(rb_from(source, *names), kind, role, PROFILES.profile(kind))
    return found.get("V012", [])


def v012_status(source, kind, role, *names):
    return {f.name: f.status for f in v012(source, kind, role, *names)}


VPM_OKS = ("SM_Test_K_1.fbx", "vpm", "oks")
VPM_GROUND = ("SM_Test_K_1_Ground.fbx", "vpm", "ground")
NPM_GROUND = ("0000_Test_K_1_Ground.fbx", "npm", "ground")
NPM_OKS = ("0000_Test_K_1_01.fbx", "npm", "oks")


# --- GREEN fixtures: clean names -> no failing finding ---------------------------------------

def test_vpm_oks_clean_names_pass():
    got = v012_status(*VPM_OKS, "SM_Test_K_1_Main", "SM_Test_K_1_MainGlass",
                      "UCX_SM_Test_K_1_Main_001", "UCX_SM_Test_K_1_Main_010", "UCX_SM_Test_K_1_Main_999")
    assert got == {"mesh names": "pass", "UCX names": "pass"}


def test_vpm_ground_clean_names_pass():
    got = v012_status(*VPM_GROUND, "SM_Test_K_1_Ground", "SM_Test_K_1_GroundGlass", "UCX_SM_Test_K_1_Ground_001")
    assert got == {"mesh names": "pass", "UCX names": "pass"}


def test_npm_ground_clean_groundel_names_pass():
    got = v012_status(*NPM_GROUND, "SM_Test_K_1_Ground", "SM_Test_K_1_GroundGlass", "SM_Test_K_1_GroundEl",
                      "SM_Test_K_1_GroundElGlass", "SM_Test_K_1_Flora")
    assert got == {"mesh names": "pass"}


def test_npm_oks_clean_names_pass():
    got = v012_status(*NPM_OKS, "SM_Test_K_1_001_Main", "SM_Test_K_1_001_MainGlass", "SM_Test_K_1_020_Main")
    assert got == {"mesh names": "pass"}


def test_vpm_without_ucx_has_no_ucx_name_finding():
    # UCX presence is R05 (another card); the name check reports only on UCX meshes that exist.
    assert v012_status(*VPM_OKS, "SM_Test_K_1_Main") == {"mesh names": "pass"}


# --- RED fixtures: defect -> finding ---------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "UCX_SM_Test_K_1_Main_000",        # index below 001
    "UCX_SM_Test_K_1_Main_1000",       # index above 999
    "UCX_SM_Test_K_1_Main_01",         # two digits
    "UCX_SM_Test_K_1_Main_1",          # one digit
    "UCX_SM_Test_K_1_Main",            # no index
    "UCX_SM_Test_K_1_Ground_001",      # Ground collision in the OKS FBX
    "UCX_SM_Other_K_1_Main_001",       # foreign address
    "ucx_SM_Test_K_1_Main_001",        # prefix case
    "UCX_SM_Test_K_1_main_001",        # suffix case
    "UCX_Test_K_1_Main_001",           # SM_ missing
    "UCX_SM_Test_K_1_Main_001.001",    # Blender duplicate suffix
    "UCX_SM_Test_K_1_MainGlass_001",   # glass is not a collision target
])
def test_vpm_oks_bad_ucx_name_fails(bad):
    found = v012(*VPM_OKS, "SM_Test_K_1_Main", "UCX_SM_Test_K_1_Main_001", bad)
    ucx = next(f for f in found if f.name == "UCX names")
    assert ucx.status == "fail" and bad in ucx.observed
    assert next(f for f in found if f.name == "mesh names").status == "pass"
    assert ucx.source_pdf_pages == [34]


@pytest.mark.parametrize("bad", ["UCX_SM_Test_K_1_Main_001", "UCX_SM_Test_K_1_Ground_000", "UCX_SM_Test_K_1_Ground_1000"])
def test_vpm_ground_bad_ucx_name_fails(bad):
    assert v012_status(*VPM_GROUND, "SM_Test_K_1_Ground", bad)["UCX names"] == "fail"


@pytest.mark.parametrize("bad", [
    "SM_Test_K_1_Groundel",            # suffix case
    "SM_Test_K_1_GroundEl_1",          # extra affix
    "SM_Test_K_1_GroundEl.001",        # dot (Blender duplicate)
    "SM_Тест_K_1_GroundEl",            # Cyrillic
    "SM_Test-K_1_GroundEl",            # hyphen
    "SM_Test K_1_GroundEl",            # space
    "SM_Test_K_2_GroundEl",            # foreign address
    "Test_K_1_GroundEl",               # SM_ missing
    "SM_Test_K_1_Main",                # OKS suffix in the Ground FBX
    "UCX_SM_Test_K_1_GroundEl",        # GroundEl with a collision prefix but not UCX grammar either
])
def test_npm_ground_bad_groundel_name_fails(bad):
    found = v012(*NPM_GROUND, "SM_Test_K_1_Ground", "SM_Test_K_1_GroundEl", bad)
    names = next(f for f in found if f.name in ("mesh names", "UCX names") and bad in f.observed)
    assert names.status in ("fail", "review")
    if not bad.upper().startswith("UCX_"):
        assert names.name == "mesh names" and names.status == "fail"
        assert names.source_pdf_pages == [11, 12]


def test_vpm_ground_rejects_npm_groundel_suffix():
    # GroundEl is an NPM suffix; VPM Ground keeps only Ground / GroundGlass (reg p.33 §4.2).
    assert v012_status(*VPM_GROUND, "SM_Test_K_1_Ground", "SM_Test_K_1_GroundEl")["mesh names"] == "fail"


@pytest.mark.parametrize("bad", ["SM_Test_K_1_000_Main", "SM_Test_K_1_021_Main", "SM_Test_K_1_Main", "SM_Test_K_1_1_Main"])
def test_npm_oks_bad_number_fails(bad):
    assert v012_status(*NPM_OKS, "SM_Test_K_1_001_Main", bad)["mesh names"] == "fail"


def test_duplicate_mesh_name_fails():
    assert v012_status(*VPM_OKS, "SM_Test_K_1_Main", "SM_Test_K_1_Main")["mesh names"] == "fail"


# --- length and character rules --------------------------------------------------------------

def _npm_ground_with_name_length(n):
    address = "A" * (n - len("SM__GroundEl"))
    return v012(f"0000_{address}_Ground.fbx", "npm", "ground", f"SM_{address}_GroundEl")


def test_length_254_passes_and_255_fails():
    ok, = _npm_ground_with_name_length(254)
    assert ok.status == "pass"
    bad, = _npm_ground_with_name_length(255)
    assert bad.status == "fail" and "254" in bad.observed


def test_length_limit_comes_from_profile():
    assert PROFILES.npm["naming"]["max_characters"] == 254 == PROFILES.vpm["naming"]["max_characters"]


def test_ucx_name_over_254_fails_even_with_valid_index():
    address = "A" * (255 - len("UCX_SM__Main_001"))
    got = v012_status(f"SM_{address}.fbx", "vpm", "oks", f"SM_{address}_Main", f"UCX_SM_{address}_Main_001")
    assert got["UCX names"] == "fail"


# --- unknown data is never pass --------------------------------------------------------------

def test_address_not_derivable_gives_review_not_pass():
    got = v012_status("model.fbx", "vpm", "oks", "SM_Test_K_1_Main", "UCX_SM_Test_K_1_Main_001")
    assert got == {"mesh names": "review", "UCX names": "review"}


def test_address_not_derivable_still_fails_structural_defects():
    got = v012_status("model.fbx", "vpm", "oks", "SM_Test_K_1_Main", "UCX_SM_Test_K_1_Main_1000")
    assert got["UCX names"] == "fail"


def test_npm_ucx_is_review_not_regulated():
    got = v012_status(*NPM_GROUND, "SM_Test_K_1_Ground", "UCX_SM_Test_K_1_Ground_001")
    assert got == {"mesh names": "pass", "UCX names": "review"}


def test_light_fbx_and_failed_readback_have_no_name_findings():
    assert v012("SM_Test_K_1_Light.fbx", "vpm", "light", "Lamp") == []
    found = scene_findings({"source": "C:/x/SM_Test_K_1.fbx", "readback_ok": False}, "vpm", "oks", PROFILES.vpm)
    assert found.get("V012", []) == []


@pytest.mark.parametrize("kind, stem, role, address", [
    ("vpm", "SM_Test_K_1", "oks", "Test_K_1"),
    ("vpm", "SM_Test_K_1_Ground", "ground", "Test_K_1"),
    ("npm", "0313_ProezdNansena_ZU_8_Ground", "ground", "ProezdNansena_ZU_8"),
    ("npm", "0313_ProezdNansena_ZU_8_01", "oks", "ProezdNansena_ZU_8"),
    ("npm", "0313_ProezdNansena_ZU_8_21", "oks", None),
    ("npm", "313_X_Ground", "ground", None),
    ("vpm", "Test_K_1", "oks", None),
    ("vpm", "SM_", "oks", None),
    ("vpm", "SM_Test-K", "oks", None),
])
def test_address_from_fbx(kind, stem, role, address):
    assert address_from_fbx(kind, role, stem) == address


# --- generated probe against an independent oracle -------------------------------------------

def _oracle(name, kind, role, address, limit=254):
    """Independent grammar: string splitting, no regular expressions."""
    if len(name) > limit or not name or any(c not in string.ascii_letters + string.digits + "_" for c in name):
        return False
    if name.startswith("UCX_"):
        if kind != "vpm":
            return False
        target = "Main" if role == "oks" else "Ground"
        head = f"UCX_SM_{address}_{target}_"
        index = name[len(head):]
        return name.startswith(head) and len(index) == 3 and index.isdigit() and 1 <= int(index) <= 999
    if kind == "vpm":
        suffixes = ("Main", "MainGlass") if role == "oks" else ("Ground", "GroundGlass")
        return name in {f"SM_{address}_{s}" for s in suffixes}
    if role == "ground":
        return name in {f"SM_{address}_{s}" for s in ("Ground", "GroundGlass", "GroundEl", "GroundElGlass", "Flora")}
    return name in {f"SM_{address}_{n:03d}_{s}" for n in range(1, 21) for s in ("Main", "MainGlass")}


ALPHABET = string.printable[:95] + "АяЁ._-"


def _mutants(seed_names, rng, count):
    for _ in range(count):
        name = list(rng.choice(seed_names))
        for _ in range(rng.randint(1, 3)):
            op, pos = rng.choice("sid"), rng.randrange(len(name) + 1)
            if op == "s" and pos < len(name):
                name[pos] = rng.choice(ALPHABET)
            elif op == "i":
                name.insert(pos, rng.choice(ALPHABET))
            elif op == "d" and pos < len(name):
                del name[pos]
        yield "".join(name)


CASES = [("vpm", "oks", ["SM_Ab_1_Main", "SM_Ab_1_MainGlass", "UCX_SM_Ab_1_Main_001", "UCX_SM_Ab_1_Main_999"]),
         ("vpm", "ground", ["SM_Ab_1_Ground", "SM_Ab_1_GroundGlass", "UCX_SM_Ab_1_Ground_042"]),
         ("npm", "ground", ["SM_Ab_1_GroundEl", "SM_Ab_1_GroundElGlass", "SM_Ab_1_Flora", "SM_Ab_1_Ground"]),
         ("npm", "oks", ["SM_Ab_1_001_Main", "SM_Ab_1_020_MainGlass"])]


@pytest.mark.parametrize("kind, role, seeds", CASES, ids=[f"{k}-{r}" for k, r, _ in CASES])
def test_generated_grammar_probe_matches_oracle(kind, role, seeds):
    rng = random.Random(163)
    names = list(_mutants(seeds, rng, 4000)) + seeds
    names += [f"UCX_SM_Ab_1_{t}_{i:0{w}d}" for t in ("Main", "Ground") for i in range(0, 1101) for w in (1, 2, 3, 4)]
    names += [f"SM_Ab_1_{i:0{w}d}_{s}" for s in ("Main", "MainGlass") for i in range(0, 30) for w in (1, 2, 3)]
    disagreements = [n for n in names if (mesh_name_violation(n, kind, role, "Ab_1", 254) is None)
                     != _oracle(n, kind, role, "Ab_1")]
    assert not disagreements, disagreements[:10]
    assert len(names) > 8000


# --- real FBX readback through the validator (Blender) ---------------------------------------

BLENDER = find_blender()
MAKE_SCENE = """
import bpy, sys
out, ucx = sys.argv[sys.argv.index('--') + 1], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
for name, z in (('SM_Test_K_1_Main', 1), (ucx, 1)):
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, z))
    bpy.context.object.name = name
    bpy.ops.object.modifier_add(type='TRIANGULATE'); bpy.ops.object.modifier_apply(modifier='Triangulate')
bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("ucx, status", [("UCX_SM_Test_K_1_Main_001", "pass"), ("UCX_SM_Test_K_1_Main_1000", "fail")])
def test_blender_fbx_readback_ucx_name(tmp_path, ucx, status):
    fbx_path = tmp_path / "SM_Test_K_1.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_SCENE, "--", str(fbx_path), ucx], check=True, capture_output=True, timeout=300)
    report = vp.validate(Path(fbx_path), "vpm", PROFILES, scene=True)
    st = {s.id: s for s in report.stages}
    names = {f.name: f for f in st["V012"].findings}
    assert names["mesh names"].status == "pass"
    assert names["UCX names"].status == status
    if status == "fail":
        assert ucx in names["UCX names"].observed and st["V012"].status == "fail"
