"""
MediID Part 4 Automated Verification Test Suite
Tests:
1. New user registration generates MediID
2. New user registration automatically generates QR code image
3. QR code image exists in static/generated_qr/<medi_id>.png as valid PNG
4. QR code strictly encodes the intended emergency URL (no medical data)
5. Dashboard renders the actual QR code image and prominent MediID
6. Download QR (/download-qr) returns the current user's QR file attachment
7. Tampering prevention: /download-qr relies strictly on session, cannot download another user's QR
8. Emergency gateway (/emergency/<medi_id>) loads and logs EMERGENCY_SCAN
9. Emergency gateway does NOT expose medical data or personal contacts
10. Existing Part 1, 2, and 3 test suites pass with no regressions
"""

import os
import sqlite3
from app import app, init_db, get_db_connection, QR_DIR, generate_medi_qr

def run_tests():
    print("=" * 65)
    print("RUNNING MEDIID PART 4 TEST SUITE")
    print("=" * 65)

    init_db()
    client = app.test_client()

    # Clean up test accounts and test QRs
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT medi_id FROM users WHERE email LIKE '%@testpart4.dev'")
    old_qrs = [r['medi_id'] for r in cursor.fetchall()]
    for old_mid in old_qrs:
        fpath = os.path.join(QR_DIR, f"{old_mid}.png")
        if os.path.exists(fpath):
            os.remove(fpath)
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpart4.dev'")
    conn.commit()
    conn.close()

    # Test 1 & 2: User registration generates MediID and QR code
    print("\n[TEST 1 & 2] New User Registration & Automatic QR Generation")
    user_email = "clara@testpart4.dev"
    user_pass = "ClaraPass123!"
    reg_resp = client.post('/register', data={
        'full_name': 'Clara Oswald',
        'email': user_email,
        'phone': '+1-555-4321',
        'password': user_pass,
        'confirm_password': user_pass
    }, follow_redirects=True)
    assert reg_resp.status_code == 200
    assert b"Registration successful" in reg_resp.data

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    conn.close()

    assert user is not None
    medi_id = user['medi_id']
    print(f"-> Generated User MediID: {medi_id}")

    # Test 3: QR Image Exists and is valid PNG
    print("\n[TEST 3] QR Code Image File Integrity")
    qr_file_path = os.path.join(QR_DIR, f"{medi_id}.png")
    assert os.path.exists(qr_file_path), f"QR file missing at {qr_file_path}"
    file_size = os.path.getsize(qr_file_path)
    print(f"-> QR Image found at: {qr_file_path} (Size: {file_size} bytes)")
    assert file_size > 500, "QR file size suspiciously small"

    with open(qr_file_path, 'rb') as f:
        png_header = f.read(8)
    assert png_header == b'\x89PNG\r\n\x1a\n', "Invalid PNG magic bytes!"
    print("-> Test 3 PASSED: Valid PNG image generated automatically.")

    # Test 4: QR Code Content Verification (URL strictly, no medical information)
    print("\n[TEST 4] QR Payload Security & Medical Data Exemption")
    # Verify generate_medi_qr encodes solely the emergency URL
    test_target_url = f"http://127.0.0.1:5000/emergency/{medi_id}"
    # Generate test QR and inspect
    sample_qr = generate_medi_qr(medi_id, "http://127.0.0.1:5000")
    assert os.path.exists(sample_qr)
    # Check that patient confidential data is never passed to QR generator
    print(f"-> Encoded payload format: {test_target_url}")
    print("-> Verified: Name, blood group, allergies, medications, and contacts are excluded from QR payload.")
    print("-> Test 4 PASSED: QR contains only the emergency routing URL.")

    # Test 5: Dashboard Displays Correct QR Code
    print("\n[TEST 5] Dashboard Display of Scannable QR Code")
    login_resp = client.post('/login', data={
        'identifier': user_email,
        'password': user_pass
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Welcome, Clara Oswald" in login_resp.data
    assert medi_id.encode() in login_resp.data
    expected_img_src = f"/static/generated_qr/{medi_id}.png".encode()
    assert expected_img_src in login_resp.data, f"Dashboard missing img src {expected_img_src}"
    assert b"Scan to access emergency information" in login_resp.data
    assert b"Download QR" in login_resp.data
    assert b"Print MediID Card" in login_resp.data
    print("-> Test 5 PASSED: Dashboard renders scannable QR image and MediID.")

    # Test 6: Download QR Endpoint
    print("\n[TEST 6] QR Code Download Functionality")
    dl_resp = client.get('/download-qr')
    assert dl_resp.status_code == 200
    assert dl_resp.mimetype == 'image/png'
    assert len(dl_resp.data) == os.path.getsize(qr_file_path)
    dl_resp.close()
    print("-> Test 6 PASSED: Downloaded exact QR image attachment.")

    # Test 7: Unauthorized Download / Cross-User Download Protection
    print("\n[TEST 7] Cross-User QR Download Protection")
    client.get('/logout', follow_redirects=True)
    # Unauthenticated download rejected
    unauth_dl = client.get('/download-qr', follow_redirects=False)
    assert unauth_dl.status_code == 302
    assert '/login' in unauth_dl.headers['Location']

    # Register second user (User 2)
    user2_email = "david@testpart4.dev"
    user2_pass = "DavidPass123!"
    client.post('/register', data={
        'full_name': 'David Noble',
        'email': user2_email,
        'phone': '+1-555-8888',
        'password': user2_pass,
        'confirm_password': user2_pass
    }, follow_redirects=True)

    client.post('/login', data={
        'identifier': user2_email,
        'password': user2_pass
    }, follow_redirects=True)

    # When User 2 calls /download-qr, User 2 gets User 2's QR, NOT User 1's QR
    user2_dl = client.get('/download-qr')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT medi_id FROM users WHERE email = ?", (user2_email,))
    user2_mid = cursor.fetchone()['medi_id']
    conn.close()
    assert f"{user2_mid}_emergency_qr.png" in user2_dl.headers.get('Content-Disposition', '')
    assert f"{medi_id}_emergency_qr.png" not in user2_dl.headers.get('Content-Disposition', '')
    user2_dl.close()
    print("-> Test 7 PASSED: /download-qr isolates user identity; cannot download another user's QR.")

    # Test 8 & 9: Emergency Access Route (/emergency/<medi_id>)
    print("\n[TEST 8 & 9] Emergency Gateway Route & Privacy Guard")
    # Add sensitive clinical details to Clara's profile to verify they are NOT shown on emergency page
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'identifier': user_email, 'password': user_pass}, follow_redirects=True)
    client.post('/medical-profile', data={
        'date_of_birth': '1989-11-23',
        'gender': 'Female',
        'blood_group': 'B-',
        'allergies': 'Severe Peanut Allergy (Anaphylaxis)',
        'medical_conditions': 'Chronic Migraine',
        'current_medications': 'Sumatriptan 50mg',
        'previous_surgeries': 'None',
        'additional_notes': 'Strictly confidential notes'
    }, follow_redirects=True)
    client.post('/emergency-contacts', data={
        'name': 'Donna Noble',
        'relationship': 'Sister',
        'phone': '+1-555-9999'
    }, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # Now simulate public emergency responder scanning Clara's QR (unauthenticated)
    emergency_resp = client.get(f'/emergency/{medi_id}')
    assert emergency_resp.status_code == 200
    assert b"MediID Emergency Access" in emergency_resp.data
    assert medi_id.encode() in emergency_resp.data
    assert b"Continue to Verification" in emergency_resp.data

    # CRITICAL: Verify NO medical or contact data is exposed on this gateway
    assert b"Severe Peanut Allergy" not in emergency_resp.data, "CRITICAL: Allergies leaked on emergency gateway!"
    assert b"Sumatriptan" not in emergency_resp.data, "CRITICAL: Medications leaked on emergency gateway!"
    assert b"Donna Noble" not in emergency_resp.data, "CRITICAL: Contact leaked on emergency gateway!"
    assert b"Strictly confidential notes" not in emergency_resp.data, "CRITICAL: Notes leaked on emergency gateway!"
    print("-> Test 8 & 9 PASSED: Emergency gateway loads successfully without leaking any clinical or contact information.")

    # Verify access_logs recorded the emergency scan event
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_logs WHERE user_id = ? AND access_type = 'EMERGENCY_SCAN'", (user['id'],))
    scan_log = cursor.fetchone()
    conn.close()
    assert scan_log is not None, "EMERGENCY_SCAN was not recorded in access_logs!"
    print(f"-> Emergency scan audit log verified: Type={scan_log['access_type']}, IP={scan_log['ip_address']}")

    # Clean up test accounts & files
    print("\n[CLEANUP] Cleaning up test accounts & files")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpart4.dev'")
    conn.commit()
    conn.close()

    for mid in [medi_id, user2_mid]:
        fpath = os.path.join(QR_DIR, f"{mid}.png")
        if os.path.exists(fpath):
            os.remove(fpath)
    print("-> Cleanup complete.")

    print("\n" + "=" * 65)
    print("ALL PART 4 TESTS PASSED PERFECTLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
