# SahayID Architecture Overview

SahayID is a privacy-centric digital medical identity and clinical access management platform. It bridges rapid emergency medical access with strict, patient-mediated clinical authorization.

---

## 1. System Topology & Role Hierarchy

SahayID enforces a three-tier role-based access control (RBAC) model:

```
                  ┌─────────────────────────────────────┐
                  │       System Administrator          │
                  │   (/admin/login & /admin portal)    │
                  └──────────────────┬──────────────────┘
                                     │
                    Oversees & Verifies Credentials
                                     │
                                     ▼
┌─────────────────────────┐                   ┌─────────────────────────┐
│     Patient / User      │ ◄─── OTP Consent ─┤   Verified Physician    │
│  - Medical Profile      │       Exchange    │   - Clinical Search     │
│  - Emergency Contacts   │                   │   - QR Badge Scanner    │
│  - Zero-Knowledge QR    │                   │   - Audit Trail Logging │
│  - Active OTP Generator │                   │   - Break-Glass Triage  │
└─────────────────────────┘                   └─────────────────────────┘
             ▲                                             ▲
             │                                             │
             └──────────── Emergency Break-Glass ──────────┘
```

### Roles & Responsibilities

1. **Patient / Individual (`role: 'patient'`):**
   - Unique identifier formatted as `MED-XXXXXXXX` (Base32 Crockford charset, high entropy).
   - Manages personal vitals, blood type, drug allergies, medications, and surgical history.
   - Configures prioritized emergency next-of-kin contacts.
   - Generates dynamic 6-digit numeric OTPs with 5-minute cryptographic validity for clinician access requests.
   - Monitors an unalterable access history audit log recording every clinical and emergency inspection.

2. **Physician / Clinician (`role: 'doctor'`):**
   - Unique identifier formatted as `DOC-XXXXXXXX`.
   - Requires verification by an administrator (`verification_status = 'verified'`).
   - Searches patients via SahayID number or integrated QR scanner.
   - Initiates OTP-based clinical consent requests before accessing full medical profiles.
   - Possesses emergency triage access rights governed by audit penalties and mandatory justification tracking.

3. **System Administrator (`role: 'admin'`):**
   - Accessible strictly via unlisted route (`/admin/login`).
   - Oversees pending medical practitioner registrations.
   - Reviews professional license credentials, hospital affiliations, and contact details.
   - Approves (`status='verified'`) or rejects (`status='rejected'` with mandatory reason) practitioner accounts.
   - Audits global access trails without exposing sensitive clinical records.

---

## 2. Zero-Knowledge QR Code Architecture

Traditional medical cards print sensitive health details directly onto barcodes or QR codes, presenting severe privacy risks if lost, stolen, or photographed.

SahayID implements **Zero-Knowledge QR Routing**:
- **QR Payload:** Contains strictly an HTTPS routing URL (e.g. `https://sahayid.app/emergency/MED-XXXXXXXX`).
- **Data Exclusion:** No name, blood group, allergies, conditions, or contact numbers are embedded in the QR image bytes.
- **Access Gating:** Scanning the QR directs the responder to the emergency gateway verification page where legal acknowledgments and identification are required before record retrieval.

---

## 3. Database Schema Overview

SahayID utilizes an abstracted database layer compatible with both local SQLite and production PostgreSQL (Supabase).

```
┌─────────────────┐       ┌──────────────────────┐
│      users      │───1:1─┤   medical_profiles   │
│-----------------│       │----------------------│
│ id (PK)         │       │ id (PK)              │
│ medi_id (UNIQUE)│       │ user_id (FK -> users)│
│ full_name       │       │ blood_group          │
│ email (UNIQUE)  │       │ allergies            │
│ phone           │       │ current_medications  │
│ password_hash   │       │ medical_conditions   │
│ photo_url       │       │ previous_surgeries   │
│ created_at      │       │ updated_at           │
└────────┬────────┘       └──────────────────────┘
         │
         │ 1:N
         ├──────────────────────┐
         │                      │
         ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│emergency_contacts│   │   access_logs    │
│------------------│   │------------------│
│ id (PK)          │   │ id (PK)          │
│ user_id (FK)     │   │ user_id (FK)     │
│ name             │   │ doctor_id (FK)   │
│ relationship     │   │ actor_type       │
│ phone            │   │ actor_name       │
│ created_at       │   │ organization     │
└──────────────────┘   │ access_type      │
                       │ reason           │
                       │ ip_address       │
                       │ accessed_at      │
                       └──────────────────┘

┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│     doctors      │   │ access_requests  │   │  emergency_access│
│------------------│   │------------------│   │------------------│
│ id (PK)          │   │ id (PK)          │   │ id (PK)          │
│ doctor_id(UNIQUE)│   │ patient_id (FK)  │   │ user_id (FK)     │
│ full_name        │   │ doctor_id (FK)   │   │ token_hash       │
│ email (UNIQUE)   │   │ request_token    │   │ responder_name   │
│ specialization   │   │ otp_hash         │   │ organization     │
│ registration_no  │   │ status           │   │ reason           │
│ verification_stat│   │ expires_at       │   │ expires_at       │
│ photo_url        │   │ authorized_until │   │ ip_address       │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```
