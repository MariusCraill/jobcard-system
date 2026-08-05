from datetime import datetime, date
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from database import db_session, get_or_404
from models import (
    Ticket, TicketComment, TicketStatus, Priority, JobCard, JobCardStatus, Customer, Setting,
)
from blueprints.admin import get_setting
from blueprints.jobcards import _next_job_number
from utils.email_sender import send_ticket_email

tickets_bp = Blueprint("tickets", __name__)

# Endpoints accessible without logging in (client-facing).
PUBLIC_ENDPOINTS = ("tickets.new_ticket", "tickets.ticket_lookup")

STATUS_BADGES = {
    "open": "primary",
    "in_progress": "info",
    "resolved": "success",
    "closed": "dark",
    "cancelled": "danger",
}


def staff_required(f):
    """End users may view/track their own tickets but not manage them."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        if current_user.role == "user":
            flash("You do not have permission to perform that action", "danger")
            return redirect(url_for("tickets.list_tickets"))
        return f(*args, **kwargs)
    return wrapper


def _user_ticket_filter(query):
    """Restrict a ticket query to the current end user's own tickets."""
    if current_user.role != "user":
        return query
    email = (current_user.email or "").strip().lower()
    if email:
        from sqlalchemy import func
        return query.filter(func.lower(Ticket.email) == email)
    return query.filter(Ticket.customer_name == (current_user.full_name or ""))


def _can_access(ticket):
    """Whether the current user may view this ticket (end users only see their own)."""
    if current_user.role != "user":
        return True
    email = (current_user.email or "").strip().lower()
    if email and ticket.email and ticket.email.strip().lower() == email:
        return True
    return bool(ticket.customer_name and ticket.customer_name == (current_user.full_name or ""))


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _next_ticket_number():
    next_num = _to_int(get_setting("next_ticket_number", "1001"), 1001)
    ticket_number = f"TKT-{next_num}"
    while db_session.query(Ticket).filter(Ticket.ticket_number == ticket_number).first():
        next_num += 1
        ticket_number = f"TKT-{next_num}"
    s = db_session.query(Setting).filter(Setting.key == "next_ticket_number").first()
    if s:
        s.value = str(next_num + 1)
    else:
        s = Setting(key="next_ticket_number", value=str(next_num + 1))
        db_session.add(s)
    db_session.commit()
    return ticket_number


# ---------------------------------------------------------------------------
# Client-facing (public) pages
# ---------------------------------------------------------------------------

@tickets_bp.route("/new", methods=["GET", "POST"])
def new_ticket():
    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        if not customer_name or not subject:
            flash("Your name and a subject are required", "danger")
            return redirect(url_for("tickets.new_ticket"))
        try:
            priority = Priority[request.form.get("priority", "medium")]
        except KeyError:
            priority = Priority.medium

        email = request.form.get("email", "").strip()
        if current_user.is_authenticated and not email:
            email = current_user.email or ""

        ticket = Ticket(
            ticket_number=_next_ticket_number(),
            customer_name=customer_name,
            company=request.form.get("company", "").strip(),
            email=email,
            phone=request.form.get("phone", "").strip(),
            subject=subject,
            description=description,
            priority=priority,
            status=TicketStatus.open,
            source="portal" if current_user.is_authenticated else "web",
        )
        db_session.add(ticket)
        db_session.commit()
        flash(
            f"Ticket {ticket.ticket_number} logged successfully. "
            "Keep this number and your email to track the ticket.",
            "success",
        )
        if ticket.email:
            send_ticket_email(
                ticket,
                subject=f"Ticket {ticket.ticket_number} received - {ticket.subject}",
                body=(
                    f"Hello {ticket.customer_name},\n\n"
                    f"Thank you. Your ticket {ticket.ticket_number} has been logged.\n\n"
                    f"Subject: {ticket.subject}\n"
                    f"Priority: {ticket.priority.value.upper()}\n\n"
                    "Keep your ticket number handy. You can track progress at any time "
                    "using the ticket tracking page, or by logging in to your account.\n\n"
                    f"Regards,\n{get_setting('company_name', 'Support Team')}"
                ),
            )
        return render_template("tickets/public_track.html", ticket=ticket, comments=[])

    prefill = {}
    if current_user.is_authenticated:
        prefill = {
            "customer_name": current_user.full_name or current_user.username,
            "email": current_user.email or "",
        }
    return render_template("tickets/public_new.html", prefill=prefill)


@tickets_bp.route("/lookup", methods=["GET", "POST"])
def ticket_lookup():
    ticket = None
    comments = []
    if request.method == "POST":
        ticket_number = request.form.get("ticket_number", "").strip()
        email = request.form.get("email", "").strip()
        ticket = db_session.query(Ticket).filter(
            Ticket.ticket_number == ticket_number
        ).first()
        if not ticket:
            flash("No ticket found with that number", "danger")
        elif ticket.email and ticket.email.lower() != email.lower():
            flash("The email does not match this ticket", "danger")
            ticket = None
        else:
            comments = db_session.query(TicketComment).filter(
                TicketComment.ticket_id == ticket.id,
                TicketComment.is_internal == False,
            ).order_by(TicketComment.created_at.asc()).all()
    return render_template("tickets/public_track.html", ticket=ticket, comments=comments)


# ---------------------------------------------------------------------------
# Staff pages (login required)
# ---------------------------------------------------------------------------

@tickets_bp.route("/")
def list_tickets():
    status_filter = request.args.get("status", "")
    query = db_session.query(Ticket)
    if status_filter:
        try:
            query = query.filter(Ticket.status == TicketStatus[status_filter])
        except KeyError:
            pass
    query = _user_ticket_filter(query)
    tickets = query.order_by(Ticket.created_at.desc()).all()
    return render_template("tickets/list.html", tickets=tickets, status_filter=status_filter)


@tickets_bp.route("/<int:ticket_id>")
def view_ticket(ticket_id):
    ticket = get_or_404(Ticket, ticket_id)
    if not _can_access(ticket):
        flash("You do not have permission to view that ticket", "danger")
        return redirect(url_for("tickets.list_tickets"))
    comments = db_session.query(TicketComment).filter(
        TicketComment.ticket_id == ticket.id
    ).order_by(TicketComment.created_at.asc()).all()
    return render_template("tickets/view.html", ticket=ticket, comments=comments)


@tickets_bp.route("/<int:ticket_id>/edit", methods=["GET", "POST"])
@staff_required
def edit_ticket(ticket_id):
    ticket = get_or_404(Ticket, ticket_id)
    if request.method == "POST":
        ticket.customer_name = request.form.get("customer_name", "").strip() or ticket.customer_name
        ticket.company = request.form.get("company", "").strip()
        ticket.email = request.form.get("email", "").strip()
        ticket.phone = request.form.get("phone", "").strip()
        ticket.subject = request.form.get("subject", "").strip() or ticket.subject
        ticket.description = request.form.get("description", "").strip()
        try:
            ticket.priority = Priority[request.form.get("priority", "medium")]
        except KeyError:
            ticket.priority = Priority.medium
        ticket.assigned_to = request.form.get("assigned_to", "").strip()
        ticket.internal_notes = request.form.get("internal_notes", "").strip()
        ticket.updated_at = datetime.utcnow()
        db_session.commit()
        flash("Ticket updated", "success")
        return redirect(url_for("tickets.view_ticket", ticket_id=ticket.id))
    return render_template("tickets/form.html", ticket=ticket)


@tickets_bp.route("/<int:ticket_id>/status", methods=["POST"])
@staff_required
def update_ticket_status(ticket_id):
    ticket = get_or_404(Ticket, ticket_id)
    try:
        new_status = TicketStatus[request.form.get("status", "")]
    except KeyError:
        flash("Invalid status", "danger")
        return redirect(url_for("tickets.view_ticket", ticket_id=ticket.id))
    ticket.status = new_status
    if new_status == TicketStatus.resolved and not ticket.resolved_at:
        ticket.resolved_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    db_session.commit()
    flash(f"Ticket status changed to {new_status.value.replace('_', ' ').title()}", "success")
    if ticket.email and new_status in (TicketStatus.resolved, TicketStatus.closed):
        send_ticket_email(
            ticket,
            subject=f"Update on ticket {ticket.ticket_number} - {ticket.subject}",
            body=(
                f"Hello {ticket.customer_name},\n\n"
                f"Your ticket {ticket.ticket_number} has been updated.\n\n"
                f"New status: {new_status.value.replace('_', ' ').title()}\n\n"
                "You can track the full history of this ticket at any time using the "
                "ticket tracking page, or by logging in to your account.\n\n"
                f"Regards,\n{get_setting('company_name', 'Support Team')}"
            ),
        )
    return redirect(url_for("tickets.view_ticket", ticket_id=ticket.id))


@tickets_bp.route("/<int:ticket_id>/comment", methods=["POST"])
@staff_required
def add_ticket_comment(ticket_id):
    ticket = get_or_404(Ticket, ticket_id)
    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty", "danger")
        return redirect(url_for("tickets.view_ticket", ticket_id=ticket.id))
    comment = TicketComment(
        ticket_id=ticket.id,
        author=request.form.get("author", "").strip()
        or (current_user.full_name or current_user.username),
        body=body,
        is_internal=True if request.form.get("is_internal") else False,
    )
    db_session.add(comment)
    ticket.updated_at = datetime.utcnow()
    db_session.commit()
    flash("Comment added", "success")
    return redirect(url_for("tickets.view_ticket", ticket_id=ticket.id))


@tickets_bp.route("/<int:ticket_id>/convert", methods=["POST"])
@staff_required
def convert_to_jobcard(ticket_id):
    ticket = get_or_404(Ticket, ticket_id)
    if ticket.jobcard_id:
        flash("This ticket is already converted to a job card", "warning")
        return redirect(url_for("tickets.view_ticket", ticket_id=ticket.id))

    customer = None
    if ticket.email:
        customer = db_session.query(Customer).filter(Customer.email == ticket.email).first()
    if not customer and ticket.phone:
        customer = db_session.query(Customer).filter(Customer.phone == ticket.phone).first()
    if not customer:
        customer = Customer(
            name=ticket.customer_name,
            company=ticket.company or "",
            email=ticket.email or "",
            phone=ticket.phone or "",
            is_active=True,
        )
        db_session.add(customer)
        db_session.flush()

    jc = JobCard(
        job_number=_next_job_number(),
        customer_id=customer.id,
        priority=ticket.priority,
        status=JobCardStatus.open,
        title=ticket.subject,
        description=ticket.description,
        requested_date=date.today(),
        created_by=current_user.full_name or current_user.username,
    )
    db_session.add(jc)
    db_session.flush()

    ticket.jobcard_id = jc.id
    ticket.status = TicketStatus.closed
    ticket.updated_at = datetime.utcnow()
    db_session.add(TicketComment(
        ticket_id=ticket.id,
        author=current_user.full_name or current_user.username,
        body=f"Converted to job card {jc.job_number}.",
        is_internal=False,
    ))
    db_session.commit()
    flash(f"Ticket converted to job card {jc.job_number}", "success")
    return redirect(url_for("jobcards.view_jobcard", jobcard_id=jc.id))


@tickets_bp.route("/<int:ticket_id>/delete", methods=["POST"])
@staff_required
def delete_ticket(ticket_id):
    ticket = get_or_404(Ticket, ticket_id)
    db_session.query(TicketComment).filter(TicketComment.ticket_id == ticket.id).delete(synchronize_session=False)
    db_session.delete(ticket)
    db_session.commit()
    flash("Ticket deleted", "success")
    return redirect(url_for("tickets.list_tickets"))
