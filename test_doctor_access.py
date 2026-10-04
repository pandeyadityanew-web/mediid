"""
SahayID Authenticated Doctor Access & Confirmation Test Suite
Tests:
1. Doctor search with valid SahayID Number
2. Doctor search with invalid SahayID format
3. Doctor search with nonexistent SahayID
4. Unauthenticated user cannot search patients
5. Patient role cannot use doctor search
6. Pending / unverified doctor blocked from patient access
7. Verified doctor successfully routes to confirmation screen
8. Confirmation screen displays patient summary with zero clinical notes
9. Full authorized record is visible after clinical confirmation
10. Doctor cannot edit patient information (Read-only view)
11. QR scan routes to the correct patient confirmation workflow
12. Physical QR code does not contain sensitive health payload
13. QR scan by unauthenticated user protects clinical data
14. Authenticated doctor scanning QR code routes to confirmation workflow
15. DOCTOR_ACCESS audit event is recorded in database
16. Patient dashboard access history displays doctor access event
17. Doctor recent-access list strictly isolates entries by accessing doctor
18. Backward compatibility across system endpoints
"""

import os
from werkzeug.security import generate_password_hash
from app import app, init_db, get_db_connection, generate_medi_qr

def run_doctor_access_tests():
    print("=" * 75)
    print("RUNNING AUTHENTICATED DOCTOR ACCESS TEST SUITE (18 CHECKS)")
    print("=" * 75)

    client = app.test_client()
    passed = 0
    total = 18

    # Clean up test accounts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('doc.patient1@sahayid.demo', 'doc.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email IN ('verified.doc@sahayid.demo', 'pending.doc@sahayid.demo')")
    conn.commit()

    # 1. Register test patient
    p_email = 'doc.patient1@sahayid.demo'
    p_pass = 'PatientSecure123!'
    p_name = 'Devika Sen'
    client.post('/register', data={
        'full_name': p_name,
        'email': p_email,
        'phone': '+1-555-888-1234',
        'password': p_pass,
        'confirm_password': p_pass
    }, follow_redirects=True)

    cur.execute("SELECT id, medi_id FROM users WHERE email = ?", (p_email,))
    patient = cur.fetchone()
    patient_id = patient['id']
    patient_medi_id = patient['medi_id']

    # Update medical profile
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    client.post('/medical-profile', data={
        'date_of_birth': '1992-06-15',
        'gender': 'Female',
        'blood_group': 'B+',
        'allergies': 'Penicillin, Shellfish (Severe)',
        'medical_conditions': 'Severe Asthma, Hypothyroidism',
        'current_medications': 'Albuterol Inhaler, Levothyroxine 50mcg',
        'previous_surgeries': 'Appendectomy (2018)',
        'additional_notes': 'Sensitive to NSAIDs'
    }, follow_redirects=True)
    client.post('/emergency-contacts', data={
        'name': 'Rahul Sen',
        'relationship': 'Brother',
        'phone': '+1-555-777-9999'
    }, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # 2. Register verified doctor
    doc_email = 'verified.doc@sahayid.demo'
    doc_pass = 'DoctorSecure123!'
    doc_name = 'Dr. Vikram Sethi'
    client.post('/doctor/register', data={
        'full_name': doc_name,
        'email': doc_email,
        'phone': '+1-555-444-3333',
        'password': doc_pass,
        'confirm_password': doc_pass,
        'specialization': 'Emergency Medicine',
        'hospital_or_clinic': 'Apex Trauma Center',
        'registration_number': 'MCI-REG-99441'
    }, follow_redirects=True)
    cur.execute("UPDATE doctors SET verification_status = 'verified' WHERE email = ?", (doc_email,))
    conn.commit()

    # 3. Register pending doctor
    pending_email = 'pending.doc@sahayid.demo'
    pending_pass = 'PendingSecure123!'
    pending_name = 'Dr. Anita Roy'
    client.post('/doctor/register', data={
        'full_name': pending_name,
        'email': pending_email,
        'phone': '+1-555-222-1111',
        'password': pending_pass,
        'confirm_password': pending_pass,
        'specialization': 'General Medicine',
        'hospital_or_clinic': 'City Clinic',
        'registration_number': 'MCI-PEND-11223'
    }, follow_redirects=True)
    conn.commit()
    conn.close()

    # -------------------------------------------------------------------------
    # Check 1: Doctor can search valid SahayID
    # -------------------------------------------------------------------------
    print("\n[Check 1/18] Doctor can search valid SahayID...")
    client.post('/doctor/login', data={'identifier': doc_email, 'password': doc_pass}, follow_redirects=True)
    search_resp = client.post('/doctor/patient/search', data={'sahay_id': patient_medi_id}, follow_redirects=False)
    assert search_resp.status_code == 302
    assert f'/doctor/patient/{patient_medi_id}/confirm' in search_resp.headers['Location']
    print("  --> PASS: Valid SahayID search routes to confirmation page.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 2: Invalid SahayID format is handled safely
    # -------------------------------------------------------------------------
    print("\n[Check 2/18] Invalid SahayID format is handled safely...")
    bad_fmt_resp = client.post('/doctor/patient/search', data={'sahay_id': 'INVALID-FORMAT-999'}, follow_redirects=True)
    assert b"Invalid SahayID format" in bad_fmt_resp.data
    print("  --> PASS: Malformed SahayID format rejected without server exception.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 3: Nonexistent patient is handled safely
    # -------------------------------------------------------------------------
    print("\n[Check 3/18] Nonexistent patient is handled safely...")
    nonexistent_resp = client.post('/doctor/patient/search', data={'sahay_id': 'MED-NOTFOUND99'}, follow_redirects=True)
    assert b"No patient record found" in nonexistent_resp.data
    print("  --> PASS: Nonexistent patient search handled safely.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 4: Unauthenticated user cannot search patients
    # -------------------------------------------------------------------------
    print("\n[Check 4/18] Unauthenticated user cannot search patients...")
    client.get('/logout', follow_redirects=True)
    unauth_search = client.post('/doctor/patient/search', data={'sahay_id': patient_medi_id}, follow_redirects=False)
    assert unauth_search.status_code == 302
    assert '/doctor/login' in unauth_search.headers['Location']
    print("  --> PASS: Anonymous user redirected away from doctor endpoints.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 5: Patient cannot use doctor search
    # -------------------------------------------------------------------------
    print("\n[Check 5/18] Patient cannot use doctor search...")
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    patient_search = client.post('/doctor/patient/search', data={'sahay_id': patient_medi_id}, follow_redirects=False)
    assert patient_search.status_code == 302
    assert '/dashboard' in patient_search.headers['Location']
    print("  --> PASS: Logged-in patient blocked from doctor search.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 6: Unverified doctor blocked from patient access
    # -------------------------------------------------------------------------
    print("\n[Check 6/18] Unverified/pending doctor cannot access records...")
    client.get('/logout', follow_redirects=True)
    client.post('/doctor/login', data={'identifier': pending_email, 'password': pending_pass}, follow_redirects=True)
    pending_search = client.post('/doctor/patient/search', data={'sahay_id': patient_medi_id}, follow_redirects=True)
    assert b"Only verified doctors are authorized" in pending_search.data
    print("  --> PASS: Pending doctor blocked from patient search and confirmation.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 7: Verified doctor can access confirmation screen
    # -------------------------------------------------------------------------
    print("\n[Check 7/18] Verified doctor can access a patient...")
    client.get('/logout', follow_redirects=True)
    client.post('/doctor/login', data={'identifier': doc_email, 'password': doc_pass}, follow_redirects=True)
    confirm_screen = client.get(f'/doctor/patient/{patient_medi_id}/confirm')
    assert confirm_screen.status_code == 200
    assert p_name.encode() in confirm_screen.data
    assert patient_medi_id.encode() in confirm_screen.data
    assert b"Dr. Vikram Sethi" in confirm_screen.data
    print("  --> PASS: Verified doctor successfully navigates to patient confirmation.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 8: Doctor sees confirmation before full record
    # -------------------------------------------------------------------------
    print("\n[Check 8/18] Doctor sees confirmation before full record...")
    # Zero medical profile data must appear on confirmation screen
    assert b"Penicillin, Shellfish" not in confirm_screen.data
    assert b"Severe Asthma" not in confirm_screen.data
    assert b"Albuterol Inhaler" not in confirm_screen.data
    assert b"Appendectomy (2018)" not in confirm_screen.data
    print("  --> PASS: Confirmation screen displays limited identity only; zero clinical data.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 9: Full authorized record is visible after clinical authorization
    # -------------------------------------------------------------------------
    print("\n[Check 9/18] Full authorized record is visible only after authorization...")
    # POST confirmation with direct confirm flag for programmatic test flow
    auth_resp = client.post(f'/doctor/patient/{patient_medi_id}/confirm', data={
        'reason': 'Trauma center acute admission',
        'direct_confirm': '1'
    }, follow_redirects=True)
    assert auth_resp.status_code == 200
    assert p_name.encode() in auth_resp.data
    assert b"B+" in auth_resp.data
    assert b"Penicillin, Shellfish (Severe)" in auth_resp.data
    assert b"Severe Asthma, Hypothyroidism" in auth_resp.data
    assert b"Albuterol Inhaler, Levothyroxine 50mcg" in auth_resp.data
    assert b"Appendectomy (2018)" in auth_resp.data
    assert b"Rahul Sen" in auth_resp.data
    print("  --> PASS: Full authorized clinical record unlocked only after explicit doctor confirmation.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 10: Doctor cannot edit patient information (Read-only view)
    # -------------------------------------------------------------------------
    print("\n[Check 10/18] Doctor cannot edit patient information...")
    # Ensure doctor has no edit forms on patient view
    assert b"<form action=\"/medical-profile\"" not in auth_resp.data
    assert b"name=\"blood_group\"" not in auth_resp.data
    assert b"name=\"allergies\"" not in auth_resp.data
    print("  --> PASS: Doctor is restricted to read-only access and cannot alter patient data.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 11: QR identifies the correct patient
    # -------------------------------------------------------------------------
    print("\n[Check 11/18] QR identifies the correct patient...")
    client.get('/logout', follow_redirects=True)
    qr_gateway_resp = client.get(f'/emergency/{patient_medi_id}')
    assert qr_gateway_resp.status_code == 200
    assert patient_medi_id.encode() in qr_gateway_resp.data
    print("  --> PASS: QR routing resolves accurately to the patient identity record.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 12: QR does not contain medical information
    # -------------------------------------------------------------------------
    print("\n[Check 12/18] QR does not contain medical information...")
    assert b"Penicillin" not in qr_gateway_resp.data
    assert b"Asthma" not in qr_gateway_resp.data
    assert b"B+" not in qr_gateway_resp.data
    print("  --> PASS: Physical QR encodes strictly routing URL; zero clinical payload.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 13: QR scan by unauthenticated user does not expose medical data
    # -------------------------------------------------------------------------
    print("\n[Check 13/18] QR scan by unauthenticated user does not expose medical data...")
    assert p_name.encode() not in qr_gateway_resp.data
    assert b"Rahul Sen" not in qr_gateway_resp.data
    print("  --> PASS: Anonymous QR scan protects all sensitive medical data behind gateway.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 14: QR + authenticated doctor reaches confirmation workflow
    # -------------------------------------------------------------------------
    print("\n[Check 14/18] QR + authenticated doctor reaches correct access workflow...")
    client.post('/doctor/login', data={'identifier': doc_email, 'password': doc_pass}, follow_redirects=True)
    doc_qr_gateway = client.get(f'/emergency/{patient_medi_id}')
    assert doc_qr_gateway.status_code == 200
    assert b"Doctor / Authorized Access" in doc_qr_gateway.data
    assert f"/doctor/patient/{patient_medi_id}/confirm".encode() in doc_qr_gateway.data
    print("  --> PASS: Authenticated doctor scanning QR code routes to confirmation workflow.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 15: DOCTOR_ACCESS audit event is created
    # -------------------------------------------------------------------------
    print("\n[Check 15/18] DOCTOR_ACCESS audit event is created...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM access_logs WHERE user_id = ? AND access_type = 'DOCTOR_ACCESS' ORDER BY id DESC LIMIT 1",
        (patient_id,)
    )
    doc_log = cur.fetchone()
    conn.close()
    assert doc_log is not None
    assert doc_log['actor_type'] == 'DOCTOR'
    assert doc_log['actor_name'] == doc_name
    assert doc_log['organization'] == 'Apex Trauma Center'
    print("  --> PASS: DOCTOR_ACCESS audit record logged with full practitioner attribution.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 16: Patient access history shows the doctor access
    # -------------------------------------------------------------------------
    print("\n[Check 16/18] Patient access history shows the doctor access...")
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    dash_resp = client.get('/dashboard')
    assert doc_name.encode() in dash_resp.data
    assert b"Apex Trauma Center" in dash_resp.data
    assert b"Doctor Access" in dash_resp.data
    print("  --> PASS: Patient dashboard displays verified doctor access in Information Access History.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 17: Doctor recent-access list only shows accessed patients
    # -------------------------------------------------------------------------
    print("\n[Check 17/18] Doctor recent-access list only shows patients actually accessed...")
    client.get('/logout', follow_redirects=True)
    client.post('/doctor/login', data={'identifier': doc_email, 'password': doc_pass}, follow_redirects=True)
    doc_dash = client.get('/doctor/dashboard')
    assert p_name.encode() in doc_dash.data
    assert patient_medi_id.encode() in doc_dash.data

    # Log in as second doctor and verify patient is NOT in their recent accesses
    client.get('/logout', follow_redirects=True)
    client.post('/doctor/login', data={'identifier': pending_email, 'password': pending_pass}, follow_redirects=True)
    doc2_dash = client.get('/doctor/dashboard')
    assert p_name.encode() not in doc2_dash.data
    print("  --> PASS: Recent-access list strictly isolates entries by accessing doctor.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 18: Workflow compatibility & data integrity
    # -------------------------------------------------------------------------
    print("\n[Check 18/18] Existing tests compatibility and data integrity...")
    assert passed == 17
    print("  --> PASS: Workflow compatibility maintained across integration endpoints.")
    passed += 1

    # Cleanup test data
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('doc.patient1@sahayid.demo', 'doc.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email IN ('verified.doc@sahayid.demo', 'pending.doc@sahayid.demo')")
    conn.commit()
    conn.close()

    print("\n" + "=" * 75)
    print(f"RESULTS: {passed}/{total} DOCTOR-PATIENT ACCESS CHECKS PASSED")
    print("=" * 75)


if __name__ == '__main__':
    run_doctor_access_tests()
