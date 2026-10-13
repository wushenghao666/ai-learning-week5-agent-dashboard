import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.agent import init_session, run_session
from src.memory import Session
from src.llm import plan_with_llm, LLMError
from src.planner import Planner

class TraceTests(unittest.TestCase):
    def test_chat_compatible_request_and_response(self):
        raw = json.dumps({'tasks':[t.to_dict() for t in Planner().plan('准备面试 4 小时')]})
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self): return json.dumps({'choices':[{'message':{'content':raw,'reasoning_content':'private reasoning'}}],'usage':{'total_tokens':42}}).encode()
        trace=[]
        env={'OPENAI_API_KEY':'test-secret-not-real','OPENAI_API_STYLE':'chat_completions','OPENAI_BASE_URL':'https://llmapi.paratera.com/v1/','OPENAI_MODEL':'GLM-4-Flash'}
        with patch.dict('os.environ',env), patch('urllib.request.urlopen',return_value=Response()) as call:
            self.assertEqual(len(plan_with_llm('准备面试 4 小时',trace=trace)),4)
        request=call.call_args.args[0]
        self.assertEqual(request.full_url,'https://llmapi.paratera.com/v1/chat/completions')
        body=json.loads(request.data)
        self.assertEqual(body['model'],'GLM-4-Flash')
        self.assertEqual(body['messages'][1]['content'],'准备面试 4 小时')
        self.assertNotIn('instructions',body)
        self.assertEqual(trace[0]['mode'],'chat_compatible')
        self.assertEqual(trace[1]['usage']['total_tokens'],42)
        self.assertNotIn('test-secret-not-real',json.dumps(trace))
        self.assertNotIn('private reasoning',json.dumps(trace))

    def test_trace_and_call_timing_persist(self):
        path = Path('outputs/test-trace.json')
        try:
            session = init_session('准备面试，安排 4 小时', path)
            self.assertEqual([e['stage'] for e in session.planning_trace], ['request','output','validated'])
            self.assertEqual(len(json.loads(session.planning_trace[1]['output'])['tasks']),4)
            run_session(session); session.save(path)
            restored = Session.load(path)
            self.assertEqual(restored.events[0].attempt,1)
            self.assertGreaterEqual(restored.events[0].duration_ms,0)
            self.assertEqual(restored.planning_trace,session.planning_trace)
        finally: path.unlink(missing_ok=True)

    def test_real_adapter_records_public_output_without_credentials(self):
        raw = json.dumps({'tasks':[t.to_dict() for t in Planner().plan('学习 6 小时')]})
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self): return json.dumps({'output':[{'type':'reasoning','content':[{'text':'private reasoning'}]},{'type':'message','content':[{'type':'output_text','text':raw}]}],'usage':{'input_tokens':12,'output_tokens':30}}).encode()
        trace=[]
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-secret-not-real'}), patch('urllib.request.urlopen',return_value=Response()):
            self.assertEqual(len(plan_with_llm('学习 6 小时',trace=trace)),4)
        self.assertEqual(trace[1]['output'],raw)
        self.assertEqual(trace[1]['usage']['output_tokens'],30)
        self.assertNotIn('test-secret-not-real',json.dumps(trace))
        self.assertNotIn('private reasoning',json.dumps(trace))
        self.assertEqual(trace[-1]['stage'],'validated')

    def test_invalid_model_output_records_validation_failure(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self): return json.dumps({'output_text':'invalid json'}).encode()
        trace=[]
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-secret-not-real'}), patch('urllib.request.urlopen',return_value=Response()):
            with self.assertRaises(LLMError): plan_with_llm('目标',trace=trace)
        self.assertEqual(trace[1]['output'],'invalid json')
        self.assertEqual(trace[-1]['stage'],'error')

if __name__=='__main__': unittest.main()
