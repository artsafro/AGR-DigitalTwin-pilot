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


def test_prompt_dispatcher_carries_the_scenario(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_")}
    env |= {"AGR_USAGE_LOG": str(tmp_path / "u.jsonl"), "CLAUDE_PROJECT_DIR": str(ROOT)}
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "НПМ флора по СПОЗУ"}
    result = subprocess.run([sys.executable, str(PROMPT_HOOKS)], input=json.dumps(payload), capture_output=True,
                            text=True, encoding="utf-8", env=env, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "ground-npm" in context and "docs/scenarios/ground-npm.md" in context
