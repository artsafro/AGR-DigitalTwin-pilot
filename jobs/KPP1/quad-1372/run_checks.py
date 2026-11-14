"""new-case: #1372 checks of the KPP1 quad master; copy of benchmark-1318/run_benchmark.py with the quad master.

Same stages, frozen packet and manifest verification as #1318; the master is `master-quad-v001.blend`, the
V003 `--master` input is the quad work FBX, and a fresh-process readback of that FBX is added.
Never certifies delivery.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
VERSION = 'v001'   # argv[3] selects another master version (v002: union of the R1 overlaps, #1372)


def verify(packet):
    expected = {}
    for line in (packet/'SHA256SUMS.txt').read_text().splitlines():
        digest, name = line.split('  ',1)
        if name in expected or (packet/name).resolve().is_relative_to(packet.resolve()) is False:
            raise ValueError(f'duplicate/escaping manifest member: {name}')
        expected[name] = digest
    actual = {p.relative_to(packet).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in packet.rglob('*') if p.is_file() and p != packet/'SHA256SUMS.txt'}
    if not expected or expected != actual:
        raise ValueError('packet integrity mismatch')
    return hashlib.sha256((packet/'SHA256SUMS.txt').read_bytes()).hexdigest()


def main(packet, out, version=VERSION):
    MASTER, MASTER_FBX = f'master-quad-{version}.blend', f'SM_Kpp_1.quad-{version}.fbx'
    packet, out = packet.resolve(), out.resolve()
    if out.is_relative_to(packet) or packet.is_relative_to(out):
        raise ValueError('run root aliases frozen packet')
    manifest = verify(packet)
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', DT_BLENDER=BLENDER)
    env.pop('MSYS_NO_PATHCONV',None)
    env.pop('MSYS2_ARG_CONV_EXCL',None)
    start = time.perf_counter()
    record = {'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'manifest_sha256': manifest, 'code_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'master': MASTER, 'stages': [], 'delivery_complete': False}

    def stage(name, cmd):
        verify(packet)
        t = time.perf_counter()
        with (out/f'{name}.log').open('xb') as log:
            result = subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        record['stages'].append({'name':name,'argv':list(map(str,cmd)),
            'exit':result.returncode,'wall_seconds':time.perf_counter()-t})
        verify(packet)
        return result.returncode

    try:
        # New readback, reports and export directories; diagnostics may fail without aborting later diagnostics.
        stage('master-readback',[BLENDER,'--background','--factory-startup','--disable-autoexec',
            '--threads','1','--python-exit-code','1','--python',str(ROOT/'tools/blender/fbx_readback.py'),
            '--',str(packet/MASTER_FBX),str(out/'master-readback.json')])
        stage('master-xview',['uv','run','dt','qa','xview',str(packet/MASTER),
            '--out',str(out/'master-xview.json'),'--blender',BLENDER])
        code = stage('derive',['uv','run','agr','vpm-to-npm','--blender',BLENDER,
            str(packet/'spec.json'),str(out/'atlas'),'--recipe-dir',str(packet/'jobs/TEC26-OKS/scripts'),
            '--cell','512','--pad','8','--then-npm',str(packet/MASTER),
            str(packet/'spec.json'),str(out/'atlas'),str(out/'export/fbx'),'0000',
            '--recipe-dir',str(packet/'jobs/TEC26-OKS/scripts')])
        if code:
            raise RuntimeError(f'derivation exited {code}; no replacement success run')
        fbx = out/'export/fbx/0000_Kpp_1_01.fbx'
        stage('readback',[BLENDER,'--background','--factory-startup','--disable-autoexec',
            '--threads','1','--python-exit-code','1','--python',str(ROOT/'tools/blender/fbx_readback.py'),
            '--',str(fbx),str(out/'readback.json')])
        stage('export-xview',['uv','run','dt','qa','xview',str(fbx),'--out',str(out/'export-xview.json'),
            '--blender',BLENDER])
        stage('validate',['uv','run','agr','validate',str(fbx),'--profile','npm','--scene',
            '--master',str(packet/MASTER_FBX),'--json'])
        record['diagnostics_completed'] = all((out/name).is_file() for name in
            ('master-readback.json','readback.json','master-xview.json','export-xview.json','validate.log'))
        record['quality_status'] = 'not_passed'  # open manual/Max/checker gates, even if machine stages pass
    finally:
        record['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['wall_seconds'] = time.perf_counter()-start
        try:
            record['packet_unchanged'] = verify(packet) == manifest
        except ValueError as exc:
            record['packet_unchanged'] = False
            record['integrity_error'] = str(exc)
        (out/'run.json').write_text(json.dumps(record,indent=2))
        print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]),Path(sys.argv[2]),*sys.argv[3:4])
