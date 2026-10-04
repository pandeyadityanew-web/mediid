"""
SahayID Emergency Break-Glass & Verification Test Suite
Tests:
1. Emergency verification form rendered with required fields
2. Invalid MediID safely rejected
3. Empty responder name validation (HTTP 400)
4. Emergency confirmation checkbox requirement (HTTP 400)
5. Valid submission creates temporary access record and redirects to token URL
6. Ephemeral access token generation & SHA-256 token hashing at rest
7. Raw token not stored in database (only SHA-256 hash stored)
8. Temporary emergency access page displays vital information
9. Cross-user isolation (token maps strictly to intended patient)
10. Expired tokens are rejected (HTTP 403) and do not leak data
11. Emergency access event logged in access_logs
12. Patient dashboard reflects emergency access history accurately
13. URL contains only unguessable random token
"""

import hashlib
from datetime import datetime, timedelta, timezone
from app import app, init_db, get_db_connection

def run_tests():
    print("=" * 65)
    print("RUNNING SAHAYID EMERGENCY BREAK-GLASS TEST SUITE")
    print("=" * 65)

    init_db()
    client = app.test_client()

    # Clean up old test data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testemergency.dev'")
    conn.commit()
    conn.close()

    # Register Patient A (Sarah Connor)
    patient_a_email = "sarah@testemergency.dev"
    patient_a_pass = "TerminatorPass123!"
    client.post('/register', data={
        'full_name': 'Sarah Connor',
        'email': patient_a_email,
        'phone': '+1-555-1001',
        'password': patient_a_pass,
        'confirm_password': patient_a_pass
    }, follow_redirects=True)

    # Register Patient B (Arthur Dent)
    patient_b_email = "arthur@testemergency.dev"
    patient_b_pass = "DontPanic42!"
    client.post('/register', data={
        'full_name': 'Arthur Dent',
        'email': patient_b_email,
        'phone': '+1-555-1002',
        'password': patient_b_pass,
        'confirm_password': patient_b_pass
    }, follow_redirects=True)

    # Retrieve patient records
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (patient_a_email,))
    patient_a = cursor.fetchone()
    cursor.execute("SELECT * FROM users WHERE email = ?", (patient_b_email,))
    patient_b = cursor.fetchone()

    # Update Patient A's medical profile & contacts
    client.post('/login', data={'identifier': patient_a_email, 'password': patient_a_pass}, follow_redirects=True)
    client.post('/medical-profile', data={
        'date_of_birth': '1984-05-12',
        'gender': 'Female',
        'blood_group': 'AB-',
        'allergies': 'Penicillin (Anaphylaxis), Morphine',
        'medical_conditions': 'Hypertension, PTSD',
        'current_medications': 'Lisinopril 10mg daily',
        'previous_surgeries': 'Left Shoulder Reconstruction (2019)',
        'additional_notes': 'Prefers non-opioid analgesics when possible'
    }, follow_redirects=True)

    client.post('/emergency-contacts', data={
        'name': 'John Connor',
        'relationship': 'Son',
        'phone': '+1-555-2002'
    }, follow_redirects=True)
    client.get('/logout', follow_redirects=True)
    conn.close()

    medi_id_a = patient_a['medi_id']
    medi_id_b = patient_b['medi_id']
    print(f"-> Registered Patient A: {patient_a['full_name']} ({medi_id_a})")
    print(f"-> Registered Patient B: {patient_b['full_name']} ({medi_id_b})")

    # 1. Verification Gateway Form Rendering
    print("\n[TEST 1] Valid SahayID Opens Verification Gateway")
    verify_page = client.get(f'/emergency/{medi_id_a}/verify')
    assert verify_page.status_code == 200
    assert medi_id_a.encode('utf-8') in verify_page.data
    assert b"Emergency Break-Glass Access" in verify_page.data or b"Emergency" in verify_page.data
    assert b"name=\"responder_name\"" in verify_page.data
    assert b"name=\"organization\"" in verify_page.data
    assert b"name=\"reason\"" in verify_page.data
    assert b"name=\"confirm_emergency\"" in verify_page.data
    print("-> Test 1 PASSED: Verification gateway loads with required form fields.")

    # 2. Invalid SahayID Rejection
    print("\n[TEST 2] Invalid SahayID Rejection")
    bad_verify = client.get('/emergency/MED-NONEXISTENT/verify', follow_redirects=False)
    assert bad_verify.status_code == 404
    print("-> Test 2 PASSED: Non-existent SahayID properly rejected.")

    # 3. Empty Responder Name Validation
    print("\n[TEST 3] Empty Responder Name Validation")
    resp_empty_name = client.post(f'/emergency/{medi_id_a}/verify', data={
        'responder_name': '   ',
        'organization': 'Metro EMS',
        'reason': 'Severe trauma evaluation',
        'confirm_emergency': 'on'
    })
    assert resp_empty_name.status_code == 400
    assert b"Responder name is required" in resp_empty_name.data
    print("-> Test 3 PASSED: Blank responder name rejected with HTTP 400.")

    # 4. Emergency Confirmation Checkbox Requirement
    print("\n[TEST 4] Emergency Confirmation Checkbox Requirement")
    resp_no_checkbox = client.post(f'/emergency/{medi_id_a}/verify', data={
        'responder_name': 'Paramedic Evans',
        'organization': 'Metro EMS Unit 3',
        'reason': 'Severe trauma evaluation'
        # confirm_emergency omitted
    })
    assert resp_no_checkbox.status_code == 400
    assert b"confirm that this access is for an emergency" in resp_no_checkbox.data
    print("-> Test 4 PASSED: Missing emergency confirmation rejected with HTTP 400.")

    # 5, 6 & 7. Valid Request, Ephemeral Token Generation & SHA-256 Hashing
    print("\n[TEST 5] Valid Emergency Request & Token Redirection")
    valid_resp = client.post(f'/emergency/{medi_id_a}/verify', data={
        'responder_name': 'Paramedic Michael Evans',
        'organization': 'City Ambulance Unit 12',
        'reason': 'Unconscious patient with severe head trauma',
        'confirm_emergency': 'on'
    }, follow_redirects=False)
    
    assert valid_resp.status_code == 302, f"Expected 302 redirect, got {valid_resp.status_code}"
    redirect_location = valid_resp.headers['Location']
    assert '/emergency/access/' in redirect_location
    
    raw_token = redirect_location.split('/emergency/access/')[-1]
    assert len(raw_token) >= 32, f"Raw token is too short: {raw_token}"
    print(f"-> Issued Raw Token: {raw_token[:12]}... (length: {len(raw_token)})")
    print("-> Test 5 PASSED: Valid request successfully created temporary access token.")

    # Verify SHA-256 hash storage at rest
    print("\n[TEST 6 & 7] Token Hashing & Database Security")
    expected_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    print(f"-> SHA-256 Token Hash: {expected_hash[:20]}... (length: {len(expected_hash)})")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergency_access WHERE token_hash = ?", (expected_hash,))
    token_row = cursor.fetchone()
    conn.close()

    assert token_row is not None, "Token hash not found in emergency_access table!"
    assert token_row['user_id'] == patient_a['id']
    assert token_row['responder_name'] == 'Paramedic Michael Evans'
    assert token_row['organization'] == 'City Ambulance Unit 12'
    assert token_row['reason'] == 'Unconscious patient with severe head trauma'
    
    # Ensure raw token was NEVER stored in DB
    cursor = get_db_connection().cursor()
    cursor.execute("SELECT COUNT(*) as count FROM emergency_access WHERE token_hash LIKE ?", (f"%{raw_token}%",))
    assert cursor.fetchone()['count'] == 0, "SECURITY HAZARD: Raw token is present in database!"
    print("-> Test 6 & 7 PASSED: Stored token hash only; raw token is never persisted in database.")

    # 8. Access Emergency Information Page
    print("\n[TEST 8] Emergency Clinical Information View")
    info_resp = client.get(f'/emergency/access/{raw_token}')
    assert info_resp.status_code == 200
    assert b"Sarah Connor" in info_resp.data
    assert medi_id_a.encode('utf-8') in info_resp.data
    assert b"AB-" in info_resp.data
    assert b"Penicillin (Anaphylaxis), Morphine" in info_resp.data
    assert b"Hypertension, PTSD" in info_resp.data
    assert b"Lisinopril 10mg daily" in info_resp.data
    assert b"John Connor" in info_resp.data
    assert b"+1-555-2002" in info_resp.data
    assert b"Paramedic Michael Evans" in info_resp.data
    print("-> Test 8 PASSED: Emergency clinical information and next-of-kin contacts displayed correctly.")

    # 9. Cross-User Isolation
    print("\n[TEST 9] Cross-User Isolation")
    # Patient B's details should NOT appear when viewing Patient A's emergency token
    assert b"Arthur Dent" not in info_resp.data
    assert medi_id_b.encode('utf-8') not in info_resp.data
    print("-> Test 9 PASSED: User isolation strictly enforced.")

    # 10. Expired Token Invalidation
    print("\n[TEST 10] Expired Token Invalidation")
    conn = get_db_connection()
    cursor = conn.cursor()
    # Artificially expire the token in the database
    past_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE emergency_access SET expires_at = ? WHERE token_hash = ?", (past_timestamp, expected_hash))
    conn.commit()
    conn.close()

    expired_resp = client.get(f'/emergency/access/{raw_token}')
    assert expired_resp.status_code == 403, f"Expected 403 Forbidden, got {expired_resp.status_code}"
    assert b"Emergency access has expired" in expired_resp.data
    # Ensure clinical data is NOT exposed
    assert b"Sarah Connor" not in expired_resp.data
    assert b"Lisinopril" not in expired_resp.data
    print("-> Test 10 PASSED: Expired token rejected with HTTP 403; zero clinical data disclosed.")

    # 11. Audit Logging Verification
    print("\n[TEST 11] Audit Logging Verification")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_logs WHERE user_id = ? AND access_type IN ('EMERGENCY_ACCESS', 'EMERGENCY_BREAK_GLASS') ORDER BY id DESC LIMIT 1;", (patient_a['id'],))
    access_log = cursor.fetchone()
    conn.close()

    assert access_log is not None, "Emergency access was not logged in access_logs table!"
    print(f"-> Access log confirmed: Type={access_log['access_type']}, IP={access_log['ip_address']}")
    print("-> Test 11 PASSED: Emergency access event logged in audit trail.")

    # 12. Patient Dashboard Access History View
    print("\n[TEST 12] Patient Dashboard Access History View")
    client.post('/login', data={'identifier': patient_a_email, 'password': patient_a_pass}, follow_redirects=True)
    dash_resp = client.get('/dashboard')
    assert dash_resp.status_code == 200
    assert b"Paramedic Michael Evans" in dash_resp.data
    assert b"City Ambulance Unit 12" in dash_resp.data
    assert b"Unconscious patient with severe head trauma" in dash_resp.data
    print("-> Test 12 PASSED: Patient dashboard accurately reflects emergency access audit records.")

    # 13. URL Privacy Check
    print("\n[TEST 13] URL Privacy Assurance")
    # Verify no email or MediID is present in access URL
    assert patient_a_email not in redirect_location
    assert medi_id_a not in redirect_location
    print("-> Test 13 PASSED: URLs contain only unguessable random token.")

    # Cleanup
    print("\n[CLEANUP] Cleaning up test data")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testemergency.dev'")
    conn.commit()
    conn.close()
    print("-> Cleanup complete.")

    print("\n" + "=" * 65)
    print("ALL 13 EMERGENCY BREAK-GLASS TESTS PASSED PERFECTLY!")
    print("=" * 65)


if __name__ == '__main__':
    run_tests()
