from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import db_session, get_or_404
from models import Technician, JobCard

technicians_bp = Blueprint("technicians", __name__)


@technicians_bp.route("/")
def list_technicians():
    search = request.args.get("search", "")
    query = db_session.query(Technician).filter(Technician.is_active == True)
    if search:
        query = query.filter(
            Technician.name.ilike(f"%{search}%") |
            Technician.email.ilike(f"%{search}%") |
            Technician.employee_code.ilike(f"%{search}%")
        )
    technicians = query.order_by(Technician.name).all()
    active_statuses = ['open', 'assigned', 'in_progress', 'on_hold', 'awaiting_parts']
    for t in technicians:
        t.active_jobs = db_session.query(JobCard).filter(
            JobCard.technician_id == t.id,
            JobCard.status.in_(active_statuses)
        ).count()
    return render_template("technicians/list.html", **locals())


@technicians_bp.route("/new", methods=["GET", "POST"])
def new_technician():
    if request.method == "POST":
        tech = Technician(
            employee_code=request.form["employee_code"],
            name=request.form["name"],
            email=request.form.get("email", ""),
            phone=request.form.get("phone", ""),
            mobile=request.form.get("mobile", ""),
            whatsapp=request.form.get("whatsapp", ""),
            role=request.form.get("role", "Technician"),
            specialties=request.form.get("specialties", ""),
            max_jobcards=int(request.form.get("max_jobcards") or 5),
            hourly_rate=float(request.form.get("hourly_rate") or 0),
            notes=request.form.get("notes", ""),
        )
        db_session.add(tech)
        db_session.commit()
        flash("Technician created successfully", "success")
        return redirect(url_for("technicians.list_technicians"))
    return render_template("technicians/form.html", technician=None)


@technicians_bp.route("/<int:tech_id>/edit", methods=["GET", "POST"])
def edit_technician(tech_id):
    tech = get_or_404(Technician, tech_id)
    if request.method == "POST":
        tech.employee_code = request.form["employee_code"]
        tech.name = request.form["name"]
        tech.email = request.form.get("email", "")
        tech.phone = request.form.get("phone", "")
        tech.mobile = request.form.get("mobile", "")
        tech.whatsapp = request.form.get("whatsapp", "")
        tech.role = request.form.get("role", "Technician")
        tech.specialties = request.form.get("specialties", "")
        tech.max_jobcards = int(request.form.get("max_jobcards") or 5)
        tech.hourly_rate = float(request.form.get("hourly_rate") or 0)
        tech.notes = request.form.get("notes", "")
        tech.updated_at = datetime.utcnow()
        db_session.commit()
        flash("Technician updated successfully", "success")
        return redirect(url_for("technicians.list_technicians"))
    return render_template("technicians/form.html", technician=tech)


@technicians_bp.route("/<int:tech_id>/view")
def view_technician(tech_id):
    tech = get_or_404(Technician, tech_id)
    jobcards = db_session.query(JobCard).filter(JobCard.technician_id == tech_id).order_by(JobCard.created_at.desc()).all()
    return render_template("technicians/view.html", **locals())


@technicians_bp.route("/<int:tech_id>/delete", methods=["POST"])
def delete_technician(tech_id):
    tech = get_or_404(Technician, tech_id)
    jobcard_count = db_session.query(JobCard).filter(JobCard.technician_id == tech_id).count()
    if jobcard_count > 0:
        tech.is_active = False
        flash("Technician has job cards — deactivated instead", "warning")
    else:
        db_session.delete(tech)
        flash("Technician deleted", "success")
    db_session.commit()
    return redirect(url_for("technicians.list_technicians"))
