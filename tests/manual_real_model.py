"""Explicit opt-in live test: python tests/manual_real_model.py (requires env key)."""
import json
import os
import sys
import threading
import urllib.request
import urllib.error
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from http.server import ThreadingHTTPServer
from src import web

if not os.getenv('OPENAI_API_KEY'):
    raise SystemExit('Set OPENAI_API_KEY before explicitly running this live test.')
server = ThreadingHTTPServer(('127.0.0.1', 0), web.DashboardHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
token = str(uuid.uuid4())
base = f'http://127.0.0.1:{server.server_port}'

def request(path, body=None):
    req = urllib.request.Request(base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json','X-Session-Token':token})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8').replace(os.environ['OPENAI_API_KEY'], '[redacted]')
        raise RuntimeError(f'HTTP {exc.code}: {detail}') from None

try:
    assert request('/api/health')['model_configured']
    session = request('/api/init', {'goal':'准备 Python 后端开发面试，安排 4 小时，涵盖 HTTP、数据库和项目复盘。','use_llm':True})
    assert session['model_mode'] in ('openai','chat_compatible')
    assert session['planning_trace'][-1]['stage'] == 'validated'
    task_count = len(session['tasks'])
    for _ in range(task_count):
        if all(t['status'] == 'done' for t in session['tasks']): break
        assert session['ready_tasks'], 'No ready task; execution blocked'
        session = request('/api/run', {})
    assert all(t['status'] == 'done' for t in session['tasks'])
    restored = request('/api/session')
    assert restored['events'] == session['events']
    assert os.environ['OPENAI_API_KEY'] not in json.dumps(session)
    print(json.dumps({'success':True,'model':os.getenv('OPENAI_MODEL'),
        'mode':session['model_mode'],'task_count':task_count,
        'tools':[t['tool'] for t in session['tasks']],
        'usage':session['planning_trace'][1].get('usage'),
        'duration_ms':session['planning_trace'][1].get('duration_ms'),
        'completion':session['review'],'credential_in_output':False}, ensure_ascii=False, indent=2))
finally:
    (web.SESSION_PATH.parent / 'sessions' / f'{token}.json').unlink(missing_ok=True)
    server.shutdown()
    server.server_close()
