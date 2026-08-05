import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'jobcards.db')}")

# Render and other platforms provide postgres:// URLs; SQLAlchemy 2.x expects postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_engine_kwargs = {"echo": False, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    # SQLite needs this for multi-threaded Flask; Postgres does not
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine)
db_session = scoped_session(SessionLocal)

Base = declarative_base()


def get_db():
    return db_session


def get_or_404(model, ident):
    """SQLAlchemy 2.0 equivalent of Flask-SQLAlchemy's get_or_404."""
    result = db_session.get(model, ident)
    if result is None:
        from flask import abort
        abort(404)
    return result


def first_or_404(query):
    """Execute query and return first result or 404."""
    result = query.first()
    if result is None:
        from flask import abort
        abort(404)
    return result


def init_db():
    from models import (
        Customer, Technician, JobCard, JobCardTask, PartUsed,
        TimeEntry, Comment, Attachment, StatusHistory,
        EmailLog, WhatsAppLog, Setting, User, Ticket, TicketComment
    )
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns():
    """Add columns introduced after a table was first created (create_all does
    not alter existing tables)."""
    from sqlalchemy import inspect, text
    try:
        insp = inspect(engine)
    except Exception:
        return
    existing = {c["name"] for c in insp.get_columns("jobcards")} if "jobcards" in insp.get_table_names() else set()
    if "signature_data" not in existing:
        try:
            db_session.execute(text("ALTER TABLE jobcards ADD COLUMN signature_data TEXT"))
            db_session.commit()
        except Exception:
            db_session.rollback()

    user_cols = {c["name"] for c in insp.get_columns("users")} if "users" in insp.get_table_names() else set()
    if "email" not in user_cols:
        try:
            db_session.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(200)"))
            db_session.commit()
        except Exception:
            db_session.rollback()

    email_log_cols = {c["name"] for c in insp.get_columns("email_logs")} if "email_logs" in insp.get_table_names() else set()
    if "ticket_id" not in email_log_cols:
        try:
            db_session.execute(text("ALTER TABLE email_logs ADD COLUMN ticket_id INTEGER"))
            db_session.commit()
        except Exception:
            db_session.rollback()
