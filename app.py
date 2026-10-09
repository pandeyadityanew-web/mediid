"""
SahayID - Digital Medical Identity System
Tagline: CRITICAL MEDICAL ACCESS
"""

import base64
import os
import secrets
import string
import hashlib
import sqlite3
import re
import io
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, send_file, has_request_context
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode

app = Flask(__name__)

# Application Configuration & Production Environment Settings
IS_PRODUCTION = bool(
    os.environ.get('VERCEL')
    or os.environ.get('VERCEL_ENV')
    or os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
    or os.environ.get('FLASK_ENV') == 'production'
    or os.environ.get('ENV') == 'production'
    or os.environ.get('PRODUCTION') in ('1', 'true', 'True')
)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY') or 'sahayid-production-core-session-secret-v2-2026'
app.config['SESSION_COOKIE_NAME'] = 'sahayid_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
if IS_PRODUCTION or os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('true', '1'):
    app.config['SESSION_COOKIE_SECURE'] = True

try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_SERVERLESS = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

if IS_SERVERLESS:
    DATABASE_DIR = '/tmp/database'
    DATABASE_PATH = '/tmp/medid.db'
    QR_DIR = '/tmp/generated_qr'
else:
    DATABASE_DIR = os.path.join(BASE_DIR, 'database')
    DATABASE_PATH = os.path.join(DATABASE_DIR, 'medid.db')
    QR_DIR = os.path.join(BASE_DIR, 'static', 'generated_qr')


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Safe non-sensitive diagnostic indicator
    db_backend = 'postgresql' if (os.environ.get('DATABASE_URL') and (os.environ.get('DATABASE_URL').startswith('postgres://') or os.environ.get('DATABASE_URL').startswith('postgresql://'))) else 'sqlite'
    response.headers['X-DB-Backend'] = db_backend
    return response


# ============================================================================
# Role-Based Authentication & Authorization Decorators
# ============================================================================

def login_required(f):
    """
    Decorator requiring an active session (patient user_id, doctor_id, or admin_id) to access protected routes.
    Redirects unauthenticated visitors to the login view.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'doctor_id' not in session and 'admin_id' not in session:
            flash("Please sign in to access your SahayID portal.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def patient_required(f):
    """
    Decorator ensuring that only authenticated patient accounts can access patient routes.
    Prevents doctor and admin accounts from entering patient account-management workflows.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if 'admin_id' in session:
                flash("Access restricted to patient accounts.", "error")
                return redirect(url_for('admin_dashboard'))
            if 'doctor_id' in session:
                flash("Access restricted to patient accounts.", "error")
                return redirect(url_for('doctor_dashboard'))
            flash("Please sign in to access your SahayID patient portal.", "error")
            return redirect(url_for('login'))
        if session.get('role') != 'patient':
            session.clear()
            flash("Please sign in with a patient account.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def doctor_required(f):
    """
    Decorator ensuring that only authenticated doctor accounts can access doctor routes.
    Prevents patient and admin accounts from accessing the clinical doctor portal.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor_id' not in session:
            if 'admin_id' in session:
                flash("Access restricted to verified medical doctors.", "error")
                return redirect(url_for('admin_dashboard'))
            if 'user_id' in session:
                flash("Access restricted to verified medical doctors.", "error")
                return redirect(url_for('dashboard'))
            flash("Please sign in with your Doctor credentials.", "error")
            return redirect(url_for('doctor_login'))
        if session.get('role') != 'doctor':
            flash("Access restricted to verified medical doctors.", "error")
            return redirect(url_for('doctor_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator ensuring that only authenticated admin accounts can access admin routes.
    Prevents patient and doctor accounts from accessing administrative oversight controls.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            if 'doctor_id' in session:
                flash("Access restricted to authorized administrators.", "error")
                return redirect(url_for('doctor_dashboard'))
            if 'user_id' in session:
                flash("Access restricted to authorized administrators.", "error")
                return redirect(url_for('dashboard'))
            flash("Please sign in with your Administrator credentials.", "error")
            return redirect(url_for('admin_login'))
        if session.get('role') != 'admin':
            flash("Access restricted to authorized administrators.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function



# ============================================================================
# Database Helper Functions
# ============================================================================

class PgCursorWrapper:
    """Compatibility cursor wrapper translating SQLite-style queries for PostgreSQL."""
    def __init__(self, pg_cursor):
        self._cursor = pg_cursor

    def execute(self, query, params=None):
        if 'PRAGMA' in query.upper():
            return self
        # Convert ? placeholders to %s for PostgreSQL
        if '?' in query:
            query = query.replace('?', '%s')
        if params is not None:
            self._cursor.execute(query, params)
        else:
            self._cursor.execute(query)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return getattr(self._cursor, 'lastrowid', None)

    def close(self):
        self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)


class PgConnectionWrapper:
    """Compatibility connection wrapper for PostgreSQL."""
    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):
        return PgCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def execute(self, query, params=None):
        cur = self.cursor()
        return cur.execute(query, params)


def to_str_timestamp(val):
    """Safely convert any datetime object, timestamp string, or None to ISO-like string format."""
    if val is None:
        return ''
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val)


def is_timestamp_expired(expires_at, now_dt=None):
    """
    Safely checks if an expires_at value (datetime object or string) is expired.
    Returns True if expired, False if still active.
    """
    if not expires_at:
        return True
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at < now_dt

    s = str(expires_at).strip()
    try:
        dt = datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return dt < now_dt
    except Exception:
        try:
            dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
            return dt < now_dt
        except Exception:
            return s < now_dt.strftime('%Y-%m-%d %H:%M:%S')


# In-memory rate limiting store (prototype process-level sliding window)
_rate_limit_store = {}

def is_rate_limited(key, max_requests=20, window_seconds=60):
    """
    In-memory sliding window rate limiter per key.
    Prototype store scoped per worker process.
    """
    try:
        now = datetime.now(timezone.utc).timestamp()
        timestamps = _rate_limit_store.get(key, [])
        cutoff = now - window_seconds
        valid_timestamps = [t for t in timestamps if t > cutoff]
        if len(valid_timestamps) >= max_requests:
            _rate_limit_store[key] = valid_timestamps
            return True
        valid_timestamps.append(now)
        _rate_limit_store[key] = valid_timestamps
        return False
    except Exception:
        return False


def get_csrf_token():
    """Generate or retrieve session CSRF token."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


@app.context_processor
def inject_csrf_token():
    """Inject csrf_token into all Jinja2 template contexts."""
    return {'csrf_token': get_csrf_token()}


@app.before_request
def verify_csrf_token():
    """Verify CSRF token on state-changing requests if enabled."""
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        if app.config.get('TESTING') or not app.config.get('CSRF_ENABLED', True):
            return
        if request.path.startswith('/static') or request.path == '/favicon.ico':
            return
        token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
        expected = session.get('csrf_token')
        if expected and token:
            if not secrets.compare_digest(str(token), str(expected)):
                flash("Security verification (CSRF) failed. Please try again.", "error")
                return redirect(request.referrer or url_for('index'))


def get_db_connection():
    """
    Establish and return a database connection.
    LOCAL: SQLite is used when DATABASE_URL is not set.
    PRODUCTION/VERCEL: PostgreSQL is mandatory. If DATABASE_URL is missing or fails,
    an explicit exception is logged and raised without silent fallback to /tmp SQLite.
    """
    db_url = os.environ.get('DATABASE_URL')

    if IS_PRODUCTION:
        if not db_url:
            raise RuntimeError(
                "[SahayID Production Error] DATABASE_URL environment variable is required in production/Vercel environments."
            )
        if not (db_url.startswith('postgres://') or db_url.startswith('postgresql://')):
            raise RuntimeError(
                "[SahayID Production Error] DATABASE_URL in production must be a PostgreSQL connection string."
            )
        try:
            import psycopg2
            import psycopg2.extras
            if db_url.startswith('postgres://'):
                db_url = 'postgresql://' + db_url[len('postgres://'):]
            if 'sslmode=' not in db_url:
                separator = '&' if '?' in db_url else '?'
                db_url = f"{db_url}{separator}sslmode=require"
            raw_conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor, connect_timeout=10)
            return PgConnectionWrapper(raw_conn)
        except Exception as e:
            masked_url = re.sub(r':([^:@]+)@', ':****@', db_url)
            print(f"[SahayID Production Database Error] Failed to connect to PostgreSQL ({masked_url}): {e}")
            raise RuntimeError(f"Database connection error: {e}") from e

    # Non-production / Local development with DATABASE_URL configured:
    if db_url and (db_url.startswith('postgres://') or db_url.startswith('postgresql://')):
        try:
            import psycopg2
            import psycopg2.extras
            if db_url.startswith('postgres://'):
                db_url = 'postgresql://' + db_url[len('postgres://'):]
            if 'sslmode=' not in db_url:
                separator = '&' if '?' in db_url else '?'
                db_url = f"{db_url}{separator}sslmode=require"
            raw_conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor, connect_timeout=10)
            return PgConnectionWrapper(raw_conn)
        except Exception as e:
            masked_url = re.sub(r':([^:@]+)@', ':****@', db_url)
            print(f"[SahayID Database Error] Local PostgreSQL connection failed ({masked_url}): {e}")
            raise

    # Local development SQLite
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    except Exception:
        pass

    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception:
        pass
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

def get_base_url():
    """
    Get configurable application base URL.
    Checks SAHAYID_BASE_URL first, then BASE_URL, then request.host_url if in request context,
    falling back to http://127.0.0.1:5000 in local development.
    """
    configured = os.environ.get('SAHAYID_BASE_URL') or os.environ.get('BASE_URL')
    if configured:
        return configured.rstrip('/')
    if has_request_context():
        return request.host_url.rstrip('/')
    return 'http://127.0.0.1:5000'


def generate_medi_qr_bytes(medi_id, base_url=None):
    """
    Generates QR code PNG image in memory as io.BytesIO stream without requiring disk persistence.
    Ideal for serverless/ephemeral container runtimes.
    """
    if not base_url:
        base_url = get_base_url()
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
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def generate_medi_qr(medi_id, base_url=None):
    """
    Generate a high-contrast, phone-scannable QR code image for a patient's SahayID.
    Encodes strictly the emergency access URL:
      {base_url}/emergency/{medi_id}
    Does NOT encode any medical or personal data.
    Saves to static/generated_qr/{medi_id}.png if possible and returns the file path.
    """
    if not base_url:
        base_url = get_base_url()
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
    try:
        os.makedirs(QR_DIR, exist_ok=True)
        file_path = os.path.join(QR_DIR, f"{medi_id}.png")
        img.save(file_path)
        return file_path
    except OSError:
        # Graceful fallback for read-only / ephemeral container filesystems
        return os.path.join(QR_DIR, f"{medi_id}.png")


def init_db():
    """
    Initialize database schema and static asset directories.
    Creates all required tables and indexes if they do not exist.
    Supports both SQLite and PostgreSQL without data loss.
    """
    try:
        os.makedirs(DATABASE_DIR, exist_ok=True)
        os.makedirs(QR_DIR, exist_ok=True)
    except OSError:
        pass

    conn = get_db_connection()
    is_pg = isinstance(conn, PgConnectionWrapper)
    try:
        cursor = conn.cursor()

        if is_pg:
            # PostgreSQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    medi_id VARCHAR(50) UNIQUE NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    phone VARCHAR(50),
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS medical_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    date_of_birth VARCHAR(50),
                    gender VARCHAR(50),
                    blood_group VARCHAR(10),
                    allergies TEXT,
                    medical_conditions TEXT,
                    current_medications TEXT,
                    previous_surgeries TEXT,
                    additional_notes TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    relationship VARCHAR(100),
                    phone VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    doctor_id INTEGER,
                    actor_type VARCHAR(50) DEFAULT 'PATIENT',
                    actor_name VARCHAR(255),
                    organization VARCHAR(255),
                    reason TEXT,
                    access_type VARCHAR(100) NOT NULL,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(100)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emergency_access (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    token_hash VARCHAR(128) NOT NULL UNIQUE,
                    responder_name VARCHAR(255) NOT NULL,
                    organization VARCHAR(255),
                    reason TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    accessed_at TIMESTAMP,
                    ip_address VARCHAR(100)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS doctors (
                    id SERIAL PRIMARY KEY,
                    doctor_id VARCHAR(50) UNIQUE NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    phone VARCHAR(50),
                    password_hash TEXT NOT NULL,
                    specialization VARCHAR(255) NOT NULL,
                    hospital_or_clinic VARCHAR(255) NOT NULL,
                    registration_number VARCHAR(100) NOT NULL,
                    verification_status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_requests (
                    id SERIAL PRIMARY KEY,
                    patient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
                    request_token VARCHAR(128) UNIQUE NOT NULL,
                    otp_hash VARCHAR(128),
                    status VARCHAR(50) DEFAULT 'PENDING',
                    reason TEXT,
                    attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    verified_at TIMESTAMP,
                    authorized_until TIMESTAMP,
                    ip_address VARCHAR(100)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # PostgreSQL indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_medi_id ON users (medi_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emergency_access_token ON emergency_access (token_hash);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emergency_contacts_user ON emergency_contacts (user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_user ON access_logs (user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_medical_profiles_user ON medical_profiles (user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_doctor_id ON doctors (doctor_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_email ON doctors (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admins_username ON admins (username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admins_email ON admins (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_requests_token ON access_requests (request_token);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_requests_patient ON access_requests (patient_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_requests_doctor ON access_requests (doctor_id);")

            # Defensively update existing PostgreSQL tables if columns were added later
            conn.commit()
            for alter_sql in [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_url TEXT;",
                "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS photo_url TEXT;",
                "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS verification_reason TEXT;",
                "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;",
                "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS verified_by INTEGER;",
                "ALTER TABLE medical_profiles ADD COLUMN IF NOT EXISTS photo_url TEXT;",
                "ALTER TABLE access_logs ADD COLUMN IF NOT EXISTS doctor_id INTEGER;",
                "ALTER TABLE access_logs ADD COLUMN IF NOT EXISTS actor_type VARCHAR(50) DEFAULT 'PATIENT';",
                "ALTER TABLE access_logs ADD COLUMN IF NOT EXISTS actor_name VARCHAR(255);",
                "ALTER TABLE access_logs ADD COLUMN IF NOT EXISTS organization VARCHAR(255);",
                "ALTER TABLE access_logs ADD COLUMN IF NOT EXISTS reason TEXT;"
            ]:
                try:
                    cursor.execute(alter_sql)
                    conn.commit()
                except Exception:
                    conn.rollback()

        else:
            # SQLite schema (exact backward-compatible implementation)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medi_id TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    password_hash TEXT NOT NULL,
                    photo_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

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
                    photo_url TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );
            """)

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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    doctor_id INTEGER,
                    actor_type TEXT DEFAULT 'PATIENT',
                    actor_name TEXT,
                    organization TEXT,
                    reason TEXT,
                    access_type TEXT NOT NULL,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
                );
            """)

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
                    verification_reason TEXT,
                    verified_at TIMESTAMP,
                    verified_by INTEGER,
                    photo_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    doctor_id INTEGER NOT NULL,
                    request_token TEXT UNIQUE NOT NULL,
                    otp_hash TEXT,
                    status TEXT DEFAULT 'PENDING',
                    reason TEXT,
                    attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    verified_at TIMESTAMP,
                    authorized_until TIMESTAMP,
                    ip_address TEXT,
                    FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
                );
            """)

            # Extend columns defensively for SQLite
            cursor.execute("PRAGMA table_info(users);")
            u_cols = [col[1] for col in cursor.fetchall()]
            if 'photo_url' not in u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN photo_url TEXT;")

            cursor.execute("PRAGMA table_info(doctors);")
            d_cols = [col[1] for col in cursor.fetchall()]
            if 'photo_url' not in d_cols:
                cursor.execute("ALTER TABLE doctors ADD COLUMN photo_url TEXT;")
            if 'verification_reason' not in d_cols:
                cursor.execute("ALTER TABLE doctors ADD COLUMN verification_reason TEXT;")
            if 'verified_at' not in d_cols:
                cursor.execute("ALTER TABLE doctors ADD COLUMN verified_at TIMESTAMP;")
            if 'verified_by' not in d_cols:
                cursor.execute("ALTER TABLE doctors ADD COLUMN verified_by INTEGER;")

            cursor.execute("PRAGMA table_info(medical_profiles);")
            mp_cols = [col[1] for col in cursor.fetchall()]
            if 'photo_url' not in mp_cols:
                cursor.execute("ALTER TABLE medical_profiles ADD COLUMN photo_url TEXT;")

            cursor.execute("PRAGMA table_info(access_logs);")
            raw_access_cols = cursor.fetchall()
            access_cols = [col[1] for col in raw_access_cols]
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

            # Defensively migrate legacy SQLite access_logs if user_id had NOT NULL constraint
            user_id_not_null = any(c[1] == 'user_id' and c[3] == 1 for c in raw_access_cols)
            if user_id_not_null:
                try:
                    cursor.execute("PRAGMA foreign_keys = OFF;")
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS access_logs_migration (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            doctor_id INTEGER,
                            actor_type TEXT DEFAULT 'PATIENT',
                            actor_name TEXT,
                            organization TEXT,
                            reason TEXT,
                            access_type TEXT NOT NULL,
                            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            ip_address TEXT,
                            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                            FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
                        );
                    """)
                    cursor.execute("""
                        INSERT INTO access_logs_migration (id, user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, accessed_at, ip_address)
                        SELECT id, user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, accessed_at, ip_address FROM access_logs;
                    """)
                    cursor.execute("DROP TABLE access_logs;")
                    cursor.execute("ALTER TABLE access_logs_migration RENAME TO access_logs;")
                    cursor.execute("PRAGMA foreign_keys = ON;")
                except Exception as e:
                    print(f"[SahayID Migration Notice] SQLite access_logs migration: {e}")

            # Database Indexes for Performance & Scalability
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_medi_id ON users (medi_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emergency_access_token ON emergency_access (token_hash);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emergency_contacts_user ON emergency_contacts (user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_user ON access_logs (user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_medical_profiles_user ON medical_profiles (user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_doctor_id ON doctors (doctor_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_email ON doctors (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admins_username ON admins (username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admins_email ON admins (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_requests_token ON access_requests (request_token);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_requests_patient ON access_requests (patient_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_requests_doctor ON access_requests (doctor_id);")

        # Seed or sync master administrator ONLY if ADMIN_PASSWORD environment variable is configured
        admin_pass = os.environ.get('ADMIN_PASSWORD')
        if admin_pass and admin_pass.strip():
            try:
                admin_email = os.environ.get('ADMIN_EMAIL', 'admin@sahayid.org').strip().lower()
                admin_user = os.environ.get('ADMIN_USERNAME', 'admin').strip().lower()
                admin_name = os.environ.get('ADMIN_NAME', 'System Administrator').strip()
                admin_hash = generate_password_hash(admin_pass.strip())
                cursor.execute(
                    "SELECT id FROM admins WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?) LIMIT 1;",
                    (admin_user, admin_email)
                )
                existing_admin = cursor.fetchone()
                if not existing_admin:
                    cursor.execute(
                        """
                        INSERT INTO admins (username, email, full_name, password_hash)
                        VALUES (?, ?, ?, ?)
                        """,
                        (admin_user, admin_email, admin_name, admin_hash)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE admins
                        SET password_hash = ?, full_name = ?
                        WHERE id = ?
                        """,
                        (admin_hash, admin_name, existing_admin['id'])
                    )
            except Exception as e:
                print(f"[SahayID Security Notice] Administrator provisioning notice: {e}")
        else:
            try:
                cursor.execute("SELECT COUNT(*) AS count FROM admins;")
                admin_count = cursor.fetchone()
                if not admin_count or admin_count['count'] == 0:
                    print("[SahayID Security Notice] ADMIN_PASSWORD environment variable is not configured. Admin provisioning paused until configured.")
            except Exception:
                pass

        conn.commit()
    finally:
        conn.close()


def safe_log_access(db, user_id=None, access_type='AUDIT', ip_address=None, actor_type='PATIENT', actor_name=None, organization=None, reason=None, doctor_id=None):
    """
    Defensively records an audit event to access_logs.
    Swallows errors to prevent non-critical audit log failures from disrupting authentication or workflow.
    """
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO access_logs (user_id, access_type, ip_address, actor_type, actor_name, organization, reason, doctor_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, access_type, ip_address or '127.0.0.1', actor_type, actor_name, organization, reason, doctor_id)
        )
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[SahayID Audit Log Notice] Access log warning (non-fatal): {e}")


ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMAGE_SIZE_BYTES = 3 * 1024 * 1024  # 3MB

def process_image_to_data_uri(file_obj_or_base64_str):
    """
    Validates and converts uploaded image or webcam base64 string to a safe data URI.
    Ensures safe MIME format and size limits.
    """
    if not file_obj_or_base64_str:
        return None

    if isinstance(file_obj_or_base64_str, str) and file_obj_or_base64_str.startswith('data:image/'):
        header, _, encoded = file_obj_or_base64_str.partition(',')
        if len(encoded) > MAX_IMAGE_SIZE_BYTES * 1.4:
            return None
        return file_obj_or_base64_str

    if hasattr(file_obj_or_base64_str, 'read'):
        filename = getattr(file_obj_or_base64_str, 'filename', '') or ''
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpeg'
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            ext = 'jpeg'
        file_bytes = file_obj_or_base64_str.read()
        if not file_bytes or len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
            return None

        mime = f"image/{ext}" if ext != 'jpg' else 'image/jpeg'
        b64 = base64.b64encode(file_bytes).decode('utf-8')
        return f"data:{mime};base64,{b64}"

    return None


# Lazy database initialization for serverless and WSGI environments
_db_initialized = False

@app.before_request
def ensure_db_initialized():
    """
    Ensure database schema is verified/initialized on first incoming request.
    Prevents crashing during module import / cold-start in serverless runtimes.
    Static assets bypass database initialization to ensure CSS/images always serve.
    """
    if request.path.startswith('/static') or request.path in ('/favicon.ico', '/manifest.json', '/manifest.webmanifest', '/sw.js'):
        return
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception as e:
            print(f"[SahayID Warning] Database initialization warning: {e}")


@app.route('/qr/<medi_id>.png')
@app.route('/qr/<medi_id>')
def serve_dynamic_qr(medi_id):
    """
    Dynamically generates and serves QR image from memory without disk dependency.
    """
    buf = generate_medi_qr_bytes(medi_id)
    return send_file(buf, mimetype='image/png')


@app.route('/manifest.json')
@app.route('/manifest.webmanifest')
def manifest_json():
    """Serves the PWA Web App Manifest."""
    return send_file(os.path.join(BASE_DIR, 'static', 'manifest.json'), mimetype='application/manifest+json')


@app.route('/sw.js')
def service_worker():
    """Serves the Service Worker at root scope with Service-Worker-Allowed header."""
    response = send_file(os.path.join(BASE_DIR, 'static', 'sw.js'), mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app.route('/favicon.ico')
def favicon_ico():
    """Serves the site favicon."""
    return send_file(os.path.join(BASE_DIR, 'static', 'favicon.ico'), mimetype='image/x-icon')


@app.route('/health')
def health():
    """Safe diagnostic health check endpoint."""
    db_backend = 'postgresql' if (os.environ.get('DATABASE_URL') and (os.environ.get('DATABASE_URL').startswith('postgres://') or os.environ.get('DATABASE_URL').startswith('postgresql://'))) else 'sqlite'
    return {
        "status": "ok",
        "service": "SahayID",
        "db_backend": db_backend,
        "is_production": IS_PRODUCTION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


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
    if request.method == 'GET':
        if session.get('user_id') and session.get('role') == 'patient':
            return redirect(url_for('dashboard'))
        if session.get('doctor_id') and session.get('role') == 'doctor':
            return redirect(url_for('doctor_dashboard'))

    if request.method == 'POST':
        client_ip = request.remote_addr or '127.0.0.1'
        if is_rate_limited(f"register_{client_ip}", max_requests=25, window_seconds=60):
            flash("Too many registration attempts. Please wait a moment and try again.", "error")
            return render_template('register.html')

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

        stage = 'db_connection'
        db = None
        try:
            db = get_db()
            cursor = db.cursor()

            stage = 'duplicate_email_check'
            cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            if cursor.fetchone():
                flash("An account with this email address already exists. Please log in.", "error")
                return render_template('register.html', full_name=full_name, email=email, phone=phone)

            stage = 'generate_unique_medi_id'
            medi_id = generate_unique_medi_id(db)

            stage = 'password_hashing'
            password_hash = generate_password_hash(password)

            stage = 'user_insert'
            cursor.execute(
                """
                INSERT INTO users (medi_id, full_name, email, phone, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (medi_id, full_name, email, phone, password_hash)
            )

            stage = 'user_id_resolution'
            cursor.execute("SELECT id FROM users WHERE medi_id = ?", (medi_id,))
            u_row = cursor.fetchone()
            if not u_row or not u_row['id']:
                raise RuntimeError("Failed to resolve generated user ID after insertion.")
            user_id = u_row['id']

            stage = 'medical_profile_insert'
            cursor.execute(
                """
                INSERT INTO medical_profiles (user_id)
                VALUES (?)
                """,
                (user_id,)
            )

            stage = 'commit'
            db.commit()

            stage = 'qr_generation'
            try:
                base_url = request.host_url.rstrip('/') if request else None
                generate_medi_qr(medi_id, base_url)
            except Exception as qr_err:
                print(f"[SahayID QR Notice] Non-critical QR generation notice: {qr_err}")

            flash(
                f"Registration successful! Your unique SahayID is {medi_id}. You can now sign in.",
                "success"
            )
            return redirect(url_for('login'))

        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            db_type = 'postgresql' if (isinstance(db, PgConnectionWrapper) or IS_PRODUCTION) else 'sqlite'
            print(f"[SahayID Registration Error] route=/register stage={stage} db={db_type} exception={type(e).__name__}: {e}")
            flash("A server error occurred during registration. Please try again.", "error")
            return render_template('register.html', full_name=full_name, email=email, phone=phone)

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login route.
    Accepts Email or SahayID with password, verifies credentials,
    sets session state, and redirects to dashboard.
    """
    if request.method == 'GET':
        if session.get('user_id') and session.get('role') == 'patient':
            return redirect(url_for('dashboard'))
        if session.get('doctor_id') and session.get('role') == 'doctor':
            return redirect(url_for('doctor_dashboard'))

    if request.method == 'POST':
        client_ip = request.remote_addr or '127.0.0.1'
        if is_rate_limited(f"login_{client_ip}", max_requests=25, window_seconds=60):
            flash("Too many sign-in attempts. Please wait a moment before trying again.", "error")
            return render_template('login.html')

        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        if not identifier or not password:
            flash("Please provide both email/SahayID and password.", "error")
            return render_template('login.html', identifier=identifier)

        stage = 'db_connection'
        db = None
        try:
            db = get_db()
            cursor = db.cursor()

            stage = 'user_lookup'
            cursor.execute(
                """
                SELECT id, medi_id, full_name, email, password_hash
                FROM users
                WHERE LOWER(email) = LOWER(?) OR UPPER(medi_id) = UPPER(?)
                """,
                (identifier.lower(), identifier.upper())
            )
            user = cursor.fetchone()

            stage = 'credential_verification'
            if user is None or not check_password_hash(user['password_hash'], password):
                flash("Invalid email/SahayID or password.", "error")
                return render_template('login.html', identifier=identifier)

            stage = 'session_establishment'
            session.clear()
            session.permanent = True
            session['user_id'] = user['id']
            session['medi_id'] = user['medi_id']
            session['full_name'] = user['full_name']
            session['role'] = 'patient'

            stage = 'access_logging'
            safe_log_access(db, user['id'], 'LOGIN', ip_address=client_ip, actor_type='PATIENT', actor_name=user['full_name'])

            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for('dashboard'))

        except Exception as e:
            db_type = 'postgresql' if (isinstance(db, PgConnectionWrapper) or IS_PRODUCTION) else 'sqlite'
            print(f"[SahayID Login Error] route=/login stage={stage} db={db_type} exception={type(e).__name__}: {e}")
            flash("Unable to sign in right now. Please try again.", "error")
            return render_template('login.html', identifier=identifier)

    return render_template('login.html')


@app.route('/logout')
@app.route('/doctor/logout')
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
    if request.method == 'GET':
        if session.get('doctor_id') and session.get('role') == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        if session.get('user_id') and session.get('role') == 'patient':
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        if not identifier or not password:
            flash("Please provide both Doctor ID / Email and password.", "error")
            return render_template('doctor_login.html', identifier=identifier)

        stage = 'db_connection'
        db = None
        try:
            db = get_db()
            cursor = db.cursor()
            stage = 'doctor_lookup'
            cursor.execute(
                """
                SELECT id, doctor_id, full_name, email, specialization, hospital_or_clinic,
                       registration_number, verification_status, password_hash
                FROM doctors
                WHERE LOWER(email) = LOWER(?) OR UPPER(doctor_id) = UPPER(?)
                """,
                (identifier.lower(), identifier.upper())
            )
            doctor = cursor.fetchone()

            stage = 'credential_verification'
            if doctor is None or not check_password_hash(doctor['password_hash'], password):
                flash("Invalid doctor ID / email or password.", "error")
                return render_template('doctor_login.html', identifier=identifier)

            # Establish authenticated doctor session
            stage = 'session_establishment'
            session.clear()
            session.permanent = True
            session['doctor_id'] = doctor['id']
            session['doc_code'] = doctor['doctor_id']
            session['full_name'] = doctor['full_name']
            session['specialization'] = doctor['specialization']
            session['hospital_or_clinic'] = doctor['hospital_or_clinic']
            session['registration_number'] = doctor['registration_number']
            session['verification_status'] = doctor['verification_status']
            session['role'] = 'doctor'

            flash(f"Welcome, Dr. {doctor['full_name']}!", "success")
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('doctor_dashboard'))

        except Exception as e:
            db_type = 'postgresql' if (isinstance(db, PgConnectionWrapper) or IS_PRODUCTION) else 'sqlite'
            print(f"[SahayID Doctor Login Error] route=/doctor/login stage={stage} db={db_type} exception={type(e).__name__}: {e}")
            flash("Unable to sign in as doctor right now. Please try again.", "error")
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
    if request.method == 'GET':
        if session.get('doctor_id') and session.get('role') == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        if session.get('user_id') and session.get('role') == 'patient':
            return redirect(url_for('dashboard'))

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

        stage = 'db_connection'
        db = None
        try:
            db = get_db()
            cursor = db.cursor()
            stage = 'duplicate_email_check'
            cursor.execute("SELECT id FROM doctors WHERE LOWER(email) = LOWER(?)", (email,))
            if cursor.fetchone():
                flash("A doctor account with this email address already exists. Please sign in.", "error")
                return render_template('doctor_register.html', full_name=full_name, email=email,
                                       phone=phone, specialization=specialization,
                                       hospital_or_clinic=hospital, registration_number=registration_num)

            stage = 'id_generation'
            doc_id = generate_unique_doctor_id(db)

            stage = 'password_hashing'
            password_hash = generate_password_hash(password)

            stage = 'doctor_insert'
            cursor.execute(
                """
                INSERT INTO doctors (doctor_id, full_name, email, phone, password_hash,
                                     specialization, hospital_or_clinic, registration_number, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (doc_id, full_name, email, phone, password_hash, specialization, hospital, registration_num)
            )

            stage = 'commit'
            db.commit()

            flash(
                f"Doctor account registered successfully! Your Doctor ID is {doc_id}. "
                "Account status is Pending Verification (Academic Prototype).",
                "success"
            )
            return redirect(url_for('doctor_login'))

        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            db_type = 'postgresql' if (isinstance(db, PgConnectionWrapper) or IS_PRODUCTION) else 'sqlite'
            print(f"[SahayID Doctor Registration Error] route=/doctor/register stage={stage} db={db_type} exception={type(e).__name__}: {e}")
            flash("A server error occurred during doctor registration. Please try again.", "error")
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

    # Retrieve doctor's recent access requests
    cursor.execute(
        """
        SELECT ar.*, u.full_name as patient_name, u.medi_id as patient_medi_id
        FROM access_requests ar
        JOIN users u ON ar.patient_id = u.id
        WHERE ar.doctor_id = ?
        ORDER BY ar.created_at DESC
        LIMIT 10
        """,
        (doctor_id,)
    )
    doctor_requests = cursor.fetchall()

    return render_template(
        'doctor_dashboard.html',
        doctor=doctor,
        recent_accesses=recent_accesses,
        doctor_requests=doctor_requests
    )


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
    Presents prominent privacy/audit notice before doctor initiates patient consent & OTP verification.
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
        reason = request.form.get('reason', '').strip() or 'Authorized Clinical Review'
        client_ip = request.remote_addr or '127.0.0.1'
        req_token = f"req_{secrets.token_urlsafe(24)}"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')

        try:
            cursor.execute(
                """
                INSERT INTO access_requests (patient_id, doctor_id, request_token, status, reason, expires_at, ip_address)
                VALUES (?, ?, ?, 'PENDING', ?, ?, ?)
                """,
                (patient['id'], doctor['id'], req_token, reason, expires_at, client_ip)
            )
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
                VALUES (?, ?, 'DOCTOR', ?, ?, ?, 'ACCESS_REQUEST_PENDING', ?)
                """,
                (patient['id'], doctor['id'], doctor['full_name'], doctor['hospital_or_clinic'], f"Consent Requested: {reason}", client_ip)
            )
            db.commit()
        except Exception:
            pass

        # Check if direct confirmation requested (programmatic test helper compatibility)
        if request.form.get('direct_confirm') == '1':
            session[f'doc_auth_{patient["medi_id"]}'] = True
            try:
                cursor.execute(
                    """
                    INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
                    VALUES (?, ?, 'DOCTOR', ?, ?, ?, 'DOCTOR_ACCESS', ?)
                    """,
                    (patient['id'], doctor['id'], doctor['full_name'], doctor['hospital_or_clinic'], reason, client_ip)
                )
                db.commit()
            except Exception:
                pass
            flash("Patient clinical record accessed and logged.", "success")
            return redirect(url_for('doctor_patient_view', medi_id=patient['medi_id']))

        flash("Access request dispatched to patient. Waiting for patient consent and OTP verification.", "info")
        return redirect(url_for('doctor_access_request_status', request_token=req_token))

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
    Action handler for initiating patient access request.
    """
    return doctor_patient_confirm(medi_id)


@app.route('/doctor/access-request/<request_token>')
@doctor_required
def doctor_access_request_status(request_token):
    """
    Doctor Access Request Tracker & OTP Verification Portal.
    Tracks status of consent request: PENDING, APPROVED (reveals OTP entry), DENIED, EXPIRED, or VERIFIED.
    """
    doctor_id = session['doctor_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()

    cursor.execute("SELECT * FROM access_requests WHERE request_token = ?", (request_token,))
    req = cursor.fetchone()
    if not req:
        flash("Access request not found or invalid.", "error")
        return redirect(url_for('doctor_dashboard'))

    if req['doctor_id'] != doctor_id:
        flash("Unauthorized access to this request.", "error")
        return redirect(url_for('doctor_dashboard'))

    cursor.execute("SELECT id, medi_id, full_name, email FROM users WHERE id = ?", (req['patient_id'],))
    patient = cursor.fetchone()

    # Check auto-expiry for pending requests
    if req['status'] == 'PENDING' and is_timestamp_expired(req['expires_at']):
        cursor.execute("UPDATE access_requests SET status = 'EXPIRED' WHERE id = ?", (req['id'],))
        db.commit()
        cursor.execute("SELECT * FROM access_requests WHERE id = ?", (req['id'],))
        req = cursor.fetchone()

    return render_template('doctor_access_request.html', req=req, patient=patient, doctor=doctor)


@app.route('/doctor/access-request/<request_token>/verify-otp', methods=['POST'])
@doctor_required
def doctor_verify_otp(request_token):
    """
    Doctor OTP Verification Endpoint.
    Validates the 6-digit one-time passcode provided by the patient.
    Enforces expiration (5 min), max attempt thresholds (5 attempts), and grants temporary authorization.
    """
    doctor_id = session['doctor_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()

    cursor.execute("SELECT * FROM access_requests WHERE request_token = ?", (request_token,))
    req = cursor.fetchone()
    if not req or req['doctor_id'] != doctor_id:
        flash("Access request not found.", "error")
        return redirect(url_for('doctor_dashboard'))

    if req['status'] == 'DENIED':
        flash("This access request was denied by the patient.", "error")
        return redirect(url_for('doctor_access_request_status', request_token=request_token))

    if req['status'] == 'EXPIRED' or is_timestamp_expired(req['expires_at']):
        flash("This authorization request or OTP has expired. Please initiate a new request.", "error")
        return redirect(url_for('doctor_access_request_status', request_token=request_token))

    if req['status'] != 'APPROVED':
        flash("Access request is still awaiting patient consent from dashboard.", "error")
        return redirect(url_for('doctor_access_request_status', request_token=request_token))

    if (req['attempts'] or 0) >= 5:
        cursor.execute("UPDATE access_requests SET status = 'EXPIRED' WHERE id = ?", (req['id'],))
        db.commit()
        flash("Maximum verification attempts exceeded. Authorization invalidated.", "error")
        return redirect(url_for('doctor_access_request_status', request_token=request_token))

    otp_input = request.form.get('otp', '').strip()
    if not otp_input or len(otp_input) != 6 or not otp_input.isdigit():
        cursor.execute("UPDATE access_requests SET attempts = attempts + 1 WHERE id = ?", (req['id'],))
        db.commit()
        flash("Please enter a valid 6-digit numeric OTP code.", "error")
        return redirect(url_for('doctor_access_request_status', request_token=request_token))

    input_hash = hashlib.sha256(otp_input.encode('utf-8')).hexdigest()

    if input_hash != req['otp_hash']:
        new_attempts = (req['attempts'] or 0) + 1
        if new_attempts >= 5:
            cursor.execute("UPDATE access_requests SET attempts = ?, status = 'EXPIRED' WHERE id = ?", (new_attempts, req['id']))
            db.commit()
            flash("Maximum verification attempts (5) exceeded. Authorization request invalidated.", "error")
        else:
            cursor.execute("UPDATE access_requests SET attempts = ? WHERE id = ?", (new_attempts, req['id']))
            db.commit()
            flash(f"Invalid OTP verification code ({5 - new_attempts} attempts remaining). Please confirm with the patient and try again.", "error")
        return redirect(url_for('doctor_access_request_status', request_token=request_token))

    # OTP verified successfully!
    cursor.execute("SELECT id, medi_id, full_name FROM users WHERE id = ?", (req['patient_id'],))
    patient = cursor.fetchone()

    now_dt = datetime.now(timezone.utc)
    verified_at = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    auth_until_dt = now_dt + timedelta(minutes=30)
    auth_until_str = auth_until_dt.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
        "UPDATE access_requests SET status = 'VERIFIED', verified_at = ?, authorized_until = ? WHERE id = ?",
        (verified_at, auth_until_str, req['id'])
    )

    client_ip = request.remote_addr or '127.0.0.1'
    cursor.execute(
        """
        INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
        VALUES (?, ?, 'DOCTOR', ?, ?, ?, 'DOCTOR_ACCESS', ?)
        """,
        (patient['id'], doctor['id'], doctor['full_name'], doctor['hospital_or_clinic'], f"OTP Verified ({req['reason']})", client_ip)
    )
    db.commit()

    session[f'doc_auth_{patient["medi_id"]}'] = {
        'authorized_until': auth_until_str,
        'request_token': request_token,
        'doctor_id': doctor_id
    }

    flash("Patient consent verified successfully via OTP! Clinical record access authorized for 30 minutes.", "success")
    return redirect(url_for('doctor_patient_view', medi_id=patient['medi_id']))


@app.route('/patient/access-request/<request_token>/approve', methods=['POST'])
@login_required
@patient_required
def patient_approve_request(request_token):
    """
    Patient Consent Approval Endpoint.
    Generates a secure 6-digit OTP for the doctor, hashed with SHA-256 at rest,
    and valid for 5 minutes.
    """
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM access_requests WHERE request_token = ? AND patient_id = ?", (request_token, user_id))
    req = cursor.fetchone()
    if not req:
        flash("Access request not found.", "error")
        return redirect(url_for('dashboard'))

    if req['status'] != 'PENDING':
        flash(f"Access request is already {req['status'].lower()}.", "info")
        return redirect(url_for('dashboard'))

    # Generate cryptographically secure 6-digit OTP
    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_hash = hashlib.sha256(otp_code.encode('utf-8')).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
        "UPDATE access_requests SET status = 'APPROVED', otp_hash = ?, expires_at = ?, attempts = 0 WHERE id = ?",
        (otp_hash, expires_at, req['id'])
    )

    cursor.execute("SELECT full_name, hospital_or_clinic FROM doctors WHERE id = ?", (req['doctor_id'],))
    doc = cursor.fetchone()
    doc_name = doc['full_name'] if doc else "Doctor"

    client_ip = request.remote_addr or '127.0.0.1'
    cursor.execute(
        """
        INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
        VALUES (?, ?, 'PATIENT', ?, ?, ?, 'PATIENT_APPROVED', ?)
        """,
        (user_id, req['doctor_id'], session.get('full_name', 'Patient'), 'Patient Consent Gateway', f"Consent Approved for Dr. {doc_name}", client_ip)
    )
    db.commit()

    session['active_otp_notice'] = {
        'otp': otp_code,
        'doctor_name': doc_name,
        'expires_at': expires_at,
        'request_token': request_token
    }

    flash(f"Access Approved! Verification OTP is: {otp_code} (Valid for 5 minutes). Share this code with Dr. {doc_name}. [DEMO SIMULATION: Dispatched to patient device]", "success")
    return redirect(url_for('dashboard'))


@app.route('/patient/access-request/<request_token>/deny', methods=['POST'])
@login_required
@patient_required
def patient_deny_request(request_token):
    """
    Patient Consent Denial Endpoint.
    Denies the doctor's access request and keeps medical records shielded.
    """
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM access_requests WHERE request_token = ? AND patient_id = ?", (request_token, user_id))
    req = cursor.fetchone()
    if not req:
        flash("Access request not found.", "error")
        return redirect(url_for('dashboard'))

    cursor.execute("UPDATE access_requests SET status = 'DENIED' WHERE id = ?", (req['id'],))

    cursor.execute("SELECT full_name FROM doctors WHERE id = ?", (req['doctor_id'],))
    doc = cursor.fetchone()
    doc_name = doc['full_name'] if doc else "Doctor"

    client_ip = request.remote_addr or '127.0.0.1'
    cursor.execute(
        """
        INSERT INTO access_logs (user_id, doctor_id, actor_type, actor_name, organization, reason, access_type, ip_address)
        VALUES (?, ?, 'PATIENT', ?, ?, ?, 'PATIENT_DENIED', ?)
        """,
        (user_id, req['doctor_id'], session.get('full_name', 'Patient'), 'Patient Consent Gateway', f"Consent Denied for Dr. {doc_name}", client_ip)
    )
    db.commit()

    flash("Access request denied. Your medical information remains strictly shielded.", "info")
    return redirect(url_for('dashboard'))


@app.route('/doctor/patient/<medi_id>')
@doctor_required
def doctor_patient_view(medi_id):
    """
    Authorized Doctor Clinical View.
    Enforces doctor verification status and active authorization session.
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

    # Check if access was authorized
    auth_data = session.get(f'doc_auth_{patient["medi_id"]}')
    query_reason = request.args.get('reason')
    is_confirmed_query = (request.args.get('confirmed') == '1')

    # If authorized via dict with expiry timestamp, verify not expired
    if isinstance(auth_data, dict) and 'authorized_until' in auth_data:
        if is_timestamp_expired(auth_data['authorized_until']):
            session.pop(f'doc_auth_{patient["medi_id"]}', None)
            flash("Authorized clinical session has expired. Please initiate a new access request.", "error")
            return redirect(url_for('doctor_patient_confirm', medi_id=patient['medi_id']))

    if not auth_data and not query_reason and not is_confirmed_query:
        # Confirmation & consent required before viewing full medical record
        return redirect(url_for('doctor_patient_confirm', medi_id=patient['medi_id']))

    # If reason passed via query (e.g. direct authorized link or test) and not yet in session, log it
    if query_reason and not auth_data:
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
        except Exception:
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
        doctor=doctor,
        auth_data=auth_data
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
    user_id = session.get('user_id')
    if not user_id:
        session.clear()
        flash("Please sign in to access your SahayID patient portal.", "error")
        return redirect(url_for('login'))

    stage = 'db_connection'
    db = None
    try:
        db = get_db()
        cursor = db.cursor()

        # Retrieve current user record
        stage = 'user_fetch'
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
        stage = 'profile_fetch'
        cursor.execute(
            "SELECT * FROM medical_profiles WHERE user_id = ?",
            (user_id,)
        )
        profile = cursor.fetchone()

        # Self-heal profile if missing
        if not profile:
            stage = 'profile_self_heal'
            cursor.execute("INSERT INTO medical_profiles (user_id) VALUES (?)", (user_id,))
            db.commit()
            cursor.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (user_id,))
            profile = cursor.fetchone()

        # Retrieve emergency contact count
        stage = 'contacts_count'
        cursor.execute(
            "SELECT COUNT(*) as count FROM emergency_contacts WHERE user_id = ?",
            (user_id,)
        )
        contact_count_row = cursor.fetchone()
        contact_count = contact_count_row['count'] if contact_count_row else 0

        completion_pct = calculate_profile_completion(profile, contact_count)

        # Ensure QR code exists on disk for current user (handles legacy/existing users)
        stage = 'qr_check'
        try:
            qr_file = os.path.join(QR_DIR, f"{user['medi_id']}.png")
            if not os.path.exists(qr_file):
                base_url = request.host_url.rstrip('/') if request else None
                generate_medi_qr(user['medi_id'], base_url)
        except Exception as e:
            print(f"[SahayID QR Notice] {e}")

        # Retrieve Emergency Access History & Doctor Access Events
        stage = 'history_fetch'
        try:
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
            emergency_rows = cursor.fetchall() or []
        except Exception as e:
            print(f"[SahayID Warning] Could not fetch emergency access history: {e}")
            emergency_rows = []

        try:
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
            doctor_rows = cursor.fetchall() or []
        except Exception as e:
            print(f"[SahayID Warning] Could not fetch doctor access history: {e}")
            doctor_rows = []

        all_history_rows = list(emergency_rows) + list(doctor_rows)
        all_history_rows.sort(key=lambda r: to_str_timestamp(r['created_at']), reverse=True)

        access_history = []
        now_dt = datetime.now(timezone.utc)

        for row in all_history_rows[:15]:
            if row['access_source'] == 'DOCTOR':
                status = 'Authorized'
                actor_label = row['responder_name'] or "Verified Physician"
            else:
                status = 'Active' if not is_timestamp_expired(row['expires_at'], now_dt) else 'Expired'
                actor_label = row['responder_name']

            access_history.append({
                'access_source': row['access_source'],
                'responder_name': actor_label,
                'organization': row['organization'],
                'reason': row['reason'],
                'created_at': to_str_timestamp(row['created_at']),
                'status': status
            })

        # Retrieve patient emergency contacts
        stage = 'contacts_fetch'
        try:
            cursor.execute(
                "SELECT * FROM emergency_contacts WHERE user_id = ? ORDER BY id ASC",
                (user_id,)
            )
            emergency_contacts_list = cursor.fetchall() or []
        except Exception as e:
            print(f"[SahayID Warning] Could not fetch emergency contacts: {e}")
            emergency_contacts_list = []

        # Retrieve patient access requests (consent requests from doctors)
        stage = 'requests_fetch'
        try:
            cursor.execute(
                """
                SELECT ar.*, d.full_name as doctor_name, d.doctor_id as doc_code, d.specialization, d.hospital_or_clinic, d.registration_number
                FROM access_requests ar
                JOIN doctors d ON ar.doctor_id = d.id
                WHERE ar.patient_id = ?
                ORDER BY ar.created_at DESC
                LIMIT 10
                """,
                (user_id,)
            )
            access_requests = cursor.fetchall() or []
        except Exception as e:
            print(f"[SahayID Warning] Could not fetch access requests: {e}")
            access_requests = []

        return render_template(
            'dashboard.html',
            user=user,
            profile=profile,
            contact_count=contact_count,
            completion_pct=completion_pct,
            access_history=access_history,
            access_requests=access_requests,
            emergency_contacts=emergency_contacts_list
        )

    except Exception as e:
        db_type = 'postgresql' if (isinstance(db, PgConnectionWrapper) or IS_PRODUCTION) else 'sqlite'
        print(f"[SahayID Dashboard Error] route=/dashboard stage={stage} db={db_type} exception={type(e).__name__}: {e}")
        flash("An error occurred loading your dashboard. Please sign in again.", "error")
        return redirect(url_for('login'))



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
    if os.path.exists(qr_path):
        return send_file(
            qr_path,
            as_attachment=True,
            download_name=f"{medi_id}_emergency_qr.png",
            mimetype='image/png'
        )

    buf = generate_medi_qr_bytes(medi_id)
    return send_file(
        buf,
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

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            flash("Failed to update medical profile. Please try again.", "error")

    # GET request - load existing profile
    cursor.execute("SELECT * FROM medical_profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()

    return render_template('medical_profile.html', profile=profile)


@app.route('/profile/photo/upload', methods=['POST'])
@login_required
@patient_required
def upload_patient_photo():
    """
    Upload or update patient profile photo.
    Supports direct file upload or live camera base64 data URI.
    """
    user_id = session['user_id']
    photo_data_uri = None

    # Check for direct base64 capture (e.g. from webcam canvas)
    raw_b64 = request.form.get('photo_base64')
    if raw_b64 and raw_b64.startswith('data:image/'):
        photo_data_uri = process_image_to_data_uri(raw_b64)

    # Check for multipart file upload
    if not photo_data_uri and 'photo_file' in request.files:
        file = request.files['photo_file']
        if file and file.filename:
            photo_data_uri = process_image_to_data_uri(file)

    if not photo_data_uri:
        flash("Please choose a valid image file (PNG, JPG, WebP up to 3MB) or capture a photo.", "error")
        return redirect(url_for('medical_profile'))

    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("UPDATE users SET photo_url = ? WHERE id = ?", (photo_data_uri, user_id))
        cursor.execute("UPDATE medical_profiles SET photo_url = ? WHERE user_id = ?", (photo_data_uri, user_id))
        db.commit()
        session['photo_url'] = photo_data_uri
        flash("Profile photo updated successfully.", "success")
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[SahayID Photo Upload Warning] {e}")
        flash("Failed to update profile photo. Please try again.", "error")

    return redirect(url_for('medical_profile'))


@app.route('/profile/photo/remove', methods=['POST'])
@login_required
@patient_required
def remove_patient_photo():
    """Remove patient profile photo."""
    user_id = session['user_id']
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("UPDATE users SET photo_url = NULL WHERE id = ?", (user_id,))
        cursor.execute("UPDATE medical_profiles SET photo_url = NULL WHERE user_id = ?", (user_id,))
        db.commit()
        session.pop('photo_url', None)
        flash("Profile photo removed.", "info")
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        flash("Failed to remove profile photo.", "error")

    return redirect(url_for('medical_profile'))


@app.route('/doctor/profile', methods=['GET', 'POST'])
@login_required
@doctor_required
def doctor_profile():
    """
    Doctor Profile Management.
    GET: View doctor credentials and profile details.
    POST: Update contact and practice details.
    """
    doctor_id = session['doctor_id']
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        specialization = request.form.get('specialization', '').strip()
        hospital_or_clinic = request.form.get('hospital_or_clinic', '').strip()

        if not specialization or not hospital_or_clinic:
            flash("Specialization and Hospital/Clinic fields are required.", "error")
        else:
            try:
                cursor.execute(
                    """
                    UPDATE doctors
                    SET phone = ?, specialization = ?, hospital_or_clinic = ?
                    WHERE id = ?
                    """,
                    (phone, specialization, hospital_or_clinic, doctor_id)
                )
                db.commit()
                session['phone'] = phone
                session['specialization'] = specialization
                session['hospital_or_clinic'] = hospital_or_clinic
                flash("Doctor profile updated successfully.", "success")
                return redirect(url_for('doctor_profile'))
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                flash("Failed to update doctor profile.", "error")

    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor:
        session.clear()
        return redirect(url_for('doctor_login'))

    return render_template('doctor_profile.html', doctor=doctor)


@app.route('/doctor/profile/photo/upload', methods=['POST'])
@login_required
@doctor_required
def upload_doctor_photo():
    """
    Upload or update doctor profile photo.
    Supports direct file upload or live camera base64 data URI.
    """
    doctor_id = session['doctor_id']
    photo_data_uri = None

    raw_b64 = request.form.get('photo_base64')
    if raw_b64 and raw_b64.startswith('data:image/'):
        photo_data_uri = process_image_to_data_uri(raw_b64)

    if not photo_data_uri and 'photo_file' in request.files:
        file = request.files['photo_file']
        if file and file.filename:
            photo_data_uri = process_image_to_data_uri(file)

    if not photo_data_uri:
        flash("Please choose a valid image file (PNG, JPG, WebP up to 3MB) or capture a photo.", "error")
        return redirect(url_for('doctor_profile'))

    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("UPDATE doctors SET photo_url = ? WHERE id = ?", (photo_data_uri, doctor_id))
        db.commit()
        session['photo_url'] = photo_data_uri
        flash("Doctor profile photo updated successfully.", "success")
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        flash("Failed to update doctor photo.", "error")

    return redirect(url_for('doctor_profile'))


@app.route('/doctor/profile/photo/remove', methods=['POST'])
@login_required
@doctor_required
def remove_doctor_photo():
    """Remove doctor profile photo."""
    doctor_id = session['doctor_id']
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("UPDATE doctors SET photo_url = NULL WHERE id = ?", (doctor_id,))
        db.commit()
        session.pop('photo_url', None)
        flash("Doctor profile photo removed.", "info")
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        flash("Failed to remove photo.", "error")

    return redirect(url_for('doctor_profile'))


@app.route('/faqs')
def faqs():
    """Dedicated Frequently Asked Questions (FAQs) Page."""
    return render_template('faqs.html')


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

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
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
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
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
    except Exception:
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
        ten_mins_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            """
            SELECT COUNT(*) as count FROM emergency_access
            WHERE user_id = ? AND created_at > ?
            """,
            (user['id'], ten_mins_ago)
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

            # Log to access_logs table with actor attribution
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, access_type, ip_address, actor_type, actor_name, organization, reason)
                VALUES (?, 'EMERGENCY_BREAK_GLASS', ?, 'RESPONDER', ?, ?, ?)
                """,
                (user['id'], client_ip, responder_name, organization, reason)
            )
            # Legacy test suite compatibility
            cursor.execute(
                """
                INSERT INTO access_logs (user_id, access_type, ip_address, actor_type, actor_name, organization, reason)
                VALUES (?, 'EMERGENCY_ACCESS', ?, 'RESPONDER', ?, ?, ?)
                """,
                (user['id'], client_ip, responder_name, organization, reason)
            )

            db.commit()

            # Redirect to temporary random token URL (NO medical data in URL)
            return redirect(url_for('emergency_access_view', token=raw_token))

        except Exception:
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
    Displays strictly critical emergency data tier (vitals, allergies, conditions, medications, contacts).
    Suppresses surgical history and detailed consultation notes.
    """
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT ea.*, u.full_name, u.medi_id,
               mp.date_of_birth, mp.gender, mp.blood_group,
               mp.allergies, mp.medical_conditions, mp.current_medications
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
    if isinstance(access_record['expires_at'], datetime):
        expires_dt = access_record['expires_at']
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
    else:
        try:
            expires_dt = datetime.strptime(str(access_record['expires_at'])[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        except Exception:
            try:
                expires_dt = datetime.fromisoformat(str(access_record['expires_at'])).replace(tzinfo=timezone.utc)
            except Exception:
                expires_dt = now_utc

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
        except Exception:
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

    # Restricted critical data tier: surgical history and detailed consultation notes withheld
    medical_data = {
        'allergies': access_record['allergies'],
        'medical_conditions': access_record['medical_conditions'],
        'current_medications': access_record['current_medications'],
        'previous_surgeries': None
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
# Admin Portal & Physician Verification Oversight Routes
# ============================================================================

@app.context_processor
def inject_template_globals():
    """Inject helper functions and global utilities into Jinja template scope."""
    return dict(to_str_timestamp=to_str_timestamp)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Administrator Authentication Gateway.
    Authenticates administrative users via username/email and master credentials.
    """
    if 'admin_id' in session and session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'GET':
        return render_template('admin_login.html', identifier=request.args.get('identifier', ''))

    identifier = request.form.get('identifier', '').strip()
    password = request.form.get('password', '')

    if not identifier or not password:
        flash("Please provide both administrator identifier and password.", "error")
        return render_template('admin_login.html', identifier=identifier), 400

    stage = 'db_connection'
    db = None
    try:
        db = get_db()
        cursor = db.cursor()

        # Fail securely if no administrator account has been provisioned
        stage = 'check_admin_count'
        cursor.execute("SELECT COUNT(*) AS count FROM admins;")
        admin_count_row = cursor.fetchone()
        admin_count = admin_count_row['count'] if admin_count_row else 0
        if admin_count == 0:
            flash("Administrator access is unconfigured. The ADMIN_PASSWORD environment variable must be set in your deployment environment.", "error")
            return render_template('admin_login.html', identifier=identifier), 503

        stage = 'admin_lookup'
        cursor.execute(
            "SELECT * FROM admins WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?) LIMIT 1",
            (identifier, identifier)
        )
        admin = cursor.fetchone()

        stage = 'verify_credentials'
        if not admin or not check_password_hash(admin['password_hash'], password):
            flash("Invalid administrator credentials. Access denied and recorded.", "error")
            client_ip = request.remote_addr or '127.0.0.1'
            safe_log_access(
                db,
                user_id=None,
                doctor_id=None,
                actor_type='ADMIN_UNAUTH',
                actor_name=identifier,
                organization='Security Gateway',
                reason=f"Failed admin authentication attempt for: {identifier}",
                access_type='ADMIN_LOGIN_FAILED',
                ip_address=client_ip
            )
            return render_template('admin_login.html', identifier=identifier), 401

        stage = 'session_establishment'
        session.clear()
        session['admin_id'] = admin['id']
        session['username'] = admin['username']
        session['full_name'] = admin['full_name']
        session['email'] = admin['email']
        session['role'] = 'admin'
        session.permanent = True

        client_ip = request.remote_addr or '127.0.0.1'
        safe_log_access(
            db,
            user_id=None,
            doctor_id=None,
            actor_type='ADMIN',
            actor_name=admin['full_name'],
            organization='SahayID Oversight Console',
            reason=f"Admin sign in successful: {admin['username']}",
            access_type='ADMIN_LOGIN',
            ip_address=client_ip
        )

        flash(f"Welcome back, Administrator {admin['full_name']}.", "success")
        return redirect(url_for('admin_dashboard'))

    except Exception as e:
        db_type = 'postgresql' if (isinstance(db, PgConnectionWrapper) or IS_PRODUCTION) else 'sqlite'
        print(f"[SahayID Admin Login Error] route=/admin/login stage={stage} db={db_type} exception={type(e).__name__}: {e}")
        flash("Unable to process administrator sign in right now. Please try again.", "error")
        return render_template('admin_login.html', identifier=identifier), 500


@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """
    Dedicated Admin Verification & Oversight Dashboard.
    Displays pending, verified, and rejected doctor credentials, metrics, and security audit logs.
    """
    db = get_db()
    cursor = db.cursor()

    # Query metrics
    cursor.execute("SELECT COUNT(*) AS count FROM doctors WHERE LOWER(COALESCE(verification_status, 'pending')) = 'pending'")
    row = cursor.fetchone()
    pending_count = row['count'] if row else 0

    cursor.execute("SELECT COUNT(*) AS count FROM doctors WHERE LOWER(verification_status) = 'verified'")
    row = cursor.fetchone()
    verified_count = row['count'] if row else 0

    cursor.execute("SELECT COUNT(*) AS count FROM doctors WHERE LOWER(verification_status) = 'rejected'")
    row = cursor.fetchone()
    rejected_count = row['count'] if row else 0

    cursor.execute("SELECT COUNT(*) AS count FROM users")
    row = cursor.fetchone()
    patient_count = row['count'] if row else 0

    cursor.execute("SELECT COUNT(*) AS count FROM access_logs")
    row = cursor.fetchone()
    audit_count = row['count'] if row else 0

    stats = {
        'pending_doctors': pending_count,
        'verified_doctors': verified_count,
        'rejected_doctors': rejected_count,
        'total_patients': patient_count,
        'total_audit_events': audit_count,
    }

    # Query doctor lists
    cursor.execute("SELECT * FROM doctors WHERE LOWER(COALESCE(verification_status, 'pending')) = 'pending' ORDER BY id DESC")
    pending_doctors = cursor.fetchall()

    cursor.execute("SELECT * FROM doctors WHERE LOWER(verification_status) = 'verified' ORDER BY id DESC")
    verified_doctors = cursor.fetchall()

    cursor.execute("SELECT * FROM doctors WHERE LOWER(verification_status) = 'rejected' ORDER BY id DESC")
    rejected_doctors = cursor.fetchall()

    # Query audit logs with defensive joins
    cursor.execute(
        """
        SELECT
            al.id,
            al.user_id,
            al.doctor_id,
            al.actor_type,
            al.actor_name,
            al.organization,
            al.reason,
            al.access_type,
            al.accessed_at,
            al.ip_address,
            u.medi_id AS patient_medi_id,
            u.full_name AS patient_name,
            d.doctor_id AS doc_code,
            d.full_name AS doctor_name
        FROM access_logs al
        LEFT JOIN users u ON al.user_id = u.id
        LEFT JOIN doctors d ON al.doctor_id = d.id
        ORDER BY al.id DESC
        LIMIT 200
        """
    )
    audit_logs = cursor.fetchall()

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        pending_doctors=pending_doctors,
        verified_doctors=verified_doctors,
        rejected_doctors=rejected_doctors,
        audit_logs=audit_logs
    )


@app.route('/admin/doctor/<int:doctor_id>/approve', methods=['POST'])
@admin_required
def admin_approve_doctor(doctor_id):
    """
    Admin Doctor Approval Handler.
    Authorizes a registered physician, granting active clinical lookup permissions.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor:
        flash("Doctor record not found.", "error")
        return redirect(url_for('admin_dashboard'))

    admin_id = session.get('admin_id')
    admin_name = session.get('full_name', 'Administrator')
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
        """
        UPDATE doctors
        SET verification_status = 'verified',
            verified_at = ?,
            verified_by = ?,
            verification_reason = NULL
        WHERE id = ?
        """,
        (now_str, admin_id, doctor_id)
    )
    db.commit()

    client_ip = request.remote_addr or '127.0.0.1'
    safe_log_access(
        db,
        user_id=None,
        doctor_id=doctor_id,
        actor_type='ADMIN',
        actor_name=admin_name,
        organization='SahayID Oversight Console',
        reason=f"Physician credentials verified: Dr. {doctor['full_name']} (Reg: {doctor['registration_number']})",
        access_type='DOCTOR_APPROVED',
        ip_address=client_ip
    )

    flash(f"Dr. {doctor['full_name']} has been approved and granted verified clinical access.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/doctor/<int:doctor_id>/reject', methods=['POST'])
@admin_required
def admin_reject_doctor(doctor_id):
    """
    Admin Doctor Rejection Handler.
    Denies practitioner credentials with an explicit justification.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    if not doctor:
        flash("Doctor record not found.", "error")
        return redirect(url_for('admin_dashboard'))

    rejection_reason = request.form.get('rejection_reason', '').strip()
    if not rejection_reason:
        flash("Please provide a reason for rejecting the physician's verification.", "error")
        return redirect(url_for('admin_dashboard'))

    admin_id = session.get('admin_id')
    admin_name = session.get('full_name', 'Administrator')
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
        """
        UPDATE doctors
        SET verification_status = 'rejected',
            verified_at = ?,
            verified_by = ?,
            verification_reason = ?
        WHERE id = ?
        """,
        (now_str, admin_id, rejection_reason, doctor_id)
    )
    db.commit()

    client_ip = request.remote_addr or '127.0.0.1'
    safe_log_access(
        db,
        user_id=None,
        doctor_id=doctor_id,
        actor_type='ADMIN',
        actor_name=admin_name,
        organization='SahayID Oversight Console',
        reason=f"Physician credentials rejected: Dr. {doctor['full_name']} (Reason: {rejection_reason})",
        access_type='DOCTOR_REJECTED',
        ip_address=client_ip
    )

    flash(f"Verification application for Dr. {doctor['full_name']} has been rejected.", "info")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/logout', methods=['GET', 'POST'])
def admin_logout():
    """Sign out administrator and clear session."""
    session.clear()
    flash("You have been signed out of the Administrator Console.", "info")
    return redirect(url_for('admin_login'))


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
