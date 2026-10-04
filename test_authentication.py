"""
SahayID Core Authentication & Schema Verification Test Suite
Tests:
1. Database initialization and schema verification (all tables)
2. Foreign-key constraint enforcement
3. Unique SahayID generation format and collision-avoidance
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
    print("RUNNING SAHAYID CORE AUTHENTICATION TEST SUITE")
    print("=" * 60)

    # 1. Database Initialization
    print("\n[TEST 1] Database Initialization & Table Existence")
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r['name'] for r in cursor.fetchall() if not r['name'].startswith('sqlite_')]
    print(f"Tables detected: {tables}")
    for req_table in ['users', 'medical_profiles', 'emergency_contacts', 'access_logs', 'access_requests']:
        assert req_table in tables, f"Missing table: {req_table}"
    print("-> Test 1 PASSED: All core tables exist.")

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

    # 3. MediID Generation Format & Randomness
    print("\n[TEST 3] SahayID Generation Format & Randomness")
    sample_ids = [generate_unique_medi_id(conn) for _ in range(50)]
    print(f"Sample generated IDs: {sample_ids[:5]}...")
    assert len(set(sample_ids)) == 50, "Collision detected in generated SahayIDs!"
    for mid in sample_ids:
        assert mid.startswith("MED-"), f"Invalid prefix: {mid}"
        assert len(mid) == 12, f"Invalid length: {mid}"
        alphanumeric_part = mid[4:]
        assert alphanumeric_part.isalnum() and alphanumeric_part.isupper(), f"Invalid charset in ID: {mid}"
    print("-> Test 3 PASSED: Format matches 'MED-XXXXXXXX' with high entropy.")

    # 4. User Registration & Record Insertion
    print("\n[TEST 4] New User Registration & Record Insertion")
    client = app.test_client()
    
    # Clean up test user if exists
    cursor.execute("DELETE FROM users WHERE email = ?", ('test.auth@example.com',))
    conn.commit()

    test_pass = "SecureP@ssw0rd123!"
    reg_response = client.post('/register', data={
        'full_name': 'Test Verification User',
        'email': 'test.auth@example.com',
        'phone': '+1234567890',
        'password': test_pass,
        'confirm_password': test_pass
    }, follow_redirects=False)

    assert reg_response.status_code == 302, f"Expected 302 redirect, got {reg_response.status_code}"
    assert '/login' in reg_response.headers['Location']
    print("-> Test 4 PASSED: Registration successful and redirected to login.")

    # 5. Password Hashing Verification
    print("\n[TEST 5] Password Hashing & Privacy Verification")
    cursor.execute("SELECT id, medi_id, password_hash FROM users WHERE email = ?", ('test.auth@example.com',))
    user_row = cursor.fetchone()
    assert user_row is not None, "User record was not created in database!"
    stored_hash = user_row['password_hash']
    assert stored_hash != test_pass, "Password was stored in PLAINTEXT!"
    assert check_password_hash(stored_hash, test_pass), "Stored hash does not match original password!"
    print(f"User ID: {user_row['id']}")
    print(f"Generated SahayID: {user_row['medi_id']}")
    print(f"Stored Password Hash prefix: {stored_hash[:25]}... (length: {len(stored_hash)})")
    print("-> Test 5 PASSED: Password hashed securely and verified.")

    # 6. Automatic Medical Profile Linked
    print("\n[TEST 6] Automatic Medical Profile Creation")
    cursor.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (user_row['id'],))
    profile_row = cursor.fetchone()
    assert profile_row is not None, "Medical profile was not automatically created for user!"
    print(f"Medical profile ID: {profile_row['id']} linked to User ID: {profile_row['user_id']}")
    print("-> Test 6 PASSED: Blank medical profile linked to new user.")

    # 7. Duplicate Email Prevention
    print("\n[TEST 7] Duplicate Email Registration Prevention")
    dup_response = client.post('/register', data={
        'full_name': 'Duplicate User',
        'email': 'test.auth@example.com',
        'password': 'AnotherPassword123!',
        'confirm_password': 'AnotherPassword123!'
    }, follow_redirects=True)
    assert b"An account with this email address already exists" in dup_response.data
    print("-> Test 7 PASSED: Duplicate registration rejected with error message.")

    # 8. Login with Valid Credentials & Access Logging
    print("\n[TEST 8] Login with Correct Credentials")
    with client:
        login_resp = client.post('/login', data={
            'identifier': 'test.auth@example.com',
            'password': test_pass
        }, follow_redirects=True)
        assert login_resp.status_code == 200
        print("-> Email login verified.")

        from flask import session
        assert session.get('user_id') == user_row['id']
        assert session.get('medi_id') == user_row['medi_id']
        assert session.get('full_name') == 'Test Verification User'
        print(f"-> Flask session contains user_id, medi_id, and full_name.")

        cursor.execute("SELECT * FROM access_logs WHERE user_id = ? ORDER BY id DESC LIMIT 1;", (user_row['id'],))
        log_entry = cursor.fetchone()
        assert log_entry is not None, "Login access log entry was not recorded!"
        assert log_entry['access_type'] == 'LOGIN'
        print(f"-> Access log verified: Type={log_entry['access_type']}, IP={log_entry['ip_address']}, Time={log_entry['accessed_at']}")

        # Test MediID login
        client.get('/logout', follow_redirects=True)
        mid_login_resp = client.post('/login', data={
            'identifier': user_row['medi_id'],
            'password': test_pass
        }, follow_redirects=True)
        assert mid_login_resp.status_code == 200
        assert session.get('user_id') == user_row['id']
        print("-> SahayID login verified.")
        print("-> Test 8 PASSED: Login with both Email and SahayID works.")

    # 9. Login with Incorrect Credentials
    print("\n[TEST 9] Login with Incorrect Credentials")
    bad_login = client.post('/login', data={
        'identifier': 'test.auth@example.com',
        'password': 'WrongPassword999!'
    }, follow_redirects=True)
    assert b"Invalid email / SahayID Number or password" in bad_login.data or b"Invalid" in bad_login.data
    print("-> Test 9 PASSED: Invalid credentials properly rejected.")

    # Clean up test accounts
    print("\n[CLEANUP] Removing temporary test account")
    cursor.execute("DELETE FROM users WHERE id = ?", (user_row['id'],))
    conn.commit()

    # Verify CASCADE delete
    cursor.execute("SELECT COUNT(*) as count FROM medical_profiles WHERE user_id = ?", (user_row['id'],))
    assert cursor.fetchone()['count'] == 0
    print("-> Cleanup complete. ON DELETE CASCADE verified.")

    conn.close()
    print("\n" + "=" * 60)
    print("ALL 9 AUTHENTICATION TESTS PASSED PERFECTLY!")
    print("=" * 60)


if __name__ == '__main__':
    run_tests()
