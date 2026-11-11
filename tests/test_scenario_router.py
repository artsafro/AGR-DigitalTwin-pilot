"""Scenario router (tools/hooks/scenario_router.py) and its table docs/scenarios/scenarios.json."""
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TABLE = json.loads((ROOT / "docs/scenarios/scenarios.json").read_text(encoding="utf-8"))
PROMPT_HOOKS = ROOT / "tools/hooks/prompt_hooks.py"


def _router():
    spec = importlib.util.spec_from_file_location("scenario_router", ROOT / "tools/hooks/scenario_router.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


router = _router()


@pytest.mark.parametrize("prompt, cells, ask", [
    ("делаем ВПМ ОКС по Элеваторной", ["oks-vpm"], None),
    ("моделирую НПМ ОКС, средняя сложность", ["oks-npm"], None),
    ("НПМ: флора и МАФ по СПОЗУ", ["ground-npm"], None),
    ("НПМ упрощённый, благоустройство", ["ground-npm"], None),
    ("НПМ упрощённый для здания", ["oks-npm-lite"], None),
    ("Ground VPM для Ватутинок", ["ground-vpm"], None),
    ("сделай UCX для ОКС", ["oks-vpm"], None),
    ("ВПМ: ОКС и благоустройство", ["oks-vpm", "ground-vpm"], None),
    ("работаю с Ground", [], router.PROFILE_ASK),
    ("моделирую НПМ", [], router.OBJECT_ASK),
    ("нужны коллизии", [], router.UCX_ASK),
    ("посмотри PR и слей", [], None),
    ("npm install left-pad", [], None),
    ("http ссылка на lp файл", [], None),
])
def test_route(prompt, cells, ask):
    result = router.route(prompt, TABLE)
    assert result["cells"] == cells
    assert result["ask"] == ask


@pytest.mark.parametrize("relative", [
    "docs/procedure/TASK_TO_MODEL.md",
    ".agents/skills/scenario/SKILL.md",
    ".claude/skills/scenario/SKILL.md",
])
def test_model_entry_sequence(relative):
    text = (ROOT / relative).read_text(encoding="utf-8")
    # One explicit sequence from either entry, not an independently inferred order.
    sequence = "`docs/scenarios/<cell>.md` -> `jobs/<ID>/TASK.md` / contract questions -> `jobs/<ID>/job.yaml` gates"
    assert sequence in text
    if relative.startswith("docs/"):
        assert ".agents/skills/scenario/SKILL.md#step-3" in text
    else:
        handover = text.split("## Step 4", 1)[0].split("## Step 3", 1)[1]
        assert "TASK_TO_MODEL.md#gates" in handover
        assert "eight gates" in handover
    assert "docs/procedure/TASK_TO_MODEL.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert (ROOT / ".agents/skills/scenario/SKILL.md").read_bytes() == (
        ROOT / ".claude/skills/scenario/SKILL.md").read_bytes()


def test_oks_vpm_route_policy():
    cell = (ROOT / "docs/scenarios/oks-vpm.md").read_text(encoding="utf-8")
    route = cell.split("## Route by stage", 1)[1].split("## Etalons", 1)[0]
    for required in ("standard", "AGR Tools stages 1–4", "body", "windows", "roof",
                     "after Gate 1", "Max is busy", "dt_ai.ops", "R14", "path: deviation",
                     "all eight gates", "[D249]"):
        assert required in route, required
    procedure = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    operations = next(line for line in procedure.splitlines() if line.startswith("| operations |"))
    assert "oks-vpm.md#route-by-stage" in operations
    assert "cell's standard route" in operations
    decision = next(line for line in (ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines()
                    if line.startswith("| D249 |"))
    assert "2026-11-11" in decision and "path: deviation" in decision


def test_real_building_cold_run_pointer():
    text = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    assert "No real-building run is required." not in text
    assert "../../jobs/KPP1/cold-run-1172/RUN-LOG.md" in text


@pytest.mark.parametrize("relative", [
    "docs/procedure/TASK_TO_MODEL.md", ".agents/skills/scenario/SKILL.md",
    ".claude/skills/scenario/SKILL.md",
])
def test_model_entry_links(relative):
    source = ROOT / relative
    for target in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
        path, _, anchor = target.partition("#")
        destination = (source.parent / path).resolve() if path else source
        assert destination.exists(), f"{relative}: {target}"
        if anchor:
            headings = re.findall(r"^#+ (.+)$", destination.read_text(encoding="utf-8"), re.M)
            slugs = {re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-") for heading in headings}
            assert anchor in slugs, f"{relative}: missing anchor {target}"


def test_table_points_at_real_files():
    ids = [c["id"] for c in TABLE["cells"]]
    assert len(ids) == len(set(ids))
    for cell in TABLE["cells"]:
        assert cell["status"] in ("ready", "todo"), cell["id"]
        if cell["status"] == "ready":
            assert (ROOT / cell["card"]).is_file(), cell["card"]
        for path in cell.get("reads", []):
            assert (ROOT / path).exists(), path
    for kind in TABLE["object_cell"].values():
        assert kind is None or any(c.startswith(kind + "-") for c in ids)


@pytest.mark.parametrize("card", sorted((ROOT / "docs/scenarios").glob("*.md")))
def test_card_links_and_decisions_exist(card):
    text = card.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text):
        assert (card.parent / target).resolve().exists(), f"{card.name}: {target}"
    for path in re.findall(r"`((?:jobs|tools|src|library|docs|\.agents)/[^`*<> ]+)`", text):
        assert (ROOT / path).exists(), f"{card.name}: {path}"
    known = set(re.findall(r"^\| (D\d+) ", (ROOT / "docs/decisions.md").read_text(encoding="utf-8"), re.M))
    for decision in set(re.findall(r"\[(D\d+)\]", text)):
        assert decision in known, f"{card.name}: unknown {decision}"


def test_cell_announced_once_per_session_and_question_repeats(tmp_path):
    transcript = tmp_path / "s.jsonl"
    transcript.write_text("", encoding="utf-8")
    payload = {"session_id": "s1", "transcript_path": str(transcript), "prompt": "ВПМ ОКС"}
    first = router.check(payload)
    assert "oks-vpm" in first["hookSpecificOutput"]["additionalContext"]
    assert router.check(payload) == {}
    assert router.check(payload | {"session_id": "s2"}) != {}
    ask = payload | {"prompt": "моделирую НПМ"}
    assert router.check(ask) and router.check(ask)


def test_slash_command_is_ignored():
    assert router.check({"prompt": "/handover ВПМ ОКС"}) == {}


@pytest.mark.parametrize("prompt", [
    "<pasted_content id=\"x\">ВПМ ОКС</pasted_content>",
    "Отчёт доски: ВПМ ОКС. " + "Задача заведена, ждёт ответа. " * 60,
    "Статус: НПМ и ВПМ, ОКС и Ground, флора и МАФ — всё по плану",
])
def test_pasted_reports_stay_silent(prompt):
    assert router.check({"prompt": prompt}) == {}


def test_two_cells_still_route():
    out = router.check({"prompt": "ВПМ: ОКС и благоустройство"})
    assert "oks-vpm" in out["hookSpecificOutput"]["additionalContext"]


def test_prompt_dispatcher_carries_the_scenario(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_")}
    env |= {"AGR_USAGE_LOG": str(tmp_path / "u.jsonl"), "CLAUDE_PROJECT_DIR": str(ROOT)}
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "НПМ флора по СПОЗУ"}
    result = subprocess.run([sys.executable, str(PROMPT_HOOKS)], input=json.dumps(payload), capture_output=True,
                            text=True, encoding="utf-8", env=env, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "ground-npm" in context and "docs/scenarios/ground-npm.md" in context
