"""new-case: generate fresh headless PDFIMPORT script for one research page.

Execute with dcc_batch.py acad --file SCRIPT. Import scale=1 is paper units,
not a claim of model scale. Never save to the input PDF.
"""
import argparse
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf', type=Path, required=True)
    p.add_argument('--page', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--script', type=Path, required=True)
    a = p.parse_args()
    import pymupdf
    from probe import validate_pages
    with pymupdf.open(a.pdf) as doc:
        validate_pages([a.page], len(doc))
    targets = [a.out.with_suffix(s).resolve() for s in ['.dwg', '.dxf']] + [a.script.resolve()]
    inputs = a.pdf.resolve()
    for target in targets:
        if target.exists() or str(target).casefold() == str(inputs).casefold():
            raise ValueError(f'refusing existing or input path: {target}')
        if any(c in str(target) for c in ['"', '\n', '\r']):
            raise ValueError('unsafe command path')
    if len(set(str(x).casefold() for x in targets)) != len(targets):
        raise ValueError('output aliases')
    a.script.parent.mkdir(parents=True, exist_ok=True)
    lines = ['(setvar "FILEDIA" 0)', '(setvar "CMDDIA" 0)', '(setvar "INSUNITS" 4)',
             '(princ (strcat "RESEARCH_ACADVER=" (getvar "ACADVER")))',
             '_-PDFIMPORT', '_File', a.pdf.resolve().as_posix(), str(a.page), '0,0', '1', '0',
             '_SAVEAS', '2018', targets[0].as_posix(), '_DXFOUT', targets[1].as_posix(), '16',
             '_QUIT', '_N', '']
    with a.script.open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(a.script)


if __name__ == '__main__':
    main()
