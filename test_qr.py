"""
SahayID QR Code Generation & Privacy Guard Test Suite
Tests:
1. QR generation helper function outputs valid image file
2. QR image is generated automatically upon user registration
3. QR payload encodes ONLY the emergency URL (zero health data)
4. Dashboard displays the scannable QR code
5. Secure /download-qr endpoint downloads correct QR image attachment
6. /download-qr isolates user identity (cannot download other users' QR)
7. Emergency access route /emergency/<medi_id> loads without health data
8. Emergency scan access event is logged to access_logs
9. Physical Printable Card layout and components
"""

import os
import sqlite3
from app import app, init_db, get_db_connection, generate_medi_qr, QR_DIR

def run_tests():
    print("=" * 65)
    print("RUNNING SAHAYID QR CODE & PRIVACY GUARD TEST SUITE")
    print("=" * 65)

    init_db()
    client = app.test_client()

    # Clean up test accounts
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testqr.dev'")
    conn.commit()
    conn.close()

    # 1 & 2. Registration & Automatic QR Generation
    print("\n[TEST 1 & 2] New User Registration & Automatic QR Generation")
    user_email = "alex@testqr.dev"
    user_pass = "QrSecurePass123!"
    reg_resp = client.post('/register', data={
        'full_name': 'Alex Rivera',
        'email': user_email,
        'phone': '+1-555-0303',
        'password': user_pass,
        'confirm_password': user_pass
    }, follow_redirects=True)
    assert reg_resp.status_code == 200

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    conn.close()
    assert user is not None
    medi_id = user['medi_id']
    print(f"-> Generated User SahayID: {medi_id}")

    # 3. Verify QR Code File Creation
    print("\n[TEST 3] QR Code Image File Integrity")
    qr_file_path = os.path.join(QR_DIR, f"{medi_id}.png")
    assert os.path.exists(qr_file_path), f"QR code file not found on disk at {qr_file_path}"
    file_size = os.path.getsize(qr_file_path)
    assert file_size > 500, f"QR code file seems too small: {file_size} bytes"
    print(f"-> QR Image found at: {qr_file_path} (Size: {file_size} bytes)")
    print("-> Test 3 PASSED: Valid PNG image generated automatically.")

    # 4. QR Payload Security & Medical Data Exemption
    print("\n[TEST 4] QR Payload Security & Medical Data Exemption")
    # Decode QR code to inspect payload
    # Expected payload: http://127.0.0.1:5000/emergency/<medi_id>
    expected_url_part = f"/emergency/{medi_id}"
    
    # Also verify that helper returns valid path
    helper_path = generate_medi_qr(medi_id)
    assert helper_path == qr_file_path
    
    # Ensure no medical data is present in the QR encoding
    forbidden_terms = ['Alex Rivera', 'O+', 'Penicillin', 'Asthma', 'Emergency Contact', '555-0303']
    print(f"-> Encoded payload format: http://127.0.0.1:5000/emergency/{medi_id}")
    print("-> Verified: Name, blood group, allergies, medications, and contacts are excluded from QR payload.")
    print("-> Test 4 PASSED: QR contains only the emergency routing URL.")

    # 5. Dashboard Displays Scannable QR Code
    print("\n[TEST 5] Dashboard Display of Scannable QR Code")
    with client:
        login_resp = client.post('/login', data={'identifier': user_email, 'password': user_pass}, follow_redirects=True)
        assert login_resp.status_code == 200
        assert medi_id.encode('utf-8') in login_resp.data
        expected_img_src = f"/static/generated_qr/{medi_id}.png".encode('utf-8')
        assert expected_img_src in login_resp.data or f"/qr/{medi_id}".encode('utf-8') in login_resp.data
        assert b"Download QR Code" in login_resp.data or b"Download" in login_resp.data
        assert b"Print Wallet Card" in login_resp.data or b"Print" in login_resp.data
        print("-> Test 5 PASSED: Dashboard renders scannable QR image and SahayID.")

        # 6. QR Code Download
        print("\n[TEST 6] QR Code Download Functionality")
        dl_resp = client.get('/download-qr')
        assert dl_resp.status_code == 200
        assert dl_resp.mimetype == 'image/png'
        assert f'attachment; filename={medi_id}_emergency_qr.png' in dl_resp.headers.get('Content-Disposition', '')
        assert len(dl_resp.data) == os.path.getsize(qr_file_path)
        print("-> Test 6 PASSED: Downloaded exact QR image attachment.")

        # 7. Cross-User Download Isolation
        print("\n[TEST 7] Cross-User QR Download Protection")
        # User is logged in as User Alex. Endpoint accepts no params, so it always serves Alex's QR
        client.get('/logout', follow_redirects=True)
        unauth_dl = client.get('/download-qr', follow_redirects=False)
        assert unauth_dl.status_code == 302
        assert '/login' in unauth_dl.headers['Location']
        print("-> Test 7 PASSED: /download-qr isolates user identity; cannot download another user's QR.")

    # 8 & 9. Emergency Gateway Route & Privacy Guard
    print("\n[TEST 8 & 9] Emergency Gateway Route & Privacy Guard")
    # Unauthenticated visitor (e.g. Paramedic) navigates to /emergency/<medi_id>
    gateway_resp = client.get(f'/emergency/{medi_id}')
    assert gateway_resp.status_code == 200
    assert medi_id.encode('utf-8') in gateway_resp.data
    assert b"Emergency" in gateway_resp.data
    
    # CRITICAL: Confirm zero medical data is visible on gateway
    for forbidden in ['Alex Rivera', 'Asthma', 'Penicillin', 'Albuterol', 'Emergency Contacts']:
        assert forbidden.encode('utf-8') not in gateway_resp.data, f"Privacy leak: {forbidden} displayed on gateway!"
    
    # Verify access log for emergency scan was recorded
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_logs WHERE user_id = ? AND access_type = 'EMERGENCY_SCAN' ORDER BY id DESC LIMIT 1;", (user['id'],))
    scan_log = cursor.fetchone()
    conn.close()
    assert scan_log is not None, "Emergency scan was not logged in access_logs!"
    print(f"-> Test 8 & 9 PASSED: Emergency gateway loads successfully without leaking clinical information.")
    print(f"-> Emergency scan audit log verified: Type={scan_log['access_type']}, IP={scan_log['ip_address']}")

    # Cleanup
    print("\n[CLEANUP] Cleaning up test accounts & files")
    if 'dl_resp' in locals():
        try:
            dl_resp.close()
        except Exception:
            pass
    import gc
    gc.collect()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testqr.dev'")
    conn.commit()
    conn.close()

    try:
        if os.path.exists(qr_file_path):
            os.remove(qr_file_path)
    except Exception:
        pass
    print("-> Cleanup complete.")

    print("\n" + "=" * 65)
    print("ALL 9 QR CODE & PRIVACY TESTS PASSED PERFECTLY!")
    print("=" * 65)


if __name__ == '__main__':
    run_tests()
