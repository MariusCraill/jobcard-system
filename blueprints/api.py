"""
REST API for JobCard System
Provides endpoints for external integration (mobile app, third-party systems).
"""

from datetime import datetime, date
from flask import Blueprint, jsonify, request
from flask_login import current_user
from database import db_session, get_or_404, first_or_404
from models import (
    JobCard, JobCardStatus, JobCardTask, TaskStatus,
    Customer, Technician, PartUsed, TimeEntry,
    Comment, Attachment, StatusHistory, Priority
)

api_bp = Blueprint("api", __name__)


@api_bp.before_request
def require_api_access():
    """Allow requests with a valid X-API-Key header OR an active login session."""
    from blueprints.admin import get_setting
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    expected = get_setting("api_key", "")
    if key and expected and key == expected:
        return
    if current_user.is_authenticated:
        return
    return jsonify({"error": "Unauthorized. Provide a valid X-API-Key header or log in."}), 401


def _jc_to_dict(jc):
    customer = db_session.get(Customer, jc.customer_id)
    tech = db_session.get(Technician, jc.technician_id) if jc.technician_id else None
    return {
        "id": jc.id,
        "job_number": jc.job_number,
        "title": jc.title,
        "status": jc.status.value,
        "priority": jc.priority.value,
        "customer": customer.name if customer else None,
        "technician": tech.name if tech else None,
        "requested_date": jc.requested_date.isoformat() if jc.requested_date else None,
        "scheduled_date": jc.scheduled_date.isoformat() if jc.scheduled_date else None,
        "due_date": jc.due_date.isoformat() if jc.due_date else None,
        "completed_date": jc.completed_date.isoformat() if jc.completed_date else None,
        "site_address": jc.site_address,
        "description": jc.description,
        "actual_hours": jc.actual_hours,
        "total_cost": jc.total_cost,
        "created_at": jc.created_at.isoformat() if jc.created_at else None,
    }


@api_bp.route("/jobcards")
def api_list_jobcards():
    status = request.args.get("status")
    technician_id = request.args.get("technician_id")
    query = db_session.query(JobCard)
    if status:
        try:
            query = query.filter(JobCard.status == JobCardStatus[status])
        except KeyError:
            return jsonify({"error": f"Invalid status: {status}"}), 400
    if technician_id:
        query = query.filter(JobCard.technician_id == int(technician_id))
    jobcards = query.order_by(JobCard.created_at.desc()).limit(100).all()
    return jsonify([_jc_to_dict(jc) for jc in jobcards])


@api_bp.route("/jobcards/<int:jobcard_id>")
def api_get_jobcard(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    data = _jc_to_dict(jc)
    data["tasks"] = [{
        "id": t.id, "description": t.description, "status": t.status.value,
        "estimated_minutes": t.estimated_minutes, "actual_minutes": t.actual_minutes
    } for t in jc.tasks]
    data["parts"] = [{
        "id": p.id, "part_name": p.part_name, "part_sku": p.part_sku,
        "quantity": p.quantity, "unit_cost": p.unit_cost, "total_cost": p.total_cost
    } for p in jc.parts_used]
    data["time_entries"] = [{
        "id": te.id, "technician_name": te.technician_name,
        "start_time": te.start_time.isoformat() if te.start_time else None,
        "end_time": te.end_time.isoformat() if te.end_time else None,
        "hours": te.hours, "hourly_rate": te.hourly_rate, "total_cost": te.total_cost
    } for te in jc.time_entries]
    data["comments"] = [{
        "id": c.id, "author": c.author, "body": c.body,
        "is_internal": c.is_internal,
        "created_at": c.created_at.isoformat() if c.created_at else None
    } for c in jc.comments]
    data["attachments"] = [{
        "id": a.id, "filename": a.filename, "original_name": a.original_name,
        "file_type": a.file_type, "file_size": a.file_size
    } for a in jc.attachments]
    return jsonify(data)


@api_bp.route("/jobcards/<int:jobcard_id>/status", methods=["PUT"])
def api_update_status(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    data = request.get_json()
    new_status_str = data.get("status")
    if not new_status_str:
        return jsonify({"error": "status is required"}), 400
    try:
        new_status = JobCardStatus[new_status_str]
    except KeyError:
        return jsonify({"error": f"Invalid status: {new_status_str}"}), 400

    old_status = jc.status.value if jc.status else None
    jc.status = new_status
    if new_status == JobCardStatus.completed and not jc.completed_date:
        jc.completed_date = date.today()

    history = StatusHistory(
        jobcard_id=jc.id,
        from_status=old_status,
        to_status=new_status_str,
        changed_by=data.get("changed_by", "API"),
        notes=data.get("notes", ""),
    )
    db_session.add(history)
    db_session.commit()
    return jsonify({"success": True, "jobcard": _jc_to_dict(jc)})


@api_bp.route("/jobcards/<int:jobcard_id>/tasks", methods=["POST"])
def api_add_task(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    data = request.get_json()
    task = JobCardTask(
        jobcard_id=jc.id,
        description=data.get("description", ""),
        estimated_minutes=data.get("estimated_minutes", 0),
        assigned_to=data.get("assigned_to", ""),
        sort_order=data.get("sort_order", 0),
    )
    db_session.add(task)
    db_session.commit()
    return jsonify({"success": True, "task_id": task.id}), 201


@api_bp.route("/jobcards/<int:jobcard_id>/tasks/<int:task_id>", methods=["PUT"])
def api_update_task(jobcard_id, task_id):
    task = first_or_404(
        db_session.query(JobCardTask).filter(
            JobCardTask.id == task_id, JobCardTask.jobcard_id == jobcard_id
        )
    )
    data = request.get_json()
    if "status" in data:
        task.status = TaskStatus[data["status"]]
    if "actual_minutes" in data:
        task.actual_minutes = data["actual_minutes"]
    if "notes" in data:
        task.notes = data["notes"]
    db_session.commit()
    return jsonify({"success": True})


@api_bp.route("/customers")
def api_list_customers():
    customers = db_session.query(Customer).filter(Customer.is_active == True).order_by(Customer.name).all()
    return jsonify([{
        "id": c.id, "name": c.name, "company": c.company,
        "email": c.email, "phone": c.phone, "contact_person": c.contact_person
    } for c in customers])


@api_bp.route("/technicians")
def api_list_technicians():
    techs = db_session.query(Technician).filter(Technician.is_active == True).order_by(Technician.name).all()
    return jsonify([{
        "id": t.id, "employee_code": t.employee_code, "name": t.name,
        "email": t.email, "phone": t.phone, "mobile": t.mobile,
        "role": t.role, "specialties": t.specialties, "hourly_rate": t.hourly_rate
    } for t in techs])


@api_bp.route("/dashboard/stats")
def api_dashboard_stats():
    total = db_session.query(JobCard).count()
    open_count = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.open).count()
    in_progress = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.in_progress).count()
    completed = db_session.query(JobCard).filter(JobCard.status == JobCardStatus.completed).count()
    return jsonify({
        "total": total, "open": open_count,
        "in_progress": in_progress, "completed": completed
    })
