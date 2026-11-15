"""new-case: #1425 generated short-route and owner/migration view contracts."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/architecture"))
import route_map  # noqa: E402


def test_two_views_for_every_route():
    routes, _, files = route_map.render_all(ROOT)
    for name in routes:
        stem = route_map.OUTPUTS[name]
        scheme = stem.with_name(stem.name + "-scheme")
        table = stem.with_name(stem.name + "-owners.md")
        assert scheme.with_suffix(".svg") in files
        doc = json.loads(files[scheme.with_suffix(".excalidraw")])
        texts = "\n".join(e.get("text", "") for e in doc["elements"])
        assert "Редакция" in texts and "Ревизия исходников" in texts
        assert "Владелец экспорта" in texts
        assert "export_core.py" in texts
        assert not re.search(r"\.py:[0-9]|\.py::", texts)
        assert "Живых обходов" in texts
        assert table in files
        assert "Критерий завершения миграции" in files[table]
        assert "Причина различий" in files[table]
        assert "Живые обходы" in files[table]
