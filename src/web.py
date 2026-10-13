"""Local or cloud browser dashboard for the persistent study agent."""
from __future__ import annotations
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .agent import init_session, review, run_session
from .llm import LLMError, simulation_plan
from .memory import Session

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
SESSION_PATH = ROOT / 'outputs' / 'session.json'
ALLOWED_ORIGIN = os.getenv('AGENT_ALLOWED_ORIGIN', '*')


def session_payload(session: Session) -> dict:
    data = json.loads(json.dumps(session, default=lambda o: o.__dict__, ensure_ascii=False))
    data['review'] = review(session)
    data['ready_tasks'] = [task.id for task in session.ready_tasks()]
    return data

class DashboardHandler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get('Content-Length', '0'))
        return json.loads(self.rfile.read(length) or b'{}')

    def do_OPTIONS(self) -> None:
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == '/api/health':
            return self._json({'ok': True, 'model_configured': bool(os.getenv('OPENAI_API_KEY'))})
        if path == '/api/session':
            if SESSION_PATH.exists():
                return self._json(session_payload(Session.load(SESSION_PATH)))
            return self._json({'session': None})
        target = WEB / ('index.html' if path == '/' else path.lstrip('/'))
        if target.exists() and target.is_file():
            body = target.read_bytes()
            content_type = 'text/html; charset=utf-8' if target.suffix == '.html' else 'text/css; charset=utf-8' if target.suffix == '.css' else 'application/javascript; charset=utf-8'
            self.send_response(200); self._cors(); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        self._json({'error': '页面不存在'}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == '/api/init':
                body = self._body(); goal = str(body.get('goal', '')).strip(); use_llm = bool(body.get('use_llm', False))
                if not goal: return self._json({'error': '学习目标不能为空'}, 400)
                if use_llm and not os.getenv('OPENAI_API_KEY'):
                    session = Session.create(goal, [task.to_dict() for task in simulation_plan(goal)])
                    session.model_mode = 'simulation'
                    session.model_notice = '未配置 OPENAI_API_KEY，当前使用本地模拟模型。结果用于演示流程，不会产生真实模型调用费用。'
                    session.save(SESSION_PATH)
                    return self._json(session_payload(session))
                session = init_session(goal, str(SESSION_PATH), use_llm, allow_fallback=False)
                session.model_mode = 'openai' if use_llm else 'rules'
                session.save(SESSION_PATH)
                return self._json(session_payload(session))
            if path == '/api/run':
                if not SESSION_PATH.exists(): return self._json({'error': '请先创建学习计划'}, 400)
                session = Session.load(SESSION_PATH); outputs = run_session(session); session.save(SESSION_PATH)
                result = session_payload(session); result['outputs'] = outputs; return self._json(result)
            if path == '/api/reset':
                SESSION_PATH.unlink(missing_ok=True); return self._json({'session': None})
            self._json({'error': '接口不存在'}, 404)
        except LLMError as exc:
            self._json({'error': str(exc)}, 503)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._json({'error': str(exc)}, 400)

    def log_message(self, format: str, *args: object) -> None:
        return

def serve(host: str = '127.0.0.1', port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f'学习 Agent Web 应用：http://{host}:{port}')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--host', default=os.getenv('HOST', '127.0.0.1')); parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '8000')))
    args = parser.parse_args(); serve(args.host, args.port)

