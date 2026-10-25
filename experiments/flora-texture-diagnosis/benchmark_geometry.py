"""Benchmark #369 source role decomposition, not botanical acceptance.

Pattern: n/a | new-case: offline comparison on the same 99 copied native records.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/flora'))
from diagnose_texture import guard_outputs
from geometry_parts import parts_and_charts
from sprite_coverage import island_role, uv_components


def compare(records, runs=3):
    if type(runs) is not int or runs<3:
        raise ValueError('at least three runs required')
    result={}
    for method in ('baseline','prototype'):
        timings=[]
        for _ in range(runs):
            start=time.perf_counter();rows=[]
            for tag,key,record in records:
                vertices=np.asarray(record['vertices']);faces=np.asarray(record['faces'])
                if method=='prototype':
                    parts,charts=parts_and_charts(record)
                else:
                    height=float(np.ptp(vertices[:,2]));profile=key.rsplit('_',1)[1]
                    parts=[]
                    for indices in uv_components(record['faces'],len(vertices)):
                        role,reason=island_role(vertices[np.unique(faces[indices])],height,profile)
                        parts.append({'faces':indices,'role':role,'reason':reason})
                    byface={i:part['role'] for part in parts for i in part['faces']}
                    charts=[]
                    for indices in uv_components(record['uvfaces'],len(record['uv'])):
                        roles={byface[i] for i in indices}
                        charts.append({'faces':indices,'role':next(iter(roles)) if len(roles)==1 else 'unknown'})
                expected=list(range(len(faces)))
                if sorted(i for part in parts for i in part['faces'])!=expected:
                    raise ValueError('geometry face accounting failed '+key)
                if sorted(i for chart in charts for i in chart['faces'])!=expected:
                    raise ValueError('UV chart face accounting failed '+key)
                counts=Counter(chart['role'] for chart in charts)
                rows.append({'tag':tag,'object':key,'triangles':len(faces),'charts':len(charts),
                             'roles':dict(counts),'kinds':dict(Counter(p.get('kind','legacy') for p in parts)),
                             'face_accounting':True})
            timings.append(time.perf_counter()-start)
        result[method]={'times_seconds':timings,'median_seconds':statistics.median(timings),
                        'charts':sum(r['charts'] for r in rows),
                        'unknown':sum(r['roles'].get('unknown',0) for r in rows),'rows':rows}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    job=json.loads(args.job.read_text(encoding='utf-8'))
    inventory=Path(job['work'])/job['inventory']
    guard_outputs([args.job,inventory],[args.output])
    raw=inventory.read_bytes();data=json.loads(raw)
    if data.get('failures'):raise ValueError('native inventory contains failures')
    records=[(tag,key,record) for tag in ('original','florio')
             for key,record in data['scenes'][tag]['records'].items()]
    if len(records)!=99 or len({key for _,key,_ in records})!=99:
        raise ValueError('99 unique source objects required')
    result=compare(records)
    result.update(accepted=False,inventory_sha256=hashlib.sha256(raw).hexdigest(),
                  scope='geometry/chart diagnostic only; no semantic calibration or threshold change')
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({method:{k:v for k,v in result[method].items() if k!='rows'}
                      for method in ('baseline','prototype')}))


if __name__=='__main__':main()
