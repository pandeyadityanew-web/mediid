# Contributing to SahayID

Thank you for your interest in contributing to SahayID! This guide outlines development practices, code standards, and test verification workflows.

---

## 1. Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/pandeyadityanew-web/mediid.git
   cd mediid
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables (`.env`):**
   ```env
   SECRET_KEY=your_local_secret_key
   ADMIN_PASSWORD=YourLocalAdminPassword!
   ```

4. **Seed demo data (Optional):**
   ```bash
   python seed_demo.py
   ```

5. **Start the Flask development server:**
   ```bash
   python app.py
   ```
   Open `http://127.0.0.1:5000` in your browser.

---

## 2. Test Verification

Before submitting code changes, verify that all test suites pass without regression:

```bash
python test_admin.py
python test_authentication.py
python test_break_glass_and_production.py
python test_consent_otp.py
python test_doctor_access.py
python test_emergency_access.py
python test_integration.py
python test_new_features.py
python test_patient_access.py
python test_qr.py
python test_roles.py
```

---

## 3. Code & Design Guidelines

- **Privacy First:** Never embed patient health records, names, or contact numbers in QR code payloads.
- **Security by Default:** Never commit production passwords or API keys to git. Secrets must always resolve from environment variables.
- **Role Isolation:** Maintain strict separation between patient (`/dashboard`), physician (`/doctor`), and administrative (`/admin`) sessions.
- **Microcopy & Accessibility:** Preserve semantic headings, ARIA attributes, and accessible color contrast.
