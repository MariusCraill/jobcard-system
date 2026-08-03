from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, Date,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import Base
import enum


class JobCardStatus(enum.Enum):
    open = "open"
    assigned = "assigned"
    in_progress = "in_progress"
    on_hold = "on_hold"
    awaiting_parts = "awaiting_parts"
    completed = "completed"
    closed = "closed"
    cancelled = "cancelled"


class Priority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
    emergency = "emergency"


class TaskStatus(enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    company = Column(String(200))
    email = Column(String(200))
    phone = Column(String(50))
    alt_phone = Column(String(50))
    address = Column(Text)
    city = Column(String(100))
    province = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100), default="South Africa")
    contact_person = Column(String(150))
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobcards = relationship("JobCard", back_populates="customer")


class Technician(Base):
    __tablename__ = "technicians"

    id = Column(Integer, primary_key=True)
    employee_code = Column(String(30), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    email = Column(String(200))
    phone = Column(String(50))
    mobile = Column(String(50))
    whatsapp = Column(String(50))
    role = Column(String(50), default="Technician")
    specialties = Column(Text)
    is_active = Column(Boolean, default=True)
    max_jobcards = Column(Integer, default=5)
    current_load = Column(Integer, default=0)
    hourly_rate = Column(Float, default=0.0)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_jobcards = relationship("JobCard", back_populates="assigned_technician")


class JobCard(Base):
    __tablename__ = "jobcards"

    id = Column(Integer, primary_key=True)
    job_number = Column(String(30), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    technician_id = Column(Integer, ForeignKey("technicians.id"))
    status = Column(SAEnum(JobCardStatus), default=JobCardStatus.open)
    priority = Column(SAEnum(Priority), default=Priority.medium)

    title = Column(String(300), nullable=False)
    description = Column(Text)
    site_address = Column(Text)
    site_contact = Column(String(150))
    site_phone = Column(String(50))

    requested_date = Column(Date, default=date.today)
    scheduled_date = Column(Date)
    completed_date = Column(Date)
    due_date = Column(Date)

    estimated_hours = Column(Float, default=0.0)
    actual_hours = Column(Float, default=0.0)
    estimated_cost = Column(Float, default=0.0)
    total_parts_cost = Column(Float, default=0.0)
    total_labour_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    amount_charged = Column(Float, default=0.0)

    customer_po = Column(String(50))
    invoice_number = Column(String(50))
    signed_off = Column(Boolean, default=False)
    signed_off_by = Column(String(150))
    signed_off_at = Column(DateTime)

    internal_notes = Column(Text)
    customer_notes = Column(Text)
    resolution_notes = Column(Text)

    created_by = Column(String(150))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="jobcards")
    assigned_technician = relationship("Technician", back_populates="assigned_jobcards")
    tasks = relationship("JobCardTask", back_populates="jobcard", cascade="all, delete-orphan")
    parts_used = relationship("PartUsed", back_populates="jobcard", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="jobcard", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="jobcard", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="jobcard", cascade="all, delete-orphan")
    status_history = relationship("StatusHistory", back_populates="jobcard", cascade="all, delete-orphan")


class JobCardTask(Base):
    __tablename__ = "jobcard_tasks"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.pending)
    assigned_to = Column(String(150))
    estimated_minutes = Column(Integer, default=0)
    actual_minutes = Column(Integer, default=0)
    notes = Column(Text)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobcard = relationship("JobCard", back_populates="tasks")


class PartUsed(Base):
    __tablename__ = "parts_used"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"), nullable=False)
    part_name = Column(String(200), nullable=False)
    part_sku = Column(String(50))
    quantity = Column(Integer, default=1)
    unit_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    supplier = Column(String(200))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobcard = relationship("JobCard", back_populates="parts_used")


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"), nullable=False)
    technician_name = Column(String(150))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    hours = Column(Float, default=0.0)
    hourly_rate = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    work_description = Column(Text)
    overtime = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobcard = relationship("JobCard", back_populates="time_entries")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"), nullable=False)
    author = Column(String(150), nullable=False)
    body = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobcard = relationship("JobCard", back_populates="comments")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"), nullable=False)
    filename = Column(String(300), nullable=False)
    original_name = Column(String(300))
    file_type = Column(String(50))
    file_size = Column(Integer, default=0)
    uploaded_by = Column(String(150))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobcard = relationship("JobCard", back_populates="attachments")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"), nullable=False)
    from_status = Column(String(30))
    to_status = Column(String(30), nullable=False)
    changed_by = Column(String(150))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobcard = relationship("JobCard", back_populates="status_history")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"))
    recipient = Column(String(200), nullable=False)
    subject = Column(String(300))
    body_preview = Column(String(200))
    status = Column(String(30), default="sent")
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhatsAppLog(Base):
    __tablename__ = "whatsapp_logs"

    id = Column(Integer, primary_key=True)
    jobcard_id = Column(Integer, ForeignKey("jobcards.id"))
    recipient_number = Column(String(50), nullable=False)
    recipient_name = Column(String(150))
    message_preview = Column(String(200))
    message_type = Column(String(30), default="notification")
    status = Column(String(30), default="pending")
    external_id = Column(String(100))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, default="")

    def __repr__(self):
        return f"<Setting {self.key}={self.value}>"


class User(UserMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150))
    role = Column(String(30), default="user")  # admin | technician | user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
