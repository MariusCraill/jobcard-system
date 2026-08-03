from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from database import db_session
from models import User

auth_bp = Blueprint("auth", __name__)


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        if current_user.role != "admin":
            flash("You do not have permission to view that page", "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return wrapper


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db_session.query(User).filter(User.username == username).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db_session.commit()
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))
        flash("Invalid username or password", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect", "danger")
        elif len(new_password) < 6:
            flash("New password must be at least 6 characters", "danger")
        elif new_password != confirm:
            flash("New passwords do not match", "danger")
        else:
            current_user.set_password(new_password)
            db_session.commit()
            flash("Password changed successfully", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("auth/change_password.html")
