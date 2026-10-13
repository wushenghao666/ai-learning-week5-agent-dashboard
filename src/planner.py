"""Planning rules for the persistent study agent."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import re

@dataclass
class PlannedTask:
    id: str
    title: str
    action: str
    tool: str
    argument: object
    depends_on: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

class Planner:
    def plan(self, goal: str) -> list[PlannedTask]:
        goal = ' '.join(goal.split())
        items = ['阅读核心概念', '完成小型实现', '运行测试并记录问题']
        if '网站' in goal or '作品集' in goal:
            items = ['整理作品与个人介绍', '绘制页面原型', '检查布局和链接']
        elif '面试' in goal:
            items = ['复习核心知识', '练习常见问题', '记录薄弱项并复盘']
        elif '读书' in goal or '笔记' in goal:
            items = ['整理摘录', '归纳主题', '写出复盘清单']
        tasks: list[PlannedTask] = [
            PlannedTask('t1', '明确本周目标', '提取目标中的主题和产出', 'summarize', goal, []),
            PlannedTask('t2', '建立学习清单', '把目标拆成可执行项目', 'checklist', items, ['t1']),
            PlannedTask('t3', '安排时间预算', '根据目标中的时长计算每天投入', 'time_budget', goal, ['t2']),
            PlannedTask('t4', '生成复盘提醒', '根据当前计划生成复盘事项', 'review_prompt', goal, ['t3']),
        ]
        hour = re.search(r'(\d+)\s*(小时|h|hour)', goal, re.I)
        if hour:
            tasks[2].argument = {'goal': goal, 'hours': int(hour.group(1))}
        return tasks
