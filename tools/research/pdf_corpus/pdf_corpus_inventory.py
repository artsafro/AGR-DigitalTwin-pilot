"""new-case: zero-token PDF corpus inventory of company albums (#1274), research only.

Walks the given roots, reads every ``*.pdf`` locally with pypdf (no LLM, no network
calls of its own) and writes a full CSV list plus a Markdown summary per company:
size, page count, sha256 (or fast hash), modified date, company/project/section
guesses, text-layer presence and duplicate groups. PDFs are only read, never copied,
moved or written. Every discovered PDF ends in the CSV; read failures stay as rows with
``status`` and ``error``; skipped directories and walk errors are counted in the summary.

Token estimate rates come from PR #1272 (#1236): 225420 whole-session tokens for five
physical pages measured by the vision fallback, conservative cap 80000 tokens/page.
"""
from __future__ import annotations

import argparse
import csv
import errno
import hashlib
import io
import logging
import os
import re
import sys
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

MEASURED_TOKENS = 225420
MEASURED_PAGES = 5
TOKENS_PER_PAGE_MEASURED = MEASURED_TOKENS // MEASURED_PAGES  # 45084
TOKENS_PER_PAGE_CAP = 80000
TEXT_MIN_CHARS = 20
CHUNK = 1 << 20

SKIP_DIRS = {
    '$recycle.bin', 'system volume information', 'windows', 'program files',
    'program files (x86)', 'programdata', 'appdata', 'recovery', '$windows.~ws',
    '$getcurrent', 'config.msi', 'msocache', '.git', 'node_modules', '.venv', 'venv',
    'site-packages', '__pycache__', '.worktrees', '.tmp.drivedownload', '.tmp.driveupload',
    '.claude', '.codex', '.cursor', '.gemini',  # agent caches (web fetches, tool results)
}

COMPANIES = (
    ('Вилтба', re.compile(r'в[иі]лтба|viltba|vilt[-_ ]ba|weltbau|вельтбау', re.I)),
    ('NTR', re.compile(r'(?<![^\W\d_])(?:ntr|нтр)(?![^\W\d_])', re.I)),
    ('АСТО-1', re.compile(r'(?<![^\W\d_])(?:асто|asto)(?:[-_ ]?1)?(?![^\W_])', re.I)),
    ('А101', re.compile(r'(?<![^\W\d_])[аa]101(?!\d)', re.I)),  # found on disk, not named in #1274
)
PILOT_COMPANIES = ('Вилтба', 'NTR', 'АСТО-1')
OTHER = 'other'

_CODES = ('АГР', 'АР', 'АИ', 'ГП', 'АС', 'КЖ', 'КМ', 'КР', 'ОВ', 'ВК', 'ЭОМ', 'ЭС', 'СС',
          'ТХ', 'ПЗ', 'ПЗУ', 'ПОС', 'ООС', 'ПБ', 'МАФ', 'БЛ')
_LATIN = {'AGR': 'АГР', 'AR': 'АР', 'GP': 'ГП', 'AS': 'АС', 'KZH': 'КЖ', 'KJ': 'КЖ', 'KM': 'КМ',
          'KR': 'КР', 'OV': 'ОВ', 'VK': 'ВК', 'EOM': 'ЭОМ', 'MAF': 'МАФ'}
_CODE_RE = re.compile(r'(?<![^\W\d_])(' + '|'.join(sorted(_CODES + tuple(_LATIN), key=len, reverse=True))
                      + r')(?:\d{0,2})(?![^\W\d_])')
_DESIGNATION_RE = re.compile(r'\d[\w./-]*[-.]\s?(' + '|'.join(sorted(_CODES, key=len, reverse=True))
                             + r')\d{0,2}(?![^\W\d_])')
_WORDS = (
    ('отделка', re.compile(r'отделк|finish', re.I)),
    ('спецификации', re.compile(r'специфика|ведомост', re.I)),
    ('фасады', re.compile(r'фасад|facade', re.I)),
    ('окна', re.compile(r'оконн|окна|витраж|window', re.I)),
    ('благоустройство', re.compile(r'благоустр|landscap', re.I)),
    ('озеленение', re.compile(r'озеленен|дендро', re.I)),
    ('паспорт', re.compile(r'паспорт', re.I)),
    ('материалы', re.compile(r'материал|колер|material', re.I)),
)
PILOT_PRIORITY = ('АГР', 'фасады', 'отделка', 'материалы', 'окна', 'АР', 'ГП', 'благоустройство',
                  'МАФ', 'озеленение', 'спецификации', 'паспорт')

FIELDS = ('path', 'root', 'size_bytes', 'modified_utc', 'hash', 'hash_kind', 'status', 'error',
          'pages', 'encrypted', 'text_layer', 'text_chars', 'meta_title', 'meta_author',
          'meta_creator', 'meta_producer', 'company', 'company_source', 'project', 'sections',
          'section_source', 'dup_group', 'dup_count')


class InventoryError(Exception):
    """Fail-closed input/output error; nothing is written."""


# ---------------------------------------------------------------- discovery

def _key(path):
    return os.path.normcase(os.path.realpath(path))


def discover(roots, excludes=()):
    """Return (pdf paths, skipped dirs, walk errors); paths de-duplicated by real path."""
    seen, files, skipped, errors = set(), [], [], []
    excluded = {_key(e) for e in excludes}
    for root in roots:
        def onerror(e):
            errors.append((str(e.filename), type(e).__name__))
        for directory, dirs, names in os.walk(root, onerror=onerror, followlinks=False):
            keep = []
            for d in dirs:
                full = os.path.join(directory, d)
                if d.lower() in SKIP_DIRS or d.startswith('~$'):
                    skipped.append((full, 'skip-list'))
                elif _key(full) in excluded:
                    skipped.append((full, 'excluded'))
                elif os.path.islink(full) or (hasattr(os.path, 'isjunction') and os.path.isjunction(full)):
                    skipped.append((full, 'link/junction'))
                else:
                    keep.append(d)
            dirs[:] = sorted(keep)
            for name in sorted(names):
                if not name.lower().endswith('.pdf'):
                    continue
                full = os.path.join(directory, name)
                key = _key(full)
                if key in seen:
                    continue
                seen.add(key)
                files.append((full, root))
    return files, skipped, errors


# ---------------------------------------------------------------- per-file inspection

CLOUD_ATTRS = 0x1000 | 0x40000 | 0x400000  # OFFLINE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS


def _is_placeholder(st):
    """True for an online-only cloud file (OneDrive/Dropbox): reading it would download it."""
    return bool(getattr(st, 'st_file_attributes', 0) & CLOUD_ATTRS)


def _hash(path, kind, size):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        if kind == 'fast' and size > 2 * CHUNK:
            h.update(str(size).encode())
            h.update(f.read(CHUNK))
            f.seek(size - CHUNK)
            h.update(f.read(CHUNK))
            return 'fast-' + h.hexdigest()
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def _meta(reader):
    try:
        meta = reader.metadata or {}
    except Exception:  # noqa: BLE001 - broken info dict is data, not a crash
        return {}
    out = {}
    for key, field in (('/Title', 'meta_title'), ('/Author', 'meta_author'),
                       ('/Creator', 'meta_creator'), ('/Producer', 'meta_producer')):
        value = meta.get(key)
        if value is not None:
            out[field] = ' '.join(str(value).split())[:200]
    return out


def inspect(path, hash_kind='sha256', text_pages=2):
    """Read one PDF; never raises for a bad file, returns a row with status/error."""
    from pypdf import PdfReader
    logging.getLogger('pypdf').setLevel(logging.CRITICAL)
    row = {'path': path, 'status': 'ok', 'error': '', 'text_layer': 'unknown'}
    try:
        st = os.stat(path)
    except OSError as e:
        return {**row, 'status': 'error', 'error': f'stat: {type(e).__name__}'}
    row['size_bytes'] = st.st_size
    row['modified_utc'] = datetime.fromtimestamp(st.st_mtime, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if st.st_size == 0:
        return {**row, 'status': 'error', 'error': 'empty file'}
    if _is_placeholder(st):
        return {**row, 'status': 'error', 'error': 'cloud placeholder (not downloaded)'}
    try:
        row['hash'] = _hash(path, hash_kind, st.st_size)
        row['hash_kind'] = 'fast' if row['hash'].startswith('fast-') else 'sha256'
        with open(path, 'rb') as f:
            head = f.read(1024)
            if b'%PDF-' not in head:
                return {**row, 'status': 'error', 'error': 'not a PDF (no %PDF- header)'}
            f.seek(0)
            data = f.read() if st.st_size <= 512 * CHUNK else None
        reader = PdfReader(io.BytesIO(data) if data is not None else path, strict=False)
        row['encrypted'] = bool(reader.is_encrypted)
        if reader.is_encrypted:
            try:
                if not reader.decrypt(''):
                    return {**row, 'status': 'error', 'error': 'encrypted (password)'}
            except Exception as e:  # noqa: BLE001
                return {**row, 'status': 'error', 'error': f'encrypted: {type(e).__name__}'}
        row['pages'] = len(reader.pages)
        row.update(_meta(reader))
        text, chars = [], 0
        for i in range(min(text_pages, row['pages'])):
            try:
                t = reader.pages[i].extract_text() or ''
            except Exception:  # noqa: BLE001
                t = ''
            text.append(t[:4000])
            chars += len(''.join(t.split()))
        row['text_chars'] = chars
        row['text_layer'] = 'yes' if chars >= TEXT_MIN_CHARS else 'no'
        row['_text'] = '\n'.join(text)
    except Exception as e:  # noqa: BLE001 - malformed PDFs are reported, not fatal
        row.update(status='error', error=f'{type(e).__name__}: {str(e)[:120]}')
    try:
        st2 = os.stat(path)
        if (st2.st_size, st2.st_mtime_ns) != (st.st_size, st.st_mtime_ns):
            row.update(status='error', error='changed during scan')
    except OSError:
        row.update(status='error', error='vanished during scan')
    return row


def inspect_all(paths, hash_kind, text_pages, workers, timeout):
    if workers <= 1:
        return {p: inspect(p, hash_kind, text_pages) for p in paths}
    results, pending, inflight, ex = {}, list(reversed(paths)), {}, None
    while pending or inflight:
        if ex is None:
            ex = ProcessPoolExecutor(workers)
        while pending and len(inflight) < workers:
            p = pending.pop()
            inflight[ex.submit(inspect, p, hash_kind, text_pages)] = (p, time.monotonic())
        done, _ = wait(list(inflight), timeout=1, return_when=FIRST_COMPLETED)
        for fut in done:
            p, _t = inflight.pop(fut)
            try:
                results[p] = fut.result()
            except Exception as e:  # noqa: BLE001 - worker crash is a row, not a lost file
                results[p] = {'path': p, 'status': 'error', 'error': f'worker: {type(e).__name__}'}
        now = time.monotonic()
        if any(now - t > timeout for _p, t in inflight.values()):
            wait(list(inflight), timeout=max(0.0, timeout - min(now - t for _p, t in inflight.values())))
            for fut, (p, _t) in list(inflight.items()):
                if fut.done() and not fut.exception():
                    results[p] = fut.result()
                else:
                    results[p] = {'path': p, 'status': 'error', 'error': f'timeout > {timeout}s'}
            inflight = {}
            for proc in list(getattr(ex, '_processes', {}).values()):
                proc.kill()
            ex.shutdown(wait=False, cancel_futures=True)
            ex = None
    if ex is not None:
        ex.shutdown()
    return results


# ---------------------------------------------------------------- classification

def guess_company(path, row):
    parts = Path(path).parts
    for idx in range(len(parts) - 1, -1, -1):
        for name, rx in COMPANIES:
            if rx.search(parts[idx]):
                return name, 'path', idx
    meta = ' '.join(str(row.get(k, '')) for k in ('meta_title', 'meta_author', 'meta_creator'))
    for name, rx in COMPANIES:
        if rx.search(meta):
            return name, 'metadata', None
    for name, rx in COMPANIES:
        if rx.search(row.get('_text', '')):
            return name, 'text', None
    return OTHER, 'none', None


def guess_project(path, idx):
    parts = Path(path).parts
    if idx is not None and idx + 1 < len(parts) - 1:
        return parts[idx + 1]
    return parts[-2] if len(parts) > 1 else ''


def guess_sections(path, text):
    p = Path(path)
    found = []
    for source, chunk in (('filename', p.stem), ('folder', p.parent.name)):
        for m in _CODE_RE.finditer(chunk):
            code = _LATIN.get(m.group(1).upper(), m.group(1)) if m.group(1).isascii() else m.group(1)
            found.append(code)
        for label, rx in _WORDS:
            if rx.search(chunk):
                found.append(label)
        if found:
            return sorted(set(found)), source
    if text:
        found = [m.group(1) for m in _DESIGNATION_RE.finditer(text)]
        found += [label for label, rx in _WORDS if rx.search(text[:1500])]
        if found:
            return sorted(set(found)), 'text'
    return [], 'none'


def classify(rows):
    for row in rows:
        company, source, idx = guess_company(row['path'], row)
        row['company'], row['company_source'] = company, source
        row['project'] = guess_project(row['path'], idx)
        sections, ssource = guess_sections(row['path'], row.get('_text', ''))
        row['sections'], row['section_source'] = ';'.join(sections), ssource
    groups = defaultdict(list)
    for row in rows:
        if row.get('hash') and row['status'] == 'ok':
            groups[row['hash']].append(row)
    for h, members in groups.items():
        named = {r['company'] for r in members if r['company'] != OTHER}
        for row in members:
            if len(named) == 1 and row['company'] == OTHER:  # a copy inherits its twin's company
                row['company'], row['company_source'] = next(iter(named)), 'duplicate'
            row['dup_group'] = h.replace('fast-', '')[:12] if len(members) > 1 else ''
            row['dup_count'] = len(members)
    return rows


# ---------------------------------------------------------------- outputs

def _canonical(rows):
    """One row per unique hash (first by path) among readable PDFs."""
    seen, out = set(), []
    for row in sorted(rows, key=lambda r: (r.get('company_source') in ('duplicate', 'none'), r['path'])):
        if row['status'] == 'ok' and row['hash'] not in seen:
            seen.add(row['hash'])
            out.append(row)
    return out


def pick_pilot(rows, company=None, n=10):
    uniq = _canonical(rows)
    named = PILOT_COMPANIES
    if company is None:
        counts = Counter(r['company'] for r in uniq if r['company'] in named)
        if not counts:
            return None, []
        pages = Counter()
        for r in uniq:
            pages[r['company']] += r.get('pages') or 0
        company = sorted(counts, key=lambda c: (-counts[c], -pages[c], c))[0]
    pool = [r for r in uniq if r['company'] == company]

    def score(r):
        secs = set(filter(None, r['sections'].split(';')))
        prio = min((PILOT_PRIORITY.index(s) for s in secs if s in PILOT_PRIORITY), default=99)
        pages = r.get('pages') or 0
        return (r['text_layer'] != 'yes', not 3 <= pages <= 300, prio, r['path'])

    chosen = []
    for tier in sorted({score(r)[:2] for r in pool}):  # round-robin over projects inside each tier
        by_project = defaultdict(list)
        for r in sorted((r for r in pool if score(r)[:2] == tier), key=score):
            by_project[r['project']].append(r)
        order = sorted(by_project, key=lambda p: score(by_project[p][0]))
        while len(chosen) < n and any(by_project[p] for p in order):
            for p in order:
                if by_project[p] and len(chosen) < n:
                    chosen.append(by_project[p].pop(0))
    return company, chosen


def _pct(a, b):
    return f'{100 * a / b:.0f}%' if b else 'n/a'


def render_summary(rows, roots, skipped, walk_errors, hash_kind, csv_path, command, pilot_company=None,
                   excludes=()):
    uniq = _canonical(rows)
    errors = Counter(r['error'].split(':')[0] for r in rows if r['status'] != 'ok')
    lines = [
        '# PDF corpus inventory (#1274)', '',
        f'Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `{command}` '
        '(pypdf, zero LLM tokens). PDFs are read in place; none copied or committed.', '',
        f'- Roots: {", ".join(f"`{r}`" for r in roots)}',
        f'- PDF files found: **{len(rows)}**; readable: **{sum(r["status"] == "ok" for r in rows)}**; '
        f'unique by {hash_kind} hash: **{len(uniq)}**; unreadable: **{sum(errors.values())}**',
        f'- Skipped directories: ' + (', '.join(f'{k} {v}' for k, v in sorted(Counter(r for _p, r in skipped).items()))
                                      or '0') + f'; walk errors: {len(walk_errors)}',
        f'- Excluded by `--exclude`: ' + (', '.join(f'`{e}`' for e in excludes) or 'none'),
        f'- Full list: `{csv_path}` (one row per file, incl. unreadable ones with `status`/`error`).',
        '',
    ]
    if errors:
        lines += ['Unreadable files by reason: ' + ', '.join(f'{k} {v}' for k, v in errors.most_common()), '']
    lines += ['## Per company', '',
              'Albums and pages count unique hashes only; duplicates are listed in "files".', '',
              '| Company | Files | Albums | Pages | Text-layer albums | Text-layer pages | Projects | Top sections |',
              '|---|---:|---:|---:|---:|---:|---:|---|']
    companies = [c for c, _ in COMPANIES] + [OTHER]
    stats = {}
    for c in companies:
        files = [r for r in rows if r.get('company') == c]
        u = [r for r in uniq if r['company'] == c]
        pages = sum(r['pages'] for r in u)
        tpages = sum(r['pages'] for r in u if r['text_layer'] == 'yes')
        secs = Counter(s for r in u for s in r['sections'].split(';') if s)
        stats[c] = (u, pages, tpages)
        lines.append(f'| {c} | {len(files)} | {len(u)} | {pages} | '
                     f'{_pct(sum(r["text_layer"] == "yes" for r in u), len(u))} | {_pct(tpages, pages)} | '
                     f'{len({r["project"] for r in u})} | '
                     + (', '.join(f'{s} {n}' for s, n in secs.most_common(6)) or '-') + ' |')
    lines += ['', '## Estimated token cost of a full parse', '',
              f'Rates from PR #1272 (#1236): measured {MEASURED_TOKENS} whole-session tokens for '
              f'{MEASURED_PAGES} physical pages = **{TOKENS_PER_PAGE_MEASURED} tokens/page** (vision route, '
              f'session usage incl. context, not isolated image billing); conservative cap '
              f'**{TOKENS_PER_PAGE_CAP} tokens/page**. "Text-first" sends only pages without a text layer '
              'to vision and reads text-layer pages locally (0 LLM tokens). Unique pages only.', '',
              '| Company | Pages | All pages @ measured | All pages @ cap | Text-first @ measured |',
              '|---|---:|---:|---:|---:|']
    for c in companies:
        u, pages, tpages = stats[c]
        lines.append(f'| {c} | {pages} | {pages * TOKENS_PER_PAGE_MEASURED:,} | '
                     f'{pages * TOKENS_PER_PAGE_CAP:,} | {(pages - tpages) * TOKENS_PER_PAGE_MEASURED:,} |')
    dups = {(r['dup_group'], r['dup_count'], r['size_bytes'], r['company'])
            for r in rows if r.get('dup_group')}
    lines += ['', '## Duplicate groups', '',
              f'{len(dups)} hash groups with more than one file; '
              f'{sum(k[1] - 1 for k in dups)} redundant copies. Largest by wasted bytes:', '']
    top = sorted(dups, key=lambda k: -(k[1] - 1) * k[2])[:15]
    if top:
        lines += ['| Group | Copies | Size MB | Company |', '|---|---:|---:|---|']
        lines += [f'| {g} | {n} | {s / 1e6:.1f} | {c} |' for g, n, s, c in top]
    company, pilot = pick_pilot(rows, pilot_company)
    lines += ['', '## Proposed pilot parse (10 albums of one company)', '']
    if company is None:
        lines.append('No album of ' + ', '.join(PILOT_COMPANIES) + ' found; no pilot proposed.')
    else:
        lines += [f'Company: **{company}** (most unique albums, then pages, among the named companies). Ranking: text '
                  'layer first, then 3-300 pages, then section priority ' + ' > '.join(PILOT_PRIORITY) +
                  ', round-robin over projects. ' +
                  (f'Only {len(pilot)} albums available.' if len(pilot) < 10 else ''), '',
                  '| # | Project | Sections | Pages | Text | sha256 (12) | Path |', '|---:|---|---|---:|---|---|---|']
        for i, r in enumerate(pilot, 1):
            lines.append(f'| {i} | {r["project"]} | {r["sections"] or "-"} | {r["pages"]} | {r["text_layer"]} | '
                         f'{r["hash"].replace("fast-", "")[:12]} | `{r["path"]}` |')
        pp = sum(r['pages'] for r in pilot)
        lines += ['', f'Pilot pages: {pp}; estimate {pp * TOKENS_PER_PAGE_MEASURED:,} tokens at the measured '
                  f'rate, {pp * TOKENS_PER_PAGE_CAP:,} at the cap.']
    return '\n'.join(lines) + '\n'


def _write_new(path, text):
    """Publish complete text; reserve exclusively before a no-hardlink replacement.

    The reservation prevents clobbering an existing destination (including a dangling
    symlink). Replacement is atomic per file, not a cross-filesystem transaction.
    """
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.{uuid.uuid4().hex}.partial')
    created_tmp = False
    reservation = None
    try:
        with open(tmp, 'x', encoding='utf-8', newline='') as f:
            created_tmp = True
            f.write(text)
        try:
            os.link(tmp, path)
        except OSError as e:
            if (e.errno not in {errno.EPERM, errno.EINVAL, errno.ENOTSUP, errno.ENOSYS}
                    and getattr(e, 'winerror', None) != 1):
                raise
            with open(path, 'x', encoding='utf-8') as f:
                reservation = os.fstat(f.fileno())
            os.replace(tmp, path)
            reservation = None
    except OSError as e:
        raise InventoryError(f'cannot publish output {path}: {e}') from e
    finally:
        if reservation is not None and path.exists():
            if os.path.samestat(path.stat(), reservation):
                path.unlink()
        if created_tmp and tmp.exists():
            tmp.unlink()


def _csv_text(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction='ignore', lineterminator='\n')
    w.writeheader()
    for row in sorted(rows, key=lambda r: r['path']):
        w.writerow({k: row.get(k, '') for k in FIELDS})
    return buf.getvalue()


def run(roots, csv_path, summary_path, hash_kind='sha256', workers=1, timeout=120.0,
        text_pages=2, pilot_company=None, command='pdf_corpus_inventory.py', excludes=()):
    if not roots:
        raise InventoryError('no --root given')
    norm_roots = []
    for r in roots:
        if not os.path.isdir(r):
            raise InventoryError(f'root is not a directory: {r}')
        norm_roots.append(os.path.abspath(r))
    for e in excludes:
        if not os.path.isdir(e):
            raise InventoryError(f'exclude is not a directory: {e}')
    if pilot_company is not None and pilot_company not in [c for c, _ in COMPANIES]:
        raise InventoryError(f'unknown pilot company: {pilot_company}')
    if not (timeout > 0 and timeout != float('inf')) or text_pages < 1 or workers < 1:
        raise InventoryError('timeout must be finite > 0, text_pages >= 1, workers >= 1')
    outs = [Path(csv_path).absolute(), Path(summary_path).absolute()]
    if outs[0].suffix.lower() != '.csv' or outs[1].suffix.lower() != '.md':
        raise InventoryError('--csv must end with .csv and --summary with .md')
    if os.path.normcase(outs[0]) == os.path.normcase(outs[1]):
        raise InventoryError('--csv and --summary are the same path')
    for o in outs:
        if o.exists():
            raise InventoryError(f'output exists, refusing to overwrite: {o}')
        if not o.parent.is_dir():
            raise InventoryError(f'output directory missing: {o.parent}')
    files, skipped, walk_errors = discover(norm_roots, excludes)
    if not files:
        raise InventoryError('no PDF found under the roots')
    results = inspect_all([p for p, _r in files], hash_kind, text_pages, workers, timeout)
    rows = []
    for p, root in files:
        row = results[p]
        row['root'] = root
        rows.append(row)
    classify(rows)
    for o in outs:  # re-check after the long scan: state may change during the run
        if o.exists():
            raise InventoryError(f'output appeared during scan, refusing to overwrite: {o}')
    _write_new(outs[0], _csv_text(rows))
    _write_new(outs[1], render_summary(rows, norm_roots, skipped, walk_errors, hash_kind,
                                       csv_path, command, pilot_company, list(excludes)))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description='Zero-token PDF corpus inventory (#1274).')
    ap.add_argument('--root', action='append', required=True, help='directory to scan (repeatable)')
    ap.add_argument('--csv', required=True)
    ap.add_argument('--summary', required=True)
    ap.add_argument('--hash', choices=('sha256', 'fast'), default='sha256')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--timeout', type=float, default=120.0, help='seconds per PDF (workers > 1)')
    ap.add_argument('--text-pages', type=int, default=2)
    ap.add_argument('--pilot-company', default=None)
    ap.add_argument('--exclude', action='append', default=[], help='directory to skip (repeatable)')
    args = ap.parse_args(argv)
    try:
        rows = run(args.root, args.csv, args.summary, args.hash, args.workers, args.timeout,
                   args.text_pages, args.pilot_company, excludes=args.exclude,
                   command='python tools/research/pdf_corpus/pdf_corpus_inventory.py ' + ' '.join(
                       a for a in (argv if argv is not None else sys.argv[1:])))
    except InventoryError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    print(f'{len(rows)} PDFs, {sum(r["status"] == "ok" for r in rows)} readable -> {args.csv}, {args.summary}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
