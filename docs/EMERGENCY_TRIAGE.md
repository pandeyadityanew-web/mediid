# SahayID Emergency Triage & Break-Glass Protocol

In critical emergencies where a patient is unconscious, incapacitated, or unable to provide a 6-digit OTP, SahayID features an audited **Break-Glass Emergency Protocol**.

---

## 1. Zero-Exposure Emergency Scan

When a bystander, paramedic, or ER doctor scans a patient's physical badge QR code or enters their SahayID number:

1. The browser requests `GET /emergency/<medi_id>`.
2. **Zero-Knowledge Privacy Gate:** The initial landing page does **not** display any medical records, diagnoses, or contact information.
3. The page presents a clear emergency disclaimer:
   - Warning that all access events are cryptographically audited and timestamped.
   - Requirement to provide the responder's full name, organization (e.g. *Metro EMS, Memorial ER*), and clinical reason for access.
   - Mandatory legal confirmation checkbox certifying life-critical emergency triage.

```
┌──────────────────────────────────────────────────────────┐
│                   SahayID Physical Badge                 │
│                 [Zero-Knowledge QR Code]                 │
└────────────────────────────┬─────────────────────────────┘
                             │ Scan
                             ▼
┌──────────────────────────────────────────────────────────┐
│              Emergency Gateway (/emergency/MED-XXX)      │
│  - No medical information shown                          │
│  - Responder Name & Hospital / EMS Agency required       │
│  - Clinical Reason & Legal Declaration required          │
└────────────────────────────┬─────────────────────────────┘
                             │ Submit
                             ▼
┌──────────────────────────────────────────────────────────┐
│              Ephemeral Access Token Generated            │
│  - 64-character URL-safe cryptographic token             │
│  - SHA-256 hash stored in database                       │
│  - Time To Live: 15 Minutes                              │
│  - Immediate log written to access_logs (EMERGENCY_ACCESS)│
└────────────────────────────┬─────────────────────────────┘
                             │ Redirect
                             ▼
┌──────────────────────────────────────────────────────────┐
│              Critical Triage Record View                 │
│  - Blood Group & Critical Allergies                      │
│  - Current Medications & Emergency Contacts (Direct Call)│
│  - Visual 15-Minute Countdown Timer                      │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Emergency Ephemeral Access Token Lifecycle

- **Token Format:** `secrets.token_urlsafe(32)`
- **Database Storage:** Stored strictly as SHA-256 hash in `emergency_access.token_hash`.
- **TTL Duration:** 15 minutes (`datetime.utcnow() + timedelta(minutes=15)`).
- **Post-Expiry:** Requests made after expiration immediately receive HTTP 403 Forbidden.

---

## 3. Transparency & Patient Notification

Every emergency access event is recorded with:
- Timestamp (UTC)
- Responder Full Name
- Organization / Hospital / EMS Unit
- Stated Clinical Justification
- Client IP Address

When the patient logs into their SahayID dashboard, the emergency event is surfaced prominently in their **Access History & Audit Trail**, ensuring total transparency against unauthorized misuse.
