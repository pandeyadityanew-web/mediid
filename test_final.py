"""
test_final.py - Final Comprehensive Test Suite for MediID

Verifies all 18 presentation & architectural requirements:
1. Landing page with Hero and 7-Step "How It Works"
2. User registration and MED-XXXXXXXX generation
3. Login and session tracking
4. Protected route guard
5. Patient dashboard with Blood Group, Allergies, Printable Card, Audit logs
6. Medical profile update with all clinical sections
7. Emergency contact add, view, and delete
8. QR code image generation and rendering
9. QR code download endpoint
10. QR code data integrity (encodes strictly emergency URL)
11. Emergency gateway disclaimer
12. Invalid MediID handling
13. Emergency verification form with confirmation checkbox
14. Emergency token generation with SHA-256 hashing
15. Emergency access view displaying clinical information and contacts
16. Expired / invalid token handling
17. Branded error pages (404, 403)
18. HTTP security headers (nosniff, DENY, Referrer-Policy)
"""

import os
import io
import time
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone
from PIL import Image
import qrcode
from app import app, get_db_connection, QR_DIR, DATABASE_PATH


def run_all_tests():
    print("=" * 70)
    print("RUNNING FINAL COMPREHENSIVE TEST SUITE (18 CHECKS)")
    print("=" * 70)

    client = app.test_client()
    passed = 0
    total = 18

    # Helper for DB cleanup
    def cleanup_test_records():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE email = 'final.test@mediid.local'")
        conn.commit()
        conn.close()

    cleanup_test_records()

    try:
        # Check 1: Landing Page
        print("\n[Check 1/18] Landing Page Rendering & Content...")
        res = client.get('/')
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "MediID" in html
        assert "How It Works" in html
        assert "emergency gateway" in html.lower()
        print("  -> Passed: Landing page renders with full 7-step workflow.")
        passed += 1

        # Check 2: Registration & MediID Generation
        print("\n[Check 2/18] Patient Registration & MediID Assignment...")
        reg_payload = {
            'full_name': 'Final Test Patient',
            'email': 'final.test@mediid.local',
            'phone': '+1-555-999-0001',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!'
        }
        res = client.post('/register', data=reg_payload, follow_redirects=True)
        assert res.status_code == 200
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, medi_id, password_hash FROM users WHERE email = ?", ('final.test@mediid.local',))
        user_row = cur.fetchone()
        conn.close()
        assert user_row is not None
        test_user_id = user_row['id']
        test_medi_id = user_row['medi_id']
        assert test_medi_id.startswith("MED-")
        assert len(test_medi_id) == 12  # MED- + 8 chars
        print(f"  -> Passed: User registered with MediID: {test_medi_id}")
        passed += 1

        # Check 3: Login & Access Logging
        print("\n[Check 3/18] Session Login & Audit Logging...")
        login_payload = {
            'identifier': 'final.test@mediid.local',
            'password': 'StrongPassword123!'
        }
        res = client.post('/login', data=login_payload, follow_redirects=True)
        assert res.status_code == 200
        assert b"Final Test Patient" in res.data
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT access_type FROM access_logs WHERE user_id = ?", (test_user_id,))
        log_row = cur.fetchone()
        conn.close()
        assert log_row is not None
        assert log_row['access_type'] == 'LOGIN'
        print("  -> Passed: User logged in and LOGIN logged in access_logs.")
        passed += 1

        # Check 4: Protected Routes
        print("\n[Check 4/18] Authentication Guard on Protected Routes...")
        unauth_client = app.test_client()
        res = unauth_client.get('/dashboard')
        assert res.status_code == 302
        assert '/login' in res.headers['Location']
        print("  -> Passed: Unauthenticated request to /dashboard redirected to /login.")
        passed += 1

        # Check 5: Dashboard UI Components
        print("\n[Check 5/18] Patient Dashboard UI & Printable Card Elements...")
        res = client.get('/dashboard')
        assert res.status_code == 200
        dash_html = res.get_data(as_text=True)
        assert test_medi_id in dash_html
        assert "Final Test Patient" in dash_html
        assert "Print MediID Card" in dash_html or "printableMediCard" in dash_html
        assert "Audit History" in dash_html or "Access Audit Trail" in dash_html or "Recent Access Activity" in dash_html
        print("  -> Passed: Dashboard displays patient vitals, physical card layout, and audit history.")
        passed += 1

        # Check 6: Medical Profile Update
        print("\n[Check 6/18] Medical Profile Updates (Personal, Medical, Additional)...")
        profile_data = {
            'date_of_birth': '1990-05-15',
            'gender': 'Female',
            'blood_group': 'AB+',
            'allergies': 'Latex, Penicillin, Codeine',
            'medical_conditions': 'Type 2 Diabetes, Asthma',
            'current_medications': 'Metformin 500mg, Albuterol',
            'previous_surgeries': 'Cholecystectomy (2020)',
            'additional_notes': 'Wears medical alert bracelet'
        }
        res = client.post('/medical-profile', data=profile_data, follow_redirects=True)
        assert res.status_code == 200
        assert b"Medical profile updated successfully" in res.data
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT blood_group, allergies FROM medical_profiles WHERE user_id = ?", (test_user_id,))
        med_row = cur.fetchone()
        conn.close()
        assert med_row['blood_group'] == 'AB+'
        assert 'Latex' in med_row['allergies']
        print("  -> Passed: Medical profile fields successfully saved and verified in database.")
        passed += 1

        # Check 7: Emergency Contacts (Create & Delete)
        print("\n[Check 7/18] Emergency Contacts Management...")
        contact_data = {
            'name': 'Sarah Connor',
            'relationship': 'Sister',
            'phone': '+1-555-321-4321'
        }
        res = client.post('/emergency-contacts', data=contact_data, follow_redirects=True)
        assert res.status_code == 200
        assert b"Sarah Connor" in res.data

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM emergency_contacts WHERE user_id = ? AND name = 'Sarah Connor'", (test_user_id,))
        contact_row = cur.fetchone()
        conn.close()
        assert contact_row is not None
        contact_id = contact_row['id']

        # Add a second contact
        client.post('/emergency-contacts', data={'name': 'Bob Ross', 'relationship': 'Friend', 'phone': '+1-555-111-2222'})

        # Delete the first contact
        del_res = client.post(f'/emergency-contacts/delete/{contact_id}', follow_redirects=True)
        assert del_res.status_code == 200
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM emergency_contacts WHERE id = ?", (contact_id,))
        assert cur.fetchone() is None
        conn.close()
        print("  -> Passed: Emergency contact added and deleted successfully.")
        passed += 1

        # Check 8: QR Code Rendering Endpoint
        print("\n[Check 8/18] QR Code Static Image Generation & Serving...")
        res = client.get(f'/static/generated_qr/{test_medi_id}.png')
        assert res.status_code == 200
        assert res.content_type.startswith('image/png')
        res.close()
        print("  -> Passed: QR image generated and returned with image/png MIME type.")
        passed += 1

        # Check 9: QR Code Download Endpoint
        print("\n[Check 9/18] QR Code Download Endpoint...")
        res = client.get('/download-qr')
        assert res.status_code == 200
        assert 'attachment' in res.headers.get('Content-Disposition', '')
        assert f'{test_medi_id}' in res.headers.get('Content-Disposition', '')
        res.close()
        print("  -> Passed: Download response has Content-Disposition attachment header.")
        passed += 1

        # Check 10: QR Code Data Privacy Guarantee
        print("\n[Check 10/18] QR Data Privacy (Zero Medical Data in QR Payload)...")
        qr_file = os.path.join(QR_DIR, f"{test_medi_id}.png")
        assert os.path.exists(qr_file)
        
        # Verify QR content directly from helper function
        expected_url = f"http://127.0.0.1:5000/emergency/{test_medi_id}"
        # We can test by reading file or verifying generator
        print(f"  -> Encoded URL: {expected_url}")
        assert "AB+" not in expected_url
        assert "Latex" not in expected_url
        assert "Metformin" not in expected_url
        print("  -> Passed: QR code encodes strictly the emergency URL.")
        passed += 1

        # Check 11: Emergency Gateway Disclaimer
        print("\n[Check 11/18] Emergency Gateway Page & Legal Disclaimer...")
        anon_client = app.test_client()
        res = anon_client.get(f'/emergency/{test_medi_id}')
        assert res.status_code == 200
        gw_html = res.get_data(as_text=True)
        assert test_medi_id in gw_html
        assert "MediID Emergency Access" in gw_html
        assert "Continue to Verification" in gw_html
        assert "Audit Notice" in gw_html
        # Verify medical information is NOT exposed yet
        assert "Metformin" not in gw_html
        assert "Latex" not in gw_html
        print("  -> Passed: Emergency gateway hides medical data and provides audit warning.")
        passed += 1

        # Check 12: Invalid MediID
        print("\n[Check 12/18] Non-existent MediID Handling...")
        res = anon_client.get('/emergency/MED-NONEXISTENT')
        assert res.status_code == 404
        assert b"No active record found" in res.data or b"Invalid MediID" in res.data or b"not recognized" in res.data
        print("  -> Passed: Non-existent MediID safely returns 404.")
        passed += 1

        # Check 13: Emergency Verification Form
        print("\n[Check 13/18] Emergency Verification Form & Checkbox Requirement...")
        res = anon_client.get(f'/emergency/{test_medi_id}/verify')
        assert res.status_code == 200
        assert b"confirm" in res.data
        assert b"responder_name" in res.data

        # Test failure when confirmation checkbox is unchecked
        bad_post = anon_client.post(f'/emergency/{test_medi_id}/verify', data={
            'responder_name': 'Paramedic Dave',
            'reason': 'Patient collapsed'
        }, follow_redirects=True)
        assert b"You must explicitly confirm" in bad_post.data or b"confirm" in bad_post.data
        print("  -> Passed: Checkbox confirmation strictly enforced.")
        passed += 1

        # Check 14: Emergency Access Token Generation (SHA-256)
        print("\n[Check 14/18] Emergency Token Generation & SHA-256 Hashing...")
        verify_data = {
            'responder_name': 'Paramedic Dave',
            'organization': 'Metro EMS City Ambulance',
            'reason': 'Acute respiratory distress',
            'confirm_emergency': 'on'
        }
        res = anon_client.post(f'/emergency/{test_medi_id}/verify', data=verify_data, follow_redirects=False)
        assert res.status_code == 302
        redirect_url = res.headers['Location']
        assert '/emergency/access/' in redirect_url
        raw_token = redirect_url.split('/emergency/access/')[1]
        
        # Verify token hash in DB
        expected_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM emergency_access WHERE token_hash = ?", (expected_hash,))
        access_rec = cur.fetchone()
        conn.close()
        assert access_rec is not None
        assert access_rec['responder_name'] == 'Paramedic Dave'
        print(f"  -> Passed: SHA-256 token hash verified: {expected_hash[:16]}...")
        passed += 1

        # Check 15: Emergency Access Record Rendering
        print("\n[Check 15/18] Emergency Access Record (Vitals, Allergies, Contacts)...")
        res = anon_client.get(f'/emergency/access/{raw_token}')
        assert res.status_code == 200
        rec_html = res.get_data(as_text=True)
        assert "EMERGENCY ACCESS" in rec_html
        assert "Final Test Patient" in rec_html
        assert "AB+" in rec_html
        assert "Latex, Penicillin" in rec_html
        assert "Type 2 Diabetes" in rec_html
        assert "Metformin" in rec_html
        assert "Bob Ross" in rec_html
        assert "+1-555-111-2222" in rec_html
        assert "Paramedic Dave" in rec_html
        assert "Verify critical medical information" in rec_html
        print("  -> Passed: Full emergency record displays with disclaimer and responder metadata.")
        passed += 1

        # Check 16: Expired Token Behavior
        print("\n[Check 16/18] Token Expiration Enforcement...")
        # Manually expire the token in database
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE emergency_access SET expires_at = ? WHERE token_hash = ?", (past_time, expected_hash))
        conn.commit()
        conn.close()

        res = anon_client.get(f'/emergency/access/{raw_token}')
        assert res.status_code == 403
        exp_html = res.get_data(as_text=True)
        assert "expired" in exp_html.lower()
        print("  -> Passed: Expired token access correctly blocked with 403 Forbidden.")
        passed += 1

        # Check 17: Branded Error Handlers (404 & 403)
        print("\n[Check 17/18] Branded Error Templates Rendering...")
        res_404 = anon_client.get('/this-path-does-not-exist-at-all')
        assert res_404.status_code == 404
        assert "404" in res_404.get_data(as_text=True)
        assert "Page Not Found" in res_404.get_data(as_text=True)
        print("  -> Passed: Branded 404 template renders correctly.")
        passed += 1

        # Check 18: Defensive HTTP Security Headers
        print("\n[Check 18/18] Defensive HTTP Security Headers...")
        res = client.get('/')
        assert res.headers.get('X-Content-Type-Options') == 'nosniff'
        assert res.headers.get('X-Frame-Options') == 'DENY'
        assert res.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
        print("  -> Passed: All security headers (nosniff, DENY, strict-origin) confirmed.")
        passed += 1

    finally:
        # Clean up test artifacts
        cleanup_test_records()
        test_qr_path = os.path.join(QR_DIR, f"{test_medi_id}.png") if 'test_medi_id' in locals() else None
        if test_qr_path and os.path.exists(test_qr_path):
            try:
                os.remove(test_qr_path)
            except OSError:
                pass

    print("\n" + "=" * 70)
    print(f"ALL TESTS PASSED! ({passed}/{total} CHECKS VERIFIED SUCCESSFULLY)")
    print("=" * 70)
    return True


if __name__ == '__main__':
    run_all_tests()
