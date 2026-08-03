# JobCard System — Production Deployment Guide

Your Flask app is ready to deploy. It now has:

- **User accounts** (login, logout, change password) with roles:
  - `admin` — full access (settings, users, everything)
  - `technician` — jobcards, customers, technicians, reports
  - `user` — jobcards, customers only
- **SQLite** for local dev, **PostgreSQL** support for cloud hosting (`DATABASE_URL`)
- An auto-created first admin (from `ADMIN_USERNAME` / `ADMIN_PASSWORD` env vars)

---

## Quick local run

```powershell
cd "C:\Users\MariusCrail\Documents\Default Project\jobcard_system"
python seed_data.py          # optional: sample data + local admin (admin/admin123)
python app.py                # http://localhost:5000
```

If you already have a database with users, your local admin is `admin / admin123`
(created by `seed_data.py`).

---

## Option A — Render.com (recommended, free)

Render's free tier gives you a web service (750 hrs/month, sleeps after 15 min idle)
plus a free PostgreSQL database. Git-based deploys with auto HTTPS.

### 1. Create a Git repo and push to GitHub

```powershell
cd "C:\Users\MariusCrail\Documents\Default Project\jobcard_system"
git init
git add .
git commit -m "Initial production setup"
```

Push to a GitHub repo (create one on github.com first, then):

```powershell
git remote add origin https://github.com/YOUR_USERNAME/jobcard-system.git
git branch -M main
git push -u origin main
```

### 2. Create the database on Render

1. Go to https://dashboard.render.com/new/database → PostgreSQL.
2. Choose **Free** plan, name it `jobcard-db`, create it.
3. Copy its **Internal Database URL** (or External).

### 3. Create the web service

1. https://dashboard.render.com/new → **Web Service** → connect your GitHub repo.
2. Settings:
   - **Name:** `jobcard-system`
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 60 wsgi:app`
   - **Plan:** Free
3. **Environment variables** (Advanced → Add Environment Variable):

   | Key | Value |
   |---|---|
   | `SECRET_KEY` | a long random string (use "Generate" button) |
   | `DATABASE_URL` | your PostgreSQL connection string from step 2 |
   | `FLASK_DEBUG` | `false` |
   | `ADMIN_USERNAME` | `admin` |
   | `ADMIN_PASSWORD` | your chosen password |
   | `UPLOAD_FOLDER` | `/var/data/uploads` (or add a Persistent Disk) |

4. Create the service. On first deploy the app auto-creates the database tables and
   the admin user from `ADMIN_USERNAME`/`ADMIN_PASSWORD`.
5. Open the `https://jobcard-system.onrender.com` URL and log in.

> **Free tier notes:** the service sleeps after ~15 min idle and takes ~30–60 s to
> wake up on the first request. The Render-managed free database expires after 30 days —
> see below to use Neon instead for a truly persistent free Postgres.

### (Optional) Use Neon for a permanent free PostgreSQL

1. Create a free account at https://neon.tech and create a project (database `jobcards`).
2. Copy the connection string (looks like `postgresql://user:pass@host/dbname`).
3. Set it as `DATABASE_URL` on Render instead of the Render-managed DB.
   (Your app already converts `postgres://` → `postgresql://` automatically.)

---

## Option B — PythonAnywhere (free, keeps SQLite)

PythonAnywhere free tier keeps your SQLite database file permanently — no database
changes needed.

1. Create a free account at https://www.pythonanywhere.com
2. Open the **Bash** console and upload your code:
   ```bash
   git clone https://github.com/YOUR_USERNAME/jobcard-system.git
   cd jobcard-system
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set your admin credentials:
   ```bash
   export ADMIN_USERNAME=admin
   export ADMIN_PASSWORD=yourpassword
   python seed_data.py   # first-time only
   ```
4. Go to **Web** tab → **Add a new web app** → manual config → Python 3.12.
5. In the **WSGI configuration file**, replace the contents with:
   ```python
   import os, sys
   path = '/home/YOUR_USERNAME/jobcard-system'
   if path not in sys.path:
       sys.path.append(path)
   from wsgi import app as application
   ```
6. In the **Virtualenv** section set `/home/YOUR_USERNAME/jobcard-system/venv`.
7. Reload the web app. Your site is at `https://YOUR_USERNAME.pythonanywhere.com`.

---

## API access (for external integrations, e.g. WhatsApp webhook)

All `/api/*` endpoints require either:
- a logged-in session, **or**
- a **`X-API-Key`** header (or `?api_key=` query param) matching the API key you set in
  Admin → Settings → **API Key (for /api endpoints)**.

Example:

```bash
curl -H "X-API-Key: your-api-key" https://jobcard-system.onrender.com/api/jobcards
```

---

## Production checklist

- [ ] `SECRET_KEY` is a long random value (not the default)
- [ ] `ADMIN_PASSWORD` is set and strong
- [ ] Created additional users with least-privilege roles (Admin → Users)
- [ ] Set an **API Key** if external systems will call the API
- [ ] For SMTP email, fill in SMTP settings under Admin → Settings (or use "client" mode)
- [ ] Update company name/address/phone under Admin → Settings
