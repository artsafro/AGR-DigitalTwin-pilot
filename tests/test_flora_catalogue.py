"""Flora library catalogue: source selection, stable material IDs, and schema check.

The random probe builds synthetic species, meshes and catalogues. Those records are
not a real planting schedule, library scene or approved texture.
"""
import importlib.util
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
    assert betula["NPM"]["basis"] == "LP -> HP"
    assert betula["VPM"] is None
    assert betula["vpm_status"] == "unconfirmed"


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


def test_committed_catalogue_has_no_findings_and_matches_rebuild():
    catalogue = _load("library/flora/catalogue.json")
    assert fc.check(catalogue) == []
    assert _build_real(previous=catalogue) == catalogue


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


def test_distinct_lp_hp_vpm_stays_available():
    chosen = fc.select_sources([_mesh("npm", "LP", 8), _mesh("vpm", "LP -> HP", 80)])
    assert chosen["NPM"]["entry_id"] == "npm"
    assert chosen["VPM"]["entry_id"] == "vpm"
    assert chosen["VPM"]["basis"] == "LP -> HP"
    assert chosen["vpm_status"] == "available"


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
    assert "same mesh" in merged["reason"]


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


def test_explicit_hp_with_the_npm_triangle_count_is_not_a_vpm():
    """Synthetic LP and HP rows that share a triangle count are one mesh."""
    chosen = fc.select_sources([_mesh("npm", "LP", 12), _mesh("copy", "HP", 12)])
    assert chosen["VPM"] is None
    assert chosen["vpm_status"] == "none"


def test_explicit_hp_with_a_different_triangle_count_is_a_vpm():
    """Synthetic control: a different triangle count is distinct VPM geometry."""
    chosen = fc.select_sources([_mesh("npm", "LP", 12), _mesh("vpm", "HP", 80)])
    assert chosen["VPM"]["entry_id"] == "vpm"
    assert chosen["vpm_status"] == "available"


@pytest.mark.parametrize(
    ("latin", "npm_id", "vpm_id"),
    [
        ("Tilia cordata", "library-028", "library-001"),
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
