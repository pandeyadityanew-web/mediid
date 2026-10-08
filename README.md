# SahayID - CRITICAL MEDICAL ACCESS

<div align="center">

```
  ____        _                 ___ ____  
 / ___|  __ _| |__   __ _ _   _|_ _|  _ \ 
 \___ \ / _` | '_ \ / _` | | | || || | | |
  ___) | (_| | | | | (_| | |_| || || |_| |
 |____/ \__,_|_| |_|\__,_|\__, |___|____/ 
                          |___/           
        CRITICAL MEDICAL ACCESS
```

**Privacy-Centric Digital Medical Identity, Authorized Clinical Portal & Emergency Break-Glass Gateway**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.x](https://img.shields.io/badge/flask-3.x-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Database: SQLite / PostgreSQL](https://img.shields.io/badge/database-SQLite%203%20%2F%20PostgreSQL-lightgrey.svg)](https://www.sqlite.org/)
[![Production: Gunicorn](https://img.shields.io/badge/WSGI-Gunicorn-darkgreen.svg)](https://gunicorn.org/)

</div>

---

## 1. Executive Summary

**SahayID** (*Critical Medical Access*) is a privacy-first digital medical identity infrastructure designed for emergency healthcare triage and authorized clinical inquiry. 

In acute medical crises—such as unconscious trauma victims, cardiac emergencies, or severe anaphylaxis—first responders and hospital clinicians face a critical information vacuum. Simultaneously, public exposure of raw medical records violates basic patient privacy.

SahayID resolves this tension by providing:
1. **Zero-Knowledge Emergency QR Codes**: Scannable QR cards that encode **only** an unguessable routing gateway URL—never embedding raw personal or medical data inside the physical QR code.
2. **Dual Access Model**:
   - **Emergency Break-Glass Gateway**: Intended for first responders and paramedics without account credentials; enforces emergency acknowledgement, identity disclosure, clinical reasoning, 10-minute ephemeral tokens, and strictly throttled access to critical lifesaving data only.
   - **Normal Authorized Doctor Access**: Intended for licensed, verified medical practitioners; enforces multi-field credentials, verification status checks, explicit access confirmation, and access to full clinical records.
3. **Emergency Data Tiering**: Strict separation between critical triage data (blood group, life-threatening allergies, acute conditions, active medications, next-of-kin contacts) and full medical history (surgical history, psychiatric consultations, private physician notes).
4. **Admin Verification & Oversight Portal**: Secure administrative console (`/admin`) for evaluating medical licenses and managing physician verification status (`pending`, `verified`, `rejected`).
5. **Bilateral Audit Logging**: Immutable audit records in `access_logs` differentiating between `EMERGENCY_BREAK_GLASS`, `DOCTOR_ACCESS`, and `CONSENT_OTP_ACCESS`.
6. **Progressive Web App (PWA)**: Native install prompt support, offline asset caching, and mobile responsiveness.
7. **Production Ready & Multi-Database**: Seamless deployment on Vercel and Supabase PostgreSQL with SSL pooling.

---

## 📚 Technical Documentation Index

- 📋 **[Software Requirements Specification (SRS)](docs/SRS.md)**: Formal functional and non-functional requirements specification (IEEE 830 standard).
- 📐 **[System Design Document (SDD)](docs/DESIGN.md)**: Architectural components, sequence diagrams, STRIDE threat model, and UI design system.
- 🏛️ **[System Architecture](docs/ARCHITECTURE.md)**: Role-based access control, topology, and database entity relationships.
- 🔒 **[Security & API Specification](docs/SECURITY_AND_API.md)**: Cryptographic hashing, OTP consent engine, HTTP defensive headers, and endpoints.
- 👨‍⚕️ **[Administrator & Doctor Verification Guide](docs/ADMIN_GUIDE.md)**: Practitioner onboarding, license validation, and audit controls.
- 🚨 **[Emergency Triage & Break-Glass Protocol](docs/EMERGENCY_TRIAGE.md)**: Zero-knowledge QR mechanics, ephemeral token lifecycle, and triage data gating.
- 📱 **[Progressive Web App (PWA) Guide](docs/PWA_GUIDE.md)**: Native installation mechanics, Web Manifest, and service worker strategies.
- 🚀 **[Production Deployment Guide](docs/DEPLOYMENT.md)**: Supabase PostgreSQL setup, environment variables, and Vercel configuration.
- 💡 **[Platform FAQs & Knowledge Base](docs/FAQ.md)**: Frequently asked questions and privacy guarantees.

---

## 2. Core Problem & Engineering Solution

### The Critical Medical Vacuum
- **Unconscious or Incapacitated Patients**: Victims of road accidents, strokes, or diabetic shock cannot communicate blood types, drug allergies, or current prescriptions.
- **Lethal Blind Treatment**: Administering common drugs (e.g., Penicillin, Cephalosporins, NSAIDs) or incompatible blood transfusions without known patient history causes preventable fatalities.
- **The Public Privacy Hazard**: Traditional medical alert bracelets or naive QR code systems print sensitive clinical data in plaintext, exposing private medical histories to anyone nearby.

### The SahayID Architectural Solution
```
                                 [ PHYSICAL QR BADGE ]
                                           │
                                           │ Encodes ONLY:
                                           ▼ https://domain/emergency/MED-XXXXXXXX
                                [ EMERGENCY ACCESS GATEWAY ]
                                           │
              ┌────────────────────────────┴────────────────────────────┐
              │                                                         │
              ▼                                                         ▼
   [ EMERGENCY BREAK-GLASS ]                                [ NORMAL DOCTOR ACCESS ]
  - Intended for Paramedics/EMS                            - Intended for Verified Physicians
  - Mandatory Emergency Checkbox                           - Authenticated Login Required
  - Mandatory Responder Name & Reason                      - Verified Medical License Enforced
  - IP Address & Timestamp Logged                          - Explicit Confirmation Screen
              │                                                         │
              ▼                                                         ▼
   [ EPHEMERAL TIME-LIMITED TOKEN ]                         [ CLINICAL DOCTOR AUDIT ]
  - 10-Minute Expiry (TTL)                                 - Permanent Record in Database
  - SHA-256 Hashed at Rest                                 - Attributed to Doctor ID & Hospital
              │                                                         │
              ▼                                                         ▼
  [ CRITICAL EMERGENCY TIER ONLY ]                         [ FULL CLINICAL RECORD ]
  - Blood Group (Prominent)                                - Blood Group & Vitals
  - Life-Threatening Allergies                             - Full Allergies & Conditions
  - Chronic Critical Conditions                            - Active Medications
  - Active Medications                                     - Past Surgical History
  - Next-of-Kin Direct Contacts                            - Clinical Consultation Notes
  (Surgical & Private Notes SUPPRESSED)                    - Next-of-Kin Emergency Contacts
              │                                                         │
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
                       [ PATIENT INFORMATION ACCESS HISTORY ]
                       - Real-time audit trail on Patient Dashboard
                       - Distinguishes "Doctor Access" vs "Emergency Break-Glass"
```

---

## 3. Dual Access Model & Emergency Data Tiering

SahayID enforces a strict architectural boundary between routine physician access and urgent emergency triage:

### Access Model Comparison

| Dimension | Normal Doctor Access | Emergency Break-Glass Access |
|---|---|---|
| **Target User** | Licensed Hospital / Clinic Physicians | First Responders, Paramedics, ER Nurses |
| **Authentication** | Username/Email + Password (`DOC-XXXXXXXX`) | Anonymous / Ephemeral (No account required) |
| **Prerequisites** | Verification Status = `verified` | Explicit Emergency Acknowledgement Checkbox |
| **Identity Collection**| Registered Practitioner Profile & License | Responder Name, Reason, Organization |
| **Session Lifetime** | Authenticated Doctor Session | 10-Minute Cryptographic Ephemeral Token |
| **Token Storage** | Secure HTTP-Only Cookie Session | Single-use URL token, SHA-256 hash at rest |
| **Data Scope** | **Full Clinical Record**: Vitals, allergies, conditions, medications, surgeries, notes | **Critical Lifesaving Tier Only**: Blood group, severe allergies, conditions, meds, contacts |
| **Data Suppression** | No clinical data suppressed | **Suppresses**: Surgical history & private notes |
| **Audit Log Type** | `DOCTOR_ACCESS` (`actor_type: DOCTOR`) | `EMERGENCY_BREAK_GLASS` (`actor_type: RESPONDER`) |
| **Patient Visibility** | Prominently listed with Doctor & Hospital name | Prominently listed with Responder & Reason |

---

## 4. Role-Based Architecture & Portals

SahayID enforces server-side role isolation using independent database models, session guards, and distinct authentication gateways:

```
                            [ APPLICATION ENTRY ]
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
         [ PATIENT ROLE ]                          [ DOCTOR ROLE ]
         Identifier: MED-XXXXXXXX                  Identifier: DOC-XXXXXXXX
         Portal: /dashboard                        Portal: /doctor/dashboard
         Guard: @patient_required                  Guard: @doctor_required
```

### 1. Patient Portal
- **Unique Identifier**: `MED-XXXXXXXX` (8-character collision-resistant random code).
- **Personal Dashboard**: Profile completion percentage tracking across 8 clinical components, blood group indicator, printable wallet card, and emergency QR code.
- **Medical Profile Management**: Self-administered clinical profile including allergies, medical conditions, active prescriptions, surgical history, and emergency notes.
- **Emergency Contacts**: Dedicated next-of-kin contact management with instant phone dialing support.
- **Information Access History**: Full audit trail reflecting every time a doctor or first responder accessed the patient's record, with clear badges distinguishing access modes.

### 2. Doctor Clinical Portal
- **Unique Identifier**: `DOC-XXXXXXXX` (8-character collision-resistant practitioner code).
- **Practitioner Profile**: Tracks doctor name, medical specialization, hospital/clinic affiliation, medical council registration number, and verification status.
- **Verification Lifecycle**:
  - `pending`: Default status upon practitioner registration. Clinical lookup actions are restricted with warning banners until administrator/council verification.
  - `verified`: Fully authorized practitioner. Can inspect patient clinical records via SahayID Number or simulated QR scan.
  - `suspended`: Temporarily or permanently revoked practitioner access.
- **Patient Search & Lookup**: Instant retrieval of patient records by entering their SahayID Number or scanning a QR code link.
- **Confirmation Gate**: Pre-access screen displaying limited demographics (Name, SahayID, DOB) and prominent privacy/audit disclaimers before unlocking the complete record.
- **Read-Only Clinical View**: Displays complete medical records without modification privileges, automatically logging a `DOCTOR_ACCESS` audit event.

---

## 5. Security & Privacy Architecture

### Zero-Knowledge QR Generation & Ephemeral Filesystem Support
- **Payload Privacy**: Encodes strictly the routing URL (`/emergency/{medi_id}`). Zero personal or health data is stored in the QR image.
- **Dynamic In-Memory Generation**: Supports ephemeral cloud environments (Heroku, Render, Railway) where local filesystems are non-persistent. The helper `generate_medi_qr_bytes(medi_id)` renders QR codes on the fly using `io.BytesIO`.
- **Configurable Routing Domain**: Reads domain URLs dynamically from `SAHAYID_BASE_URL` or `BASE_URL` with local fallback.
- **Dynamic Endpoints**: Both `/qr/<medi_id>.png` and `/download-qr` stream PNG buffers directly from memory.

### Ephemeral Break-Glass Tokens
- **Generation**: Issued using cryptographically secure random bytes (`secrets.token_urlsafe(32)`).
- **Storage-at-Rest**: Raw tokens are never stored in the database. Only the SHA-256 hash (`token_hash`) is persisted.
- **Strict Time-To-Live**: Tokens expire automatically after 10 minutes.
- **Post-Expiration Rejection**: Expired tokens return HTTP 403 Forbidden with zero clinical disclosure.

### Defensive HTTP Headers & Secure Cookies
- `X-Content-Type-Options: nosniff` (Prevents MIME-confusion attacks)
- `X-Frame-Options: DENY` (Mitigates clickjacking in framed contexts)
- `Referrer-Policy: strict-origin` (Prevents ephemeral token leakage in HTTP referrers)
- `SESSION_COOKIE_HTTPONLY = True` (Guards session tokens from client-side script access)
- `SESSION_COOKIE_SAMESITE = 'Lax'` (Protects against Cross-Site Request Forgery)
- `SESSION_COOKIE_SECURE = True` (Activated automatically when `FLASK_ENV=production` or behind HTTPS)

---

## 6. Database Schema & Multi-Database Support

The application abstracts database access to support both **SQLite 3** (for local development and testing) and **PostgreSQL** (for production cloud deployments):

```
+------------------+         +-----------------------+
|      users       |1       1|   medical_profiles    |
|------------------+---------+-----------------------|
| id (PK)          |         | id (PK)               |
| medi_id (UNIQUE) |         | user_id (FK)          |
| full_name        |         | date_of_birth         |
| email (UNIQUE)   |         | gender                |
| phone            |         | blood_group           |
| password_hash    |         | allergies             |
| created_at       |         | medical_conditions    |
+--------+---------+         | current_medications   |
         |                   | previous_surgeries    |
         |                   | additional_notes      |
         |                   +-----------------------+
         |1
         +-------------------+1          +-----------------------+
         |                   +-----------+  emergency_contacts   |
         |                   |           |-----------------------|
         |                   |           | id (PK)               |
         |                   |           | user_id (FK)          |
         |                   |           | name, relationship    |
         |                   |           | phone, created_at     |
         |                   |           +-----------------------+
         |                   |
         |1                  |1          +-----------------------+
         +-------------------+-----------+      access_logs      |
         |                   |           |-----------------------|
         |                   |           | id (PK)               |
         |                   |           | user_id (FK)          |
         |                   |           | doctor_id (FK/NULL)   |
         |                   |           | actor_type            |
         |                   |           | actor_name            |
         |                   |           | organization          |
         |                   |           | reason                |
         |                   |           | access_type           |
         |                   |           | accessed_at           |
         |                   |           | ip_address            |
         |                   |           +-----------------------+
         |                   |
         |1                  |1          +-----------------------+
         +-------------------+-----------+   emergency_access    |
         |                               |-----------------------|
         |                               | id (PK)               |
         |                               | user_id (FK)          |
         |                               | token_hash (UNIQUE)   |
         |                               | responder_name        |
         |                               | organization          |
         |                               | reason                |
         |                               | created_at            |
         |                               | expires_at            |
         |                               | accessed_at           |
         |                               | ip_address            |
         |                               +-----------------------+
         |
+--------+---------+
|     doctors      |
|------------------|
| id (PK)          |
| doctor_id (UNQ)  |
| full_name        |
| email (UNIQUE)   |
| phone            |
| password_hash    |
| specialization   |
| hospital_or_cl.. |
| registration_num |
| verification_st..| ('pending' | 'verified' | 'suspended')
| created_at       |
+------------------+
```

### Strategic Indexes
- `idx_users_medi_id` ON `users(medi_id)`
- `idx_users_email` ON `users(email)`
- `idx_doctors_doctor_id` ON `doctors(doctor_id)`
- `idx_doctors_email` ON `doctors(email)`
- `idx_emergency_access_token` ON `emergency_access(token_hash)`
- `idx_emergency_contacts_user` ON `emergency_contacts(user_id)`
- `idx_access_logs_user` ON `access_logs(user_id)`
- `idx_medical_profiles_user` ON `medical_profiles(user_id)`

---

## 7. Installation & Setup Instructions

### Prerequisites
- Python 3.10 or higher
- `pip` package manager
- Modern web browser

### Step 1: Clone or Navigate to Project
```bash
git clone https://github.com/pandeyadityanew-web/mediid.git
cd mediid
```

### Step 2: Create and Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 8. Environment Variables & Production Deployment

### Environment Configuration

Configure the following environment variables in production:

| Variable | Description | Default (Development) |
|---|---|---|
| `SECRET_KEY` | Flask cryptographically signed session key | Generated fallback key |
| `DATABASE_URL` | PostgreSQL connection string (`postgresql://...`) | Uses local SQLite database |
| `SAHAYID_BASE_URL` | Public production base URL for generated QR codes | `http://127.0.0.1:5000` |
| `FLASK_ENV` | Application environment (`development` / `production`) | `development` |

### Running Locally (Development)
```bash
# Seed demo accounts
python seed_demo.py

# Launch development server
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

### Running with Gunicorn (Production)
```bash
gunicorn --workers 4 --bind 0.0.0.0:5000 --timeout 60 app:app
```

### Reverse Proxy Deployment (Nginx)
When running behind an Nginx or cloud load balancer reverse proxy, Werkzeug's `ProxyFix` middleware automatically ensures correct client IP attribution and protocol scheme detection.

---

## 9. Demonstration Guide & Test Credentials

The database seeding script creates two fully configured accounts ready for live evaluation:

### 1. Patient Demo Account
- **Role**: Patient
- **Identifier**: `alex.demo@mediid.local` *(or `MED-DEMO2026`)*
- **Password**: `DemoPass123!`
- **Assigned SahayID Number**: `MED-DEMO2026`
- **Patient Name**: Alex Sharma
- **Blood Group**: O+
- **Critical Allergies**: Penicillin (severe anaphylaxis), Peanuts
- **Conditions**: Type 1 Diabetes
- **Medications**: Insulin Glargine 20 units nightly
- **Emergency Contact**: Priya Sharma (Spouse &bull; `+1-555-019-9944`)

### 2. Verified Doctor Demo Account
- **Role**: Doctor (Verified Practitioner)
- **Identifier**: `doctor@sahayid.demo` *(or `DOC-DEMO2026`)*
- **Password**: `DemoDoctor123!`
- **Doctor ID**: `DOC-DEMO2026`
- **Doctor Name**: Dr. Arjun Mehta
- **Specialization**: Emergency Medicine & Critical Care
- **Affiliated Hospital**: Sahay General Hospital
- **Registration Number**: REG-MH-2026-8842
- **Verification Status**: Verified

### Demonstration Walkthrough
1. **Patient Portal**:
   - Sign in as `alex.demo@mediid.local` at `/login`.
   - Inspect the patient dashboard, 100% profile completion bar, printable wallet card, incoming physician access requests, and Information Access History.
2. **Emergency Break-Glass Gateway**:
   - Open a private/incognito window (simulating a paramedic scanning a QR code).
   - Navigate to: `http://127.0.0.1:5000/emergency/MED-DEMO2026`.
   - Observe the two options: `[ Doctor / Authorized Access ]` and `[ Emergency Break-Glass ]`.
   - Select **Emergency Break-Glass**.
   - Complete verification (Responder Name: `Paramedic Sarah`, Organization: `Metro EMS Unit 4`, Reason: `Roadside acute trauma`).
   - Check the mandatory emergency confirmation checkbox and submit.
   - Review the verified critical emergency tier with active 10-minute countdown (vitals, allergies, conditions, medications, contacts; surgical and private notes suppressed).
3. **Doctor Clinical Portal & Patient Consent + OTP Workflow**:
   - Open another browser tab and navigate to `/doctor/login`.
   - Sign in as `doctor@sahayid.demo` / `DemoDoctor123!`.
   - Under **Access Patient Record**, enter SahayID Number `MED-DEMO2026` (or scan the QR link).
   - Review the **Access Confirmation** screen displaying limited identity and privacy notices.
   - Click **Request Patient Consent & Initiate OTP Verification**.
   - Doctor UI enters live polling mode on `/doctor/access-request/<request_token>`.
   - In the patient browser tab, reload `/dashboard` and view the pending request from Dr. Arjun Mehta.
   - Click **Approve (Generate OTP)**. A secure 6-digit one-time passcode is generated and displayed on the patient screen.
   - In the doctor tab, enter the 6-digit OTP code and submit verification.
   - Doctor is granted temporary 30-minute access to the full medical record (including surgical history and consultation notes).
4. **Audit Trail Verification**:
   - Switch back to the Patient Dashboard tab and refresh.
   - Observe both access events in the **Information Access History** table:
     - `Paramedic Sarah` (Emergency Break-Glass &bull; Metro EMS Unit 4)
     - `Doctor: Dr. Arjun Mehta` (Doctor Access &bull; Sahay General Hospital &bull; Authorized)

---

## 10. Automated Test Battery (127 Checks Verified)

The project includes 9 modular automated test suites providing 100% verification across all functional, security, and integration layers:

```bash
# Execute individual test suites
python test_authentication.py
python test_patient_access.py
python test_qr.py
python test_emergency_access.py
python test_integration.py
python test_doctor_access.py
python test_roles.py
python test_break_glass_and_production.py
python test_consent_otp.py
```

### Test Coverage Summary

| Test Suite | Focus Area | Checks | Status |
|---|---|---|---|
| `test_authentication.py` | Database schema, foreign keys, password hashing, registration, and dual login. | 9 / 9 | PASS |
| `test_patient_access.py` | Patient dashboard, medical profile updates, emergency contacts, IDOR defenses. | 10 / 10 | PASS |
| `test_qr.py` | QR code generation, zero-knowledge payload validation, download isolation. | 9 / 9 | PASS |
| `test_emergency_access.py` | Emergency verification gateway, ephemeral tokens, SHA-256 token hashing, audit logs. | 13 / 13 | PASS |
| `test_integration.py` | Full end-to-end integration, process path timeline, security headers, branded error pages. | 18 / 18 | PASS |
| `test_doctor_access.py` | Doctor lookup, confirmation gate, QR routing, recent access isolation, read-only view. | 18 / 18 | PASS |
| `test_roles.py` | Doctor role authentication, session isolation, doctor verification gate, audit logs. | 15 / 15 | PASS |
| `test_break_glass_and_production.py` | Break-glass validation, emergency data tiering, dynamic QR, environment config, DB abstraction. | 20 / 20 | PASS |
| `test_consent_otp.py` | Patient consent approval/denial, 6-digit OTP generation, SHA-256 hash at rest, rate limiting, and 30m authorization. | 15 / 15 | PASS |
| **Total** | **Comprehensive Full-Spectrum Verification** | **127 / 127** | **100% PASS** |

---

## 11. Security & Privacy Matrix (Viva Discussion Points)

| Security Aspect | Implementation Mechanism | Viva Examination Talking Point |
|---|---|---|
| **QR Code Privacy** | Encodes strictly the routing URL (`/emergency/{medi_id}`). Zero medical payload. | Anyone photographing or scanning the QR code in public receives zero health information. |
| **Emergency Data Tiering** | Break-glass view filters strictly for lifesaving data, suppressing surgeries and consultation notes. | Paramedics receive only triage essentials; sensitive psychological/surgical history remains shielded. |
| **Token-at-Rest Security** | Raw 32-byte token given to responder; database stores solely SHA-256 hash. | Even a complete database leakage does not expose valid active emergency tokens. |
| **Session & Role Isolation** | `@patient_required` and `@doctor_required` check session roles on every request. | Patients cannot access doctor lookups, and doctors cannot tamper with patient profile forms. |
| **Doctor Verification Gate** | Unverified / pending doctor accounts are blocked from accessing patient medical files. | Prevents newly self-registered accounts from abusing clinical search before accreditation. |
| **Ephemeral Storage Defense** | QR images generated on the fly via `generate_medi_qr_bytes` without relying on disk persistence. | Ensures reliable operation on containerized platforms (Render, Heroku, AWS ECS) with read-only root filesystems. |
| **Database Abstraction** | Seamlessly switches to PostgreSQL via `DATABASE_URL` using cursor and connection wrappers. | Production-grade concurrency and enterprise scalability with zero code alterations. |
| **IDOR Prevention** | Contact deletion and QR download verify `WHERE id = ? AND user_id = session['user_id']`. | Malicious users cannot manipulate URL parameters to delete or view another user's records. |
| **SQL Injection Defense** | 100% Parameterized queries (`?` bindings) across all routes and database engines. | Zero raw string interpolation inside SQL statements across the entire application codebase. |
| **Defensive HTTP Headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin`. | Protects against UI clickjacking, MIME sniffing, and referrer token leakages. |
| **Bilateral Auditability** | Dual-source logging for both Emergency Break-Glass and Verified Physicians. | Full accountability; patients possess complete visibility into who viewed their record. |

---

## 12. Academic Prototype Context & Real-World Considerations

### Prototype Scope & Academic Disclaimers
- **Self-Reported Health Data**: Medical details are currently entered by the patient for academic demonstration purposes. In a commercial clinical deployment, records would synchronize with certified hospital Electronic Health Record (EHR) systems.
- **Simulated Medical Council Accreditation**: Doctor verification status is managed via database flags rather than a live National Medical Commission (NMC) API.
- **Emergency Triage Intent**: The break-glass feature is engineered for acute resuscitation and triage contexts where patient consent cannot be obtained.
- **Simulated Telephony Alerts**: Access events are logged to the database rather than triggering live outbound SMS/cellular alerts to emergency contacts.

### Future Roadmap
- **FHIR / HL7 Interoperability**: Bi-directional synchronization with Fast Healthcare Interoperability Resources standards.
- **National Registry Single Sign-On**: Integration with institutional identity providers (e.g., ABDM / NHS digital identity gateways) for instant practitioner verification.
- **Automated Next-of-Kin Cellular Alerts**: Automated Twilio integration to dispatch SMS alerts with GPS coordinates whenever emergency verification occurs.
- **NFC Medical Hardware Integration**: Flashing physical NFC bracelets or smart cards with the same secure gateway link for tap-to-access paramedic equipment.

---

## 13. License & Project Metadata

- **Project Title**: SahayID
- **Tagline**: CRITICAL MEDICAL ACCESS
- **License**: MIT License
- **Year**: 2026
