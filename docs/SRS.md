# Software Requirements Specification (SRS)
## SahayID: Critical Medical Access Infrastructure

**Document Version:** 2.0  
**Status:** Approved  
**Author:** SahayID Engineering & Clinical Architecture Team  

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) document details the complete functional and non-functional requirements for the **SahayID** (*Critical Medical Access*) system. It serves as the primary technical specification for developers, quality assurance engineers, security auditors, and clinical administrators.

### 1.2 Scope
SahayID is a privacy-first digital medical identity and clinical access management platform. The software provides:
1. **Patient-Mediated Medical Identity:** Unique, privacy-preserving medical identifiers (`MED-XXXXXXXX`) and self-managed health records (vitals, blood group, allergies, medications, past surgeries, emergency contacts).
2. **Zero-Knowledge Emergency Badges:** QR codes encoding strictly unguessable routing URLs with zero embedded clinical data.
3. **Emergency Break-Glass Triage:** Time-limited (15-minute), audited emergency access for first responders with mandatory identification and legal acknowledgement.
4. **Physician Verification & Clinical Consent Engine:** Dynamic 6-digit One-Time Password (OTP) exchange granting verified physicians 30-minute access windows.
5. **Administrative Oversight Portal:** Secure console (`/admin`) for validating physician medical licenses and managing credential approvals/rejections.
6. **Progressive Web App (PWA):** Native installability across mobile and desktop environments.

### 1.3 Definitions, Acronyms, and Abbreviations
- **SahayID / MediID:** The unique 12-character identifier assigned to patient records (`MED-XXXXXXXX`).
- **Doctor ID:** The unique 12-character identifier assigned to verified medical practitioners (`DOC-XXXXXXXX`).
- **Zero-Knowledge QR:** A QR code containing only a routing URL without any raw medical, clinical, or personal information.
- **Break-Glass:** The emergency protocol allowing immediate, audited access to lifesaving vitals without prior patient authentication.
- **OTP:** One-Time Password; a 6-digit cryptographically generated numeric code valid for 5 minutes.
- **RBAC:** Role-Based Access Control (`patient`, `doctor`, `admin`).
- **TTL:** Time To Live; cryptographic lifespan of temporary tokens.
- **PWA:** Progressive Web App.

### 1.4 References
- IEEE Std 830-1998 (Recommended Practice for Software Requirements Specifications).
- Health Insurance Portability and Accountability Act (HIPAA) Security and Privacy Rules.
- OWASP Top 10 Web Application Security Risks.

---

## 2. Overall Description

### 2.1 Product Perspective
SahayID is an independent, responsive web application operating in dual runtime environments (local development via SQLite, production via Supabase PostgreSQL on Vercel Serverless).

```
┌─────────────────────────────────────────────────────────────┐
│                    SahayID Client Layers                    │
│   Desktop Web / Mobile Web / PWA Standalone Mobile Client   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / TLS 1.3
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Flask Application Server / WSGI               │
│   - Route Controllers & Jinja2 Templates                    │
│   - Cryptographic Hashing (scrypt, SHA-256)                 │
│   - Session Manager & Defensive Security Middleware         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Dual Database Layer (SQLite / PostgreSQL)          │
│   - Users & Medical Profiles                                │
│   - Emergency Contacts & Doctors Directory                  │
│   - Access Requests, Ephemeral Tokens & Audit Logs          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 User Classes & Personas
1. **Patient:** Individuals managing their personal emergency vitals, generating printable QR badges, and authorizing doctor access via OTP.
2. **Physician / Clinician:** Licensed medical doctors who search patients, initiate OTP consent requests, view clinical records, and perform emergency triage.
3. **Emergency Responder / Paramedic:** Field responders who scan physical badges during acute crises and execute the Break-Glass protocol.
4. **System Administrator:** Healthcare compliance officers who review doctor registrations, verify medical licenses, and audit access logs.

### 2.3 Operating Environment
- **Server Environment:** Python 3.10+, Flask 3.x, Gunicorn (Linux/Containers) / Vercel Python Serverless.
- **Database Backend:** SQLite 3 (Development/Testing) and PostgreSQL 15+ via Supabase Pooler (Production).
- **Client Platforms:** Modern web browsers (Chrome, Edge, Safari, Firefox, Opera) on iOS, Android, macOS, Windows, Linux.

### 2.4 Design & Implementation Constraints
- Zero clinical or personal data may be stored in plain text inside QR code payloads.
- Master administrator passwords must never be hardcoded in repository files and must strictly resolve from environment variables.
- Ephemeral tokens must strictly expire after their configured TTLs (15 minutes for Break-Glass, 30 minutes for Doctor OTP sessions).

---

## 3. Specific System Requirements

### 3.1 User Interfaces & Authentication
- **REQ-UI-01 (Full-Page Healthcare Background):** All 5 authentication views (`login.html`, `register.html`, `doctor_login.html`, `doctor_register.html`, `admin_login.html`) shall render a full-page healthcare team background with a left-aligned frosted-glass auth card.
- **REQ-UI-02 (Branded Identity Header):** Every authentication card shall display the SahayID logo, brand name, and the tagline *"Secure medical access, when it matters most."*
- **REQ-UI-03 (Theme Toggle):** The application shall support persistent Light and Dark themes stored in `localStorage`.

### 3.2 Patient Management Requirements (FR-PAT)
- **FR-PAT-01 (Registration):** The system shall allow patients to register with Full Name, Email, Phone, and Password, automatically generating a unique `MED-XXXXXXXX` identifier.
- **FR-PAT-02 (Medical Profile):** Patients shall be able to edit Date of Birth, Gender, Blood Group, Drug Allergies, Medical Conditions, Current Medications, and Previous Surgeries.
- **FR-PAT-03 (Emergency Contacts):** Patients shall be able to add, view, and delete prioritized emergency contacts with name, relationship, and telephone number.
- **FR-PAT-04 (Portrait Photo):** Patients shall be able to upload a portrait image (Base64 data URI) or capture a photo via their device camera.
- **FR-PAT-05 (Audit Trail Visibility):** Patients shall have real-time visibility into all access logs recording who viewed their record, the access type (`LOGIN`, `DOCTOR_ACCESS`, `EMERGENCY_ACCESS`), timestamp, and reason.

### 3.3 Physician Management Requirements (FR-DOC)
- **FR-DOC-01 (Registration):** Doctors shall register with Full Name, Institutional Email, Phone, Specialization, Hospital/Clinic Name, License Number, and Password.
- **FR-DOC-02 (Pending State):** Newly registered doctors shall immediately enter `verification_status = 'pending'`, restricting clinical search until administrative approval.
- **FR-DOC-03 (Patient Search):** Verified doctors shall be able to look up patients via their exact `MED-XXXXXXXX` identifier or camera QR scanner.
- **FR-DOC-04 (Access Request):** Doctors shall initiate OTP access requests, generating an unguessable request token and awaiting patient OTP submission.

### 3.4 One-Time Password (OTP) Consent Engine (FR-OTP)
- **FR-OTP-01 (Generation):** When an access request is initiated, the system shall generate a secure 6-digit numeric OTP and store its SHA-256 hash with a 5-minute TTL.
- **FR-OTP-02 (Display):** The patient dashboard shall surface the active OTP in a high-visibility broadcast banner.
- **FR-OTP-03 (Verification):** The doctor shall enter the OTP at `/doctor/verify-otp/<token>`. Upon successful match, an authorization window of 30 minutes is granted.
- **FR-OTP-04 (Brute-Force Guard):** The request token shall be permanently invalidated after 3 incorrect OTP attempts.

### 3.5 Emergency Break-Glass Protocol (FR-EMG)
- **FR-EMG-01 (Privacy Gate):** The initial QR scan endpoint (`/emergency/<medi_id>`) shall withhold all clinical information until emergency verification is submitted.
- **FR-EMG-02 (Responder Capture):** Responders must input their Full Name, Organization, Clinical Justification, and check the mandatory legal emergency declaration.
- **FR-EMG-03 (Ephemeral Token):** Upon submission, the system shall generate a 64-character URL-safe token, store its SHA-256 hash in `emergency_access`, and redirect to `/emergency/view/<token>`.
- **FR-EMG-04 (Critical Tier Display):** The triage view shall display Blood Group, Critical Allergies, Medications, and Emergency Contacts with a live 15-minute countdown timer.
- **FR-EMG-05 (Expiry Enforcement):** Requests to view expired tokens shall be rejected with HTTP 403 Forbidden.

### 3.6 Administrative Portal Requirements (FR-ADM)
- **FR-ADM-01 (Protected Route):** Administrative login shall be accessible strictly at `/admin/login` and omitted from public navigation menus.
- **FR-ADM-02 (Environment Authentication):** Admin sign-in shall validate credentials against `ADMIN_USERNAME`/`ADMIN_EMAIL` and `ADMIN_PASSWORD`.
- **FR-ADM-03 (Doctor Approval):** Administrators shall review pending doctors and approve them (`verification_status = 'verified'`), creating a `DOCTOR_APPROVED` audit event.
- **FR-ADM-04 (Doctor Rejection):** Administrators shall be able to reject doctors with a mandatory written justification, setting `verification_status = 'rejected'` and logging `DOCTOR_REJECTED`.

---

## 4. Non-Functional Requirements (NFR)

### 4.1 Security & Privacy (NFR-SEC)
- **NFR-SEC-01:** Passwords shall be hashed using Werkzeug's `scrypt` with cryptographic salt.
- **NFR-SEC-02:** All HTTP responses shall include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **NFR-SEC-03:** Session cookies shall enforce `HttpOnly`, `SameSite=Lax`, and `Secure` on production deployments.
- **NFR-SEC-04:** QR codes shall contain zero medical bytes.

### 4.2 Performance & Scalability (NFR-PERF)
- **NFR-PERF-01:** QR image generation via `/qr/<medi_id>.png` shall return in under 150ms.
- **NFR-PERF-02:** Emergency triage payload delivery shall complete within 250ms under typical 4G mobile conditions.

### 4.3 Reliability & Availability (NFR-REL)
- **NFR-REL-01:** In the absence of `ADMIN_PASSWORD`, administrative routes shall fail securely (HTTP 503) without exposing default credentials.
- **NFR-REL-02:** Database connections shall support automatic failover and reconnect via connection pooling.

---

## 5. Verification Matrix

| Req ID | Requirement Summary | Verification Method | Automated Test Suite |
| :--- | :--- | :--- | :--- |
| **FR-PAT-01** | Patient registration & SahayID assignment | Integration Test | `test_authentication.py` |
| **FR-PAT-02** | Medical profile updates & persistence | Integration Test | `test_patient_access.py` |
| **FR-DOC-02** | Doctor verification gating | Integration Test | `test_roles.py`, `test_admin.py` |
| **FR-OTP-01** | SHA-256 hashed OTP consent | Unit / Integration Test | `test_consent_otp.py` |
| **FR-EMG-01** | Zero-knowledge emergency privacy gate | Integration Test | `test_emergency_access.py` |
| **FR-EMG-03** | 15-minute ephemeral token lifecycle | Integration Test | `test_break_glass_and_production.py` |
| **FR-ADM-02** | Environment-based admin authentication | Integration Test | `test_admin.py` |
| **NFR-SEC-04** | QR payload zero medical data | Security Audit Test | `test_qr.py` |
