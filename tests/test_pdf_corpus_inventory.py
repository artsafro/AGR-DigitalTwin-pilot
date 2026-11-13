"""new-case: synthetic-folder tests for the zero-token PDF corpus inventory (#1274)."""
import csv
import hashlib
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'research' / 'pdf_corpus'))
import pdf_corpus_inventory as inv  # noqa: E402


def make_pdf(path, pages=1, text=None, author=None):
    """Minimal hand-built PDF; ``text`` (ASCII) goes on every page as a real text layer."""
    objs = ['<< /Type /Catalog /Pages 2 0 R >>', None, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for i in range(pages):
        stream = f'BT /F1 12 Tf 72 720 Td ({text} page {i + 1}) Tj ET' if text else ''
        objs.append(f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream')
        objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
                    f'/Resources << /Font << /F1 3 0 R >> >> /Contents {len(objs)} 0 R >>')
        kids.append(f'{len(objs)} 0 R')
    objs[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {pages} >>'
    info = None
    if author:
        objs.append(f'<< /Author ({author}) >>')
        info = len(objs)
    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f'{n} 0 obj\n{body}\nendobj\n'.encode('latin-1')
    xref = len(out)
    out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
    out += b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    trailer = f'<< /Size {len(objs) + 1} /Root 1 0 R' + (f' /Info {info} 0 R' if info else '') + ' >>'
    out += f'trailer\n{trailer}\nstartxref\n{xref}\n%%EOF\n'.encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))
    return path


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / 'scan'
    make_pdf(root / 'Вилтба' / 'ЖК Альфа' / '0123-АР фасады.pdf', pages=3, text='Facade sheet 0123-AR')
    make_pdf(root / 'copy' / 'same.pdf', pages=3, text='Facade sheet 0123-AR')  # duplicate bytes? no: rebuilt
    (root / 'copy' / 'same.pdf').write_bytes((root / 'Вилтба' / 'ЖК Альфа' / '0123-АР фасады.pdf').read_bytes())
    make_pdf(root / 'NTR' / '22_COD' / 'ГП благоустройство.pdf', pages=2)
    make_pdf(root / 'misc' / 'unnamed' / 'scan.pdf', pages=1, author='ASTO-1 bureau')
    make_pdf(root / 'ЦЕНТР' / 'Проект' / 'КЖ1.pdf', pages=4)
    (root / 'misc' / 'broken.pdf').write_bytes(b'not a pdf at all')
    (root / 'misc' / 'empty.pdf').write_bytes(b'')
    (root / 'misc' / 'notes.txt').write_text('ignore me')
    make_pdf(root / 'node_modules' / 'hidden.pdf')
    make_pdf(root / '.claude' / 'ntr-AI' / 'webfetch.pdf')
    return root


def read_csv(path):
    with open(path, encoding='utf-8', newline='') as f:
        return {Path(r['path']).name: r for r in csv.DictReader(f)}


def digest_tree(root):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}


def test_synthetic_folder_inventory(corpus, tmp_path):
    before = digest_tree(corpus)
    out_csv, out_md = tmp_path / 'inv.csv', tmp_path / 'inv.md'
    assert inv.main(['--root', str(corpus), '--csv', str(out_csv), '--summary', str(out_md)]) == 0
    rows = read_csv(out_csv)
    assert set(rows) == {'0123-АР фасады.pdf', 'same.pdf', 'ГП благоустройство.pdf', 'scan.pdf',
                         'КЖ1.pdf', 'broken.pdf', 'empty.pdf'}  # skip-list dir excluded, txt ignored
    a = rows['0123-АР фасады.pdf']
    assert (a['company'], a['company_source'], a['project']) == ('Вилтба', 'path', 'ЖК Альфа')
    assert a['pages'] == '3' and a['text_layer'] == 'yes' and a['hash_kind'] == 'sha256'
    assert set(a['sections'].split(';')) == {'АР', 'фасады'} and a['section_source'] == 'filename'
    assert a['hash'] == hashlib.sha256((corpus / 'copy' / 'same.pdf').read_bytes()).hexdigest()
    assert a['dup_group'] and a['dup_group'] == rows['same.pdf']['dup_group'] and a['dup_count'] == '2'
    assert (rows['same.pdf']['company'], rows['same.pdf']['company_source']) == ('Вилтба', 'duplicate')
    n = rows['ГП благоустройство.pdf']
    assert (n['company'], n['text_layer'], n['pages']) == ('NTR', 'no', '2')
    assert set(n['sections'].split(';')) == {'ГП', 'благоустройство'}
    s = rows['scan.pdf']
    assert (s['company'], s['company_source'], s['meta_author']) == ('АСТО-1', 'metadata', 'ASTO-1 bureau')
    assert rows['КЖ1.pdf']['company'] == 'other'  # НТР inside ЦЕНТР is not NTR
    assert rows['КЖ1.pdf']['sections'] == 'КЖ'
    assert rows['broken.pdf']['status'] == 'error' and 'not a PDF' in rows['broken.pdf']['error']
    assert rows['empty.pdf']['error'] == 'empty file'
    md = out_md.read_text(encoding='utf-8')
    assert 'PDF files found: **7**; readable: **5**; unique by sha256 hash: **4**' in md
    assert '| Вилтба | 2 | 1 | 3 | 100% | 100% | 1 |' in md
    assert f'| Вилтба | 3 | {3 * 45084:,} | {3 * 80000:,} | 0 |' in md
    assert f'| NTR | 2 | {2 * 45084:,} | {2 * 80000:,} | {2 * 45084:,} |' in md
    assert 'Company: **Вилтба**' in md and 'Only 1 albums available.' in md
    assert digest_tree(corpus) == before  # inputs never modified, nothing written under roots
    assert not list(tmp_path.glob('*.partial'))


@pytest.mark.parametrize('case', ['no-root', 'missing-root', 'no-pdf', 'csv-exists', 'same-output',
                                  'bad-suffix', 'unknown-company', 'timeout-nan', 'timeout-inf',
                                  'timeout-zero', 'output-is-input', 'missing-exclude', 'all-excluded'])
def test_fail_closed_writes_nothing(corpus, tmp_path, case):
    empty = tmp_path / 'empty'
    empty.mkdir()
    (empty / 'a.txt').write_text('x')
    out_csv, out_md = tmp_path / 'o.csv', tmp_path / 'o.md'
    args = {'root': [str(corpus)], 'csv': str(out_csv), 'summary': str(out_md), 'extra': []}
    if case == 'no-root':
        args['root'] = []
    elif case == 'missing-root':
        args['root'] = [str(tmp_path / 'nope')]
    elif case == 'no-pdf':
        args['root'] = [str(empty)]
    elif case == 'csv-exists':
        out_csv.write_text('keep')
    elif case == 'same-output':
        args['summary'] = args['csv'] = str(tmp_path / 'o.md')
    elif case == 'bad-suffix':
        args['csv'] = str(tmp_path / 'o.txt')
    elif case == 'unknown-company':
        args['extra'] = ['--pilot-company', 'Acme']
    elif case.startswith('timeout'):
        args['extra'] = ['--timeout', {'timeout-nan': 'nan', 'timeout-inf': 'inf', 'timeout-zero': '0'}[case]]
    elif case == 'missing-exclude':
        args['extra'] = ['--exclude', str(tmp_path / 'typo')]
    elif case == 'all-excluded':
        args['extra'] = [x for d in corpus.iterdir() for x in ('--exclude', str(d))]
    elif case == 'output-is-input':
        args['csv'] = str(corpus / 'misc' / 'broken.pdf')
    before = digest_tree(tmp_path)
    argv = [x for r in args['root'] for x in ('--root', r)] + ['--csv', args['csv'],
                                                               '--summary', args['summary']] + args['extra']
    if not args['root']:
        with pytest.raises(SystemExit):
            inv.main(argv)
    else:
        assert inv.main(argv) == 2
    assert digest_tree(tmp_path) == before


def test_path_alias_roots_list_each_file_once(corpus, tmp_path):
    rows = inv.run([str(corpus), str(corpus / '.' / 'NTR'), str(corpus) + '/'],
                   tmp_path / 'a.csv', tmp_path / 'a.md')
    paths = [Path(r['path']).resolve() for r in rows]
    assert len(paths) == len(set(paths)) == 7


def test_exclude_skips_directory_and_is_reported(corpus, tmp_path):
    rows = inv.run([str(corpus)], tmp_path / 'e.csv', tmp_path / 'e.md', excludes=[str(corpus / 'misc')])
    assert {Path(r['path']).name for r in rows} == {'0123-АР фасады.pdf', 'same.pdf', 'ГП благоустройство.pdf',
                                                    'КЖ1.pdf'}
    md = (tmp_path / 'e.md').read_text(encoding='utf-8')
    assert 'excluded 1' in md and 'skip-list 2' in md and str(corpus / 'misc') in md


def test_cloud_placeholder_is_not_read(corpus, tmp_path, monkeypatch):
    target = str(corpus / 'NTR' / '22_COD' / 'ГП благоустройство.pdf')
    real_stat = inv.os.stat

    class Fake:
        def __init__(self, st):
            self.st_size, self.st_mtime, self.st_mtime_ns = st.st_size, st.st_mtime, st.st_mtime_ns
            self.st_file_attributes = 0x400000

    monkeypatch.setattr(inv.os, 'stat', lambda p, *a, **k: Fake(real_stat(p)) if str(p) == target
                        else real_stat(p, *a, **k))
    opened = []
    real_open = open
    monkeypatch.setattr('builtins.open', lambda p, *a, **k: (opened.append(str(p)), real_open(p, *a, **k))[1])
    row = inv.inspect(target)
    assert (row['status'], row['error']) == ('error', 'cloud placeholder (not downloaded)')
    assert target not in opened and 'hash' not in row


def test_file_changed_during_scan_is_an_error_row(corpus, tmp_path, monkeypatch):
    real = inv._hash

    def mutating(path, kind, size):
        digest = real(path, kind, size)
        if path.endswith('КЖ1.pdf'):
            with open(path, 'ab') as f:
                f.write(b'%changed\n')
        return digest
    monkeypatch.setattr(inv, '_hash', mutating)
    rows = {Path(r['path']).name: r for r in inv.run([str(corpus)], tmp_path / 'c.csv', tmp_path / 'c.md')}
    assert (rows['КЖ1.pdf']['status'], rows['КЖ1.pdf']['error']) == ('error', 'changed during scan')
    assert rows['0123-АР фасады.pdf']['status'] == 'ok'


def test_fast_hash_and_pool_match_inline(corpus, tmp_path):
    inline = {r['path']: r for r in inv.run([str(corpus)], tmp_path / 'i.csv', tmp_path / 'i.md')}
    pooled = {r['path']: r for r in inv.run([str(corpus)], tmp_path / 'p.csv', tmp_path / 'p.md', workers=2)}
    keys = ('status', 'pages', 'hash', 'text_layer', 'company', 'sections', 'dup_group')
    assert {p: [r.get(k) for k in keys] for p, r in inline.items()} == \
           {p: [r.get(k) for k in keys] for p, r in pooled.items()}
    big = corpus / 'big.pdf'
    big.write_bytes(b'%PDF-1.4\n' + b'0' * (3 << 20))
    assert inv._hash(str(big), 'fast', big.stat().st_size).startswith('fast-')


def test_company_regex_probe():
    """Generated probe: every spelling is found as a path part; embedded in a word it is not."""
    rng = random.Random(1274)
    spellings = {'Вилтба': ['Вилтба', 'ВИЛТБА', 'Viltba', 'VILTBA', 'vilt_ba', '!Weltbau', 'Вельтбау'],
                 'NTR': ['NTR', 'ntr', 'НТР'], 'АСТО-1': ['АСТО-1', 'АСТО', 'ASTO-1', 'asto_1', 'Асто 1'],
                 'А101': ['!А101', 'A101', 'а101']}
    hits = total = 0
    for company, words in spellings.items():
        for w in words:
            for _ in range(20):
                pre = rng.choice(['', '00_', 'Архив ', '2024-'])
                post = rng.choice(['', '_альбомы', ' 2023', '-проекты'])
                path = f'D:/{pre}{w}{post}/Проект/лист.pdf'
                got = inv.guess_company(path, {})[0]
                total += 1
                hits += got == company
                assert inv.guess_company(f'D:/x{w.lstrip("!")}y/Проект/лист.pdf', {})[0] != company or company == 'Вилтба'
    assert hits == total == 360
    assert inv.guess_company('D:/А1011/a.pdf', {})[0] == 'other'
    for word in ('ЦЕНТР', 'НАСТОЯЩИЙ', 'CONTROL', 'entrance', 'Pastor', 'мастока'):
        assert inv.guess_company(f'D:/{word}/a.pdf', {})[0] == 'other', word


def test_pilot_picks_ten_distinct_of_one_company():
    rows = []
    for i in range(14):
        rows.append({'path': f'D:/Вилтба/P{i % 4}/{i:02d}.pdf', 'status': 'ok', 'hash': f'h{i}',
                     'company': 'Вилтба', 'project': f'P{i % 4}', 'sections': 'АР' if i % 2 else 'КЖ',
                     'pages': 10, 'text_layer': 'yes' if i < 12 else 'no'})
    rows += [{'path': 'D:/NTR/a.pdf', 'status': 'ok', 'hash': 'n1', 'company': 'NTR', 'project': 'x',
              'sections': '', 'pages': 1, 'text_layer': 'yes'}]
    rows.append(dict(rows[0], path='D:/copy/00.pdf'))  # duplicate hash is not a second album
    company, pilot = inv.pick_pilot(rows)
    assert company == 'Вилтба' and len(pilot) == 10
    assert len({r['hash'] for r in pilot}) == 10 and all(r['company'] == 'Вилтба' for r in pilot)
    assert all(r['text_layer'] == 'yes' for r in pilot) and len({r['project'] for r in pilot}) == 4
    assert inv.pick_pilot(rows, 'NTR')[1] == [rows[14]]
    a101 = [dict(r, company='А101', hash='a' + r['hash']) for r in rows[:3]]
    assert inv.pick_pilot(a101)[0] is None  # auto pilot stays within the companies named in #1274
    assert len(inv.pick_pilot(a101, 'А101')[1]) == 3
    short = [dict(rows[i], pages=1, sections='АГР') for i in range(4)] + rows[4:12]
    assert [r['pages'] for r in inv.pick_pilot(short)[1]] == [10] * 8 + [1] * 2  # albums before single sheets
    assert inv.pick_pilot([r for r in rows if r['company'] == 'other']) == (None, [])


def test_output_appearing_during_scan_is_not_clobbered(corpus, tmp_path, monkeypatch):
    out_csv, out_md = tmp_path / 'late.csv', tmp_path / 'late.md'
    real = inv.classify

    def racing(rows):
        out_md.write_text('someone else', encoding='utf-8')
        return real(rows)
    monkeypatch.setattr(inv, 'classify', racing)
    assert inv.main(['--root', str(corpus), '--csv', str(out_csv), '--summary', str(out_md)]) == 2
    assert out_md.read_text(encoding='utf-8') == 'someone else' and not out_csv.exists()
    assert not list(tmp_path.glob('.*.partial'))


@pytest.mark.parametrize('unsupported_at', ['csv', 'summary', 'both'])
def test_publish_without_hardlinks(corpus, tmp_path, monkeypatch, unsupported_at):
    import errno
    real_link, real_replace = inv.os.link, inv.os.replace
    replaced = []
    out_csv, out_md = tmp_path / 'drive.csv', tmp_path / 'drive.md'
    before = digest_tree(corpus)

    def link(src, dst):
        if unsupported_at == 'both' or (dst == out_csv) == (unsupported_at == 'csv'):
            raise OSError(errno.EINVAL, 'hard links unsupported')
        return real_link(src, dst)

    def replace(src, dst):
        assert Path(src).parent == dst.parent
        assert Path(src).name.endswith('.partial')
        replaced.append(dst)
        return real_replace(src, dst)

    monkeypatch.setattr(inv.os, 'link', link)
    monkeypatch.setattr(inv.os, 'replace', replace)
    argv = ['--root', str(corpus), '--csv', str(out_csv), '--summary', str(out_md)]
    assert inv.main(argv) == 0
    assert len(read_csv(out_csv)) == 7 and 'PDF files found: **7**' in out_md.read_text(encoding='utf-8')
    assert len(replaced) == (2 if unsupported_at == 'both' else 1)
    outputs = digest_tree(tmp_path)
    assert inv.main(argv) == 2
    assert digest_tree(tmp_path) == outputs and digest_tree(corpus) == before
    assert not list(tmp_path.glob('.*.partial'))


def test_fresh_process_cli(corpus, tmp_path):
    import subprocess
    script = Path(inv.__file__)
    args = [sys.executable, str(script), '--root', str(corpus), '--csv', str(tmp_path / 'f.csv'),
            '--summary', str(tmp_path / 'f.md')]
    ok = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    assert ok.returncode == 0 and '7 PDFs, 5 readable' in ok.stdout
    again = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')  # outputs exist now
    assert again.returncode == 2 and 'refusing to overwrite' in again.stderr
