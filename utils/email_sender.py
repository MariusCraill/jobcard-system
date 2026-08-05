import smtplib
import os
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from database import db_session
from models import EmailLog, Setting


def _get_setting(key, default=""):
    s = db_session.query(Setting).filter(Setting.key == key).first()
    return s.value if s and s.value else default


def build_mailto_link(to_email, subject, body_text):
    """Generate a mailto: URL that opens the user's default email client."""
    params = urllib.parse.urlencode({
        "subject": subject,
        "body": body_text
    })
    return f"mailto:{to_email}?{params}"


def _send_smtp(to_email, subject, body_text, jobcard_id=None, ticket_id=None):
    """Send a plain-text email via the configured SMTP server and log the result."""
    from_email = _get_setting("smtp_from_email", os.environ.get("SMTP_FROM_EMAIL", "noreply@jobcardsystem.co.za"))
    smtp_host = _get_setting("smtp_host", os.environ.get("SMTP_HOST", ""))
    smtp_port = int(_get_setting("smtp_port", os.environ.get("SMTP_PORT", "587")))
    smtp_user = _get_setting("smtp_user", os.environ.get("SMTP_USER", ""))
    smtp_pass = _get_setting("smtp_pass", os.environ.get("SMTP_PASS", ""))

    if not smtp_host:
        log = EmailLog(jobcard_id=jobcard_id, ticket_id=ticket_id, recipient=to_email,
                       subject=subject, body_preview=body_text[:200], status="failed",
                       error_message="SMTP not configured")
        db_session.add(log)
        db_session.commit()
        return False, "SMTP not configured"

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            if smtp_user:
                server.starttls()
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        log = EmailLog(jobcard_id=jobcard_id, ticket_id=ticket_id, recipient=to_email,
                       subject=subject, body_preview=body_text[:200], status="sent")
        db_session.add(log)
        db_session.commit()
        return True, "Email sent successfully"
    except Exception as e:
        log = EmailLog(jobcard_id=jobcard_id, ticket_id=ticket_id, recipient=to_email,
                       subject=subject, body_preview=body_text[:200], status="failed",
                       error_message=str(e))
        db_session.add(log)
        db_session.commit()
        return False, str(e)


def send_ticket_email(ticket, subject, body):
    """Send a ticket notification to the client (no-op if not configured)."""
    if not ticket.email:
        return False, "No recipient email address"
    if _get_setting("email_method", "smtp") != "smtp":
        return False, "SMTP not configured (email_method is not smtp)"
    return _send_smtp(ticket.email, subject, body, ticket_id=ticket.id)


def send_test_email(to_email):
    """Send a test message using the configured SMTP settings."""
    subject = f"Test email from {_get_setting('company_name', 'JobCard System')}"
    body = (
        "This is a test email from your Job Card System.\n\n"
        "If you received this, your SMTP settings are working correctly.\n\n"
        f"Regards,\n{_get_setting('company_name', 'Support Team')}"
    )
    return _send_smtp(to_email, subject, body)


def send_jobcard_email(to_email, subject, body_text, pdf_bytes=None, pdf_filename=None, jobcard_id=None):
    if not to_email:
        return False, "No recipient email address"

    email_method = _get_setting("email_method", "smtp")

    # Client mode — return mailto link instead of sending
    if email_method == "client":
        mailto_link = build_mailto_link(to_email, subject, body_text)
        log = EmailLog(jobcard_id=jobcard_id, recipient=to_email, subject=subject,
                       body_preview=body_text[:200], status="mailto_link")
        db_session.add(log)
        db_session.commit()
        return True, mailto_link

    # SMTP mode — send via configured server
    from_email = _get_setting("smtp_from_email", os.environ.get("SMTP_FROM_EMAIL", "noreply@jobcardsystem.co.za"))
    smtp_host = _get_setting("smtp_host", os.environ.get("SMTP_HOST", ""))
    smtp_port = int(_get_setting("smtp_port", os.environ.get("SMTP_PORT", "587")))
    smtp_user = _get_setting("smtp_user", os.environ.get("SMTP_USER", ""))
    smtp_pass = _get_setting("smtp_pass", os.environ.get("SMTP_PASS", ""))

    if not smtp_host:
        log = EmailLog(jobcard_id=jobcard_id, recipient=to_email, subject=subject,
                       body_preview=body_text[:200], status="failed", error_message="SMTP not configured")
        db_session.add(log)
        db_session.commit()
        return False, "SMTP not configured"

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    if pdf_bytes and pdf_filename:
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(pdf_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header("Content-Disposition", f"attachment; filename={pdf_filename}")
        msg.attach(attachment)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            if smtp_user:
                server.starttls()
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        log = EmailLog(jobcard_id=jobcard_id, recipient=to_email, subject=subject,
                       body_preview=body_text[:200], status="sent")
        db_session.add(log)
        db_session.commit()
        return True, "Email sent successfully"
    except Exception as e:
        log = EmailLog(jobcard_id=jobcard_id, recipient=to_email, subject=subject,
                       body_preview=body_text[:200], status="failed", error_message=str(e))
        db_session.add(log)
        db_session.commit()
        return False, str(e)


def generate_status_change_email(jobcard, old_status, new_status):
    subject = f"Job Card {jobcard.job_number} Status: {old_status} → {new_status}"
    body = f"""Job Card {jobcard.job_number} - {jobcard.title}

Status Change: {old_status} → {new_status}

Customer: {jobcard.customer.name if jobcard.customer else 'N/A'}
Technician: {jobcard.assigned_technician.name if jobcard.assigned_technician else 'Unassigned'}
Priority: {jobcard.priority.value.upper()}
Due Date: {jobcard.due_date or 'Not set'}

Description:
{jobcard.description or 'No description'}

---
Job Card System
"""
    return subject, body


def generate_assignment_email(jobcard):
    tech = jobcard.assigned_technician
    subject = f"New Job Assigned: {jobcard.job_number} - {jobcard.title}"
    body = f"""Hello {tech.name if tech else 'Technician'},

A new job has been assigned to you.

Job Card: {jobcard.job_number}
Title: {jobcard.title}
Priority: {jobcard.priority.value.upper()}
Customer: {jobcard.customer.name if jobcard.customer else 'N/A'}
Site: {jobcard.site_address or 'N/A'}
Contact: {jobcard.site_contact or jobcard.customer.contact_person if jobcard.customer else 'N/A'}
Phone: {jobcard.site_phone or jobcard.customer.phone if jobcard.customer else 'N/A'}
Due Date: {jobcard.due_date or 'Not set'}

Description:
{jobcard.description or 'No description'}

Please log in to the system to view full details and update progress.

---
Job Card System
"""
    return subject, body


def generate_completion_email(jobcard):
    subject = f"Job Card {jobcard.job_number} Completed - {jobcard.title}"
    body = f"""Job Card {jobcard.job_number} has been marked as completed.

Title: {jobcard.title}
Customer: {jobcard.customer.name if jobcard.customer else 'N/A'}
Technician: {jobcard.assigned_technician.name if jobcard.assigned_technician else 'N/A'}
Completed: {jobcard.completed_date or 'N/A'}

Resolution Notes:
{jobcard.resolution_notes or 'No resolution notes'}

Total Hours: {jobcard.actual_hours}
Total Cost: R{jobcard.total_cost:,.2f}

---
Job Card System
"""
    return subject, body
