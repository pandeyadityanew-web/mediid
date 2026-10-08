"""
SahayID Comprehensive Production Hardening and Verification Suite
Tests the complete patient authentication lifecycle, session persistence across serverless invocations,
PWA installability and manifest compliance, database transactional integrity, and role protections.
"""

import unittest
import json
import os
import re
from app import app, get_db_connection, init_db, generate_unique_medi_id

class ProductionHardenTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        os.environ['ADMIN_PASSWORD'] = 'AdminSahay@ProdTest2026!'
        init_db()

    def setUp(self):
        self.client = app.test_client()

    def test_01_health_diagnostic_endpoint(self):
        """Verify /health diagnostic returns safe non-sensitive metadata and X-DB-Backend header."""
        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['service'], 'SahayID')
        self.assertIn('db_backend', data)
        self.assertIn('X-DB-Backend', res.headers)
        self.assertIn(res.headers['X-DB-Backend'], ['postgresql', 'sqlite'])

    def test_02_pwa_manifest_and_sw_compliance(self):
        """Verify manifest.json, sw.js headers, and icon requirements for native PWA installation."""
        # 1. Manifest
        manifest_res = self.client.get('/manifest.json')
        self.assertEqual(manifest_res.status_code, 200)
        self.assertIn('manifest', manifest_res.content_type)
        manifest_data = json.loads(manifest_res.data)
        self.assertEqual(manifest_data['name'], 'SahayID - Critical Medical Access')
        self.assertEqual(manifest_data['short_name'], 'SahayID')
        self.assertEqual(manifest_data['display'], 'standalone')
        self.assertEqual(manifest_data['start_url'], '/')
        
        # Check icons
        icons = manifest_data['icons']
        sizes = [i['sizes'] for i in icons]
        self.assertIn('192x192', sizes)
        self.assertIn('512x512', sizes)

        # 2. Service Worker
        sw_res = self.client.get('/sw.js')
        self.assertEqual(sw_res.status_code, 200)
        self.assertEqual(sw_res.headers.get('Service-Worker-Allowed'), '/')
        self.assertIn(b'fetch', sw_res.data)
        self.assertIn(b'caches.open', sw_res.data)

    def test_03_patient_registration_login_dashboard_flow(self):
        """
        Verify end-to-end patient flow:
        Register -> Not logged in -> Login -> Authenticated -> Dashboard -> Refresh -> Logout -> Protected.
        """
        test_email = f"shubham_{os.urandom(4).hex()}@testdomain.org"
        test_pass = "SecurePass123!"
        test_name = "Shubham Sharma"

        # 1. Register Patient
        reg_res = self.client.post('/register', data={
            'full_name': test_name,
            'email': test_email,
            'phone': '+91 9876543210',
            'password': test_pass,
            'confirm_password': test_pass
        }, follow_redirects=False)

        # Registration must redirect to /login (302)
        self.assertEqual(reg_res.status_code, 302)
        self.assertIn('/login', reg_res.headers['Location'])

        # Session must NOT be authenticated after registration
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

        # 2. Verify patient was created in database with initial medical profile
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, medi_id, full_name, email FROM users WHERE LOWER(email) = LOWER(?)", (test_email,))
        user_row = cur.fetchone()
        self.assertIsNotNone(user_row)
        self.assertEqual(user_row['full_name'], test_name)
        user_id = user_row['id']
        medi_id = user_row['medi_id']

        cur.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (user_id,))
        prof_row = cur.fetchone()
        self.assertIsNotNone(prof_row)

        # 3. Duplicate Registration Prevention
        dup_res = self.client.post('/register', data={
            'full_name': test_name,
            'email': test_email.upper(),
            'phone': '+91 9876543210',
            'password': test_pass,
            'confirm_password': test_pass
        })
        self.assertEqual(dup_res.status_code, 200)
        self.assertIn(b'already exists', dup_res.data)

        # 4. Attempt Accessing /dashboard while unauthenticated -> must redirect to /login
        unauth_dash = self.client.get('/dashboard')
        self.assertEqual(unauth_dash.status_code, 302)
        self.assertIn('/login', unauth_dash.headers['Location'])

        # 5. Login Patient with Case-Insensitive Email
        login_res = self.client.post('/login', data={
            'identifier': test_email.upper(),
            'password': test_pass
        }, follow_redirects=False)

        self.assertEqual(login_res.status_code, 302)
        self.assertIn('/dashboard', login_res.headers['Location'])

        # Verify session state
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_id'), user_id)
            self.assertEqual(sess.get('medi_id'), medi_id)
            self.assertEqual(sess.get('role'), 'patient')
            self.assertEqual(sess.get('full_name'), test_name)

        # 6. Access Patient Dashboard
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(test_name.encode(), dash_res.data)
        self.assertIn(medi_id.encode(), dash_res.data)
        self.assertIn(b'Profile Completion', dash_res.data)

        # 7. Refresh / Subsequent Dashboard Request (Session Persistence)
        dash_refresh = self.client.get('/dashboard')
        self.assertEqual(dash_refresh.status_code, 200)
        self.assertIn(test_name.encode(), dash_refresh.data)

        # 8. Logout
        logout_res = self.client.get('/logout')
        self.assertEqual(logout_res.status_code, 302)

        # 9. Verify Dashboard is Protected after logout
        post_logout_dash = self.client.get('/dashboard')
        self.assertEqual(post_logout_dash.status_code, 302)
        self.assertIn('/login', post_logout_dash.headers['Location'])

    def test_04_doctor_and_admin_flows_remain_intact(self):
        """Verify doctor registration, doctor login, admin login, and role barriers."""
        doc_email = f"dr_{os.urandom(4).hex()}@hospital.org"
        doc_pass = "DoctorPass2026!"
        doc_name = "Dr. Ananya Roy"

        # Register doctor
        doc_reg = self.client.post('/doctor/register', data={
            'full_name': doc_name,
            'email': doc_email,
            'phone': '+91 9988776655',
            'specialization': 'Emergency Medicine',
            'hospital_or_clinic': 'Apollo Speciality Hospital',
            'registration_number': f'MCI-{os.urandom(3).hex().upper()}',
            'password': doc_pass,
            'confirm_password': doc_pass
        }, follow_redirects=False)
        self.assertEqual(doc_reg.status_code, 302)
        self.assertIn('/doctor/login', doc_reg.headers['Location'])

        # Login doctor
        doc_login = self.client.post('/doctor/login', data={
            'identifier': doc_email,
            'password': doc_pass
        }, follow_redirects=False)
        self.assertEqual(doc_login.status_code, 302)
        self.assertIn('/doctor/dashboard', doc_login.headers['Location'])

        # Doctor cannot access patient dashboard
        doc_on_pat_dash = self.client.get('/dashboard')
        self.assertEqual(doc_on_pat_dash.status_code, 302)
        self.assertIn('/doctor/dashboard', doc_on_pat_dash.headers['Location'])

        self.client.get('/logout')

        # Admin login
        admin_login = self.client.post('/admin/login', data={
            'identifier': 'admin',
            'password': 'AdminSahay@ProdTest2026!'
        }, follow_redirects=False)
        self.assertEqual(admin_login.status_code, 302)
        self.assertIn('/admin', admin_login.headers['Location'])

        # Admin dashboard
        admin_dash = self.client.get('/admin')
        self.assertEqual(admin_dash.status_code, 200)
        self.assertIn(b'Physician Credential Verification', admin_dash.data)

        self.client.get('/logout')


if __name__ == '__main__':
    unittest.main()
