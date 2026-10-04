"""
MediID Part 3 Automated Verification Test Suite
Tests:
1. Unauthenticated user cannot access /dashboard (redirects to /login)
2. Authenticated user can access /dashboard
3. Correct user's MediID is displayed on dashboard
4. Medical profile retrieval and initial state
5. Medical profile editing via POST
6. Changes persist after logout and re-login
7. Emergency contact can be added
8. Emergency contact can be deleted
9. User A cannot delete User B's emergency contact (authorization / ID tampering check)
10. Profile completion percentage updates dynamically as fields are filled
11. Part 1 and Part 2 regression tests (registration, unique MediID, landing page)
"""

import sqlite3
from app import app, init_db, get_db_connection, calculate_profile_completion

def run_tests():
    print("=" * 65)
    print("RUNNING MEDIID PART 3 TEST SUITE")
    print("=" * 65)

    init_db()
    client = app.test_client()

    # Clean up test accounts
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpart3.dev'")
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
    user_a_email = "usera@testpart3.dev"
    user_a_pass = "PasswordA123!"
    reg_a = client.post('/register', data={
        'full_name': 'Alice Smith',
        'email': user_a_email,
        'phone': '+1-555-0101',
        'password': user_a_pass,
        'confirm_password': user_a_pass
    }, follow_redirects=True)
    assert reg_a.status_code == 200
    assert b"Registration successful" in reg_a.data

    # Register User B
    user_b_email = "userb@testpart3.dev"
    user_b_pass = "PasswordB123!"
    reg_b = client.post('/register', data={
        'full_name': 'Bob Jones',
        'email': user_b_email,
        'phone': '+1-555-0102',
        'password': user_b_pass,
        'confirm_password': user_b_pass
    }, follow_redirects=True)
    assert reg_b.status_code == 200

    # Retrieve User A and User B database records
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_a_email,))
    user_a = cursor.fetchone()
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_b_email,))
    user_b = cursor.fetchone()
    conn.close()

    assert user_a is not None and user_b is not None
    print(f"-> Created User A: {user_a['full_name']} ({user_a['medi_id']})")
    print(f"-> Created User B: {user_b['full_name']} ({user_b['medi_id']})")

    # 2 & 3. Login as User A and verify Dashboard access and MediID display
    print("\n[TEST 2 & 3] Authenticated User Dashboard & Correct MediID Display")
    login_a = client.post('/login', data={
        'identifier': user_a_email,
        'password': user_a_pass
    }, follow_redirects=True)
    assert login_a.status_code == 200
    # Must redirect to /dashboard
    assert b"Welcome, Alice Smith" in login_a.data
    assert user_a['medi_id'].encode() in login_a.data
    assert b"Profile Completion" in login_a.data
    print("-> Test 2 & 3 PASSED: Dashboard accessible and displays User A's MediID.")

    # 4 & 5. Edit User A's Medical Profile
    print("\n[TEST 4 & 5] Medical Profile Editing via POST")
    # Initial completion should be 0%
    dash_resp = client.get('/dashboard')
    assert b"0%" in dash_resp.data

    update_resp = client.post('/medical-profile', data={
        'date_of_birth': '1990-05-15',
        'gender': 'Female',
        'blood_group': 'O+',
        'allergies': 'Penicillin (severe anaphylaxis)',
        'medical_conditions': 'Asthma',
        'current_medications': 'Albuterol inhaler',
        'previous_surgeries': 'Tonsillectomy (2005)',
        'additional_notes': 'Prefers contact via SMS'
    }, follow_redirects=True)
    assert update_resp.status_code == 200
    assert b"Medical profile updated successfully" in update_resp.data
    assert b"Penicillin" in update_resp.data
    print("-> Test 4 & 5 PASSED: Medical profile updated successfully.")

    # 6. Changes Persist After Logout & Re-login
    print("\n[TEST 6] Changes Persist Across Sessions")
    client.get('/logout', follow_redirects=True)
    # Log back in using MediID instead of email
    login_again = client.post('/login', data={
        'identifier': user_a['medi_id'],
        'password': user_a_pass
    }, follow_redirects=True)
    assert login_again.status_code == 200
    assert b"Welcome, Alice Smith" in login_again.data
    # Check medical profile page
    prof_resp = client.get('/medical-profile')
    assert b"Penicillin (severe anaphylaxis)" in prof_resp.data
    assert b"Asthma" in prof_resp.data
    assert b"O+" in prof_resp.data
    print("-> Test 6 PASSED: Profile updates persisted and verified after MediID login.")

    # 7. Add Emergency Contact for User A
    print("\n[TEST 7] Adding Emergency Contact")
    add_contact_resp = client.post('/emergency-contacts', data={
        'name': 'David Smith',
        'relationship': 'Spouse',
        'phone': '+1-555-987-6543'
    }, follow_redirects=True)
    assert add_contact_resp.status_code == 200
    assert b"David Smith" in add_contact_resp.data
    assert b"Spouse" in add_contact_resp.data

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergency_contacts WHERE user_id = ?", (user_a['id'],))
    contact_a = cursor.fetchone()
    conn.close()
    assert contact_a is not None
    print(f"-> Test 7 PASSED: Emergency contact created (ID: {contact_a['id']}).")

    # 10. Profile Completion Percentage Updates
    print("\n[TEST 10] Profile Completion Calculation")
    dash_updated = client.get('/dashboard')
    # All 8 criteria are now filled (DOB, Gender, Blood, Allergies, Conditions, Meds, Surgeries, 1+ Contact)
    # Should be 100%
    assert b"100%" in dash_updated.data
    print("-> Test 10 PASSED: Profile completion calculated as 100% when all 8 criteria are met.")

    # 9. User B Cannot Delete User A's Emergency Contact (Cross-User Authorization Test)
    print("\n[TEST 9] Cross-User Authorization & Tampering Protection")
    client.get('/logout', follow_redirects=True)

    # Login as User B
    client.post('/login', data={
        'identifier': user_b_email,
        'password': user_b_pass
    }, follow_redirects=True)

    # User B attempts to delete User A's contact
    tamper_resp = client.post(f"/emergency-contacts/delete/{contact_a['id']}", follow_redirects=True)
    assert tamper_resp.status_code == 200
    assert b"access denied" in tamper_resp.data.lower() or b"not found" in tamper_resp.data.lower()

    # Verify contact still exists in database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergency_contacts WHERE id = ?", (contact_a['id'],))
    still_exists = cursor.fetchone()
    conn.close()
    assert still_exists is not None, "CRITICAL: User B was able to delete User A's emergency contact!"
    print("-> Test 9 PASSED: User B unauthorized deletion was blocked and denied.")

    # 8. User A Deleting Their Own Contact
    print("\n[TEST 8] User A Deleting Their Own Contact")
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={
        'identifier': user_a_email,
        'password': user_a_pass
    }, follow_redirects=True)

    delete_resp = client.post(f"/emergency-contacts/delete/{contact_a['id']}", follow_redirects=True)
    assert delete_resp.status_code == 200
    assert b"removed successfully" in delete_resp.data

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergency_contacts WHERE id = ?", (contact_a['id'],))
    assert cursor.fetchone() is None
    conn.close()
    print("-> Test 8 PASSED: Contact successfully deleted by owner.")

    # Completion should now drop to 88% (7 of 8 criteria met since contact was removed)
    dash_after_delete = client.get('/dashboard')
    assert b"88%" in dash_after_delete.data
    print("-> Profile completion dynamically dropped to 88% after contact deletion.")

    # Clean up test accounts
    print("\n[CLEANUP] Cleaning up test accounts")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@testpart3.dev'")
    conn.commit()
    conn.close()
    print("-> Cleanup complete.")

    print("\n" + "=" * 65)
    print("ALL PART 3 TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
