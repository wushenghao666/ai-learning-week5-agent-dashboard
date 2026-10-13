"""Controlled local tools for the persistent agent."""
from __future__ import annotations
import ast
import operator
import re
from typing import Any, Callable

class ToolError(ValueError):
    pass

def summarize(text: str) -> str:
    cleaned = ' '.join(str(text).split())
    if not cleaned:
        raise ToolError('摘要输入不能为空')
    sentence = re.split(r'(?<=[。！？.!?])\s*', cleaned)[0]
    return sentence[:99] + ('…' if len(sentence) > 100 else '')

def checklist(items: list[str]) -> str:
    if not items:
        raise ToolError('清单不能为空')
    return '\n'.join(f'{i + 1}. {item}' for i, item in enumerate(items))

def time_budget(value: Any) -> str:
    if isinstance(value, dict) and 'hours' in value:
        hours = int(value['hours'])
        if hours <= 0 or hours > 168:
            raise ToolError('小时数需要在 1 到 168 之间')
        days = min(7, max(1, hours // 2 or 1))
        return f'总计 {hours} 小时，建议分为 {days} 天，每天约 {hours / days:.1f} 小时'
    return '目标未提供小时数，建议先安排每天 1 小时'

def review_prompt(goal: str) -> str:
    return f'复盘问题：{summarize(goal)}；完成后记录一个有效做法和一个待改进点。'

TOOLS: dict[str, Callable[[Any], str]] = {
    'summarize': summarize,
    'checklist': checklist,
    'time_budget': time_budget,
    'review_prompt': review_prompt,
}
