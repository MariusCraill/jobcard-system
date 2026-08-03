from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from database import db_session
from models import Setting, EmailLog, WhatsAppLog, User
from blueprints.auth import admin_required

admin_bp = Blueprint("admin", __name__)


SETTING_KEYS = [
    ("company_name", "Company Name", "JobCard System"),
    ("company_address", "Company Address", ""),
    ("company_phone", "Company Phone", ""),
    ("company_email", "Company Email", ""),
    ("email_method", "Email Method", "smtp"),
    ("smtp_from_email", "SMTP From Email", ""),
    ("smtp_host", "SMTP Host", ""),
    ("smtp_port", "SMTP Port", "587"),
    ("smtp_user", "SMTP Username", ""),
    ("smtp_pass", "SMTP Password", ""),
    ("whatsapp_enabled", "WhatsApp Enabled", "false"),
    ("whatsapp_provider", "WhatsApp Provider", "log_only"),
    ("whatsapp_action", "WhatsApp Action", "api"),
    ("whatsapp_api_key", "WhatsApp API Key", ""),
    ("whatsapp_account_id", "WhatsApp Account ID", ""),
    ("whatsapp_from_number", "WhatsApp From Number", ""),
    ("api_key", "API Key (for /api endpoints)", ""),
    ("next_job_number", "Next Job Number", "1001"),
    ("default_hourly_rate", "Default Hourly Rate", "350"),
    ("invoice_prefix", "Invoice Prefix", "INV"),
]


def get_all_settings():
    result = {}
    for key, _, default in SETTING_KEYS:
        s = db_session.query(Setting).filter(Setting.key == key).first()
        result[key] = s.value if s and s.value else default
    return result


def get_setting(key, default=""):
    s = db_session.query(Setting).filter(Setting.key == key).first()
    return s.value if s and s.value else default


@admin_bp.route("/", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        for key, _, _ in SETTING_KEYS:
            value = request.form.get(key, "")
            s = db_session.query(Setting).filter(Setting.key == key).first()
            if s:
                s.value = value
            else:
                s = Setting(key=key, value=value)
                db_session.add(s)
        db_session.commit()
        flash("Settings saved successfully", "success")
        return redirect(url_for("admin.settings"))

    current = get_all_settings()
    return render_template("admin/settings.html", **locals())


@admin_bp.route("/email-logs")
@admin_required
def email_logs():
    logs = db_session.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(100).all()
    return render_template("admin/email_logs.html", logs=logs)


@admin_bp.route("/whatsapp-logs")
@admin_required
def whatsapp_logs():
    logs = db_session.query(WhatsAppLog).order_by(WhatsAppLog.created_at.desc()).limit(100).all()
    return render_template("admin/whatsapp_logs.html", logs=logs)


@admin_bp.route("/users")
@admin_required
def users():
    users = db_session.query(User).order_by(User.username).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def user_new():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username:
            flash("Username is required", "danger")
        elif db_session.query(User).filter(User.username == username).first():
            flash("Username already exists", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters", "danger")
        else:
            user = User(
                username=username,
                full_name=request.form.get("full_name", ""),
                role=request.form.get("role", "user"),
                is_active=True,
            )
            user.set_password(password)
            db_session.add(user)
            db_session.commit()
            flash(f"User '{username}' created", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", user=None)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(user_id):
    user = db_session.get(User, user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("admin.users"))

    if request.method == "POST":
        user.full_name = request.form.get("full_name", "")
        user.role = request.form.get("role", "user")
        password = request.form.get("password", "")
        if password:
            if len(password) < 6:
                flash("Password must be at least 6 characters", "danger")
                return render_template("admin/user_form.html", user=user)
            user.set_password(password)
        db_session.commit()
        flash("User updated", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", user=user)


@admin_bp.route("/users/<int:user_id>/toggle")
@admin_required
def user_toggle(user_id):
    user = db_session.get(User, user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash("You cannot disable your own account", "warning")
        return redirect(url_for("admin.users"))
    user.is_active = not user.is_active
    db_session.commit()
    flash(f"User '{user.username}' {'enabled' if user.is_active else 'disabled'}", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def user_delete(user_id):
    user = db_session.get(User, user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash("You cannot delete your own account", "warning")
        return redirect(url_for("admin.users"))
    admin_count = db_session.query(User).filter(User.role == "admin", User.is_active == True).count()
    if user.role == "admin" and admin_count <= 1:
        flash("Cannot delete the last active admin", "danger")
        return redirect(url_for("admin.users"))
    db_session.delete(user)
    db_session.commit()
    flash(f"User '{user.username}' deleted", "success")
    return redirect(url_for("admin.users"))
