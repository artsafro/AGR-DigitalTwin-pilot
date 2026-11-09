import sys, math, importlib.util
W=str(__import__('pathlib').Path(__file__).resolve().parents[2]/'adapters/max/agr_tools')+'/'
def load(f,n):
    s=importlib.util.spec_from_file_location(n,W+f); m=importlib.util.module_from_spec(s); sys.modules[n]=m; s.loader.exec_module(m); return m
core=load('atlas_core.py','ac')
TOL=1e-6
def close(a,b): return abs(a[0]-b[0])<TOL and abs(a[1]-b[1])<TOL   # runtime.assert_uv_close: diff == tol is error
def tex(w,h,seed=0): return [[((x*3+seed)%256,(y*5)%256,(x+y)%256) for x in range(w)] for y in range(h)]
quad=lambda o,w,h:[(o,0,0),(o+w,0,0),(o+w,h,0),(o,h,0)]
def mesh(name):
    if name=='A_plug1':
        return dict(v=quad(0,4,3),u=[(.1,.2),(.8,.2),(.8,.7),(.1,.7)],f=[(0,1,2,3)],fu=[(0,1,2,3)],fm=['G'],m={'G':{'color':(20,140,40),'dissolve':1.0}})
    if name=='B_plug2_2tiles':
        return dict(v=quad(0,4,3)+quad(6,2,2),u=[(.1,.2),(.8,.2),(.8,.7),(.1,.7),(1.15,.2),(1.85,.2),(1.85,.7),(1.15,.7)],f=[(0,1,2,3),(4,5,6,7)],fu=[(0,1,2,3),(4,5,6,7)],fm=['G','C'],m={'G':{'color':(20,140,40),'dissolve':1.0},'C':{'color':(150,150,155),'dissolve':1.0}})
    if name=='C_tex1':
        return dict(v=quad(0,4,3),u=[(.1,.2),(.8,.2),(.8,.7),(.1,.7)],f=[(0,1,2,3)],fu=[(0,1,2,3)],fm=['T'],m={'T':{'rgb':tex(128,128),'dissolve':1.0}})
    if name=='D_tex2_plug1':
        return dict(v=quad(0,4,3)+quad(6,3,3)+quad(10,2,2),u=[(.1,.2),(.8,.2),(.8,.7),(.1,.7),(.2,.1),(.9,.1),(.9,.8),(.2,.8),(.3,.3),(.6,.3),(.6,.6),(.3,.6)],
          f=[(0,1,2,3),(4,5,6,7),(8,9,10,11)],fu=[(0,1,2,3),(4,5,6,7),(8,9,10,11)],fm=['T','S','P'],
          m={'T':{'rgb':tex(128,128),'dissolve':1.0},'S':{'rgb':tex(128,128,7),'dissolve':1.0},'P':{'color':(9,9,9),'dissolve':1.0}})
    if name=='E_full_tile':   # UV covers whole 0..1 tile, plug
        return dict(v=quad(0,4,3),u=[(0,0),(1,0),(1,1),(0,1)],f=[(0,1,2,3)],fu=[(0,1,2,3)],fm=['G'],m={'G':{'color':(20,140,40),'dissolve':1.0}})
def run(M,mode,x=None):
    x=x or M
    return core.pack(M['v'],x['u'],M['f'],x['fu'],M['fm'],M['m'],mode=mode,size=2048,pad=8)
for name in ['A_plug1','B_plug2_2tiles','C_tex1','D_tex2_plug1','E_full_tile']:
  for mode in ['ground','oks']:
    M=mesh(name)
    print('==',name,mode)
    cur={'u':M['u'],'fu':M['fu']}
    try:
        for it in range(1,7):
            r=run(M,mode,cur); nxt={'u':r['uvs'],'fu':r['face_uvs']}
            deltas=[]
            for fo,fn in zip(cur['fu'],nxt['fu']):
                deltas.append(max(max(abs(cur['u'][a][0]-nxt['u'][b][0]),abs(cur['u'][a][1]-nxt['u'][b][1])) for a,b in zip(fo,fn)))
            changed=[i+1 for i,d in enumerate(deltas) if not d<TOL]
            print(f' pass{it}: used={r["used"]:.4f} tiles={r["tiles"]} cells={r["cells"]} maxdelta/face={["%.3e"%d for d in deltas]} changed={changed}')
            cur=nxt
            if not changed and it>1: break
    except core.AtlasError as e: print(' AtlasError',e)
