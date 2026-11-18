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
CREATE TABLE IF NOT EXISTS contact_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    (
        'Chinh phục Toán 12', 'StudyQuest', 'Toán', 'Học tập', 'Hàm số',
        'Bộ tài liệu tổng hợp kiến thức trọng tâm Toán 12 theo chương trình THPT. '
        'Nội dung gồm lý thuyết, công thức quan trọng, ví dụ minh họa và bài tập '
        'luyện tập giúp học sinh củng cố nền tảng, chuẩn bị cho các kỳ kiểm tra '
        'và kỳ thi tốt nghiệp.',
        'images/library/toan.png', '', 4.5,
    ),
    (
        'Kỹ năng tự học hiệu quả', 'StudyQuest', 'Kỹ năng', 'Lối sống', 'Tự học',
        'Chia sẻ những phương pháp học tập khoa học, cách xây dựng thói quen học '
        'tập bền vững, quản lý thời gian và duy trì động lực để nâng cao hiệu quả tự học.',
        'images/library/tuhoc.png', '', 4.5,
    ),
    (
        'Ngữ pháp tiếng Anh THPT', 'StudyQuest', 'Tiếng Anh', 'Học tập', 'Ngữ pháp',
        'Tổng hợp các chuyên đề ngữ pháp tiếng Anh thường gặp trong chương trình '
        'THPT như thì, câu bị động, mệnh đề quan hệ, câu điều kiện và nhiều cấu '
        'trúc quan trọng khác kèm ví dụ minh họa.',
        'images/library/ta.png', '', 4.5,
    ),
    (
        'Sổ tay Hóa hữu cơ', 'StudyQuest', 'Hóa học', 'Học tập', 'Hữu cơ',
        'Tóm tắt kiến thức Hóa hữu cơ dưới dạng sơ đồ và bảng tổng hợp, bao gồm '
        'các phản ứng đặc trưng, công thức cần nhớ và mẹo giải nhanh các dạng bài thường gặp.',
        'images/library/hoa.png', '', 4.5,
    ),
    (
        'Vật lý 12 trọng tâm', 'StudyQuest', 'Vật lý', 'Học tập', 'Dao động cơ',
        'Tổng hợp kiến thức và công thức trọng tâm chương Dao động cơ lớp 12, '
        'kết hợp bài tập minh họa và hướng dẫn giải giúp học sinh ôn luyện hiệu '
        'quả cho các kỳ thi.',
        'images/library/vatly.png', '', 4.5,
    ),
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
    for book in BOOK_SEED:
        existing = db.execute(
            'SELECT id FROM books WHERE title = ?',
            (book[0],),
        ).fetchone()
        if existing:
            db.execute(
                'UPDATE books SET author=?, subject=?, category=?, topic=?, '
                'description=?, cover_url=?, resource_url=?, rating=? WHERE id=?',
                (*book[1:], existing['id']),
            )
        else:
            db.execute(
                'INSERT INTO books(title,author,subject,category,topic,description,cover_url,resource_url,rating) '
                'VALUES(?,?,?,?,?,?,?,?,?)',
                book,
            )


if __name__ == '__main__':
    init_db()
    print(f'Database ready: {DATABASE}')
