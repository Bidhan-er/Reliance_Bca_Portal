"""
database.py – MySQL connection pool + all DB operations
"""

import os
import bcrypt
import random
import string
from datetime import datetime, timedelta

import streamlit as st
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling


# Load .env for local development
load_dotenv()



def get_config(key, default=None):
    """
    Get configuration from Streamlit Secrets when deployed.
    Fall back to .env/environment variables when running locally.
    """
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, default)

_pool = None


def _get_pool():
    global _pool

    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="bca_pool",
            pool_size=5,
            host=get_config("DB_HOST", "localhost"),
            port=int(get_config("DB_PORT", 3306)),
            database=get_config("DB_NAME", "bca_portal"),
            user=get_config("DB_USER", "root"),
            password=get_config("DB_PASSWORD", ""),
            autocommit=False,
            charset="utf8mb4",
        )

    return _pool


def get_conn():
    return _get_pool().get_connection()



DDL = """
CREATE TABLE IF NOT EXISTS students (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    regno           VARCHAR(30) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    address         TEXT,
    dob             DATE,
    phone           VARCHAR(20),
    university      VARCHAR(100),
    email           VARCHAR(150),
    stream          VARCHAR(20),
    semester        VARCHAR(10),
    guardian_name   VARCHAR(100),
    guardian_phone  VARCHAR(20),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS auth (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    regno           VARCHAR(30) UNIQUE NOT NULL,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    is_first_login  TINYINT(1) DEFAULT 1,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (regno) REFERENCES students(regno) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS otp_tokens (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    regno       VARCHAR(30) NOT NULL,
    email       VARCHAR(150) NOT NULL,
    otp         VARCHAR(10) NOT NULL,
    expires_at  DATETIME NOT NULL,
    used        TINYINT(1) DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admins (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def init_db():
    """Create tables and seed default admin."""

    conn = get_conn()
    cur = conn.cursor()

    for stmt in DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)

    # Seed admin from configuration if not present
    admin_user = get_config("ADMIN_USERNAME", "admin")
    admin_pass = get_config("ADMIN_PASSWORD", "Admin@1234")

    cur.execute(
        "SELECT id FROM admins WHERE username=%s",
        (admin_user,)
    )

    if not cur.fetchone():
        hashed = bcrypt.hashpw(
            admin_pass.encode(),
            bcrypt.gensalt()
        ).decode()

        cur.execute(
            "INSERT INTO admins (username, password_hash) VALUES (%s,%s)",
            (admin_user, hashed)
        )

    conn.commit()
    cur.close()
    conn.close()



def _row(cursor) -> dict | None:
    row = cursor.fetchone()

    if not row:
        return None

    cols = [d[0] for d in cursor.description]

    return dict(zip(cols, row))


def _rows(cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]

    return [
        dict(zip(cols, r))
        for r in cursor.fetchall()
    ]


def default_password(regno: str, dob) -> str:
    """
    regno = 'BCA-2081-001'
    dob   = datetime.date or str 'YYYY-MM-DD' or 'DD/MM/YYYY'

    Returns example:
    'BCA-2081-00104082004'
    """

    if dob is None:
        return regno + "00000000"

    if hasattr(dob, "strftime"):
        dob_str = dob.strftime("%d%m%Y")

    else:
        dob = str(dob)

        if "/" in dob:
            # DD/MM/YYYY
            parts = dob.split("/")
            dob_str = parts[0] + parts[1] + parts[2]

        elif "-" in dob:
            # YYYY-MM-DD
            parts = dob.split("-")
            dob_str = parts[2] + parts[1] + parts[0]

        else:
            dob_str = dob[:8]

    return regno + dob_str



def upsert_student(
    regno,
    name,
    address,
    dob,
    phone,
    university,
    email,
    stream,
    semester,
    guardian_name,
    guardian_phone
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO students
        (
            regno,
            name,
            address,
            dob,
            phone,
            university,
            email,
            stream,
            semester,
            guardian_name,
            guardian_phone
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)

        ON DUPLICATE KEY UPDATE
            name=%s,
            address=%s,
            dob=%s,
            phone=%s,
            university=%s,
            email=%s,
            stream=%s,
            semester=%s,
            guardian_name=%s,
            guardian_phone=%s
        """,
        (
            regno,
            name,
            address,
            dob,
            phone,
            university,
            email,
            stream,
            semester,
            guardian_name,
            guardian_phone,

            name,
            address,
            dob,
            phone,
            university,
            email,
            stream,
            semester,
            guardian_name,
            guardian_phone
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def get_student(regno: str) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM students WHERE regno=%s",
        (regno,)
    )

    row = _row(cur)

    cur.close()
    conn.close()

    return row


def get_all_students() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT s.*, a.username, a.is_first_login
        FROM students s
        LEFT JOIN auth a ON s.regno = a.regno
        ORDER BY s.semester, s.regno
        """
    )

    rows = _rows(cur)

    cur.close()
    conn.close()

    return rows


def update_student_profile(
    regno,
    name,
    email,
    phone,
    address
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE students
        SET name=%s,
            email=%s,
            phone=%s,
            address=%s
        WHERE regno=%s
        """,
        (
            name,
            email,
            phone,
            address,
            regno
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def delete_student(regno: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM students WHERE regno=%s",
        (regno,)
    )

    conn.commit()
    cur.close()
    conn.close()


def search_students(query: str) -> list[dict]:
    q = f"%{query}%"

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT s.*, a.username, a.is_first_login
        FROM students s
        LEFT JOIN auth a ON s.regno=a.regno
        WHERE s.regno LIKE %s
           OR s.name LIKE %s
           OR s.email LIKE %s
           OR s.semester LIKE %s
        ORDER BY s.semester, s.regno
        """,
        (q, q, q, q)
    )

    rows = _rows(cur)

    cur.close()
    conn.close()

    return rows



def create_auth(regno: str, dob) -> str:
    """Create auth row with default password."""

    raw = default_password(regno, dob)

    hashed = bcrypt.hashpw(
        raw.encode(),
        bcrypt.gensalt()
    ).decode()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO auth
        (regno, username, password_hash, is_first_login)
        VALUES (%s,%s,%s,1)

        ON DUPLICATE KEY UPDATE
            username=%s,
            password_hash=%s,
            is_first_login=1
        """,
        (
            regno,
            regno,
            hashed,
            regno,
            hashed
        )
    )

    conn.commit()
    cur.close()
    conn.close()

    return raw


def auth_exists(regno: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM auth WHERE regno=%s",
        (regno,)
    )

    exists = cur.fetchone() is not None

    cur.close()
    conn.close()

    return exists


def verify_password(username: str, raw: str) -> str | None:
    """Returns regno if credentials are correct, else None."""

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT regno, password_hash
        FROM auth
        WHERE username=%s
        """,
        (username,)
    )

    row = _row(cur)

    cur.close()
    conn.close()

    if not row:
        return None

    if bcrypt.checkpw(
        raw.encode(),
        row["password_hash"].encode()
    ):
        return row["regno"]

    return None


def is_first_login(regno: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT is_first_login FROM auth WHERE regno=%s",
        (regno,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return bool(row[0]) if row else True


def change_password(regno: str, new_pw: str):
    hashed = bcrypt.hashpw(
        new_pw.encode(),
        bcrypt.gensalt()
    ).decode()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE auth
        SET password_hash=%s,
            is_first_login=0
        WHERE regno=%s
        """,
        (
            hashed,
            regno
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def admin_reset_password(regno: str) -> str:
    """Reset to default password."""

    student = get_student(regno)

    if not student:
        return ""

    raw = default_password(
        regno,
        student["dob"]
    )

    hashed = bcrypt.hashpw(
        raw.encode(),
        bcrypt.gensalt()
    ).decode()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE auth
        SET password_hash=%s,
            is_first_login=1
        WHERE regno=%s
        """,
        (
            hashed,
            regno
        )
    )

    conn.commit()
    cur.close()
    conn.close()

    return raw


def get_credentials_for_export() -> list[dict]:
    """For admin: all students with username and default password hint."""

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            s.regno,
            s.name,
            s.semester,
            s.email,
            s.dob,
            a.username,
            a.is_first_login
        FROM students s
        LEFT JOIN auth a ON s.regno=a.regno
        ORDER BY s.semester, s.regno
        """
    )

    rows = _rows(cur)

    cur.close()
    conn.close()

    for r in rows:
        r["default_password"] = default_password(
            r["regno"],
            r["dob"]
        )

    return rows



def generate_otp(n=6) -> str:
    return "".join(
        random.choices(
            string.digits,
            k=n
        )
    )


def save_otp(
    regno: str,
    email: str,
    otp: str,
    ttl=10
):
    expires = (
        datetime.now() +
        timedelta(minutes=ttl)
    ).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE otp_tokens
        SET used=1
        WHERE regno=%s AND used=0
        """,
        (regno,)
    )

    cur.execute(
        """
        INSERT INTO otp_tokens
        (regno,email,otp,expires_at)
        VALUES (%s,%s,%s,%s)
        """,
        (
            regno,
            email,
            otp,
            expires
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def verify_otp(regno: str, otp: str) -> bool:
    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM otp_tokens
        WHERE regno=%s
          AND otp=%s
          AND used=0
          AND expires_at > %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            regno,
            otp,
            now
        )
    )

    row = cur.fetchone()

    if row:
        cur.execute(
            """
            UPDATE otp_tokens
            SET used=1
            WHERE id=%s
            """,
            (row[0],)
        )

        conn.commit()

    cur.close()
    conn.close()

    return row is not None


def get_email_by_regno(regno: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT email FROM students WHERE regno=%s",
        (regno,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row[0] if row else None



def verify_admin(
    username: str,
    password: str
) -> bool:

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT password_hash
        FROM admins
        WHERE username=%s
        """,
        (username,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return False

    return bcrypt.checkpw(
        password.encode(),
        row[0].encode()
    )


def change_admin_password(
    username: str,
    new_pw: str
):
    hashed = bcrypt.hashpw(
        new_pw.encode(),
        bcrypt.gensalt()
    ).decode()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE admins
        SET password_hash=%s
        WHERE username=%s
        """,
        (
            hashed,
            username
        )
    )

    conn.commit()
    cur.close()
    conn.close()


def get_stats() -> dict:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM students"
    )
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM auth"
    )
    with_auth = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM auth
        WHERE is_first_login=0
        """
    )
    changed = cur.fetchone()[0]

    cur.execute(
        """
        SELECT semester, COUNT(*)
        FROM students
        GROUP BY semester
        ORDER BY semester
        """
    )

    by_sem = dict(cur.fetchall())

    cur.close()
    conn.close()

    return {
        "total": total,
        "with_auth": with_auth,
        "pw_changed": changed,
        "by_semester": by_sem
    }