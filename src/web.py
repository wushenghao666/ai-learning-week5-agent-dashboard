"""Local or cloud browser dashboard for the persistent study agent."""
from __future__ import annotations
import argparse
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .agent import init_session, review, run_session
from .llm import LLMError, simulation_plan, local_planning_trace, model_mode
from .memory import Session

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
SESSION_PATH = ROOT / 'outputs' / 'session.json'
ALLOWED_ORIGIN = os.getenv('AGENT_ALLOWED_ORIGIN', '*')
STATE_LOCK = threading.RLock()
MODEL_CALLS = []


def session_payload(session: Session) -> dict:
    data = json.loads(json.dumps(session, default=lambda o: o.__dict__, ensure_ascii=False))
    data['review'] = review(session)
    data['ready_tasks'] = [task.id for task in session.ready_tasks()]
    return data

class DashboardHandler(BaseHTTPRequestHandler):
    def _session_path(self) -> Path:
        token = self.headers.get('X-Session-Token', '')
        if not token:
            if os.getenv('RENDER'):
                raise ValueError('需要会话编号')
            return SESSION_PATH
        if not re.fullmatch(r'[a-f0-9-]{36}', token):
            raise ValueError('会话编号无效')
        return SESSION_PATH.parent / 'sessions' / f'{token}.json'

    def _cors(self) -> None:
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Session-Token')
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
        if length < 0 or length > 16384:
            raise ValueError('请求内容过长')
        result = json.loads(self.rfile.read(length) or b'{}')
        if not isinstance(result, dict):
            raise ValueError('请求必须为对象')
        return result

    def do_OPTIONS(self) -> None:
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == '/api/health':
            return self._json({'ok': True, 'model_configured': bool(os.getenv('OPENAI_API_KEY'))})
        if path == '/api/session':
            try:
                session_path = self._session_path()
            except ValueError as exc:
                return self._json({'error': str(exc)}, 400)
            with STATE_LOCK:
                if session_path.exists():
                    return self._json(session_payload(Session.load(session_path)))
            return self._json({'session': None})
        target = (WEB / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
        if not target.is_relative_to(WEB.resolve()):
            return self._json({'error': '页面不存在'}, 404)
        if target.exists() and target.is_file():
            body = target.read_bytes()
            content_type = 'text/html; charset=utf-8' if target.suffix == '.html' else 'text/css; charset=utf-8' if target.suffix == '.css' else 'application/javascript; charset=utf-8'
            self.send_response(200); self._cors(); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        self._json({'error': '页面不存在'}, 404)

    def do_POST(self) -> None:
        origin = self.headers.get('Origin')
        if ALLOWED_ORIGIN != '*' and origin and origin != ALLOWED_ORIGIN:
            return self._json({'error': '来源域名未被允许'}, 403)
        with STATE_LOCK:
            self._post_locked()

    def _post_locked(self) -> None:
        path = urlparse(self.path).path
        planning_trace = []
        try:
            session_path = self._session_path()
            if path == '/api/init':
                body = self._body(); goal = str(body.get('goal', '')).strip(); use_llm = bool(body.get('use_llm', False))
                if not 1 <= len(goal) <= 2000: return self._json({'error': '目标长度需要在 1 到 2000 字之间'}, 400)
                if use_llm and not os.getenv('OPENAI_API_KEY'):
                    session = Session.create(goal, [task.to_dict() for task in simulation_plan(goal)])
                    session.model_mode = 'simulation'
                    session.model_notice = '未配置 OPENAI_API_KEY，当前使用本地模拟模型。结果用于演示流程，不会产生真实模型调用费用。'
                    session.planning_trace = local_planning_trace(goal, [t.__dict__ for t in session.tasks], 'simulation')
                    session.save(session_path)
                    return self._json(session_payload(session))
                if use_llm:
                    now = time.time()
                    MODEL_CALLS[:] = [stamp for stamp in MODEL_CALLS if now - stamp < 86400]
                    if len(MODEL_CALLS) >= int(os.getenv('AGENT_DAILY_MODEL_LIMIT', '20')):
                        return self._json({'error': '今日模型调用额度已用完，请使用规则规划'}, 429)
                    MODEL_CALLS.append(now)
                session = init_session(goal, str(session_path), use_llm, allow_fallback=False, trace=planning_trace)
                session.model_mode = model_mode() if use_llm else 'rules'
                session.save(session_path)
                return self._json(session_payload(session))
            if path == '/api/run':
                if not session_path.exists(): return self._json({'error': '请先创建学习计划'}, 400)
                session = Session.load(session_path); outputs = run_session(session); session.save(session_path)
                result = session_payload(session); result['outputs'] = outputs; return self._json(result)
            if path == '/api/reset':
                session_path.unlink(missing_ok=True); return self._json({'session': None})
            self._json({'error': '接口不存在'}, 404)
        except LLMError as exc:
            self._json({'error': str(exc), 'planning_trace': planning_trace}, 503)
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

