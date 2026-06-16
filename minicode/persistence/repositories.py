from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from minicode.persistence.models import MessageRecord, RunRecord, SessionRecord, TaskRecord, TraceEventRecord


# Repository 层把 SQLAlchemy 查询隔离在 Runtime 之外，也方便测试使用内存 SQLite。
class SessionRepository:
    def __init__(self, factory): self.factory = factory
    def get(self, session_id):
        with self.factory() as db: return db.get(SessionRecord, session_id)
    def get_or_create(self, session_id, workspace):
        # 同一个 Session 不能复用到不同 Workspace，避免把历史上下文套到错误项目。
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
    def rename(self, old_id, new_id):
        # Session ID 是主键，重命名时必须同步所有关联表的 session_id。
        new_id = str(new_id).strip()
        if not new_id:
            raise ValueError("New session name cannot be empty")
        with self.factory() as db:
            row = db.get(SessionRecord, old_id)
            if row is None:
                raise ValueError(f"Session not found: {old_id}")
            if db.get(SessionRecord, new_id) is not None:
                raise ValueError(f"Session already exists: {new_id}")
            for model in [MessageRecord, TaskRecord, RunRecord, TraceEventRecord]:
                for related in db.scalars(select(model).where(model.session_id == old_id)):
                    related.session_id = new_id
            row.id = new_id
            row.updated_at = datetime.utcnow()
            db.commit(); db.refresh(row); return row


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
    def list_after(self, session_id, message_id=0):
        with self.factory() as db:
            return list(db.scalars(
                select(MessageRecord)
                .where(MessageRecord.session_id == session_id, MessageRecord.id > message_id)
                .order_by(MessageRecord.id)
            ))
    def count(self, session_id):
        return len(self.list_recent(session_id, 100000))


class TaskRepository:
    def __init__(self, factory): self.factory = factory
    def get_current(self, session_id):
        with self.factory() as db:
            return db.scalar(select(TaskRecord).where(TaskRecord.session_id == session_id).order_by(TaskRecord.id.desc()).limit(1))
    def get_or_create(self, session_id, goal):
        # active 任务继续使用；paused 任务恢复为 active；completed/failed 后的新输入创建新任务。
        row = self.get_current(session_id)
        if row:
            if row.status == "paused":
                self.update(row.id, status="active")
                return self.get_current(session_id)
            if row.status not in {"completed", "failed"}:
                return row
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
    def latest_run(self, session_id):
        with self.factory() as db:
            return db.scalar(select(RunRecord).where(RunRecord.session_id == session_id).order_by(RunRecord.created_at.desc()).limit(1))
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
