import json
import tempfile
import threading
import unittest
import uuid
import shutil
from pathlib import Path
from urllib import request, error
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from src import web

class WebTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).resolve().parent / ('test-data-' + uuid.uuid4().hex)
        self.directory.mkdir()
        self.path_patch = patch.object(web, 'SESSION_PATH', self.directory/'session.json')
        self.path_patch.start()
        self.env_patch = patch.dict('os.environ', {'OPENAI_API_KEY':'', 'RENDER':''})
        self.env_patch.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), web.DashboardHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.token = str(uuid.uuid4())

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.path_patch.stop(); self.env_patch.stop(); shutil.rmtree(self.directory)

    def call(self, path, payload=None, token=None, method=None):
        headers={'Content-Type':'application/json', 'X-Session-Token':token or self.token}
        req=request.Request(self.url+path, data=None if payload is None else json.dumps(payload).encode(), headers=headers, method=method or ('POST' if payload is not None else 'GET'))
        try:
            with request.urlopen(req) as r: return r.status, json.loads(r.read())
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_simulation_recovers_and_completes(self):
        status, session=self.call('/api/init', {'goal':'设计网站，安排 8 小时','use_llm':True})
        self.assertEqual(status,200); self.assertEqual(session['model_mode'],'simulation')
        self.assertIn('OPENAI_API_KEY',session['model_notice'])
        for rate in (.25,.5,.75,1.0):
            _, session=self.call('/api/run',{})
            self.assertEqual(session['review']['completion_rate'],rate)
            self.assertEqual(session['model_mode'],'simulation')
        self.assertEqual(len(session['events']),4)
        self.assertIn('4 天',session['tasks'][2]['result'])
        self.assertEqual(self.call('/api/session')[1]['model_notice'],session['model_notice'])
        self.call('/api/reset',{})
        self.assertIsNone(self.call('/api/session')[1]['session'])

    def test_sessions_are_isolated(self):
        self.call('/api/init',{'goal':'第一位用户'})
        second=str(uuid.uuid4())
        self.assertIsNone(self.call('/api/session',token=second)[1]['session'])
        self.call('/api/init',{'goal':'第二位用户'},token=second)
        self.assertEqual(self.call('/api/session')[1]['goal'],'第一位用户')

    def test_invalid_requests(self):
        self.assertEqual(self.call('/api/init',{'goal':''})[0],400)
        self.assertEqual(self.call('/api/init',{'goal':'x'*2001})[0],400)
        self.assertEqual(self.call('/api/init',{'goal':'x'},token='../private')[0],400)
        self.assertEqual(self.call('/api/run',{})[0],400)
        self.assertEqual(self.call('/api/init',[])[0],400)
        self.assertEqual(self.call('/../src/llm.py')[0],404)

    def test_failed_tool_blocks_dependents(self):
        self.call('/api/init',{'goal':'学习，安排 0 小时'})
        for _ in range(3): _, session=self.call('/api/run',{})
        self.assertEqual(session['tasks'][2]['status'],'failed')
        self.assertEqual(session['tasks'][3]['status'],'pending')
        self.assertEqual(session['tasks'][2]['attempts'],2)

if __name__ == '__main__': unittest.main()
