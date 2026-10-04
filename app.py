"""
MediID - Digital Medical Identity System
Part 5: Emergency Access & Verification System
"""

import os
import secrets
import string
import hashlib
import sqlite3
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
# Authentication Decorator
# ============================================================================

def login_required(f):
    """
    Decorator requiring an active session user_id to access protected routes.
    Redirects unauthenticated visitors to the login view.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access your MediID portal.", "error")
            return redirect(url_for('login'))
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

        # 5. emergency_access table (Part 5)
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

            # Establish authenticated session
            session.clear()
            session['user_id'] = user['id']
            session['medi_id'] = user['medi_id']
            session['full_name'] = user['full_name']

            # Record access log entry
            client_ip = request.remote_addr or '127.0.0.1'
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, access_type, ip_address)
                VALUES (?, ?, ?)
                """,
                (user['id'], 'LOGIN', client_ip)
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
    """Clear user session and redirect to login page."""
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('login'))


# ============================================================================
# Authenticated Patient Portal Routes
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Patient Dashboard.
    Displays user MediID, personal summary, profile completion percentage,
    blood group, emergency contacts overview, scannable QR code, and
    the audit history of all emergency accesses.
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

    # Retrieve Emergency Access History (Part 5)
    cursor.execute(
        """
        SELECT responder_name, organization, reason, created_at, expires_at, accessed_at, ip_address
        FROM emergency_access
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (user_id,)
    )
    raw_history = cursor.fetchall()
    access_history = []
    now_utc_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    for row in raw_history:
        status = 'Active' if row['expires_at'] > now_utc_str else 'Expired'
        access_history.append({
            'responder_name': row['responder_name'],
            'organization': row['organization'],
            'reason': row['reason'],
            'created_at': row['created_at'][:19] if row['created_at'] else '',
            'expires_at': row['expires_at'][:19] if row['expires_at'] else '',
            'ip_address': row['ip_address'],
            'status': status
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
# Emergency Gateway & Verification Routes (Parts 4 & 5)
# ============================================================================

@app.route('/emergency/<medi_id>')
def emergency_access(medi_id):
    """
    Emergency Scanned Gateway.
    Target endpoint encoded inside the MediID QR code.
    Publicly accessible to first responders scanning a physical badge/card.
    CRITICAL PRIVACY: Does NOT expose medical information.
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
        flash(f"No active record found for MediID: {medi_id}", "error")
        return render_template('emergency_access.html', medi_id=medi_id, not_found=True), 404

    # Log emergency scan event
    client_ip = request.remote_addr or '127.0.0.1'
    try:
        cursor.execute(
            """
            INSERT INTO access_logs (user_id, access_type, ip_address)
            VALUES (?, 'EMERGENCY_SCAN', ?)
            """,
            (user['id'], client_ip)
        )
        db.commit()
    except sqlite3.Error:
        pass

    return render_template('emergency_access.html', medi_id=user['medi_id'])


@app.route('/emergency/<medi_id>/verify', methods=['GET', 'POST'])
def emergency_verify(medi_id):
    """
    Emergency Authorization Protocol (Part 5).
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
    Temporary Emergency Clinical Information View (Part 5).
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


if __name__ == '__main__':
    # Run the application locally on http://127.0.0.1:5000
    app.run(host='127.0.0.1', port=5000, debug=True)
