# SahayID Production Deployment & Supabase Guide

This guide details how to deploy SahayID on **Vercel** with a **Supabase PostgreSQL** database backend.

---

## 1. Environment Variables Configuration

Set the following environment variables in your Vercel Project Dashboard (**Settings &rarr; Environment Variables**):

| Variable Name | Required | Example / Format | Purpose |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | **Yes** | `64-char-hex-random-string` | Flask session encryption and CSRF signing key. |
| `DATABASE_URL` | **Yes** (Prod) | `postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` | Supabase connection pooling string. |
| `ADMIN_PASSWORD` | **Yes** | `YourStrongAdminPassword2026!` | Master password for `/admin/login`. |
| `ADMIN_USERNAME` | No | `admin` | Custom admin username (defaults to `admin`). |
| `ADMIN_EMAIL` | No | `admin@sahayid.org` | Custom admin notification/login email. |
| `SAHAYID_BASE_URL` | No | `https://your-sahayid-domain.vercel.app` | Canonical origin used in QR routing URLs. |

> [!IMPORTANT]
> **Supabase Connection Pooler:** In serverless environments like Vercel, always use the Supabase **Transaction Pooler URL** (`port 6543`) with `sslmode=require` to prevent database connection exhaustion.

---

## 2. Vercel Serverless Configuration (`vercel.json`)

```json
{
  "version": 2,
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
```

---

## 3. Database Schema Migration

SahayID automatically initializes the required PostgreSQL schema (tables, foreign keys, indexes) on cold boot via [`init_db()`](file:///C:/Users/pande/.gemini/antigravity/scratch/mediid/app.py) if tables do not exist.

To manually inspect or verify schema tables in Supabase SQL Editor:
- `users`
- `medical_profiles`
- `emergency_contacts`
- `doctors`
- `admins`
- `access_requests`
- `access_logs`
- `emergency_access`

---

## 4. Local Development vs. Production

- **Local:** Run `python app.py` (defaults to local SQLite database at `database/mediid.db`).
- **Tests:** Execute all 11 test suites via `python test_admin.py`, `python test_authentication.py`, etc.
- **Production:** Deploy with `git push origin main` or `vercel --prod`.
