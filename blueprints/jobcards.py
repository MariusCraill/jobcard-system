import os
from datetime import datetime, date
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, jsonify
from database import db_session, get_or_404, first_or_404
from models import (
    JobCard, JobCardStatus, JobCardTask, TaskStatus, Priority,
    Customer, Technician, PartUsed, TimeEntry, Comment, Attachment, StatusHistory
)
from utils.email_sender import (
    send_jobcard_email,
    build_mailto_link,
    generate_status_change_email,
    generate_assignment_email,
    generate_completion_email,
)
from utils.whatsapp import (
    send_whatsapp_message,
    build_wa_web_link,
    build_wa_app_link,
    generate_assignment_message,
    generate_status_message,
    generate_completion_message,
)
from blueprints.admin import get_setting
from utils.pdf_export import generate_jobcard_print_html

jobcards_bp = Blueprint("jobcards", __name__)

UPLOAD_FOLDER = os.environ.get(
    "UPLOAD_FOLDER",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "doc", "docx", "xls", "xlsx", "txt"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _next_job_number():
    from blueprints.admin import get_setting
    from models import Setting
    next_num = _to_int(get_setting("next_job_number", "1001"), 1001)
    job_number = f"JC-{next_num}"
    while db_session.query(JobCard).filter(JobCard.job_number == job_number).first():
        next_num += 1
        job_number = f"JC-{next_num}"
    s = db_session.query(Setting).filter(Setting.key == "next_job_number").first()
    if s:
        s.value = str(next_num + 1)
    else:
        s = Setting(key="next_job_number", value=str(next_num + 1))
        db_session.add(s)
    db_session.commit()
    return job_number


@jobcards_bp.route("/")
def list_jobcards():
    today = date.today()
    search = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    technician_id = request.args.get("technician_id", "")

    query = db_session.query(JobCard)
    if search:
        query = query.filter(
            JobCard.job_number.ilike(f"%{search}%") |
            JobCard.title.ilike(f"%{search}%") |
            JobCard.description.ilike(f"%{search}%")
        )
    if status_filter:
        if status_filter in ("overdue", "due_today"):
            active = JobCard.status.notin_([JobCardStatus.completed, JobCardStatus.closed, JobCardStatus.cancelled])
            if status_filter == "overdue":
                query = query.filter(JobCard.due_date < today, active)
            else:
                query = query.filter(JobCard.due_date == today, active)
        else:
            try:
                query = query.filter(JobCard.status == JobCardStatus[status_filter])
            except KeyError:
                pass
    if priority_filter:
        priorities = [p.strip() for p in priority_filter.split(",") if p.strip()]
        valid = [Priority[p] for p in priorities if p in Priority.__members__]
        if valid:
            query = query.filter(JobCard.priority.in_(valid))
    if technician_id:
        query = query.filter(JobCard.technician_id == int(technician_id))

    jobcards = query.order_by(JobCard.created_at.desc()).all()
    customers = db_session.query(Customer).filter(Customer.is_active == True).order_by(Customer.name).all()
    technicians = db_session.query(Technician).filter(Technician.is_active == True).order_by(Technician.name).all()
    return render_template("jobcards/list.html", **locals())


@jobcards_bp.route("/new", methods=["GET", "POST"])
def new_jobcard():
    if request.method == "POST":
        customer_id = request.form.get("customer_id", type=int)
        if not customer_id:
            flash("Customer is required", "danger")
            return redirect(url_for("jobcards.new_jobcard"))

        try:
            priority = Priority[request.form.get("priority", "medium")]
        except KeyError:
            priority = Priority.medium

        jc = JobCard(
            job_number=_next_job_number(),
            customer_id=customer_id,
            technician_id=request.form.get("technician_id", type=int),
            priority=priority,
            title=request.form["title"],
            description=request.form.get("description", ""),
            site_address=request.form.get("site_address", ""),
            site_contact=request.form.get("site_contact", ""),
            site_phone=request.form.get("site_phone", ""),
            requested_date=date.today(),
            scheduled_date=datetime.strptime(request.form["scheduled_date"], "%Y-%m-%d").date() if request.form.get("scheduled_date") else None,
            due_date=datetime.strptime(request.form["due_date"], "%Y-%m-%d").date() if request.form.get("due_date") else None,
            estimated_hours=_to_float(request.form.get("estimated_hours")),
            estimated_cost=_to_float(request.form.get("estimated_cost")),
            customer_po=request.form.get("customer_po", ""),
            customer_notes=request.form.get("customer_notes", ""),
            internal_notes=request.form.get("internal_notes", ""),
            created_by=request.form.get("created_by", "System"),
        )
        db_session.add(jc)
        db_session.flush()

        history = StatusHistory(
            jobcard_id=jc.id,
            to_status=JobCardStatus.open.value,
            changed_by=jc.created_by,
            notes="Job card created",
        )
        db_session.add(history)

        if jc.technician_id:
            jc.status = JobCardStatus.assigned
            tech = db_session.get(Technician, jc.technician_id)
            if tech:
                _send_assignment_notifications(jc, tech)

        task_descriptions = request.form.getlist("task_description[]")
        task_minutes = request.form.getlist("task_estimated[]")
        for i, desc in enumerate(task_descriptions):
            if desc.strip():
                task = JobCardTask(
                    jobcard_id=jc.id,
                    description=desc.strip(),
                    estimated_minutes=_to_int(task_minutes[i]) if i < len(task_minutes) else 0,
                    sort_order=i,
                )
                db_session.add(task)

        db_session.commit()
        flash(f"Job card {jc.job_number} created successfully", "success")
        return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))

    customers = db_session.query(Customer).filter(Customer.is_active == True).order_by(Customer.name).all()
    technicians = db_session.query(Technician).filter(Technician.is_active == True).order_by(Technician.name).all()
    return render_template("jobcards/form.html", jobcard=None, **locals())


@jobcards_bp.route("/<int:jobcard_id>")
def view_jobcard(jobcard_id):
    today = date.today()
    jc = get_or_404(JobCard, jobcard_id)
    tasks = db_session.query(JobCardTask).filter(JobCardTask.jobcard_id == jobcard_id).order_by(JobCardTask.sort_order).all()
    parts = db_session.query(PartUsed).filter(PartUsed.jobcard_id == jobcard_id).all()
    times = db_session.query(TimeEntry).filter(TimeEntry.jobcard_id == jobcard_id).order_by(TimeEntry.start_time.desc()).all()
    comments = db_session.query(Comment).filter(Comment.jobcard_id == jobcard_id).order_by(Comment.created_at.desc()).all()
    attachments = db_session.query(Attachment).filter(Attachment.jobcard_id == jobcard_id).all()
    history = db_session.query(StatusHistory).filter(StatusHistory.jobcard_id == jobcard_id).order_by(StatusHistory.created_at.desc()).all()
    technicians = db_session.query(Technician).filter(Technician.is_active == True).order_by(Technician.name).all()
    return render_template("jobcards/view.html", **locals())


@jobcards_bp.route("/<int:jobcard_id>/edit", methods=["GET", "POST"])
def edit_jobcard(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    if request.method == "POST":
        old_tech_id = jc.technician_id
        old_status = jc.status.value if jc.status else None

        jc.title = request.form["title"]
        jc.description = request.form.get("description", "")
        jc.customer_id = request.form.get("customer_id", type=int)
        jc.technician_id = request.form.get("technician_id", type=int)
        try:
            jc.priority = Priority[request.form.get("priority", "medium")]
        except KeyError:
            pass
        jc.site_address = request.form.get("site_address", "")
        jc.site_contact = request.form.get("site_contact", "")
        jc.site_phone = request.form.get("site_phone", "")
        jc.scheduled_date = datetime.strptime(request.form["scheduled_date"], "%Y-%m-%d").date() if request.form.get("scheduled_date") else None
        jc.due_date = datetime.strptime(request.form["due_date"], "%Y-%m-%d").date() if request.form.get("due_date") else None
        jc.estimated_hours = _to_float(request.form.get("estimated_hours"))
        jc.estimated_cost = _to_float(request.form.get("estimated_cost"))
        jc.customer_po = request.form.get("customer_po", "")
        jc.customer_notes = request.form.get("customer_notes", "")
        jc.internal_notes = request.form.get("internal_notes", "")
        jc.updated_at = datetime.utcnow()

        if jc.technician_id and old_tech_id != jc.technician_id:
            tech = db_session.get(Technician, jc.technician_id)
            if tech:
                _send_assignment_notifications(jc, tech)

        db_session.commit()
        flash("Job card updated successfully", "success")
        return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))

    customers = db_session.query(Customer).filter(Customer.is_active == True).order_by(Customer.name).all()
    technicians = db_session.query(Technician).filter(Technician.is_active == True).order_by(Technician.name).all()
    tasks = db_session.query(JobCardTask).filter(JobCardTask.jobcard_id == jobcard_id).order_by(JobCardTask.sort_order).all()
    return render_template("jobcards/form.html", jobcard=jc, **locals())


@jobcards_bp.route("/<int:jobcard_id>/status", methods=["POST"])
def update_status(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    new_status_str = request.form.get("status", "")
    notes = request.form.get("notes", "")
    changed_by = request.form.get("changed_by", "System")

    try:
        new_status = JobCardStatus[new_status_str]
    except KeyError:
        flash(f"Invalid status: {new_status_str}", "danger")
        return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))

    old_status = jc.status.value if jc.status else None
    jc.status = new_status
    if new_status == JobCardStatus.completed and not jc.completed_date:
        jc.completed_date = date.today()
    jc.updated_at = datetime.utcnow()

    history = StatusHistory(
        jobcard_id=jc.id,
        from_status=old_status,
        to_status=new_status_str,
        changed_by=changed_by,
        notes=notes,
    )
    db_session.add(history)

    customer_email = jc.customer.email if jc.customer else None
    tech_email = jc.assigned_technician.email if jc.assigned_technician else None

    if new_status == JobCardStatus.completed:
        subject, body = generate_completion_email(jc)
        if customer_email:
            send_jobcard_email(customer_email, subject, body, jobcard_id=jc.id)
        if tech_email:
            send_jobcard_email(tech_email, subject, body, jobcard_id=jc.id)
        tech_whatsapp = jc.assigned_technician.whatsapp if jc.assigned_technician else None
        if tech_whatsapp:
            msg = generate_completion_message(jc)
            send_whatsapp_message(tech_whatsapp, msg, jobcard_id=jc.id, message_type="completion")
    elif old_status:
        subject, body = generate_status_change_email(jc, old_status, new_status_str)
        if customer_email:
            send_jobcard_email(customer_email, subject, body, jobcard_id=jc.id)
        if tech_email:
            send_jobcard_email(tech_email, subject, body, jobcard_id=jc.id)
        tech_whatsapp = jc.assigned_technician.whatsapp if jc.assigned_technician else None
        if tech_whatsapp:
            msg = generate_status_message(jc, old_status, new_status_str)
            send_whatsapp_message(tech_whatsapp, msg, jobcard_id=jc.id, message_type="status_change")

    db_session.commit()
    flash(f"Status updated to {new_status_str.replace('_', ' ').title()}", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


def _send_assignment_notifications(jc, tech):
    subject, body = generate_assignment_email(jc)
    if tech.email:
        send_jobcard_email(tech.email, subject, body, jobcard_id=jc.id)
    if tech.whatsapp:
        msg = generate_assignment_message(jc)
        send_whatsapp_message(tech.whatsapp, msg, jobcard_id=jc.id, message_type="assignment")


@jobcards_bp.route("/<int:jobcard_id>/add-task", methods=["POST"])
def add_task(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    task = JobCardTask(
        jobcard_id=jc.id,
        description=request.form["description"],
        estimated_minutes=_to_int(request.form.get("estimated_minutes")),
        assigned_to=request.form.get("assigned_to", ""),
        notes=request.form.get("notes", ""),
        sort_order=db_session.query(JobCardTask).filter(JobCardTask.jobcard_id == jc.id).count() + 1,
    )
    db_session.add(task)
    db_session.commit()
    flash("Task added", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_task(jobcard_id, task_id):
    task = first_or_404(
        db_session.query(JobCardTask).filter(JobCardTask.id == task_id, JobCardTask.jobcard_id == jobcard_id)
    )
    task.status = TaskStatus.completed if task.status != TaskStatus.completed else TaskStatus.pending
    db_session.commit()
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jobcard_id))


@jobcards_bp.route("/<int:jobcard_id>/delete-task/<int:task_id>", methods=["POST"])
def delete_task(jobcard_id, task_id):
    task = first_or_404(
        db_session.query(JobCardTask).filter(JobCardTask.id == task_id, JobCardTask.jobcard_id == jobcard_id)
    )
    db_session.delete(task)
    db_session.commit()
    flash("Task deleted", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jobcard_id))


@jobcards_bp.route("/<int:jobcard_id>/add-part", methods=["POST"])
def add_part(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    qty = _to_int(request.form.get("quantity"), 1)
    unit_cost = _to_float(request.form.get("unit_cost"))
    part = PartUsed(
        jobcard_id=jc.id,
        part_name=request.form["part_name"],
        part_sku=request.form.get("part_sku", ""),
        quantity=qty,
        unit_cost=unit_cost,
        total_cost=qty * unit_cost,
        supplier=request.form.get("supplier", ""),
        notes=request.form.get("notes", ""),
    )
    db_session.add(part)
    _recalc_costs(jc)
    db_session.commit()
    flash("Part added", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/delete-part/<int:part_id>", methods=["POST"])
def delete_part(jobcard_id, part_id):
    part = first_or_404(
        db_session.query(PartUsed).filter(PartUsed.id == part_id, PartUsed.jobcard_id == jobcard_id)
    )
    jc = db_session.get(JobCard, jobcard_id)
    db_session.delete(part)
    if jc:
        _recalc_costs(jc)
    db_session.commit()
    flash("Part removed", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jobcard_id))


@jobcards_bp.route("/<int:jobcard_id>/add-time", methods=["POST"])
def add_time(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    from blueprints.admin import get_setting
    rate = _to_float(request.form.get("hourly_rate")) or _to_float(get_setting("default_hourly_rate"), 350)
    start_str = request.form.get("start_time", "")
    end_str = request.form.get("end_time", "")
    hours = _to_float(request.form.get("hours"))

    start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M") if start_str else None
    end_time = datetime.strptime(end_str, "%Y-%m-%dT%H:%M") if end_str else None

    if not hours and start_time and end_time:
        hours = round((end_time - start_time).total_seconds() / 3600, 2)

    entry = TimeEntry(
        jobcard_id=jc.id,
        technician_name=request.form.get("technician_name", ""),
        start_time=start_time,
        end_time=end_time,
        hours=hours,
        hourly_rate=rate,
        total_cost=hours * rate,
        work_description=request.form.get("work_description", ""),
        overtime=bool(request.form.get("overtime")),
    )
    db_session.add(entry)
    _recalc_time(jc)
    db_session.commit()
    flash("Time entry added", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/delete-time/<int:time_id>", methods=["POST"])
def delete_time(jobcard_id, time_id):
    entry = first_or_404(
        db_session.query(TimeEntry).filter(TimeEntry.id == time_id, TimeEntry.jobcard_id == jobcard_id)
    )
    jc = db_session.query(JobCard).get(jobcard_id)
    db_session.delete(entry)
    if jc:
        _recalc_time(jc)
    db_session.commit()
    flash("Time entry removed", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jobcard_id))


def _recalc_costs(jc):
    parts = db_session.query(PartUsed).filter(PartUsed.jobcard_id == jc.id).all()
    jc.total_parts_cost = sum(p.total_cost for p in parts)


def _recalc_time(jc):
    entries = db_session.query(TimeEntry).filter(TimeEntry.jobcard_id == jc.id).all()
    jc.actual_hours = sum(e.hours for e in entries)
    jc.total_labour_cost = sum(e.total_cost for e in entries)
    jc.total_cost = jc.total_parts_cost + jc.total_labour_cost


@jobcards_bp.route("/<int:jobcard_id>/add-comment", methods=["POST"])
def add_comment(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    comment = Comment(
        jobcard_id=jc.id,
        author=request.form.get("author", "System"),
        body=request.form["body"],
        is_internal=bool(request.form.get("is_internal")),
    )
    db_session.add(comment)
    db_session.commit()
    flash("Comment added", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/upload", methods=["POST"])
def upload_attachment(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file = request.files.get("file") or request.files.get("camera_file")
    if file and file.filename and _allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        attachment = Attachment(
            jobcard_id=jc.id,
            filename=filename,
            original_name=file.filename,
            file_type=file.content_type,
            file_size=os.path.getsize(filepath),
            uploaded_by=request.form.get("uploaded_by", "System"),
        )
        db_session.add(attachment)
        db_session.commit()
        flash("File uploaded", "success")
    else:
        flash("Invalid file type or no file selected", "danger")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/attachment/<int:attachment_id>")
def download_attachment(jobcard_id, attachment_id):
    attachment = first_or_404(
        db_session.query(Attachment).filter(
            Attachment.id == attachment_id, Attachment.jobcard_id == jobcard_id
        )
    )
    filepath = os.path.join(UPLOAD_FOLDER, attachment.filename)
    if not os.path.exists(filepath):
        flash("File no longer available", "warning")
        return redirect(url_for("jobcards.view_jobcard", jobcard_id=jobcard_id))
    return send_file(filepath, as_attachment=True, download_name=attachment.original_name or attachment.filename)


@jobcards_bp.route("/<int:jobcard_id>/print")
def print_jobcard(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    html = generate_jobcard_print_html(jc)
    return html


@jobcards_bp.route("/<int:jobcard_id>/sign-off", methods=["POST"])
def sign_off(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    jc.signed_off = True
    jc.signed_off_by = request.form.get("signed_off_by", "")
    signature = request.form.get("signature", "").strip()
    if signature:
        if signature.startswith("data:image/png;base64,"):
            jc.signature_data = signature
        else:
            flash("Invalid signature data", "danger")
            return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))
    jc.signed_off_at = datetime.utcnow()
    jc.updated_at = datetime.utcnow()
    db_session.commit()
    flash("Job card signed off", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/email", methods=["POST"])
def email_jobcard(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    recipient = request.form.get("recipient", "")
    subject = request.form.get("subject", f"Job Card {jc.job_number} - {jc.title}")
    body = request.form.get("body", f"Please find attached Job Card {jc.job_number}.")
    html = generate_jobcard_print_html(jc)
    pdf_bytes = html.encode("utf-8")

    email_method = get_setting("email_method", "smtp")

    if email_method == "client":
        full_body = body + "\n\n---\n" + html[:500]
        mailto = build_mailto_link(recipient, subject, full_body)
        flash(f"<i class='bi bi-envelope'></i> Email link generated: <a href='{mailto}' target='_blank' class='alert-link'>Open Email Client</a>", "info")
    else:
        success, msg = send_jobcard_email(
            to_email=recipient,
            subject=subject,
            body_text=body,
            pdf_bytes=pdf_bytes,
            pdf_filename=f"{jc.job_number}.html",
            jobcard_id=jc.id,
        )
        if success:
            flash("Email sent successfully", "success")
        else:
            flash(f"Failed to send email: {msg}", "danger")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/send-whatsapp", methods=["POST"])
def send_whatsapp(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    number = request.form.get("number", "")
    message = request.form.get("message", "")
    wa_action = get_setting("whatsapp_action", "api")

    if wa_action == "web":
        link = build_wa_web_link(number, message)
        flash(f"<i class='bi bi-whatsapp'></i> <a href='{link}' target='_blank' class='alert-link'>Open WhatsApp Web</a> to send the message", "info")
    elif wa_action == "app":
        link = build_wa_app_link(number, message)
        flash(f"<i class='bi bi-whatsapp'></i> <a href='{link}' class='alert-link'>Open WhatsApp App</a> to send the message", "info")
    else:
        success, msg = send_whatsapp_message(number, message, jobcard_id=jc.id)
        if success:
            flash("WhatsApp message sent", "success")
        else:
            flash(f"WhatsApp: {msg}", "warning")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@jobcards_bp.route("/<int:jobcard_id>/delete", methods=["POST"])
def delete_jobcard(jobcard_id):
    jc = get_or_404(JobCard, jobcard_id)
    db_session.delete(jc)
    db_session.commit()
    flash("Job card deleted", "success")
    return redirect(url_for("jobcards.list_jobcards"))
