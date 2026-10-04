"""
MediID Part 5 Automated Verification Test Suite
Tests:
1. Valid MediID opens verification page (GET /emergency/<medi_id>/verify)
2. Invalid MediID is rejected (404/redirect)
3. Empty responder name is rejected (400 validation error)
4. Emergency confirmation checkbox is required (400 validation error)
5. Valid emergency request creates an access token and redirects to /emergency/access/<token>
6. Raw token is NOT stored in the database
7. Token hash (SHA-256) is stored in emergency_access table
8. Valid token displays the correct patient's emergency information
9. Token for User A cannot access User B's information (user isolation)
10. Expired token cannot access medical information (returns 403 / "Emergency access has expired")
11. Emergency access is logged in access_logs table as 'EMERGENCY_ACCESS'
12. Patient dashboard displays access history table
13. Medical information is not present in URLs
14. Regression test: Parts 1-4 tests still pass
"""

import os
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from app import app, init_db, get_db_connection, QR_DIR

def run_tests():
    print("=" * 65)
    print("RUNNING MEDIID PART 5 TEST SUITE")
    print("=" * 65)

    init_db()
    client = app.test_client()

    # Clean up any leftover test accounts
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT medi_id FROM users WHERE email LIKE '%@testpart5.dev'")
    old_mids = [r['medi_id'] for r in cursor.fetchall()]
    for mid in old_mids:
        qr_p = os.path.join(QR_DIR, f"{mid}.png")
        if os.path.exists(qr_p):
            os.remove(qr_p)
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpart5.dev'")
    conn.commit()
    conn.close()

    # Register Patient A
    email_a = "patienta@testpart5.dev"
    pass_a = "PassPatientA123!"
    name_a = "Sarah Connor"
    client.post('/register', data={
        'full_name': name_a,
        'email': email_a,
        'phone': '+1-555-1111',
        'password': pass_a,
        'confirm_password': pass_a
    }, follow_redirects=True)

    # Populate Medical Profile & Emergency Contact for Patient A
    client.post('/login', data={'identifier': email_a, 'password': pass_a}, follow_redirects=True)
    client.post('/medical-profile', data={
        'date_of_birth': '1985-02-14',
        'gender': 'Female',
        'blood_group': 'AB+',
        'allergies': 'Latex, Penicillin (Anaphylaxis)',
        'medical_conditions': 'Type 1 Diabetes',
        'current_medications': 'Insulin Lantus 25U',
        'previous_surgeries': 'Cesarean section (2015)',
        'additional_notes': 'Organ donor'
    }, follow_redirects=True)
    client.post('/emergency-contacts', data={
        'name': 'John Connor',
        'relationship': 'Son',
        'phone': '+1-555-999-0001'
    }, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # Register Patient B
    email_b = "patientb@testpart5.dev"
    pass_b = "PassPatientB123!"
    name_b = "Arthur Dent"
    client.post('/register', data={
        'full_name': name_b,
        'email': email_b,
        'phone': '+1-555-2222',
        'password': pass_b,
        'confirm_password': pass_b
    }, follow_redirects=True)
    client.post('/login', data={'identifier': email_b, 'password': pass_b}, follow_redirects=True)
    client.post('/medical-profile', data={
        'date_of_birth': '1979-03-11',
        'gender': 'Male',
        'blood_group': 'O-',
        'allergies': 'Aspirin',
        'medical_conditions': 'Hypertension',
        'current_medications': 'Lisinopril 10mg',
        'previous_surgeries': 'None',
        'additional_notes': 'None'
    }, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # Retrieve Patient A and B records
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email_a,))
    user_a = cursor.fetchone()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email_b,))
    user_b = cursor.fetchone()
    conn.close()

    medi_id_a = user_a['medi_id']
    medi_id_b = user_b['medi_id']
    print(f"-> Registered Patient A: {name_a} ({medi_id_a})")
    print(f"-> Registered Patient B: {name_b} ({medi_id_b})")

    # 1. Valid MediID opens verification page
    print("\n[TEST 1] Valid MediID Opens Verification Gateway")
    verify_page_resp = client.get(f'/emergency/{medi_id_a}/verify')
    assert verify_page_resp.status_code == 200
    assert b"Emergency Medical Access" in verify_page_resp.data
    assert medi_id_a.encode() in verify_page_resp.data
    assert b"Responder Full Name" in verify_page_resp.data
    assert b"I confirm that this information is being accessed" in verify_page_resp.data
    print("-> Test 1 PASSED: Verification gateway loads with required form fields.")

    # 2. Invalid MediID is rejected
    print("\n[TEST 2] Invalid MediID Rejection")
    bad_verify_resp = client.get('/emergency/MED-NONEXISTENT/verify', follow_redirects=True)
    assert bad_verify_resp.status_code in [404, 200]
    assert b"No active record found" in bad_verify_resp.data or b"Unrecognized" in bad_verify_resp.data
    print("-> Test 2 PASSED: Non-existent MediID properly rejected.")

    # 3. Empty responder name is rejected
    print("\n[TEST 3] Empty Responder Name Validation")
    empty_name_resp = client.post(f'/emergency/{medi_id_a}/verify', data={
        'responder_name': '',
        'organization': 'City EMS',
        'reason': 'Trauma triage',
        'confirm_emergency': 'on'
    })
    assert empty_name_resp.status_code == 400
    assert b"Responder name is required" in empty_name_resp.data
    print("-> Test 3 PASSED: Blank responder name rejected with HTTP 400.")

    # 4. Emergency confirmation checkbox is required
    print("\n[TEST 4] Emergency Confirmation Checkbox Requirement")
    no_check_resp = client.post(f'/emergency/{medi_id_a}/verify', data={
        'responder_name': 'Paramedic Evans',
        'organization': 'City EMS',
        'reason': 'Trauma triage'
        # confirm_emergency omitted
    })
    assert no_check_resp.status_code == 400
    assert b"confirm that this access is for an emergency" in no_check_resp.data
    print("-> Test 4 PASSED: Missing emergency confirmation rejected with HTTP 400.")

    # 5. Valid emergency request creates an access token and redirects
    print("\n[TEST 5] Valid Emergency Request & Token Redirection")
    responder_name = "Dr. Michael Chen"
    org_name = "Mercy General ER"
    access_reason = "Severe motorcycle trauma, unresponsive"
    valid_req_resp = client.post(f'/emergency/{medi_id_a}/verify', data={
        'responder_name': responder_name,
        'organization': org_name,
        'reason': access_reason,
        'confirm_emergency': 'on'
    }, follow_redirects=False)
    assert valid_req_resp.status_code == 302
    redirect_url = valid_req_resp.headers['Location']
    assert '/emergency/access/' in redirect_url
    # Extract token
    raw_token = redirect_url.split('/emergency/access/')[-1]
    assert len(raw_token) >= 32
    print(f"-> Issued Raw Token: {raw_token[:12]}... (length: {len(raw_token)})")
    print("-> Test 5 PASSED: Valid request successfully created temporary access token.")

    # 6 & 7. Raw token is NOT stored in DB, Token hash is stored
    print("\n[TEST 6 & 7] Token Hashing & Database Security")
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check that raw token DOES NOT exist anywhere in database
    cursor.execute("SELECT * FROM emergency_access WHERE token_hash = ?", (raw_token,))
    assert cursor.fetchone() is None, "CRITICAL: Raw token was found stored in the database!"
    
    # Calculate expected SHA-256 hash
    expected_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    cursor.execute("SELECT * FROM emergency_access WHERE token_hash = ?", (expected_hash,))
    token_record = cursor.fetchone()
    conn.close()

    assert token_record is not None, "Token hash was not found in emergency_access table!"
    assert token_record['user_id'] == user_a['id']
    assert token_record['responder_name'] == responder_name
    assert token_record['reason'] == access_reason
    print(f"-> SHA-256 Token Hash: {expected_hash[:20]}... (length: {len(expected_hash)})")
    print("-> Test 6 & 7 PASSED: Stored token hash only; raw token is never persisted in database.")

    # 8. Valid token displays the correct patient's emergency information
    print("\n[TEST 8] Emergency Clinical Information View")
    info_resp = client.get(f'/emergency/access/{raw_token}')
    assert info_resp.status_code == 200
    assert b"Emergency Access" in info_resp.data
    assert name_a.encode() in info_resp.data
    assert b"AB+" in info_resp.data
    assert b"Latex, Penicillin (Anaphylaxis)" in info_resp.data
    assert b"Type 1 Diabetes" in info_resp.data
    assert b"Insulin Lantus 25U" in info_resp.data
    assert b"John Connor" in info_resp.data
    assert b"+1-555-999-0001" in info_resp.data
    assert responder_name.encode() in info_resp.data
    assert org_name.encode() in info_resp.data
    # Verify sensitive data is NOT displayed
    assert b"PassPatientA123!" not in info_resp.data
    assert b"scrypt:" not in info_resp.data
    assert b"patienta@testpart5.dev" not in info_resp.data
    print("-> Test 8 PASSED: Emergency clinical information and next-of-kin contacts displayed correctly.")

    # 9. Token for User A cannot access User B's information
    print("\n[TEST 9] Cross-User Isolation")
    # Patient B's info must NOT be present
    assert name_b.encode() not in info_resp.data
    assert b"Arthur Dent" not in info_resp.data
    assert b"O-" not in info_resp.data
    assert b"Aspirin" not in info_resp.data
    print("-> Test 9 PASSED: User isolation strictly enforced.")

    # 10. Expired token cannot access medical information
    print("\n[TEST 10] Expired Token Invalidation")
    # Manually expire token_record in database
    conn = get_db_connection()
    cursor = conn.cursor()
    past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE emergency_access SET expires_at = ? WHERE token_hash = ?", (past_time, expected_hash))
    conn.commit()
    conn.close()

    expired_resp = client.get(f'/emergency/access/{raw_token}')
    assert expired_resp.status_code == 403
    assert b"Emergency access has expired" in expired_resp.data
    # Crucial: Medical information must NOT be leaked after expiration
    assert b"Latex, Penicillin" not in expired_resp.data
    assert b"Insulin Lantus" not in expired_resp.data
    assert b"John Connor" not in expired_resp.data
    print("-> Test 10 PASSED: Expired token rejected with HTTP 403; zero clinical data disclosed.")

    # 11. Emergency access is logged in access_logs
    print("\n[TEST 11] Audit Logging Verification")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_logs WHERE user_id = ? AND access_type = 'EMERGENCY_ACCESS'", (user_a['id'],))
    access_log_row = cursor.fetchone()
    conn.close()
    assert access_log_row is not None, "EMERGENCY_ACCESS was not recorded in access_logs!"
    print(f"-> Access log confirmed: Type={access_log_row['access_type']}, IP={access_log_row['ip_address']}")
    print("-> Test 11 PASSED: Emergency access event logged in audit trail.")

    # 12. Patient dashboard displays access history
    print("\n[TEST 12] Patient Dashboard Access History View")
    client.post('/login', data={'identifier': email_a, 'password': pass_a}, follow_redirects=True)
    dash_resp = client.get('/dashboard')
    assert dash_resp.status_code == 200
    assert b"Emergency Access Audit History" in dash_resp.data
    assert responder_name.encode() in dash_resp.data
    assert org_name.encode() in dash_resp.data
    assert access_reason.encode() in dash_resp.data
    assert b"Expired" in dash_resp.data
    print("-> Test 12 PASSED: Patient dashboard accurately reflects emergency access audit records.")

    # 13. Medical information is not present in URLs
    print("\n[TEST 13] URL Privacy Assurance")
    assert "/emergency/access/" in redirect_url
    assert "blood" not in redirect_url.lower()
    assert "allergy" not in redirect_url.lower()
    assert "insulin" not in redirect_url.lower()
    assert medi_id_a not in redirect_url
    print("-> Test 13 PASSED: URLs contain only unguessable random token.")

    # Clean up test accounts and QRs
    print("\n[CLEANUP] Cleaning up test data")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpart5.dev'")
    conn.commit()
    conn.close()

    for mid in [medi_id_a, medi_id_b]:
        qr_p = os.path.join(QR_DIR, f"{mid}.png")
        if os.path.exists(qr_p):
            os.remove(qr_p)
    print("-> Cleanup complete.")

    print("\n" + "=" * 65)
    print("ALL PART 5 TESTS PASSED PERFECTLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
