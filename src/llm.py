"""Small optional OpenAI Responses API adapter.

The project still runs without a key. The adapter uses only the Python standard
library so the offline rule planner remains the default path.
"""
from __future__ import annotations
import json
import os
import time
import re
from datetime import datetime, timezone
import urllib.error
import urllib.request
from urllib.parse import urlparse
from .planner import PlannedTask

class LLMError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable

SYSTEM_PROMPT = '''You plan a Chinese learning goal. Return JSON only: an object with a tasks array.
Each task must contain id, title, action, tool, argument, depends_on.
Use ids t1, t2, ...; tool must be one of summarize, checklist, time_budget, review_prompt.
Return EXACTLY FOUR tasks in this order: t1 summarize, t2 checklist, t3 time_budget, t4 review_prompt.
Each tool occurs exactly once. Put all detailed steps into the checklist array; never create extra tasks.
depends_on contains earlier task ids. Do not invent tools.
Support learning, portfolio project planning, interview preparation and note organization.
summarize and review_prompt argument must be a nonempty string.
checklist argument must be a nonempty array of strings specific to the goal.
If the user provides hours, time_budget argument must be an object with that exact total hours and goal text.
If no hours are provided, its argument must be the string 未提供小时数. Never invent hours.
These tools create planning material; do not claim to build websites or complete real-world work.
Write all titles, actions, and argument text in Chinese.
Every task MUST include depends_on, including an empty array for the first task.
The time_budget argument key is exactly goal, never goal_text.
Example of the required shape (adapt the contents to the user's goal):
{"tasks":[{"id":"t1","title":"目标摘要","action":"整理目标","tool":"summarize","argument":"用户的目标","depends_on":[]},
{"id":"t2","title":"行动清单","action":"列出步骤","tool":"checklist","argument":["阅读资料","练习与复盘"],"depends_on":["t1"]},
{"id":"t3","title":"时间安排","action":"分配时间","tool":"time_budget","argument":{"hours":4,"goal":"用户的目标"},"depends_on":["t2"]},
{"id":"t4","title":"复盘提醒","action":"整理复盘问题","tool":"review_prompt","argument":"用户的目标","depends_on":["t3"]}]}
最终检查：只输出四个任务。网站开发步骤全部写入 t2 的清单。用户没有给出小时数时，t3.argument 写为字符串 未提供小时数。'''

def _output_text(payload: dict) -> str:
    if isinstance(payload.get('output_text'), str):
        return payload['output_text']
    chunks = []
    for item in payload.get('output', []):
        if item.get('type', 'message') != 'message':
            continue
        for content in item.get('content', []):
            if isinstance(content, dict) and isinstance(content.get('text'), str):
                chunks.append(content['text'])
    if not chunks:
        raise LLMError('Responses API 没有返回文本', retryable=True)
    return ''.join(chunks)

def model_mode() -> str:
    return 'chat_compatible' if os.getenv('OPENAI_API_STYLE', 'responses') == 'chat_completions' else 'openai'

def _chat_output_text(payload: dict) -> str:
    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError('Chat Completions 接口没有返回文本', retryable=True) from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMError('Chat Completions 接口没有返回文本', retryable=True)
    return content

def trace_event(trace: list[dict], stage: str, title: str, **data) -> None:
    trace.append({'timestamp': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                  'stage': stage, 'title': title, **data})

def local_planning_trace(goal: str, planned: list[dict], mode: str) -> list[dict]:
    trace = []
    trace_event(trace, 'request', '接收目标', mode=mode, input=goal)
    trace_event(trace, 'output', '模拟模型输出' if mode == 'simulation' else '规则规划输出',
                mode=mode, output=json.dumps({'tasks': planned}, ensure_ascii=False, indent=2),
                duration_ms=0, note='本地规则生成，无真实模型请求；耗时未单独计量')
    trace_event(trace, 'validated', '计划结构已建立', task_count=len(planned),
                output='工具来自注册表，任务按前置依赖执行')
    return trace

def plan_with_llm(goal: str, timeout: int = 30, trace: list[dict] | None = None) -> list[PlannedTask]:
    trace = trace if trace is not None else []
    feedback = ''
    for attempt in range(1, 4):
        try:
            return _plan_attempt(goal, timeout, trace, feedback, attempt)
        except LLMError as exc:
            if not trace or trace[-1]['stage'] != 'error':
                trace_event(trace, 'error', '模型规划失败', error=str(exc), attempt=attempt)
            if not exc.retryable or attempt == 3:
                raise
            feedback = str(exc)
            trace_event(trace, 'retry', '重新请求模型规划', attempt=attempt + 1,
                        error=feedback, output='上一轮未通过，将错误反馈给模型；最多尝试 3 次')
    raise LLMError('模型规划失败')

def _plan_attempt(goal: str, timeout: int, trace: list[dict], feedback: str, attempt: int) -> list[PlannedTask]:
    trace = trace if trace is not None else []
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        raise LLMError('未设置 OPENAI_API_KEY')
    model = os.getenv('OPENAI_MODEL', 'gpt-5-mini')
    style = os.getenv('OPENAI_API_STYLE', 'responses')
    if style not in ('responses', 'chat_completions'):
        raise LLMError('OPENAI_API_STYLE 必须为 responses 或 chat_completions')
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    parsed = urlparse(base_url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LLMError('OPENAI_BASE_URL 必须为不含凭证、查询参数和片段的 HTTPS 地址')
    started = time.perf_counter()
    trace_event(trace, 'request', '发送模型规划请求', mode=model_mode(), model=model,
                input=goal, instructions=SYSTEM_PROMPT, attempt=attempt, note=feedback)
    prompt = goal + (f'\n上一轮计划未通过校验：{feedback}。请重新生成完整 JSON，严格使用四个任务。' if feedback else '')
    body = {
        'model': model,
        'instructions': SYSTEM_PROMPT,
        'input': prompt,
        'store': False,
        'max_output_tokens': 3000,
    }
    if style == 'chat_completions':
        body = {'model': model, 'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}], 'stream': False, 'max_tokens': 3000, 'temperature': 0}
    request = urllib.request.Request(
        base_url + ('/chat/completions' if style == 'chat_completions' else '/responses'),
        data=json.dumps(body).encode('utf-8'),
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        trace_event(trace, 'error', '模型请求失败', error=str(exc),
                    duration_ms=round((time.perf_counter() - started) * 1000, 2))
        retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in (408, 429, 500, 502, 503, 504)
        raise LLMError(f'模型请求失败：{exc}', retryable=retryable) from exc
    try:
        if not isinstance(payload, dict):
            raise ValueError('模型响应必须为 JSON 对象')
        raw = (_chat_output_text(payload) if style == 'chat_completions' else _output_text(payload)).strip()
        trace_event(trace, 'output', '收到模型输出', output=raw, model=model,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    usage=payload.get('usage', {}), attempt=attempt)
        if raw.startswith('```'):
            fenced = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', raw, re.S | re.I)
            if fenced:
                raw = fenced.group(1).strip()
        items = json.loads(raw)['tasks']
        tasks = [PlannedTask(**item) for item in items]
        if len(tasks) != 4:
            raise ValueError('必须返回 4 个任务：摘要、清单、时间预算、复盘；详细步骤放入清单')
        if [task.tool for task in tasks] != ['summarize','checklist','time_budget','review_prompt']:
            raise ValueError('四个任务的工具顺序必须为 summarize、checklist、time_budget、review_prompt')
        valid_tools = {'summarize', 'checklist', 'time_budget', 'review_prompt'}
        if any(task.tool not in valid_tools for task in tasks):
            raise ValueError('模型返回了未注册工具')
        ids = {task.id for task in tasks}
        if len(ids) != len(tasks):
            raise ValueError('任务编号重复')
        earlier = set()
        for task in tasks:
            if not all(isinstance(text, str) and text.strip() for text in (task.id, task.title, task.action)):
                raise ValueError('任务文字不能为空')
            if not isinstance(task.depends_on, list) or not all(isinstance(dep, str) for dep in task.depends_on) or not set(task.depends_on) <= earlier:
                raise ValueError('任务只能依赖较早的任务')
            if task.tool in ('summarize', 'review_prompt') and not (isinstance(task.argument, str) and task.argument.strip()):
                raise ValueError('文本工具参数必须为字符串')
            if task.tool == 'checklist' and not (isinstance(task.argument, list) and task.argument and all(isinstance(x, str) and x.strip() for x in task.argument)):
                raise ValueError('清单工具参数必须为文字数组')
            if task.tool == 'time_budget':
                hours = re.search(r'(\d+)\s*(小时|h|hour)', goal, re.I)
                if hours:
                    if not (isinstance(task.argument, dict) and type(task.argument.get('hours')) is int and task.argument['hours'] == int(hours.group(1)) and 1 <= task.argument['hours'] <= 168 and isinstance(task.argument.get('goal'), str) and task.argument['goal'].strip()):
                        raise ValueError('时间预算必须使用用户给出的总小时数，并包含 goal')
                elif task.argument != '未提供小时数':
                    task.argument = '未提供小时数'
                    trace_event(trace, 'normalized', '时间预算采用默认建议',
                                output='用户未提供小时数，忽略模型推测的时长；工具将显示每天 1 小时的建议',
                                attempt=attempt)
            earlier.add(task.id)
        trace_event(trace, 'validated', '模型计划校验通过', task_count=len(tasks),
                    output='任务编号、工具白名单、参数类型和依赖顺序校验通过')
        return tasks
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        trace_event(trace, 'error', '计划校验失败', error=str(exc))
        raise LLMError(f'模型返回格式无效：{exc}', retryable=True) from exc

def simulation_plan(goal: str) -> list[PlannedTask]:
    """Return a visible offline substitute when no API key is configured."""
    from .planner import Planner
    return Planner().plan(goal)
