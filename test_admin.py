"""
test_admin.py - Comprehensive Test Suite for SahayID Admin Verification Portal

Tests:
1. Master Admin Seed in DB on initialization
2. Admin Login (/admin/login) GET & Form rendering
3. Admin Authentication with valid username and email credentials
4. Invalid Admin Authentication handling and failed-login audit logging
5. Server-side role enforcement on /admin & /admin/dashboard (unauthenticated redirect)
6. Cross-role enforcement: Patient accounts denied /admin access
7. Cross-role enforcement: Doctor accounts denied /admin access
8. Cross-role enforcement: Admin accounts redirected from patient/doctor dashboards
9. Doctor registration initial pending status
10. Admin Doctor Approval workflow & DOCTOR_APPROVED audit log
11. Admin Doctor Rejection with required reason & DOCTOR_REJECTED audit log
12. Doctor portal displays rejection reason on doctor dashboard
13. Admin Sign Out (/admin/logout) session clearance
"""

import sys
import os
from werkzeug.security import generate_password_hash
from app import app, init_db, get_db_connection

def run_admin_portal_tests():
    print("=" * 80)
    print("RUNNING SAHAYID ADMIN VERIFICATION PORTAL TEST SUITE")
    print("=" * 80)

    # Initialize DB and seed
    init_db()
    client = app.test_client()
    passed = 0
    total = 13

    # 1. Master Admin Seeding Verification
    print("\n[Check 1/13] Verifying master admin account seeded in database...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email FROM admins WHERE username = 'admin' OR email = 'admin@sahayid.org'")
    admin_row = cur.fetchone()
    conn.close()
    assert admin_row is not None, "Master admin account not found in database!"
    print(f"  --> PASS: Master admin account exists (ID: {admin_row['id']}, Email: {admin_row['email']})")
    passed += 1

    # 2. Public Navigation Check & Admin Login Page
    print("\n[Check 2/13] Verifying /admin/login endpoint and absence from public navbar...")
    resp_home = client.get('/')
    assert resp_home.status_code == 200
    assert b'href="/admin/login"' not in resp_home.data, "Admin login must NOT be exposed in public navigation!"
    
    resp_login = client.get('/admin/login')
    assert resp_login.status_code == 200
    assert b"Admin Console Login" in resp_login.data
    assert b"Master Password" in resp_login.data
    print("  --> PASS: Admin login route is accessible; public navigation remains clean.")
    passed += 1

    # 3. Admin Authentication (Username & Email)
    print("\n[Check 3/13] Verifying admin authentication with master credentials...")
    resp_auth_user = client.post('/admin/login', data={
        'identifier': 'admin',
        'password': 'AdminSahay@2026!'
    }, follow_redirects=False)
    assert resp_auth_user.status_code == 302
    assert '/admin' in resp_auth_user.headers['Location']

    with client.session_transaction() as sess:
        assert sess.get('role') == 'admin'
        assert sess.get('admin_id') is not None
        assert sess.get('username') == 'admin'
    
    client.get('/admin/logout')

    resp_auth_email = client.post('/admin/login', data={
        'identifier': 'admin@sahayid.org',
        'password': 'AdminSahay@2026!'
    }, follow_redirects=False)
    assert resp_auth_email.status_code == 302
    print("  --> PASS: Authentication succeeds using both username and email.")
    passed += 1

    # 4. Invalid Admin Authentication Handling & Audit Log
    print("\n[Check 4/13] Verifying invalid credentials rejection & audit trail...")
    client.get('/admin/logout')
    resp_bad = client.post('/admin/login', data={
        'identifier': 'admin',
        'password': 'WrongPassword123!'
    }, follow_redirects=True)
    assert resp_bad.status_code == 401
    assert b"Invalid administrator credentials" in resp_bad.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_logs WHERE access_type = 'ADMIN_LOGIN_FAILED' ORDER BY id DESC LIMIT 1")
    bad_log = cur.fetchone()
    conn.close()
    assert bad_log is not None, "Failed admin login was not recorded in access_logs!"
    print("  --> PASS: Invalid admin credentials return HTTP 401 and log audit event.")
    passed += 1

    # 5. Role-Based Route Protection (Unauthenticated Access Denied)
    print("\n[Check 5/13] Verifying unauthenticated access to /admin is blocked...")
    client.get('/admin/logout')
    resp_unauth = client.get('/admin', follow_redirects=False)
    assert resp_unauth.status_code == 302
    assert '/admin/login' in resp_unauth.headers['Location']

    resp_unauth_dash = client.get('/admin/dashboard', follow_redirects=False)
    assert resp_unauth_dash.status_code == 302
    assert '/admin/login' in resp_unauth_dash.headers['Location']
    print("  --> PASS: Unauthenticated access safely redirected to /admin/login.")
    passed += 1

    # 6. Patient Role Cannot Access Admin Dashboard
    print("\n[Check 6/13] Verifying patient accounts cannot access /admin...")
    patient_email = "test.patient.for.admin@sahayid.demo"
    patient_pass = "PatientPass123!"
    client.post('/register', data={
        'full_name': 'Test Patient',
        'email': patient_email,
        'phone': '+1-555-0199',
        'password': patient_pass,
        'confirm_password': patient_pass
    }, follow_redirects=True)
    client.post('/login', data={'identifier': patient_email, 'password': patient_pass}, follow_redirects=True)

    resp_patient_on_admin = client.get('/admin', follow_redirects=False)
    assert resp_patient_on_admin.status_code == 302
    assert '/dashboard' in resp_patient_on_admin.headers['Location']
    print("  --> PASS: Patient role strictly blocked from administrative routes.")
    passed += 1

    # 7. Doctor Role Cannot Access Admin Dashboard
    print("\n[Check 7/13] Verifying doctor accounts cannot access /admin...")
    client.get('/logout')
    doc_email = "test.doc.for.admin@hospital.org"
    doc_pass = "DoctorPass123!"
    client.post('/doctor/register', data={
        'full_name': 'Vikram Mehra',
        'email': doc_email,
        'phone': '+1-555-0288',
        'specialization': 'Emergency Medicine',
        'hospital_or_clinic': 'Metro Trauma Center',
        'registration_number': 'MCI-998877',
        'password': doc_pass,
        'confirm_password': doc_pass
    }, follow_redirects=True)
    client.post('/doctor/login', data={'identifier': doc_email, 'password': doc_pass}, follow_redirects=True)

    resp_doc_on_admin = client.get('/admin', follow_redirects=False)
    assert resp_doc_on_admin.status_code == 302
    assert '/doctor/dashboard' in resp_doc_on_admin.headers['Location']
    print("  --> PASS: Doctor role strictly blocked from administrative routes.")
    passed += 1

    # 8. Admin Role Redirected from Doctor/Patient Portals
    print("\n[Check 8/13] Verifying admin accounts redirected from patient & doctor dashboards...")
    client.get('/doctor/logout')
    client.post('/admin/login', data={'identifier': 'admin', 'password': 'AdminSahay@2026!'}, follow_redirects=True)

    resp_adm_to_doc = client.get('/doctor/dashboard', follow_redirects=False)
    assert resp_adm_to_doc.status_code == 302
    assert '/admin' in resp_adm_to_doc.headers['Location']

    resp_adm_to_pat = client.get('/dashboard', follow_redirects=False)
    assert resp_adm_to_pat.status_code == 302
    assert '/admin' in resp_adm_to_pat.headers['Location']
    print("  --> PASS: Admin accounts redirected from clinical and patient portals.")
    passed += 1

    # 9. Doctor Registration Initial Pending Status
    print("\n[Check 9/13] Verifying newly registered doctor starts in 'pending' status...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, verification_status FROM doctors WHERE email = ?", (doc_email,))
    doc_row = cur.fetchone()
    conn.close()
    assert doc_row is not None
    assert doc_row['verification_status'] == 'pending'
    doc_id = doc_row['id']
    print(f"  --> PASS: Doctor {doc_row['full_name']} registered with verification_status = 'pending'.")
    passed += 1

    # 10. Admin Approving Doctor Workflow
    print("\n[Check 10/13] Verifying admin approval workflow & DOCTOR_APPROVED audit log...")
    resp_approve = client.post(f'/admin/doctor/{doc_id}/approve', follow_redirects=True)
    assert resp_approve.status_code == 200
    assert b"has been approved" in resp_approve.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT verification_status, verified_at, verified_by FROM doctors WHERE id = ?", (doc_id,))
    doc_updated = cur.fetchone()
    cur.execute("SELECT * FROM access_logs WHERE doctor_id = ? AND access_type = 'DOCTOR_APPROVED'", (doc_id,))
    approve_log = cur.fetchone()
    conn.close()

    assert doc_updated['verification_status'] == 'verified'
    assert doc_updated['verified_at'] is not None
    assert approve_log is not None
    assert "Physician credentials verified" in approve_log['reason']
    print(f"  --> PASS: Doctor approved (status='verified') and audit logged.")
    passed += 1

    # 11. Admin Rejecting Doctor Workflow with Custom Reason
    print("\n[Check 11/13] Verifying admin rejection workflow with required reason...")
    doc2_email = "fake.doc.for.admin@unverified.org"
    doc2_pass = "FakePass123!"
    client.post('/doctor/register', data={
        'full_name': 'Suspect Practitioner',
        'email': doc2_email,
        'phone': '+1-555-0999',
        'specialization': 'General Practice',
        'hospital_or_clinic': 'Unverified Clinic',
        'registration_number': 'REG-INVALID-000',
        'password': doc2_pass,
        'confirm_password': doc2_pass
    }, follow_redirects=True)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM doctors WHERE email = ?", (doc2_email,))
    doc2_row = cur.fetchone()
    conn.close()
    doc2_id = doc2_row['id']

    # Sign in as admin to reject
    client.post('/admin/login', data={'identifier': 'admin', 'password': 'AdminSahay@2026!'}, follow_redirects=True)
    rejection_reason = "Medical registration number could not be validated against National Medical Commission database."
    resp_reject = client.post(f'/admin/doctor/{doc2_id}/reject', data={
        'rejection_reason': rejection_reason
    }, follow_redirects=True)
    assert resp_reject.status_code == 200
    assert b"has been rejected" in resp_reject.data

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT verification_status, verification_reason FROM doctors WHERE id = ?", (doc2_id,))
    doc2_updated = cur.fetchone()
    cur.execute("SELECT * FROM access_logs WHERE doctor_id = ? AND access_type = 'DOCTOR_REJECTED'", (doc2_id,))
    reject_log = cur.fetchone()
    conn.close()

    assert doc2_updated['verification_status'] == 'rejected'
    assert doc2_updated['verification_reason'] == rejection_reason
    assert reject_log is not None
    assert rejection_reason in reject_log['reason']
    print("  --> PASS: Doctor rejected with custom reason recorded and audit logged.")
    passed += 1

    # 12. Doctor Portal Displays Rejection Reason
    print("\n[Check 12/13] Verifying doctor dashboard displays rejection banner and reason...")
    client.get('/admin/logout')
    client.post('/doctor/login', data={'identifier': doc2_email, 'password': doc2_pass}, follow_redirects=True)
    resp_doc_dash = client.get('/doctor/dashboard')
    assert resp_doc_dash.status_code == 200
    assert b"Verification Decision: Application Rejected." in resp_doc_dash.data
    assert rejection_reason.encode('utf-8') in resp_doc_dash.data
    print("  --> PASS: Rejected doctor dashboard displays rejection alert banner and explanation.")
    passed += 1

    # 13. Admin Sign Out Flow
    print("\n[Check 13/13] Verifying admin logout clears session...")
    client.post('/admin/login', data={'identifier': 'admin', 'password': 'AdminSahay@2026!'}, follow_redirects=True)
    resp_logout = client.get('/admin/logout', follow_redirects=False)
    assert resp_logout.status_code == 302
    assert '/admin/login' in resp_logout.headers['Location']

    with client.session_transaction() as sess:
        assert 'admin_id' not in sess
        assert 'role' not in sess
    print("  --> PASS: Admin sign out completely clears credentials and session.")
    passed += 1

    print("\n" + "=" * 80)
    print(f"RESULTS: {passed}/{total} ADMIN PORTAL CHECKS PASSED PERFECTLY!")
    print("=" * 80)
    return True

if __name__ == '__main__':
    success = run_admin_portal_tests()
    sys.exit(0 if success else 1)
