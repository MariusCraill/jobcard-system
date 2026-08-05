import os
import secrets
from flask import Flask, request, redirect, url_for, flash
from flask_login import LoginManager, current_user
from database import init_db, db_session
from models import User

login_manager = LoginManager()

# Which blueprint prefixes each role may access (admin = everything).
ROLE_ALLOWED_PREFIXES = {
    "technician": ("dashboard.", "jobcards.", "customers.", "technicians.", "reports.", "tickets."),
    # End users (self-registered) only see the ticket portal + their own tickets.
    "user": ("dashboard.", "tickets."),
}


def ensure_admin():
    """Create the first admin user from env vars (or a generated password)."""
    if db_session.query(User).count() > 0:
        return
    username = os.environ.get("ADMIN_USERNAME", "admin")
    if os.environ.get("ADMIN_PASSWORD"):
        password = os.environ["ADMIN_PASSWORD"]
    elif os.environ.get("DATABASE_URL"):
        password = secrets.token_urlsafe(12)
        print(f"[init] Generated admin password: {password}  (set ADMIN_PASSWORD to choose your own)")
    else:
        password = "admin123"
        print("[init] Local dev: created admin user 'admin' with password 'admin123' (run seed_data.py for sample data)")
    user = User(username=username, full_name="Administrator", role="admin", is_active=True)
    user.set_password(password)
    db_session.add(user)
    db_session.commit()
    print(f"[init] Created initial admin user: '{username}'")


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "")
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db_session.get(User, int(user_id))

    @app.before_request
    def require_login():
        if request.endpoint is None or request.endpoint == "static":
            return
        if request.endpoint.startswith("auth."):
            return
        if request.endpoint.startswith("api."):
            return  # the api blueprint handles its own auth (session or API key)
        if request.endpoint in ("tickets.new_ticket", "tickets.ticket_lookup"):
            return  # client-facing ticket pages
        if request.endpoint == "dashboard.index" and not current_user.is_authenticated:
            return  # the landing page renders its own content for visitors
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        allowed = ROLE_ALLOWED_PREFIXES.get(current_user.role)
        if allowed and not request.endpoint.startswith(allowed):
            flash("You do not have permission to view that page", "danger")
            return redirect(url_for("dashboard.index"))

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    @app.context_processor
    def inject_settings():
        from blueprints.admin import get_all_settings
        try:
            return {"app_settings": get_all_settings()}
        except Exception:
            return {"app_settings": {"company_name": "JobCard System", "logo_filename": ""}}

    from blueprints.dashboard import dashboard_bp
    from blueprints.jobcards import jobcards_bp
    from blueprints.customers import customers_bp
    from blueprints.technicians import technicians_bp
    from blueprints.reports import reports_bp
    from blueprints.admin import admin_bp
    from blueprints.api import api_bp
    from blueprints.auth import auth_bp
    from blueprints.tickets import tickets_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(jobcards_bp, url_prefix="/jobcards")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(technicians_bp, url_prefix="/technicians")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(tickets_bp, url_prefix="/tickets")

    init_db()
    ensure_admin()

    return app


if __name__ == "__main__":
    app = create_app()
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
