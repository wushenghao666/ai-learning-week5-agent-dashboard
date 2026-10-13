"""Opt-in real model regression; --base URL tests an already configured deployment."""
import argparse
import json
import re
import sys
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import web
from http.server import ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument('--base')
parser.add_argument('--rounds', type=int, default=2)
parser.add_argument('--output', default='outputs/scenario-regression.json')
args = parser.parse_args()
server = None
if not args.base:
    server = ThreadingHTTPServer(('127.0.0.1', 0), web.DashboardHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
base = args.base or f'http://127.0.0.1:{server.server_port}'
goals = re.findall(r'data-goal="([^"]+)"', (web.WEB / 'index.html').read_text(encoding='utf-8'))

def call(path, token, body=None):
    req = urllib.request.Request(base+path, data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json','Origin':'https://wushenghao666.github.io','X-Session-Token':token})
    try:
        with urllib.request.urlopen(req, timeout=150) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)

results=[]
try:
    for round_number in range(args.rounds):
        for goal in goals:
            token=str(uuid.uuid4())
            result={'round':round_number+1,'goal':goal}
            try:
                status, session=call('/api/init',token,{'goal':goal,'use_llm':True})
                result['init_status']=status
                result['planning_trace']=session.get('planning_trace',[])
                assert status == 200, session.get('error')
                assert session['model_mode'] in ('openai','chat_compatible'), 'Expected real model'
                assert [t['tool'] for t in session['tasks']] == ['summarize','checklist','time_budget','review_prompt']
                hours=re.search(r'(\d+)\s*小时',goal)
                budget=session['tasks'][2]['argument']
                assert budget['hours']==int(hours.group(1)) if hours else budget=='未提供小时数'
                for _ in range(len(session['tasks'])):
                    if all(t['status']=='done' for t in session['tasks']): break
                    assert session['ready_tasks'], 'Dependencies blocked'
                    status,session=call('/api/run',token,{})
                    assert status == 200,session
                assert all(t['status']=='done' for t in session['tasks']), 'Tool failure'
                assert session['review']['tool_success_rate']==1
                assert call('/api/session',token)[1]['events']==session['events']
                result.update(success=True,tasks=session['tasks'],review=session['review'])
            except Exception as exc:
                result.update(success=False,error=str(exc))
            finally:
                call('/api/reset',token,{})
            results.append(result)
            Path(args.output).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in result.items() if k not in ('planning_trace','tasks','review')},ensure_ascii=False),flush=True)
finally:
    if server: server.shutdown(); server.server_close()
print(f'Passed {sum(r["success"] for r in results)}/{len(results)}',flush=True)
sys.exit(0 if all(r['success'] for r in results) else 1)
