"""Prepare private copies/job for #369; no authored maps or source writes.

Pattern: n/a | new-case: lossless PNG decoder control for native Flora diagnosis.
Indexed PNGs are re-encoded ONLY in scratch, with exact decoded RGBA equality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from PIL import Image


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def prepare(args):
    work=args.work.resolve()
    sources=[args.union,args.florio,args.library,*args.light_fbx.glob('*.fbx')]
    if len(sources)!=6 or any(not p.is_file() or work==p.resolve() or work in p.resolve().parents for p in sources):
        raise ValueError('three scenes + three light FBX required; scratch must not contain inputs')
    work.mkdir(parents=True,exist_ok=False)
    job={'work':str(work),'species':json.loads(args.catalogue.read_text(encoding='utf-8'))['species'],
         'selected':[101,102,103,105,204,225],'scenes':[],'fbxs':[],
         'hashes_before':{},'bitmap_copies':{},'diagnostic_decode':{},'render_folder':'renders-v001'}
    def copy(source,target):
        source=source.resolve();target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise ValueError('duplicate copied path '+str(target))
        job['hashes_before'][str(source)]=sha(source)
        shutil.copy2(source,target)
        if sha(target)!=job['hashes_before'][str(source)]:raise ValueError('copy mismatch')
    for tag,source in zip(('original','florio','ours'),sources[:3]):
        target=work/tag/source.name;copy(source,target)
        maps=work/tag/'maps';maps.mkdir(exist_ok=True)
        folder=source.parent/'maps' if tag=='original' else source.parent
        if tag!='ours':
            candidates=folder.iterdir() if tag=='original' else folder.glob('*.png')
            for p in candidates:
                if p.is_file():copy(p,maps/p.name)
        job['scenes'].append({'tag':tag,'copy':str(target),'source':str(source.resolve()),'maps':str(maps)})
    for source in sources[3:]:
        target=work/source.name;copy(source,target);job['fbxs'].append(str(target))
    for species in job['species']:
        for slot in ('diffuse','opacity'):
            if not species['maps'][slot]:continue
            source=Path(species['maps'][slot]);target=work/'ours/maps'/source.parent.name/source.name
            key=str(source).replace('\\','/').lower()
            if key not in job['bitmap_copies']:copy(source,target)
            job['bitmap_copies'][key]=str(target)
    for p in list(work.rglob('*.png')):
        image=Image.open(p)
        if image.mode!='P':continue
        target=work/'decoded'/p.relative_to(work);target.parent.mkdir(parents=True,exist_ok=True)
        rgba=image.convert('RGBA');rgba.save(target)
        if rgba.tobytes()!=Image.open(target).convert('RGBA').tobytes():raise ValueError('decoder changed pixels')
        job['diagnostic_decode'][str(p).replace('\\','/').lower()]=str(target)
    (work/'job.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Prepared',work/'job.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('union','florio','library','light-fbx','catalogue','work'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();prepare(args)


if __name__=='__main__':main()
