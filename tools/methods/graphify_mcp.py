"""new-case: read-only stdio MCP adapter for project-local graphify CLI queries."""
import json
import os
import subprocess
import sys


def serve(executable, graph):
    for line in sys.stdin:
        request = json.loads(line)
        if 'id' not in request:
            continue
        method = request.get('method')
        if method == 'initialize':
            result = {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},
                      'serverInfo':{'name':'local-graphify','version':'1'}}
        elif method == 'tools/list':
            result = {'tools':[{'name':name,'description':f'Local graphify {name}; no network, no writes.',
                'inputSchema':{'type':'object','properties':{key:{'type':'string'} for key in keys},
                               'required':keys,'additionalProperties':False}}
                for name,keys in [('query',['question']),('path',['source','target']),('explain',['concept'])]]}
        elif method == 'tools/call':
            params=request['params']; name=params['name']; args=params.get('arguments',{})
            keys={'query':['question'],'path':['source','target'],'explain':['concept']}
            if name not in keys or set(args) != set(keys[name]) or any(not isinstance(v,str) or not v.strip() or v.startswith('-') for v in args.values()):
                result={'content':[{'type':'text','text':'Invalid graph query arguments'}],'isError':True}
            else:
                command=[executable,name,*[args[k] for k in keys[name]],'--graph',graph]
                if name=='query': command+=['--budget','2000']
                env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
                p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90,env=env)
                result={'content':[{'type':'text','text':p.stdout+p.stderr}],'isError':p.returncode not in (0,3,4)}
        elif method == 'ping': result={}
        else:
            print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32601,'message':'Method not found'}}),flush=True)
            continue
        print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)


if __name__=='__main__':
    serve(sys.argv[1],sys.argv[2])
