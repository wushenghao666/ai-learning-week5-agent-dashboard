"""Small optional OpenAI Responses API adapter.

The project still runs without a key. The adapter uses only the Python standard
library so the offline rule planner remains the default path.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from .planner import PlannedTask

class LLMError(RuntimeError):
    pass

SYSTEM_PROMPT = '''You plan a Chinese learning goal. Return JSON only: an object with a tasks array.
Each task must contain id, title, action, tool, argument, depends_on.
Use ids t1, t2, ...; tool must be one of summarize, checklist, time_budget, review_prompt.
Keep 2 to 5 tasks. depends_on contains earlier task ids. Do not invent tools.
Support learning, portfolio project planning, interview preparation and note organization.
summarize and review_prompt argument must be a nonempty string.
checklist argument must be a nonempty array of strings specific to the goal.
time_budget argument must be an object with integer hours from 1 to 168 and goal text.
These tools create planning material; do not claim to build websites or complete real-world work.'''

def _output_text(payload: dict) -> str:
    if isinstance(payload.get('output_text'), str):
        return payload['output_text']
    chunks = []
    for item in payload.get('output', []):
        for content in item.get('content', []):
            if isinstance(content, dict) and isinstance(content.get('text'), str):
                chunks.append(content['text'])
    if not chunks:
        raise LLMError('Responses API 没有返回文本')
    return ''.join(chunks)

def plan_with_llm(goal: str, timeout: int = 30) -> list[PlannedTask]:
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        raise LLMError('未设置 OPENAI_API_KEY')
    model = os.getenv('OPENAI_MODEL', 'gpt-5-mini')
    body = {
        'model': model,
        'instructions': SYSTEM_PROMPT,
        'input': goal,
        'store': False,
        'max_output_tokens': 3000,
    }
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(body).encode('utf-8'),
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise LLMError(f'模型请求失败：{exc}') from exc
    try:
        raw = _output_text(payload).strip()
        if raw.startswith('```'):
            raw = raw.strip('`').replace('json\n', '', 1).strip()
        items = json.loads(raw)['tasks']
        tasks = [PlannedTask(**item) for item in items]
        if not 2 <= len(tasks) <= 5:
            raise ValueError('任务数量需要在 2 到 5 之间')
        valid_tools = {'summarize', 'checklist', 'time_budget', 'review_prompt'}
        if any(task.tool not in valid_tools for task in tasks):
            raise ValueError('模型返回了未注册工具')
        ids = {task.id for task in tasks}
        if len(ids) != len(tasks):
            raise ValueError('任务编号重复')
        if any(dep not in ids for task in tasks for dep in task.depends_on):
            raise ValueError('任务依赖不存在')
        earlier = set()
        for task in tasks:
            if not all(isinstance(text, str) and text.strip() for text in (task.id, task.title, task.action)):
                raise ValueError('任务文字不能为空')
            if not isinstance(task.depends_on, list) or not set(task.depends_on) <= earlier:
                raise ValueError('任务只能依赖较早的任务')
            if task.tool in ('summarize', 'review_prompt') and not (isinstance(task.argument, str) and task.argument.strip()):
                raise ValueError('文本工具参数必须为字符串')
            if task.tool == 'checklist' and not (isinstance(task.argument, list) and task.argument and all(isinstance(x, str) and x.strip() for x in task.argument)):
                raise ValueError('清单工具参数必须为文字数组')
            if task.tool == 'time_budget' and not (isinstance(task.argument, dict) and type(task.argument.get('hours')) is int and 1 <= task.argument['hours'] <= 168):
                raise ValueError('时间预算参数无效')
            earlier.add(task.id)
        return tasks
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LLMError(f'模型返回格式无效：{exc}') from exc

def simulation_plan(goal: str) -> list[PlannedTask]:
    """Return a visible offline substitute when no API key is configured."""
    from .planner import Planner
    return Planner().plan(goal)
