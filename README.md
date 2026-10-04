# MediID - Digital Medical Identity System

**"Your Medical Identity. Available When It Matters."**

MediID is a privacy-focused digital medical identity web application. It enables patients to store essential medical information (such as blood group, allergies, medications, and emergency contacts) and generate a unique MediID with a QR code designed for fast, frictionless emergency access.

---

## 📌 Features Overview (Parts 1, 2, 3, 4 & 5)

- **Flask Backend & Application Architecture**:
  - Modular routing and application context handling.
  - Automatic SQLite database creation and table initialization.
  - Explicit SQLite foreign key enforcement on every connection.
  - Parameterized SQL queries preventing SQL injection vulnerabilities.
  - Route protection decorator (`@login_required`) guarding all private patient endpoints.
- **Cryptographic Security & Privacy**:
  - Secure password hashing using Werkzeug (`generate_password_hash` / `check_password_hash`).
  - Cryptographically random MediID generator producing unique identifiers formatted as `MED-XXXXXXXX`.
  - Session-based user authentication.
  - Strict ownership authorization checks preventing unauthorized modification or cross-user deletion.
  - No passwords or medical information in server console logs or query parameters.
- **Emergency Access & Verification System (Part 5)**:
  - **End-to-End Emergency Flow**:
    `QR Scan` &rarr; `Emergency Gateway (/emergency/<medi_id>)` &rarr; `Verification Protocol (/emergency/<medi_id>/verify)` &rarr; `Time-Limited Token View (/emergency/access/<token>)` &rarr; `Audit Logged`.
  - **Cryptographic Access Token**: Temporary URL-safe token generated via `secrets.token_urlsafe(32)`.
  - **Zero Raw Token Storage**: The server stores strictly the **SHA-256 hash** of the token in the `emergency_access` table.
  - **Server-Side 10-Minute Expiry**: Tokens are strictly invalid after 10 minutes (returns HTTP 403; zero clinical information leaked upon expiration).
  - **Zero Health Data in URLs**: URLs contain solely random tokens (`/emergency/access/<token>`).
  - **Abuse Protection / Rate Limiting**: Maximum 5 emergency access requests per 10 minutes per MediID.
  - **Audit Logging**: Every emergency scan logs `EMERGENCY_SCAN`, and every verified access logs `EMERGENCY_ACCESS` in `access_logs`.
  - **Emergency Access History on Dashboard**: Patients can view all responders, organizations, reasons, timestamps, and active/expired statuses directly in their dashboard.
- **MediID QR Code Generation System**:
  - **Zero-Medical-Data QR Payload**: The QR code strictly encodes the emergency gateway URL (`http://127.0.0.1:5000/emergency/<medi_id>`). It does NOT embed any personal or clinical information.
  - **Automatic Generation**: Generated automatically upon patient registration and saved as high-contrast PNG in `static/generated_qr/<medi_id>.png`.
  - **Download QR (`/download-qr`)**: Secure attachment download restricted strictly to the authenticated user's session ID.
  - **Print MediID Card**: Physical wallet-sized medical emergency ID card formatted with browser `@media print` support.
- **Patient Dashboard & Health Profile**:
  - **Dashboard (`/dashboard`)**: Patient details, MediID chip, dynamic profile completion percentage (8 criteria), medical overview, emergency contacts summary, emergency ID card, and emergency access audit history.
  - **Medical Profile (`/medical-profile`)**: Form for updating vitals, blood type, allergies, conditions, and medications.
  - **Emergency Contacts (`/emergency-contacts`)**: Add, view, and securely delete emergency contacts.

---

## 📂 Project Structure

```
mediid/
├── app.py                      # Flask application, DB schema, auth, portal & emergency access routes
├── requirements.txt            # Python dependency declarations (Flask, qrcode[pil])
├── test_verification.py        # Part 2 automated test suite (schema, auth, hashing)
├── test_part3.py               # Part 3 automated test suite (dashboard, profile, ownership)
├── test_part4.py               # Part 4 automated test suite (QR generation, download, gateway)
├── test_part5.py               # Part 5 automated test suite (Emergency access, tokens, expiration, audit)
├── database/
│   └── medid.db                # SQLite database file for local development
├── templates/
│   ├── index.html              # Landing page template (session-aware)
│   ├── login.html              # User login template
│   ├── register.html           # Patient registration template
│   ├── dashboard.html          # Patient dashboard with scannable QR, card & access audit history
│   ├── medical_profile.html    # Medical profile editing form
│   ├── emergency_contacts.html # Emergency contacts management and deletion
│   ├── emergency_access.html   # First responder scanned gateway (privacy-guarded)
│   ├── emergency_verify.html   # Emergency verification & confirmation form
│   └── emergency_information.html # Verified emergency clinical view (time-limited)
├── static/
│   ├── css/
│   │   └── style.css           # Healthcare design system & print stylesheet
│   ├── js/
│   │   └── script.js           # Client-side scripts and mobile navigation
│   └── generated_qr/           # Directory holding generated PNG QR codes
└── README.md                   # Project documentation and guide
```

---

## 🗄️ Database Schema Details

### 1. `users`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique user identifier |
| `medi_id` | TEXT | UNIQUE NOT NULL | Random alphanumeric ID (`MED-XXXXXXXX`) |
| `full_name` | TEXT | NOT NULL | Patient's full name |
| `email` | TEXT | UNIQUE NOT NULL | Normalized email address |
| `phone` | TEXT | | Contact phone number |
| `password_hash` | TEXT | NOT NULL | Werkzeug-hashed password |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Registration timestamp |

### 2. `medical_profiles`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Profile ID |
| `user_id` | INTEGER | NOT NULL, FK &rarr; `users.id` | Associated patient |
| `date_of_birth` | TEXT | | Birthdate |
| `gender` | TEXT | | Gender |
| `blood_group` | TEXT | | e.g., O+, A-, B+, etc. |
| `allergies` | TEXT | | Drug & food allergies |
| `medical_conditions` | TEXT | | Chronic/acute conditions |
| `current_medications` | TEXT | | Active prescriptions |
| `previous_surgeries` | TEXT | | Surgical history |
| `additional_notes` | TEXT | | Special clinical directions |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last updated timestamp |

### 3. `emergency_contacts`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Contact ID |
| `user_id` | INTEGER | NOT NULL, FK &rarr; `users.id` | Associated patient |
| `name` | TEXT | NOT NULL | Contact full name |
| `relationship` | TEXT | | Relationship (e.g. Spouse) |
| `phone` | TEXT | NOT NULL | Contact telephone |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

### 4. `access_logs`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Log entry ID |
| `user_id` | INTEGER | NOT NULL, FK &rarr; `users.id` | User accessing profile |
| `access_type` | TEXT | NOT NULL | Access event (`LOGIN`, `EMERGENCY_SCAN`, `EMERGENCY_ACCESS`) |
| `accessed_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Event timestamp |
| `ip_address` | TEXT | | Client IP address |

### 5. `emergency_access` (Part 5)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Access authorization ID |
| `user_id` | INTEGER | NOT NULL, FK &rarr; `users.id` | Patient whose profile was accessed |
| `token_hash` | TEXT | NOT NULL UNIQUE | SHA-256 hash of temporary token |
| `responder_name` | TEXT | NOT NULL | Name of responder / doctor |
| `organization` | TEXT | | Hospital / EMS facility |
| `reason` | TEXT | NOT NULL | Clinical emergency reason |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Request timestamp |
| `expires_at` | TIMESTAMP | NOT NULL | Expiry timestamp (created_at + 10 mins) |
| `accessed_at` | TIMESTAMP | | First access timestamp |
| `ip_address` | TEXT | | Responder network IP address |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.8+** installed on your system.

### 2. Navigate to the Project Directory
```bash
cd C:\Users\pande\.gemini\antigravity\scratch\mediid
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Run the Complete Automated Verification Test Suites
```bash
python test_verification.py   # Part 2 tests (schema, auth, hashing)
python test_part3.py          # Part 3 tests (dashboard, profile, ownership)
python test_part4.py          # Part 4 tests (QR generation, download protection)
python test_part5.py          # Part 5 tests (Emergency access, tokens, expiration, audit)
```

### 5. Start the Flask Application
```bash
python app.py
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Testing Checklist for Part 5

1. **Emergency Verification Access**: Visit `http://127.0.0.1:5000/emergency/<medi_id>/verify`. Confirm the form requires responder name, reason, and emergency confirmation.
2. **Token Generation**: Submit the verification form. Notice redirection to `/emergency/access/<secure_random_token>`.
3. **Database Token Security**: Check the database; confirm only the **SHA-256 hash** is stored in `emergency_access`, never the raw token.
4. **Emergency Clinical Record**: Observe the clinical view displaying blood type, allergies, conditions, medications, next-of-kin contacts, and responder audit metadata. Confirm password, email, and database IDs are not exposed.
5. **Token Expiration**: Wait 10 minutes (or advance the token expiry time). Verify the page returns HTTP 403 *"Emergency access has expired"* and displays zero medical data.
6. **Patient Audit Log**: Log into the patient account and open `/dashboard`. The **Emergency Access Audit History** table will display the responder's name, organization, reason, IP, timestamp, and status.
