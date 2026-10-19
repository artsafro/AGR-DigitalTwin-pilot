"""Flora library catalogue: source selection, stable material IDs, and schema check.

The random probe builds synthetic species, meshes and catalogues. Those records are
not a real planting schedule, library scene or approved texture.
"""
import importlib.util
import json
import random
import struct
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
    # library-024 is LP -> HP and has no geometry evidence, so it is not a VPM.
    # project-034 is explicit HP and stays an unverified VPM.
    assert ginnala["VPM"]["entry_id"] == "project-034"
    assert ginnala["vpm_status"] == "available"
    assert ginnala["vpm_identity"] == "unverified"

    pinus = fc.select_sources(_sources("Pinus nigra"))
    assert pinus["NPM"]["entry_id"] == "library-084"
    assert pinus["VPM"]["entry_id"] == "library-064"
    assert pinus["vpm_identity"] == "unverified"

    tilia = fc.select_sources(_sources("Tilia cordata"))
    assert tilia["NPM"]["entry_id"] == "library-028"
    assert tilia["VPM"] is None
    assert tilia["vpm_status"] == "unconfirmed"
    assert tilia["vpm_identity"] is None
    assert any(item["entry_id"] == "library-002" for item in tilia["merged"])
    library_001 = next(item for item in tilia["merged"] if item["entry_id"] == "library-001")
    assert "unverified" in library_001["reason"]

    betula = fc.select_sources(_sources("Betula pendula"))
    assert betula["NPM"]["entry_id"] == "library-006"
    assert betula["NPM"]["basis"] == "LP -> HP"
    assert betula["VPM"] is None
    assert betula["vpm_status"] == "unconfirmed"
    assert betula["vpm_identity"] is None


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
    assert old_ids[removed["latin"]] in _retired_ids(rebuilt)
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


def test_committed_catalogue_has_no_findings_and_matches_rebuild_with_identity():
    """The committed catalogue is exactly the build from the committed inputs and Max identity evidence."""
    catalogue = _load("library/flora/catalogue.json")
    identity = fc.load_identity(_load("library/flora/geometry-identity.json"))
    rebuilt = fc.build(
        _load("experiments/flora-library-audit/catalogue.json"),
        _load("library/flora/species-curation.json"),
        _load("library/flora/maps.json"),
        catalogue,
        identity,
    )
    assert fc.check(catalogue) == []
    assert rebuilt == catalogue
    assert {item["vpm_identity"] for item in catalogue["species"] if item["vpm"] is not None} == {"verified_distinct"}


def test_committed_material_ids_survive_a_rebuild_without_identity():
    """Without identity evidence the material IDs still do not move."""
    catalogue = _load("library/flora/catalogue.json")
    rebuilt = _build_real(previous=catalogue)
    assert fc.check(rebuilt) == []
    assert {item["latin"]: item["material_id"] for item in rebuilt["species"]} == {
        item["latin"]: item["material_id"] for item in catalogue["species"]
    }
    assert {
        item["latin"]: item["material_id"]
        for item in rebuilt["gaps"]["project_species_shared_stand_in"]
    } == {
        item["latin"]: item["material_id"]
        for item in catalogue["gaps"]["project_species_shared_stand_in"]
    }


def _text(findings: list[str]) -> str:
    return "\n".join(findings)


def _retired_ids(catalogue) -> set[int]:
    found = set()
    for item in catalogue["retired_ids"]:
        if isinstance(item, dict):
            found.add(item["material_id"])
        else:
            found.add(item)
    return found


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
    catalogue["species"][0]["type"] = "lichen"
    assert "lichen" in _text(fc.check(catalogue))


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
    holder = catalogue["species"][0]
    catalogue["retired_ids"].append({
        "material_id": holder["material_id"],
        "latin": "Synthetic retired holder",
        "type": holder["type"],
    })
    assert "is retired" in _text(fc.check(catalogue))


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


def _mesh(entry_id, profile, triangles=10):
    return {
        "id": entry_id,
        "scene": "FLORA_Union_v1.max",
        "source_name": entry_id,
        "profile_raw": [profile],
        "hidden": False,
        "triangles": triangles,
        "dimensions_m": [1.0, 1.0, 2.0],
    }


def test_lone_lp_hp_is_not_a_vpm():
    chosen = fc.select_sources([_mesh("solo", "LP -> HP")])
    assert chosen["VPM"] is None
    assert chosen["NPM"]["basis"] == "LP -> HP"
    assert chosen["vpm_status"] == "unconfirmed"


def test_lp_hp_without_a_fingerprint_is_not_a_vpm():
    """An LP -> HP row is not a VPM until pair evidence shows a distinct mesh."""
    chosen = fc.select_sources([_mesh("npm", "LP", 8), _mesh("vpm", "LP -> HP", 80)])
    assert chosen["NPM"]["entry_id"] == "npm"
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "unconfirmed"
    assert chosen["vpm_identity"] is None
    assert "unverified" in chosen["merged"][0]["reason"]


def test_vpm_status_none_without_a_vpm_candidate():
    chosen = fc.select_sources([_mesh("npm", "LP")])
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "none"


def test_shared_stand_in_gap_keeps_a_reserved_id():
    """The inserted tree is synthetic and is not a real library species."""
    catalogue = _load("library/flora/catalogue.json")
    pinus = next(
        item for item in catalogue["gaps"]["project_species_shared_stand_in"] if item["latin"] == "Pinus sylvestris"
    )
    assert pinus["material_id"] == 126
    assert pinus["status"] == fc.SHARED_STAND_IN_STATUS
    assert pinus["type"] == "tree"
    assert "Pinus sylvestris" not in {item["latin"] for item in catalogue["species"]}
    curation = _load("library/flora/species-curation.json")
    curation["species"].insert(0, {
        "latin": "Syntheticus reservatus",
        "russian": "synthetic",
        "type": "tree",
        "sources": ["library-028"],
        "geometry_basis": "own_mesh",
        "note": "synthetic species that must not receive a reserved gap id",
    })
    rebuilt = fc.build(
        _load("experiments/flora-library-audit/catalogue.json"),
        curation,
        _load("library/flora/maps.json"),
        catalogue,
    )
    again = next(
        item for item in rebuilt["gaps"]["project_species_shared_stand_in"] if item["latin"] == "Pinus sylvestris"
    )
    assert again["material_id"] == 126
    assert 126 not in _retired_ids(rebuilt)
    synthetic = next(item for item in rebuilt["species"] if item["latin"] == "Syntheticus reservatus")
    assert synthetic["material_id"] != 126
    gap_ids = {item["material_id"] for item in rebuilt["gaps"]["project_species_shared_stand_in"]}
    assert synthetic["material_id"] not in gap_ids
    old_ids = {item["latin"]: item["material_id"] for item in catalogue["species"]}
    new_ids = {item["latin"]: item["material_id"] for item in rebuilt["species"]}
    for latin, material_id in old_ids.items():
        assert new_ids[latin] == material_id
    assert fc.check(rebuilt) == []


def test_parthenocissus_is_climber_501():
    catalogue = _load("library/flora/catalogue.json")
    item = next(row for row in catalogue["species"] if row["latin"] == "Parthenocissus quinquefolia")
    assert item["type"] == "climber"
    assert item["material_id"] == 501
    assert item["geometry_basis"] == "own_mesh"
    assert item["vpm"] is not None
    assert item["vpm_status"] == "available"
    assert catalogue["id_ranges"]["climber"] == [501, 599]
    assert catalogue["counts"]["by_type"]["climber"] == 1


def test_grasses_stay_flowers():
    catalogue = _load("library/flora/catalogue.json")
    ids = {item["latin"]: item for item in catalogue["species"]}
    assert ids["Tilia cordata"]["material_id"] == 101
    assert ids["Spiraea × bumalda"]["material_id"] == 239
    for latin, material_id in (
        ("Symphyotrichum novae-angliae", 401),
        ("Miscanthus sinensis", 406),
        ("Calamagrostis × acutiflora 'Karl Foerster'", 409),
    ):
        assert ids[latin]["type"] == "flower"
        assert ids[latin]["material_id"] == material_id


def test_check_reports_climber_id_outside_its_range():
    catalogue = _load("library/flora/catalogue.json")
    climber = next(item for item in catalogue["species"] if item["type"] == "climber")
    climber["material_id"] = 500
    assert "501-599" in _text(fc.check(catalogue))


def test_unresolved_mnogotsvetnik_is_unidentified():
    catalogue = _load("library/flora/catalogue.json")
    rows = catalogue["gaps"]["unresolved"]
    assert catalogue["counts"]["unresolved"] == 1
    assert catalogue["counts"]["shared_stand_in_gaps"] == 15
    assert rows[0]["status"] == "unidentified"
    assert "latin" not in rows[0]
    assert rows[0]["source_names"] == [
        "Многоцветник_v1",
        "Многоцветник_v2",
        "Многоцветник_v3",
        "Многоцветники_v4",
    ]


def test_batch1_maps_are_approved_in_the_library_folder():
    evidence = (
        "Artem 2026-10-16 card t_6c48bc9d comment: all five batch-1 pairs approved "
        "(map-only approval, not model acceptance); review-sheet-batch1-v001.png"
    )
    maps = _load("library/flora/maps.json")
    approved = (
        "Tilia cordata",
        "Acer platanoides",
        "Sorbus aucuparia",
        "Cornus alba",
        "Hydrangea arborescens",
    )
    for latin in approved:
        assert maps[latin]["review_status"] == "approved"
        assert maps[latin]["evidence"] == evidence
    for latin in approved + ("Betula pendula", "Spiraea japonica", "Pinus sylvestris"):
        folder = fc.slug(latin)
        assert maps[latin]["diffuse"] == f"{fc.MAPS_ROOT}/{folder}/diffuse-v001.png"
        assert maps[latin]["opacity"] == f"{fc.MAPS_ROOT}/{folder}/opacity-v001.png"
    catalogue = _load("library/flora/catalogue.json")
    tilia = next(item for item in catalogue["species"] if item["latin"] == "Tilia cordata")
    assert tilia["maps"]["review_status"] == "approved"
    assert "Pinus sylvestris" not in {item["latin"] for item in catalogue["species"]}
    assert "Pinus sylvestris" in maps


def test_check_reports_vpm_status_mismatch():
    catalogue = _load("library/flora/catalogue.json")
    betula = next(item for item in catalogue["species"] if item["latin"] == "Betula pendula")
    assert betula["vpm"] is None
    assert betula["vpm_status"] == "unconfirmed"
    assert betula["npm"]["basis"] == "LP -> HP"
    betula["vpm_status"] = "available"
    assert "vpm_status" in _text(fc.check(catalogue))


def _builder():
    path = ROOT / "tools" / "flora" / "build_flora_library_max.py"
    spec = importlib.util.spec_from_file_location("build_flora_library_max", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_library_layout_and_pivot_helpers():
    builder = _builder()
    assert builder.layout_position(0, 0) == (0.0, 0.0, 0.0)
    assert builder.layout_position(2, 1) == (24.0, 12.0, 0.0)
    assert builder.pivot_target(0.0, 0.0, 2.0, 4.0, -0.2) == (1.0, 2.0, -0.1)
    assert builder.material_name("Tilia_cordata_NPM", 101) == "Tilia_cordata_ID101"
    assert builder.material_name("Tilia_cordata_VPM", 101) == "Tilia_cordata_ID101"


def test_random_id_sets_keep_reserved_and_retired_ids():
    """Synthetic species only: random previous and current sets, not a real planting schedule."""
    rng = random.Random(216)
    kinds = ("tree", "bush", "hedge", "flower", "climber")
    for step in range(400):
        pool = []
        used = {kind: set() for kind in kinds}
        for kind in kinds:
            low, high = fc.RANGES[kind]
            numbers = list(range(low, high + 1))
            rng.shuffle(numbers)
            for index, material_id in enumerate(numbers[: rng.randint(0, 12)]):
                pool.append({"latin": f"{kind}-{index}", "type": kind, "material_id": material_id})
                used[kind].add(material_id)
        previous_species, previous_gaps = [], []
        for item in pool:
            target = previous_gaps if rng.random() < 0.3 else previous_species
            target.append(dict(item))
        retired_seed = []
        for kind in kinds:
            low, high = fc.RANGES[kind]
            free = [number for number in range(low, high + 1) if number not in used[kind]]
            rng.shuffle(free)
            retired_seed.extend(free[: rng.randint(0, 5)])
        current_species, current_gaps, kept = [], [], {}
        retired_expected = []
        for item in pool:
            roll = rng.random()
            if roll < 0.2:
                retired_expected.append(item["material_id"])
                continue
            target = current_gaps if roll < 0.45 else current_species
            target.append({"latin": item["latin"], "type": item["type"]})
            kept[item["latin"]] = item["material_id"]
        for kind in kinds:
            low, high = fc.RANGES[kind]
            free = [
                number for number in range(low, high + 1)
                if number not in used[kind] and number not in retired_seed
            ]
            rng.shuffle(free)
            for index, _material_id in enumerate(free[: rng.randint(0, 3)]):
                current_species.append({"latin": f"new-{kind}-{index}-{step}", "type": kind})
        previous = {
            "retired_ids": list(retired_seed),
            "species": previous_species,
            "gaps": {"project_species_shared_stand_in": previous_gaps},
        }
        assigned = fc.assign_ids(current_species, previous, current_gaps)
        types = {item["latin"]: item["type"] for item in current_species + current_gaps}
        values = list(assigned["by_latin"].values())
        assert len(values) == len(set(values))
        for latin, material_id in assigned["by_latin"].items():
            low, high = fc.RANGES[types[latin]]
            assert low <= material_id <= high
            assert not 1 <= material_id <= 100
        for latin, material_id in kept.items():
            assert assigned["by_latin"][latin] == material_id
        blocked = set(retired_expected) | set(retired_seed)
        for material_id in blocked:
            assert material_id in _retired_ids(assigned)
            assert material_id not in values
        reserved = {kept[item["latin"]] for item in current_gaps}
        for item in current_species + current_gaps:
            if item["latin"] not in kept:
                assert assigned["by_latin"][item["latin"]] not in blocked
                assert assigned["by_latin"][item["latin"]] not in reserved


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
        species[0]["type"] = "lichen"
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
        holder = species[0]
        catalogue["retired_ids"].append({
            "material_id": holder["material_id"],
            "latin": "Synthetic retired holder",
            "type": holder["type"],
        })
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
    kinds = ("tree", "bush", "hedge", "flower", "climber")
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
        assert all(item["geometry_basis"] != "shared_multi_species_stand_in" for item in second["species"])
        first_gap_ids = {
            item["latin"]: item["material_id"] for item in first["gaps"]["project_species_shared_stand_in"]
        }
        second_gap_ids = {
            item["latin"]: item["material_id"] for item in second["gaps"]["project_species_shared_stand_in"]
        }
        all_ids = [item["material_id"] for item in second["species"]] + list(second_gap_ids.values())
        assert len(all_ids) == len(set(all_ids))
        assert all(not 1 <= material_id <= 100 for material_id in all_ids)
        for item in list(second["species"]) + list(second["gaps"]["project_species_shared_stand_in"]):
            low, high = fc.RANGES[item["type"]]
            assert low <= item["material_id"] <= high
        retired_ids = _retired_ids(second)
        for latin, material_id in first_gap_ids.items():
            if latin in removed:
                assert material_id in retired_ids
                assert material_id not in all_ids
            else:
                assert second_gap_ids[latin] == material_id
        reserved = {material_id for latin, material_id in first_gap_ids.items() if latin not in removed}
        for item in second["species"]:
            if item["latin"] not in old_ids:
                assert item["material_id"] not in reserved
                assert item["material_id"] not in retired_ids
        for latin, material_id in second_gap_ids.items():
            if latin not in first_gap_ids:
                assert material_id not in reserved
                assert material_id not in retired_ids
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


def test_pivot_for_bounds_uses_lowest_z_not_max_y():
    """Regression: adopt() passed world_vertex_bounds positionally into pivot_target (pivot 12 m off in Max readback)."""
    builder = _builder()
    bounds = (-22.25, 7.80, -0.03, -18.03, 12.02)  # min_x, min_y, min_z, max_x, max_y (library-028 Tilia)
    x, y, z = builder.pivot_for_bounds(bounds)
    assert abs(x - (-20.14)) < 1e-9 and abs(y - 9.91) < 1e-9 and abs(z - 0.07) < 1e-9


_FLORA_KINDS = ("tree", "bush", "hedge", "flower", "climber")
_SAME_MESH_PAIRS = (
    ("Hydrangea arborescens 'Bounty'", "library-087"),
    ("Hydrangea paniculata 'Limelight'", "library-088"),
    ("Sorbaria sorbifolia 'Sem'", "library-090"),
)


@pytest.mark.parametrize(("latin", "duplicate"), _SAME_MESH_PAIRS)
def test_duplicate_lp_hp_rows_are_not_a_distinct_vpm(latin, duplicate):
    chosen = fc.select_sources(_sources(latin))
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "unconfirmed"
    assert chosen["NPM"]["basis"] == "LP -> HP"
    merged = next(item for item in chosen["merged"] if item["entry_id"] == duplicate)
    assert "unverified" in merged["reason"]
    assert chosen["vpm_identity"] is None


def test_three_equal_lp_hp_rows_leave_vpm_unconfirmed():
    """Three synthetic LP -> HP copies of one mesh are not a VPM pair."""
    chosen = fc.select_sources([
        _mesh("copy-a", "LP -> HP", 40),
        _mesh("copy-b", "LP -> HP", 40),
        _mesh("copy-c", "LP -> HP", 40),
    ])
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "unconfirmed"
    assert chosen["NPM"]["basis"] == "LP -> HP"


def test_explicit_hp_with_a_different_triangle_count_is_a_vpm():
    """Synthetic control: explicit HP with no pair evidence is an unverified VPM."""
    chosen = fc.select_sources([_mesh("npm", "LP", 12), _mesh("vpm", "HP", 80)])
    assert chosen["VPM"]["entry_id"] == "vpm"
    assert chosen["vpm_status"] == "available"
    assert chosen["vpm_identity"] == "unverified"


@pytest.mark.parametrize(
    ("latin", "npm_id", "vpm_id"),
    [
        ("Cornus alba", "library-011", "library-010"),
        ("Amelanchier lamarckii", "project-009", "library-020"),
    ],
)
def test_distinct_geometry_keeps_its_vpm(latin, npm_id, vpm_id):
    chosen = fc.select_sources(_sources(latin))
    assert chosen["NPM"]["entry_id"] == npm_id
    assert chosen["VPM"]["entry_id"] == vpm_id
    assert chosen["vpm_status"] == "available"


def test_check_reports_vpm_that_repeats_the_npm_mesh():
    catalogue = _load("library/flora/catalogue.json")
    item = next(row for row in catalogue["species"] if row["latin"] == "Tilia cordata")
    item["vpm"] = deepcopy(item["npm"])
    item["vpm_status"] = "available"
    item["objects"]["VPM"] = fc.object_name(item["latin"], "VPM")
    item["triangles"]["VPM"] = item["npm"]["triangles"]
    assert "not a distinct VPM" in _text(fc.check(catalogue))


def test_committed_catalogue_has_no_same_mesh_vpm():
    catalogue = _load("library/flora/catalogue.json")
    by_latin = {item["latin"]: item for item in catalogue["species"]}
    for latin, _duplicate in _SAME_MESH_PAIRS:
        item = by_latin[latin]
        assert item["vpm"] is None
        assert item["objects"]["VPM"] is None
        assert item["vpm_status"] == "unconfirmed"
    assert catalogue["counts"]["with_vpm"] == 38


def _id_invariants(assigned, rows):
    types = {item["latin"]: item["type"] for item in rows}
    values = list(assigned["by_latin"].values())
    assert len(values) == len(set(values))
    assert set(assigned["by_latin"]) == set(types)
    for latin, material_id in assigned["by_latin"].items():
        low, high = fc.RANGES[types[latin]]
        assert low <= material_id <= high
        assert not 1 <= material_id <= 100


def _previous_from(assigned, species, gaps):
    return {
        "retired_ids": assigned["retired_ids"],
        "species": [
            {"latin": item["latin"], "type": item["type"], "material_id": assigned["by_latin"][item["latin"]]}
            for item in species
        ],
        "gaps": {
            "project_species_shared_stand_in": [
                {"latin": item["latin"], "type": item["type"], "material_id": assigned["by_latin"][item["latin"]]}
                for item in gaps
            ]
        },
    }


@pytest.mark.parametrize("kind", _FLORA_KINDS)
def test_readded_species_recovers_its_material_id(kind):
    """Synthetic species: remove and re-add must return the same material ID."""
    latin = "Synthetic reappearing plant"
    first = fc.assign_ids([{"latin": latin, "type": kind}])
    old = first["by_latin"][latin]
    removed = fc.assign_ids(
        [],
        {"species": [{"latin": latin, "type": kind, "material_id": old}], "retired_ids": []},
    )
    third = fc.assign_ids(
        [{"latin": latin, "type": kind}],
        {"species": [], "retired_ids": removed["retired_ids"]},
    )
    assert third["by_latin"][latin] == old


@pytest.mark.parametrize("kind", _FLORA_KINDS)
def test_material_id_is_not_reissued_across_generations(kind):
    """Synthetic species and one stand-in gap: an ID stays with its latin name."""
    names = {key: f"Synthetic {kind} {key}" for key in ("A", "B", "C", "G", "N", "M")}

    def row(key):
        return {"latin": names[key], "type": kind}

    gen1_species = [row("A"), row("B"), row("C")]
    gen1_gaps = [row("G")]
    gen1 = fc.assign_ids(gen1_species, gaps=gen1_gaps)
    _id_invariants(gen1, gen1_species + gen1_gaps)
    id_a = gen1["by_latin"][names["A"]]
    id_b = gen1["by_latin"][names["B"]]
    id_c = gen1["by_latin"][names["C"]]
    id_g = gen1["by_latin"][names["G"]]

    gen2_species = [row("C"), row("B"), row("N")]
    gen2_gaps = [row("G")]
    gen2 = fc.assign_ids(gen2_species, _previous_from(gen1, gen1_species, gen1_gaps), gen2_gaps)
    _id_invariants(gen2, gen2_species + gen2_gaps)
    assert gen2["by_latin"][names["B"]] == id_b
    assert gen2["by_latin"][names["C"]] == id_c
    assert gen2["by_latin"][names["G"]] == id_g
    assert gen2["by_latin"][names["N"]] != id_a
    retired_a = next(item for item in gen2["retired_ids"] if item["latin"] == names["A"])
    assert retired_a == {"material_id": id_a, "latin": names["A"], "type": kind}
    id_n = gen2["by_latin"][names["N"]]

    gen3_species = [row("A"), row("M"), row("B"), row("C")]
    gen3_gaps = [row("G")]
    gen3 = fc.assign_ids(gen3_species, _previous_from(gen2, gen2_species, gen2_gaps), gen3_gaps)
    _id_invariants(gen3, gen3_species + gen3_gaps)
    assert gen3["by_latin"][names["A"]] == id_a
    assert gen3["by_latin"][names["B"]] == id_b
    assert gen3["by_latin"][names["C"]] == id_c
    assert gen3["by_latin"][names["G"]] == id_g
    assert gen3["by_latin"][names["M"]] not in {id_a, id_n}

    gen4_species = [row("N"), row("A"), row("B"), row("C"), row("M")]
    gen4_gaps = [row("G")]
    gen4 = fc.assign_ids(gen4_species, _previous_from(gen3, gen3_species, gen3_gaps), gen4_gaps)
    _id_invariants(gen4, gen4_species + gen4_gaps)
    assert gen4["by_latin"][names["N"]] == id_n
    assert gen4["by_latin"][names["A"]] == id_a
    assert gen4["by_latin"][names["M"]] == gen3["by_latin"][names["M"]]


def test_removed_real_species_retires_and_recovers_its_id():
    committed = _load("library/flora/catalogue.json")
    bush = next(item for item in committed["species"] if item["type"] == "bush")
    audit = _load("experiments/flora-library-audit/catalogue.json")
    maps = _load("library/flora/maps.json")
    curation = _load("library/flora/species-curation.json")
    without_curation = deepcopy(curation)
    index = next(i for i, item in enumerate(without_curation["species"]) if item["latin"] == bush["latin"])
    without_curation["species"].pop(index)
    without = fc.build(audit, without_curation, maps, committed)
    assert fc.check(without) == []
    retired = next(item for item in without["retired_ids"] if item["material_id"] == bush["material_id"])
    assert retired["latin"] == bush["latin"]
    assert retired["type"] == bush["type"]
    restored = fc.build(audit, curation, maps, without)
    assert fc.check(restored) == []
    again = next(item for item in restored["species"] if item["latin"] == bush["latin"])
    assert again["material_id"] == bush["material_id"]
    committed_ids = {item["latin"]: item["material_id"] for item in committed["species"]}
    restored_ids = {item["latin"]: item["material_id"] for item in restored["species"]}
    assert restored_ids == committed_ids
    committed_gaps = {
        item["latin"]: item["material_id"]
        for item in committed["gaps"]["project_species_shared_stand_in"]
    }
    restored_gaps = {
        item["latin"]: item["material_id"]
        for item in restored["gaps"]["project_species_shared_stand_in"]
    }
    assert len(restored_gaps) == 15
    assert restored_gaps == committed_gaps


def test_legacy_retired_ints_stay_blocked_and_are_normalized():
    """Bare ints in a previous catalogue stay blocked; they are not a real species."""
    previous = {"species": [], "retired_ids": [101, 202]}
    assigned = fc.assign_ids(
        [
            {"latin": "Synthetic blocked tree", "type": "tree"},
            {"latin": "Synthetic blocked bush", "type": "bush"},
        ],
        previous,
    )
    assert assigned["by_latin"]["Synthetic blocked tree"] == 102
    assert assigned["by_latin"]["Synthetic blocked bush"] == 201
    assert assigned["retired_ids"] == [
        {"material_id": 101, "latin": None, "type": None},
        {"material_id": 202, "latin": None, "type": None},
    ]


def _free_material_id(catalogue, kind):
    used = {item["material_id"] for item in catalogue["species"]}
    used |= {item["material_id"] for item in catalogue["gaps"]["project_species_shared_stand_in"]}
    low, high = fc.RANGES[kind]
    return next(number for number in range(low, high + 1) if number not in used)


def test_check_reports_retired_latin_that_is_also_active():
    catalogue = _load("library/flora/catalogue.json")
    holder = catalogue["species"][0]
    catalogue["retired_ids"].append({
        "material_id": _free_material_id(catalogue, holder["type"]),
        "latin": holder["latin"],
        "type": holder["type"],
    })
    assert "is also active" in _text(fc.check(catalogue))


def test_check_reports_retired_id_outside_its_type_range():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["retired_ids"].append({
        "material_id": 250,
        "latin": "Synthetic retired tree",
        "type": "tree",
    })
    assert "outside the tree range" in _text(fc.check(catalogue))


def test_check_reports_duplicate_retired_material_id():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["retired_ids"] = [
        {"material_id": 199, "latin": "Synthetic retired one", "type": "tree"},
        {"material_id": 199, "latin": "Synthetic retired two", "type": "tree"},
    ]
    assert "duplicate retired material_id 199" in _text(fc.check(catalogue))


def test_check_reports_bare_int_retired_entry():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["retired_ids"].append(180)
    assert "is not an object" in _text(fc.check(catalogue))


def test_check_reports_retired_latin_without_a_type():
    catalogue = _load("library/flora/catalogue.json")
    catalogue["retired_ids"].append({
        "material_id": 180,
        "latin": "Synthetic retired tree",
        "type": None,
    })
    assert "both be set or both be null" in _text(fc.check(catalogue))


def test_random_generations_keep_each_material_id_with_one_species():
    """Synthetic species: 300 four-generation rebuilds, not a real planting schedule."""
    rng = random.Random(2161)
    for run in range(300):
        pool = {
            kind: [f"Synthetic {kind} {index} run {run}" for index in range(6)]
            for kind in _FLORA_KINDS
        }
        active = {kind: [] for kind in _FLORA_KINDS}
        previous = None
        held_by_latin = {}
        latin_by_id = {}
        for _generation in range(4):
            species = []
            for kind in _FLORA_KINDS:
                active[kind] = [latin for latin in active[kind] if rng.random() >= 0.35]
                absent = [latin for latin in pool[kind] if latin not in active[kind]]
                rng.shuffle(absent)
                active[kind].extend(absent[: rng.randint(0, 2)])
                rng.shuffle(active[kind])
                species.extend({"latin": latin, "type": kind} for latin in active[kind])
            assigned = fc.assign_ids(species, previous)
            _id_invariants(assigned, species)
            for latin, material_id in assigned["by_latin"].items():
                if latin in held_by_latin:
                    assert held_by_latin[latin] == material_id
                else:
                    held_by_latin[latin] = material_id
                if material_id in latin_by_id:
                    assert latin_by_id[material_id] == latin
                else:
                    latin_by_id[material_id] = latin
            previous = _previous_from(assigned, species, [])


def _equal_count_pair():
    """Synthetic 2x2x4 m LP star and HP shell, both 12 triangles. Not a real species."""
    star = _mesh("synthetic-star", "LP", 12)
    shell = _mesh("synthetic-shell", "HP", 12)
    star["source_name"] = "Synthetic_equal_count_star_LP"
    shell["source_name"] = "Synthetic_equal_count_shell_HP"
    star["dimensions_m"] = [2.0, 2.0, 4.0]
    shell["dimensions_m"] = [2.0, 2.0, 4.0]
    star["scene"] = "Synthetic.max"
    shell["scene"] = "Synthetic.max"
    return [star, shell]


def _catalogue_for(entries, identity=None):
    audit = {"scenes": [{"source": {"scene": entries[0]["scene"]}, "entries": entries}]}
    curation = {
        "species": [{
            "latin": "Synthetic witness",
            "russian": "synthetic",
            "type": "bush",
            "sources": [entry["id"] for entry in entries],
            "geometry_basis": "own_mesh",
            "note": "synthetic",
        }],
        "unresolved": [],
    }
    return fc.build(audit, curation, {}, identity=identity)


def _signature(chosen):
    return (
        chosen["NPM"]["entry_id"],
        None if chosen["VPM"] is None else chosen["VPM"]["entry_id"],
        chosen["vpm_status"],
        chosen["vpm_identity"],
    )


_BASE_CLOUD = (
    [0.0, 0.0, 0.0],
    [1.2, 0.1, 0.0],
    [0.2, 1.4, 0.3],
    [0.15, 0.2, 2.2],
    [0.8, 0.9, 1.1],
)


def _box_points():
    """Closed 2 x 2 x 4 m box, 8 vertices. Synthetic, not a library mesh."""
    return [[x, y, z] for x in (0.0, 2.0) for y in (0.0, 2.0) for z in (0.0, 4.0)]


def _star_planes():
    """Six unwelded vertical quads inside a 2 x 2 x 4 m volume. Synthetic."""
    points = []
    for y in (0.0, 1.0, 2.0):
        points.extend([[0.0, y, 0.0], [2.0, y, 0.0], [2.0, y, 4.0], [0.0, y, 4.0]])
    for x in (0.0, 1.0, 2.0):
        points.extend([[x, 0.0, 0.0], [x, 2.0, 0.0], [x, 2.0, 4.0], [x, 0.0, 4.0]])
    return points


def _other_eight():
    """Same vertex count as the box, not a translation or a uniform scale of it."""
    points = _box_points()
    points[7] = [3.5, 0.4, 2.2]
    return points


def _identity_for(clouds: dict) -> dict:
    curation = {
        "species": [{
            "latin": "Synthetic witness",
            "russian": "synthetic",
            "type": "bush",
            "sources": list(clouds),
            "geometry_basis": "own_mesh",
            "note": "synthetic",
        }],
        "unresolved": [],
    }
    return fc.load_identity(fc.build_identity(clouds, curation))


def _translate(points, offset):
    return [[point[0] + offset[0], point[1] + offset[1], point[2] + offset[2]] for point in points]


def _scale_then_translate(points, factor, offset):
    return _translate(
        [[point[0] * factor, point[1] * factor, point[2] * factor] for point in points],
        offset,
    )


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _float32_cloud(points, offset, scale=1.0, jitter=1.5e-5):
    copied = []
    for index, point in enumerate(points):
        sign = -1.0 if index % 2 else 1.0
        copied.append([
            _f32(point[axis] * scale + offset[axis] + sign * jitter)
            for axis in range(3)
        ])
    return copied


def test_star_and_shell_vertex_counts_differ_and_same_count_clouds_are_distinct():
    """Synthetic 2x2x4 m clouds. Triangle counts are 12/12 and are not the relation."""
    star = _star_planes()
    shell = _box_points()
    assert len(star) != len(shell) == 8
    counted = fc.compare_clouds(star, shell)
    assert counted["relation"] == "distinct"
    assert counted["translation_dev_m"] is None
    assert counted["scaled_dev_rel"] is None
    assert counted["vertices"] == [len(star), 8]
    same_count = fc.compare_clouds(shell, _other_eight())
    assert same_count["relation"] == "distinct"
    assert same_count["vertices"] == [8, 8]


def test_equal_count_lp_hp_without_evidence_stays_available():
    entries = _equal_count_pair()
    chosen = fc.select_sources(entries)
    assert chosen["VPM"]["entry_id"] == "synthetic-shell"
    assert chosen["vpm_status"] == "available"
    assert chosen["vpm_identity"] == "unverified"
    assert chosen["vpm_evidence"] == {
        "relation": "unknown",
        "translation_dev_m": None,
        "scaled_dev_rel": None,
    }
    assert chosen["merged"] == []
    assert "geometry_fingerprint" not in chosen["NPM"]
    assert "geometry_fingerprint" not in chosen["VPM"]
    catalogue = _catalogue_for(entries)
    assert catalogue["species"][0]["vpm_identity"] == "unverified"
    assert catalogue["species"][0]["vpm_evidence"]["relation"] == "unknown"
    assert fc.check(catalogue) == []


def test_compare_clouds_evidence_verifies_a_distinct_vpm():
    entries = _equal_count_pair()
    clouds = {"synthetic-star": _star_plane_faces(), "synthetic-shell": _box_faces()}
    identity = _identity_for(clouds)
    chosen = fc.select_sources(entries, identity)
    assert chosen["VPM"]["entry_id"] == "synthetic-shell"
    assert chosen["vpm_identity"] == "verified_distinct"
    assert chosen["vpm_evidence"]["relation"] == "distinct"
    assert chosen["vpm_evidence"]["translation_dev_m"] > 1e-4
    catalogue = _catalogue_for(entries, identity)
    assert catalogue["species"][0]["npm"]["triangles"] == catalogue["species"][0]["vpm"]["triangles"] == 12
    assert fc.check(catalogue) == []
    same_count_entries = _equal_count_pair()
    same_count_entries[0]["id"] = "synthetic-box"
    same_count_entries[1]["id"] = "synthetic-other"
    same_clouds = {"synthetic-box": _box_faces(), "synthetic-other": _faces_on(_other_eight())}
    same_identity = _identity_for(same_clouds)
    verified = fc.select_sources(same_count_entries, same_identity)
    assert verified["vpm_identity"] == "verified_distinct"
    assert verified["vpm_evidence"]["relation"] == "distinct"
    assert fc.check(_catalogue_for(same_count_entries, same_identity)) == []


def test_translated_copy_is_same_geometry_and_not_a_vpm():
    box = _box_points()
    moved = _translate(box, (37.1, -5.2, 3.3))
    compared = fc.compare_clouds(box, list(reversed(moved)))
    assert compared["relation"] == "same"
    assert compared["translation_dev_m"] <= 1e-4
    assert compared["scaled_dev_rel"] is None
    entries = _equal_count_pair()
    identity = _identity_for({
        "synthetic-star": _box_faces(),
        "synthetic-shell": _translate_faces(_box_faces(), (37.1, -5.2, 3.3)),
    })
    chosen = fc.select_sources(entries, identity)
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "none"
    assert chosen["vpm_identity"] is None
    assert chosen["vpm_evidence"] is None
    assert "verified same geometry" in chosen["merged"][0]["reason"]


def test_uniform_scale_of_lp_hp_rows_is_not_a_vpm():
    """Bounty shape: an LP -> HP mesh scaled by 0.799 is a scaled copy, not a VPM."""
    box = _box_points()
    scaled = _scale_then_translate(box, 0.799, (37.1, -5.2, 3.3))
    assert fc.compare_clouds(box, scaled)["relation"] == "scaled_copy"
    entries = [_mesh("library-044", "LP -> HP", 88), _mesh("library-087", "LP -> HP", 88)]
    identity = _identity_for({
        "library-044": _box_faces(),
        "library-087": _scale_faces(_box_faces(), 0.799, (37.1, -5.2, 3.3)),
    })
    chosen = fc.select_sources(entries, identity)
    assert fc.geometry_relation(entries[0], entries[1], identity) == "scaled_copy"
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "unconfirmed"
    assert chosen["vpm_identity"] is None
    assert "verified uniformly scaled copy" in chosen["merged"][0]["reason"]


def test_lp_hp_without_evidence_stays_unconfirmed():
    entries = [_mesh("library-044", "LP -> HP", 88), _mesh("library-087", "LP -> HP", 88)]
    chosen = fc.select_sources(entries)
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "unconfirmed"
    assert chosen["vpm_identity"] is None
    assert "unverified" in chosen["merged"][0]["reason"]
    assert "no fingerprint" not in chosen["merged"][0]["reason"]


def test_triangle_counts_do_not_decide_identity():
    entries = [_mesh("npm", "LP", 12), _mesh("vpm", "HP", 80)]
    box = _box_points()
    unverified = fc.select_sources(entries)
    assert unverified["vpm_status"] == "available"
    assert unverified["vpm_identity"] == "unverified"
    cloned = fc.select_sources(entries, _identity_for({"npm": _box_faces(), "vpm": _box_faces()}))
    assert cloned["VPM"] is None
    assert "verified same geometry" in cloned["merged"][0]["reason"]
    distinct = fc.select_sources(entries, _identity_for({
        "npm": _box_faces(),
        "vpm": _faces_on(_other_eight()),
    }))
    assert distinct["VPM"]["entry_id"] == "vpm"
    assert distinct["vpm_identity"] == "verified_distinct"
    assert distinct["NPM"]["triangles"] == 12
    assert distinct["VPM"]["triangles"] == 80


def test_float32_noise_stays_inside_the_hausdorff_tolerance():
    box = _box_points()
    offset = (100.0, -40.0, 15.0)
    copied = _float32_cloud(box, offset)
    assert fc.compare_clouds(box, copied)["relation"] == "same"
    scaled = _float32_cloud(box, offset, scale=0.799)
    assert fc.compare_clouds(box, scaled)["relation"] == "scaled_copy"
    moved = [list(point) for point in box]
    moved[3][2] += 1e-3
    assert fc.compare_clouds(box, moved)["relation"] == "distinct"


def test_seeded_clouds_match_the_constructed_relation_and_ignore_triangle_counts():
    """Synthetic clouds and meshes. Not a real planting schedule."""
    rng = random.Random(216)
    profiles = (["LP"], ["HP"], ["LP -> HP"], [])
    scenes = ("FLORA_Union_v1.max", "FLORIO_2BT_2022.max")
    factors = (0.5, 0.799, 1.7, 2.2)
    for case in range(300):
        cloud = [list(point) for point in _BASE_CLOUD]
        for _extra in range(rng.randint(0, 3)):
            cloud.append([rng.uniform(0.0, 1.2), rng.uniform(0.0, 1.4), rng.uniform(0.0, 2.2)])
        kind = rng.choice(("translate", "scale", "perturb", "count"))
        if kind == "translate":
            other = _translate(cloud, (rng.uniform(-80.0, 80.0), rng.uniform(-80.0, 80.0), rng.uniform(-20.0, 20.0)))
            expected = "same"
        elif kind == "scale":
            other = _scale_then_translate(
                cloud,
                rng.choice(factors),
                (rng.uniform(-30.0, 30.0), rng.uniform(-30.0, 30.0), rng.uniform(-5.0, 5.0)),
            )
            expected = "scaled_copy"
        elif kind == "perturb":
            other = [list(point) for point in cloud]
            other[rng.randrange(len(other))][rng.randrange(3)] += rng.choice((-1.0, 1.0)) * rng.uniform(0.35, 0.8)
            expected = "distinct"
        else:
            other = [list(point) for point in cloud]
            other.append([9.0, -4.0, 3.0])
            expected = "distinct"
        assert fc.compare_clouds(cloud, other)["relation"] == expected
        width = rng.randint(2, 4)
        entries = []
        for index in range(width):
            entry = _mesh(f"c{case}-{index}", "LP", rng.randint(1, 5000))
            entry["profile_raw"] = list(rng.choice(profiles))
            entry["hidden"] = rng.choice((False, True))
            entry["scene"] = rng.choice(scenes)
            entries.append(entry)
        if not any(fc._npm_basis(entry) is not None for entry in entries):
            entries[0]["profile_raw"] = ["LP"]
        before = fc.select_sources(entries)
        npm_id = before["NPM"]["entry_id"]
        npm_triangles = next(entry["triangles"] for entry in entries if entry["id"] == npm_id)
        shifted = deepcopy(entries)
        for entry in shifted:
            if entry["profile_raw"] == ["HP"]:
                entry["triangles"] = entry["triangles"] + 1
        assert _signature(fc.select_sources(shifted)) == _signature(before)
        npm_rows = [entry for entry in entries if entry["profile_raw"] != ["HP"]]
        for hp in [entry for entry in entries if entry["profile_raw"] == ["HP"]]:
            signatures = []
            for triangles in (hp["triangles"], npm_triangles, npm_triangles + 997):
                trial = deepcopy(npm_rows + [hp])
                trial[-1]["triangles"] = triangles
                signatures.append(_signature(fc.select_sources(trial)))
            assert signatures[0] == signatures[1] == signatures[2]


def test_id_lifecycle_with_an_equal_count_distinct_pair():
    """Synthetic species. Material IDs stay put, and a 12/12 distinct LP+HP pair stays available."""
    for kind in _FLORA_KINDS:
        test_material_id_is_not_reissued_across_generations(kind)
    entries = _equal_count_pair()
    clouds = {"synthetic-star": _star_plane_faces(), "synthetic-shell": _faces_on(_other_eight())}
    identity = _identity_for(clouds)
    catalogue = _catalogue_for(entries, identity)
    assert catalogue["species"][0]["vpm_status"] == "available"
    assert catalogue["species"][0]["vpm"]["entry_id"] == "synthetic-shell"
    assert catalogue["species"][0]["vpm_identity"] == "verified_distinct"
    assert catalogue["species"][0]["npm"]["triangles"] == catalogue["species"][0]["vpm"]["triangles"]
    material_id = catalogue["species"][0]["material_id"]
    again = fc.build(
        {"scenes": [{"source": {"scene": entries[0]["scene"]}, "entries": entries}]},
        {
            "species": [{
                "latin": "Synthetic witness",
                "russian": "synthetic",
                "type": "bush",
                "sources": [entry["id"] for entry in entries],
                "geometry_basis": "own_mesh",
                "note": "synthetic",
            }],
            "unresolved": [],
        },
        {},
        catalogue,
        identity,
    )
    assert again["species"][0]["material_id"] == material_id
    assert again["species"][0]["vpm_status"] == "available"
    assert again["species"][0]["vpm_identity"] == "verified_distinct"
    assert fc.check(again) == []


def test_geometry_identity_file_classifies_scaled_copies_and_translations():
    path = ROOT / "library" / "flora" / "geometry-identity.json"
    if not path.exists():
        pytest.skip(
            "library/flora/geometry-identity.json is not in the repo yet; "
            "the driver adds it after the Max vertex probe"
        )
    identity = fc.load_identity(json.loads(path.read_text(encoding="utf-8")))
    scaled = (
        ("Hydrangea arborescens 'Bounty'", "library-044", "library-087"),
        ("Hydrangea paniculata 'Limelight'", "library-045", "library-088"),
        ("Sorbaria sorbifolia 'Sem'", "library-052", "library-090"),
    )
    for latin, left, right in scaled:
        assert identity[frozenset((left, right))] == "scaled_copy"
        chosen = fc.select_sources(_sources(latin), identity)
        assert chosen["VPM"] is None
        assert chosen["vpm_status"] == "unconfirmed"
    assert identity[frozenset(("library-075", "library-076"))] == "same"
    assert fc.check(_load("library/flora/catalogue.json")) == []


def test_checker_vpm_evidence_rules():
    catalogue = _catalogue_for(_equal_count_pair())
    item = catalogue["species"][0]
    del item["vpm_evidence"]
    assert "vpm_evidence" in _text(fc.check(catalogue))
    catalogue = _catalogue_for(_equal_count_pair())
    item = catalogue["species"][0]
    item["vpm_identity"] = "verified_distinct"
    assert item["vpm_evidence"]["relation"] == "unknown"
    assert "verified_distinct requires vpm_evidence.relation distinct" in _text(fc.check(catalogue))
    catalogue = _catalogue_for(_equal_count_pair())
    item = catalogue["species"][0]
    item["vpm_evidence"] = {"relation": "same", "translation_dev_m": 0.0, "scaled_dev_rel": None}
    assert "same" in _text(fc.check(catalogue))
    catalogue = _catalogue_for(_equal_count_pair())
    item = catalogue["species"][0]
    item["vpm_evidence"] = {"relation": "scaled_copy", "translation_dev_m": None, "scaled_dev_rel": 0.0}
    assert "scaled_copy" in _text(fc.check(catalogue))
    entries = _equal_count_pair()
    evidenced = _catalogue_for(entries, _identity_for({
        "synthetic-star": _star_plane_faces(),
        "synthetic-shell": _faces_on(_other_eight()),
    }))
    assert evidenced["species"][0]["npm"]["triangles"] == evidenced["species"][0]["vpm"]["triangles"] == 12
    assert evidenced["species"][0]["vpm_evidence"]["relation"] == "distinct"
    assert fc.check(evidenced) == []


def test_build_identity_skips_stand_ins_and_deduplicates_pairs():
    points = {
        "library-a": _box_faces(),
        "library-b": _translate_faces(_box_faces(), (1.0, 2.0, 3.0)),
        "library-gap": [[0.0, 0.0, 0.0]],
    }
    curation = {
        "species": [
            {
                "latin": "Synthetic own",
                "sources": ["library-b", "library-a"],
                "geometry_basis": "own_mesh",
            },
            {
                "latin": "Synthetic own again",
                "sources": ["library-a", "library-b"],
                "geometry_basis": "own_mesh",
            },
            {
                "latin": "Synthetic gap",
                "sources": ["library-gap", "library-a"],
                "geometry_basis": "shared_multi_species_stand_in",
            },
        ]
    }
    document = fc.build_identity(points, curation)
    assert document["schema"] == "flora-geometry-identity-v3"
    assert document["tolerance"] == 1e-4
    assert set(document["entries"]) == {"library-a", "library-b"}
    assert document["pairs"] == [{
        "a": "library-a",
        "b": "library-b",
        "relation": "same",
        "translation_dev_m": 0.0,
        "scaled_dev_rel": None,
    }]
    with pytest.raises(ValueError, match="flora-geometry-identity-v3"):
        fc.load_identity({"schema": "flora-geometry-identity-v2", "entries": {}, "pairs": []})


def test_compare_clouds_is_fast_for_seven_thousand_points():
    points = [[(index % 100) * 0.05, (index // 100) * 0.05, (index % 13) * 0.03] for index in range(7000)]
    shifted = _translate(points, (100.0, -20.0, 3.0))
    assert fc.compare_clouds(points, shifted)["relation"] == "same"


def test_vertex_dump_script_has_no_fingerprint_copy():
    text = (ROOT / "tools" / "flora" / "dump_flora_source_vertices.py").read_text(encoding="utf-8")
    assert "Pattern: n/a | new-case: Flora source face dump for VPM identity evidence (#216)." in text
    assert "flora-faces entries=" in text
    assert "getFace" in text
    assert "fingerprint_points" not in text
    assert "mesh_sha256" not in text
    source = (ROOT / "src" / "dt_ai" / "materials" / "flora_catalogue.py").read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":\n    main()' in source


def test_identity_cli_refuses_failures_and_build_reads_pairs(tmp_path):
    entries = _equal_count_pair()
    audit = tmp_path / "audit.json"
    curation_path = tmp_path / "curation.json"
    maps = tmp_path / "maps.json"
    points_path = tmp_path / "points.json"
    identity_path = tmp_path / "geometry-identity.json"
    out = tmp_path / "catalogue.json"
    curation = {
        "species": [{
            "latin": "Synthetic witness",
            "russian": "synthetic",
            "type": "bush",
            "sources": ["synthetic-star", "synthetic-shell"],
            "geometry_basis": "own_mesh",
            "note": "synthetic",
        }],
        "unresolved": [],
    }
    audit.write_text(json.dumps({
        "scenes": [{"source": {"scene": "Synthetic.max"}, "entries": entries}],
    }), encoding="utf-8")
    curation_path.write_text(json.dumps(curation), encoding="utf-8")
    maps.write_text("{}", encoding="utf-8")
    dump = {
        "entries": {
            "synthetic-star": {"triangles": _star_plane_faces()},
            "synthetic-shell": {"triangles": _box_faces()},
        },
        "failures": [{"entry_id": "synthetic-star", "reason": "synthetic failure"}],
    }
    points_path.write_text(json.dumps(dump), encoding="utf-8")
    with pytest.raises(SystemExit):
        fc.main([
            "identity",
            "--points", str(points_path),
            "--curation", str(curation_path),
            "--out", str(identity_path),
        ])
    dump["failures"] = []
    points_path.write_text(json.dumps(dump), encoding="utf-8")
    fc.main([
        "identity",
        "--points", str(points_path),
        "--curation", str(curation_path),
        "--out", str(identity_path),
    ])
    fc.main([
        "build",
        "--audit", str(audit),
        "--curation", str(curation_path),
        "--maps", str(maps),
        "--identity", str(identity_path),
        "--out", str(out),
    ])
    catalogue = json.loads(out.read_text(encoding="utf-8"))
    assert catalogue["species"][0]["vpm_identity"] == "verified_distinct"
    assert catalogue["species"][0]["vpm_evidence"]["relation"] == "distinct"
    assert catalogue["species"][0]["vpm"]["entry_id"] == "synthetic-shell"


def _box_faces():
    """Closed 2 x 2 x 4 m shell, 12 triangles on the 8 box corners. Synthetic."""
    points = _box_points()
    quads = (
        (0, 2, 3, 1),
        (4, 5, 7, 6),
        (0, 1, 5, 4),
        (2, 6, 7, 3),
        (0, 4, 6, 2),
        (1, 3, 7, 5),
    )
    faces = []
    for a, b, c, d in quads:
        faces.append([points[a][:], points[b][:], points[c][:]])
        faces.append([points[a][:], points[c][:], points[d][:]])
    return faces


def _faces_on(points):
    """Same 12-triangle shell topology as _box_faces, on an 8-point list."""
    quads = (
        (0, 2, 3, 1),
        (4, 5, 7, 6),
        (0, 1, 5, 4),
        (2, 6, 7, 3),
        (0, 4, 6, 2),
        (1, 3, 7, 5),
    )
    faces = []
    for a, b, c, d in quads:
        faces.append([list(points[a]), list(points[b]), list(points[c])])
        faces.append([list(points[a]), list(points[c]), list(points[d])])
    return faces


def _crossed_star_faces():
    """Four triangles, two vertical diagonals, the same 8 corners as the shell. Synthetic."""
    points = _box_points()
    quads = ((0, 6, 7, 1), (4, 2, 3, 5))
    faces = []
    for a, b, c, d in quads:
        faces.append([points[a][:], points[b][:], points[c][:]])
        faces.append([points[a][:], points[c][:], points[d][:]])
    return faces


def _fresh_faces(faces):
    """Unwelded copy: each corner is its own vertex, the triangles are unchanged."""
    return [[[float(coord) for coord in corner] for corner in face] for face in faces]


def _translate_faces(faces, offset):
    return [
        [[corner[0] + offset[0], corner[1] + offset[1], corner[2] + offset[2]] for corner in face]
        for face in faces
    ]


def _scale_faces(faces, factor, offset=(0.0, 0.0, 0.0)):
    return _translate_faces(
        [[[corner[0] * factor, corner[1] * factor, corner[2] * factor] for corner in face] for face in faces],
        offset,
    )


def _face_curation(ids):
    return {
        "species": [{
            "latin": "Synthetic witness",
            "russian": "synthetic",
            "type": "bush",
            "sources": list(ids),
            "geometry_basis": "own_mesh",
            "note": "synthetic",
        }],
        "unresolved": [],
    }


def _star_plane_faces():
    """Six vertical quads inside the 2 x 2 x 4 m volume, 12 triangles. Synthetic."""
    faces = []
    for y in (0.0, 1.0, 2.0):
        quad = [[0.0, y, 0.0], [2.0, y, 0.0], [2.0, y, 4.0], [0.0, y, 4.0]]
        faces.append([quad[0][:], quad[1][:], quad[2][:]])
        faces.append([quad[0][:], quad[2][:], quad[3][:]])
    for x in (0.0, 1.0, 2.0):
        quad = [[x, 0.0, 0.0], [x, 2.0, 0.0], [x, 2.0, 4.0], [x, 0.0, 4.0]]
        faces.append([quad[0][:], quad[1][:], quad[2][:]])
        faces.append([quad[0][:], quad[2][:], quad[3][:]])
    return faces


def test_crossed_four_face_star_is_distinct_from_the_closed_shell():
    """Same 8 corners. Vertex Hausdorff says same; the surfaces are a 4-face star and a 12-face shell."""
    star = _crossed_star_faces()
    shell = _box_faces()
    assert len(star) == 4 and len(shell) == 12
    star_corners = [tuple(corner) for face in star for corner in face]
    assert {tuple(point) for point in _box_points()} == set(star_corners)
    assert fc.compare_clouds(_box_points(), list(set(star_corners)))["relation"] == "same"
    compared = fc.compare_surfaces(star, shell)
    assert compared["relation"] == "distinct"
    assert compared["relation"] != "same"
    identity = fc.load_identity(fc.build_identity(
        {"synthetic-star": star, "synthetic-shell": shell},
        _face_curation(("synthetic-star", "synthetic-shell")),
    ))
    entries = _equal_count_pair()
    entries[0]["triangles"] = 4
    entries[1]["triangles"] = 12
    chosen = fc.select_sources(entries, identity)
    assert chosen["VPM"]["entry_id"] == "synthetic-shell"
    assert chosen["vpm_identity"] == "verified_distinct"
    assert chosen["vpm_evidence"]["relation"] == "distinct"


def test_unwelded_four_face_star_is_the_same_surface():
    """Duplicate corners change the vertex count. The four triangles are the same surface."""
    welded = _crossed_star_faces()
    unwelded = _fresh_faces(welded)
    welded_cloud = list({tuple(corner) for face in welded for corner in face})
    unwelded_cloud = [corner[:] for face in unwelded for corner in face]
    assert len(welded_cloud) == 8 and len(unwelded_cloud) == 12
    assert fc.compare_clouds(welded_cloud, unwelded_cloud)["relation"] == "distinct"
    compared = fc.compare_surfaces(welded, unwelded)
    assert compared["relation"] == "same"
    assert compared["translation_dev_m"] <= 1e-4
    assert compared["scaled_dev_rel"] is None
    moved = _translate_faces(unwelded, (18.0, -4.0, 2.5))
    assert fc.compare_surfaces(welded, moved)["relation"] == "same"
    scaled = _scale_faces(unwelded, 0.799, (18.0, -4.0, 2.5))
    assert fc.compare_surfaces(welded, scaled)["relation"] == "scaled_copy"


def test_equal_triangle_count_surfaces_stay_distinct():
    """Prior counterexample: 12 vertical-plane triangles and 12 shell triangles are not one mesh."""
    planes = _star_plane_faces()
    shell = _box_faces()
    assert len(planes) == len(shell) == 12
    assert fc.compare_surfaces(planes, shell)["relation"] == "distinct"
    perturbed = _faces_on(_other_eight())
    assert len(perturbed) == 12
    assert fc.compare_surfaces(shell, perturbed)["relation"] == "distinct"
    identity = fc.load_identity(fc.build_identity(
        {"synthetic-star": planes, "synthetic-shell": perturbed},
        _face_curation(("synthetic-star", "synthetic-shell")),
    ))
    chosen = fc.select_sources(_equal_count_pair(), identity)
    assert chosen["vpm_identity"] == "verified_distinct"
    assert chosen["NPM"]["triangles"] == chosen["VPM"]["triangles"] == 12


def test_vertex_cloud_pair_is_not_classified_same_or_distinct():
    """A point list is not a surface. Identity must stay unknown."""
    clouds = {
        "synthetic-star": _box_points(),
        "synthetic-shell": _translate(_box_points(), (4.0, -2.0, 1.0)),
    }
    document = fc.build_identity(clouds, _face_curation(clouds))
    assert document["schema"] == "flora-geometry-identity-v3"
    assert document["pairs"][0]["relation"] == "unknown"
    assert document["pairs"][0]["translation_dev_m"] is None
    assert document["pairs"][0]["scaled_dev_rel"] is None
    identity = fc.load_identity(document)
    assert fc.geometry_relation({"id": "synthetic-star"}, {"id": "synthetic-shell"}, identity) == "unknown"


def test_ambiguous_pair_stays_unverified_and_vpm_unconfirmed():
    """No finite surface on one side is unknown. An LP -> HP candidate is not a VPM."""
    entries = [_mesh("library-044", "LP -> HP", 88), _mesh("library-087", "LP -> HP", 88)]
    document = fc.build_identity(
        {"library-044": [], "library-087": _box_faces()},
        _face_curation(("library-044", "library-087")),
    )
    assert document["pairs"][0]["relation"] == "unknown"
    identity = fc.load_identity(document)
    chosen = fc.select_sources(entries, identity)
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "unconfirmed"
    assert chosen["vpm_identity"] is None
    assert chosen["vpm_evidence"] is None
    assert "unverified" in chosen["merged"][0]["reason"]
    assert "verified same" not in chosen["merged"][0]["reason"]
    explicit = [_mesh("npm", "LP", 12), _mesh("vpm", "HP", 80)]
    explicit_identity = fc.load_identity(fc.build_identity(
        {"npm": [[[float("nan"), 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]], "vpm": _box_faces()},
        _face_curation(("npm", "vpm")),
    ))
    held = fc.select_sources(explicit, explicit_identity)
    assert held["vpm_status"] == "available"
    assert held["vpm_identity"] == "unverified"
    assert held["vpm_evidence"]["relation"] == "unknown"
    assert held["vpm_evidence"]["relation"] not in ("same", "distinct", "scaled_copy")


def test_surface_tolerance_and_scale_bounds():
    """<= 1e-4 m is same; <= 1e-4 relative after normalizing extent is scaled_copy."""
    base = [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]]
    on_limit = [[[0.0, 0.0, 1e-4], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]]
    past_limit = [[[0.0, 0.0, 2e-4], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]]
    assert fc.compare_surfaces(base, on_limit)["relation"] == "same"
    assert fc.compare_surfaces(base, on_limit)["translation_dev_m"] <= 1e-4
    assert fc.compare_surfaces(base, past_limit)["relation"] == "distinct"
    scaled = _scale_faces(_box_faces(), 0.799, (37.1, -5.2, 3.3))
    compared = fc.compare_surfaces(_box_faces(), scaled)
    assert compared["relation"] == "scaled_copy"
    assert compared["scaled_dev_rel"] <= 1e-4


def test_generated_surfaces_ignore_counts_and_unknown_never_claims_a_relation():
    """Synthetic meshes. Triangle count, vertex count and a missing surface never decide the relation."""
    rng = random.Random(216)
    factors = (0.5, 0.799, 1.7, 2.2)
    relations = []
    for case in range(40):
        faces = []
        for _triangle in range(rng.randint(1, 4)):
            faces.append([
                [rng.uniform(0.0, 1.2), rng.uniform(0.0, 1.4), rng.uniform(0.0, 2.2)]
                for _corner in range(3)
            ])
        offset = (rng.uniform(-80.0, 80.0), rng.uniform(-80.0, 80.0), rng.uniform(-20.0, 20.0))
        assert fc.compare_surfaces(faces, _translate_faces(faces, offset))["relation"] == "same"
        factor = rng.choice(factors)
        scaled = _scale_faces(faces, factor, offset)
        assert fc.compare_surfaces(faces, scaled)["relation"] == "scaled_copy"
        duplicated = faces + _fresh_faces(faces)
        assert len(duplicated) == 2 * len(faces)
        assert fc.compare_surfaces(faces, duplicated)["relation"] == "same"
        perturbed = _fresh_faces(faces)
        perturbed[0][0][rng.randrange(3)] += rng.choice((-1.0, 1.0)) * rng.uniform(0.35, 0.8)
        assert fc.compare_surfaces(faces, perturbed)["relation"] == "distinct"
        relations.append(fc.compare_surfaces(faces, duplicated)["relation"])
    assert relations == ["same"] * 40
    junk = (
        [],
        [[0.0, 0.0, 0.0]],
        [[[float("nan"), 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]],
        [[[float("inf"), 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]],
        _box_points(),
        [[[0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]],
    )
    claims = []
    for case in range(30):
        left = junk[case % len(junk)]
        right = _box_faces() if case % 2 else junk[(case * 3) % len(junk)]
        relation = fc.compare_surfaces(left, right)["relation"]
        claims.append(relation)
        assert relation == "unknown"
        assert relation not in ("same", "distinct", "scaled_copy")
    assert claims == ["unknown"] * 30


def test_face_distinct_pair_keeps_material_ids():
    """Synthetic species. A 12/12 distinct surface pair stays a VPM and does not move the material ID."""
    for kind in _FLORA_KINDS:
        test_material_id_is_not_reissued_across_generations(kind)
    entries = _equal_count_pair()
    identity = fc.load_identity(fc.build_identity(
        {"synthetic-star": _star_plane_faces(), "synthetic-shell": _faces_on(_other_eight())},
        _face_curation(("synthetic-star", "synthetic-shell")),
    ))
    catalogue = _catalogue_for(entries, identity)
    assert catalogue["species"][0]["vpm_status"] == "available"
    assert catalogue["species"][0]["vpm_identity"] == "verified_distinct"
    material_id = catalogue["species"][0]["material_id"]
    again = fc.build(
        {"scenes": [{"source": {"scene": entries[0]["scene"]}, "entries": entries}]},
        _face_curation(("synthetic-star", "synthetic-shell")),
        {},
        catalogue,
        identity,
    )
    assert again["species"][0]["material_id"] == material_id
    assert again["retired_ids"] == []
    assert fc.check(again) == []


def test_library_keeps_seventy_six_ids_and_scaled_copy_exclusions():
    """Bounty, Limelight and Sem stay scaled copies. 61 species + 15 stand-in gaps keep their IDs."""
    catalogue = _load("library/flora/catalogue.json")
    species_ids = [item["material_id"] for item in catalogue["species"]]
    gap_ids = [item["material_id"] for item in catalogue["gaps"]["project_species_shared_stand_in"]]
    assert len(species_ids) == 61
    assert len(gap_ids) == 15
    assert len(set(species_ids) | set(gap_ids)) == 76
    assert catalogue["retired_ids"] == []
    identity = fc.load_identity(_load("library/flora/geometry-identity.json"))
    for latin, left, right in (
        ("Hydrangea arborescens 'Bounty'", "library-044", "library-087"),
        ("Hydrangea paniculata 'Limelight'", "library-045", "library-088"),
        ("Sorbaria sorbifolia 'Sem'", "library-052", "library-090"),
    ):
        assert identity[frozenset((left, right))] == "scaled_copy"
        chosen = fc.select_sources(_sources(latin), identity)
        assert chosen["VPM"] is None
        assert chosen["vpm_status"] == "unconfirmed"
        assert chosen["vpm_identity"] is None
    assert identity[frozenset(("library-075", "library-076"))] == "same"
