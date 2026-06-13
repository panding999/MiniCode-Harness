from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from minicode.persistence.models import MessageRecord, RunRecord, SessionRecord, TaskRecord, TraceEventRecord


class SessionRepository:
    def __init__(self, factory): self.factory = factory
    def get(self, session_id):
        with self.factory() as db: return db.get(SessionRecord, session_id)
    def get_or_create(self, session_id, workspace):
        with self.factory() as db:
            row = db.get(SessionRecord, session_id)
            if not row:
                row = SessionRecord(id=session_id, workspace=workspace)
                db.add(row); db.commit(); db.refresh(row)
            elif row.workspace != workspace:
                raise ValueError("Session belongs to a different workspace")
            return row
    def list(self):
        with self.factory() as db: return list(db.scalars(select(SessionRecord).order_by(SessionRecord.updated_at.desc())))
    def update_summary(self, session_id, summary):
        with self.factory() as db:
            row = db.get(SessionRecord, session_id); row.summary = summary; db.commit()


class MessageRepository:
    def __init__(self, factory): self.factory = factory
    def add(self, session_id, role, content, tool_call_id=None, extra_data=None):
        with self.factory() as db:
            row = MessageRecord(session_id=session_id, role=role, content=content, tool_call_id=tool_call_id, extra_data=extra_data or {})
            db.add(row); db.commit(); db.refresh(row); return row
    def list_recent(self, session_id, limit=20):
        with self.factory() as db:
            rows = list(db.scalars(select(MessageRecord).where(MessageRecord.session_id == session_id).order_by(MessageRecord.id.desc()).limit(limit)))
            return list(reversed(rows))
    def count(self, session_id):
        return len(self.list_recent(session_id, 100000))


class TaskRepository:
    def __init__(self, factory): self.factory = factory
    def get_current(self, session_id):
        with self.factory() as db:
            return db.scalar(select(TaskRecord).where(TaskRecord.session_id == session_id).order_by(TaskRecord.id.desc()).limit(1))
    def get_or_create(self, session_id, goal):
        row = self.get_current(session_id)
        if row:
            if row.status == "paused":
                self.update(row.id, status="active")
            return self.get_current(session_id)
        with self.factory() as db:
            row = TaskRecord(session_id=session_id, goal=goal)
            db.add(row); db.commit(); db.refresh(row); return row
    def update(self, task_id, **values):
        with self.factory() as db:
            row = db.get(TaskRecord, task_id)
            for key, value in values.items(): setattr(row, key, value)
            row.updated_at = datetime.utcnow()
            db.commit(); db.refresh(row); return row


class TraceRepository:
    def __init__(self, factory): self.factory = factory
    def start_run(self, session_id):
        run_id = str(uuid4())
        with self.factory() as db: db.add(RunRecord(id=run_id, session_id=session_id)); db.commit()
        return run_id
    def add(self, run_id, session_id, step_number, event_type, **values):
        with self.factory() as db:
            row = TraceEventRecord(run_id=run_id, session_id=session_id, step_number=step_number, event_type=event_type, **values)
            db.add(row); db.commit(); db.refresh(row); return row
    def finish(self, run_id, status):
        with self.factory() as db:
            row = db.get(RunRecord, run_id); row.status = status; row.finished_at = datetime.utcnow(); db.commit()
    def list_for_session(self, session_id):
        with self.factory() as db:
            return list(db.scalars(select(TraceEventRecord).where(TraceEventRecord.session_id == session_id).order_by(TraceEventRecord.id)))


@dataclass
class Repositories:
    sessions: SessionRepository
    messages: MessageRepository
    tasks: TaskRepository
    traces: TraceRepository

    @classmethod
    def create(cls, factory):
        return cls(SessionRepository(factory), MessageRepository(factory), TaskRepository(factory), TraceRepository(factory))
