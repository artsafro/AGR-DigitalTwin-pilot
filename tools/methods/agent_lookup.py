"""new-case: isolated, auditable 20-question agent lookup comparison (#712)."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import time

MODEL = 'claude-sonnet-4-6'
SOURCE = '4c863c1a4616f1812595536d0507f53034e9acfe'
ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs/methods/sources/agent-lookup'
FIELDS = ('input_tokens','cache_read_tokens','cache_creation_tokens','output_tokens')
SYSTEM = '''You answer a single lookup question about the AGR pilot or a public library API.
Use only the provided lookup tools. Do not modify files. Do not read outside the current
repository. Do not look for benchmark questions, answer keys or prior sessions.
If graphify tools are available, query the graph first; fall back to repository search.
If context7 tools are available, consult them for public API/library questions only;
never send repository text, private source or drawings to context7. Repo/job questions
must use local search. Be concise. Return a JSON object with answer (a JSON number for
numeric questions, a string for API explanations), evidence (file:line or public docs),
and uncertainty. If unable to find support, say so; do not invent citations.'''


def finite(value):
    return type(value) in (int,float) and math.isfinite(value) and value >= 0


def total_tokens(row):
    if any(k not in row or not finite(row[k]) or int(row[k]) != row[k] for k in FIELDS):
        raise ValueError('missing or invalid token accounting')
    return sum(row[k] for k in FIELDS)


def score_number(answer, expected):
    if not finite(expected):
        raise ValueError('invalid numeric ground truth')
    return 'correct' if finite(answer) and answer == expected else 'wrong'


def eligible(accuracy, tokens, base_accuracy, base_tokens):
    return bool((base_accuracy > 0 and accuracy >= base_accuracy * 1.10) or
                (base_tokens > 0 and tokens <= base_tokens * .70))


def validate_matrix(rows):
    expected = {(f'Q{i:02}',v) for i in range(1,21) for v in 'ABC'}
    pairs = [(r.get('question_id'),r.get('variant')) for r in rows]
    if len(pairs) != 60 or set(pairs) != expected:
        raise ValueError('expected 60 unique Q01..Q20 x A/B/C pairs')
    if len({r.get('session_id') for r in rows}) != 60 or any(not r.get('session_id') for r in rows):
        raise ValueError('sessions must be fresh and nonempty')
    if len({r.get('model') for r in rows}) != 1 or any(not r.get('model') for r in rows):
        raise ValueError('answer models differ or are missing')
    for r in rows:
        total_tokens(r)
        if r.get('status') != 'completed' or r.get('correct') not in ('correct','partly','wrong'):
            raise ValueError('unmeasured/error/invalid grade cannot count as measured')
        if not finite(r.get('wall_s')) or not isinstance(r.get('files_read'),list):
            raise ValueError('invalid wall time or missing file-read audit')


def write_new(path, text, inputs=()):
    path = Path(path)
    if any(path.resolve() == Path(p).resolve() or
           (path.exists() and Path(p).exists() and path.samefile(p)) for p in inputs):
        raise ValueError('output aliases input')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:
        f.write(text)


def extract_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n',1)[1].rsplit('```',1)[0]
    return json.loads(text)


def session(prompt, cwd, config, log, model=MODEL, tools='Read,Grep,Glob'):
    cmd = [shutil.which('claude') or 'claude','-p',prompt,'--model',model,
           '--no-session-persistence','--disable-slash-commands','--setting-sources','',
           '--settings','{"disableAllHooks":true,"autoMemoryEnabled":false}',
           '--strict-mcp-config','--mcp-config',str(config),'--tools',tools,
           '--allowedTools','Read,Grep,Glob,mcp__graphify__query,mcp__graphify__path,mcp__graphify__explain,mcp__context7__resolve-library-id,mcp__context7__query-docs',
           '--permission-mode','dontAsk','--system-prompt',SYSTEM,
           '--output-format','stream-json','--verbose']
    start = time.perf_counter()
    env = os.environ.copy(); env.pop('CLAUDE_CODE_SIMPLE',None)
    p = subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',timeout=600)
    wall = time.perf_counter()-start
    write_new(log,p.stdout)
    write_new(str(log)+'.stderr',p.stderr)
    events = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
    end = next((x for x in reversed(events) if x.get('type') == 'result'),{})
    if p.returncode or end.get('is_error') or end.get('terminal_reason') != 'completed':
        raise RuntimeError(f'Claude failed; evidence {log}; {end.get("result",p.stderr)[-500:]}')
    if end.get('permission_denials'):
        raise RuntimeError(f'tool permission denied; evidence {log}')
    return end,events,wall,cmd


def audit(events):
    calls = []
    for event in events:
        for block in event.get('message',{}).get('content',[]):
            if isinstance(block,dict) and block.get('type') == 'tool_use':
                calls.append({'name':block['name'],'input':block.get('input',{})})
    return calls


def run(work):
    work = Path(work)
    questions = json.loads((DOCS/'questions.json').read_text())['questions']
    subprocess.run(['git','diff','--exit-code','HEAD','--',str(DOCS/'questions.json')],cwd=ROOT,check=True)
    if subprocess.check_output(['git','rev-parse','HEAD:docs/methods/sources/agent-lookup/questions.json'],cwd=ROOT).strip() == b'':
        raise ValueError('questions must be committed')
    write_new(work/'run-start.json',json.dumps({'model':MODEL,'source':SOURCE,'started_unix':time.time(),
        'questions_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}))
    for i,q in enumerate(questions):
        for v in ('ABC'[i%3:]+'ABC'[:i%3]):
            repo = work / {'A':'baseline','B':'repo','C':'context7-repo'}[v]
            if subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip() != SOURCE:
                raise ValueError('source snapshot changed')
            prompt = f'Question {q["id"]} (category: {q["category"]}): {q["question"]}\nReturn only the requested JSON answer and evidence.'
            end,events,wall,cmd = session(prompt,repo,work/f'{v}.json',work/'raw'/f'{q["id"]}-{v}.jsonl')
            calls = audit(events); u=end['usage']
            ans = extract_json(end['result'])
            row = dict(question_id=q['id'],category=q['category'],variant=v,model=MODEL,
                session_id=end['session_id'],status='completed',answer=ans['answer'],evidence=ans.get('evidence'),
                uncertainty=ans.get('uncertainty'),input_tokens=u['input_tokens'],
                cache_read_tokens=u['cache_read_input_tokens'],cache_creation_tokens=u['cache_creation_input_tokens'],
                output_tokens=u['output_tokens'],wall_s=wall,files_read=[c['input']['file_path'] for c in calls if c['name']=='Read'],
                tool_calls=calls,correct=score_number(ans['answer'],q['answer']) if q['scoring']=='number' else 'pending_judge',
                cost_usd=end['total_cost_usd'],command=cmd)
            write_new(work/'rows'/f'{q["id"]}-{v}.json',json.dumps(row,ensure_ascii=False,indent=2))
            print(f'{q["id"]} {v}: {row["correct"]}, {total_tokens(row)} tokens, {wall:.2f}s',flush=True)


def summarize(rows):
    validate_matrix(rows)
    return {v:dict(correct=sum(r['correct']=='correct' for r in rows if r['variant']==v),
         partly=sum(r['correct']=='partly' for r in rows if r['variant']==v),
         accuracy=sum(r['correct']=='correct' for r in rows if r['variant']==v)/20,
         median_tokens=statistics.median(total_tokens(r) for r in rows if r['variant']==v),
         median_wall_s=statistics.median(r['wall_s'] for r in rows if r['variant']==v)) for v in 'ABC'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['run','validate','summarize']); parser.add_argument('path')
    args=parser.parse_args()
    if args.action=='run': run(args.path)
    else:
        rows=[json.loads(line) for line in Path(args.path).read_text(encoding='utf-8').splitlines() if line.strip()]
        validate_matrix(rows)
        print(json.dumps(summarize(rows) if args.action=='summarize' else {'measured_rows':len(rows)},indent=2))
