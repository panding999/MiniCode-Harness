from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from minicode.persistence.database import Base


def now() -> datetime:
    return datetime.utcnow()


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class MessageRecord(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    tool_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TaskRecord(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="active")
    summary: Mapped[str] = mapped_column(Text, default="")
    completed_steps: Mapped[list[Any]] = mapped_column(JSON, default=list)
    next_action: Mapped[str] = mapped_column(Text, default="")
    files_read: Mapped[list[Any]] = mapped_column(JSON, default=list)
    files_changed: Mapped[list[Any]] = mapped_column(JSON, default=list)
    commands_run: Mapped[list[Any]] = mapped_column(JSON, default=list)
    test_result: Mapped[str] = mapped_column(Text, default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class RunRecord(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TraceEventRecord(Base):
    __tablename__ = "trace_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String)
    tool_name: Mapped[str | None] = mapped_column(String, nullable=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    success: Mapped[bool] = mapped_column(default=True)
    output_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
