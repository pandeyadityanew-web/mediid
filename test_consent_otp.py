"""
SahayID Patient Consent & OTP Verification Test Suite
Tests:
1. Doctor initiates access request -> access_requests record created with status 'PENDING'
2. Doctor tracking page displays 'PENDING' status
3. Patient sees incoming access request on Patient Dashboard
4. Patient denies request -> status becomes 'DENIED', audit event logged
5. Doctor checking denied request sees 'Access Denied by Patient'
6. Patient approves request -> status becomes 'APPROVED', 6-digit OTP generated, SHA-256 hashed at rest
7. Doctor enters incorrect OTP -> attempt counter increments, error returned
8. Maximum attempt threshold (5 attempts) -> request marked 'EXPIRED'
9. Doctor enters correct 6-digit OTP -> request marked 'VERIFIED', temporary authorization granted
10. Doctor views full medical record with active authorization banner
11. Expired authorization (after 30 min) invalidates session and redirects
12. Unauthenticated user cannot approve or verify OTP
13. Cross-patient tampering blocked: Patient A cannot approve Patient B's access request
14. Cross-doctor tampering blocked: Doctor A cannot verify Doctor B's access request OTP
15. Full audit history on patient dashboard clearly reflects consent status
"""

import hashlib
from datetime import datetime, timedelta, timezone
from app import app, init_db, get_db_connection

def run_consent_otp_tests():
    print("=" * 75)
    print("RUNNING PATIENT CONSENT & OTP VERIFICATION TEST SUITE (15 CHECKS)")
    print("=" * 75)

    client = app.test_client()
    passed = 0
    total = 15

    # Clean up test accounts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('otp.patient@sahayid.demo', 'otp.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email IN ('otp.doctor1@sahayid.demo', 'otp.doctor2@sahayid.demo')")
    conn.commit()
    conn.close()

    # 1. Register Patient A
    p_email = 'otp.patient@sahayid.demo'
    p_pass = 'PatientOtpPass123!'
    p_name = 'Kavita Menon'
    client.post('/register', data={
        'full_name': p_name,
        'email': p_email,
        'phone': '+1-555-333-1111',
        'password': p_pass,
        'confirm_password': p_pass
    }, follow_redirects=True)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, medi_id FROM users WHERE email = ?", (p_email,))
    patient = cur.fetchone()
    patient_id = patient['id']
    patient_medi_id = patient['medi_id']
    conn.close()

    # Populate Patient Medical Profile
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    client.post('/medical-profile', data={
        'date_of_birth': '1995-08-20',
        'gender': 'Female',
        'blood_group': 'A+',
        'allergies': 'Ciprofloxacin, Latex',
        'medical_conditions': 'Chronic Migraine',
        'current_medications': 'Sumatriptan 50mg PRN',
        'previous_surgeries': 'Tonsillectomy (2010)',
        'additional_notes': 'Allergic to adhesive tape'
    }, follow_redirects=True)
    client.post('/emergency-contacts', data={
        'name': 'Ramesh Menon',
        'relationship': 'Father',
        'phone': '+1-555-444-2222'
    }, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # 2. Register Patient B (for cross-patient tampering check)
    p2_email = 'otp.patient2@sahayid.demo'
    p2_pass = 'Patient2OtpPass123!'
    client.post('/register', data={
        'full_name': 'Suresh Nair',
        'email': p2_email,
        'phone': '+1-555-333-2222',
        'password': p2_pass,
        'confirm_password': p2_pass
    }, follow_redirects=True)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, medi_id FROM users WHERE email = ?", (p2_email,))
    patient2 = cur.fetchone()
    conn.close()

    # 3. Register Doctor 1 (Verified)
    doc1_email = 'otp.doctor1@sahayid.demo'
    doc1_pass = 'Doc1SecurePass123!'
    doc1_name = 'Dr. Rohan Mehra'
    client.post('/doctor/register', data={
        'full_name': doc1_name,
        'email': doc1_email,
        'phone': '+1-555-777-1111',
        'password': doc1_pass,
        'confirm_password': doc1_pass,
        'specialization': 'Cardiology',
        'hospital_or_clinic': 'Fortis Heart Institute',
        'registration_number': 'MCI-CARDIO-8811'
    }, follow_redirects=True)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE doctors SET verification_status = 'verified' WHERE email = ?", (doc1_email,))
    cur.execute("SELECT id FROM doctors WHERE email = ?", (doc1_email,))
    doc1_id = cur.fetchone()['id']
    conn.commit()
    conn.close()

    # 4. Register Doctor 2 (Verified - for cross-doctor tampering check)
    doc2_email = 'otp.doctor2@sahayid.demo'
    doc2_pass = 'Doc2SecurePass123!'
    doc2_name = 'Dr. Priya Rao'
    client.post('/doctor/register', data={
        'full_name': doc2_name,
        'email': doc2_email,
        'phone': '+1-555-777-2222',
        'password': doc2_pass,
        'confirm_password': doc2_pass,
        'specialization': 'Neurology',
        'hospital_or_clinic': 'Apollo Hospital',
        'registration_number': 'MCI-NEURO-9922'
    }, follow_redirects=True)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE doctors SET verification_status = 'verified' WHERE email = ?", (doc2_email,))
    cur.execute("SELECT id FROM doctors WHERE email = ?", (doc2_email,))
    doc2_id = cur.fetchone()['id']
    conn.commit()
    conn.close()

    # -------------------------------------------------------------------------
    # Check 1: Doctor initiates access request
    # -------------------------------------------------------------------------
    print("\n[Check 1/15] Doctor initiates access request...")
    client.post('/doctor/login', data={'identifier': doc1_email, 'password': doc1_pass}, follow_redirects=True)
    req_create_resp = client.post(f'/doctor/patient/{patient_medi_id}/confirm', data={
        'reason': 'Cardiac stress consultation & ECG evaluation'
    }, follow_redirects=False)

    assert req_create_resp.status_code == 302
    redirect_target = req_create_resp.headers['Location']
    assert '/doctor/access-request/' in redirect_target
    req_token_1 = redirect_target.split('/doctor/access-request/')[-1]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_requests WHERE request_token = ?", (req_token_1,))
    req_db_1 = cur.fetchone()
    conn.close()

    assert req_db_1 is not None
    assert req_db_1['status'] == 'PENDING'
    assert req_db_1['patient_id'] == patient_id
    assert req_db_1['doctor_id'] == doc1_id
    print("  --> PASS: Access request created in database with status PENDING.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 2: Doctor tracking page displays PENDING status
    # -------------------------------------------------------------------------
    print("\n[Check 2/15] Doctor tracking page displays PENDING status...")
    tracker_resp = client.get(f'/doctor/access-request/{req_token_1}')
    assert tracker_resp.status_code == 200
    assert b"Access Request Pending Patient Approval" in tracker_resp.data
    assert p_name.encode() in tracker_resp.data
    print("  --> PASS: Doctor status tracker renders pending state correctly.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 3: Patient sees incoming access request on dashboard
    # -------------------------------------------------------------------------
    print("\n[Check 3/15] Patient sees incoming access request on dashboard...")
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    p_dash_resp = client.get('/dashboard')
    assert p_dash_resp.status_code == 200
    assert doc1_name.encode() in p_dash_resp.data
    assert b"Fortis Heart Institute" in p_dash_resp.data
    assert b"Cardiac stress consultation" in p_dash_resp.data
    assert b"Approve (Generate OTP)" in p_dash_resp.data
    assert b"Deny" in p_dash_resp.data
    print("  --> PASS: Patient dashboard displays pending doctor consent request.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 4: Patient denies access request
    # -------------------------------------------------------------------------
    print("\n[Check 4/15] Patient denies request...")
    deny_resp = client.post(f'/patient/access-request/{req_token_1}/deny', follow_redirects=True)
    assert deny_resp.status_code == 200
    assert b"Access request denied" in deny_resp.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM access_requests WHERE request_token = ?", (req_token_1,))
    assert cur.fetchone()['status'] == 'DENIED'
    conn.close()
    print("  --> PASS: Patient denial successfully sets status to DENIED.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 5: Doctor checking denied request sees 'Access Denied by Patient'
    # -------------------------------------------------------------------------
    print("\n[Check 5/15] Doctor checking denied request sees 'Access Denied'...")
    client.get('/logout', follow_redirects=True)
    client.post('/doctor/login', data={'identifier': doc1_email, 'password': doc1_pass}, follow_redirects=True)
    denied_tracker = client.get(f'/doctor/access-request/{req_token_1}')
    assert b"Access Request Denied by Patient" in denied_tracker.data
    print("  --> PASS: Doctor view displays denial notice without disclosing clinical data.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 6: Doctor creates new request and Patient approves -> Generates OTP
    # -------------------------------------------------------------------------
    print("\n[Check 6/15] Patient approves request -> status APPROVED & 6-digit OTP generated...")
    req2_resp = client.post(f'/doctor/patient/{patient_medi_id}/confirm', data={
        'reason': 'Follow-up cardiology consultation'
    }, follow_redirects=False)
    req_token_2 = req2_resp.headers['Location'].split('/doctor/access-request/')[-1]

    # Log in as patient and approve
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    approve_resp = client.post(f'/patient/access-request/{req_token_2}/approve', follow_redirects=True)
    assert approve_resp.status_code == 200
    assert b"Access Approved!" in approve_resp.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_requests WHERE request_token = ?", (req_token_2,))
    req_db_2 = cur.fetchone()
    conn.close()

    assert req_db_2['status'] == 'APPROVED'
    assert req_db_2['otp_hash'] is not None
    assert len(req_db_2['otp_hash']) == 64  # SHA-256 length

    # Extract OTP from patient dashboard session or text
    otp_text = approve_resp.get_data(as_text=True)
    import re
    otp_matches = re.findall(r"\b\d{6}\b", otp_text)
    assert len(otp_matches) > 0
    valid_otp = otp_matches[0]
    # Verify hash match
    assert hashlib.sha256(valid_otp.encode('utf-8')).hexdigest() == req_db_2['otp_hash']
    print(f"  --> PASS: 6-digit OTP ({valid_otp}) generated and SHA-256 hashed at rest.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 7: Doctor enters incorrect OTP -> attempt counter increments
    # -------------------------------------------------------------------------
    print("\n[Check 7/15] Doctor enters incorrect OTP -> attempt counter increments...")
    client.get('/logout', follow_redirects=True)
    client.post('/doctor/login', data={'identifier': doc1_email, 'password': doc1_pass}, follow_redirects=True)

    bad_otp_resp = client.post(f'/doctor/access-request/{req_token_2}/verify-otp', data={'otp': '000000'}, follow_redirects=True)
    assert b"Invalid OTP verification code" in bad_otp_resp.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT attempts FROM access_requests WHERE request_token = ?", (req_token_2,))
    assert cur.fetchone()['attempts'] == 1
    conn.close()
    print("  --> PASS: Invalid OTP rejected and attempts counter incremented.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 8: Rate limiting & attempt threshold (5 attempts max)
    # -------------------------------------------------------------------------
    print("\n[Check 8/15] Maximum attempt threshold (5 attempts) -> request EXPIRED...")
    # Create request 3 for attempt lockout test
    req3_resp = client.post(f'/doctor/patient/{patient_medi_id}/confirm', data={'reason': 'Lockout test'}, follow_redirects=False)
    req_token_3 = req3_resp.headers['Location'].split('/doctor/access-request/')[-1]

    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    client.post(f'/patient/access-request/{req_token_3}/approve', follow_redirects=True)

    client.get('/logout', follow_redirects=True)
    client.post('/doctor/login', data={'identifier': doc1_email, 'password': doc1_pass}, follow_redirects=True)

    for i in range(5):
        client.post(f'/doctor/access-request/{req_token_3}/verify-otp', data={'otp': '999999'}, follow_redirects=True)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM access_requests WHERE request_token = ?", (req_token_3,))
    assert cur.fetchone()['status'] == 'EXPIRED'
    conn.close()
    print("  --> PASS: Exceeding 5 failed OTP attempts invalidates the access request.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 9: Doctor enters valid OTP -> status VERIFIED & Temporary Auth Granted
    # -------------------------------------------------------------------------
    print("\n[Check 9/15] Doctor enters correct OTP -> status VERIFIED...")
    good_otp_resp = client.post(f'/doctor/access-request/{req_token_2}/verify-otp', data={'otp': valid_otp}, follow_redirects=True)
    assert good_otp_resp.status_code == 200
    assert b"Patient consent verified successfully via OTP" in good_otp_resp.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, authorized_until FROM access_requests WHERE request_token = ?", (req_token_2,))
    req_db_verified = cur.fetchone()
    conn.close()
    assert req_db_verified['status'] == 'VERIFIED'
    assert req_db_verified['authorized_until'] is not None
    print("  --> PASS: Correct OTP verified and temporary authorization granted.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 10: Doctor views full medical record with verified authorization
    # -------------------------------------------------------------------------
    print("\n[Check 10/15] Doctor views full medical record with verified authorization...")
    doc_view_resp = client.get(f'/doctor/patient/{patient_medi_id}')
    assert doc_view_resp.status_code == 200
    assert p_name.encode() in doc_view_resp.data
    assert b"A+" in doc_view_resp.data
    assert b"Ciprofloxacin, Latex" in doc_view_resp.data
    assert b"Chronic Migraine" in doc_view_resp.data
    assert b"Sumatriptan 50mg PRN" in doc_view_resp.data
    assert b"Tonsillectomy (2010)" in doc_view_resp.data
    assert b"Ramesh Menon" in doc_view_resp.data
    print("  --> PASS: Full authorized clinical record unlocked for verified doctor.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 11: Expired authorization invalidates session
    # -------------------------------------------------------------------------
    print("\n[Check 11/15] Expired authorization invalidates session...")
    with client.session_transaction() as sess:
        past_auth_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
        sess[f'doc_auth_{patient_medi_id}'] = {
            'authorized_until': past_auth_time,
            'request_token': req_token_2,
            'doctor_id': doc1_id
        }

    expired_auth_resp = client.get(f'/doctor/patient/{patient_medi_id}', follow_redirects=False)
    assert expired_auth_resp.status_code == 302
    assert f'/doctor/patient/{patient_medi_id}/confirm' in expired_auth_resp.headers['Location']
    print("  --> PASS: Expired doctor session authorization blocked; redirected to confirm.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 12: Unauthenticated user cannot approve or verify OTP
    # -------------------------------------------------------------------------
    print("\n[Check 12/15] Unauthenticated user cannot approve or verify OTP...")
    client.get('/logout', follow_redirects=True)
    unauth_appr = client.post(f'/patient/access-request/{req_token_2}/approve', follow_redirects=False)
    assert unauth_appr.status_code == 302
    assert '/login' in unauth_appr.headers['Location']

    unauth_vfy = client.post(f'/doctor/access-request/{req_token_2}/verify-otp', data={'otp': '123456'}, follow_redirects=False)
    assert unauth_vfy.status_code == 302
    assert '/doctor/login' in unauth_vfy.headers['Location']
    print("  --> PASS: Unauthenticated access rejected on approval and verification routes.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 13: Cross-patient tampering protection
    # -------------------------------------------------------------------------
    print("\n[Check 13/15] Cross-patient tampering protection...")
    # Patient 2 attempts to approve Patient 1's request
    client.post('/login', data={'identifier': p2_email, 'password': p2_pass}, follow_redirects=True)
    tamper_appr = client.post(f'/patient/access-request/{req_token_2}/approve', follow_redirects=True)
    assert b"Access request not found" in tamper_appr.data
    print("  --> PASS: Patient 2 blocked from approving Patient 1's access request.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 14: Cross-doctor tampering protection
    # -------------------------------------------------------------------------
    print("\n[Check 14/15] Cross-doctor tampering protection...")
    client.get('/logout', follow_redirects=True)
    # Doctor 2 attempts to verify Doctor 1's request
    client.post('/doctor/login', data={'identifier': doc2_email, 'password': doc2_pass}, follow_redirects=True)
    tamper_doc_vfy = client.post(f'/doctor/access-request/{req_token_2}/verify-otp', data={'otp': valid_otp}, follow_redirects=True)
    assert b"Access request not found" in tamper_doc_vfy.data or b"Unauthorized" in tamper_doc_vfy.data
    print("  --> PASS: Doctor 2 blocked from verifying Doctor 1's request.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 15: Full audit history reflects consent events
    # -------------------------------------------------------------------------
    print("\n[Check 15/15] Full audit history reflects consent events...")
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    p_final_dash = client.get('/dashboard')
    assert doc1_name.encode() in p_final_dash.data
    assert b"Patient Approved" in p_final_dash.data or b"DOCTOR_ACCESS" in p_final_dash.data
    print("  --> PASS: Patient dashboard audit trail records consent approval and doctor access.")
    passed += 1

    # Cleanup test data
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('otp.patient@sahayid.demo', 'otp.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email IN ('otp.doctor1@sahayid.demo', 'otp.doctor2@sahayid.demo')")
    conn.commit()
    conn.close()

    print("\n" + "=" * 75)
    print(f"RESULTS: {passed}/{total} CONSENT & OTP VERIFICATION CHECKS PASSED")
    print("=" * 75)


if __name__ == '__main__':
    run_consent_otp_tests()
