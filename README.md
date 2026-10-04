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

**Privacy-Centric Digital Medical Identity & Authorized Clinical Gateway**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.x](https://img.shields.io/badge/flask-3.x-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Database: SQLite](https://img.shields.io/badge/database-SQLite%203-lightgrey.svg)](https://www.sqlite.org/)

</div>

---

## 1. Executive Summary

**SahayID** (*Critical Medical Access*) is a privacy-first digital medical identity infrastructure designed for emergency healthcare triage and authorized clinical inquiry. 

In acute medical crises—such as unconscious trauma victims, cardiac emergencies, or severe anaphylaxis—first responders and hospital clinicians face a critical information vacuum. Simultaneously, public exposure of raw medical records violates basic patient privacy.

SahayID resolves this tension by providing:
1. **Zero-Knowledge Emergency QR Codes**: Scannable QR cards that encode **only** an unguessable routing gateway URL—never embedding raw personal or medical data inside the physical QR code.
2. **First Responder Emergency Gateway & Verification**: A legally monitored gateway requiring responders to submit their identity, medical organization, and an emergency declaration before accessing lifesaving information.
3. **Dedicated Doctor Clinical Portal**: A secure, verified practitioner portal allowing licensed physicians to look up patient records by SahayID Number or QR code under active clinical review.
4. **Unified Information Access History**: An immutable audit log displaying every access event—distinguishing between First Responder emergency access and Verified Doctor clinical review.

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
                                [ EMERGENCY GATEWAY ]
                                           │
             ┌─────────────────────────────┴─────────────────────────────┐
             ▼                                                           ▼
   [ FIRST RESPONDER ]                                         [ LICENSED DOCTOR ]
  - Honor Declaration                                         - Authenticated Portal
  - Stated Emergency Reason                                   - Verified Medical License
  - Network IP + Timestamp                                    - Direct Clinical Access
             │                                                           │
             ▼                                                           ▼
   [ EPHEMERAL TOKEN ]                                         [ DOCTOR ACCESS LOG ]
  - 10-Minute Expiry (TTL)                                    - Recorded to Database
  - SHA-256 Hashed at Rest                                    - Attributed to Doctor ID
             │                                                           │
             └─────────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                            [ EMERGENCY MEDICAL RECORD ]
                            - Blood Group (Prominent)
                            - Critical Drug Allergies
                            - Chronic Medical Conditions
                            - Current Active Medications
                            - Next-of-Kin Contacts (Direct Dial)
                                           │
                                           ▼
                       [ PATIENT INFORMATION ACCESS HISTORY ]
                       - Real-time audit trail on Patient Dashboard
```

---

## 3. Role-Based Architecture (Patient vs. Doctor)

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
- **Information Access History**: Full audit trail reflecting every time a doctor or first responder accessed the patient's record.

### 2. Doctor Clinical Portal
- **Unique Identifier**: `DOC-XXXXXXXX` (8-character collision-resistant practitioner code).
- **Practitioner Profile**: Tracks doctor name, medical specialization, hospital/clinic affiliation, medical council registration number, and verification status.
- **Verification Lifecycle**:
  - `pending`: Default status upon practitioner registration. Clinical lookup actions are restricted with warning banners until administrator/council verification.
  - `verified`: Fully authorized practitioner. Can inspect patient clinical records via SahayID Number or simulated QR scan.
  - `suspended`: Temporarily or permanently revoked practitioner access.
- **Patient Search & Lookup**: Instant retrieval of patient records by entering their SahayID Number or simulating QR scan review.
- **Clinical Review View**: Displays comprehensive emergency records, blood group, allergies, medications, and next-of-kin contacts, with an automatic `DOCTOR_ACCESS` audit entry recorded in the patient's history.

---

## 4. Key Functional Capabilities

### Modern Healthcare Design System
- Semantic, accessible HTML5 and custom CSS3 design system with medical color palettes (Primary Clinical Blue `#0284c7`, Secondary Surgeon Teal `#0d9488`, Emergency Red `#dc2626`).
- Responsive layout optimized for mobile screens, tablets, and desktop workstations.
- Official SahayID branding, logo, and shield icon embedded across all navigation headers.
- Branded HTTP error pages (`404 Not Found`, `403 Forbidden`, `429 Too Many Requests`, `500 Server Error`).

### Zero-Knowledge QR Generation & Wallet Card
- Automatic QR generation upon patient registration using `qrcode[pil]`.
- Enforces zero health information in QR payload (strictly encodes the access routing URL).
- Printable physical SahayID wallet card with front and rear views, patient blood badge, and `@media print` layout.
- Authenticated, user-isolated QR code download (`/download-qr`).

### Time-Limited Emergency Access Protocol
- Two-tier gateway verification preventing unauthorized lookups.
- Ephemeral cryptographic access tokens (`secrets.token_urlsafe(32)`) with a strict 10-minute server-side time-to-live (TTL).
- Token security at rest: Server stores strictly the SHA-256 hash (`token_hash`) of the issued token.
- Automatic countdown timer with live client-side synchronization and server-side invalidation.

### Comprehensive Audit Logging
- Every interaction generates a permanent audit trail entry in `access_logs`.
- Patient dashboard aggregates both emergency responder accesses and verified doctor clinical reviews.
- Details logged include accessor name, organization/hospital, clinical reason, network IP, timestamp, and authorization status.

---

## 5. Database Schema

The system uses SQLite 3 with strict foreign key constraints (`PRAGMA foreign_keys = ON;`) and optimized indexes:

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

## 6. Installation & Setup Instructions

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

### Step 4: Environment Variables (Optional)
Copy `.env.example` to `.env` if custom secrets or host ports are needed:
```bash
copy .env.example .env
```
Default fallbacks are configured out of the box (`BASE_URL='http://127.0.0.1:5000'`, `SECRET_KEY='sahayid-dev-secret-key-2026'`).

---

## 7. How to Run

### Step 1: Seed Demo Data
Initialize the database with pre-configured, presentation-ready fictional accounts for both Patient and Doctor roles:
```bash
python seed_demo.py
```

### Step 2: Start the Web Application
```bash
python app.py
```

### Step 3: Open in Browser
Visit: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 8. Demonstration Guide & Test Credentials

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
   - Inspect the patient dashboard, 100% profile completion bar, printable wallet card, and Information Access History.
2. **First Responder Emergency Workflow**:
   - Open a private/incognito window (simulating a paramedic scanning a QR code).
   - Navigate to: `http://127.0.0.1:5000/emergency/MED-DEMO2026`.
   - Observe that medical data is hidden and the legal disclaimer is presented.
   - Complete verification (Responder Name: `Paramedic Sarah`, Organization: `Metro EMS Unit 4`, Reason: `Roadside trauma evaluation`).
   - Confirm emergency and submit. Review the verified clinical record with active 10-minute countdown.
3. **Doctor Clinical Portal Workflow**:
   - Open another browser tab and navigate to `/doctor/login`.
   - Sign in as `doctor@sahayid.demo` / `DemoDoctor123!`.
   - Inspect the Doctor Dashboard displaying Dr. Arjun Mehta's verified badge and recent access log.
   - Under **Access Patient Record**, enter SahayID Number `MED-DEMO2026` (or scan/paste the QR link).
   - Review the **Patient Found** confirmation screen displaying limited demographics, doctor identity, and the prominent privacy/audit message.
   - Click **Access Medical Record** to view the full read-only clinical record (allergies, conditions, medications, next-of-kin contacts).
4. **Audit Trail Verification**:
   - Switch back to the Patient Dashboard tab and refresh.
   - Observe both access events in the **Information Access History** table:
     - `Paramedic Sarah` (Metro EMS Unit 4 &bull; First Responder Access)
     - `Doctor: Dr. Arjun Mehta` (Sahay General Hospital &bull; Doctor Access &bull; Authorized)

---

## 9. Comprehensive Automated Test Suites

The project features a modular automated test suite covering every system layer:

```bash
# Run all test suites
python test_verification.py
python test_part3.py
python test_part4.py
python test_part5.py
python test_final.py
python test_roles.py
python test_doctor_patient_access.py
```

### Test Coverage Summary (92 Total Checks)

| Test Suite | Focus Area | Checks |
|---|---|---|
| `test_verification.py` | Database schema, foreign keys, password hashing, user registration, and login. | 9 / 9 Passing |
| `test_part3.py` | Patient dashboard, medical profile updates, emergency contacts, IDOR defenses. | 10 / 10 Passing |
| `test_part4.py` | QR code generation, zero-knowledge payload validation, download endpoint isolation. | 9 / 9 Passing |
| `test_part5.py` | Emergency verification gateway, ephemeral tokens, SHA-256 token hashing, audit logs. | 13 / 13 Passing |
| `test_final.py` | Full end-to-end integration, 7-step landing page, security headers, branded error templates. | 18 / 18 Passing |
| `test_roles.py` | Doctor role authentication, session isolation, doctor verification gate, DOCTOR_ACCESS audit logs. | 15 / 15 Passing |
| `test_doctor_patient_access.py` | Secure lookup, invalid ID handling, confirmation gate, QR routing, and recent access isolation. | 18 / 18 Passing |
| **Total** | | **92 / 92 Passing** |

---

## 10. Security & Privacy Matrix (Viva Discussion Points)

| Security Aspect | Implementation Mechanism | Viva Examination Talking Point |
|---|---|---|
| **QR Code Privacy** | Encodes strictly the routing URL (`/emergency/{medi_id}`). Zero medical payload. | Anyone photographing or scanning the QR code in public receives zero health information. |
| **Token-at-Rest Security** | Raw 32-byte token given to responder; database stores solely SHA-256 hash. | Even a complete database leakage does not expose valid active emergency tokens. |
| **Session & Role Isolation** | `@patient_required` and `@doctor_required` check session roles on every request. | Patients cannot access doctor lookups, and doctors cannot tamper with patient profile forms. |
| **Doctor Verification Gate** | Unverified / pending doctor accounts are blocked from accessing patient medical files. | Prevents newly self-registered accounts from abusing clinical search before accreditation. |
| **IDOR Prevention** | Contact deletion and QR download verify `WHERE id = ? AND user_id = session['user_id']`. | Malicious users cannot manipulate URL parameters to delete or view another user's records. |
| **SQL Injection Defense** | 100% Parameterized queries (`?` bindings). | Zero raw string interpolation inside SQL statements across all application routes. |
| **Brute-Force Rate Limiting** | Sliding window tracking on verification endpoints (max 5 attempts per 10 minutes). | Mitigates automated dictionary attacks against patient SahayID Numbers. |
| **Defensive HTTP Headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin`. | Protects against UI clickjacking, MIME sniffing, and referrer token leakages. |
| **Bilateral Auditability** | Dual-source logging for both Emergency Responders and Verified Physicians. | Full accountability; patients possess complete visibility into who viewed their record. |

---

## 11. Realistic Limitations & Future Roadmap

### Prototype Scope & Academic Disclaimers
- **Self-Reported Health Data**: Medical details are currently entered by the patient. In a commercial production environment, records would synchronize with certified hospital Electronic Health Record (EHR) systems.
- **Simulated Medical Council Accreditation**: Doctor verification status is managed via database flags rather than a live National Medical Commission (NMC) API.
- **Development Database**: SQLite 3 provides zero-configuration development; high-concurrency enterprise deployments would transition to PostgreSQL with connection pooling.
- **Simulated Telephony Alerts**: Access events are logged to the database rather than triggering live outbound SMS/cellular alerts to emergency contacts.

### Future Roadmap
- **FHIR / HL7 Interoperability**: Bi-directional synchronization with Fast Healthcare Interoperability Resources standards.
- **National Registry Single Sign-On**: Integration with institutional identity providers (e.g., ABDM / NHS digital identity gateways) for instant practitioner verification.
- **Automated Next-of-Kin Cellular Alerts**: Automated Twilio integration to dispatch SMS alerts with GPS coordinates whenever emergency verification occurs.
- **NFC Medical Hardware Integration**: Flashing physical NFC bracelets or smart cards with the same secure gateway link for tap-to-access paramedic equipment.

---

## 12. License & Project Metadata

- **Project Title**: SahayID
- **Tagline**: CRITICAL MEDICAL ACCESS
- **License**: MIT License
- **Year**: 2026
