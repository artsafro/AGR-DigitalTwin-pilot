"""A/B harness of the #553 loop (evidence, not a tool): `uv run python ab.py <rounds> [<rev>]` alternates <rev>'s
(default HEAD) inv_xview_fast (A) and the working tree (B) in one process on TOW02 v005 + user05, asserting the lists.
Pattern: none | new-case: in-process A/B timing under board load for the #553 autoresearch loop.
"""
import sys, time, subprocess, importlib.util, statistics; sys.path.insert(0,'tools/qa')
import xview_bench as b, tempfile, os
HEAD_COPY=os.path.join(tempfile.gettempdir(),'_xview_head_fast.py')
from pathlib import Path
src=subprocess.run(['git','show',(sys.argv[2] if len(sys.argv)>2 else 'HEAD')+':src/dt_ai/ops/inv_xview_fast.py'],capture_output=True,text=True,check=True).stdout
Path(HEAD_COPY).write_text(src,encoding='utf-8')
def mod(p,n):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
A=mod(HEAD_COPY,'A'); B=mod('src/dt_ai/ops/inv_xview_fast.py','B')
fx,_=b.fixtures(Path(b.DEFAULT_DATA), Path(b.GROUND))
R=int(sys.argv[1]) if len(sys.argv)>1 else 7
for n,v,f,of,ov,tol in fx[:2]:
    ta,tb=[],[]
    for r in range(R):
        for m,t in ((A,ta),(B,tb)) if r%2==0 else ((B,tb),(A,ta)):
            c=time.process_time(); x=m.xview_lists(v,f,tol); t.append(time.process_time()-c)
            assert x['xview_faces']==of and x['vertices']==ov, (n,m.__name__)
    ma,mb=statistics.median(ta),statistics.median(tb)
    print(f'{n}: A(HEAD)={ma:.3f} B(work)={mb:.3f} delta={100*(mb-ma)/ma:+.1f}%')
