"""Fresh-process fail-closed controls for the Vatutino-only v015 producer."""
from pathlib import Path
import subprocess,sys
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'jobs/VATUTINO-SITE/build_ground_v015.py'


def test_v015_driver_exposes_a_real_fresh_process_cli():
    assert SCRIPT.exists(),'the checkpoint must have a reproducible producer, not scratch-only code'
    r=subprocess.run([sys.executable,str(SCRIPT),'--help'],capture_output=True,text=True)
    assert r.returncode==0
    for text in ('--adapter-json','--source-master','--d150-reference','--out'):
        assert text in r.stdout


@pytest.mark.parametrize('alias',['direct','relative','report','hardlink'])
def test_v015_output_alias_refuses_before_any_write(tmp_path,alias):
    assert SCRIPT.exists(),'v015 producer missing'
    source=tmp_path/'source.json';source.write_text('{}')
    out=tmp_path/'out'
    if alias=='direct':out=source
    elif alias=='relative':out=tmp_path/'x'/'..'/'source.json'
    else:
        out.mkdir()
        if alias=='report':(out/'report.json').write_text('{}')
        else:(out/'master-npm.json').hardlink_to(source)
    before={p.name:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    cmd=[sys.executable,str(SCRIPT),'--adapter-json',str(source),'--source-master',str(source),
         '--d150-reference',str(source),'--out',str(out)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode!=0 and ('alias' in r.stderr or 'new output' in r.stderr)
    after={p.name:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert before==after
