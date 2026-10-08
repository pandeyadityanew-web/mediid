# SahayID Security Architecture & Endpoint Specification

SahayID incorporates defensive security protocols across authentication, data transport, access delegation, and database operations.

---

## 1. Cryptographic Safeguards

### Password Hashing
- **Algorithm:** Werkzeug `generate_password_hash` utilizing `scrypt` with cryptographic salt.
- **Complexity:** Minimum 8 characters enforced for patient and doctor signups.
- **Admin Passwords:** Loaded dynamically via environment variables (`ADMIN_PASSWORD`), never hardcoded in repository files.

### One-Time Password (OTP) Consent Engine
- **Entropy:** 6-digit cryptographically secure numeric codes (`secrets.randbelow(900000) + 100000`).
- **Storage:** OTPs are never stored in plaintext within the database. They are hashed using SHA-256 before insertion into `access_requests`.
- **TTL (Time To Live):** 5 minutes from initiation.
- **Brute-Force Guard:** Maximum 3 verification attempts before the request token is permanently invalidated.
- **Session Duration:** Once confirmed by the patient's OTP, clinical authorization is valid for a maximum window of 30 minutes.

### Emergency Ephemeral Tokens
- **Generation:** 64-character URL-safe random string (`secrets.token_urlsafe(32)`).
- **Storage:** Hashed with SHA-256 (`hashlib.sha256`) prior to storage in `emergency_access`.
- **Validity:** 15 minutes TTL for emergency responder review, after which the token expires and returns HTTP 403 Forbidden.

---

## 2. HTTP Defensive Headers & Middleware

All responses processed by the SahayID Flask backend automatically include the following defensive HTTP headers:

| Header | Value | Purpose |
| :--- | :--- | :--- |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing attacks. |
| `X-Frame-Options` | `DENY` | Prevents clickjacking by blocking iframe embedding. |
| `X-XSS-Protection` | `1; mode=block` | Activates legacy browser XSS filters. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Protects patient URLs and IDs in outbound referrers. |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforces HTTPS on production deployments. |

---

## 3. Key API Endpoints & Routes

### Public Endpoints
- `GET /`: Landing page, feature breakdown, role selector modal, and FAQs.
- `GET /faqs`: Comprehensive medical identity and platform knowledge base.
- `GET /manifest.json`: Web App Manifest for native PWA installation.
- `GET /sw.js`: Service Worker for offline asset caching.
- `GET /qr/<medi_id>.png`: Dynamic PNG stream for scannable QR badge.

### Patient Portal (`/dashboard`)
- `GET, POST /register`: Patient registration and automatic SahayID assignment.
- `GET, POST /login`: Patient sign-in via Email or SahayID number.
- `GET /dashboard`: Main patient portal, vitals summary, and scannable QR badge.
- `POST /update-profile`: Update medical vitals, blood group, allergies, and medications.
- `POST /add-emergency-contact`: Add prioritized next-of-kin contacts.
- `POST /delete-emergency-contact/<id>`: Delete personal emergency contact.
- `POST /upload-photo` & `POST /remove-photo`: Upload / clear patient portrait photo.
- `GET /download-qr`: Download scannable QR code PNG image.

### Doctor Portal (`/doctor`)
- `GET, POST /doctor/register`: Physician onboarding with institutional credentials.
- `GET, POST /doctor/login`: Physician portal login via Doctor ID or professional email.
- `GET /doctor/dashboard`: Doctor portal, patient search bar, and QR scanner interface.
- `GET, POST /doctor/profile`: Physician profile editing and portrait photo management.
- `POST /doctor/request-access`: Initiate 6-digit OTP clinical access request for a patient.
- `GET, POST /doctor/verify-otp/<token>`: Verify patient's OTP and unlock clinical record.
- `GET /doctor/patient/<medi_id>`: View authorized patient record within the 30-minute window.

### Emergency Gateway (`/emergency`)
- `GET /emergency/<medi_id>`: Emergency landing page displaying responder notice (no medical data).
- `POST /emergency/<medi_id>`: Submit responder identity and legal acknowledgment.
- `GET /emergency/view/<token>`: View critical emergency vitals (valid for 15 minutes).

### Administrative Gateway (`/admin`)
- `GET, POST /admin/login`: Administrator sign-in (unlisted in public navigation).
- `GET /admin`: Administrator dashboard, pending doctor queue, verified doctors, and audit trail.
- `POST /admin/doctor/<id>/approve`: Verify and approve a doctor's credentials.
- `POST /admin/doctor/<id>/reject`: Reject a doctor's registration with required reason.
- `GET /logout`: Terminate session and clear all authentication cookies.
