"""new-case: batch native AutoCAD readback of six staged TEC26 drawings, no DWG saves."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('C:/x/tec26-oks')
OUT = ROOT / 'acad-readback-v001'
OUT.mkdir(exist_ok=False)
rows = json.loads(Path('jobs/TEC26-OKS/census/sources.json').read_text(encoding='utf-8'))
for i in range(4, 10):
    found = [r for r in rows if f'АС.{i:02d}' in r['relative'] and r['relative'].lower().endswith('.dwg')]
    assert len(found) == 1, (i, found)
    path = Path(found[0]['copy'])
    assert path.resolve().is_relative_to((ROOT/'sources-v001').resolve())
    dxf = OUT / f'ac{i:02d}.dxf'
    script = OUT / f'ac{i:02d}.scr'
    script.write_text('(setvar "FILEDIA" 0)\n(setvar "CMDECHO" 1)\n'
        '(princ (strcat "TEC26 INSUNITS=" (itoa (getvar "INSUNITS")) " ACADVER=" (getvar "ACADVER")))\n'
        f'(command "_.DXFOUT" "{dxf.as_posix()}" "_V" "2018" "16")\n'
        '(princ "TEC26_ACAD_COMPLETE")\n', encoding='utf-8')
    p = subprocess.run([sys.executable, 'C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py',
        'acad','--file', str(script),'--dwg',str(path),'--wait','120','--timeout','180',
        '--out',str(OUT/f'ac{i:02d}-run.json'),'--max-chars','1200','--card','t_8e55c5f5'],capture_output=True,text=True,encoding='utf-8',errors='replace')
    print(i,p.returncode,p.stdout[-1200:],flush=True)
    assert p.returncode == 0 and dxf.exists() and dxf.stat().st_size > 0
