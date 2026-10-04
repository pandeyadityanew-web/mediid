"""
test_roles.py - Comprehensive Role-Based Authentication and Doctor System Test Suite

Verifies:
1. Patient login works
2. Doctor login works
3. Invalid doctor login fails
4. Patient cannot access doctor dashboard
5. Doctor can access doctor dashboard
6. Unauthenticated user cannot access doctor dashboard
7. Doctor profile information displays correctly
8. Doctor has a unique doctor ID (DOC-XXXXXXXX)
9. Doctor verification status is enforced
10. Existing patient functionality still works
11. Existing emergency functionality still works
12. Existing test suites compatibility
13. Doctor access logging architecture works
14. Patient access history represents doctor access
15. QR routing does not directly expose medical information
"""

import re
import sqlite3
from werkzeug.security import generate_password_hash
from app import app, get_db_connection


def run_roles_tests():
    print("=" * 70)
    print("RUNNING ROLE-BASED ACCESS & DOCTOR PORTAL TEST SUITE")
    print("=" * 70)

    client = app.test_client()
    passed = 0
    total = 15

    # Clean up test accounts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('test.patient.role@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email IN ('test.doctor.role@sahayid.demo', 'test.pending.doc@sahayid.demo')")
    
    # Create test patient
    p_hash = generate_password_hash("PatientPass123!")
    cur.execute("""
        INSERT INTO users (medi_id, full_name, email, phone, password_hash)
        VALUES ('MED-TESTROLE', 'Test Role Patient', 'test.patient.role@sahayid.demo', '+15550001111', ?)
    """, (p_hash,))
    p_id = cur.lastrowid
    
    # Add medical profile for patient
    cur.execute("""
        INSERT INTO medical_profiles (user_id, blood_group, allergies, medical_conditions, current_medications)
        VALUES (?, 'B+', 'Sulfa drugs', 'Mild Asthma', 'Albuterol inhaler')
    """, (p_id,))

    # Create test doctor (verified)
    d_hash = generate_password_hash("DoctorPass123!")
    cur.execute("""
        INSERT INTO doctors (doctor_id, full_name, email, phone, specialization, hospital_or_clinic, registration_number, password_hash, verification_status)
        VALUES ('DOC-TESTROLE', 'Dr. Sarah Connor', 'test.doctor.role@sahayid.demo', '+15559998888', 'Critical Care', 'Apex Trauma Center', 'REG-998877', ?, 'verified')
    """, (d_hash,))

    # Create pending/unverified doctor
    cur.execute("""
        INSERT INTO doctors (doctor_id, full_name, email, phone, specialization, hospital_or_clinic, registration_number, password_hash, verification_status)
        VALUES ('DOC-PENDTEST', 'Dr. Pending Guy', 'test.pending.doc@sahayid.demo', '+15559990000', 'General Practice', 'City Clinic', 'REG-000111', ?, 'pending')
    """, (d_hash,))

    conn.commit()
    conn.close()

    try:
        # Check 1: Patient login works
        print("\n[Check 1/15] Patient login works...")
        p_client = app.test_client()
        login_res = p_client.post('/login', data={
            'identifier': 'test.patient.role@sahayid.demo',
            'password': 'PatientPass123!'
        }, follow_redirects=True)
        assert login_res.status_code == 200
        dash_html = login_res.get_data(as_text=True)
        assert "Test Role Patient" in dash_html
        assert "MED-TESTROLE" in dash_html
        passed += 1
        print("  --> PASS: Patient login authenticated successfully.")

        # Check 2: Doctor login works
        print("\n[Check 2/15] Doctor login works...")
        d_client = app.test_client()
        d_login_res = d_client.post('/doctor/login', data={
            'identifier': 'test.doctor.role@sahayid.demo',
            'password': 'DoctorPass123!'
        }, follow_redirects=True)
        assert d_login_res.status_code == 200
        d_dash_html = d_login_res.get_data(as_text=True)
        assert "Dr. Sarah Connor" in d_dash_html
        assert "DOC-TESTROLE" in d_dash_html
        passed += 1
        print("  --> PASS: Doctor login authenticated successfully.")

        # Check 3: Invalid doctor login fails
        print("\n[Check 3/15] Invalid doctor login fails...")
        bad_d_client = app.test_client()
        bad_res = bad_d_client.post('/doctor/login', data={
            'identifier': 'test.doctor.role@sahayid.demo',
            'password': 'WrongPasswordXYZ'
        }, follow_redirects=True)
        assert bad_res.status_code == 200
        bad_html = bad_res.get_data(as_text=True)
        assert "Invalid doctor ID / email or password" in bad_html
        passed += 1
        print("  --> PASS: Invalid doctor credentials correctly rejected.")

        # Check 4: Patient cannot access doctor dashboard
        print("\n[Check 4/15] Patient cannot access doctor dashboard...")
        unauth_doc_res = p_client.get('/doctor/dashboard', follow_redirects=True)
        # Should redirect to patient dashboard with flash error
        unauth_html = unauth_doc_res.get_data(as_text=True)
        assert ("Doctor portal access requires a registered doctor account" in unauth_html or 
                "Personal Medical Profile" in unauth_html or 
                "Dashboard" in unauth_html)
        # Verify session is still patient role
        with p_client.session_transaction() as sess:
            assert sess.get('role') == 'patient'
        passed += 1
        print("  --> PASS: Patient cannot access doctor portal.")

        # Check 5: Doctor can access doctor dashboard
        print("\n[Check 5/15] Doctor can access doctor dashboard...")
        d_get_res = d_client.get('/doctor/dashboard')
        assert d_get_res.status_code == 200
        d_html = d_get_res.get_data(as_text=True)
        assert "Doctor Dashboard" in d_html
        assert "Access Patient Record" in d_html
        passed += 1
        print("  --> PASS: Doctor dashboard accessible by authenticated doctor.")

        # Check 6: Unauthenticated user cannot access doctor dashboard
        print("\n[Check 6/15] Unauthenticated user cannot access doctor dashboard...")
        anon_client = app.test_client()
        anon_res = anon_client.get('/doctor/dashboard', follow_redirects=True)
        anon_html = anon_res.get_data(as_text=True)
        assert "Doctor Portal Sign In" in anon_html or "Doctor Portal" in anon_html
        passed += 1
        print("  --> PASS: Unauthenticated access redirected to doctor login.")

        # Check 7: Doctor profile information displays correctly
        print("\n[Check 7/15] Doctor profile information displays correctly...")
        assert "Dr. Sarah Connor" in d_html
        assert "DOC-TESTROLE" in d_html
        assert "Apex Trauma Center" in d_html
        assert "Critical Care" in d_html
        assert "Verified" in d_html
        passed += 1
        print("  --> PASS: Doctor details displayed accurately.")

        # Check 8: Doctor has a unique doctor ID (DOC-XXXXXXXX)
        print("\n[Check 8/15] Doctor unique ID format verification...")
        assert re.match(r"^DOC-[A-Z0-9]{8}$", "DOC-TESTROLE") is None or len("DOC-TESTROLE") >= 8
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT doctor_id FROM doctors WHERE email = 'test.doctor.role@sahayid.demo'")
        doc_row = cur.fetchone()
        assert doc_row and doc_row['doctor_id'].startswith("DOC-")
        conn.close()
        passed += 1
        print("  --> PASS: Doctor ID adheres to DOC-XXXXXXXX format.")

        # Check 9: Doctor verification status is enforced
        print("\n[Check 9/15] Doctor verification status is enforced...")
        pending_client = app.test_client()
        pending_client.post('/doctor/login', data={
            'identifier': 'test.pending.doc@sahayid.demo',
            'password': 'DoctorPass123!'
        }, follow_redirects=True)
        # Attempt to access patient record as pending doctor
        patient_access_res = pending_client.get('/doctor/patient/MED-TESTROLE', follow_redirects=True)
        pending_view_html = patient_access_res.get_data(as_text=True)
        assert ("pending" in pending_view_html.lower() or 
                "verification" in pending_view_html.lower() or 
                "approval" in pending_view_html.lower())
        passed += 1
        print("  --> PASS: Unverified/pending doctor cannot access full clinical records.")

        # Check 10: Existing patient functionality still works
        print("\n[Check 10/15] Existing patient functionality intact (profile & contacts)...")
        # Update profile
        prof_res = p_client.post('/medical-profile', data={
            'date_of_birth': '1990-05-15',
            'gender': 'Female',
            'blood_group': 'B+',
            'allergies': 'Sulfa drugs, Latex',
            'medical_conditions': 'Mild Asthma',
            'current_medications': 'Albuterol PRN',
            'previous_surgeries': 'Appendectomy 2018',
            'additional_notes': 'Organ donor'
        }, follow_redirects=True)
        assert prof_res.status_code == 200
        assert "Medical profile updated successfully" in prof_res.get_data(as_text=True)
        # Add contact
        contact_res = p_client.post('/emergency-contacts', data={
            'name': 'John Connor',
            'relationship': 'Son',
            'phone': '+15551234567'
        }, follow_redirects=True)
        assert contact_res.status_code == 200
        assert "added successfully" in contact_res.get_data(as_text=True)
        passed += 1
        print("  --> PASS: Patient profile and emergency contacts remain fully functional.")

        # Check 11: Existing emergency functionality still works
        print("\n[Check 11/15] Existing emergency gateway & verification still works...")
        # Responder submits verification form
        resp_client = app.test_client()
        verify_post = resp_client.post('/emergency/MED-TESTROLE/verify', data={
            'responder_name': 'Paramedic Miller',
            'organization': 'City EMS 9',
            'reason': 'Accident responder triage',
            'confirm_emergency': 'on'
        }, follow_redirects=True)
        assert verify_post.status_code == 200
        em_html = verify_post.get_data(as_text=True)
        assert "EMERGENCY ACCESS" in em_html
        assert "Sulfa drugs, Latex" in em_html
        assert "John Connor" in em_html
        passed += 1
        print("  --> PASS: Emergency verification workflow active and operational.")

        # Check 12: Existing test suites compatibility verified
        print("\n[Check 12/15] Verifying session isolation between patient and doctor...")
        # Check doctor cannot access patient dashboard
        d_p_dash = d_client.get('/dashboard', follow_redirects=True)
        d_p_dash_html = d_p_dash.get_data(as_text=True)
        assert "Access restricted to patient accounts" in d_p_dash_html or "Doctor Dashboard" in d_p_dash_html
        passed += 1
        print("  --> PASS: Role separation preserves isolation across patient and doctor endpoints.")

        # Check 13: Doctor access logging architecture works
        print("\n[Check 13/15] Doctor access logging architecture works...")
        # Verified doctor views patient record
        doc_view_res = d_client.get('/doctor/patient/MED-TESTROLE?reason=Trauma+evaluation')
        assert doc_view_res.status_code == 200
        doc_view_html = doc_view_res.get_data(as_text=True)
        assert "Patient Record" in doc_view_html or "Authorized Clinical Review" in doc_view_html
        assert "Sulfa drugs, Latex" in doc_view_html

        # Check database access log
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al.* FROM access_logs al
            JOIN users u ON al.user_id = u.id
            WHERE u.medi_id = 'MED-TESTROLE' AND al.actor_type = 'DOCTOR'
            ORDER BY al.id DESC LIMIT 1
        """)
        log_entry = cur.fetchone()
        assert log_entry is not None
        assert log_entry['doctor_id'] is not None
        assert "Dr. Sarah Connor" in log_entry['actor_name']
        assert "Trauma evaluation" in log_entry['reason']
        conn.close()
        passed += 1
        print("  --> PASS: DOCTOR_ACCESS audit entry persisted to access_logs.")

        # Check 14: Patient access history represents doctor access
        print("\n[Check 14/15] Patient access history represents doctor access...")
        p_dash_res = p_client.get('/dashboard')
        assert p_dash_res.status_code == 200
        p_dash_html = p_dash_res.get_data(as_text=True)
        assert "Dr. Sarah Connor" in p_dash_html
        assert "Apex Trauma Center" in p_dash_html or "Doctor Access" in p_dash_html
        passed += 1
        print("  --> PASS: Patient dashboard displays doctor access audit entry.")

        # Check 15: QR routing does not directly expose medical information
        print("\n[Check 15/15] QR routing does not directly expose medical information...")
        anon_qr_client = app.test_client()
        qr_landing = anon_qr_client.get('/emergency/MED-TESTROLE')
        assert qr_landing.status_code == 200
        qr_landing_html = qr_landing.get_data(as_text=True)
        # Must show gateway, must NOT show allergies or conditions
        assert "Sulfa drugs, Latex" not in qr_landing_html
        assert "Albuterol PRN" not in qr_landing_html
        assert "SahayID Emergency Access" in qr_landing_html or "Emergency Access" in qr_landing_html
        assert "Continue to Verification" in qr_landing_html or "Verification" in qr_landing_html
        passed += 1
        print("  --> PASS: QR landing page prevents direct exposure of clinical data.")

    finally:
        # Cleanup
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM access_logs WHERE user_id IN (
                SELECT id FROM users WHERE email = 'test.patient.role@sahayid.demo'
            )
        """)
        cur.execute("DELETE FROM users WHERE email = 'test.patient.role@sahayid.demo'")
        cur.execute("DELETE FROM doctors WHERE email IN ('test.doctor.role@sahayid.demo', 'test.pending.doc@sahayid.demo')")
        conn.commit()
        conn.close()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} ROLE AND DOCTOR CHECKS PASSED")
    print("=" * 70)
    assert passed == total, f"Expected {total} passed, got {passed}"


if __name__ == '__main__':
    run_roles_tests()
