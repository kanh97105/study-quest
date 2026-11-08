"""Các hàm dữ liệu dùng chung cho Smart Learning Hub/Library."""
from .database import get_db


def list_books(search='', subject='', category='', limit=50):
    clauses = []
    params = []
    if search.strip():
        clauses.append('(title LIKE ? OR author LIKE ? OR description LIKE ?)')
        value = f'%{search.strip()}%'
        params.extend([value, value, value])
    if subject.strip():
        clauses.append('subject = ?')
        params.append(subject.strip())
    if category.strip():
        clauses.append('category = ?')
        params.append(category.strip())
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params.append(int(limit))
    return get_db().execute(
        f'SELECT * FROM books{where} ORDER BY rating DESC, title LIMIT ?', tuple(params)
    ).fetchall()


def get_book(book_id):
    return get_db().execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()


def list_subjects():
    return [row['subject'] for row in get_db().execute(
        'SELECT DISTINCT subject FROM books ORDER BY subject'
    ).fetchall()]


def list_categories():
    return [row['category'] for row in get_db().execute(
        'SELECT DISTINCT category FROM books ORDER BY category'
    ).fetchall()]
