"""Persistent session state for the study agent."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any

@dataclass
class Task:
    id: str
    title: str
    action: str
    tool: str
    argument: Any
    depends_on: list[str] = field(default_factory=list)
    status: str = 'pending'
    attempts: int = 0
    result: Any = None
    error: str | None = None

@dataclass
class Event:
    timestamp: str
    kind: str
    task_id: str
    tool: str
    status: str
    input: Any
    output: Any = None
    error: str | None = None
    duration_ms: float | None = None
    attempt: int | None = None

@dataclass
class Session:
    goal: str
    created_at: str
    updated_at: str
    tasks: list[Task]
    events: list[Event] = field(default_factory=list)
    model_mode: str = 'rules'
    model_notice: str | None = None
    planning_trace: list[dict] = field(default_factory=list)

    @classmethod
    def create(cls, goal: str, planned_tasks: list[dict]) -> 'Session':
        now = datetime.now().isoformat(timespec='seconds')
        return cls(goal, now, now, [Task(**item) for item in planned_tasks])

    @classmethod
    def load(cls, path: str | Path) -> 'Session':
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        data['tasks'] = [Task(**item) for item in data.get('tasks', [])]
        data['events'] = [Event(**item) for item in data.get('events', [])]
        return cls(**data)

    def save(self, path: str | Path) -> None:
        self.updated_at = datetime.now().isoformat(timespec='seconds')
        payload = asdict(self)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    def task(self, task_id: str) -> Task:
        for item in self.tasks:
            if item.id == task_id:
                return item
        raise KeyError(task_id)

    def ready_tasks(self) -> list[Task]:
        done = {item.id for item in self.tasks if item.status == 'done'}
        return [item for item in self.tasks if item.status == 'pending' and set(item.depends_on) <= done]

    def completion(self) -> float:
        return sum(item.status == 'done' for item in self.tasks) / len(self.tasks) if self.tasks else 0.0
