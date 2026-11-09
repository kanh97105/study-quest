"""Các thao tác dữ liệu cho users. Route Auth/Admin gọi các hàm ở đây."""
from .database import get_db


def find_by_identity(identity):
    return get_db().execute(
        'SELECT * FROM users WHERE username = ? OR email = ?',
        (identity.strip(), identity.strip()),
    ).fetchone()


def find_by_id(user_id):
    return get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()


def update_password_hash(user_id, password_hash):
    db = get_db()
    cursor = db.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (password_hash, user_id),
    )
    db.commit()
    return cursor.rowcount == 1


def create_user(username, email, password_hash, role='user', admin_permission=None):
    db = get_db()
    cursor = db.execute(
        'INSERT INTO users(username,email,password_hash,role,admin_permission) VALUES(?,?,?,?,?)',
        (username.strip(), email.strip().lower(), password_hash, role, admin_permission),
    )
    db.execute(
        'INSERT INTO profiles(user_id, character_name) VALUES(?, ?)',
        (cursor.lastrowid, username.strip().title()),
    )
    db.commit()
    return cursor.lastrowid


def list_users(limit=100):
    return get_db().execute(
        'SELECT id, username, email, role, admin_permission, created_at FROM users ORDER BY id DESC LIMIT ?',
        (int(limit),),
    ).fetchall()
