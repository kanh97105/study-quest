"""Database layer dùng chung cho toàn bộ Study Quest.

Các route/model khác chỉ cần:
    from models.database import get_db
    db = get_db()

Không tạo sqlite3.connect() ở module khác.
"""
from pathlib import Path
import sqlite3
from flask import g
from werkzeug.security import generate_password_hash

from config import DATABASE

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    admin_permission TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    character_name TEXT NOT NULL DEFAULT 'Quest Rookie',
    avatar TEXT NOT NULL DEFAULT '🧙',
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    reward_points INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    exam_date TEXT NOT NULL,
    current_score REAL NOT NULL CHECK(current_score BETWEEN 0 AND 10),
    target_score REAL NOT NULL CHECK(target_score BETWEEN 0 AND 10),
    study_minutes_per_day INTEGER NOT NULL CHECK(study_minutes_per_day >= 10),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Chưa học',
    progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
    FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS study_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    study_date TEXT NOT NULL,
    title TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'medium',
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_answer TEXT NOT NULL CHECK(correct_answer IN ('A','B','C','D')),
    explanation TEXT
);
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    topic TEXT,
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    score REAL NOT NULL,
    exp_earned INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS quiz_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    selected_answer TEXT,
    is_correct INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY(question_id) REFERENCES questions(id)
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    subject TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Học tập',
    topic TEXT,
    description TEXT,
    cover_url TEXT,
    resource_url TEXT,
    rating REAL NOT NULL DEFAULT 4.5,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pomodoro_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    duration_minutes INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 1,
    exp_earned INTEGER NOT NULL DEFAULT 10,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, title),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

QUESTION_SEED = [
    ('Toán', 'Hàm số', 'easy', 'Đạo hàm của x² là gì?', 'x', '2x', 'x²', '2', 'B', "Quy tắc đạo hàm: (x²)' = 2x."),
    ('Toán', 'Hàm số', 'easy', 'Hàm số y = 2x + 1 có hệ số góc là?', '1', '2', '-1', '0', 'B', 'Hệ số của x là hệ số góc.'),
    ('Vật lý', 'Dao động', 'easy', 'Đơn vị của tần số là gì?', 'Newton', 'Joule', 'Hertz', 'Watt', 'C', 'Tần số đo bằng Hertz (Hz).'),
    ('Hóa học', 'Hữu cơ', 'easy', 'Công thức của methane là?', 'CH4', 'C2H6', 'CO2', 'H2O', 'A', 'Methane có công thức CH4.'),
    ('Anh văn', 'Từ vựng', 'easy', 'Choose the synonym of “rapid”.', 'slow', 'quick', 'weak', 'late', 'B', 'Rapid means quick.'),
]

BOOK_SEED = [
    ('Toán 12', 'Study Quest', 'Toán học', 'Tài liệu học tập', 'Hàm số và tích phân',
     'Tài liệu hỗ trợ học tập môn Toán lớp 12, tổng hợp các kiến thức quan trọng về hàm số, nguyên hàm - tích phân, số phức, hình học và xác suất. Nội dung được trình bày ngắn gọn, dễ theo dõi, giúp học sinh củng cố nền tảng và rèn luyện tư duy giải bài tập.',
     'images/library/toan.png', '', 4.5),
    ('Vật Lý 12', 'Study Quest', 'Vật lý', 'Tài liệu học tập', 'Dao động và sóng',
     'Tài liệu tổng hợp các kiến thức trọng tâm của Vật lý 12 như dao động, sóng, điện xoay chiều, lượng tử ánh sáng và vật lý hạt nhân. Nội dung giúp học sinh hệ thống hóa công thức, hiểu bản chất hiện tượng và hỗ trợ quá trình ôn tập.',
     'images/library/vatly.png', '', 4.5),
    ('Hóa Học 12', 'Study Quest', 'Hóa học', 'Tài liệu học tập', 'Hóa hữu cơ',
     'Tài liệu học tập môn Hóa học 12 tập trung vào các chuyên đề quan trọng như hóa hữu cơ, hợp chất carbon, phản ứng hóa học và ứng dụng thực tế. Nội dung được thiết kế để giúp học sinh dễ dàng ôn tập và ghi nhớ kiến thức.',
     'images/library/hoa.png', '', 4.5),
    ('Ngữ Pháp Tiếng Anh THPT', 'Study Quest', 'Tiếng Anh', 'Tài liệu học tập', 'Ngữ pháp',
     'Tài liệu tổng hợp các chủ điểm ngữ pháp tiếng Anh thường gặp trong chương trình THPT như các thì, câu bị động, câu điều kiện, mệnh đề quan hệ và cấu trúc câu. Giúp học sinh tra cứu nhanh và củng cố kiến thức ngữ pháp.',
     'images/library/ta.png', '', 4.5),
    ('Kỹ Năng Tự Học Hiệu Quả', 'Study Quest', 'Kỹ năng học tập', 'Tài liệu học tập', 'Tự học',
     'Tài liệu hướng dẫn xây dựng phương pháp học tập hiệu quả thông qua việc lập kế hoạch, quản lý thời gian, ghi chú và phát triển thói quen tự học. Nội dung giúp học sinh nâng cao khả năng tổ chức việc học và duy trì động lực.',
     'images/library/tuhoc.png', '', 4.5),
]


def get_db():
    """Lấy connection hiện tại của request Flask, dùng Row để truy cập bằng tên cột."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(seed=True):
    """Tạo schema an toàn và seed dữ liệu mẫu. Gọi một lần khi khởi động app."""
    Path(DATABASE).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript(SCHEMA)
    if seed:
        _seed_admin(db)
        _seed_questions(db)
        _seed_books(db)
    db.commit()
    db.close()


def _seed_admin(db):
    if db.execute('SELECT 1 FROM users WHERE username = ?', ('admin',)).fetchone():
        return
    cur = db.execute(
        'INSERT INTO users(username,email,password_hash,role,admin_permission) VALUES(?,?,?,?,?)',
        ('admin', 'admin@studyquest.local', generate_password_hash('admin123'), 'admin', 'super_admin'),
    )
    db.execute(
        'INSERT INTO profiles(user_id,character_name,avatar) VALUES(?,?,?)',
        (cur.lastrowid, 'Quest Master', '🛡️'),
    )


def _seed_questions(db):
    if db.execute('SELECT COUNT(*) FROM questions').fetchone()[0] == 0:
        db.executemany(
            'INSERT INTO questions(subject,topic,difficulty,question_text,option_a,option_b,option_c,option_d,correct_answer,explanation) VALUES(?,?,?,?,?,?,?,?,?,?)',
            QUESTION_SEED,
        )


def _seed_books(db):
    legacy_titles = {
        'Toán 12': 'Chinh phục Toán 12',
        'Vật Lý 12': 'Vật lý 12 trọng tâm',
        'Hóa Học 12': 'Sổ tay Hóa hữu cơ',
        'Ngữ Pháp Tiếng Anh THPT': 'Ngữ pháp tiếng Anh THPT',
        'Kỹ Năng Tự Học Hiệu Quả': 'Kỹ năng tự học hiệu quả',
    }
    for book in BOOK_SEED:
        title = book[0]
        existing = db.execute(
            'SELECT id FROM books WHERE title IN (?, ?) ORDER BY title = ? DESC LIMIT 1',
            (title, legacy_titles[title], title),
        ).fetchone()
        if existing:
            db.execute(
                'UPDATE books SET title=?,author=?,subject=?,category=?,topic=?,description=?,cover_url=? WHERE id=?',
                (*book[:7], existing['id']),
            )
        else:
            db.execute(
                'INSERT INTO books(title,author,subject,category,topic,description,cover_url,resource_url,rating) VALUES(?,?,?,?,?,?,?,?,?)',
                book,
            )


if __name__ == '__main__':
    init_db()
    print(f'Database ready: {DATABASE}')
