"""
seed_demo.py - MediID Fictional Demo Patient Seeder

Creates or refreshes a presentation-ready fictional patient profile:
- Patient: Alex Sharma
- MediID: MED-DEMO2026
- Email: alex.demo@mediid.local
- Password: DemoPass123!
- Blood Group: O+
- Critical Allergies: Penicillin, Peanuts
- Emergency Contact: Priya Sharma
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

    # Demo Patient Details
    medi_id = "MED-DEMO2026"
    full_name = "Alex Sharma"
    email = "alex.demo@mediid.local"
    phone = "+1-555-019-2834"
    password = "DemoPass123!"
    password_hash = generate_password_hash(password)

    # 1. Clean up prior demo record if exists
    cursor.execute("SELECT id FROM users WHERE medi_id = ? OR email = ?", (medi_id, email))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("DELETE FROM users WHERE id = ?", (existing[0],))
        conn.commit()

    # 2. Insert User
    cursor.execute("""
        INSERT INTO users (medi_id, full_name, email, phone, password_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (medi_id, full_name, email, phone, password_hash))
    user_id = cursor.lastrowid

    # 3. Insert Medical Profile
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

    # 4. Insert Emergency Contacts
    contacts = [
        ("Priya Sharma", "Spouse", "+1-555-019-9944"),
        ("Dr. Robert Vance", "Primary Care Physician", "+1-555-012-3456")
    ]
    cursor.executemany("""
        INSERT INTO emergency_contacts (user_id, name, relationship, phone)
        VALUES (?, ?, ?, ?)
    """, [(user_id, name, rel, phone) for name, rel, phone in contacts])

    # 5. Insert Access Log Sample
    cursor.execute("""
        INSERT INTO access_logs (user_id, access_type, ip_address)
        VALUES (?, 'PATIENT_LOGIN', '127.0.0.1')
    """, (user_id,))

    conn.commit()
    conn.close()

    # 6. Generate QR code
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

    print("=" * 60)
    print("MediID Demo Patient Seeded Successfully!")
    print("=" * 60)
    print(f"Patient Name:       {full_name}")
    print(f"MediID:             {medi_id}")
    print(f"Login Email:        {email}")
    print(f"Login Password:     {password}")
    print(f"Blood Group:        O+")
    print(f"Allergies:          Penicillin, Peanuts")
    print(f"Emergency Contacts: Priya Sharma (+1-555-019-9944)")
    print(f"Emergency URL:      {emergency_url}")
    print(f"QR Code Path:       {qr_file}")
    print("=" * 60)


if __name__ == '__main__':
    seed_demo_data()
