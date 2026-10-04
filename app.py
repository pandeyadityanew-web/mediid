"""
SahayID - Digital Medical Identity System
Tagline: CRITICAL MEDICAL ACCESS
"""

import os
import secrets
import string
import hashlib
import sqlite3
import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode

app = Flask(__name__)

# Application Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mediid-dev-secret-key-2026')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'database')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'medid.db')
QR_DIR = os.path.join(BASE_DIR, 'static', 'generated_qr')


# ============================================================================
# Role-Based Authentication & Authorization Decorators
# ============================================================================

def login_required(f):
    """
    Decorator requiring an active session (patient user_id or doctor_id) to access protected routes.
    Redirects unauthenticated visitors to the login view.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'doctor_id' not in session:
            flash("Please sign in to access your SahayID portal.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def patient_required(f):
    """
    Decorator ensuring that only authenticated patient accounts can access patient routes.
    Prevents doctor accounts from entering patient account-management workflows.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if 'doctor_id' in session:
                flash("Access restricted to patient accounts.", "error")
                return redirect(url_for('doctor_dashboard'))
            flash("Please sign in to access your SahayID patient portal.", "error")
            return redirect(url_for('login'))
        if session.get('role') != 'patient':
            flash("Access restricted to patient accounts.", "error")
            return redirect(url_for('doctor_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def doctor_required(f):
    """
    Decorator ensuring that only authenticated doctor accounts can access doctor routes.
    Prevents patient accounts from accessing the clinical doctor portal.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor_id' not in session:
            if 'user_id' in session:
                flash("Access restricted to verified medical doctors.", "error")
                return redirect(url_for('dashboard'))
            flash("Please sign in with your Doctor credentials.", "error")
            return redirect(url_for('doctor_login'))
        if session.get('role') != 'doctor':
            flash("Access restricted to verified medical doctors.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Database Helper Functions
# ============================================================================

def get_db_connection():
    """
    Establish and return a standalone connection to the SQLite database.
    Foreign key enforcement is explicitly activated on each connection.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_db():
    """
    Get or create a database connection for the current Flask application context.
    """
    if 'db' not in g:
        g.db = get_db_connection()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """
    Close the database connection at the end of the request context.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def generate_unique_medi_id(conn):
    """
    Generate a cryptographically random, collision-resistant MediID in the format:
    MED-XXXXXXXX (where X is an uppercase alphanumeric character).
    Ensures uniqueness against existing records in the users table.
    """
    alphabet = string.ascii_uppercase + string.digits
    max_attempts = 100

    for _ in range(max_attempts):
        suffix = ''.join(secrets.choice(alphabet) for _ in range(8))
        candidate_id = f"MED-{suffix}"

        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE medi_id = ?", (candidate_id,))
        if cursor.fetchone() is None:
            return candidate_id

    raise RuntimeError("Unable to generate a unique MediID after multiple attempts.")


def generate_unique_doctor_id(conn):
    """
    Generate a cryptographically random, collision-resistant Doctor ID in the format:
    DOC-XXXXXXXX (where X is an uppercase alphanumeric character).
    Ensures uniqueness against existing records in the doctors table.
    """
    alphabet = string.ascii_uppercase + string.digits
    max_attempts = 100

    for _ in range(max_attempts):
        suffix = ''.join(secrets.choice(alphabet) for _ in range(8))
        candidate_id = f"DOC-{suffix}"

        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM doctors WHERE doctor_id = ?", (candidate_id,))
        if cursor.fetchone() is None:
            return candidate_id

    raise RuntimeError("Unable to generate a unique Doctor ID after multiple attempts.")


def calculate_profile_completion(profile, contact_count):
    """
    Calculate a simple profile completion percentage.
    Required criteria (8 components):
    1. Date of birth
    2. Gender
    3. Blood group
    4. Allergies
    5. Medical conditions
    6. Current medications
    7. Previous surgeries
    8. At least one emergency contact
    Optional notes are NOT treated as required.
    """
    if not profile:
        return 0

    criteria = [
        bool(profile['date_of_birth'] and profile['date_of_birth'].strip()),
        bool(profile['gender'] and profile['gender'].strip()),
        bool(profile['blood_group'] and profile['blood_group'].strip()),
        bool(profile['allergies'] and profile['allergies'].strip()),
        bool(profile['medical_conditions'] and profile['medical_conditions'].strip()),
        bool(profile['current_medications'] and profile['current_medications'].strip()),
        bool(profile['previous_surgeries'] and profile['previous_surgeries'].strip()),
        contact_count > 0,
    ]
    completed = sum(1 for met in criteria if met)
    return round((completed / len(criteria)) * 100)


# ============================================================================
# QR Code Helper Function
# ============================================================================

def generate_medi_qr(medi_id, base_url=None):
    """
    Generate a high-contrast, phone-scannable QR code image for a patient's MediID.
    Encodes strictly the emergency access URL:
      {base_url}/emergency/{medi_id}
    Does NOT encode any medical or personal data.
    Saves to static/generated_qr/{medi_id}.png and returns the file path.
    """
    os.makedirs(QR_DIR, exist_ok=True)

    if not base_url:
        base_url = os.environ.get('BASE_URL', 'http://127.0.0.1:5000').rstrip('/')
    else:
        base_url = base_url.rstrip('/')

    emergency_url = f"{base_url}/emergency/{medi_id}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(emergency_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    file_path = os.path.join(QR_DIR, f"{medi_id}.png")
    img.save(file_path)
    return file_path


def init_db():
    """
    Initialize SQLite database schema and static asset directories.
    Creates all required tables and indexes if they do not exist.
    """
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(QR_DIR, exist_ok=True)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medi_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. medical_profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medical_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date_of_birth TEXT,
                gender TEXT,
                blood_group TEXT,
                allergies TEXT,
                medical_conditions TEXT,
                current_medications TEXT,
                previous_surgeries TEXT,
                additional_notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        # 3. emergency_contacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emergency_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                relationship TEXT,
                phone TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        # 4. access_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                access_type TEXT NOT NULL,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        # 5. emergency_access table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emergency_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                responder_name TEXT NOT NULL,
                organization TEXT,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                accessed_at TIMESTAMP,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        # 6. doctors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                password_hash TEXT NOT NULL,
                specialization TEXT NOT NULL,
                hospital_or_clinic TEXT NOT NULL,
                registration_number TEXT NOT NULL,
                verification_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Extend access_logs columns defensively if they do not exist
        cursor.execute("PRAGMA table_info(access_logs);")
        access_cols = [col[1] for col in cursor.fetchall()]
        if 'doctor_id' not in access_cols:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN doctor_id INTEGER;")
        if 'actor_type' not in access_cols:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN actor_type TEXT DEFAULT 'PATIENT';")
        if 'actor_name' not in access_cols:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN actor_name TEXT;")
        if 'organization' not in access_cols:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN organization TEXT;")
        if 'reason' not in access_cols:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN reason TEXT;")

        # Database Indexes for Performance & Scalability
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_medi_id ON users (medi_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emergency_access_token ON emergency_access (token_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emergency_contacts_user ON emergency_contacts (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_user ON access_logs (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medical_profiles_user ON medical_profiles (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_doctor_id ON doctors (doctor_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_email ON doctors (email);")

        conn.commit()
    finally:
        conn.close()


# Ensure database tables and asset folders exist on startup
init_db()


# ============================================================================
# Public & Authentication Routes
# ============================================================================

@app.route('/')
def index():
    """Landing page route."""
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration route.
    Validates input, checks duplicate email, generates unique MediID,
    hashes password, creates an initial medical profile, and automatically
    generates the patient's emergency QR code.
    """
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Input validation
        if not full_name or not email or not password or not confirm_password:
            flash("All required fields must be filled.", "error")
            return render_template('register.html', full_name=full_name, email=email, phone=phone)

        if '@' not in email or '.' not in email:
            flash("Please enter a valid email address.", "error")
            return render_template('register.html', full_name=full_name, email=email, phone=phone)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template('register.html', full_name=full_name, email=email, phone=phone)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "error")
            return render_template('register.html', full_name=full_name, email=email, phone=phone)

        db = get_db()
        try:
            # Check for existing email using parameterized query
            cursor = db.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                flash("An account with this email address already exists. Please log in.", "error")
                return render_template('register.html', full_name=full_name, email=email, phone=phone)

            # Generate unique MediID (e.g. MED-XXXXXXXX)
            medi_id = generate_unique_medi_id(db)

            # Hash password securely using Werkzeug
            password_hash = generate_password_hash(password)

            # Insert user record
            cursor.execute(
                """
                INSERT INTO users (medi_id, full_name, email, phone, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (medi_id, full_name, email, phone, password_hash)
            )
            user_id = cursor.lastrowid

            # Create initial empty medical profile for the new user
            cursor.execute(
                """
                INSERT INTO medical_profiles (user_id)
                VALUES (?)
                """,
                (user_id,)
            )

            db.commit()

            # Automatically generate emergency QR code for new user
            base_url = request.host_url.rstrip('/') if request else None
            generate_medi_qr(medi_id, base_url)

            flash(
                f"Registration successful! Your unique MediID is {medi_id}. You can now sign in.",
                "success"
            )
            return redirect(url_for('login'))

        except sqlite3.Error:
            db.rollback()
            flash("A database error occurred during registration. Please try again.", "error")
            return render_template('register.html', full_name=full_name, email=email, phone=phone)

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login route.
    Accepts Email or MediID with password, verifies credentials,
    sets session state, and redirects to dashboard.
    """
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        if not identifier or not password:
            flash("Please provide both email/MediID and password.", "error")
            return render_template('login.html', identifier=identifier)

        db = get_db()
        try:
            cursor = db.cursor()
            # Lookup user by either lowercase email or uppercase MediID
            cursor.execute(
                """
                SELECT id, medi_id, full_name, email, password_hash
                FROM users
                WHERE email = ? OR UPPER(medi_id) = ?
                """,
                (identifier.lower(), identifier.upper())
            )
            user = cursor.fetchone()

            # Verify password using Werkzeug check_password_hash
            if user is None or not check_password_hash(user['password_hash'], password):
                flash("Invalid email/MediID or password.", "error")
                return render_template('login.html', identifier=identifier)

            # Establish authenticated patient session
            session.clear()
            session['user_id'] = user['id']
            session['medi_id'] = user['medi_id']
            session['full_name'] = user['full_name']
            session['role'] = 'patient'

            # Record access log entry
            client_ip = request.remote_addr or '127.0.0.1'
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, access_type, ip_address, actor_type, actor_name)
                VALUES (?, 'LOGIN', ?, 'PATIENT', ?)
                """,
                (user['id'], client_ip, user['full_name'])
            )
            db.commit()

            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for('dashboard'))

        except sqlite3.Error:
            flash("An error occurred during sign in. Please try again.", "error")
            return render_template('login.html', identifier=identifier)

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Clear user session and redirect to landing page."""
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('index'))


# ============================================================================
# Doctor Portal & Verification Routes
# ============================================================================

@app.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():
    """
    Doctor authentication route.
    Accepts Email or Doctor ID with password, verifies credentials,
    sets doctor session state, and redirects to doctor dashboard.
    """
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        if not identifier or not password:
            flash("Please provide both Doctor ID / Email and password.", "error")
            return render_template('doctor_login.html', identifier=identifier)

        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT id, doctor_id, full_name, email, specialization, hospital_or_clinic,
                       registration_number, verification_status, password_hash
                FROM doctors
                WHERE email = ? OR UPPER(doctor_id) = ?
                """,
                (identifier.lower(), identifier.upper())
            )
            doctor = cursor.fetchone()

            if doctor is None or not check_password_hash(doctor['password_hash'], password):
                flash("Invalid doctor ID / email or password.", "error")
                return render_template('doctor_login.html', identifier=identifier)

            # Establish authenticated doctor session
            session.clear()
            session['doctor_id'] = doctor['id']
            session['doc_code'] = doctor['doctor_id']
            session['full_name'] = doctor['full_name']
            session['specialization'] = doctor['specialization']
            session['hospital_or_clinic'] = doctor['hospital_or_clinic']
            session['registration_number'] = doctor['registration_number']
            session['verification_status'] = doctor['verification_status']
            session['role'] = 'doctor'

            flash(f"Welcome, {doctor['full_name']}!", "success")
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('doctor_dashboard'))

        except sqlite3.Error:
            flash("An error occurred during doctor sign in. Please try again.", "error")
            return render_template('doctor_login.html', identifier=identifier)

    return render_template('doctor_login.html')


@app.route('/doctor/register', methods=['GET', 'POST'])
def doctor_register():
    """
    Doctor registration route.
    Allows medical practitioners to register.
    Academic / Prototype Note: Real medical council API verification is not performed.
    Accounts are created with verification_status = 'pending' by default.
    """
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        specialization = request.form.get('specialization', '').strip()
        hospital = request.form.get('hospital_or_clinic', '').strip()
        registration_num = request.form.get('registration_number', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validations
        if not full_name or not email or not specialization or not hospital or not registration_num or not password:
            flash("Please complete all required fields.", "error")
            return render_template('doctor_register.html', full_name=full_name, email=email,
                                   phone=phone, specialization=specialization,
                                   hospital_or_clinic=hospital, registration_number=registration_num)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template('doctor_register.html', full_name=full_name, email=email,
                                   phone=phone, specialization=specialization,
                                   hospital_or_clinic=hospital, registration_number=registration_num)

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template('doctor_register.html', full_name=full_name, email=email,
                                   phone=phone, specialization=specialization,
                                   hospital_or_clinic=hospital, registration_number=registration_num)

        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute("SELECT id FROM doctors WHERE email = ?", (email,))
            if cursor.fetchone():
                flash("A doctor account with this email address already exists. Please sign in.", "error")
                return render_template('doctor_register.html', full_name=full_name, email=email,
                                       phone=phone, specialization=specialization,
                                       hospital_or_clinic=hospital, registration_number=registration_num)

            doc_id = generate_unique_doctor_id(db)
            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO doctors (doctor_id, full_name, email, phone, password_hash,
                                     specialization, hospital_or_clinic, registration_number, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (doc_id, full_name, email, phone, password_hash, specialization, hospital, registration_num)
            )
            db.commit()

            flash(
                f"Doctor account registered successfully! Your Doctor ID is {doc_id}. "
                "Account status is Pending Verification (Academic Prototype).",
                "success"
            )
            return redirect(url_for('doctor_login'))

        except sqlite3.Error:
            db.rollback()
            flash("A database error occurred during doctor registration. Please try again.", "error")
            return render_template('doctor_register.html', full_name=full_name, email=email,
                                   phone=phone, specialization=specialization,
                                   hospital_or_clinic=hospital, registration_number=registration_num)

    return render_template('doctor_register.html')


@app.route('/doctor/dashboard')
@doctor_required
def doctor_dashboard():
    """
    Dedicated Doctor Portal Dashboard.
    Displays doctor profile details, verification status, patient lookup tools,
    and recent patient record access history.
    """
    doctor_id = session['doctor_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor:
        session.clear()
        flash("Doctor session expired or invalid.", "error")
        return redirect(url_for('doctor_login'))

    # Retrieve recent patient accesses logged by this doctor
    cursor.execute(
        """
        SELECT al.id, al.accessed_at, al.reason, al.ip_address,
               u.medi_id, u.full_name as patient_name
        FROM access_logs al
        JOIN users u ON al.user_id = u.id
        WHERE al.doctor_id = ? AND al.access_type = 'DOCTOR_ACCESS'
        ORDER BY al.id DESC
        LIMIT 10
        """,
        (doctor_id,)
    )
    recent_accesses = cursor.fetchall()

    return render_template('doctor_dashboard.html', doctor=doctor, recent_accesses=recent_accesses)


@app.route('/doctor/patient/search', methods=['GET', 'POST'])
@doctor_required
def doctor_patient_search():
    """
    Secure doctor-only patient lookup endpoint.
    Accepts SahayID Number or scanned QR URL, validates format,
    verifies doctor status, looks up patient, and directs to the
    authorization confirmation screen.
    """
    if request.method == 'GET':
        sahay_id = request.args.get('sahay_id', '').strip()
        if not sahay_id:
            return redirect(url_for('doctor_dashboard'))
    else:
        sahay_id = request.form.get('sahay_id', '').strip()

    # 1. Confirm doctor is authenticated and verified
    doctor_id = session.get('doctor_id')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT verification_status FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor or doctor['verification_status'] != 'verified':
        status_label = doctor['verification_status'].title() if doctor else 'Unknown'
        flash(
            f"Access restricted: Only verified doctors are authorized to access patient records. "
            f"Your current status is: {status_label}.",
            "error"
        )
        return redirect(url_for('doctor_dashboard'))

    if not sahay_id:
        flash("Please enter a valid SahayID Number to search.", "error")
        return redirect(url_for('doctor_dashboard'))

    # Support raw QR URLs (e.g. http://127.0.0.1:5000/emergency/MED-XXXXXX or /emergency/MED-XXXXXX)
    if '/emergency/' in sahay_id:
        sahay_id = sahay_id.split('/emergency/')[-1].split('?')[0].split('/')[0].strip()

    sahay_id = sahay_id.upper()

    # 3. Validate SahayID format
    if not re.match(r"^MED-[A-Z0-9]{4,16}$", sahay_id):
        flash("Invalid SahayID format. SahayID must be in format MED-XXXXXXXX.", "error")
        return redirect(url_for('doctor_dashboard'))

    # 4. Look up patient securely
    cursor.execute("SELECT id, medi_id, full_name FROM users WHERE UPPER(medi_id) = ?", (sahay_id,))
    patient = cursor.fetchone()

    # 5. If not found, show a safe error
    if not patient:
        flash(f"No patient record found for SahayID Number: {sahay_id}.", "error")
        return redirect(url_for('doctor_dashboard'))

    # 6. If found, route to patient access confirmation screen
    return redirect(url_for('doctor_patient_confirm', medi_id=patient['medi_id']))


@app.route('/doctor/patient/<medi_id>/confirm', methods=['GET', 'POST'])
@doctor_required
def doctor_patient_confirm(medi_id):
    """
    Access Confirmation Screen.
    Displays limited patient summary (Name, SahayID, DOB) and accessing doctor details.
    Presents prominent privacy/audit notice before doctor authorizes full medical record access.
    """
    doctor_id = session['doctor_id']
    db = get_db()
    cursor = db.cursor()

    # Verify doctor profile and verification status
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor:
        session.clear()
        return redirect(url_for('doctor_login'))

    if doctor['verification_status'] != 'verified':
        flash(
            f"Access restricted: Only verified doctors are authorized to access patient records. "
            f"Your current status is: {doctor['verification_status'].title()}.",
            "error"
        )
        return redirect(url_for('doctor_dashboard'))

    clean_id = medi_id.strip().upper()
    if not re.match(r"^MED-[A-Z0-9]{4,16}$", clean_id):
        flash("Invalid SahayID format.", "error")
        return redirect(url_for('doctor_dashboard'))

    cursor.execute("SELECT id, medi_id, full_name FROM users WHERE UPPER(medi_id) = ?", (clean_id,))
    patient = cursor.fetchone()
    if not patient:
        flash(f"No patient record found for SahayID Number: {clean_id}.", "error")
        return redirect(url_for('doctor_dashboard'))

    if request.method == 'POST':
        # Doctor confirmed access
        reason = request.form.get('reason', '').strip() or 'Authorized Clinical Review'
        client_ip = request.remote_addr or '127.0.0.1'

        try:
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
                VALUES (?, ?, 'DOCTOR', ?, ?, ?, 'DOCTOR_ACCESS', ?)
                """,
                (patient['id'], doctor['id'], doctor['full_name'], doctor['hospital_or_clinic'], reason, client_ip)
            )
            db.commit()
        except sqlite3.Error:
            pass

        # Authorize session for this patient
        session[f'doc_auth_{patient["medi_id"]}'] = True
        flash("Patient clinical record accessed and logged.", "success")
        return redirect(url_for('doctor_patient_view', medi_id=patient['medi_id']))

    # GET: Retrieve limited identifier (DOB only) - zero medical profile data
    cursor.execute("SELECT date_of_birth FROM medical_profiles WHERE user_id = ?", (patient['id'],))
    mp = cursor.fetchone()
    date_of_birth = mp['date_of_birth'] if mp else None

    return render_template(
        'doctor_patient_confirm.html',
        patient=patient,
        date_of_birth=date_of_birth,
        doctor=doctor
    )


@app.route('/doctor/patient/<medi_id>/access', methods=['POST'])
@doctor_required
def doctor_patient_access(medi_id):
    """
    Action handler for confirming patient access.
    """
    return doctor_patient_confirm(medi_id)


@app.route('/doctor/patient/<medi_id>')
@doctor_required
def doctor_patient_view(medi_id):
    """
    Authorized Doctor Clinical View.
    Enforces doctor verification status and authorization confirmation.
    Displays patient's complete medical record to authorized physician in read-only mode.
    """
    doctor_id = session['doctor_id']
    db = get_db()
    cursor = db.cursor()

    # Verify doctor profile and verification status
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor:
        session.clear()
        return redirect(url_for('doctor_login'))

    if doctor['verification_status'] != 'verified':
        flash(
            f"Access restricted: Only verified doctors are authorized to access patient records. "
            f"Your current status is: {doctor['verification_status'].title()}.",
            "error"
        )
        return redirect(url_for('doctor_dashboard'))

    clean_id = medi_id.strip().upper()
    cursor.execute("SELECT * FROM users WHERE UPPER(medi_id) = ?", (clean_id,))
    patient = cursor.fetchone()
    if not patient:
        flash(f"No patient record found for SahayID Number: {clean_id}", "error")
        return redirect(url_for('doctor_dashboard'))

    # Check if access was confirmed
    is_session_auth = session.get(f'doc_auth_{patient["medi_id"]}')
    query_reason = request.args.get('reason')
    is_confirmed_query = (request.args.get('confirmed') == '1')

    if not is_session_auth and not query_reason and not is_confirmed_query:
        # Confirmation required before viewing full medical record
        return redirect(url_for('doctor_patient_confirm', medi_id=patient['medi_id']))

    # If reason passed via query (e.g. direct authorized link or test) and not yet in session, log it
    if query_reason and not is_session_auth:
        client_ip = request.remote_addr or '127.0.0.1'
        try:
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
                VALUES (?, ?, 'DOCTOR', ?, ?, ?, 'DOCTOR_ACCESS', ?)
                """,
                (patient['id'], doctor['id'], doctor['full_name'], doctor['hospital_or_clinic'], query_reason, client_ip)
            )
            db.commit()
        except sqlite3.Error:
            pass
        session[f'doc_auth_{patient["medi_id"]}'] = True

    # Retrieve patient medical profile (read-only)
    cursor.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (patient['id'],))
    profile = cursor.fetchone()

    # Retrieve emergency contacts (read-only)
    cursor.execute(
        "SELECT name, relationship, phone FROM emergency_contacts WHERE user_id = ? ORDER BY id ASC",
        (patient['id'],)
    )
    contacts = cursor.fetchall()

    return render_template(
        'doctor_patient_view.html',
        patient=patient,
        profile=profile,
        contacts=contacts,
        doctor=doctor
    )



# ============================================================================
# Authenticated Patient Portal Routes
# ============================================================================

@app.route('/dashboard')
@login_required
@patient_required
def dashboard():
    """
    Patient Dashboard.
    Displays user SahayID Number, personal summary, profile completion percentage,
    blood group, emergency contacts overview, scannable QR code, and
    the audit history of all emergency and doctor accesses.
    """
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Retrieve current user record
    cursor.execute(
        "SELECT id, medi_id, full_name, email, phone, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    user = cursor.fetchone()
    if not user:
        session.clear()
        flash("Session invalid. Please sign in again.", "error")
        return redirect(url_for('login'))

    # Retrieve medical profile record
    cursor.execute(
        "SELECT * FROM medical_profiles WHERE user_id = ?",
        (user_id,)
    )
    profile = cursor.fetchone()

    # Self-heal profile if missing
    if not profile:
        cursor.execute("INSERT INTO medical_profiles (user_id) VALUES (?)", (user_id,))
        db.commit()
        cursor.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (user_id,))
        profile = cursor.fetchone()

    # Retrieve emergency contact count
    cursor.execute(
        "SELECT COUNT(*) as count FROM emergency_contacts WHERE user_id = ?",
        (user_id,)
    )
    contact_count_row = cursor.fetchone()
    contact_count = contact_count_row['count'] if contact_count_row else 0

    completion_pct = calculate_profile_completion(profile, contact_count)

    # Ensure QR code exists on disk for current user (handles legacy/existing users)
    qr_file = os.path.join(QR_DIR, f"{user['medi_id']}.png")
    if not os.path.exists(qr_file):
        base_url = request.host_url.rstrip('/') if request else None
        generate_medi_qr(user['medi_id'], base_url)

    # Retrieve Emergency Access History & Doctor Access Events
    cursor.execute(
        """
        SELECT responder_name, organization, reason, created_at, expires_at, accessed_at, ip_address, 'EMERGENCY' as access_source
        FROM emergency_access
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (user_id,)
    )
    emergency_rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT actor_name as responder_name, organization, reason, accessed_at as created_at,
               'Authorized Session' as expires_at, accessed_at, ip_address, 'DOCTOR' as access_source
        FROM access_logs
        WHERE user_id = ? AND access_type = 'DOCTOR_ACCESS'
        ORDER BY accessed_at DESC
        LIMIT 10
        """,
        (user_id,)
    )
    doctor_rows = cursor.fetchall()

    all_history_rows = list(emergency_rows) + list(doctor_rows)
    all_history_rows.sort(key=lambda r: r['created_at'] or '', reverse=True)

    access_history = []
    now_utc_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    for row in all_history_rows[:15]:
        if row['access_source'] == 'DOCTOR':
            status = 'Authorized'
            actor_label = f"Doctor: {row['responder_name']}"
        else:
            status = 'Active' if row['expires_at'] > now_utc_str else 'Expired'
            actor_label = row['responder_name']

        access_history.append({
            'responder_name': actor_label,
            'organization': row['organization'],
            'reason': row['reason'],
            'created_at': row['created_at'][:19] if row['created_at'] else '',
            'expires_at': row['expires_at'][:19] if row['expires_at'] else '',
            'ip_address': row['ip_address'],
            'status': status,
            'access_source': row['access_source']
        })

    return render_template(
        'dashboard.html',
        user=user,
        profile=profile,
        contact_count=contact_count,
        completion_pct=completion_pct,
        access_history=access_history
    )


@app.route('/download-qr')
@login_required
@patient_required
def download_qr():
    """
    Secure QR code file download.
    STRICT SECURITY: Strictly serves the currently authenticated user's QR file.
    Does NOT accept any filename or user identifier from query params or URL.
    """
    medi_id = session.get('medi_id')
    if not medi_id:
        flash("Unable to identify current patient profile.", "error")
        return redirect(url_for('dashboard'))

    qr_path = os.path.join(QR_DIR, f"{medi_id}.png")
    if not os.path.exists(qr_path):
        base_url = request.host_url.rstrip('/') if request else None
        generate_medi_qr(medi_id, base_url)

    return send_file(
        qr_path,
        as_attachment=True,
        download_name=f"{medi_id}_emergency_qr.png",
        mimetype='image/png'
    )


@app.route('/regenerate-qr', methods=['POST'])
@login_required
@patient_required
def regenerate_qr():
    """
    Regenerates the authenticated user's QR code image.
    Preserves the existing MediID and updates the image file.
    """
    medi_id = session.get('medi_id')
    if not medi_id:
        flash("Session expired. Please sign in again.", "error")
        return redirect(url_for('login'))

    base_url = request.host_url.rstrip('/') if request else None
    generate_medi_qr(medi_id, base_url)

    flash("Your emergency QR code has been regenerated successfully.", "success")
    return redirect(url_for('dashboard'))


@app.route('/medical-profile', methods=['GET', 'POST'])
@login_required
@patient_required
def medical_profile():
    """
    Medical Profile Management.
    GET: View and populate current medical profile details.
    POST: Update vital clinical information strictly for the logged-in user.
    """
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        date_of_birth = request.form.get('date_of_birth', '').strip()
        gender = request.form.get('gender', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        allergies = request.form.get('allergies', '').strip()
        medical_conditions = request.form.get('medical_conditions', '').strip()
        current_medications = request.form.get('current_medications', '').strip()
        previous_surgeries = request.form.get('previous_surgeries', '').strip()
        additional_notes = request.form.get('additional_notes', '').strip()

        try:
            # Update only the current user's medical profile
            cursor.execute(
                """
                UPDATE medical_profiles
                SET date_of_birth = ?,
                    gender = ?,
                    blood_group = ?,
                    allergies = ?,
                    medical_conditions = ?,
                    current_medications = ?,
                    previous_surgeries = ?,
                    additional_notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    date_of_birth,
                    gender,
                    blood_group,
                    allergies,
                    medical_conditions,
                    current_medications,
                    previous_surgeries,
                    additional_notes,
                    user_id
                )
            )

            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO medical_profiles (
                        user_id, date_of_birth, gender, blood_group, allergies,
                        medical_conditions, current_medications, previous_surgeries, additional_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id, date_of_birth, gender, blood_group, allergies,
                        medical_conditions, current_medications, previous_surgeries, additional_notes
                    )
                )

            db.commit()
            flash("Medical profile updated successfully.", "success")
            return redirect(url_for('medical_profile'))

        except sqlite3.Error:
            db.rollback()
            flash("Failed to update medical profile. Please try again.", "error")

    # GET request - load existing profile
    cursor.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()

    return render_template('medical_profile.html', profile=profile)


@app.route('/emergency-contacts', methods=['GET', 'POST'])
@login_required
@patient_required
def emergency_contacts():
    """
    Emergency Contacts Management.
    GET: View contacts belonging exclusively to the authenticated user.
    POST: Add a new emergency contact for the authenticated user.
    """
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        relationship = request.form.get('relationship', '').strip()
        phone = request.form.get('phone', '').strip()

        if not name or not phone:
            flash("Both contact name and phone number are required.", "error")
            return redirect(url_for('emergency_contacts'))

        try:
            cursor.execute(
                """
                INSERT INTO emergency_contacts (user_id, name, relationship, phone)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, name, relationship, phone)
            )
            db.commit()
            flash(f"Emergency contact '{name}' added successfully.", "success")
            return redirect(url_for('emergency_contacts'))

        except sqlite3.Error:
            db.rollback()
            flash("Failed to add emergency contact. Please try again.", "error")
            return redirect(url_for('emergency_contacts'))

    # GET request - retrieve user's contacts
    cursor.execute(
        "SELECT id, name, relationship, phone, created_at FROM emergency_contacts WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    )
    contacts = cursor.fetchall()

    return render_template('emergency_contacts.html', contacts=contacts)


@app.route('/emergency-contacts/delete/<int:contact_id>', methods=['POST'])
@login_required
@patient_required
def delete_emergency_contact(contact_id):
    """
    Secure deletion of an emergency contact.
    CRITICAL SECURITY: Verifies that contact_id belongs to session['user_id'] before deleting.
    """
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id, name FROM emergency_contacts WHERE id = ? AND user_id = ?",
        (contact_id, user_id)
    )
    contact = cursor.fetchone()

    if not contact:
        flash("Emergency contact not found or access denied.", "error")
        return redirect(url_for('emergency_contacts'))

    try:
        cursor.execute(
            "DELETE FROM emergency_contacts WHERE id = ? AND user_id = ?",
            (contact_id, user_id)
        )
        db.commit()
        flash(f"Contact '{contact['name']}' removed successfully.", "success")
    except sqlite3.Error:
        db.rollback()
        flash("Failed to remove emergency contact.", "error")

    return redirect(url_for('emergency_contacts'))


# ============================================================================
# Emergency Gateway & Verification Routes
# ============================================================================

@app.route('/emergency/<medi_id>')
def emergency_access(medi_id):
    """
    Emergency Scanned Gateway.
    Target endpoint encoded inside the SahayID QR code.
    Publicly accessible to first responders and doctors scanning a physical badge/card.
    CRITICAL PRIVACY: Does NOT expose medical information directly.
    Presents an authorization gateway and logs the access scan event.
    """
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id, medi_id, created_at FROM users WHERE UPPER(medi_id) = ?",
        (medi_id.upper(),)
    )
    user = cursor.fetchone()

    if not user:
        flash(f"No active record found for SahayID: {medi_id}", "error")
        return render_template('emergency_access.html', medi_id=medi_id, not_found=True), 404

    # Log emergency scan event
    client_ip = request.remote_addr or '127.0.0.1'
    try:
        cursor.execute(
            """
            INSERT INTO access_logs (user_id, access_type, ip_address, actor_type)
            VALUES (?, 'EMERGENCY_SCAN', ?, 'RESPONDER')
            """,
            (user['id'], client_ip)
        )
        db.commit()
    except sqlite3.Error:
        pass

    is_doctor = (session.get('role') == 'doctor')
    doctor_name = session.get('full_name') if is_doctor else None

    return render_template(
        'emergency_access.html',
        medi_id=user['medi_id'],
        is_doctor=is_doctor,
        doctor_name=doctor_name
    )


@app.route('/emergency/<medi_id>/verify', methods=['GET', 'POST'])
def emergency_verify(medi_id):
    """
    Emergency Authorization Protocol.
    Allows first responders to confirm the emergency situation and state their identity/reason.
    Generates a cryptographically random, temporary access token (10-minute expiry)
    and stores only the SHA-256 hash in the database.
    """
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id, medi_id, full_name FROM users WHERE UPPER(medi_id) = ?",
        (medi_id.upper(),)
    )
    user = cursor.fetchone()

    if not user:
        flash(f"Unrecognized MediID: {medi_id}", "error")
        return render_template('emergency_access.html', medi_id=medi_id, not_found=True), 404

    if request.method == 'POST':
        responder_name = request.form.get('responder_name', '').strip()
        organization = request.form.get('organization', '').strip()
        reason = request.form.get('reason', '').strip()
        confirm_emergency = request.form.get('confirm_emergency')

        # Form validations
        if not confirm_emergency:
            flash("You must confirm that this access is for an emergency medical purpose.", "error")
            return render_template('emergency_verify.html', medi_id=user['medi_id'],
                                   responder_name=responder_name, organization=organization, reason=reason), 400

        if not responder_name:
            flash("Responder name is required.", "error")
            return render_template('emergency_verify.html', medi_id=user['medi_id'],
                                   responder_name=responder_name, organization=organization, reason=reason), 400

        if not reason:
            flash("Reason for emergency access is required.", "error")
            return render_template('emergency_verify.html', medi_id=user['medi_id'],
                                   responder_name=responder_name, organization=organization, reason=reason), 400

        # Rate limiting / abuse protection: check attempts within last 10 minutes
        cursor.execute(
            """
            SELECT COUNT(*) as count FROM emergency_access
            WHERE user_id = ? AND datetime(created_at) > datetime('now', '-10 minutes')
            """,
            (user['id'],)
        )
        recent_count = cursor.fetchone()['count']
        if recent_count >= 5:
            flash("Emergency access requests for this MediID are temporarily rate-limited. Please wait a few minutes before trying again.", "error")
            return render_template('emergency_verify.html', medi_id=user['medi_id'],
                                   responder_name=responder_name, organization=organization, reason=reason), 429

        # Generate cryptographically secure random token (URL-safe)
        raw_token = secrets.token_urlsafe(32)
        # Store only SHA-256 hash in the database
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        # Set 10-minute expiry timestamp in UTC
        now_utc = datetime.now(timezone.utc)
        expires_at = (now_utc + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
        client_ip = request.remote_addr or '127.0.0.1'

        try:
            # Insert into emergency_access
            cursor.execute(
                """
                INSERT INTO emergency_access (
                    user_id, token_hash, responder_name, organization, reason, expires_at, ip_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user['id'], token_hash, responder_name, organization, reason, expires_at, client_ip)
            )

            # Log to access_logs table
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, access_type, ip_address)
                VALUES (?, 'EMERGENCY_ACCESS', ?)
                """,
                (user['id'], client_ip)
            )

            db.commit()

            # Redirect to temporary random token URL (NO medical data in URL)
            return redirect(url_for('emergency_access_view', token=raw_token))

        except sqlite3.Error:
            db.rollback()
            flash("A server error occurred while processing emergency verification.", "error")
            return render_template('emergency_verify.html', medi_id=user['medi_id'],
                                   responder_name=responder_name, organization=organization, reason=reason)

    return render_template('emergency_verify.html', medi_id=user['medi_id'])


@app.route('/emergency/access/<token>')
def emergency_access_view(token):
    """
    Temporary Emergency Clinical Information View.
    Resolves temporary token via SHA-256 hash lookup.
    Enforces strict server-side 10-minute expiration.
    Displays critical medical essentials, allergies, and emergency contacts.
    """
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT ea.*, u.full_name, u.medi_id,
               mp.date_of_birth, mp.gender, mp.blood_group,
               mp.allergies, mp.medical_conditions, mp.current_medications, mp.previous_surgeries
        FROM emergency_access ea
        JOIN users u ON ea.user_id = u.id
        LEFT JOIN medical_profiles mp ON u.id = mp.user_id
        WHERE ea.token_hash = ?
        """,
        (token_hash,)
    )
    access_record = cursor.fetchone()

    if not access_record:
        return render_template(
            'emergency_information.html',
            error="Invalid or unrecognized emergency access token.",
            expired=True
        ), 404

    # Server-side Expiration Check
    now_utc = datetime.now(timezone.utc)
    try:
        expires_dt = datetime.strptime(access_record['expires_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except ValueError:
        expires_dt = datetime.fromisoformat(access_record['expires_at']).replace(tzinfo=timezone.utc)

    if now_utc > expires_dt:
        return render_template(
            'emergency_information.html',
            error="Emergency access has expired.",
            expired=True,
            medi_id=access_record['medi_id']
        ), 403

    # Update accessed_at timestamp if first view
    if not access_record['accessed_at']:
        try:
            cursor.execute(
                "UPDATE emergency_access SET accessed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (access_record['id'],)
            )
            db.commit()
        except sqlite3.Error:
            pass

    # Retrieve patient emergency contacts
    cursor.execute(
        "SELECT name, relationship, phone FROM emergency_contacts WHERE user_id = ? ORDER BY id ASC",
        (access_record['user_id'],)
    )
    contacts = cursor.fetchall()

    remaining_seconds = max(0, int((expires_dt - now_utc).total_seconds()))

    patient_data = {
        'full_name': access_record['full_name'],
        'medi_id': access_record['medi_id'],
        'date_of_birth': access_record['date_of_birth'],
        'gender': access_record['gender'],
        'blood_group': access_record['blood_group']
    }

    medical_data = {
        'allergies': access_record['allergies'],
        'medical_conditions': access_record['medical_conditions'],
        'current_medications': access_record['current_medications'],
        'previous_surgeries': access_record['previous_surgeries']
    }

    access_meta = {
        'responder_name': access_record['responder_name'],
        'organization': access_record['organization'],
        'reason': access_record['reason'],
        'created_at': access_record['created_at'],
        'expires_at': access_record['expires_at'],
        'medi_id': access_record['medi_id']
    }

    return render_template(
        'emergency_information.html',
        patient=patient_data,
        medical=medical_data,
        contacts=contacts,
        access=access_meta,
        remaining_seconds=remaining_seconds
    )


# ============================================================================
# Security Headers & Custom HTTP Error Handlers
# ============================================================================

@app.after_request
def set_security_headers(response):
    """
    Attach standard defensive HTTP security headers to all outgoing responses.
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


@app.errorhandler(404)
def not_found_error(error):
    """Render custom branded 404 page."""
    return render_template('404.html'), 404


@app.errorhandler(403)
def forbidden_error(error):
    """Render custom branded 403 page."""
    return render_template('403.html'), 403


@app.errorhandler(429)
def ratelimit_error(error):
    """Render custom branded 429 page."""
    return render_template('429.html'), 429


@app.errorhandler(500)
def internal_error(error):
    """Render custom branded 500 page."""
    return render_template('500.html'), 500


if __name__ == '__main__':
    # Run the application locally on http://127.0.0.1:5000
    app.run(host='127.0.0.1', port=5000, debug=True)
