from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import db_session, get_or_404
from models import Customer, JobCard

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/")
def list_customers():
    search = request.args.get("search", "")
    query = db_session.query(Customer).filter(Customer.is_active == True)
    if search:
        query = query.filter(
            Customer.name.ilike(f"%{search}%") |
            Customer.company.ilike(f"%{search}%") |
            Customer.email.ilike(f"%{search}%") |
            Customer.phone.ilike(f"%{search}%")
        )
    customers = query.order_by(Customer.name).all()
    return render_template("customers/list.html", **locals())


@customers_bp.route("/new", methods=["GET", "POST"])
def new_customer():
    if request.method == "POST":
        customer = Customer(
            name=request.form["name"],
            company=request.form.get("company", ""),
            email=request.form.get("email", ""),
            phone=request.form.get("phone", ""),
            alt_phone=request.form.get("alt_phone", ""),
            address=request.form.get("address", ""),
            city=request.form.get("city", ""),
            province=request.form.get("province", ""),
            postal_code=request.form.get("postal_code", ""),
            country=request.form.get("country", "South Africa"),
            contact_person=request.form.get("contact_person", ""),
            notes=request.form.get("notes", ""),
        )
        db_session.add(customer)
        db_session.commit()
        flash("Customer created successfully", "success")
        return redirect(url_for("customers.list_customers"))
    return render_template("customers/form.html", customer=None)


@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
def edit_customer(customer_id):
    customer = get_or_404(Customer, customer_id)
    if request.method == "POST":
        customer.name = request.form["name"]
        customer.company = request.form.get("company", "")
        customer.email = request.form.get("email", "")
        customer.phone = request.form.get("phone", "")
        customer.alt_phone = request.form.get("alt_phone", "")
        customer.address = request.form.get("address", "")
        customer.city = request.form.get("city", "")
        customer.province = request.form.get("province", "")
        customer.postal_code = request.form.get("postal_code", "")
        customer.country = request.form.get("country", "South Africa")
        customer.contact_person = request.form.get("contact_person", "")
        customer.notes = request.form.get("notes", "")
        customer.updated_at = datetime.utcnow()
        db_session.commit()
        flash("Customer updated successfully", "success")
        return redirect(url_for("customers.list_customers"))
    return render_template("customers/form.html", customer=customer)


@customers_bp.route("/<int:customer_id>/view")
def view_customer(customer_id):
    customer = get_or_404(Customer, customer_id)
    jobcards = db_session.query(JobCard).filter(JobCard.customer_id == customer_id).order_by(JobCard.created_at.desc()).all()
    return render_template("customers/view.html", **locals())


@customers_bp.route("/<int:customer_id>/delete", methods=["POST"])
def delete_customer(customer_id):
    customer = get_or_404(Customer, customer_id)
    jobcard_count = db_session.query(JobCard).filter(JobCard.customer_id == customer_id).count()
    if jobcard_count > 0:
        customer.is_active = False
        flash("Customer has job cards — deactivated instead", "warning")
    else:
        db_session.delete(customer)
        flash("Customer deleted", "success")
    db_session.commit()
    return redirect(url_for("customers.list_customers"))
