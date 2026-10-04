"""
SahayID Patient Dashboard & Profile Management Test Suite
Tests:
1. Unauthenticated user cannot access /dashboard (redirects to /login)
2. Authenticated user can access /dashboard
3. Correct user's SahayID is displayed on dashboard
4. Medical profile retrieval and initial state
5. Medical profile editing via POST
6. Changes persist after logout and re-login
7. Emergency contact can be added
8. Emergency contact can be deleted
9. User A cannot delete User B's emergency contact (authorization / ID tampering check)
10. Profile completion percentage updates dynamically as fields are filled
"""

import sqlite3
from app import app, init_db, get_db_connection, calculate_profile_completion

def run_tests():
    print("=" * 65)
    print("RUNNING SAHAYID PATIENT ACCESS & PROFILE TEST SUITE")
    print("=" * 65)

    init_db()
    client = app.test_client()

    # Clean up test accounts
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpatient.dev'")
    conn.commit()
    conn.close()

    # 1. Unauthenticated Access Protection
    print("\n[TEST 1] Protected Routes Reject Unauthenticated Requests")
    for protected_url in ['/dashboard', '/medical-profile', '/emergency-contacts']:
        resp = client.get(protected_url, follow_redirects=False)
        assert resp.status_code == 302, f"Expected 302 redirect for {protected_url}, got {resp.status_code}"
        assert '/login' in resp.headers['Location'], f"Expected redirect to /login for {protected_url}"
    print("-> Test 1 PASSED: Unauthenticated visitors redirected to /login.")

    # Register User A
    user_a_email = "usera@testpatient.dev"
    user_a_pass = "PasswordA123!"
    reg_a = client.post('/register', data={
        'full_name': 'Alice Smith',
        'email': user_a_email,
        'phone': '+1-555-0101',
        'password': user_a_pass,
        'confirm_password': user_a_pass
    }, follow_redirects=True)
    assert reg_a.status_code == 200

    # Register User B
    user_b_email = "userb@testpatient.dev"
    user_b_pass = "PasswordB123!"
    reg_b = client.post('/register', data={
        'full_name': 'Bob Jones',
        'email': user_b_email,
        'phone': '+1-555-0202',
        'password': user_b_pass,
        'confirm_password': user_b_pass
    }, follow_redirects=True)
    assert reg_b.status_code == 200

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_a_email,))
    user_a = cursor.fetchone()
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_b_email,))
    user_b = cursor.fetchone()
    conn.close()

    print(f"-> Created User A: {user_a['full_name']} ({user_a['medi_id']})")
    print(f"-> Created User B: {user_b['full_name']} ({user_b['medi_id']})")

    # 2 & 3. Authenticated Dashboard & Correct MediID Display
    print("\n[TEST 2 & 3] Authenticated User Dashboard & Correct SahayID Display")
    with client:
        # Login User A
        client.post('/login', data={'identifier': user_a_email, 'password': user_a_pass}, follow_redirects=True)
        dash_a = client.get('/dashboard')
        assert dash_a.status_code == 200
        assert user_a['full_name'].encode('utf-8') in dash_a.data
        assert user_a['medi_id'].encode('utf-8') in dash_a.data
        # Ensure User B's MediID is NOT visible
        assert user_b['medi_id'].encode('utf-8') not in dash_a.data
        print("-> Test 2 & 3 PASSED: Dashboard accessible and displays User A's SahayID.")

        # 4 & 5. Medical Profile Editing via POST
        print("\n[TEST 4 & 5] Medical Profile Editing via POST")
        prof_get = client.get('/medical-profile')
        assert prof_get.status_code == 200

        update_resp = client.post('/medical-profile', data={
            'date_of_birth': '1990-05-15',
            'gender': 'Female',
            'blood_group': 'O+',
            'allergies': 'Penicillin, Peanuts',
            'medical_conditions': 'Asthma',
            'current_medications': 'Albuterol Inhaler',
            'previous_surgeries': 'Appendectomy 2015',
            'additional_notes': 'Wears contact lenses'
        }, follow_redirects=True)
        assert update_resp.status_code == 200
        assert b"Medical profile updated successfully" in update_resp.data
        assert b"Penicillin, Peanuts" in update_resp.data
        assert b"O+" in update_resp.data
        print("-> Test 4 & 5 PASSED: Medical profile updated successfully.")

        # 6. Changes Persist Across Sessions
        print("\n[TEST 6] Changes Persist Across Sessions")
        client.get('/logout', follow_redirects=True)
        # Login again via MediID
        client.post('/login', data={'identifier': user_a['medi_id'], 'password': user_a_pass}, follow_redirects=True)
        prof_recheck = client.get('/medical-profile')
        assert b"Penicillin, Peanuts" in prof_recheck.data
        assert b"1990-05-15" in prof_recheck.data
        print("-> Test 6 PASSED: Profile updates persisted and verified after SahayID login.")

        # 7. Add Emergency Contact
        print("\n[TEST 7] Adding Emergency Contact")
        contact_resp = client.post('/emergency-contacts', data={
            'name': 'Sarah Smith',
            'relationship': 'Sister',
            'phone': '+1-555-9999'
        }, follow_redirects=True)
        assert contact_resp.status_code == 200
        assert b"added successfully" in contact_resp.data
        assert b"Sarah Smith" in contact_resp.data

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM emergency_contacts WHERE user_id = ?", (user_a['id'],))
        contact_a = cursor.fetchone()
        conn.close()
        assert contact_a is not None
        assert contact_a['name'] == 'Sarah Smith'
        print(f"-> Test 7 PASSED: Emergency contact created (ID: {contact_a['id']}).")

        # 10. Profile Completion Calculation Verification
        print("\n[TEST 10] Profile Completion Calculation")
        dash_check = client.get('/dashboard')
        # All 8 components are now filled -> 100%
        assert b"100%" in dash_check.data
        print("-> Test 10 PASSED: Profile completion calculated as 100% when all 8 criteria are met.")

        # 9. Cross-User Authorization / Tampering Protection
        print("\n[TEST 9] Cross-User Authorization & Tampering Protection")
        client.get('/logout', follow_redirects=True)

        # Log in User B and attempt to delete User A's contact
        client.post('/login', data={'identifier': user_b_email, 'password': user_b_pass}, follow_redirects=True)
        tamper_resp = client.post(f'/emergency-contacts/delete/{contact_a["id"]}', follow_redirects=True)
        assert b"access denied" in tamper_resp.data.lower() or b"unauthorized" in tamper_resp.data.lower()

        # Verify contact was NOT deleted
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM emergency_contacts WHERE id = ?", (contact_a['id'],))
        assert cursor.fetchone() is not None, "Security violation: User B deleted User A's contact!"
        conn.close()
        print("-> Test 9 PASSED: User B unauthorized deletion was blocked and denied.")

        # 8. User A Deleting Their Own Contact
        print("\n[TEST 8] User A Deleting Their Own Contact")
        client.get('/logout', follow_redirects=True)
        client.post('/login', data={'identifier': user_a_email, 'password': user_a_pass}, follow_redirects=True)
        delete_resp = client.post(f'/emergency-contacts/delete/{contact_a["id"]}', follow_redirects=True)
        assert delete_resp.status_code == 200
        assert b"removed successfully" in delete_resp.data

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM emergency_contacts WHERE id = ?", (contact_a['id'],))
        assert cursor.fetchone() is None
        conn.close()
        print("-> Test 8 PASSED: Contact successfully deleted by owner.")

        # Verify completion dropped to 88%
        dash_after_del = client.get('/dashboard')
        assert b"88%" in dash_after_del.data
        print("-> Profile completion dynamically dropped to 88% after contact deletion.")

    # Cleanup
    print("\n[CLEANUP] Cleaning up test accounts")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpatient.dev'")
    conn.commit()
    conn.close()
    print("-> Cleanup complete.")

    print("\n" + "=" * 65)
    print("ALL 10 PATIENT ACCESS TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == '__main__':
    run_tests()
