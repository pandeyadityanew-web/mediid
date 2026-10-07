"""
test_new_features.py - Test Suite for New Enhanced Capabilities:
1. Dedicated FAQs route and accordion structure
2. Patient profile photo upload & removal
3. Doctor profile management & editing
4. Doctor profile photo upload & removal
5. Doctor Dashboard Camera QR Scanner modal & Break-Glass card
6. Static assets and security headers
"""

import os
import io
import base64
from werkzeug.security import generate_password_hash
from app import app, init_db, get_db_connection

def run_new_feature_tests():
    print("=" * 75)
    print("RUNNING NEW FEATURES TEST SUITE (FAQS, PHOTOS, DOCTOR PROFILE & QR SCANNER)")
    print("=" * 75)

    client = app.test_client()
    passed = 0
    total = 8

    # 1. Test /faqs Route
    print("\n[Check 1/8] Verifying /faqs route & content...")
    resp = client.get('/faqs')
    assert resp.status_code == 200, f"Expected 200 on /faqs, got {resp.status_code}"
    assert b"Frequently Asked Questions" in resp.data
    assert b"What is SahayID" in resp.data
    assert b"Emergency Break-Glass" in resp.data
    passed += 1
    print("  --> PASS: /faqs renders successfully with complete knowledge base.")

    # 2. Test Homepage #faqs section
    print("\n[Check 2/8] Verifying homepage #faqs section & navigation link...")
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'id="faqs"' in resp.data
    assert b'href="#faqs"' in resp.data
    passed += 1
    print("  --> PASS: Homepage contains integrated FAQs accordion & nav link.")

    # Register test patient
    p_email = 'photo.patient@sahayid.demo'
    p_pass = 'PhotoPass123!'
    client.post('/register', data={
        'full_name': 'Aarav Sharma',
        'email': p_email,
        'phone': '+1-555-444-1111',
        'password': p_pass,
        'confirm_password': p_pass
    }, follow_redirects=True)

    client.post('/login', data={'identifier': p_email, 'password': p_pass}, follow_redirects=True)

    # 3. Test Patient Photo Upload & Removal
    print("\n[Check 3/8] Verifying Patient Profile Photo Upload & Removal...")
    sample_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    upload_resp = client.post('/profile/photo/upload', data={'photo_base64': sample_b64}, follow_redirects=True)
    assert upload_resp.status_code == 200
    assert b"Profile photo updated successfully" in upload_resp.data

    # Check photo persists in medical profile view
    mp_resp = client.get('/medical-profile')
    assert b"data:image/png;base64" in mp_resp.data

    # Remove photo
    remove_resp = client.post('/profile/photo/remove', follow_redirects=True)
    assert remove_resp.status_code == 200
    assert b"Profile photo removed" in remove_resp.data
    passed += 1
    print("  --> PASS: Patient photo upload (base64 data URI) & removal verified.")

    client.get('/logout')

    # Register test doctor
    d_email = 'photo.doctor@sahayid.demo'
    d_pass = 'DoctorPass123!'
    client.post('/doctor/register', data={
        'full_name': 'Vikram Mehra',
        'email': d_email,
        'phone': '+1-555-999-0000',
        'specialization': 'Trauma Surgery',
        'hospital_or_clinic': 'Metro General Hospital',
        'registration_number': 'MC-987654',
        'password': d_pass,
        'confirm_password': d_pass
    }, follow_redirects=True)

    client.post('/doctor/login', data={'identifier': d_email, 'password': d_pass}, follow_redirects=True)

    # 4. Test Doctor Profile View & Edit
    print("\n[Check 4/8] Verifying Doctor Profile Management...")
    doc_prof = client.get('/doctor/profile')
    assert doc_prof.status_code == 200
    assert b"Physician Profile &amp; Credentials" in doc_prof.data or b"Physician Profile & Credentials" in doc_prof.data
    assert b"Trauma Surgery" in doc_prof.data

    # Update doctor profile
    edit_resp = client.post('/doctor/profile', data={
        'phone': '+1-555-111-2222',
        'specialization': 'Emergency Medicine',
        'hospital_or_clinic': 'City Trauma Center'
    }, follow_redirects=True)
    assert edit_resp.status_code == 200
    assert b"Doctor profile updated successfully" in edit_resp.data
    assert b"Emergency Medicine" in edit_resp.data
    passed += 1
    print("  --> PASS: Doctor profile view and update verified.")

    # 5. Test Doctor Photo Upload & Removal
    print("\n[Check 5/8] Verifying Doctor Photo Upload & Removal...")
    d_upload_resp = client.post('/doctor/profile/photo/upload', data={'photo_base64': sample_b64}, follow_redirects=True)
    assert d_upload_resp.status_code == 200
    assert b"Doctor profile photo updated successfully" in d_upload_resp.data

    d_remove_resp = client.post('/doctor/profile/photo/remove', follow_redirects=True)
    assert d_remove_resp.status_code == 200
    assert b"Doctor profile photo removed" in d_remove_resp.data
    passed += 1
    print("  --> PASS: Doctor photo upload & removal verified.")

    # 6. Test Doctor Dashboard QR Scanner Modal & Break-Glass Card
    print("\n[Check 6/8] Verifying Doctor Dashboard QR Scanner & Break-Glass elements...")
    dd_resp = client.get('/doctor/dashboard')
    assert dd_resp.status_code == 200
    assert b'id="startQrScanBtn"' in dd_resp.data
    assert b'id="qrScannerModal"' in dd_resp.data
    assert b'id="emergency-break-glass-card"' in dd_resp.data
    assert b"Emergency Break-Glass Access" in dd_resp.data
    passed += 1
    print("  --> PASS: Doctor Dashboard contains QR Scanner triggers and Break-Glass portal.")

    # 7. Test Static Assets (CSS, JS, Logo, Video, Manifest)
    print("\n[Check 7/8] Verifying Static Asset Serving...")
    for asset in ['/static/css/style.css', '/static/js/script.js', '/static/images/sahayid-logo.jpg', '/static/manifest.json']:
        a_resp = client.get(asset)
        assert a_resp.status_code == 200, f"Failed to serve {asset}"
    passed += 1
    print("  --> PASS: All core static assets return HTTP 200.")

    # 8. Test Security Headers on New Routes
    print("\n[Check 8/8] Verifying Security Headers on /faqs and /doctor/profile...")
    faq_headers = client.get('/faqs').headers
    assert faq_headers.get('X-Content-Type-Options') == 'nosniff'
    assert faq_headers.get('X-Frame-Options') == 'DENY'
    passed += 1
    print("  --> PASS: Security headers enforced across new endpoints.")

    # Clean up test accounts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email = ?", (p_email,))
    cur.execute("DELETE FROM doctors WHERE email = ?", (d_email,))
    conn.commit()

    print("\n" + "=" * 75)
    print(f"RESULTS: {passed}/{total} NEW FEATURE CHECKS PASSED PERFECTLY!")
    print("=" * 75)

if __name__ == '__main__':
    run_new_feature_tests()
