# MediID - Privacy-Focused Digital Medical Identity System

> **"Your Medical Identity. Available When It Matters."**

MediID is a lightweight, privacy-first digital medical identity system designed for emergency healthcare scenarios. It enables individuals to maintain essential, lifesaving medical information—such as blood group, critical allergies, chronic conditions, active medications, and next-of-kin emergency contacts—and provides a unique **MediID** paired with a scannable **QR code** for immediate, controlled access during medical emergencies.

---

## 1. Problem Statement

In acute medical emergencies (such as vehicular collisions, sudden unconsciousness, or severe allergic anaphylaxis), first responders and emergency physicians face a critical information vacuum:
- **Unconscious or Incapacitated Patients**: Patients are frequently unable to communicate their medical history, known drug allergies, or next-of-kin contacts.
- **Dangers of Blind Treatment**: Administering common emergency drugs (such as penicillin or NSAIDs) or incompatible blood transfusions without knowing a patient's medical history can lead to fatal complications.
- **Privacy vs. Access Dilemma**: Storing raw medical data on public cards or directly inside standard QR codes exposes highly confidential health information to anyone who glances at or scans the code in public.

---

## 2. The Solution

MediID bridges the critical gap between **speed of emergency access** and **patient privacy**:
1. **Zero Raw Health Data in QR Codes**: The physical MediID QR code contains solely a secure gateway URL (`http://.../emergency/<medi_id>`). It never embeds names, blood groups, or medical conditions in the QR payload.
2. **First Responder Emergency Gateway & Verification**: Anyone scanning the code lands on a protected authorization gateway. To view emergency information, the responder must state their identity, organization, reason, and confirm under penalty of law that an emergency exists.
3. **Time-Limited Cryptographic Tokens**: Upon verification, a cryptographically random URL-safe token is issued with a **strict 10-minute expiration**. The server stores only the **SHA-256 hash** of the token.
4. **Complete Patient Auditability**: Every QR scan and every verified clinical view is logged with timestamps and IP addresses. Patients can inspect their entire emergency access history directly from their dashboard.

---

## 3. Key Features (Parts 1 – 6)

### Part 1: Modern Healthcare Design & Layout
- Clean, responsive UI built with custom semantic CSS (zero heavy front-end framework bloat).
- Mobile-optimized navigation and accessible forms.
- Branded error pages (`404 Not Found`, `403 Forbidden`, `429 Rate Limited`, `500 Server Error`).

### Part 2: Secure Database & Authentication Foundation
- SQLite database with explicit foreign key enforcement (`PRAGMA foreign_keys = ON;`) on every connection.
- Cryptographically random MediID format: `MED-XXXXXXXX` (uppercase alphanumeric, collision-resistant).
- Secure password hashing using Werkzeug (`scrypt` / PBKDF2).
- Parameterized SQL queries throughout to eliminate SQL injection vulnerabilities.
- Session-based authentication with ownership guards (`@login_required`).

### Part 3: Patient Dashboard & Medical Profile
- Patient dashboard with dynamic profile completion percentage tracking (8 clinical criteria).
- Medical profile management organized into:
  - **Personal Information**: Date of birth, gender, blood group.
  - **Medical Information**: Critical allergies, chronic conditions, current medications, surgical history.
  - **Additional Information**: Emergency notes (e.g., organ donor status, implants).
- Emergency contacts manager: Add, list, and securely delete next-of-kin contacts with strict ownership verification.

### Part 4: MediID QR Code Generation System
- Dynamic QR code generation using `qrcode[pil]`.
- QR codes encode strictly the emergency access URL (`{BASE_URL}/emergency/{medi_id}`).
- Dedicated QR image download endpoint (`/download-qr`) restricted to the authenticated session owner.
- Printable physical MediID card layout optimized for standard wallet/badge dimensions with `@media print` styles.

### Part 5: Emergency Access & Verification Protocol
- Emergency gateway route (`/emergency/<medi_id>`) displaying identity confirmation and legal audit notices.
- Verification protocol form (`/emergency/<medi_id>/verify`) requiring responder identification, clinical reason, and emergency declaration checkbox.
- Ephemeral access tokens (`secrets.token_urlsafe(32)`) with 10-minute server-side time-to-live (TTL).
- Token security: Raw tokens are never stored in the database; only SHA-256 hashes (`token_hash`) are persisted.
- Clinical emergency view (`/emergency/access/<token>`) featuring live countdown timer, prominent blood group badge, allergy warnings, and one-click contact dialing.
- Abuse protection: In-built rate limiting restricting excessive verification requests per MediID.

### Part 6: System Hardening & Polish
- Defensive HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-XSS-Protection`).
- Strategic database indexes for fast lookups on high-traffic columns (`users.medi_id`, `users.email`, `emergency_access.token_hash`).
- Automated demo seeding script (`seed_demo.py`) for presentations and viva examinations.
- Comprehensive end-to-end automated test suite covering all 18 system requirements.

---

## 4. End-to-End Emergency Workflow

```
+-------------------------------------------------------------------------+
|                              PATIENT SIDE                               |
+-------------------------------------------------------------------------+
   [ Register ] ---> [ Enter Medical Data ] ---> [ Download/Print QR Card ]
                                                             |
                                                             v
+-------------------------------------------------------------------------+
|                            EMERGENCY EVENT                              |
+-------------------------------------------------------------------------+
                     1. Responder Scans Physical QR Code
                                     |
                                     v
                   2. Public Emergency Gateway Loaded
                        (/emergency/<medi_id>)
                 (Medical info is HIDDEN at this stage)
                                     |
                                     v
                    3. Responder Completes Verification
                     - Responder Name & Organization
                     - Emergency Reason & Legal Confirmation
                                     |
                                     v
                4. Cryptographic Temporary Token Generated
                     - 32-byte URL-safe random string
                     - SHA-256 hash stored in SQLite
                     - 10-minute automatic expiration
                                     |
                                     v
                  5. Emergency Clinical Record Displayed
                       (/emergency/access/<token>)
                     - Blood Group & Critical Allergies
                     - Active Medications & Medical Conditions
                     - Next-of-Kin Emergency Contacts
                     - Active 10-minute countdown timer
                                     |
                                     v
                     6. Access Recorded in Audit Trail
                     - Responder identity, reason & timestamp
                     - Patient can inspect audit log in Dashboard
```

---

## 5. Technology Stack

- **Backend**: Python 3.10+ / Flask 3.x
- **Database**: SQLite 3 (with foreign key constraints and indexed queries)
- **Frontend**: HTML5, CSS3 (Healthcare design system), Vanilla JavaScript
- **Security & Cryptography**: Werkzeug (`generate_password_hash`, `check_password_hash`), Python standard library `secrets`, `hashlib` (SHA-256)
- **QR Code Generation**: `qrcode[pil]`, Pillow

---

## 6. Database Architecture

The SQLite schema consists of 5 relational tables:

```
+------------------+         +-----------------------+
|      users       |1       1|   medical_profiles    |
|------------------+---------+-----------------------|
| id (PK)          |         | id (PK)               |
| medi_id (UNIQUE) |         | user_id (FK)          |
| full_name        |         | blood_group           |
| email (UNIQUE)   |         | allergies             |
| phone            |         | medical_conditions    |
| password_hash    |         | current_medications   |
| created_at       |         | previous_surgeries    |
+--------+---------+         | additional_notes      |
         |                   +-----------------------+
         |1
         |
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
         |                   |           | access_type           |
         |                   |           | ip_address            |
         |                   |           | accessed_at           |
         |                   |           +-----------------------+
         |                   |
         |1                  |1          +-----------------------+
         +-------------------+-----------+   emergency_access    |
                                         |-----------------------|
                                         | id (PK)               |
                                         | user_id (FK)          |
                                         | token_hash (UNIQUE)   |
                                         | responder_name        |
                                         | organization          |
                                         | reason                |
                                         | created_at            |
                                         | expires_at            |
                                         | accessed_at           |
                                         | ip_address            |
                                         +-----------------------+
```

### Strategic Indexes
- `idx_users_medi_id` ON `users(medi_id)`: Instant lookup during QR scan routing.
- `idx_users_email` ON `users(email)`: Instant lookup during patient login.
- `idx_emergency_access_token` ON `emergency_access(token_hash)`: High-performance validation of temporary tokens.
- `idx_emergency_contacts_user` ON `emergency_contacts(user_id)`: Quick retrieval of next-of-kin contacts.
- `idx_access_logs_user` ON `access_logs(user_id)`: Efficient dashboard audit log queries.

---

## 7. Security & Privacy Highlights (Viva Discussion Points)

| Security Aspect | Implementation in MediID | Viva Talking Point |
|---|---|---|
| **QR Code Privacy** | Encodes `{BASE_URL}/emergency/{medi_id}` only. Zero medical data. | If someone photographs the patient's badge, they obtain zero medical details. |
| **Password Storage** | `werkzeug.security` with strong salts and modern hashing algorithms. | Raw passwords are never stored or logged in plain text. |
| **Token Ephemerality** | 32-byte cryptographically secure random token, 10-minute server TTL. | Access automatically ceases after emergency triage. |
| **Token-at-Rest Protection** | Server hashes token with SHA-256 before inserting into DB. | Even full database compromise does not yield valid active tokens. |
| **SQL Injection Defense** | 100% Parameterized queries (`?` bindings). | Prevents SQL injection across registration, login, and queries. |
| **Cross-User Tampering** | Deletion routes verify `WHERE id = ? AND user_id = session['user_id']`. | Prevents Insecure Direct Object References (IDOR). |
| **Rate Limiting** | Max 5 verification attempts per 10 minutes per MediID. | Mitigates brute-force token generation and denial-of-service. |
| **Defensive HTTP Headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`. | Mitigates clickjacking, MIME-sniffing, and referrer leakage. |
| **Audit Accountability** | Dual-event logging (`EMERGENCY_SCAN` and `EMERGENCY_ACCESS`). | Complete transparency; patients can review access history. |

---

## 8. Installation & Setup Instructions

### Prerequisites
- Python 3.10 or higher
- `pip` package manager
- Modern web browser (Chrome, Edge, Firefox, Safari)

### Step 1: Clone or Navigate to Project
```bash
git clone https://github.com/pandeyadityanew-web/mediid.git
cd mediid
```

### Step 2: Create and Activate Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables (Optional)
Copy `.env.example` to `.env` (or configure system variables):
```bash
# Windows PowerShell
copy .env.example .env
```
Default fallback values (`SECRET_KEY='mediid-dev-secret-key-2026'`, `BASE_URL='http://127.0.0.1:5000'`) are already configured for local execution.

---

## 9. How to Run

### Step 1: Seed Demo Patient Data
Populate the database with a pre-configured, presentation-ready fictional patient:
```bash
python seed_demo.py
```

### Step 2: Start the Flask Application
```bash
python app.py
```

### Step 3: Open in Browser
Visit: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 10. Demo Walkthrough & Test Credentials

### Demo Account (Pre-Seeded via `seed_demo.py`)
- **Login Identifier**: `alex.demo@mediid.local` *(or `MED-DEMO2026`)*
- **Password**: `DemoPass123!`
- **Assigned MediID**: `MED-DEMO2026`
- **Blood Group**: O+
- **Critical Allergies**: Penicillin (severe anaphylaxis), Peanuts
- **Emergency Contact**: Priya Sharma (`+1-555-019-9944`)

### Viva Demonstration Steps
1. **Patient Authentication**: Log in as Alex Sharma using either email or MediID.
2. **Dashboard Overview**: Review the patient header, blood group badge, profile completion bar, printable physical ID card, and access audit log.
3. **Download QR Code**: Click **Download QR** to inspect the generated image file.
4. **Simulate First Responder Scan**:
   - Open an incognito/private browser window (simulating an external responder's phone).
   - Navigate to: `http://127.0.0.1:5000/emergency/MED-DEMO2026`.
   - Observe that medical data is **hidden** and the legal audit disclaimer is presented.
5. **Execute Verification**:
   - Click **Continue to Verification**.
   - Enter responder details (e.g., Name: `Dr. Sarah Patel`, Org: `City Trauma Center`, Reason: `Acute trauma triage`).
   - Check the mandatory emergency confirmation box and submit.
6. **Review Emergency View**:
   - Inspect the verified clinical page: blood group banner, critical allergy box, medications, next-of-kin contact, and the active 10-minute countdown timer.
7. **Verify Audit Trail**:
   - Switch back to the authenticated patient's dashboard and refresh.
   - Observe that `Dr. Sarah Patel`'s emergency access is now immutably logged with timestamp and active status.

---

## 11. Automated Test Suites

MediID includes 5 automated test suites verifying every layer of the system:

```bash
# Run all test suites sequentially
python test_verification.py
python test_part3.py
python test_part4.py
python test_part5.py
python test_final.py
```

### What `test_final.py` Verifies:
1. Landing page rendering & 7-step "How It Works" workflow.
2. User registration & cryptographic `MED-XXXXXXXX` formatting.
3. User login & session audit trail recording.
4. Route protection guards on unauthenticated visits.
5. Dashboard rendering with vitals, printable card, and audit tables.
6. Medical profile update functionality across all clinical categories.
7. Emergency contact addition and secure deletion.
8. Scannable QR code image generation.
9. Secure QR attachment download endpoint.
10. QR data privacy guarantee (zero health data in payload).
11. First responder gateway privacy guard & legal disclaimer.
12. Graceful rejection of non-existent MediIDs (404).
13. Emergency verification validation (mandatory confirmation checkbox).
14. Cryptographic token generation & SHA-256 database hashing.
15. Full clinical view rendering with countdown timer.
16. Server-side token expiration enforcement (403 Forbidden).
17. Custom branded error templates (404, 403, 500).
18. Defensive HTTP security headers (`nosniff`, `DENY`, `strict-origin`).

---

## 12. Realistic Limitations & Future Scope

### Current Academic / Prototype Limitations
- **Patient-Provided Information**: Clinical data is self-reported by the patient; MediID does not currently interface with hospital Electronic Health Record (EHR) systems to independently verify clinical claims.
- **Local SQLite Database**: While suitable for development and demonstrations, high-concurrency production deployments would require PostgreSQL or MySQL with connection pooling.
- **Simulated Responder Identity**: First responder verification is based on honor-system self-declaration with legal warnings, rather than integration with government paramedic registry APIs or smart card PKI.
- **Simulated SMS / Push Notifications**: Access events are logged in the database rather than immediately triggering real-time SMS/cellular alerts to emergency contacts.

### Future Scope
- **FHIR / HL7 Interoperability**: Integration with Fast Healthcare Interoperability Resources (FHIR) to synchronize verified diagnoses directly from hospital EHR systems.
- **National Emergency Registry Integration**: Integration with emergency dispatch portals (e.g., 911 / 112 CAD systems) to authenticate emergency personnel via institutional credentials.
- **Automated Emergency Contact Alerts**: Automated Twilio/telephony integration to instantly broadcast SMS and GPS location alerts to next-of-kin when emergency access is verified.
- **NFC Tag Support**: Programming physical NFC wristbands or cards with the same secure gateway link for tap-to-access paramedic hardware.
- **Zero-Knowledge Multi-Key Encryption**: Encrypting sensitive medical fields client-side, with key fragments revealed only upon multi-party emergency consensus.

---

## 13. License & Authorship

- **Project**: MediID
- **Purpose**: Academic Demonstration & Viva Examination
- **Year**: 2026
- **License**: MIT License
