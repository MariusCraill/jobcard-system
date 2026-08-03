from datetime import datetime, date
from flask import Blueprint, render_template, request, send_file
from sqlalchemy import func
from database import db_session
from models import JobCard, JobCardStatus, Priority, Customer, Technician
from utils.pdf_export import generate_jobcard_excel_export

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/")
def index():
    return render_template("reports/index.html")


@reports_bp.route("/export-excel")
def export_excel():
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    technician_id = request.args.get("technician_id", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    output = generate_jobcard_excel_export(
        status_filter=status_filter if status_filter else None,
        priority_filter=priority_filter if priority_filter else None,
        technician_id=technician_id if technician_id else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
    )
    filename = f"jobcards_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@reports_bp.route("/summary")
def summary():
    total = db_session.query(JobCard).count()
    open_count = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.open).count()
    in_progress = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.in_progress).count()
    completed = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.completed).count()

    total_revenue = db_session.query(func.coalesce(func.sum(JobCard.amount_charged), 0)).filter(
        JobCard.status.in_([JobCardStatus.completed, JobCardStatus.closed])
    ).scalar()

    total_cost = db_session.query(func.coalesce(func.sum(JobCard.total_cost), 0)).filter(
        JobCard.status.in_([JobCardStatus.completed, JobCardStatus.closed])
    ).scalar()

    avg_hours = db_session.query(func.coalesce(func.avg(JobCard.actual_hours), 0)).filter(
        JobCard.status.in_([JobCardStatus.completed, JobCardStatus.closed])
    ).scalar()

    customers = db_session.query(Customer).filter(Customer.is_active == True).count()
    technicians = db_session.query(Technician).filter(Technician.is_active == True).count()

    return render_template("reports/summary.html", **locals())
