"""
Seed the database with sample data for development/testing.
Run: python seed_data.py
"""
from datetime import datetime, date, timedelta
import random
from database import init_db, db_session
from models import (
    Customer, Technician, JobCard, JobCardStatus, JobCardTask, TaskStatus,
    Priority, PartUsed, TimeEntry, Comment, StatusHistory, Setting, User
)


def seed():
    init_db()

    # Admin user for local development (login: admin / admin123)
    if db_session.query(User).count() == 0:
        admin = User(username="admin", full_name="System Administrator", role="admin", is_active=True)
        admin.set_password("admin123")
        db_session.add(admin)
        print("Created local admin user: admin / admin123")
    db_session.commit()

    # Settings
    settings = {
        "company_name": "JobCard Pro",
        "company_address": "123 Business Central, Sandton, Johannesburg",
        "company_phone": "+27 11 555 0100",
        "company_email": "info@jobcardpro.co.za",
        "next_job_number": "1008",
        "default_hourly_rate": "350",
        "whatsapp_enabled": "false",
        "whatsapp_provider": "log_only",
    }
    for key, value in settings.items():
        s = db_session.query(Setting).filter(Setting.key == key).first()
        if not s:
            db_session.add(Setting(key=key, value=value))
    db_session.commit()

    # Customers
    customers_data = [
        ("John Smith", "Smith Electronics", "john@smith.co.za", "+27 11 123 4567", "Johannesburg"),
        ("Sarah van der Merwe", "van der Merwe Security", "sarah@vdmsecurity.co.za", "+27 21 987 6543", "Cape Town"),
        ("Thabo Nkosi", "Nkosi Tech Solutions", "thabo@nkositech.co.za", "+27 31 555 7890", "Durban"),
        ("Lerato Molefe", "Molefe Holdings", "lerato@molefe.co.za", "+27 12 345 6789", "Pretoria"),
        ("David Botha", "Botha Alarms", "david@bothaalarms.co.za", "+27 41 111 2222", "Port Elizabeth"),
    ]
    for name, company, email, phone, city in customers_data:
        if not db_session.query(Customer).filter(Customer.email == email).first():
            db_session.add(Customer(
                name=name, company=company, email=email, phone=phone, city=city,
                contact_person=name, country="South Africa", is_active=True
            ))
    db_session.commit()

    # Technicians
    techs_data = [
        ("T001", "Mike Johnson", "mike.j@example.com", "+27 82 555 0101", "+27 82 555 0101", "Senior Technician", "CCTV, Access Control, Networking", 5, 450),
        ("T002", "Pieter Nel", "pieter.n@example.com", "+27 82 555 0102", "+27 82 555 0102", "Technician", "CCTV, Alarms", 4, 350),
        ("T003", "Sipho Zulu", "sipho.z@example.com", "+27 82 555 0103", "", "Junior Technician", "Cabling, Installations", 3, 250),
        ("T004", "Daniel Kruger", "daniel.k@example.com", "+27 82 555 0104", "+27 82 555 0104", "Senior Technician", "Access Control, Fire Systems, Networking", 5, 500),
    ]
    for code, name, email, phone, whatsapp, role, specialties, max_jobs, rate in techs_data:
        if not db_session.query(Technician).filter(Technician.employee_code == code).first():
            db_session.add(Technician(
                employee_code=code, name=name, email=email, phone=phone, whatsapp=whatsapp,
                role=role, specialties=specialties, max_jobcards=max_jobs, hourly_rate=rate, is_active=True
            ))
    db_session.commit()

    customers = db_session.query(Customer).all()
    techs = db_session.query(Technician).all()

    # Sample Job Cards
    jobs_data = [
        ("JC-1001", 0, 0, "Install 4MP Dome Camera at Main Entrance", "Replace existing analog camera with new Hikvision 4MP AcuSense dome. Run new CAT6 cable. Configure NVR.", "123 Main Rd, Sandton", Priority.medium, 4, 0),
        ("JC-1002", 1, 1, "Repair Access Control Gate at Warehouse", "Warehouse sliding gate motor not responding to remote or card reader. Check control board and power supply.", "15 Industrial Rd, Cape Town", Priority.high, 3, 0),
        ("JC-1003", 2, 2, "Annual Fire System Inspection", "Conduct annual inspection of fire alarm panel, smoke detectors, and emergency lighting at head office.", "45 Albert St, Durban", Priority.medium, 8, 0),
        ("JC-1004", 3, 0, "Emergency: Server Room AC Failure", "Server room temperature rising due to AC failure. Critical — risk of equipment damage. Install temporary cooling and repair AC.", "78 Church St, Pretoria", Priority.critical, 2, 0),
        ("JC-1005", 4, 3, "Upgrade Security System for Branch Office", "Install new DVR, 8 cameras, and access control at new branch office. Full system commissioning.", "22 Beach Rd, Port Elizabeth", Priority.low, 16, 0),
        ("JC-1006", 0, 1, "Network Switch Replacement", "Replace faulty PoE switch in comms room. Re-terminate cables and test all ports.", "123 Main Rd, Sandton", Priority.medium, 3, 0),
        ("JC-1007", 1, 1, "Install Electric Fence Energizer", "Old energizer failed. Replace with new 8J energizer. Test fence continuity and grounding.", "55 Farm Rd, Stellenbosch", Priority.high, 5, 0),
    ]

    statuses = [
        JobCardStatus.open, JobCardStatus.assigned, JobCardStatus.in_progress,
        JobCardStatus.on_hold, JobCardStatus.completed, JobCardStatus.completed, JobCardStatus.closed
    ]

    for i, (jnum, cidx, tidx, title, desc, site, pri, hours, _) in enumerate(jobs_data):
        cust = customers[cidx]
        tech = techs[tidx] if tidx < len(techs) else None
        status = statuses[i]

        jc = JobCard(
            job_number=jnum,
            customer_id=cust.id,
            technician_id=tech.id if tech else None,
            status=status,
            priority=pri,
            title=title,
            description=desc,
            site_address=site,
            site_contact=cust.contact_person,
            site_phone=cust.phone,
            requested_date=date.today() - timedelta(days=random.randint(1, 30)),
            scheduled_date=date.today() + timedelta(days=random.randint(-5, 10)),
            due_date=date.today() + timedelta(days=random.randint(-2, 14)),
            estimated_hours=hours,
            created_by="System",
        )
        if status == JobCardStatus.completed or status == JobCardStatus.closed:
            jc.completed_date = date.today() - timedelta(days=random.randint(1, 5))
            jc.actual_hours = hours + round(random.uniform(-1, 2), 1)
            jc.total_parts_cost = round(random.uniform(500, 5000), 2)
            jc.total_labour_cost = jc.actual_hours * 350
            jc.total_cost = jc.total_parts_cost + jc.total_labour_cost
            jc.amount_charged = round(jc.total_cost * 1.25, 2)
            if status == JobCardStatus.closed:
                jc.signed_off = True
                jc.signed_off_by = "Client"
                jc.signed_off_at = datetime.utcnow() - timedelta(days=random.randint(1, 3))
                jc.resolution_notes = "Job completed successfully. All systems tested and operational."

        db_session.add(jc)
        db_session.flush()

        # History
        db_session.add(StatusHistory(jobcard_id=jc.id, to_status=JobCardStatus.open.value, changed_by="System", notes="Job created"))
        if tech:
            db_session.add(StatusHistory(jobcard_id=jc.id, to_status=JobCardStatus.assigned.value, changed_by="Admin", notes=f"Assigned to {tech.name}"))
        if status in [JobCardStatus.in_progress, JobCardStatus.completed, JobCardStatus.closed]:
            db_session.add(StatusHistory(jobcard_id=jc.id, to_status=JobCardStatus.in_progress.value, changed_by=tech.name if tech else "System", notes="Work started"))
        if status in [JobCardStatus.completed, JobCardStatus.closed]:
            db_session.add(StatusHistory(jobcard_id=jc.id, to_status=JobCardStatus.completed.value, changed_by=tech.name if tech else "System", notes="Work completed"))

        # Tasks
        tasks_data = [
            "Site assessment",
            "Gather materials and tools",
            "Perform installation/repair",
            "Test all systems",
            "Clean up work area",
            "Document completion",
        ]
        for j, task_desc in enumerate(tasks_data):
            task_status = TaskStatus.completed if status in [JobCardStatus.completed, JobCardStatus.closed] and j < 4 else TaskStatus.pending
            if status == JobCardStatus.in_progress and j < 2:
                task_status = TaskStatus.completed
            db_session.add(JobCardTask(
                jobcard_id=jc.id,
                description=task_desc,
                status=task_status,
                sort_order=j,
                estimated_minutes=random.choice([15, 30, 45, 60, 90]),
                actual_minutes=random.choice([15, 30, 45, 60, 90]) if task_status == TaskStatus.completed else 0,
            ))

        # Parts for some jobs
        if random.random() > 0.3:
            parts_pool = [
                ("Hikvision DS-2CD2347G2-LSU", "HIK-4MP-DOME", 1, 1850),
                ("CAT6 Cable (per meter)", "CAT6-M", 15, 12),
                ("PoE Injector", "POE-INJ", 1, 350),
                ("Wall Mount Bracket", "BRK-WM", 1, 85),
                ("RJ45 Connector", "RJ45-C5E", 2, 8),
                ("Power Supply 12V 2A", "PSU-12V2A", 1, 120),
            ]
            for _ in range(random.randint(1, 3)):
                part = random.choice(parts_pool)
                qty = random.randint(1, 5)
                db_session.add(PartUsed(
                    jobcard_id=jc.id,
                    part_name=part[0],
                    part_sku=part[1],
                    quantity=qty,
                    unit_cost=part[3],
                    total_cost=qty * part[3],
                ))

        # Time entries for in-progress or completed
        if status in [JobCardStatus.in_progress, JobCardStatus.completed, JobCardStatus.closed]:
            start = datetime.utcnow() - timedelta(days=random.randint(1, 7), hours=random.randint(1, 8))
            end = start + timedelta(hours=hours)
            db_session.add(TimeEntry(
                jobcard_id=jc.id,
                technician_name=tech.name if tech else "Technician",
                start_time=start,
                end_time=end,
                hours=hours,
                hourly_rate=350,
                total_cost=hours * 350,
            ))

        # Comments
        comments = [
            ("Technician", "Arrived on site. Initial assessment complete."),
            ("Admin", "Parts ordered. Awaiting delivery."),
            ("Technician", "Installation in progress. Going well."),
            ("Technician", "Job completed. Customer satisfied."),
            ("Customer", "Thank you for the great service!"),
        ]
        for k in range(random.randint(0, 2)):
            author, body = comments[random.randint(0, len(comments) - 1)]
            db_session.add(Comment(
                jobcard_id=jc.id,
                author=author,
                body=body,
                is_internal=author == "Admin",
            ))

    db_session.commit()
    print("Seed data inserted successfully!")
    print(f"  - {len(customers_data)} customers")
    print(f"  - {len(techs_data)} technicians")
    print(f"  - {len(jobs_data)} job cards")


if __name__ == "__main__":
    seed()
