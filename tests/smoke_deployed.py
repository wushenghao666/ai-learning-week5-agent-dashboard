"""Public smoke checks using disposable, isolated test sessions."""
import json
import uuid
from urllib import request, error
BASE = 'https://ai-learning-week5-agent-dashboard.onrender.com'
ORIGIN = 'https://wushenghao666.github.io'
def call(path, token, payload=None, method=None):
    req = request.Request(BASE+path, data=None if payload is None else json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json','Origin':ORIGIN,'X-Session-Token':token}, method=method or ('POST' if payload is not None else 'GET'))
    try:
        with request.urlopen(req, timeout=60) as r:
            assert r.headers.get('Access-Control-Allow-Origin') == ORIGIN
            return r.status, json.loads(r.read() or '{}')
    except error.HTTPError as exc:
        return exc.code,json.loads(exc.read())
for goal,time_text in [('本周学习 RAG，安排 6 小时','3 天'),('设计作品集网站，安排 8 小时','4 天'),('准备机器学习面试，安排 4 小时','2 天'),('整理读书笔记','每天 1 小时')]:
    token=str(uuid.uuid4())
    try:
        status,session=call('/api/init',token,{'goal':goal,'use_llm':True})
        assert status==200,session
        assert session['model_mode']=='simulation',session['model_mode']
        assert 'OPENAI_API_KEY' in session['model_notice']
        for completion in (.25,.5,.75,1):
            status,session=call('/api/run',token,{})
            assert status==200 and session['review']['completion_rate']==completion
        assert time_text in session['tasks'][2]['result']
        assert session['review']['tool_success_rate']==1
        assert len(session['events'])==4
        assert call('/api/session',token)[1]['model_notice']==session['model_notice']
        assert call('/api/session',str(uuid.uuid4()))[1]['session'] is None
        assert call('/api/session',token,method='OPTIONS')[0]==204
        print('PASS scenario',time_text,flush=True)
    finally:
        call('/api/reset',token,{})
        assert call('/api/session',token)[1]['session'] is None
print('PASS public API, CORS, simulation warning, execution, restore, isolation, reset',flush=True)
