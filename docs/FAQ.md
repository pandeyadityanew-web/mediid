# SahayID Knowledge Base & Frequently Asked Questions (FAQs)

Comprehensive answers regarding SahayID's privacy model, doctor verification, emergency break-glass triage, and identity badge generation.

---

### Q1: What is SahayID and how does it work?
SahayID is a privacy-first digital medical identity system designed to solve two competing healthcare challenges:
1. Enabling immediate access to critical medical data (allergies, blood type, emergency contacts) in life-threatening situations.
2. Protecting patient privacy during routine consultations through audited, patient-controlled One-Time Password (OTP) authorization.

---

### Q2: What is Zero-Knowledge QR Code technology?
Standard medical QR badges embed names, diagnoses, and medical histories directly into the QR code matrix. If photographed or lost, anyone can extract the holder's medical background.

SahayID utilizes **Zero-Knowledge QR Routing**: the QR code embeds strictly a secure HTTPS routing URL (`https://sahayid.app/emergency/MED-XXXXXXXX`). No health data or personal identifiers are stored in the QR image itself.

---

### Q3: How does doctor consent verification work?
When consulting an authorized physician:
1. The physician searches for your SahayID or scans your physical badge.
2. The physician initiates an access request, prompting SahayID to generate a 6-digit numeric OTP.
3. You provide the OTP displayed on your patient dashboard.
4. Once verified, the physician receives a 30-minute authorized window to view your medical history.
5. All access details are permanently recorded in your dashboard audit log.

---

### Q4: How does Emergency Break-Glass access function?
In an emergency where a patient is unconscious:
1. Paramedics or ER clinicians scan the patient's SahayID badge.
2. The responder must provide their full name, medical agency/hospital, and clinical reason.
3. Upon signing the legal emergency declaration, a 15-minute ephemeral access token is generated to display blood type, allergies, current medications, and prioritized emergency contacts.
4. An unalterable `EMERGENCY_ACCESS` log entry is immediately created.

---

### Q5: How are medical doctors verified?
Doctors register with their institutional email, hospital affiliation, medical specialization, and registration/license number. All accounts are initialized in a `pending` state and must be manually verified and approved by a SahayID administrator (`/admin`) before clinical search tools are unlocked.

---

### Q6: Can I install SahayID on my mobile phone?
Yes. SahayID is a Progressive Web App (PWA). Clicking **"Install App"** in the top navigation activates the browser's native installation prompt on Android, iOS, Windows, macOS, and Linux without downloading from third-party app stores.
