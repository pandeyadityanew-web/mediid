# System Design Document (SDD)
## SahayID: Critical Medical Access Infrastructure

**Document Version:** 2.0  
**Status:** Approved Architecture  
**Author:** SahayID Engineering & Systems Architecture Team  

---

## 1. Design Overview & Core Principles

SahayID is engineered around four core architectural principles:

1. **Zero-Knowledge QR Data Routing:** Physical credentials (badges, cards, wristbands) must never embed unencrypted health data. The QR code acts strictly as an unguessable routing pointer to an audited gateway.
2. **Consent-Gated Clinical Access:** In routine clinical consultations, access to medical records requires bidirectional consent via cryptographic 6-digit One-Time Passwords (OTPs).
3. **Audited Break-Glass Emergency Triage:** In life-threatening emergencies, immediate access to critical vitals is granted via ephemeral tokens (15-minute TTL) with non-repudiable responder identification and legal acknowledgement.
4. **Defense-in-Depth & Fail-Secure Defaults:** All endpoints employ strict role-based gating, cryptographic hashing (scrypt, SHA-256), defensive HTTP headers, and environment-driven master authentication.

---

## 2. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Ecosystem                              │
│  - Desktop Browser / Mobile Safari / Mobile Chrome                      │
│  - Standalone Progressive Web App (PWA)                                 │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTPS (TLS 1.3)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Flask Web Application Tier                        │
│                                                                         │
│  ┌───────────────────────┐ ┌──────────────────────┐ ┌────────────────┐  │
│  │  Authentication Engine│ │ Security Middleware  │ │ Dynamic Assets │  │
│  │  - Patient RBAC       │ │ - HTTP Headers Guard │ │ - QR Streamer  │  │
│  │  - Doctor RBAC        │ │ - Rate-Limit Guard   │ │ - PWA Manifest │  │
│  │  - Admin RBAC         │ │ - Session Encryption │ │ - ServiceWorker│  │
│  └───────────────────────┘ └──────────────────────┘ └────────────────┘  │
│  ┌───────────────────────┐ ┌──────────────────────┐ ┌────────────────┐  │
│  │  OTP Consent Engine   │ │ Break-Glass Engine   │ │ Audit Manager  │  │
│  │  - 6-Digit Generator  │ │ - Ephemeral Tokens   │ │ - Bilateral Log│  │
│  │  - SHA-256 Verifier   │ │ - 15-Min TTL Enforcer│ │ - Access Trails│  │
│  └───────────────────────┘ └──────────────────────┘ └────────────────┘  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Database Abstraction Tier                          │
│                                                                         │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────┐  │
│  │      Local SQLite Backend       │   │  Supabase PostgreSQL Backend│  │
│  │  - Dev & Automated Test Suites  │   │  - Production & SSL Pooler  │  │
│  │  - database/mediid.db           │   │  - Port 6543 (Transaction)  │  │
│  └─────────────────────────────────┘   └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Sequence Diagrams & Interaction Flows

### 3.1 Patient Registration & QR Badge Generation
```
Patient                     Flask Server                  Database
   │                              │                           │
   │─── POST /register ───────────►│                           │
   │    (Name, Email, Pass)       │─── Generate SahayID ─────►│ (Insert users)
   │                              │    (MED-XXXXXXXX)         │ (Insert medical_profiles)
   │                              │                           │
   │◄── Redirect /login ──────────│                           │
   │                              │                           │
   │─── GET /qr/MED-XXXXXXXX.png ─►│                           │
   │                              │─── Encode URL payload ───►│ (No clinical data)
   │◄── Stream image/png ─────────│    (https://.../emergency)│
```

### 3.2 Doctor OTP Consent Handshake
```
Physician                  Flask Server            Patient Dashboard           Database
   │                              │                        │                       │
   │── POST /doctor/request-access►│                        │                       │
   │   (patient_id=MED-XXX)       │─── Create OTP ─────────┼──────────────────────►│ (Insert access_requests)
   │                              │    (6-digit SHA-256)   │                       │ (Status: PENDING)
   │                              │                        │                       │
   │                              │                        │─── Real-time Banner ─►│
   │                              │                        │    "Doctor requesting │
   │                              │                        │     OTP: 492810"      │
   │                              │                        │                       │
   │── Provide OTP to Doctor ────►│                        │                       │
   │── POST /doctor/verify-otp ──►│                        │                       │
   │   (token, otp=492810)        │─── Verify Hash ────────┼──────────────────────►│ (Status: VERIFIED)
   │                              │    & Grant 30-min sess │                       │ (Log: DOCTOR_ACCESS)
   │◄── Render Clinical Profile ──│                        │                       │
```

### 3.3 Emergency Break-Glass Protocol
```
First Responder             Flask Server                  Database
   │                              │                           │
   │─── Scan QR (GET /emergency) ─►│                           │
   │◄── Render Gate (No Data) ────│                           │
   │                              │                           │
   │─── POST /emergency/MED-XXX ──►│                           │
   │    (Responder Name, Hospital,│─── Generate 64-char ─────►│ (Insert emergency_access)
   │     Clinical Reason, Checkbox│    Ephemeral Token        │ (Hash: SHA-256, TTL: 15m)
   │                              │    & Log Access ─────────►│ (Log: EMERGENCY_ACCESS)
   │◄── Redirect /emergency/view ─│                           │
   │                              │                           │
   │─── GET /emergency/view/<tok>─►│─── Verify Expiration ────►│ (Check expires_at > now)
   │◄── Render Triage Vitals ─────│    (Blood Group, Allergy, │
   │    (Live 15-min countdown)   │     Contacts, Medications)│
```

---

## 4. Data Design & Entity Relationships

```
┌─────────────────────────┐        ┌─────────────────────────┐
│          users          │        │    medical_profiles     │
├─────────────────────────┤        ├─────────────────────────┤
│ id (SERIAL / PK)        │───1:1──┤ id (SERIAL / PK)        │
│ medi_id (VARCHAR / UNQ) │        │ user_id (INTEGER / FK)  │
│ full_name (VARCHAR)     │        │ blood_group (VARCHAR)   │
│ email (VARCHAR / UNQ)   │        │ allergies (TEXT)        │
│ phone (VARCHAR)         │        │ medical_conditions (TEXT│
│ password_hash (TEXT)    │        │ current_medications(TEXT│
│ photo_url (TEXT)        │        │ previous_surgeries(TEXT)│
│ created_at (TIMESTAMP)  │        │ updated_at (TIMESTAMP)  │
└────────────┬────────────┘        └─────────────────────────┘
             │
             ├───────────────1:N──────────────┐
             │                                │
             ▼                                ▼
┌─────────────────────────┐        ┌─────────────────────────┐
│   emergency_contacts    │        │       access_logs       │
├─────────────────────────┤        ├─────────────────────────┤
│ id (SERIAL / PK)        │        │ id (SERIAL / PK)        │
│ user_id (INTEGER / FK)  │        │ user_id (INTEGER / FK)  │
│ name (VARCHAR)          │        │ doctor_id (INTEGER / FK)│
│ relationship (VARCHAR)  │        │ actor_type (VARCHAR)    │
│ phone (VARCHAR)         │        │ actor_name (VARCHAR)    │
│ created_at (TIMESTAMP)  │        │ access_type (VARCHAR)   │
└─────────────────────────┘        │ reason (TEXT)           │
                                   │ ip_address (VARCHAR)    │
                                   │ accessed_at (TIMESTAMP) │
                                   └─────────────────────────┘

┌─────────────────────────┐        ┌─────────────────────────┐
│         doctors         │        │     access_requests     │
├─────────────────────────┤        ├─────────────────────────┤
│ id (SERIAL / PK)        │───1:N──┤ id (SERIAL / PK)        │
│ doctor_id (VARCHAR/UNQ) │        │ patient_id (INT / FK)   │
│ full_name (VARCHAR)     │        │ doctor_id (INT / FK)    │
│ email (VARCHAR / UNQ)   │        │ request_token (VARCHAR) │
│ specialization (VARCHAR)│        │ otp_hash (VARCHAR)      │
│ registration_no (VAR)   │        │ status (VARCHAR)        │
│ verification_status(VAR)│        │ attempts (INTEGER)      │
│ photo_url (TEXT)        │        │ expires_at (TIMESTAMP)  │
└─────────────────────────┘        │ authorized_until (TS)   │
                                   └─────────────────────────┘
```

---

## 5. Security & Threat Modeling (STRIDE)

| Threat Category | Potential Risk | SahayID Architectural Mitigation |
| :--- | :--- | :--- |
| **Spoofing** | Unauthorized doctor impersonation. | Mandatory administrative license verification (`verification_status='verified'`) before clinical tools activate. |
| **Tampering** | Modifying another patient's medical vitals. | Strict session authentication validation (`session['user_id'] == profile['user_id']`). |
| **Repudiation** | Denying an emergency record access event. | Permanent immutable record in `access_logs` capturing responder name, agency, justification, IP, and UTC timestamp. |
| **Information Disclosure** | QR code photography or interception. | Zero-knowledge QR payload encoding only routing URLs; no medical data embedded in image bytes. |
| **Denial of Service** | Brute-forcing 6-digit consent OTPs. | Max 3 incorrect attempts before request token is permanently invalidated. |
| **Elevation of Privilege** | Normal user accessing `/admin`. | Dedicated `admin_required` decorator checking `session['role'] == 'admin'` and isolated `admins` table. |

---

## 6. UI & Design System Architecture

- **Color Tokens:**
  - Primary Cyan: `#0284c7` (Hover: `#0369a1`, Light: `#f0f9ff`)
  - Clinical Teal: `#0d9488` (Hover: `#0f766e`, Light: `#f0fdfa`)
  - Emergency Crimson: `#dc2626` (Light: `#fef2f2`, Border: `#fecaca`)
  - Deep Navy Slate: `#071527`, `#0c2340`, `#132f54`
- **Frosted Glass Auth Cards:**
  - `backdrop-filter: blur(16px);`
  - `background: rgba(255, 255, 255, 0.95);` (Dark Mode: `rgba(15, 23, 42, 0.92)`)
  - Subtle multi-layered elevation shadow and left-aligned layout preserving background illustration visibility.
