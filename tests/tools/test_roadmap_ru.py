"""#2100: the Russian roadmap page renders from a fixture readiness JSON + a fixture GitHub snapshot."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import roadmap_ru as R  # noqa: E402

FX = ROOT / "tests/fixtures/roadmap_ru"
TODAY = "2026-11-28"


def _inputs():
    readiness = R.load_readiness(FX / "readiness")
    github = json.loads((FX / "github.json").read_text(encoding="utf-8"))
    plans = R.load_plans(FX / "plans")
    return readiness, github, plans


def _page() -> str:
    readiness, github, plans = _inputs()
    return R.render_page(readiness, github, plans, today=TODAY)


def test_newest_readiness_json_is_picked_by_name():
    assert R.load_readiness(FX / "readiness")["overall"] == 91.3


def test_header_says_generated_never_hand_edited():
    head = "\n".join(_page().splitlines()[:6])
    assert "создаётся автоматически" in head
    assert "не править вручную" in head.lower()
    assert "tools/roadmap_ru.py" in head


def test_sections_in_order():
    page = _page()
    titles = ["## Сделано за 7 дней", "## Идёт сейчас", "## Осталось до сдачи без Артёма",
              "## Ждёт Артёма", "## Отложено сознательно"]
    pos = [page.index(t) for t in titles]
    assert pos == sorted(pos)


def test_area_names_in_russian_with_scores():
    page = _page()
    for name, score in (("Флора", 78), ("МАФ", 83), ("UCX", 81), ("Ground", 88)):
        assert f"| {name} | {score} |" in page, name
    assert "91" in page.split("## Сделано")[0]


def test_done_last_7_days_grouped_by_area():
    done = _page().split("## Сделано за 7 дней")[1].split("## Идёт сейчас")[0]
    assert "#2086" in done and "#2061" in done and "#1985" in done and "#2072" in done
    assert "#1500" not in done  # merged 18 days before
    assert done.index("### Ground") < done.index("#2086")
    assert "### МАФ" in done and "### UCX" in done


def test_in_progress_lists_open_prs_and_active_plans():
    now = _page().split("## Идёт сейчас")[1].split("## Осталось")[0]
    assert "#2092" in now and "#2084" in now
    assert "Telegram findings" in now
    assert "Block MAF route" not in now  # done plan


def test_three_blockers_numbered_with_what_closes_each():
    left = _page().split("## Осталось до сдачи без Артёма")[1].split("## Ждёт Артёма")[0]
    for n in (1, 2, 3):
        assert f"\n{n}. " in left
    assert left.count("Что закроет:") == 3
    assert "Ground, UCX, МАФ, Флора" in left
    assert "#1972" in left


def test_waits_for_artem_numbered_with_recommendation():
    wait = _page().split("## Ждёт Артёма")[1].split("## Отложено")[0]
    assert "1. Sokolniki NPM" in wait
    assert "Рекомендация: нет" in wait
    assert "Рекомендация: snap в копии сдачи" in wait
    assert "#1509" in wait  # waits-artem issue


def test_parked_with_reason():
    parked = _page().split("## Отложено сознательно")[1]
    assert "#1948" in parked and "ждёт #1944" in parked
    assert "Max is busy" in parked
    assert "AGR Tools 2.0" in parked and "frozen by D393" in parked
    assert "#2094" not in parked


def test_telegram_digest_is_at_most_25_lines():
    readiness, github, plans = _inputs()
    github = dict(github, open_issues=github["open_issues"] + [
        {"number": 3000 + i, "title": f"t{i}", "labels": [{"name": "waits-artem"}], "body": ""} for i in range(40)])
    readiness = dict(readiness, questions_for_user=readiness["questions_for_user"] * 10)
    text = R.render_telegram(readiness, github, plans, today=TODAY)
    lines = text.splitlines()
    assert 5 <= len(lines) <= 25
    assert "91" in lines[0]
    assert any("Флора 78" in line for line in lines)


@pytest.mark.parametrize("title, area", [
    ("Package validator: check named Ground work FBX and align archive address parsing (#1919)", "Ground"),
    ("UCX: diff + adopt from Codex skill pack (OKS/Ground collision builders)", "UCX"),
    ("Preserve verified Ground FBX placement through UCX and binding (#1922)", "Ground"),
    ("MAF from PDF + library NPM status after Artem's session", "МАФ"),
    ("chore: regenerate .ignore after merge batch 20261128b2070", "Служебное"),
    ("fix: red main 1c2f297b (ETALONS dated decision)", "Служебное"),
    ("research(#155): keyplan-arrow view->face reader", "Исследования"),
    ("Sokolniki NPM package v002: snap the 0.9 mm body seams", "Здание целиком"),
])
def test_titles_map_to_areas(title, area):
    assert R.area_name(R.classify(title)) == area


def test_service_prs_are_counted_not_listed():
    readiness, github, plans = _inputs()
    github = dict(github, merged_prs=github["merged_prs"] + [
        {"number": 2096, "title": "chore: regenerate .ignore after merge batch x", "mergedAt": "2026-11-28T09:00:00Z"}])
    done = R.render_page(readiness, github, plans, today=TODAY).split("## Сделано")[1].split("## Идёт")[0]
    assert "### Служебное — 1" in done and "#2096" not in done


def test_gh_wrapper_is_read_only():
    with pytest.raises(PermissionError):
        R.gh_json("pr", "merge", "1")
    with pytest.raises(PermissionError):
        R.gh_json("issue", "edit", "1")


def test_cli_writes_page_from_fixtures(tmp_path, capsys):
    out = tmp_path / "ROADMAP.ru.md"
    rc = R.main(["--readiness", str(FX / "readiness"), "--github-json", str(FX / "github.json"),
                 "--plans", str(FX / "plans"), "--today", TODAY, "--out", str(out)])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == _page()
    rc = R.main(["--readiness", str(FX / "readiness"), "--github-json", str(FX / "github.json"),
                 "--plans", str(FX / "plans"), "--today", TODAY, "--telegram"])
    assert rc == 0
    assert len(capsys.readouterr().out.strip().splitlines()) <= 25
