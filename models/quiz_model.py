"""Các hàm dữ liệu dùng chung cho Quiz."""
from .database import get_db


def list_subjects():
    return [row['subject'] for row in get_db().execute(
        'SELECT DISTINCT subject FROM questions ORDER BY subject'
    ).fetchall()]


def list_topics(subject=None):
    if subject:
        return [row['topic'] for row in get_db().execute(
            'SELECT DISTINCT topic FROM questions WHERE subject = ? ORDER BY topic', (subject,)
        ).fetchall()]
    return [row['topic'] for row in get_db().execute(
        'SELECT DISTINCT topic FROM questions ORDER BY topic'
    ).fetchall()]


def random_questions(subject, topic=None, quantity=5):
    quantity = min(max(int(quantity), 1), 10)
    if topic:
        return get_db().execute(
            'SELECT * FROM questions WHERE subject = ? AND topic = ? ORDER BY RANDOM() LIMIT ?',
            (subject, topic, quantity),
        ).fetchall()
    return get_db().execute(
        'SELECT * FROM questions WHERE subject = ? ORDER BY RANDOM() LIMIT ?',
        (subject, quantity),
    ).fetchall()


def save_attempt(user_id, subject, topic, total, correct, score, exp_earned):
    db = get_db()
    cursor = db.execute(
        'INSERT INTO quiz_attempts(user_id,subject,topic,total_questions,correct_answers,score,exp_earned) VALUES(?,?,?,?,?,?,?)',
        (user_id, subject, topic or '', int(total), int(correct), float(score), int(exp_earned)),
    )
    db.commit()
    return cursor.lastrowid


def user_history(user_id, limit=20):
    return get_db().execute(
        'SELECT * FROM quiz_attempts WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?',
        (user_id, int(limit)),
    ).fetchall()
