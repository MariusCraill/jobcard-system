from datetime import datetime, timedelta, date
from flask import Blueprint, render_template
from sqlalchemy import func
from database import db_session
from models import JobCard, JobCardStatus, Priority, Customer, Technician

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    total = db_session.query(JobCard).count()
    open_count = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.open).count()
    in_progress = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.in_progress).count()
    completed = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.completed).count()
    closed = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.closed).count()
    on_hold = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.on_hold).count()
    cancelled = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.cancelled).count()

    critical = db_session.query(JobCard).filter(
        JobCard.priority == Priority.critical,
        JobCard.status.notin_([JobCardStatus.completed, JobCardStatus.closed, JobCardStatus.cancelled])
    ).count()
    high = db_session.query(JobCard).filter(
        JobCard.priority == Priority.high,
        JobCard.status.notin_([JobCardStatus.completed, JobCardStatus.closed, JobCardStatus.cancelled])
    ).count()

    today = date.today()
    overdue = db_session.query(JobCard).filter(
        JobCard.due_date < today,
        JobCard.status.notin_([JobCardStatus.completed, JobCardStatus.closed, JobCardStatus.cancelled])
    ).count()

    due_today = db_session.query(JobCard).filter(
        JobCard.due_date == today,
        JobCard.status.notin_([JobCardStatus.completed, JobCardStatus.closed, JobCardStatus.cancelled])
    ).count()

    this_month_start = today.replace(day=1)
    created_this_month = db_session.query(JobCard).filter(JobCard.created_at >= this_month_start).count()
    completed_this_month = db_session.query(JobCard).filter(
        JobCard.completed_date >= this_month_start
    ).count()

    total_customers = db_session.query(Customer).filter(Customer.is_active == True).count()
    total_techs = db_session.query(Technician).filter(Technician.is_active == True).count()

    recent_jobcards = db_session.query(JobCard).order_by(JobCard.created_at.desc()).limit(10).all()

    status_counts = [
        ("Open", open_count, "#1565c0", "open"),
        ("In Progress", in_progress, "#2e7d32", "in_progress"),
        ("On Hold", on_hold, "#f9a825", "on_hold"),
        ("Completed", completed, "#1b5e20", "completed"),
        ("Closed", closed, "#6a1b9a", "closed"),
        ("Cancelled", cancelled, "#bf360c", "cancelled"),
    ]

    return render_template("dashboard.html", **locals())
