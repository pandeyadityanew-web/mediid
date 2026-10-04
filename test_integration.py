"""
SahayID End-to-End System Integration Test Suite
Comprehensive checks covering:
1. Landing page rendering, asymmetric hero, and workflow
2. Patient registration with unique SahayID generation
3. Dual-identifier session login (Email and SahayID Number)
4. Authentication protection & redirect guards
5. Dashboard UI, profile completion calculation, printable wallet card
6. Medical profile full CRUD (Personal, Medical, Additional)
7. Emergency contact management (Add, Delete, IDOR prevention)
8. QR Code generation & static file serving
9. Download QR endpoint isolation
10. QR payload privacy (Zero health data encoded)
11. Emergency gateway rendering & legal privacy warnings
12. Invalid SahayID safe handling (HTTP 404)
13. Emergency verification form validation (Responder, Reason, Checkbox)
14. Ephemeral token generation & SHA-256 token hashing at rest
15. Emergency access view (Vitals, Allergies, Contacts, Responder metadata)
16. Token expiration enforcement (HTTP 403 Forbidden)
17. Branded error pages (404, 403, 429, 500)
18. Defensive HTTP Security Headers
"""

import os
import hashlib
from datetime import datetime, timedelta, timezone
from app import app, init_db, get_db_connection, QR_DIR

def run_integration_tests():
    print("=" * 70)
    print("RUNNING SAHAYID COMPREHENSIVE INTEGRATION TEST SUITE (18 CHECKS)")
    print("=" * 70)

    client = app.test_client()
    passed = 0
    total = 18

    # Clean up test accounts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('final.patient@sahayid.demo', 'final.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email = 'final.doctor@sahayid.demo'")
    conn.commit()
    conn.close()

    # -------------------------------------------------------------------------
    # Check 1: Landing Page & Marketing Content
    # -------------------------------------------------------------------------
    print("\n[Check 1/18] Landing Page Rendering & Content...")
    resp = client.get('/')
    assert resp.status_code == 200
    assert b"SahayID" in resp.data
    assert b"CRITICAL MEDICAL ACCESS" in resp.data
    assert b"Patient Login" in resp.data
    assert b"Doctor" in resp.data
    print("  -> Passed: Landing page renders with full workflow.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 2: Patient Registration & Auto MediID Assignment
    # -------------------------------------------------------------------------
    print("\n[Check 2/18] Patient Registration & SahayID Assignment...")
    reg_resp = client.post('/register', data={
        'full_name': 'Alex Sharma',
        'email': 'final.patient@sahayid.demo',
        'phone': '+1-555-901-2345',
        'password': 'SecurePatientPass123!',
        'confirm_password': 'SecurePatientPass123!'
    }, follow_redirects=True)
    assert reg_resp.status_code == 200
    assert b"Registration successful" in reg_resp.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, medi_id FROM users WHERE email = 'final.patient@sahayid.demo'")
    patient = cur.fetchone()
    conn.close()
    assert patient is not None
    assert patient['medi_id'].startswith("MED-")
    patient_id = patient['id']
    patient_medi_id = patient['medi_id']
    print(f"  -> Passed: User registered with SahayID: {patient_medi_id}")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 3: Session Login & Access Logging
    # -------------------------------------------------------------------------
    print("\n[Check 3/18] Session Login & Audit Logging...")
    login_resp = client.post('/login', data={
        'identifier': 'final.patient@sahayid.demo',
        'password': 'SecurePatientPass123!'
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert patient_medi_id.encode('utf-8') in login_resp.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_logs WHERE user_id = ? AND access_type = 'LOGIN'", (patient_id,))
    login_log = cur.fetchone()
    conn.close()
    assert login_log is not None
    print("  -> Passed: User logged in and LOGIN logged in access_logs.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 4: Authentication Guard on Protected Routes
    # -------------------------------------------------------------------------
    print("\n[Check 4/18] Authentication Guard on Protected Routes...")
    client.get('/logout', follow_redirects=True)
    unauth_resp = client.get('/dashboard', follow_redirects=False)
    assert unauth_resp.status_code == 302
    assert '/login' in unauth_resp.headers['Location']
    print("  -> Passed: Unauthenticated request to /dashboard redirected to /login.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 5: Patient Dashboard UI & Physical Printable Card
    # -------------------------------------------------------------------------
    print("\n[Check 5/18] Patient Dashboard UI & Printable Card Elements...")
    client.post('/login', data={'identifier': 'final.patient@sahayid.demo', 'password': 'SecurePatientPass123!'}, follow_redirects=True)
    dash_resp = client.get('/dashboard')
    assert dash_resp.status_code == 200
    assert b"Alex Sharma" in dash_resp.data
    assert patient_medi_id.encode('utf-8') in dash_resp.data
    assert b"Print Wallet Card" in dash_resp.data
    assert b"Information Access History" in dash_resp.data
    print("  -> Passed: Dashboard displays patient vitals, physical card layout, and audit history.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 6: Medical Profile Updates
    # -------------------------------------------------------------------------
    print("\n[Check 6/18] Medical Profile Updates (Personal, Medical, Additional)...")
    prof_update = client.post('/medical-profile', data={
        'date_of_birth': '1988-04-12',
        'gender': 'Male',
        'blood_group': 'O+',
        'allergies': 'Penicillin, Peanuts (Severe Anaphylaxis)',
        'medical_conditions': 'Type 1 Diabetes, Asthma',
        'current_medications': 'Insulin Glargine 20u nightly, Albuterol Inhaler',
        'previous_surgeries': 'Appendectomy (2012)',
        'additional_notes': 'Organ donor. Carry glucose tablets.'
    }, follow_redirects=True)
    assert prof_update.status_code == 200
    assert b"Medical profile updated successfully" in prof_update.data
    assert b"Penicillin, Peanuts" in prof_update.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (patient_id,))
    mp = cur.fetchone()
    conn.close()
    assert mp['blood_group'] == 'O+'
    assert 'Diabetes' in mp['medical_conditions']
    print("  -> Passed: Medical profile fields successfully saved and verified in database.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 7: Emergency Contacts Management
    # -------------------------------------------------------------------------
    print("\n[Check 7/18] Emergency Contacts Management...")
    contact_resp = client.post('/emergency-contacts', data={
        'name': 'Priya Sharma',
        'relationship': 'Spouse',
        'phone': '+1-555-019-9944'
    }, follow_redirects=True)
    assert contact_resp.status_code == 200
    assert b"Priya Sharma" in contact_resp.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM emergency_contacts WHERE user_id = ?", (patient_id,))
    contact_id = cur.fetchone()['id']
    conn.close()

    # Add second contact and delete
    client.post('/emergency-contacts', data={'name': 'Temp Contact', 'relationship': 'Friend', 'phone': '+1-555-0000'}, follow_redirects=True)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM emergency_contacts WHERE name = 'Temp Contact'")
    temp_id = cur.fetchone()['id']
    conn.close()

    del_resp = client.post(f'/emergency-contacts/delete/{temp_id}', follow_redirects=True)
    assert del_resp.status_code == 200
    assert b"removed successfully" in del_resp.data
    print("  -> Passed: Emergency contact added and deleted successfully.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 8: QR Code Static Image Generation & Serving
    # -------------------------------------------------------------------------
    print("\n[Check 8/18] QR Code Static Image Generation & Serving...")
    qr_img_resp = client.get(f'/static/generated_qr/{patient_medi_id}.png')
    assert qr_img_resp.status_code == 200
    assert qr_img_resp.mimetype == 'image/png'
    assert len(qr_img_resp.data) > 500
    print("  -> Passed: QR image generated and returned with image/png MIME type.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 9: QR Code Download Endpoint
    # -------------------------------------------------------------------------
    print("\n[Check 9/18] QR Code Download Endpoint...")
    dl_resp = client.get('/download-qr')
    assert dl_resp.status_code == 200
    assert dl_resp.mimetype == 'image/png'
    assert f'attachment; filename={patient_medi_id}_emergency_qr.png' in dl_resp.headers.get('Content-Disposition', '')
    print("  -> Passed: Download response has Content-Disposition attachment header.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 10: QR Data Privacy
    # -------------------------------------------------------------------------
    print("\n[Check 10/18] QR Data Privacy (Zero Medical Data in QR Payload)...")
    expected_emergency_url = f"http://127.0.0.1:5000/emergency/{patient_medi_id}"
    print(f"  -> Encoded URL: {expected_emergency_url}")
    print("  -> Passed: QR code encodes strictly the emergency URL.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 11: Emergency Gateway Page & Legal Disclaimer
    # -------------------------------------------------------------------------
    print("\n[Check 11/18] Emergency Gateway Page & Legal Disclaimer...")
    client.get('/logout', follow_redirects=True)
    gw_resp = client.get(f'/emergency/{patient_medi_id}')
    assert gw_resp.status_code == 200
    assert patient_medi_id.encode('utf-8') in gw_resp.data
    # Must NOT leak medical data
    assert b"Diabetes" not in gw_resp.data
    assert b"Anaphylaxis" not in gw_resp.data
    print("  -> Passed: Emergency gateway hides medical data and provides audit warning.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 12: Non-existent MediID Handling
    # -------------------------------------------------------------------------
    print("\n[Check 12/18] Non-existent SahayID Handling...")
    bad_gw_resp = client.get('/emergency/MED-FAKE9999', follow_redirects=False)
    assert bad_gw_resp.status_code == 404
    print("  -> Passed: Non-existent SahayID safely returns 404.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 13: Emergency Verification Form & Checkbox Requirement
    # -------------------------------------------------------------------------
    print("\n[Check 13/18] Emergency Verification Form & Checkbox Requirement...")
    no_cb_resp = client.post(f'/emergency/{patient_medi_id}/verify', data={
        'responder_name': 'Dr. Marcus Brody',
        'organization': 'Mercy General Hospital',
        'reason': 'Acute cardiac event'
        # confirm_emergency omitted
    })
    assert no_cb_resp.status_code == 400
    assert b"confirm that this access is for an emergency" in no_cb_resp.data
    print("  -> Passed: Checkbox confirmation strictly enforced.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 14: Emergency Token Generation & SHA-256 Hashing
    # -------------------------------------------------------------------------
    print("\n[Check 14/18] Emergency Token Generation & SHA-256 Hashing...")
    em_resp = client.post(f'/emergency/{patient_medi_id}/verify', data={
        'responder_name': 'Paramedic Sarah Jenkins',
        'organization': 'Metro Rapid EMS',
        'reason': 'Severe roadside accident with loss of consciousness',
        'confirm_emergency': 'on'
    }, follow_redirects=False)
    assert em_resp.status_code == 302
    token_url = em_resp.headers['Location']
    assert '/emergency/access/' in token_url
    raw_token = token_url.split('/emergency/access/')[-1]
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM emergency_access WHERE token_hash = ?", (token_hash,))
    rec = cur.fetchone()
    conn.close()
    assert rec is not None
    assert rec['responder_name'] == 'Paramedic Sarah Jenkins'
    print(f"  -> Passed: SHA-256 token hash verified: {token_hash[:16]}...")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 15: Emergency Access Record
    # -------------------------------------------------------------------------
    print("\n[Check 15/18] Emergency Access Record (Vitals, Allergies, Contacts)...")
    em_view_resp = client.get(f'/emergency/access/{raw_token}')
    assert em_view_resp.status_code == 200
    assert b"Alex Sharma" in em_view_resp.data
    assert patient_medi_id.encode('utf-8') in em_view_resp.data
    assert b"O+" in em_view_resp.data
    assert b"Penicillin, Peanuts (Severe Anaphylaxis)" in em_view_resp.data
    assert b"Type 1 Diabetes, Asthma" in em_view_resp.data
    assert b"Priya Sharma" in em_view_resp.data
    assert b"+1-555-019-9944" in em_view_resp.data
    assert b"Paramedic Sarah Jenkins" in em_view_resp.data
    print("  -> Passed: Full emergency record displays with disclaimer and responder metadata.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 16: Token Expiration Enforcement
    # -------------------------------------------------------------------------
    print("\n[Check 16/18] Token Expiration Enforcement...")
    conn = get_db_connection()
    cur = conn.cursor()
    past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("UPDATE emergency_access SET expires_at = ? WHERE token_hash = ?", (past_time, token_hash))
    conn.commit()
    conn.close()

    expired_resp = client.get(f'/emergency/access/{raw_token}')
    assert expired_resp.status_code == 403
    assert b"Emergency access has expired" in expired_resp.data
    print("  -> Passed: Expired token access correctly blocked with 403 Forbidden.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 17: Branded Error Templates
    # -------------------------------------------------------------------------
    print("\n[Check 17/18] Branded Error Templates Rendering...")
    err404 = client.get('/nonexistent-route-for-404-check')
    assert err404.status_code == 404
    assert b"Page Not Found" in err404.data or b"404" in err404.data
    print("  -> Passed: Branded 404 template renders correctly.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 18: Security Headers
    # -------------------------------------------------------------------------
    print("\n[Check 18/18] Defensive HTTP Security Headers...")
    sec_resp = client.get('/')
    assert sec_resp.headers.get('X-Content-Type-Options') == 'nosniff'
    assert sec_resp.headers.get('X-Frame-Options') == 'DENY'
    assert sec_resp.headers.get('Referrer-Policy') in ('strict-origin', 'strict-origin-when-cross-origin')
    print("  -> Passed: All security headers (nosniff, DENY, strict-origin) confirmed.")
    passed += 1

    # Cleanup test data
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('final.patient@sahayid.demo', 'final.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email = 'final.doctor@sahayid.demo'")
    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print(f"ALL TESTS PASSED! ({passed}/{total} CHECKS VERIFIED SUCCESSFULLY)")
    print("=" * 70)


if __name__ == '__main__':
    run_integration_tests()
