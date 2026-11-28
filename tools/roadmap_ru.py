"""Russian roadmap page for Artem (#2100): done / in progress / left / waits for Artem / parked.

new-case: tools/roadmap_ru.py - generated Russian status page (no existing pattern).

One owner: `docs/ROADMAP.ru.md` is produced by this script only and is never edited by hand.
Inputs: (a) the newest readiness JSON (`~/hermes_kanban/kpi/readiness/*.json`, newest by file name),
(b) open issues / PRs and PRs merged in the last 7 days of the pilot repo (gh, READ-ONLY: only
`gh pr list` / `gh issue list` are allowed), (c) the `Status:` line of `docs/plans/*.md`.

    uv run python tools/roadmap_ru.py                    # writes docs/ROADMAP.ru.md
    uv run python tools/roadmap_ru.py --telegram         # prints a <= 25-line digest
    uv run python tools/roadmap_ru.py --github-json snap.json --readiness DIR --today 2026-11-28 --out X.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "artsafro/AGR-DigitalTwin-pilot"
DEFAULT_OUT = ROOT / "docs" / "ROADMAP.ru.md"
DEFAULT_PLANS = ROOT / "docs" / "plans"
TELEGRAM_MAX_LINES = 25
DONE_DAYS = 7
PER_AREA = 6

# Readiness rubric areas (hermes_kanban/docs/readiness_rubric.md), names and "done" in plain Russian.
AREAS = {
    "1": ("Вход и правила", "новый агент за 10 тысяч токенов находит нужные решения и правила"),
    "2": ("Порядок «задача → модель»", "один порядок работы от исходников до отчёта, проверенный на новом агенте"),
    "3": ("Операции ядра", "операции над геометрией работают на новом здании с проверками до и после"),
    "4": ("Самопроверки", "автоматические проверки модели ловят ошибки и не пропускают брак"),
    "5": ("Ground", "рельеф участка собран из исходников, текстуры привязаны и проверены после экспорта"),
    "6": ("UCX", "коллизии односторонние, в бюджете и проверены на выгруженной сцене"),
    "7": ("МАФ", "МАФ выбраны из принятой библиотеки и расставлены по точкам"),
    "8": ("Флора", "растения из библиотеки расставлены, прозрачность и бюджет NPM проверены"),
    "9": ("Доступ к файлам", "внешний агент скачивает всё нужное по манифестам без нас"),
    "10": ("Визуальная проверка", "каждый результат приходит Артёму на просмотр, решение записывается"),
    "11": ("Здание целиком", "реальное здание прошло весь путь до пакета сдачи"),
}
OTHER = "Прочее"
RESEARCH, SERVICE = "90", "91"
GROUPS = {RESEARCH: "Исследования", SERVICE: "Служебное"}
SERVICE_NOTE = "порядок в репозитории и исправления упавших проверок, по одному не перечисляем"

# Title -> group. Service / research first, then a domain word (5-8) in the prefix before ':',
# then the first area whose keywords occur in the whole title.
_SERVICE = re.compile(r"^(chore|improve:\s*red main|hygiene|test\(hygiene\))|red main|regenerate \.ignore", re.I)
_RESEARCH = re.compile(r"^research\b", re.I)
_KEYWORDS = [
    ("8", r"flora|флор|tree|plant|растен|дерев"),
    ("7", r"maf|маф|groundel|bench|скамей"),
    ("5", r"ground|udim|skirt|relief|рельеф|terrain"),
    ("6", r"ucx|collision|коллиз"),
    ("11", r"sokolniki|сокольник|oks|окс|building|здани|body|facade|фасад|roof|window|door|opening|"
           r"vpm|npm|kpp1|elv|lattice|revit|smoothing|package|g22|poly63"),
    ("3", r"view.?->.?face|view-face|dt_ai|kernel|ядр|operation|h1\d\d"),
    ("4", r"xview|invariant|validator|sintez|readback|проверк|check"),
    ("10", r"review|visual|просмотр"),
    ("9", r"drive|asset|manifest|evidence|ассет|library"),
    ("2", r"trainer|eval|procedure|route|trail|cold|skeleton|маршрут|prompt"),
    ("1", r"agents\.md|rule|decision|правил|решени|docs?\b|ignore|state|skill|coordination|merge|search"),
]
_KW = [(a, re.compile(rf"(?<![a-zа-я])(?:{p})", re.I)) for a, p in _KEYWORDS]
_DOMAIN = {"5", "6", "7", "8"}


def area_name(aid: str, readiness: dict | None = None) -> str:
    if aid in AREAS:
        given = ((readiness or {}).get("areas", {}).get(aid) or {}).get("name", "")
        return given if re.search(r"[А-Яа-яЁё]", given or "") else AREAS[aid][0]
    return GROUPS.get(aid, OTHER)


def classify(title: str) -> str:
    if _SERVICE.search(title):
        return SERVICE
    if _RESEARCH.search(title):
        return RESEARCH
    head = title.split(":", 1)[0] if ":" in title else ""
    for aid, rx in _KW:
        if aid in _DOMAIN and head and rx.search(head):
            return aid
    for aid, rx in _KW:
        if rx.search(title):
            return aid
    return "0"


def gh_json(*args: str):
    """Read-only gh call: only `pr list` and `issue list` are allowed."""
    if len(args) < 2 or (args[0], args[1]) not in {("pr", "list"), ("issue", "list")}:
        raise PermissionError(f"roadmap_ru is read-only; refused: gh {' '.join(args[:2])}")
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout or "[]")


def fetch_github(repo: str, today: _dt.date) -> dict:
    since = (today - _dt.timedelta(days=DONE_DAYS)).isoformat()
    return {
        "merged_prs": gh_json("pr", "list", "-R", repo, "--state", "merged", "-S", f"merged:>={since}",
                              "-L", "500", "--json", "number,title,mergedAt,labels"),
        "open_prs": gh_json("pr", "list", "-R", repo, "--state", "open", "-L", "300",
                            "--json", "number,title,labels,isDraft"),
        "open_issues": gh_json("issue", "list", "-R", repo, "--state", "open", "-L", "500",
                               "--json", "number,title,labels,body"),
    }


def default_readiness_dir() -> Path:
    env = os.environ.get("ROADMAP_READINESS_DIR")
    return Path(env) if env else Path.home() / "hermes_kanban" / "kpi" / "readiness"


def load_readiness(path: Path | str) -> dict:
    p = Path(path)
    if p.is_dir():
        files = sorted(p.glob("*.json"), key=lambda f: f.name)
        if not files:
            raise FileNotFoundError(f"no readiness JSON in {p}")
        p = files[-1]
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("_source", p.name)
    return data


def load_plans(plans_dir: Path | str) -> list[dict]:
    out = []
    for f in sorted(Path(plans_dir).glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), f.stem)
        m = re.search(r"^Status:\s*(.+)$", text, re.M)
        status = m.group(1).strip() if m else ""
        out.append({"file": f.name, "title": title, "status": status})
    return out


def _labels(item: dict) -> set[str]:
    return {(lb.get("name") if isinstance(lb, dict) else str(lb)) for lb in item.get("labels") or []}


def _short(title: str, n: int = 90) -> str:
    title = " ".join(title.split())
    return title if len(title) <= n else title[: n - 1].rstrip() + "…"


def _group(items: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(classify(it.get("title", "")), []).append(it)
    order = sorted(groups, key=lambda a: (a == "0", int(a)))
    return {a: sorted(groups[a], key=lambda i: -int(i["number"])) for a in order}


def merged_recent(github: dict, today: _dt.date) -> list[dict]:
    since = today - _dt.timedelta(days=DONE_DAYS)
    out = []
    for pr in github.get("merged_prs") or []:
        day = _dt.date.fromisoformat(str(pr.get("mergedAt", ""))[:10] or "1970-01-01")
        if since <= day <= today:
            out.append(pr)
    return out


def recommendation(question: str) -> str:
    m = re.search(r"\(\s*рекомендац\w*[^:)]*:\s*([^)]+)\)", question, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"([^:/?(]+?)\s*\(\s*рекомендован\w*\s*\)", question, re.I)
    if m:
        return m.group(1).strip()
    return ""


def parked_reason(issue: dict) -> str:
    body = issue.get("body") or ""
    m = re.search(r"^\s*(?:parked|причина|reason|отложено)\s*[:\-—]\s*(.+)$", body, re.I | re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r"^##+\s*Blocked by\s*$(.*?)(?=^##|\Z)", body, re.I | re.M | re.S)
    if m:
        refs = re.findall(r"#\d+", m.group(1))
        if refs:
            return "ждёт " + ", ".join(dict.fromkeys(refs))
    return "причина не записана в задаче"


_PARKED_STATUS = re.compile(r"^(parked|frozen|later|deferred|postponed|отложен\w*)\b\s*(.*)$", re.I)
_ACTIVE_STATUS = re.compile(r"^(active|in progress|next|идёт|в работе)\b", re.I)


def _plan_reason(status: str) -> str:
    rest = _PARKED_STATUS.match(status).group(2)
    rest = re.sub(r"^\([^)]*\)\s*", "", rest).lstrip("-—: ").strip()
    return rest or "причина в плане"


def _blocker_areas(area: str) -> tuple[list[str], bool]:
    ids = [a for a in re.findall(r"\d+", str(area)) if a in AREAS]
    return ids, "gate" in str(area).lower() or "сдач" in str(area).lower()


def _score(v) -> str:
    return f"{float(v):.0f}" if v is not None else "—"


def _sections(readiness: dict, github: dict, plans: list[dict], today: _dt.date) -> dict:
    issues = github.get("open_issues") or []
    waits = [i for i in issues if "waits-artem" in _labels(i)]
    parked = [i for i in issues if "parked" in _labels(i)]
    return {
        "done": _group(merged_recent(github, today)),
        "open_prs": _group(github.get("open_prs") or []),
        "active_plans": [p for p in plans if _ACTIVE_STATUS.match(p["status"])],
        "parked_plans": [p for p in plans if _PARKED_STATUS.match(p["status"])],
        "waits": sorted(waits, key=lambda i: int(i["number"])),
        "parked": sorted(parked, key=lambda i: int(i["number"])),
        "ready": [i for i in issues if "ready-for-agent" in _labels(i)],
        "issues": issues,
    }


def _overall_line(readiness: dict) -> str:
    delta = (readiness.get("delta_vs_previous") or {}).get("change")
    d = f" ({float(delta):+.1f} к прошлой оценке)" if delta not in (None, "") else ""
    return f"Общая готовность: **{float(readiness.get('overall', 0)):.1f} из 100**{d}."


def render_page(readiness: dict, github: dict, plans: list[dict], *, today: str | _dt.date) -> str:
    today = _dt.date.fromisoformat(str(today))
    s = _sections(readiness, github, plans, today)
    L: list[str] = []
    a = L.append
    a("# Дорожная карта AGR-DigitalTwin")
    a("")
    a("> Страница создаётся автоматически: `uv run python tools/roadmap_ru.py`. Не править вручную —")
    a("> правки пропадут при следующем запуске. Источники: оценка готовности, задачи и PR на GitHub, `docs/plans/`.")
    a("")
    a(f"Обновлено: {today.isoformat()}; оценка готовности от {readiness.get('assessed_at', '—')}.")
    a("")
    a(_overall_line(readiness))
    a("")
    a("| Направление | Балл (0-100) | Готово, когда |")
    a("|---|---|---|")
    areas = readiness.get("areas") or {}
    for aid in sorted(areas, key=lambda x: int(x) if x.isdigit() else 99):
        done_means = AREAS.get(aid, (OTHER, ""))[1]
        a(f"| {area_name(aid, readiness)} | {_score((areas[aid] or {}).get('score'))} | {done_means} |")
    a("")

    total = sum(len(v) for v in s["done"].values())
    a(f"## Сделано за 7 дней")
    a("")
    a(f"Принято изменений (PR): {total}.")
    for aid, prs in s["done"].items():
        a("")
        a(f"### {area_name(aid, readiness)} — {len(prs)}")
        if aid == SERVICE:
            a(f"- {SERVICE_NOTE}")
            continue
        for pr in prs[:PER_AREA]:
            a(f"- #{pr['number']} {_short(pr.get('title', ''))}")
        if len(prs) > PER_AREA:
            a(f"- и ещё {len(prs) - PER_AREA}")
    a("")

    a("## Идёт сейчас")
    a("")
    n_open = sum(len(v) for v in s["open_prs"].values())
    a(f"Ждут проверки или слияния: {n_open} PR. Открытых задач: {len(s['issues'])}, "
      f"из них готовы для агента: {len(s['ready'])}.")
    for aid, prs in s["open_prs"].items():
        a("")
        a(f"### {area_name(aid, readiness)} — {len(prs)}")
        if aid == SERVICE:
            a(f"- {SERVICE_NOTE}")
            continue
        for pr in prs[:PER_AREA]:
            draft = " (черновик)" if pr.get("isDraft") else ""
            a(f"- #{pr['number']} {_short(pr.get('title', ''))}{draft}")
        if len(prs) > PER_AREA:
            a(f"- и ещё {len(prs) - PER_AREA}")
    if s["active_plans"]:
        a("")
        a("### Планы в работе")
        for p in s["active_plans"]:
            a(f"- {p['title']} (`docs/plans/{p['file']}`)")
    a("")

    a("## Осталось до сдачи без Артёма")
    a("")
    a("Три главных препятствия до 100; каждое агенты закрывают сами.")
    for n, b in enumerate((readiness.get("blockers") or [])[:3], 1):
        ids, gate = _blocker_areas(b.get("area", ""))
        names = ", ".join(area_name(i, readiness) for i in ids) + (", сдача объекта" if gate else "")
        gain = b.get("gain_points")
        gain_s = f" (+{float(gain):.1f} к общему баллу)" if gain not in (None, "") else ""
        a("")
        a(f"{n}. **{names or b.get('area', '—')}**{gain_s}.")
        crit = "; ".join(AREAS[i][1] for i in ids)
        a(f"   Что закроет: {crit or 'см. подробности'}.")
        if b.get("action_ru") or b.get("action"):
            a(f"   Подробно: {b.get('action_ru') or b.get('action')}")
        if b.get("tracking"):
            a(f"   Задачи: {b['tracking']}")
    gate = readiness.get("delivery_gate") or {}
    if gate:
        yes = {True: "пройдена", False: "не пройдена"}
        a("")
        a(f"Сдача: здание — {yes.get(gate.get('object_passed'), '—')}, "
          f"участок — {yes.get(gate.get('site_passed'), '—')}.")
    a("")

    a("## Ждёт Артёма")
    a("")
    n = 0
    for q in readiness.get("questions_for_user") or []:
        n += 1
        rec = recommendation(q)
        a(f"{n}. {q}")
        a(f"   Рекомендация: {rec}" if rec else "   Рекомендация: не записана, нужен ответ Артёма.")
    for i in s["waits"]:
        n += 1
        a(f"{n}. #{i['number']} {_short(i.get('title', ''))}")
        a(f"   Рекомендация: в задаче #{i['number']}.")
    if not n:
        a("Ничего не ждёт.")
    a("")

    a("## Отложено сознательно")
    a("")
    if not s["parked"] and not s["parked_plans"]:
        a("Ничего не отложено.")
    for i in s["parked"]:
        a(f"- #{i['number']} {_short(i.get('title', ''))} — {parked_reason(i)}")
    for p in s["parked_plans"]:
        a(f"- {p['title']} (`docs/plans/{p['file']}`) — {_plan_reason(p['status'])}")
    a("")
    return "\n".join(L)


def render_telegram(readiness: dict, github: dict, plans: list[dict], *, today: str | _dt.date) -> str:
    today = _dt.date.fromisoformat(str(today))
    s = _sections(readiness, github, plans, today)
    L: list[str] = []
    delta = (readiness.get("delta_vs_previous") or {}).get("change")
    d = f" ({float(delta):+.1f})" if delta not in (None, "") else ""
    L.append(f"Готовность AGR: {float(readiness.get('overall', 0)):.1f}/100{d}, {today.isoformat()}")
    areas = readiness.get("areas") or {}
    ranked = sorted(areas, key=lambda x: float((areas[x] or {}).get("score") or 0))
    parts = [f"{area_name(x, readiness)} {_score((areas[x] or {}).get('score'))}" for x in ranked]
    L.append("Слабые: " + " · ".join(parts[:6]))
    if parts[6:]:
        L.append("Сильные: " + " · ".join(parts[6:]))
    done = s["done"]
    by = ", ".join(f"{area_name(x, readiness)} {len(v)}" for x, v in
                   sorted(done.items(), key=lambda kv: -len(kv[1]))[:5])
    L.append(f"Сделано за 7 дней: {sum(len(v) for v in done.values())} PR ({by or '—'})")
    L.append(f"Идёт: {sum(len(v) for v in s['open_prs'].values())} PR на проверке, "
             f"{len(s['ready'])} задач готовы для агента")
    L.append("Осталось без Артёма:")
    for n, b in enumerate((readiness.get("blockers") or [])[:3], 1):
        ids, gate = _blocker_areas(b.get("area", ""))
        names = ", ".join(area_name(i, readiness) for i in ids) + (", сдача" if gate else "")
        L.append(f"{n}. {names or b.get('area', '—')}: {b.get('tracking', '')}".rstrip(": "))
    waits = [q for q in readiness.get("questions_for_user") or []] + \
            [f"#{i['number']} {_short(i.get('title', ''), 60)}" for i in s["waits"]]
    parked_line = f"Отложено: {len(s['parked']) + len(s['parked_plans'])}. Полностью: docs/ROADMAP.ru.md"
    room = TELEGRAM_MAX_LINES - len(L) - 2  # the header + the parked line
    L.append(f"Ждёт Артёма ({len(waits)}):")
    shown = waits if len(waits) <= room else waits[: max(room - 1, 0)]
    for n, w in enumerate(shown, 1):
        L.append(f"{n}. {_short(w, 110)}")
    if len(shown) < len(waits):
        L.append(f"… и ещё {len(waits) - len(shown)}")
    L.append(parked_line)
    return "\n".join(L[:TELEGRAM_MAX_LINES])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--readiness", help="readiness JSON or its directory (default: newest in ~/hermes_kanban/kpi/readiness)")
    ap.add_argument("--github-json", help="snapshot {merged_prs, open_prs, open_issues} instead of calling gh")
    ap.add_argument("--plans", default=str(DEFAULT_PLANS))
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--today", default=_dt.date.today().isoformat())
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--telegram", action="store_true", help=f"print a <= {TELEGRAM_MAX_LINES}-line digest")
    args = ap.parse_args(argv)
    readiness = load_readiness(args.readiness or default_readiness_dir())
    today = _dt.date.fromisoformat(args.today)
    if args.github_json:
        github = json.loads(Path(args.github_json).read_text(encoding="utf-8"))
    else:
        github = fetch_github(args.repo, today)
    plans = load_plans(args.plans)
    if args.telegram:
        sys.stdout.reconfigure(encoding="utf-8")
        print(render_telegram(readiness, github, plans, today=today))
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_page(readiness, github, plans, today=today), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
