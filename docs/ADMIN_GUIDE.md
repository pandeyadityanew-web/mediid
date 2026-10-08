# SahayID Administrator & Doctor Verification Guide

The SahayID Admin Portal (`/admin`) empowers healthcare network administrators to review medical credentials, approve or reject practitioner accounts, and oversee clinical audit trails.

---

## 1. Accessing the Admin Console

- **Route:** `/admin/login` (intentionally unlisted in public navigation bars).
- **Authentication:** Admin accounts authenticate using either `ADMIN_USERNAME` or `ADMIN_EMAIL` along with the master `ADMIN_PASSWORD`.
- **Environment Configuration:**
  ```env
  ADMIN_USERNAME=admin
  ADMIN_EMAIL=admin@sahayid.org
  ADMIN_NAME="System Administrator"
  ADMIN_PASSWORD=YourStrongProductionMasterPassword!
  ```
- **Security Rule:** If `ADMIN_PASSWORD` is absent from the production environment, administrative login is paused and returns a secure HTTP 503 rather than falling back to default or insecure credentials.

---

## 2. Doctor Onboarding & Verification Workflow

```
┌────────────────────────────────────────────────┐
│   Physician registers at /doctor/register      │
│   - Enters Full Name, Institutional Email      │
│   - Specialization, Hospital, License No.      │
└───────────────────────┬────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────┐
│   Account initialized in 'pending' status      │
│   - Clinical search locked                     │
│   - Banner informs doctor of pending review    │
└───────────────────────┬────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────┐
│   Administrator reviews queue at /admin        │
│   - Inspects license number & hospital details │
└───────────────┬────────────────┬───────────────┘
                │                │
     [Approve]  ▼                ▼  [Reject]
┌────────────────────────┐  ┌────────────────────────┐
│ Status: 'verified'     │  │ Status: 'rejected'     │
│ Full clinical access   │  │ Reason recorded        │
│ Audit: DOCTOR_APPROVED │  │ Audit: DOCTOR_REJECTED │
└────────────────────────┘  └────────────────────────┘
```

---

## 3. Administrative Actions & Audit Event Codes

| Action | Route | Audit Event Code | Notes |
| :--- | :--- | :--- | :--- |
| **Doctor Approval** | `POST /admin/doctor/<id>/approve` | `DOCTOR_APPROVED` | Unlocks full clinical search, OTP access requests, and triage workflows. |
| **Doctor Rejection** | `POST /admin/doctor/<id>/reject` | `DOCTOR_REJECTED` | Requires explanation reason; displays clear feedback banner on doctor dashboard. |
| **Admin Sign-In** | `POST /admin/login` | `ADMIN_LOGIN` | Logs IP and timestamp. |
| **Failed Sign-In** | `POST /admin/login` | `ADMIN_LOGIN_FAILED` | Logs suspicious attempts for intrusion detection. |
