"""
Comprehensive Part 2 Verification Test Suite for MediID
Tests:
1. Database initialization and schema verification (all 4 tables)
2. Foreign-key constraint enforcement
3. Unique MediID generation format and collision-avoidance
4. Registration endpoint (validation, hashing, user record, medical profile)
5. Duplicate email rejection
6. Password hashing verification (not plaintext)
7. Login endpoint with correct credentials (session creation & access log)
8. Login endpoint with incorrect credentials (rejection & error flash)
9. Medical profile creation linked via foreign key
"""

import sqlite3
from werkzeug.security import check_password_hash
from app import app, init_db, get_db_connection, generate_unique_medi_id

def run_tests():
    print("=" * 60)
    print("RUNNING MEDIID PART 2 TEST SUITE")
    print("=" * 60)

    # 1. Database Initialization
    print("\n[TEST 1] Database Initialization & Table Existence")
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r['name'] for r in cursor.fetchall() if not r['name'].startswith('sqlite_')]
    print(f"Tables detected: {tables}")
    for req_table in ['users', 'medical_profiles', 'emergency_contacts', 'access_logs']:
        assert req_table in tables, f"Missing table: {req_table}"
    print("-> Test 1 PASSED: All 4 tables exist.")

    # 2. Foreign-Key Relationships
    print("\n[TEST 2] Foreign-Key Constraint Enforcement")
    cursor.execute("PRAGMA foreign_keys;")
    fk_enabled = cursor.fetchone()[0]
    print(f"PRAGMA foreign_keys = {fk_enabled}")
    assert fk_enabled == 1, "Foreign keys are not enabled!"

    try:
        cursor.execute("INSERT INTO medical_profiles (user_id) VALUES (999999);")
        conn.commit()
        raise AssertionError("Foreign key violation was NOT enforced for medical_profiles!")
    except sqlite3.IntegrityError:
        conn.rollback()
        print("-> Caught expected IntegrityError on invalid user_id.")

    try:
        cursor.execute("INSERT INTO emergency_contacts (user_id, name, phone) VALUES (999999, 'Test', '123');")
        conn.commit()
        raise AssertionError("Foreign key violation was NOT enforced for emergency_contacts!")
    except sqlite3.IntegrityError:
        conn.rollback()
        print("-> Caught expected IntegrityError on emergency_contacts.")

    try:
        cursor.execute("INSERT INTO access_logs (user_id, access_type) VALUES (999999, 'LOGIN');")
        conn.commit()
        raise AssertionError("Foreign key violation was NOT enforced for access_logs!")
    except sqlite3.IntegrityError:
        conn.rollback()
        print("-> Caught expected IntegrityError on access_logs.")
    print("-> Test 2 PASSED: Foreign-key relationships strictly enforced.")

    # 3. MediID Generation
    print("\n[TEST 3] MediID Generation Format & Randomness")
    sample_ids = [generate_unique_medi_id(conn) for _ in range(20)]
    print(f"Sample generated IDs: {sample_ids[:5]}...")
    assert len(set(sample_ids)) == 20, "Generated duplicate MediIDs!"
    for mid in sample_ids:
        assert mid.startswith("MED-"), f"Invalid prefix: {mid}"
        assert len(mid) == 12, f"Invalid length: {mid}"
        assert mid[4:].isalnum() and mid[4:].isupper(), f"Invalid format: {mid}"
    print("-> Test 3 PASSED: Format matches 'MED-XXXXXXXX' with high entropy.")

    conn.close()

    # Flask Test Client setup
    test_client = app.test_client()

    # Clean up any leftover test accounts before testing
    cleanup_conn = get_db_connection()
    cleanup_cursor = cleanup_conn.cursor()
    cleanup_cursor.execute("DELETE FROM users WHERE email LIKE '%@test.mediid.dev'")
    cleanup_conn.commit()
    cleanup_conn.close()

    test_email = "testpatient@test.mediid.dev"
    test_password = "SecurePassword123!"
    test_name = "Alex Mercer"
    test_phone = "+1-555-019-2834"

    # 4. New User Registration
    print("\n[TEST 4] New User Registration & Record Insertion")
    reg_response = test_client.post('/register', data={
        'full_name': test_name,
        'email': test_email,
        'phone': test_phone,
        'password': test_password,
        'confirm_password': test_password
    }, follow_redirects=True)
    assert reg_response.status_code == 200
    assert b"Registration successful" in reg_response.data
    print("-> Test 4 PASSED: Registration successful and redirected to login.")

    # 5. Password Hashing & Record Inspection
    print("\n[TEST 5] Password Hashing & Privacy Verification")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (test_email,))
    user = cursor.fetchone()
    assert user is not None, "User record was not created!"
    stored_hash = user['password_hash']
    print(f"User ID: {user['id']}")
    print(f"Generated MediID: {user['medi_id']}")
    print(f"Stored Password Hash prefix: {stored_hash[:25]}... (length: {len(stored_hash)})")
    
    # Assert password is NOT plain text
    assert stored_hash != test_password, "CRITICAL: Password stored in plaintext!"
    # Verify hash against Werkzeug check
    assert check_password_hash(stored_hash, test_password) is True, "Password hash does not verify!"
    assert check_password_hash(stored_hash, "WrongPassword") is False
    print("-> Test 5 PASSED: Password hashed using Werkzeug and verified.")

    # 6. Medical Profile Creation
    print("\n[TEST 6] Automatic Medical Profile Creation")
    cursor.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (user['id'],))
    profile = cursor.fetchone()
    assert profile is not None, "Medical profile was not created for the new user!"
    print(f"Medical profile ID: {profile['id']} linked to User ID: {profile['user_id']}")
    print("-> Test 6 PASSED: Blank medical profile linked to new user.")

    # 7. Duplicate Email Registration
    print("\n[TEST 7] Duplicate Email Registration Prevention")
    dup_response = test_client.post('/register', data={
        'full_name': 'Imposter Alex',
        'email': test_email,
        'phone': '9999999',
        'password': 'DifferentPassword123',
        'confirm_password': 'DifferentPassword123'
    }, follow_redirects=True)
    assert dup_response.status_code == 200
    assert b"already exists" in dup_response.data
    print("-> Test 7 PASSED: Duplicate registration rejected with error message.")

    # 8. Login with Correct Credentials (both email and MediID)
    print("\n[TEST 8] Login with Correct Credentials")
    # Login via Email
    login_response_email = test_client.post('/login', data={
        'identifier': test_email,
        'password': test_password
    }, follow_redirects=True)
    assert login_response_email.status_code == 200
    assert b"Welcome back" in login_response_email.data
    print("-> Email login verified.")

    # Verify session cookie was set
    with test_client.session_transaction() as sess:
        assert sess['user_id'] == user['id']
        assert sess['medi_id'] == user['medi_id']
        assert sess['full_name'] == test_name
    print("-> Flask session contains user_id, medi_id, and full_name.")

    # Verify access log entry
    cursor.execute("SELECT * FROM access_logs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user['id'],))
    log_entry = cursor.fetchone()
    assert log_entry is not None, "Access log entry was not recorded!"
    assert log_entry['access_type'] == 'LOGIN'
    print(f"-> Access log verified: Type={log_entry['access_type']}, IP={log_entry['ip_address']}, Time={log_entry['accessed_at']}")

    # Logout
    logout_resp = test_client.get('/logout', follow_redirects=True)
    assert b"signed out successfully" in logout_resp.data

    # Login via MediID
    login_response_mediid = test_client.post('/login', data={
        'identifier': user['medi_id'],
        'password': test_password
    }, follow_redirects=True)
    assert login_response_mediid.status_code == 200
    assert b"Welcome back" in login_response_mediid.data
    print("-> MediID login verified.")
    print("-> Test 8 PASSED: Login with both Email and MediID works.")

    # 9. Login with Incorrect Credentials
    print("\n[TEST 9] Login with Incorrect Credentials")
    bad_login_resp = test_client.post('/login', data={
        'identifier': test_email,
        'password': 'WrongPassword999'
    }, follow_redirects=True)
    assert bad_login_resp.status_code == 200
    assert b"Invalid email/MediID or password" in bad_login_resp.data

    bad_user_resp = test_client.post('/login', data={
        'identifier': 'MED-NONEXISTENT',
        'password': test_password
    }, follow_redirects=True)
    assert bad_user_resp.status_code == 200
    assert b"Invalid email/MediID or password" in bad_user_resp.data
    print("-> Test 9 PASSED: Invalid credentials properly rejected.")

    # Clean up temporary test account
    print("\n[CLEANUP] Removing temporary test account")
    cursor.execute("DELETE FROM users WHERE id = ?", (user['id'],))
    conn.commit()

    # Verify CASCADE on medical_profiles and access_logs
    cursor.execute("SELECT 1 FROM medical_profiles WHERE user_id = ?", (user['id'],))
    assert cursor.fetchone() is None, "CASCADE delete failed on medical_profiles!"
    cursor.execute("SELECT 1 FROM access_logs WHERE user_id = ?", (user['id'],))
    assert cursor.fetchone() is None, "CASCADE delete failed on access_logs!"
    print("-> Cleanup complete. ON DELETE CASCADE verified.")

    conn.close()
    print("\n" + "=" * 60)
    print("ALL 9 TESTS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
