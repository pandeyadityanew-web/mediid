"""
seed_demo.py - SahayID Fictional Demo Patient and Doctor Seeder

Populates presentation-ready fictional demo data:
1. Patient Profile:
   - Patient Name: Alex Sharma
   - SahayID Number: MED-DEMO2026
   - Email: alex.demo@mediid.local
   - Password: DemoPass123!
   - Blood Group: O+
   - Critical Allergies: Penicillin, Peanuts
   - Emergency Contact: Priya Sharma

2. Doctor Profile (Verified):
   - Doctor Name: Dr. Arjun Mehta
   - Doctor ID: DOC-DEMO2026
   - Specialization: Emergency Medicine
   - Hospital: Sahay General Hospital
   - Registration Number: DEMO-MED-2026
   - Email: doctor@sahayid.demo
   - Password: DemoDoctor123!
   - Verification Status: verified

Academic / Prototype Note: Real medical council verification is not performed. All identities are fictional.
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash
import qrcode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'database')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'medid.db')
QR_DIR = os.path.join(BASE_DIR, 'static', 'generated_qr')


def seed_demo_data():
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(QR_DIR, exist_ok=True)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # -------------------------------------------------------------
    # 1. Seed Fictional Patient: Alex Sharma
    # -------------------------------------------------------------
    medi_id = "MED-DEMO2026"
    full_name = "Alex Sharma"
    patient_email = "alex.demo@mediid.local"
    patient_phone = "+1-555-019-2834"
    patient_password = "DemoPass123!"
    patient_hash = generate_password_hash(patient_password)

    # Clean up prior demo patient record if exists
    cursor.execute("SELECT id FROM users WHERE medi_id = ? OR email = ?", (medi_id, patient_email))
    existing_patient = cursor.fetchone()
    if existing_patient:
        cursor.execute("DELETE FROM users WHERE id = ?", (existing_patient[0],))
        conn.commit()

    # Insert Patient User
    cursor.execute("""
        INSERT INTO users (medi_id, full_name, email, phone, password_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (medi_id, full_name, patient_email, patient_phone, patient_hash))
    user_id = cursor.lastrowid

    # Insert Medical Profile
    cursor.execute("""
        INSERT INTO medical_profiles (
            user_id, date_of_birth, gender, blood_group,
            allergies, medical_conditions, current_medications,
            previous_surgeries, additional_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        "1995-04-12",
        "Male",
        "O+",
        "Penicillin (severe anaphylaxis), Peanuts",
        "Asthma, Mild Hypertension",
        "Salbutamol Inhaler (100mcg as needed), Cetirizine 10mg",
        "Appendectomy (2019)",
        "Carries emergency EpiPen in backpack. Registered organ donor."
    ))

    # Insert Emergency Contacts
    contacts = [
        ("Priya Sharma", "Spouse", "+1-555-019-9944"),
        ("Dr. Robert Vance", "Primary Care Physician", "+1-555-012-3456")
    ]
    cursor.executemany("""
        INSERT INTO emergency_contacts (user_id, name, relationship, phone)
        VALUES (?, ?, ?, ?)
    """, [(user_id, name, rel, phone) for name, rel, phone in contacts])

    # -------------------------------------------------------------
    # 2. Seed Fictional Doctor: Dr. Arjun Mehta
    # -------------------------------------------------------------
    doctor_id = "DOC-DEMO2026"
    doc_name = "Dr. Arjun Mehta"
    doc_email = "doctor@sahayid.demo"
    doc_phone = "+1-555-019-7722"
    doc_specialization = "Emergency Medicine"
    doc_hospital = "Sahay General Hospital"
    doc_reg_number = "DEMO-MED-2026"
    doc_password = "DemoDoctor123!"
    doc_hash = generate_password_hash(doc_password)

    # Clean up prior demo doctor record if exists
    cursor.execute("SELECT id FROM doctors WHERE doctor_id = ? OR email = ?", (doctor_id, doc_email))
    existing_doc = cursor.fetchone()
    if existing_doc:
        cursor.execute("DELETE FROM doctors WHERE id = ?", (existing_doc[0],))
        conn.commit()

    # Insert Doctor
    cursor.execute("""
        INSERT INTO doctors (
            doctor_id, full_name, email, phone, password_hash,
            specialization, hospital_or_clinic, registration_number, verification_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified')
    """, (doctor_id, doc_name, doc_email, doc_phone, doc_hash, doc_specialization, doc_hospital, doc_reg_number))
    doc_db_id = cursor.lastrowid

    # -------------------------------------------------------------
    # 3. Seed Demonstrative Access History (Doctor & Patient)
    # -------------------------------------------------------------
    cursor.execute("""
        INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
        VALUES (?, ?, 'DOCTOR', ?, ?, 'Emergency Trauma Evaluation', 'DOCTOR_ACCESS', '127.0.0.1')
    """, (user_id, doc_db_id, doc_name, doc_hospital))

    conn.commit()
    conn.close()

    # -------------------------------------------------------------
    # 4. Generate Pre-built QR Code for Demo Patient
    # -------------------------------------------------------------
    base_url = os.environ.get('BASE_URL', 'http://127.0.0.1:5000').rstrip('/')
    emergency_url = f"{base_url}/emergency/{medi_id}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(emergency_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    qr_file = os.path.join(QR_DIR, f"{medi_id}.png")
    img.save(qr_file)

    print("=" * 68)
    print(" SahayID Fictional Demo Patient & Doctor Seeded Successfully")
    print("=" * 68)
    print(" PATIENT ACCOUNT:")
    print(f"   Name:             {full_name}")
    print(f"   SahayID Number:   {medi_id}")
    print(f"   Login Email:      {patient_email}")
    print(f"   Login Password:   {patient_password}")
    print(f"   Blood Group:      O+")
    print(f"   Emergency Contact:Priya Sharma (+1-555-019-9944)")
    print(f"   QR Code File:     {qr_file}")
    print("-" * 68)
    print(" VERIFIED DOCTOR ACCOUNT:")
    print(f"   Name:             {doc_name}")
    print(f"   Doctor ID:        {doctor_id}")
    print(f"   Login Email:      {doc_email}")
    print(f"   Login Password:   {doc_password}")
    print(f"   Specialization:   {doc_specialization}")
    print(f"   Hospital:         {doc_hospital}")
    print(f"   Registration No:  {doc_reg_number}")
    print(f"   Status:           VERIFIED")
    print("=" * 68)


if __name__ == '__main__':
    seed_demo_data()
