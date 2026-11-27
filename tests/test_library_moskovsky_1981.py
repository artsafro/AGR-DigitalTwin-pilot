"""#1981: Moskovsky school 1200 MAFs are library drafts, searchable by vendor article [D421]."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = "moskovsky-sosh1200-maf-v002"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ii = _load("intake_identify_1981", "tools/assets/intake_identify.py")
pub = _load("library_publish_1981", "tools/library/publish.py")
CAT = pub.load_catalogue(ROOT / "library/published/catalogue.json")
UNIFIED = json.loads((ROOT / "library/assets/maf_unified.json").read_text(encoding="utf-8"))
RECS = [r for r in CAT["records"] if r["origin"]["batch"] == BATCH]


def test_batch_is_28_drafts_none_accepted():
    assert len(RECS) == 28
    assert {r["status"] for r in RECS} == {"draft"}
    assert all(r["accepted"] is None for r in RECS)
    assert {r["origin"]["issue"] for r in RECS} == {"1743"}


def test_every_record_has_vpm_npm_max_and_preview():
    for r in RECS:
        roles = {f["role"] for f in r["files"]}
        assert {"vpm", "npm", "max", "preview"} <= roles, r["name"]


def test_vendor_articles_except_individual_fences():
    no_art = sorted(r["name"] for r in RECS if not r["card"]["article"])
    assert len(no_art) == 6 and all(n.startswith("AGR_maf_") for n in no_art)


def test_search_by_article_returns_the_draft():
    by_art, _, _ = ii.maf_library(UNIFIED)
    for art, name in [("7W2002", "Robinzon_DoskaDlyaRisovaniya_7W2002"),
                      ("10027-1", "Adanat_SkameykaSkarletSPodlokotnikami_10027-1"),
                      ("VST9614-4", "GKVysota_Pergola_VST9614-4"),
                      ("ВСТ 9614/4", "GKVysota_Pergola_VST9614-4")]:
        hits = [h for h in by_art.get(ii.lib._article_key(art), []) if h.get("source") == "published"]
        assert [(h["name"], h["status"]) for h in hits] == [(name, "draft")], art
    names = {r["name"] for r in pub.available(CAT, kind="maf")}
    assert {r["name"] for r in RECS} <= names
