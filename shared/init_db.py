from db import get_connection
from werkzeug.security import generate_password_hash
import uuid


def generate_qr_token():
    return f"USR-{uuid.uuid4().hex[:10].upper()}"


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ---------------- USERS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        qr_token TEXT,
        is_verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Ensure qr_token column exists even for old DBs
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col["name"] for col in cursor.fetchall()]
    if "qr_token" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN qr_token TEXT")

    # Create unique index for qr_token
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_qr_token
        ON users(qr_token)
    """)

    # ---------------- ADMINS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- EMAIL VERIFICATION TOKENS ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_verification_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        token TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        is_used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- WEEKLY MENUS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start_date TEXT NOT NULL,
        day_name TEXT NOT NULL,
        breakfast TEXT,
        lunch TEXT,
        snacks TEXT,
        dinner TEXT,
        created_by_admin_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(week_start_date, day_name),
        FOREIGN KEY(created_by_admin_id) REFERENCES admins(id)
    )
    """)

    # ---------------- QR CODES TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS qr_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meal_date TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        qr_token TEXT UNIQUE NOT NULL,
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )
    """)

    # ---------------- MEAL SCANS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meal_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        qr_code_id INTEGER NOT NULL,
        scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        meal_served_at TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(qr_code_id) REFERENCES qr_codes(id)
    )
    """)

    # ---------------- REVIEWS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        meal_date TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        rating INTEGER NOT NULL,
        review_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # ---------------- BACKFILL QR TOKENS FOR OLD USERS ----------------
    cursor.execute("SELECT id FROM users WHERE qr_token IS NULL OR TRIM(qr_token) = ''")
    old_users = cursor.fetchall()

    for user in old_users:
        token = generate_qr_token()

        while True:
            cursor.execute("SELECT id FROM users WHERE qr_token = ?", (token,))
            existing = cursor.fetchone()
            if not existing:
                break
            token = generate_qr_token()

        cursor.execute("UPDATE users SET qr_token = ? WHERE id = ?", (token, user["id"]))

    # ---------------- DEFAULT ADMIN ----------------
    default_admin_email = "admin@bennett.edu.in"
    default_admin_password = "admin123"

    cursor.execute("SELECT * FROM admins WHERE email = ?", (default_admin_email,))
    existing_admin = cursor.fetchone()

    if not existing_admin:
        cursor.execute("""
        INSERT INTO admins (email, password_hash)
        VALUES (?, ?)
        """, (
            default_admin_email,
            generate_password_hash(default_admin_password)
        ))

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()