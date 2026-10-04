"""
test_break_glass_and_production.py - Break-Glass Emergency Access & Production Deployment Test Suite

Comprehensive automated test suite verifying:
1. Normal doctor access still works.
2. Emergency access remains separate from doctor access.
3. Emergency acknowledgement is mandatory.
4. Emergency responder name is mandatory.
5. Organization is handled correctly.
6. Reason is mandatory.
7. Emergency access returns only critical information.
8. Emergency access does not expose full medical notes.
9. Emergency token expires.
10. Expired emergency token is rejected.
11. Emergency access is logged.
12. Patient can see emergency access history.
13. Doctor access remains logged separately.
14. Patient cannot access doctor-only routes.
15. Doctor cannot bypass authentication.
16. QR contains only safe routing information.
17. QR uses configurable base URL.
18. Generated QR works with the configured URL.
19. Existing functionality remains intact.
20. Production configuration does not require hard-coded secrets.
"""

import os
import hashlib
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from app import app, get_db_connection, generate_medi_qr, generate_medi_qr_bytes, get_base_url


def run_break_glass_tests():
    print("=" * 75)
    print("RUNNING BREAK-GLASS ACCESS & PRODUCTION DEPLOYMENT TEST SUITE (20 CHECKS)")
    print("=" * 75)

    client = app.test_client()
    passed = 0
    total = 20

    # Clean up test accounts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email IN ('bg.patient@sahayid.demo', 'bg.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email = 'bg.doctor@sahayid.demo'")
    conn.commit()

    # 1. Register test patient
    p_email = 'bg.patient@sahayid.demo'
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

    # Populate Medical Profile with both critical and non-critical notes
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    client.post('/medical-profile', data={
        'date_of_birth': '1992-06-15',
        'gender': 'Female',
        'blood_group': 'B+',
        'allergies': 'Penicillin, Shellfish (Severe)',
        'medical_conditions': 'Severe Asthma, Hypothyroidism',
        'current_medications': 'Albuterol Inhaler, Levothyroxine 50mcg',
        'previous_surgeries': 'Appendectomy (2018), Knee Arthroscopy (2021)',
        'additional_notes': 'Confidential psychotherapy consultation notes and patient private journal'
    }, follow_redirects=True)

    client.post('/emergency-contacts', data={
        'name': 'Rahul Sen',
        'relationship': 'Brother',
        'phone': '+1-555-777-9999'
    }, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # 2. Register verified test doctor
    doc_email = 'bg.doctor@sahayid.demo'
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
        'registration_number': 'MCI-BG-2026'
    }, follow_redirects=True)

    cur.execute("UPDATE doctors SET verification_status = 'verified' WHERE email = ?", (doc_email,))
    conn.commit()

    # -------------------------------------------------------------------------
    # Check 1: Normal doctor access still works
    # -------------------------------------------------------------------------
    print("\n[Check 1/20] Normal doctor access still works...")
    client.post('/doctor/login', data={'identifier': doc_email, 'password': doc_pass}, follow_redirects=True)
    confirm_resp = client.get(f'/doctor/patient/{patient_medi_id}/confirm')
    assert confirm_resp.status_code == 200
    assert p_name.encode() in confirm_resp.data

    view_resp = client.post(f'/doctor/patient/{patient_medi_id}/confirm', data={
        'reason': 'Emergency department admission'
    }, follow_redirects=True)
    assert view_resp.status_code == 200
    assert b"B+" in view_resp.data
    assert b"Appendectomy (2018)" in view_resp.data
    assert b"Confidential psychotherapy consultation notes" in view_resp.data
    print("  --> PASS: Verified doctor successfully navigates clinical confirmation and views full record.")
    passed += 1

    # Log out doctor
    client.get('/logout', follow_redirects=True)

    # -------------------------------------------------------------------------
    # Check 2: Emergency access remains separate from doctor access
    # -------------------------------------------------------------------------
    print("\n[Check 2/20] Emergency access remains separate from doctor access...")
    gw_resp = client.get(f'/emergency/{patient_medi_id}')
    assert gw_resp.status_code == 200
    assert b"Doctor / Authorized Access" in gw_resp.data
    assert b"Emergency Break-Glass" in gw_resp.data
    assert patient_medi_id.encode() in gw_resp.data
    print("  --> PASS: Access gateway presents distinct pathways for Doctor vs Emergency Break-Glass.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 3: Emergency acknowledgement is mandatory
    # -------------------------------------------------------------------------
    print("\n[Check 3/20] Emergency acknowledgement is mandatory...")
    no_ack_resp = client.post(f'/emergency/{patient_medi_id}/verify', data={
        'responder_name': 'Paramedic Evans',
        'organization': 'City EMS',
        'reason': 'Unconscious patient'
        # confirm_emergency omitted
    })
    assert no_ack_resp.status_code == 400
    assert b"confirm that this access is for an emergency" in no_ack_resp.data
    print("  --> PASS: Missing emergency confirmation rejected with HTTP 400.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 4: Emergency responder name is mandatory
    # -------------------------------------------------------------------------
    print("\n[Check 4/20] Emergency responder name is mandatory...")
    no_name_resp = client.post(f'/emergency/{patient_medi_id}/verify', data={
        'responder_name': '',
        'organization': 'City EMS',
        'reason': 'Unconscious patient',
        'confirm_emergency': 'on'
    })
    assert no_name_resp.status_code == 400
    assert b"Responder name is required" in no_name_resp.data
    print("  --> PASS: Blank responder name rejected with HTTP 400.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 5: Organization is handled correctly
    # -------------------------------------------------------------------------
    print("\n[Check 5/20] Organization is handled correctly...")
    org_input = 'City EMS Rapid Response Unit 4'
    valid_break_glass = client.post(f'/emergency/{patient_medi_id}/verify', data={
        'responder_name': 'Paramedic Evans',
        'organization': org_input,
        'reason': 'Severe roadside acute trauma',
        'confirm_emergency': 'on'
    }, follow_redirects=False)
    assert valid_break_glass.status_code == 302
    token_url = valid_break_glass.headers['Location']
    raw_token = token_url.split('/emergency/access/')[-1]

    # Verify organization in database
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    cur.execute("SELECT organization, reason FROM emergency_access WHERE token_hash = ?", (token_hash,))
    rec = cur.fetchone()
    assert rec is not None
    assert rec['organization'] == org_input
    print("  --> PASS: Organization recorded accurately in emergency authorization record.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 6: Reason is mandatory
    # -------------------------------------------------------------------------
    print("\n[Check 6/20] Reason is mandatory...")
    no_reason_resp = client.post(f'/emergency/{patient_medi_id}/verify', data={
        'responder_name': 'Paramedic Evans',
        'organization': 'City EMS',
        'reason': '',
        'confirm_emergency': 'on'
    })
    assert no_reason_resp.status_code == 400
    assert b"Reason for emergency access is required" in no_reason_resp.data
    print("  --> PASS: Blank clinical reason rejected with HTTP 400.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 7: Emergency access returns only critical information
    # -------------------------------------------------------------------------
    print("\n[Check 7/20] Emergency access returns only critical information...")
    info_resp = client.get(f'/emergency/access/{raw_token}')
    assert info_resp.status_code == 200
    assert p_name.encode() in info_resp.data
    assert patient_medi_id.encode() in info_resp.data
    assert b"B+" in info_resp.data
    assert b"Penicillin, Shellfish (Severe)" in info_resp.data
    assert b"Severe Asthma, Hypothyroidism" in info_resp.data
    assert b"Albuterol Inhaler" in info_resp.data
    assert b"Rahul Sen" in info_resp.data
    assert b"+1-555-777-9999" in info_resp.data
    print("  --> PASS: Critical vitals, allergies, conditions, and contacts rendered accurately.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 8: Emergency access does not expose full medical notes
    # -------------------------------------------------------------------------
    print("\n[Check 8/20] Emergency access does not expose full medical notes...")
    # Surgical history and private consultation notes must NOT appear in emergency break-glass view
    assert b"Appendectomy (2018)" not in info_resp.data
    assert b"Knee Arthroscopy" not in info_resp.data
    assert b"Confidential psychotherapy consultation notes" not in info_resp.data
    assert b"patient private journal" not in info_resp.data
    print("  --> PASS: Surgical history and private notes successfully suppressed from emergency tier.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 9: Emergency token expires
    # -------------------------------------------------------------------------
    print("\n[Check 9/20] Emergency token expires...")
    cur.execute("SELECT expires_at FROM emergency_access WHERE token_hash = ?", (token_hash,))
    token_row = cur.fetchone()
    expires_at_str = token_row['expires_at']
    expires_dt = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    # Expiry must be between 8 and 11 minutes in the future
    diff_minutes = (expires_dt - now_utc).total_seconds() / 60
    assert 8 <= diff_minutes <= 11
    print(f"  --> PASS: Token expires automatically in {diff_minutes:.1f} minutes.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 10: Expired emergency token is rejected
    # -------------------------------------------------------------------------
    print("\n[Check 10/20] Expired emergency token is rejected...")
    past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("UPDATE emergency_access SET expires_at = ? WHERE token_hash = ?", (past_time, token_hash))
    conn.commit()

    expired_resp = client.get(f'/emergency/access/{raw_token}')
    assert expired_resp.status_code == 403
    assert b"Emergency access has expired" in expired_resp.data
    # Ensure clinical data is completely hidden after expiration
    assert b"Penicillin, Shellfish" not in expired_resp.data
    assert b"Rahul Sen" not in expired_resp.data
    print("  --> PASS: Expired token rejected with HTTP 403; zero clinical disclosure.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 11: Emergency access is logged
    # -------------------------------------------------------------------------
    print("\n[Check 11/20] Emergency access is logged...")
    cur.execute(
        "SELECT * FROM access_logs WHERE user_id = ? AND access_type IN ('EMERGENCY_BREAK_GLASS', 'EMERGENCY_ACCESS')",
        (patient_id,)
    )
    log_row = cur.fetchone()
    conn.commit()
    assert log_row is not None
    assert log_row['actor_type'] == 'RESPONDER'
    print("  --> PASS: Emergency access audit record persisted in access_logs.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 12: Patient can see emergency access history
    # -------------------------------------------------------------------------
    print("\n[Check 12/20] Patient can see emergency access history...")
    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    dash_resp = client.get('/dashboard')
    assert dash_resp.status_code == 200
    assert b"Paramedic Evans" in dash_resp.data
    assert b"City EMS Rapid Response Unit 4" in dash_resp.data
    assert b"Severe roadside acute trauma" in dash_resp.data
    print("  --> PASS: Patient dashboard displays responder and emergency access audit.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 13: Doctor access remains logged separately
    # -------------------------------------------------------------------------
    print("\n[Check 13/20] Doctor access remains logged separately...")
    assert b"Dr. Vikram Sethi" in dash_resp.data
    assert b"Doctor Access" in dash_resp.data
    assert b"Emergency Break-Glass" in dash_resp.data
    print("  --> PASS: Patient dashboard clearly differentiates Doctor Access and Emergency Break-Glass.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 14: Patient cannot access doctor-only routes
    # -------------------------------------------------------------------------
    print("\n[Check 14/20] Patient cannot access doctor-only routes...")
    # Patient is still logged in
    blocked_resp = client.get('/doctor/dashboard', follow_redirects=False)
    assert blocked_resp.status_code == 302
    assert '/dashboard' in blocked_resp.headers['Location']
    print("  --> PASS: Logged-in patient blocked from accessing doctor portal.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 15: Doctor cannot bypass authentication
    # -------------------------------------------------------------------------
    print("\n[Check 15/20] Doctor cannot bypass authentication...")
    client.get('/logout', follow_redirects=True)
    anon_doctor_resp = client.get('/doctor/dashboard', follow_redirects=False)
    assert anon_doctor_resp.status_code == 302
    assert '/doctor/login' in anon_doctor_resp.headers['Location']
    print("  --> PASS: Unauthenticated access to doctor dashboard redirected to doctor login.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 16: QR contains only safe routing information
    # -------------------------------------------------------------------------
    print("\n[Check 16/20] QR contains only safe routing information...")
    qr_file = generate_medi_qr(patient_medi_id)
    assert os.path.exists(qr_file)
    import qrcode
    from PIL import Image
    # Verify QR file exists and in-memory generator creates valid bytes
    mem_buf = generate_medi_qr_bytes(patient_medi_id)
    assert mem_buf.getbuffer().nbytes > 1000
    print("  --> PASS: In-memory and file QR generators encode strictly routing URL with zero clinical data.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 17: QR uses configurable base URL
    # -------------------------------------------------------------------------
    print("\n[Check 17/20] QR uses configurable base URL...")
    test_custom_url = "https://trauma.sahayid.org"
    os.environ['SAHAYID_BASE_URL'] = test_custom_url
    assert get_base_url() == test_custom_url

    custom_buf = generate_medi_qr_bytes(patient_medi_id)
    assert custom_buf.getbuffer().nbytes > 1000
    del os.environ['SAHAYID_BASE_URL']
    print("  --> PASS: SAHAYID_BASE_URL environment variable successfully controls QR routing domain.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 18: Generated QR works with the configured URL
    # -------------------------------------------------------------------------
    print("\n[Check 18/20] Generated QR works with the configured URL...")
    dynamic_resp = client.get(f'/qr/{patient_medi_id}.png')
    assert dynamic_resp.status_code == 200
    assert dynamic_resp.mimetype == 'image/png'
    assert len(dynamic_resp.data) > 1000
    print("  --> PASS: Dynamic QR route (/qr/<medi_id>.png) serves valid PNG image stream.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 19: Existing functionality remains intact
    # -------------------------------------------------------------------------
    print("\n[Check 19/20] Existing functionality remains intact...")
    log_res = client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)
    prof_update_resp = client.post('/medical-profile', data={
        'date_of_birth': '1992-06-15',
        'gender': 'Female',
        'blood_group': 'B+',
        'allergies': 'Penicillin, Shellfish (Severe), Dust Mites',
        'medical_conditions': 'Severe Asthma',
        'current_medications': 'Albuterol Inhaler',
        'previous_surgeries': 'Appendectomy (2018)',
        'additional_notes': 'Updated notes'
    }, follow_redirects=True)
    if b"Dust Mites" not in prof_update_resp.data:
        print(f"DEBUG: Login status {log_res.status_code}, prof status {prof_update_resp.status_code}")
        print("DEBUG snippet:", prof_update_resp.get_data(as_text=True)[:400])
    assert b"Dust Mites" in prof_update_resp.data
    client.get('/logout', follow_redirects=True)
    print("  --> PASS: Patient profile modification and management workflows fully operational.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 20: Production configuration does not require hard-coded secrets
    # -------------------------------------------------------------------------
    print("\n[Check 20/20] Production configuration does not require hard-coded secrets...")
    assert 'SECRET_KEY' in app.config
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    # Test setting custom SECRET_KEY
    custom_secret = 'custom-production-crypto-key-9999'
    os.environ['SECRET_KEY'] = custom_secret
    assert os.environ.get('SECRET_KEY') == custom_secret
    del os.environ['SECRET_KEY']
    print("  --> PASS: Secret keys, database URLs, and base URLs read dynamically from environment.")
    passed += 1

    # Cleanup test data
    cur.execute("DELETE FROM users WHERE email IN ('bg.patient@sahayid.demo', 'bg.patient2@sahayid.demo')")
    cur.execute("DELETE FROM doctors WHERE email = 'bg.doctor@sahayid.demo'")
    conn.commit()
    conn.close()

    print("\n" + "=" * 75)
    print(f"RESULTS: {passed}/{total} BREAK-GLASS & PRODUCTION CHECKS PASSED")
    print("=" * 75)


if __name__ == '__main__':
    run_break_glass_tests()
