"""CLI and execution loop for the persistent study agent."""
from __future__ import annotations
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from .memory import Event, Session
from .planner import Planner
from .llm import LLMError, plan_with_llm, local_planning_trace
from .tools import TOOLS, ToolError

MAX_RETRIES = 2

def init_session(goal: str, path: str, use_llm: bool = False, allow_fallback: bool = True, trace: list[dict] | None = None) -> Session:
    trace = trace if trace is not None else []
    planned = Planner().plan(goal)
    if use_llm:
        try:
            planned = plan_with_llm(goal, trace=trace)
            print('规划器：OpenAI Responses API')
        except LLMError as exc:
            if not allow_fallback:
                raise
            print(f'模型规划不可用，回退规则规划：{exc}')
    session = Session.create(goal, [task.to_dict() for task in planned])
    session.planning_trace = trace or local_planning_trace(goal, [task.to_dict() for task in planned], 'rules')
    session.save(path)
    return session

def run_session(session: Session) -> list[dict]:
    outputs = []
    for task in session.ready_tasks():
        task.status = 'running'
        while task.attempts < MAX_RETRIES:
            task.attempts += 1
            started = time.perf_counter()
            try:
                result = TOOLS[task.tool](task.argument)
                task.result, task.status, task.error = result, 'done', None
                session.events.append(Event(_timestamp(), 'tool_call', task.id, task.tool, 'ok', task.argument, result,
                                            duration_ms=round((time.perf_counter() - started) * 1000, 3), attempt=task.attempts))
                outputs.append({'task': task.id, 'status': 'done', 'result': result})
                break
            except (ToolError, KeyError, TypeError) as exc:
                task.error = str(exc)
                session.events.append(Event(_timestamp(), 'tool_call', task.id, task.tool, 'error', task.argument, error=str(exc),
                                            duration_ms=round((time.perf_counter() - started) * 1000, 3), attempt=task.attempts))
                if task.attempts >= MAX_RETRIES:
                    task.status = 'failed'
                    outputs.append({'task': task.id, 'status': 'failed', 'error': str(exc)})
        if task.status == 'failed':
            break
    return outputs

def _timestamp() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec='seconds')

def review(session: Session) -> dict:
    total = len(session.tasks)
    done = sum(t.status == 'done' for t in session.tasks)
    calls = [e for e in session.events if e.kind == 'tool_call']
    success = sum(e.status == 'ok' for e in calls)
    suggestions = []
    if done < total:
        suggestions.append('继续运行可执行任务，先处理失败任务或补齐前置任务')
    if any(t.status == 'failed' for t in session.tasks):
        suggestions.append('检查失败任务的输入，再决定是否修改计划')
    if done == total:
        suggestions.append('把复盘结果写入下一次学习计划')
    return {'completion_rate': round(done / total, 3) if total else 0, 'tool_success_rate': round(success / len(calls), 3) if calls else 0, 'suggestions': suggestions}

def progress(session: Session) -> str:
    lines = [f'目标：{session.goal}', f'完成率：{session.completion():.0%}', '任务：']
    for task in session.tasks:
        deps = ','.join(task.depends_on) if task.depends_on else '无'
        lines.append(f'- [{task.status}] {task.id} {task.title}，前置：{deps}，尝试：{task.attempts}')
    return '\n'.join(lines)

def main() -> None:
    parser = argparse.ArgumentParser(description='运行可持续的学习计划 Agent')
    sub = parser.add_subparsers(dest='command', required=True)
    p_init = sub.add_parser('init'); p_init.add_argument('goal'); p_init.add_argument('--session', default='outputs/session.json'); p_init.add_argument('--llm', action='store_true', help='使用 OpenAI Responses API 生成计划')
    for name in ('run', 'progress', 'review'):
        p = sub.add_parser(name); p.add_argument('--session', default='outputs/session.json')
    args = parser.parse_args()
    if args.command == 'init':
        session = init_session(args.goal, args.session, args.llm)
        print(progress(session)); return
    session = Session.load(args.session)
    if args.command == 'run':
        print(json.dumps(run_session(session), ensure_ascii=False, indent=2)); session.save(args.session)
    elif args.command == 'progress':
        print(progress(session))
    elif args.command == 'review':
        print(json.dumps(review(session), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()



