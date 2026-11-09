"""Các hàm dữ liệu dùng chung cho Smart Exam Planner."""
from .database import get_db


def create_exam(user_id, subject, exam_date, current_score, target_score, minutes):
    db = get_db()
    cursor = db.execute(
        'INSERT INTO exams(user_id,subject,exam_date,current_score,target_score,study_minutes_per_day) VALUES(?,?,?,?,?,?)',
        (user_id, subject.strip(), exam_date, float(current_score), float(target_score), int(minutes)),
    )
    db.commit()
    return cursor.lastrowid


def add_topics(exam_id, topics):
    db = get_db()
    db.executemany(
        'INSERT INTO topics(exam_id, name) VALUES(?, ?)',
        [(exam_id, topic.strip()) for topic in topics if topic.strip()],
    )
    db.commit()


def get_user_exams(user_id):
    return get_db().execute(
        'SELECT * FROM exams WHERE user_id = ? ORDER BY exam_date, id', (user_id,)
    ).fetchall()


def get_exam(exam_id, user_id):
    return get_db().execute(
        'SELECT * FROM exams WHERE id = ? AND user_id = ?', (exam_id, user_id)
    ).fetchone()


def get_topics(exam_id):
    return get_db().execute(
        'SELECT * FROM topics WHERE exam_id = ? ORDER BY id', (exam_id,)
    ).fetchall()


def get_plan(exam_id, user_id):
    return get_db().execute(
        'SELECT sp.* FROM study_plans sp JOIN exams e ON e.id = sp.exam_id '
        'WHERE sp.exam_id = ? AND e.user_id = ? ORDER BY sp.study_date, sp.id',
        (exam_id, user_id),
    ).fetchall()


def toggle_plan(plan_id, user_id):
    db = get_db()
    row = db.execute(
        'SELECT sp.completed FROM study_plans sp JOIN exams e ON e.id = sp.exam_id '
        'WHERE sp.id = ? AND e.user_id = ?', (plan_id, user_id)
    ).fetchone()
    if row is None:
        return None
    completed = 0 if row['completed'] else 1
    db.execute('UPDATE study_plans SET completed = ? WHERE id = ?', (completed, plan_id))
    db.commit()
    return bool(completed)


def calculate_progress(exam_id, user_id):
    row = get_db().execute(
        'SELECT COUNT(*) AS total, COALESCE(SUM(completed), 0) AS done '
        'FROM study_plans sp JOIN exams e ON e.id = sp.exam_id '
        'WHERE sp.exam_id = ? AND e.user_id = ?', (exam_id, user_id)
    ).fetchone()
    return round((row['done'] * 100 / row['total']) if row['total'] else 0)
