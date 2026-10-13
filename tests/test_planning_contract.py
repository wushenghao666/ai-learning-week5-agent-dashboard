import json
import unittest
import urllib.error
from unittest.mock import patch
from src.llm import plan_with_llm, LLMError
from src.planner import Planner

class Response:
    def __init__(self, tasks): self.tasks=tasks
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self): return json.dumps({'output_text':json.dumps({'tasks':self.tasks})}).encode()

class PlanningContractTests(unittest.TestCase):
    def tasks(self, goal='学习 6 小时'):
        return [t.to_dict() for t in Planner().plan(goal)]

    def test_repair_feedback_after_excess_tasks(self):
        invalid=self.tasks()+self.tasks()
        trace=[]
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}), patch('urllib.request.urlopen',side_effect=[Response(invalid),Response(self.tasks())]) as calls:
            self.assertEqual(len(plan_with_llm('学习 6 小时',trace=trace)),4)
        self.assertEqual(calls.call_count,2)
        self.assertIn('上一轮计划未通过校验',json.loads(calls.call_args.args[0].data)['input'])
        self.assertEqual([e['stage'] for e in trace],['request','output','error','retry','request','output','validated'])

    def test_wrong_hours_are_not_executed(self):
        tasks=self.tasks();tasks[2]['argument']['hours']=4
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}), patch('urllib.request.urlopen',return_value=Response(tasks)) as calls:
            with self.assertRaises(LLMError): plan_with_llm('学习 6 小时')
        self.assertEqual(calls.call_count,3)

    def test_unspecified_hours_remain_unspecified(self):
        tasks=self.tasks('整理笔记');tasks[2]['argument']='未提供小时数'
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}), patch('urllib.request.urlopen',return_value=Response(tasks)):
            self.assertEqual(plan_with_llm('整理笔记')[2].argument,'未提供小时数')

    def test_invented_hours_are_removed_and_recorded(self):
        tasks=self.tasks('整理笔记');tasks[2]['argument']={'hours':4,'goal':'笔记'}
        trace=[]
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}), patch('urllib.request.urlopen',return_value=Response(tasks)):
            self.assertEqual(plan_with_llm('整理笔记',trace=trace)[2].argument,'未提供小时数')
        self.assertIn('normalized',[e['stage'] for e in trace])

    def test_unauthorized_is_not_retried(self):
        failure=urllib.error.HTTPError('https://example.com',401,'Unauthorized',{},None)
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}), patch('urllib.request.urlopen',side_effect=failure) as calls:
            with self.assertRaises(LLMError): plan_with_llm('学习 6 小时')
        self.assertEqual(calls.call_count,1)

    def test_transient_timeout_can_recover(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}), patch('urllib.request.urlopen',side_effect=[TimeoutError('timed out'),Response(self.tasks())]):
            self.assertEqual(len(plan_with_llm('学习 6 小时')),4)

    def test_unknown_tool_never_passes(self):
        tasks=self.tasks(); tasks[1]['tool']='shell'
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}), patch('urllib.request.urlopen',return_value=Response(tasks)):
            with self.assertRaises(LLMError): plan_with_llm('学习 6 小时')
