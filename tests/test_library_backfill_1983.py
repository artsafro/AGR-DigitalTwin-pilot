"""new-case: tests for #1983: MAF sets other sessions split into NPM/VPM are library drafts, searchable by article [D421]."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCHES = {"backfill-staropetrovskiy-maf-v001": 51, "backfill-vatutino-maf-v001": 22, "backfill-vlad-mafs-b2-v001": 5,
           "backfill-buhv12-maf-v001": 11, "backfill-two-mafs-v001": 2, "backfill-sport-floodlight-v001": 1,
           "backfill-kg1536-bench-v001": 1}


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ii = _load("intake_identify_1983", "tools/assets/intake_identify.py")
pub = _load("library_publish_1983", "tools/library/publish.py")
CAT = pub.load_catalogue(ROOT / "library/published/catalogue.json")
UNIFIED = json.loads((ROOT / "library/assets/maf_unified.json").read_text(encoding="utf-8"))
RECS = [r for r in CAT["records"] if r["origin"]["batch"] in BATCHES]


def test_every_backfill_batch_is_drafts_none_accepted():
    counts = {b: sum(r["origin"]["batch"] == b for r in RECS) for b in BATCHES}
    assert counts == BATCHES
    assert {r["status"] for r in RECS} == {"draft"}
    assert all(r["accepted"] is None for r in RECS)
    assert {r["origin"]["issue"] for r in RECS} == {"1743"}


def test_every_record_has_a_profile_fbx_and_preview():
    for r in RECS:
        roles = {f["role"] for f in r["files"]}
        assert roles & {"vpm", "npm", "archive"}, r["name"]
        assert r["preview"], r["name"]


def test_search_by_three_articles_per_batch_returns_the_draft():
    by_art, _, _ = ii.maf_library(UNIFIED)
    for art, name in [("TID180B", "Mafmarket_SkamyaTiide_TID180B"),
                      ("ЛГДП-59", "Millenium_KresloVraschayuscheesyaFiligran_LGDP-59"),
                      ("РП 008", "Aira_ReshetkaPristvolnayaKorten_RP008"),
                      ("14122", "AGR_maf_SkameykaStalnayaAndromeda_001"),
                      ("ДП 090", "AGR_maf_DetskayaPloschadka_001"),
                      ("4-060", "AGR_maf_TennisnyyStolPremium_001"),
                      ("19121", "Adanat_KachalkaNaPruzhineBozhyaKorovka_19121"),
                      ("PR014", "Aira_NavesParkovyyConfig_PR014"),
                      ("LGK-11.21", "Millenium_KaruselGnezdo_LGK-11.21"),
                      ("VP043", "Aira_VeloparkovkaVelobox_VP043"),
                      ("SPE100", "Mafmarket_BasketbolnyySchitSKoltsom_SPE100"),
                      ("SG-1550", "SportivnyeGoroda_StoykiVoleybolnyeTeleskopicheskieTonus_SG-1550"),
                      ("MG4013", "Millenium_IgrovoyKompleks_MG4013"),
                      ("171620", "Mesto_PesochnayaFabrika_171620"),
                      ("1536", "KrasivyyGorod_SkamyaParkovaya_1536")]:
        hits = [h for h in by_art.get(ii.lib._article_key(art), []) if h.get("source") == "published"]
        assert [(h["name"], h["status"]) for h in hits] == [(name, "draft")], art
    names = {r["name"] for r in pub.available(CAT, kind="maf")}
    assert {r["name"] for r in RECS} <= names
    indexed = {r["name"]: r.get("status") for r in UNIFIED["records"] if r.get("source") == "published"}
    assert all(indexed.get(r["name"]) == "draft" for r in RECS)


def test_same_maf_twice_is_one_entry():
    """Verona rows 9 and 10 are one DWG block (19865C) with the same geometry: only row 9 is registered."""
    objs = {r["origin"]["object"] for r in RECS if r["origin"]["batch"] == "backfill-vatutino-maf-v001"}
    assert "VAT_MAF_T3508_09" in objs and "VAT_MAF_T3508_10" not in objs
