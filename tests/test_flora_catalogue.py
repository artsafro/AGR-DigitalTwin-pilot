"""Flora library catalogue: source selection, stable material IDs, and schema check.

The random probe builds synthetic species, meshes and catalogues. Those records are
not a real planting schedule, library scene or approved texture.
"""
import json
import random
from copy import deepcopy
from pathlib import Path

import pytest

from dt_ai.materials import flora_catalogue as fc

ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _audit_index() -> dict[str, dict]:
    indexed = {}
    for scene in _load("experiments/flora-library-audit/catalogue.json")["scenes"]:
        scene_name = scene["source"]["scene"]
        for entry in scene["entries"]:
            item = dict(entry)
            item["scene"] = scene_name
            indexed[item["id"]] = item
    return indexed


def _sources(latin: str) -> list[dict]:
    curation = _load("library/flora/species-curation.json")
    species = next(item for item in curation["species"] if item["latin"] == latin)
    indexed = _audit_index()
    return [indexed[source] for source in species["sources"]]


@pytest.mark.parametrize(
    ("latin", "profile", "expected"),
    [
        ("Syringa vulgaris 'Andenken an Ludwig Späth'", "NPM", "Syringa_vulgaris_Andenken_an_Ludwig_Spath_NPM"),
        ("Spiraea × cinerea 'Grefsheim'", "VPM", "Spiraea_cinerea_Grefsheim_VPM"),
        ("Acer tataricum subsp. ginnala", "NPM", "Acer_tataricum_subsp_ginnala_NPM"),
    ],
)
def test_object_name(latin, profile, expected):
    assert fc.object_name(latin, profile) == expected


@pytest.mark.parametrize(
    ("latin", "expected"),
    [
        ("Syringa vulgaris 'Andenken an Ludwig Späth'", "syringa-vulgaris-andenken-an-ludwig-spath"),
        ("Spiraea × cinerea 'Grefsheim'", "spiraea-cinerea-grefsheim"),
        ("Acer tataricum subsp. ginnala", "acer-tataricum-subsp-ginnala"),
    ],
)
def test_slug(latin, expected):
    assert fc.slug(latin) == expected


def test_select_sources_on_the_real_audit():
    ginnala = fc.select_sources(_sources("Acer tataricum subsp. ginnala"))
    assert ginnala["NPM"]["entry_id"] == "library-031"
    assert ginnala["NPM"]["basis"] == "LP"
    assert ginnala["NPM"]["triangles"] == 8
    assert ginnala["VPM"]["entry_id"] == "library-024"

    pinus = fc.select_sources(_sources("Pinus nigra"))
    assert pinus["NPM"]["entry_id"] == "library-084"
    assert pinus["VPM"]["entry_id"] == "library-064"

    tilia = fc.select_sources(_sources("Tilia cordata"))
    assert tilia["NPM"]["entry_id"] == "library-028"
    assert tilia["VPM"]["entry_id"] == "library-001"
    assert any(item["entry_id"] == "library-002" for item in tilia["merged"])

    betula = fc.select_sources(_sources("Betula pendula"))
    assert betula["NPM"]["entry_id"] == "library-006"
    assert betula["VPM"]["entry_id"] == "library-006"
    assert betula["VPM"]["basis"] == "LP -> HP (same mesh as NPM)"


def _build_real(previous=None):
    return fc.build(
        _load("experiments/flora-library-audit/catalogue.json"),
        _load("library/flora/species-curation.json"),
        _load("library/flora/maps.json"),
        previous,
    )


def test_assign_ids_follow_curation_order_inside_ranges():
    catalogue = _build_real()
    trees = [item for item in catalogue["species"] if item["type"] == "tree"]
    bushes = [item for item in catalogue["species"] if item["type"] == "bush"]
    flowers = [item for item in catalogue["species"] if item["type"] == "flower"]
    assert trees[0]["latin"] == "Tilia cordata"
    assert bushes[0]["latin"] == "Berberis × ottawensis"
    assert flowers[0]["latin"] == "Symphyotrichum novae-angliae"
    assert [item["material_id"] for item in trees] == list(range(101, 101 + len(trees)))
    assert [item["material_id"] for item in bushes] == list(range(201, 201 + len(bushes)))
    assert [item["material_id"] for item in flowers] == list(range(401, 401 + len(flowers)))


def test_assign_ids_keeps_old_ids_and_retires_removed_ones():
    """The inserted tree is synthetic and is not a real library species."""
    original = _build_real()
    curation = _load("library/flora/species-curation.json")
    removed = curation["species"].pop(0)
    assert removed["latin"] == "Tilia cordata"
    inserted = {
        "latin": "Syntheticus stabilis",
        "russian": "synthetic",
        "type": "tree",
        "sources": list(removed["sources"]),
        "geometry_basis": "own_mesh",
        "note": "synthetic insertion for material-id stability",
    }
    curation["species"].insert(0, inserted)
    rebuilt = fc.build(
        _load("experiments/flora-library-audit/catalogue.json"),
        curation,
        _load("library/flora/maps.json"),
        original,
    )
    old_ids = {item["latin"]: item["material_id"] for item in original["species"]}
    new_ids = {item["latin"]: item["material_id"] for item in rebuilt["species"]}
    assert removed["latin"] not in new_ids
    for latin, material_id in old_ids.items():
        if latin == removed["latin"]:
            continue
        assert new_ids[latin] == material_id
    assert old_ids[removed["latin"]] in rebuilt["retired_ids"]
    assert new_ids[inserted["latin"]] != old_ids[removed["latin"]]
    assert new_ids[inserted["latin"]] == 128
    assert fc.check(rebuilt) == []


def test_assign_ids_full_range_and_previous_id_outside_range():
    """Synthetic species fill a range; they are not real Flora."""
    species = [{"latin": f"Synthetic tree {index}", "type": "tree"} for index in range(99)]
    assigned = fc.assign_ids(species)
    assert set(assigned["by_latin"].values()) == set(range(101, 200))
    species.append({"latin": "Synthetic tree overflow", "type": "tree"})
    with pytest.raises(ValueError, match="full"):
        fc.assign_ids(species)
    previous = {
        "retired_ids": [],
        "species": [{"latin": "Synthetic tree 0", "type": "tree", "material_id": 50}],
    }
    with pytest.raises(ValueError, match="outside"):
        fc.assign_ids([{"latin": "Synthetic tree 0", "type": "tree"}], previous)


def test_committed_catalogue_has_no_findings_and_matches_rebuild():
    catalogue = _load("library/flora/catalogue.json")
    assert fc.check(catalogue) == []
    assert _build_real(previous=catalogue) == catalogue


def _text(findings: list[str]) -> str:
    return "\n".join(findings)


def test_check_reports_duplicate_id():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["species"][1]["material_id"] = catalogue["species"][0]["material_id"]
    findings = fc.check(catalogue)
    assert "duplicate material_id" in _text(findings)


def test_check_reports_id_in_1_100():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["species"][0]["material_id"] = 50
    assert "1-100" in _text(fc.check(catalogue))


def test_check_reports_tree_id_outside_its_range():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["species"][0]["material_id"] = 205
    assert "outside" in _text(fc.check(catalogue))


def test_check_reports_bush_id_outside_its_range():
    catalogue = _load("library/flora/catalogue.json")
    bush = next(item for item in catalogue["species"] if item["type"] == "bush")
    bush["material_id"] = 150
    assert "outside" in _text(fc.check(catalogue))


def test_check_reports_flower_id_outside_its_range():
    catalogue = _load("library/flora/catalogue.json")
    flower = next(item for item in catalogue["species"] if item["type"] == "flower")
    flower["material_id"] = 101
    assert "outside" in _text(fc.check(catalogue))


def test_check_reports_unknown_type():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["species"][0]["type"] = "climber"
    assert "climber" in _text(fc.check(catalogue))


def test_check_reports_duplicate_latin():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["species"][1]["latin"] = catalogue["species"][0]["latin"]
    assert "duplicate latin" in _text(fc.check(catalogue))


def test_check_reports_wrong_object_name():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["species"][0]["objects"]["NPM"] = "Wrong_NPM"
    assert "object name" in _text(fc.check(catalogue)).lower() or "Wrong_NPM" in _text(fc.check(catalogue))


def test_check_reports_reused_retired_id():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["retired_ids"].append(catalogue["species"][0]["material_id"])
    assert "retired" in _text(fc.check(catalogue))


def test_check_reports_approved_without_opacity():
    catalogue = _load("library/flora/catalogue.json")
    betula = next(item for item in catalogue["species"] if item["latin"] == "Betula pendula")
    betula["maps"]["opacity"] = None
    assert "approved" in _text(fc.check(catalogue))


def test_check_reports_map_extension_other_than_png():
    catalogue = _load("library/flora/catalogue.json")
    betula = next(item for item in catalogue["species"] if item["latin"] == "Betula pendula")
    betula["maps"]["diffuse"] = "C:/x/flora-textures/betula-pendula/diffuse-v001.tga"
    assert ".png" in _text(fc.check(catalogue))


def test_check_reports_map_path_inside_the_repository():
    catalogue = _load("library/flora/catalogue.json")
    betula = next(item for item in catalogue["species"] if item["latin"] == "Betula pendula")
    betula["maps"]["diffuse"] = str(fc.REPO / "library" / "flora" / "synthetic-inside.png")
    assert "repository" in _text(fc.check(catalogue))


def test_check_reports_missing_key():
    catalogue = _load("library/flora/catalogue.json")
    del catalogue["species"][0]["note"]
    assert "note" in _text(fc.check(catalogue))


def _synthetic_species(kind: str, index: int, rng: random.Random) -> dict:
    return {
        "latin": f"Synthetic {kind} {index}",
        "russian": "synthetic",
        "type": kind,
        "sources": [f"synthetic-{kind}-{index}"],
        "geometry_basis": rng.choice(["own_mesh", "shared_multi_species_stand_in"]),
        "note": "synthetic",
        "profile_raw": rng.choice([["LP"], ["LP -> HP"], []]),
        "hidden": rng.choice([False, True]),
        "triangles": rng.randint(1, 4000),
        "dimensions_m": [rng.uniform(0.2, 8), rng.uniform(0.2, 8), rng.uniform(0.2, 20)],
    }


def _synthetic_inputs(species: list[dict], rng: random.Random) -> tuple[dict, dict, dict]:
    entries = []
    for item in species:
        entries.append({
            "id": item["sources"][0],
            "source_name": f"synthetic-{item['sources'][0]}",
            "profile_raw": item["profile_raw"],
            "hidden": item["hidden"],
            "triangles": item["triangles"],
            "dimensions_m": item["dimensions_m"],
        })
    audit = {"scenes": [{"source": {"scene": "FLORA_Union_v1.max"}, "entries": entries}]}
    curation = {
        "species": [
            {key: item[key] for key in ("latin", "russian", "type", "sources", "geometry_basis", "note")}
            for item in species
        ],
        "unresolved": [{"sources": ["synthetic-unresolved"], "reason": "synthetic"}],
    }
    maps = {}
    for item in species:
        if rng.random() < 0.2:
            folder = fc.slug(item["latin"])
            status = rng.choice(["approved", "pending_review"])
            maps[item["latin"]] = {
                "diffuse": f"C:/x/flora-textures/synthetic/{folder}/diffuse-v001.png",
                "opacity": f"C:/x/flora-textures/synthetic/{folder}/opacity-v001.png",
                "review_status": status,
                "evidence": "synthetic review",
            }
    return audit, curation, maps


def _apply_fault(catalogue: dict, name: str) -> bool:
    species = catalogue["species"]
    if name == "missing_key":
        if species:
            del species[0]["note"]
        else:
            del catalogue["library_file"]
        return True
    if not species:
        return False
    if name == "duplicate_id":
        if len(species) < 2:
            species.append(deepcopy(species[0]))
        else:
            species[1]["material_id"] = species[0]["material_id"]
        return True
    if name == "id_50":
        species[0]["material_id"] = 50
        return True
    if name == "tree_205":
        tree = next((item for item in species if item["type"] == "tree"), None)
        if tree is None:
            return False
        tree["material_id"] = 205
        return True
    if name == "bush_150":
        bush = next((item for item in species if item["type"] == "bush"), None)
        if bush is None:
            return False
        bush["material_id"] = 150
        return True
    if name == "flower_101":
        flower = next((item for item in species if item["type"] == "flower"), None)
        if flower is None:
            return False
        flower["material_id"] = 101
        return True
    if name == "unknown_type":
        species[0]["type"] = "climber"
        return True
    if name == "duplicate_latin":
        if len(species) < 2:
            clone = deepcopy(species[0])
            species.append(clone)
        species[1]["latin"] = species[0]["latin"]
        return True
    if name == "wrong_object_name":
        species[0]["objects"]["NPM"] = "Wrong_NPM"
        return True
    if name == "retired":
        catalogue["retired_ids"].append(species[0]["material_id"])
        return True
    if name == "approved_without_opacity":
        species[0]["maps"]["review_status"] = "approved"
        species[0]["maps"]["opacity"] = None
        return True
    if name == "tga":
        species[0]["maps"]["diffuse"] = "C:/x/flora-textures/synthetic/diffuse-v001.tga"
        return True
    if name == "inside_repo":
        species[0]["maps"]["diffuse"] = str(fc.REPO / "library" / "flora" / "synthetic-inside.png")
        return True
    raise AssertionError(name)


def test_synthetic_probe_keeps_ids_and_reports_one_fault():
    """Synthetic data: 500 random catalogues, not real Flora species or meshes."""
    rng = random.Random(216)
    kinds = ("tree", "bush", "hedge", "flower")
    faults = (
        "duplicate_id", "id_50", "tree_205", "bush_150", "flower_101", "unknown_type",
        "duplicate_latin", "wrong_object_name", "retired", "approved_without_opacity",
        "tga", "inside_repo", "missing_key",
    )
    for _ in range(500):
        pool = []
        for kind in kinds:
            for index in range(rng.randint(0, 60)):
                pool.append(_synthetic_species(kind, index, rng))
        rng.shuffle(pool)
        cut = rng.randint(0, len(pool)) if pool else 0
        initial = pool[:cut]
        held = pool[cut:]
        audit, curation, maps = _synthetic_inputs(pool, rng)
        first = fc.build(audit, {"species": [
            {key: item[key] for key in ("latin", "russian", "type", "sources", "geometry_basis", "note")}
            for item in initial
        ], "unresolved": curation["unresolved"]}, maps)
        assert fc.check(first) == []
        remove_n = rng.randint(0, len(initial)) if initial else 0
        removed = {item["latin"] for item in rng.sample(initial, remove_n)} if remove_n else set()
        remaining = [item for item in initial if item["latin"] not in removed]
        insert_n = rng.randint(0, len(held)) if held else 0
        inserted = held[:insert_n]
        rebuilt_species = inserted + remaining
        rng.shuffle(rebuilt_species)
        if inserted:
            rebuilt_species.remove(inserted[0])
            rebuilt_species.insert(0, inserted[0])
        second_curation = {
            "species": [
                {key: item[key] for key in ("latin", "russian", "type", "sources", "geometry_basis", "note")}
                for item in rebuilt_species
            ],
            "unresolved": curation["unresolved"],
        }
        second = fc.build(audit, second_curation, maps, first)
        assert fc.check(second) == []
        old_ids = {item["latin"]: item["material_id"] for item in first["species"]}
        for item in second["species"]:
            if item["latin"] in old_ids:
                assert item["material_id"] == old_ids[item["latin"]]
        fault = rng.choice(faults)
        broken = deepcopy(second)
        applied = _apply_fault(broken, fault)
        if not applied:
            for fallback in faults:
                broken = deepcopy(second)
                if _apply_fault(broken, fallback):
                    applied = True
                    break
        assert applied
        assert fc.check(broken)
