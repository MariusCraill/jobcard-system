"""
WhatsApp Integration Module
Provides functions for sending WhatsApp notifications about job card status changes,
assignments, and completions.

To enable, set the following in Admin Settings:
- whatsapp_enabled: "true"
- whatsapp_provider: "twilio" | "wati" | "whatsapp_business_api"
- whatsapp_api_key: <your API key>
- whatsapp_from_number: <sender WhatsApp number>
- whatsapp_account_id: <account ID if required>

Each provider has its own implementation. This module provides a unified interface
and falls back to logging if integration is not configured.
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime
from database import db_session
from models import WhatsAppLog, Setting


def _get_setting(key, default=""):
    s = db_session.query(Setting).filter(Setting.key == key).first()
    return s.value if s and s.value else default


def build_wa_web_link(phone, message):
    """Generate a https://wa.me/ link for WhatsApp Web."""
    import urllib.parse
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    return f"https://wa.me/{phone_clean}?text={urllib.parse.quote(message)}"


def build_wa_app_link(phone, message):
    """Generate a whatsapp:// link that opens the WhatsApp desktop/mobile app."""
    import urllib.parse
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    return f"whatsapp://send?phone={phone_clean}&text={urllib.parse.quote(message)}"


def send_whatsapp_message(to_number, message, jobcard_id=None, message_type="notification"):
    """Send a WhatsApp message via the configured method (api/web/app)."""
    import urllib.parse

    enabled = _get_setting("whatsapp_enabled", "false")
    if enabled.lower() != "true":
        log = WhatsAppLog(
            jobcard_id=jobcard_id, recipient_number=to_number,
            message_preview=message[:200], message_type=message_type,
            status="disabled"
        )
        db_session.add(log)
        db_session.commit()
        return False, "WhatsApp integration not enabled"

    action = _get_setting("whatsapp_action", "api")

    # Web mode — return wa.me link
    if action == "web":
        wa_link = build_wa_web_link(to_number, message)
        log = WhatsAppLog(
            jobcard_id=jobcard_id, recipient_number=to_number,
            message_preview=message[:200], message_type=message_type,
            status="web_link"
        )
        db_session.add(log)
        db_session.commit()
        return True, wa_link

    # App mode — return whatsapp:// link
    if action == "app":
        wa_link = build_wa_app_link(to_number, message)
        log = WhatsAppLog(
            jobcard_id=jobcard_id, recipient_number=to_number,
            message_preview=message[:200], message_type=message_type,
            status="app_link"
        )
        db_session.add(log)
        db_session.commit()
        return True, wa_link

    # API mode — send via configured provider
    provider = _get_setting("whatsapp_provider", "log_only")
    api_key = _get_setting("whatsapp_api_key", "")
    from_number = _get_setting("whatsapp_from_number", "")

    log = WhatsAppLog(
        jobcard_id=jobcard_id, recipient_number=to_number,
        message_preview=message[:200], message_type=message_type,
        status="pending"
    )
    db_session.add(log)
    db_session.flush()
    log_id = log.id

    try:
        if provider == "log_only" or not api_key:
            log.status = "logged"
            log.sent_at = datetime.utcnow()
            db_session.commit()
            return True, "WhatsApp message logged (no provider configured)"

        if provider == "twilio":
            return _send_twilio_whatsapp(to_number, message, api_key, from_number, log_id)
        elif provider == "wati":
            return _send_wati_whatsapp(to_number, message, api_key, from_number, log_id)
        elif provider == "whatsapp_business_api":
            return _send_whatsapp_business_api(to_number, message, api_key, from_number, log_id)
        else:
            log.status = "failed"
            log.error_message = f"Unknown provider: {provider}"
            db_session.commit()
            return False, f"Unknown WhatsApp provider: {provider}"
    except Exception as e:
        log_entry = db_session.query(WhatsAppLog).get(log_id)
        if log_entry:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            db_session.commit()
        return False, str(e)


def _send_twilio_whatsapp(to_number, message, api_key, from_number, log_id):
    """Send via Twilio WhatsApp API."""
    account_sid = _get_setting("whatsapp_account_id", "")
    if not account_sid:
        raise ValueError("Twilio Account SID not configured")

    to_number = to_number.replace("+", "").replace(" ", "")
    from_number = from_number.replace("+", "").replace(" ", "")

    data = urllib.parse.urlencode({
        "From": f"whatsapp:+{from_number}",
        "To": f"whatsapp:+{to_number}",
        "Body": message
    }).encode()

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    req = urllib.request.Request(url, data=data)

    import base64
    credentials = base64.b64encode(f"{account_sid}:{api_key}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode())

    log_entry = db_session.query(WhatsAppLog).get(log_id)
    if log_entry:
        log_entry.status = "sent"
        log_entry.external_id = result.get("sid", "")
        log_entry.sent_at = datetime.utcnow()
        db_session.commit()
    return True, "WhatsApp sent via Twilio"


def _send_wati_whatsapp(to_number, message, api_key, from_number, log_id):
    """Send via WATI API."""
    from_number = _get_setting("whatsapp_account_id", "")
    url = f"https://live.wati.io/api/v1/sendTemplateMessage?whatsappNumber={to_number}"
    payload = json.dumps({
        "template_name": "job_card_notification",
        "broadcast_name": "jobcard_system",
        "parameters": [{"name": "message", "value": message}]
    }).encode()
    req = urllib.request.Request(url, data=payload)
    req.add_header("Authorization", api_key)
    req.add_header("Content-Type", "application/json")

    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode())

    log_entry = db_session.query(WhatsAppLog).get(log_id)
    if log_entry:
        log_entry.status = "sent"
        log_entry.external_id = result.get("id", "")
        log_entry.sent_at = datetime.utcnow()
        db_session.commit()
    return True, "WhatsApp sent via WATI"


def _send_whatsapp_business_api(to_number, message, api_key, from_number, log_id):
    """Send via WhatsApp Business API (Meta)."""
    phone_number_id = _get_setting("whatsapp_account_id", "")
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message}
    }).encode()
    req = urllib.request.Request(url, data=payload)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode())

    log_entry = db_session.query(WhatsAppLog).get(log_id)
    if log_entry:
        log_entry.status = "sent"
        log_entry.external_id = result.get("messages", [{}])[0].get("id", "")
        log_entry.sent_at = datetime.utcnow()
        db_session.commit()
    return True, "WhatsApp sent via Business API"


def generate_assignment_message(jobcard):
    tech = jobcard.assigned_technician
    tech_name = tech.name if tech else "Technician"
    return (
        f"*NEW JOB ASSIGNED*\n"
        f"Job: {jobcard.job_number}\n"
        f"Title: {jobcard.title}\n"
        f"Priority: {jobcard.priority.value.upper()}\n"
        f"Customer: {jobcard.customer.name if jobcard.customer else 'N/A'}\n"
        f"Site: {jobcard.site_address or 'N/A'}\n"
        f"Due: {jobcard.due_date or 'N/A'}\n"
        f"Please check the system for details."
    )


def generate_status_message(jobcard, old_status, new_status):
    return (
        f"*JOB STATUS UPDATE*\n"
        f"Job: {jobcard.job_number}\n"
        f"Title: {jobcard.title}\n"
        f"Status: {old_status} → {new_status}\n"
        f"Customer: {jobcard.customer.name if jobcard.customer else 'N/A'}\n"
        f"Technician: {jobcard.assigned_technician.name if jobcard.assigned_technician else 'N/A'}"
    )


def generate_completion_message(jobcard):
    return (
        f"*JOB COMPLETED*\n"
        f"Job: {jobcard.job_number}\n"
        f"Title: {jobcard.title}\n"
        f"Customer: {jobcard.customer.name if jobcard.customer else 'N/A'}\n"
        f"Completed: {jobcard.completed_date or 'N/A'}\n"
        f"Hours: {jobcard.actual_hours}\n"
        f"Thank you for your business!"
    )
