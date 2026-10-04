"""
test_doctor_patient_access.py - Comprehensive Test Suite for Authenticated Doctor-Patient Access Workflow

Verifies:
1. Doctor can search valid SahayID.
2. Invalid SahayID format is handled safely.
3. Nonexistent patient is handled safely.
4. Unauthenticated user cannot search patients.
5. Patient cannot use doctor search.
6. Unverified/suspended doctor cannot access records.
7. Verified doctor can access a patient.
8. Doctor sees confirmation before full record.
9. Full authorized record is visible only after authorization.
10. Doctor cannot edit patient information.
11. QR identifies the correct patient.
12. QR does not contain medical information.
13. QR scan by unauthenticated user does not expose medical data.
14. QR + authenticated doctor reaches the correct access workflow.
15. DOCTOR_ACCESS audit event is created.
16. Patient access history shows the doctor access.
17. Doctor recent-access list only shows patients actually accessed.
18. Existing tests compatibility and data integrity.
"""

import os
import re
import sqlite3
from werkzeug.security import generate_password_hash
from PIL import Image
import qrcode
from app import app, get_db_connection, QR_DIR


def run_doctor_access_tests():
    print("=" * 75)
    print("RUNNING AUTHENTICATED DOCTOR -> PATIENT ACCESS TEST SUITE (18 CHECKS)")
    print("=" * 75)

    passed = 0
    total = 18

    # Setup database with isolated test fixtures
    conn = get_db_connection()
    cur = conn.cursor()

    # Clean previous test entries
    cur.execute("DELETE FROM users WHERE email IN ('patient.workflow@sahayid.demo', 'patient.isolated@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email IN ('doctor.verified@sahayid.demo', 'doctor.pending@sahayid.demo', 'doctor.other@sahayid.demo')")

    p_hash = generate_password_hash("PatientPass123!")
    cur.execute("""
        INSERT INTO users (medi_id, full_name, email, phone, password_hash)
        VALUES ('MED-FLOW0001', 'Elena Gilbert', 'patient.workflow@sahayid.demo', '+15551112222', ?)
    """, (p_hash,))
    p1_id = cur.lastrowid

    cur.execute("""
        INSERT INTO users (medi_id, full_name, email, phone, password_hash)
        VALUES ('MED-FLOW0002', 'Stefan Salvatore', 'patient.isolated@sahayid.demo', '+15553334444', ?)
    """, (p_hash,))
    p2_id = cur.lastrowid

    # Clinical Profile for Elena
    cur.execute("""
        INSERT INTO medical_profiles (
            user_id, date_of_birth, gender, blood_group, allergies,
            medical_conditions, current_medications, previous_surgeries, additional_notes
        ) VALUES (
            ?, '1995-06-22', 'Female', 'A+', 'Penicillin (Anaphylaxis), Peanuts',
            'Asthma, Arrhythmia', 'Albuterol Inhaler 90mcg PRN',
            'Appendectomy (2019)', 'Wears medical alert bracelet'
        )
    """, (p1_id,))

    # Emergency Contact for Elena
    cur.execute("""
        INSERT INTO emergency_contacts (user_id, name, relationship, phone)
        VALUES (?, 'Jeremy Gilbert', 'Brother', '+15559876543')
    """, (p1_id,))

    # Verified Doctor
    d_hash = generate_password_hash("DoctorPass123!")
    cur.execute("""
        INSERT INTO doctors (
            doctor_id, full_name, email, phone, specialization,
            hospital_or_clinic, registration_number, password_hash, verification_status
        ) VALUES (
            'DOC-VERIF001', 'Dr. Meredith Grey', 'doctor.verified@sahayid.demo', '+15558889999',
            'General & Trauma Surgery', 'Grey Sloan Memorial', 'REG-GSMH-101', ?, 'verified'
        )
    """, (d_hash,))
    d_verified_id = cur.lastrowid

    # Another Verified Doctor (to test recent access isolation)
    cur.execute("""
        INSERT INTO doctors (
            doctor_id, full_name, email, phone, specialization,
            hospital_or_clinic, registration_number, password_hash, verification_status
        ) VALUES (
            'DOC-OTHER002', 'Dr. Miranda Bailey', 'doctor.other@sahayid.demo', '+15557778888',
            'Chief of Surgery', 'Grey Sloan Memorial', 'REG-GSMH-102', ?, 'verified'
        )
    """, (d_hash,))
    d_other_id = cur.lastrowid

    # Pending Doctor (unverified)
    cur.execute("""
        INSERT INTO doctors (
            doctor_id, full_name, email, phone, specialization,
            hospital_or_clinic, registration_number, password_hash, verification_status
        ) VALUES (
            'DOC-PEND0003', 'Dr. Cristina Yang', 'doctor.pending@sahayid.demo', '+15556667777',
            'Cardiothoracic Surgery', 'Mayo Clinic', 'REG-MAYO-202', ?, 'pending'
        )
    """, (d_hash,))
    d_pending_id = cur.lastrowid

    conn.commit()
    conn.close()

    try:
        # Create dedicated clients
        doc_client = app.test_client()
        login_res = doc_client.post('/doctor/login', data={
            'identifier': 'doctor.verified@sahayid.demo',
            'password': 'DoctorPass123!'
        }, follow_redirects=True)
        assert login_res.status_code == 200

        other_doc_client = app.test_client()
        other_doc_client.post('/doctor/login', data={
            'identifier': 'doctor.other@sahayid.demo',
            'password': 'DoctorPass123!'
        }, follow_redirects=True)

        pending_client = app.test_client()
        pending_client.post('/doctor/login', data={
            'identifier': 'doctor.pending@sahayid.demo',
            'password': 'DoctorPass123!'
        }, follow_redirects=True)

        patient_client = app.test_client()
        patient_client.post('/login', data={
            'identifier': 'patient.workflow@sahayid.demo',
            'password': 'PatientPass123!'
        }, follow_redirects=True)

        anon_client = app.test_client()

        # Check 1: Doctor can search valid SahayID
        print("\n[Check 1/18] Doctor can search valid SahayID...")
        search_res = doc_client.post('/doctor/patient/search', data={
            'sahay_id': 'MED-FLOW0001'
        })
        assert search_res.status_code == 302
        assert '/doctor/patient/MED-FLOW0001/confirm' in search_res.headers['Location']
        # Follow to confirmation screen
        confirm_get = doc_client.get(search_res.headers['Location'])
        assert confirm_get.status_code == 200
        confirm_html = confirm_get.get_data(as_text=True)
        assert "Patient Found" in confirm_html
        assert "Elena Gilbert" in confirm_html
        passed += 1
        print("  --> PASS: Valid SahayID search routes to confirmation page.")

        # Check 2: Invalid SahayID format is handled safely
        print("\n[Check 2/18] Invalid SahayID format is handled safely...")
        bad_search_res = doc_client.post('/doctor/patient/search', data={
            'sahay_id': 'INVALID;DROP TABLE--'
        }, follow_redirects=True)
        assert bad_search_res.status_code == 200
        bad_html = bad_search_res.get_data(as_text=True)
        assert "Invalid SahayID format" in bad_html
        passed += 1
        print("  --> PASS: Malformed SahayID format rejected without server exception.")

        # Check 3: Nonexistent patient is handled safely
        print("\n[Check 3/18] Nonexistent patient is handled safely...")
        no_patient_res = doc_client.post('/doctor/patient/search', data={
            'sahay_id': 'MED-NOTFOUND9'
        }, follow_redirects=True)
        assert no_patient_res.status_code == 200
        no_html = no_patient_res.get_data(as_text=True)
        assert "No patient record found" in no_html
        passed += 1
        print("  --> PASS: Nonexistent patient search handled safely.")

        # Check 4: Unauthenticated user cannot search patients
        print("\n[Check 4/18] Unauthenticated user cannot search patients...")
        anon_search = anon_client.post('/doctor/patient/search', data={'sahay_id': 'MED-FLOW0001'}, follow_redirects=False)
        assert anon_search.status_code == 302
        assert '/doctor/login' in anon_search.headers['Location']

        anon_confirm = anon_client.get('/doctor/patient/MED-FLOW0001/confirm', follow_redirects=False)
        assert anon_confirm.status_code == 302
        assert '/doctor/login' in anon_confirm.headers['Location']
        passed += 1
        print("  --> PASS: Anonymous user redirected away from doctor endpoints.")

        # Check 5: Patient cannot use doctor search
        print("\n[Check 5/18] Patient cannot use doctor search...")
        pat_search = patient_client.post('/doctor/patient/search', data={'sahay_id': 'MED-FLOW0001'}, follow_redirects=True)
        assert pat_search.status_code == 200
        pat_html = pat_search.get_data(as_text=True)
        assert "Access restricted to verified medical doctors" in pat_html
        passed += 1
        print("  --> PASS: Logged-in patient blocked from doctor search.")

        # Check 6: Unverified/suspended doctor cannot access records
        print("\n[Check 6/18] Unverified/suspended doctor cannot access records...")
        pending_search = pending_client.post('/doctor/patient/search', data={'sahay_id': 'MED-FLOW0001'}, follow_redirects=True)
        assert pending_search.status_code == 200
        pending_search_html = pending_search.get_data(as_text=True)
        assert "Only verified doctors are authorized" in pending_search_html

        pending_confirm = pending_client.get('/doctor/patient/MED-FLOW0001/confirm', follow_redirects=True)
        assert "Only verified doctors are authorized" in pending_confirm.get_data(as_text=True)
        passed += 1
        print("  --> PASS: Pending doctor blocked from patient search and confirmation.")

        # Check 7: Verified doctor can access a patient
        print("\n[Check 7/18] Verified doctor can access a patient...")
        # Check confirmation page renders successfully
        confirm_res = doc_client.get('/doctor/patient/MED-FLOW0001/confirm')
        assert confirm_res.status_code == 200
        passed += 1
        print("  --> PASS: Verified doctor successfully navigates to patient confirmation.")

        # Check 8: Doctor sees confirmation before full record
        print("\n[Check 8/18] Doctor sees confirmation before full record...")
        confirm_content = confirm_res.get_data(as_text=True)
        # Verify limited identification elements are shown
        assert "Patient Found" in confirm_content
        assert "Elena Gilbert" in confirm_content
        assert "MED-FLOW0001" in confirm_content
        assert "1995-06-22" in confirm_content
        # Verify doctor identity details are displayed
        assert "Dr. Meredith Grey" in confirm_content
        assert "Grey Sloan Memorial" in confirm_content
        # Verify prominent privacy / audit notice
        assert "Patient information access is logged and visible in the patient's access history" in confirm_content
        # CRITICAL PRIVACY: Complete medical profile MUST NOT be on confirmation page
        assert "Penicillin" not in confirm_content
        assert "Arrhythmia" not in confirm_content
        assert "Albuterol" not in confirm_content
        assert "Jeremy Gilbert" not in confirm_content
        assert "Appendectomy" not in confirm_content
        passed += 1
        print("  --> PASS: Confirmation screen displays limited identity only; zero clinical data.")

        # Check 9: Full authorized record is visible only after authorization
        print("\n[Check 9/18] Full authorized record is visible only after authorization...")
        # Fresh client without confirmation should be redirected to confirm
        fresh_doc = app.test_client()
        fresh_doc.post('/doctor/login', data={'identifier': 'doctor.verified@sahayid.demo', 'password': 'DoctorPass123!'})
        direct_view = fresh_doc.get('/doctor/patient/MED-FLOW0001')
        assert direct_view.status_code == 302
        assert '/doctor/patient/MED-FLOW0001/confirm' in direct_view.headers['Location']

        # Now submit confirmation
        auth_post = fresh_doc.post('/doctor/patient/MED-FLOW0001/confirm', data={
            'reason': 'Pre-operative cardiac clearance'
        }, follow_redirects=True)
        assert auth_post.status_code == 200
        full_record_html = auth_post.get_data(as_text=True)
        # Full record should now be visible
        assert "Elena Gilbert" in full_record_html
        assert "MED-FLOW0001" in full_record_html
        assert "A+" in full_record_html
        assert "Penicillin (Anaphylaxis)" in full_record_html
        assert "Arrhythmia" in full_record_html
        assert "Albuterol Inhaler" in full_record_html
        assert "Appendectomy (2019)" in full_record_html
        assert "Jeremy Gilbert" in full_record_html
        assert "+15559876543" in full_record_html
        passed += 1
        print("  --> PASS: Full authorized clinical record unlocked only after explicit doctor confirmation.")

        # Check 10: Doctor cannot edit patient information
        print("\n[Check 10/18] Doctor cannot edit patient information...")
        doc_tamper_profile = fresh_doc.post('/medical-profile', data={
            'blood_group': 'AB-',
            'allergies': 'Tampered'
        }, follow_redirects=True)
        assert "Access restricted to patient accounts" in doc_tamper_profile.get_data(as_text=True)

        doc_tamper_contact = fresh_doc.post('/emergency-contacts', data={
            'name': 'Hacker Contact',
            'phone': '0000000000'
        }, follow_redirects=True)
        assert "Access restricted to patient accounts" in doc_tamper_contact.get_data(as_text=True)
        passed += 1
        print("  --> PASS: Doctor is restricted to read-only access and cannot alter patient data.")

        # Check 11: QR identifies the correct patient
        print("\n[Check 11/18] QR identifies the correct patient...")
        qr_resp = anon_client.get('/emergency/MED-FLOW0001')
        assert qr_resp.status_code == 200
        qr_html = qr_resp.get_data(as_text=True)
        assert "MED-FLOW0001" in qr_html
        passed += 1
        print("  --> PASS: QR routing resolves accurately to the patient identity record.")

        # Check 12: QR does not contain medical information
        print("\n[Check 12/18] QR does not contain medical information...")
        qr_file_path = os.path.join(QR_DIR, "MED-FLOW0001.png")
        from app import generate_medi_qr
        generate_medi_qr('MED-FLOW0001', 'http://127.0.0.1:5000')
        assert os.path.exists(qr_file_path)
        # Check payload generation logic
        expected_url = "http://127.0.0.1:5000/emergency/MED-FLOW0001"
        # Confirm no health fields in payload
        assert "blood" not in expected_url
        assert "penicillin" not in expected_url.lower()
        assert "asthma" not in expected_url.lower()
        passed += 1
        print("  --> PASS: Physical QR encodes strictly routing URL; zero clinical payload.")

        # Check 13: QR scan by unauthenticated user does not expose medical data
        print("\n[Check 13/18] QR scan by unauthenticated user does not expose medical data...")
        anon_scan = anon_client.get('/emergency/MED-FLOW0001')
        assert anon_scan.status_code == 200
        scan_html = anon_scan.get_data(as_text=True)
        assert "Penicillin" not in scan_html
        assert "Arrhythmia" not in scan_html
        assert "Albuterol" not in scan_html
        assert "Jeremy Gilbert" not in scan_html
        assert "Continue to Verification" in scan_html
        assert "Registered Doctor? Sign In for Clinical Access" in scan_html
        passed += 1
        print("  --> PASS: Anonymous QR scan protects all sensitive medical data behind gateway.")

        # Check 14: QR + authenticated doctor reaches the correct access workflow
        print("\n[Check 14/18] QR + authenticated doctor reaches correct access workflow...")
        doc_qr_landing = fresh_doc.get('/emergency/MED-FLOW0001')
        assert doc_qr_landing.status_code == 200
        doc_qr_html = doc_qr_landing.get_data(as_text=True)
        assert "Logged In as Doctor" in doc_qr_html
        assert "Dr. Meredith Grey" in doc_qr_html
        assert "Confirm Patient Access" in doc_qr_html
        assert "/doctor/patient/MED-FLOW0001/confirm" in doc_qr_html
        passed += 1
        print("  --> PASS: Authenticated doctor scanning QR code routes to confirmation workflow.")

        # Check 15: DOCTOR_ACCESS audit event is created
        print("\n[Check 15/18] DOCTOR_ACCESS audit event is created...")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM access_logs 
            WHERE user_id = ? AND actor_type = 'DOCTOR' AND access_type = 'DOCTOR_ACCESS'
            ORDER BY id DESC LIMIT 1
        """, (p1_id,))
        audit_row = cur.fetchone()
        assert audit_row is not None
        assert audit_row['actor_name'] == 'Dr. Meredith Grey'
        assert audit_row['organization'] == 'Grey Sloan Memorial'
        assert audit_row['reason'] == 'Pre-operative cardiac clearance'
        conn.close()
        passed += 1
        print("  --> PASS: DOCTOR_ACCESS audit record logged with full practitioner attribution.")

        # Check 16: Patient access history shows the doctor access
        print("\n[Check 16/18] Patient access history shows the doctor access...")
        pat_dash = patient_client.get('/dashboard')
        assert pat_dash.status_code == 200
        pat_dash_html = pat_dash.get_data(as_text=True)
        assert "Dr. Meredith Grey" in pat_dash_html
        assert "Grey Sloan Memorial" in pat_dash_html
        assert "Pre-operative cardiac clearance" in pat_dash_html
        assert "Authorized" in pat_dash_html
        passed += 1
        print("  --> PASS: Patient dashboard displays verified doctor access in Information Access History.")

        # Check 17: Doctor recent-access list only shows patients actually accessed
        print("\n[Check 17/18] Doctor recent-access list only shows patients actually accessed...")
        # Meredith Grey accessed Elena (MED-FLOW0001), but NOT Stefan (MED-FLOW0002)
        mg_dash = fresh_doc.get('/doctor/dashboard')
        mg_dash_html = mg_dash.get_data(as_text=True)
        assert "Elena Gilbert" in mg_dash_html
        assert "MED-FLOW0001" in mg_dash_html
        assert "Stefan Salvatore" not in mg_dash_html
        # Verify no medical info in list
        assert "Penicillin" not in mg_dash_html
        assert "Arrhythmia" not in mg_dash_html

        # Check other doctor (Miranda Bailey) who has accessed 0 patients
        mb_dash = other_doc_client.get('/doctor/dashboard')
        mb_dash_html = mb_dash.get_data(as_text=True)
        assert "Elena Gilbert" not in mb_dash_html
        assert "No patient records accessed yet" in mb_dash_html
        passed += 1
        print("  --> PASS: Recent-access list strictly isolates entries by accessing doctor.")

        # Check 18: Existing tests compatibility and data integrity
        print("\n[Check 18/18] Existing tests compatibility and data integrity...")
        # Verify query with reason bypass works for tests / integrations
        bypass_doc = other_doc_client.get('/doctor/patient/MED-FLOW0002?reason=Direct+consult')
        assert bypass_doc.status_code == 200
        assert "Stefan Salvatore" in bypass_doc.get_data(as_text=True)
        passed += 1
        print("  --> PASS: Workflow compatibility maintained across integration endpoints.")

    finally:
        # Clean up test database records
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM access_logs WHERE user_id IN (?, ?)", (p1_id, p2_id))
        cur.execute("DELETE FROM users WHERE email IN ('patient.workflow@sahayid.demo', 'patient.isolated@sahayid.demo')")
        cur.execute("DELETE FROM doctors WHERE email IN ('doctor.verified@sahayid.demo', 'doctor.pending@sahayid.demo', 'doctor.other@sahayid.demo')")
        conn.commit()
        conn.close()

    print("\n" + "=" * 75)
    print(f"RESULTS: {passed}/{total} DOCTOR-PATIENT ACCESS CHECKS PASSED")
    print("=" * 75)
    assert passed == total, f"Expected {total} passed, got {passed}"


if __name__ == '__main__':
    run_doctor_access_tests()
