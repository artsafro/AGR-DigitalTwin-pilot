"""new-case: deterministic controls for the isolated agent lookup experiment."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

PATH = Path(__file__).with_name('agent_lookup.py')

@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location('agent_lookup', PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def matrix():
    return [dict(question_id=f'Q{i:02}', variant=v, model='same', session_id=f'{v}{i}',
                 status='completed', correct='correct', input_tokens=10, cache_read_tokens=20,
                 cache_creation_tokens=30, output_tokens=5, wall_s=1.0, files_read=[])
            for i in range(1, 21) for v in 'ABC']


def test_questions(mod):
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / 'docs/methods/sources/agent-lookup/questions.json').read_text())
    qs = data['questions']
    assert len(qs) == 20
    assert {k: sum(q['category'] == k for q in qs) for k in ('repo','job','api')} == {'repo':8,'job':6,'api':6}
    for q in qs:
        path, line = q['proof'].rsplit(':', 1)
        assert (root / path).read_text(encoding='utf-8').splitlines()[int(line)-1].strip()
        assert q['answer'] is not None


def test_matrix(mod):
    mod.validate_matrix(matrix())


@pytest.mark.parametrize('mutation', ['empty','partial','duplicate','unknown','error','session','model','nan','negative','bool','score'])
def test_invalid_matrix(mod, mutation):
    rows = matrix()
    if mutation == 'empty': rows = []
    elif mutation == 'partial': rows.pop()
    elif mutation == 'duplicate': rows[-1] = copy.deepcopy(rows[0])
    elif mutation == 'unknown': rows[0]['variant'] = 'D'
    elif mutation == 'error': rows[0]['status'] = 'api_error'
    elif mutation == 'session': rows[0]['session_id'] = rows[1]['session_id']
    elif mutation == 'model': rows[0]['model'] = 'other'
    elif mutation == 'nan': rows[0]['wall_s'] = float('nan')
    elif mutation == 'negative': rows[0]['input_tokens'] = -1
    elif mutation == 'bool': rows[0]['input_tokens'] = True
    elif mutation == 'score': rows[0]['correct'] = 'not_run'
    with pytest.raises(ValueError): mod.validate_matrix(rows)


def test_session_environment(mod,tmp_path,monkeypatch):
    cred=tmp_path/'credentials.json'
    cred.write_text(json.dumps({'claudeAiOauth':{'accessToken':'synthetic-token'}}))
    monkeypatch.setenv('CLAUDE_CONFIG_DIR','forbidden-global')
    monkeypatch.setenv('ANTHROPIC_API_KEY','synthetic-other-provider')
    env=mod.session_environment(tmp_path/'A.json',cred)
    assert env['CLAUDE_CONFIG_DIR']==str(tmp_path/'claude-state')
    assert env['CLAUDE_CODE_OAUTH_TOKEN']=='synthetic-token'
    assert 'ANTHROPIC_API_KEY' not in env
    cred.write_text('{}')
    with pytest.raises(ValueError): mod.session_environment(tmp_path/'A.json',cred)


def test_extract_json(mod):
    assert mod.extract_json('Evidence.\n```json\n{"answer": 0.002}\n```') == {'answer': 0.002}
    assert mod.extract_json('Evidence.\n```yaml\n- {area_max: 0.25}\n```\n```json\n{"answer": 1125000}\n```') == {'answer':1125000}
    with pytest.raises(ValueError): mod.extract_json('```json\n{"a":1}\n```\n```json\n{"a":2}\n```')
    with pytest.raises(ValueError): mod.extract_json('No answer')
    with pytest.raises(ValueError): mod.extract_json('{"answer": 1} {"answer": 2}')


def test_tokens(mod):
    assert mod.total_tokens(matrix()[0]) == 65
    with pytest.raises(ValueError): mod.total_tokens({'input_tokens':1})


@pytest.mark.parametrize('answer,expected', [(0.002,'correct'),(0.003,'wrong'),('0.002','wrong'),(True,'wrong'),(float('nan'),'wrong')])
def test_numeric(mod,answer,expected):
    assert mod.score_number(answer,0.002) == expected
    with pytest.raises(ValueError): mod.score_number(1,float('inf'))


@pytest.mark.parametrize('acc,tokens,expected', [(1.0,100,False),(1.1,100,True),(1,70,True),(1.099,70.001,False),(1,0,True)])
def test_adoption(mod,acc,tokens,expected):
    assert mod.eligible(acc,tokens,1.0,100) is expected


def test_output(mod,tmp_path):
    inp = tmp_path/'input.json'; inp.write_text('untouched')
    with pytest.raises((ValueError,FileExistsError)): mod.write_new(inp,'clobber', [inp])
    assert inp.read_text() == 'untouched'
    out = tmp_path/'out.json'; mod.write_new(out,'new',[inp])
    with pytest.raises(FileExistsError): mod.write_new(out,'bad',[inp])
    assert out.read_text() == 'new'
    alias = tmp_path/'sub'/'..'/'input.json'
    with pytest.raises(ValueError): mod.write_new(alias,'bad',[inp])


@pytest.mark.parametrize('bad', [None,'duplicate','invalid'])
def test_judge_join(mod,tmp_path,monkeypatch,bad):
    docs = tmp_path/'docs'; docs.mkdir()
    (docs/'questions.json').write_text(json.dumps({'questions':[{'id':f'Q{i:02}','question':'synthetic','answer':'truth'} for i in range(1,21)]}))
    rowsdir=tmp_path/'rows'; rowsdir.mkdir()
    for row in matrix():
        row.update(category='api' if int(str(row['question_id'])[1:])>=15 else 'repo',answer='synthetic')
        if row['category']=='api': row['correct']='pending_judge'
        (rowsdir/f'{row["question_id"]}-{row["variant"]}.json').write_text(json.dumps(row))
    grades=[dict(id=f'R{i:02}',grade='correct',reason='synthetic test') for i in range(18)]
    if bad=='duplicate': grades[-1]['id']='R00'
    if bad=='invalid': grades[-1]['grade']='not_run'
    end=dict(result=json.dumps({'grades':grades}),session_id='judge',usage={})
    monkeypatch.setattr(mod,'DOCS',docs)
    monkeypatch.setattr(mod,'session',lambda *a,**kw:(end,[],1,[]))
    if bad:
        with pytest.raises(ValueError): mod.grade(tmp_path)
        assert not (docs/'results.jsonl').exists()
    else:
        mod.grade(tmp_path)
        mod.validate_matrix([json.loads(line) for line in (docs/'results.jsonl').read_text().splitlines()])


def test_stale_manifest(mod,tmp_path):
    (tmp_path/'measurement-manifest.json').write_text('{"model":"stale"}')
    with pytest.raises(ValueError,match='stale receipts'):
        mod.run(tmp_path)


def test_graph_adapter(tmp_path):
    script = PATH.with_name('graphify_mcp.py')
    requests = [dict(jsonrpc='2.0',id=1,method='initialize'),
                dict(jsonrpc='2.0',id=2,method='tools/list'),
                dict(jsonrpc='2.0',id=3,method='tools/call',params={'name':'query','arguments':{'question':'--delete'}}),
                dict(jsonrpc='2.0',id=4,method='ping'),
                dict(jsonrpc='2.0',id=5,method='unknown')]
    p = subprocess.run([sys.executable,str(script),'must-not-run.exe','absent.json'],
        input='\n'.join(json.dumps(r) for r in requests)+'\n',text=True,capture_output=True)
    assert p.returncode == 0
    responses = [json.loads(line) for line in p.stdout.splitlines()]
    assert responses[0]['result']['serverInfo']['name'] == 'local-graphify'
    assert {t['name'] for t in responses[1]['result']['tools']} == {'query','path','explain'}
    assert responses[2]['result']['isError'] is True
    assert responses[3]['result'] == {}
    assert responses[4]['error']['code'] == -32601


def test_cli(mod,tmp_path):
    inp = tmp_path/'rows.jsonl'
    inp.write_text('\n'.join(json.dumps(x) for x in matrix()))
    cmd = [sys.executable,str(PATH),'validate',str(inp)]
    assert subprocess.run(cmd,capture_output=True).returncode == 0
    inp.write_text('')
    assert subprocess.run(cmd,capture_output=True).returncode != 0
