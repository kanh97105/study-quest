import os
import re
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from config import DATABASE
from models.database import close_db, get_db, init_db
from models.profile_model import add_exp as add_profile_exp, get_profile
from models.user_model import find_by_id, update_password_hash
from routes.exam_routes import exam_bp
from routes.library_routes import library_bp
from routes.profile_routes import profile_bp
from routes.quiz_routes import quiz_bp

configured_secret = os.environ.get('SECRET_KEY')
if not configured_secret or len(configured_secret.encode('utf-8')) < 32:
    raise RuntimeError('Set SECRET_KEY to a random value of at least 32 bytes.')

app = Flask(__name__)
app.config.update(
    SECRET_KEY=configured_secret,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
)

app.teardown_appcontext(close_db)
app.register_blueprint(exam_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(library_bp)
app.register_blueprint(profile_bp)


def current_user():
    if 'user_id' not in session:
        return None
    return get_profile(session['user_id'])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash('Em hãy đăng nhập để tiếp tục nhé.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def _change_password_csrf_token():
    token = session.get('change_password_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['change_password_csrf'] = token
    return token


def _pomodoro_csrf_token():
    token = session.get('pomodoro_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['pomodoro_csrf'] = token
    return token


def _valid_pomodoro_csrf():
    expected_token = session.get('pomodoro_csrf', '')
    posted_token = request.form.get('csrf_token', '')
    return bool(expected_token) and secrets.compare_digest(str(expected_token), str(posted_token))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user['role'] != 'admin':
            flash('Khu vực này chỉ dành cho Admin.', 'warning')
            return redirect(url_for('dashboard'))
        return view(*args, **kwargs)
    return wrapped


def add_exp(user_id, amount):
    return add_profile_exp(user_id, amount)


def generate_plan(exam_id, exam_date, minutes, topic_names):
    db = get_db(); start = date.today(); end = date.fromisoformat(exam_date)
    days = max(1, (end - start).days); topics = topic_names or ['Tổng ôn kiến thức']
    phases = []
    for i in range(days):
        ratio = i / max(days, 1)
        if ratio < .28: kind = 'Lý thuyết'
        elif ratio < .70: kind = 'Luyện bài tập'
        elif ratio < .86: kind = 'Ôn lỗi sai'
        else: kind = 'Làm đề & chữa lỗi'
        phases.append(kind)
    for i, kind in enumerate(phases):
        topic = topics[min(len(topics)-1, int(i * len(topics) / max(days, 1)))]
        db.execute('INSERT INTO study_plans(exam_id,study_date,title,activity_type,duration_minutes) VALUES(?,?,?,?,?)',
                   (exam_id, (start + timedelta(days=i)).isoformat(), f'{kind}: {topic}', kind, minutes))
    db.commit()


@app.context_processor
def inject_globals():
    return {'current_user': current_user(), 'today': date.today().isoformat()}


@app.route('/')
def index():
    return render_template(
        'index.html',
        contact_csrf_token=_contact_csrf_token(),
        contact_values={},
        contact_cooldown_remaining=_contact_cooldown_remaining(),
    )


CONTACT_COOLDOWN_SECONDS = 15


def _contact_cooldown_remaining():
    last_sent = session.get('contact_last_sent')
    if not isinstance(last_sent, (int, float)):
        return 0
    return max(0, int(CONTACT_COOLDOWN_SECONDS - (time.time() - last_sent) + 0.999))


def _contact_csrf_token():
    token = session.get('contact_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['contact_csrf'] = token
    return token


@app.post('/contact')
def contact():
    expected_token = session.get('contact_csrf', '')
    posted_token = request.form.get('csrf_token', '')
    if not expected_token or not secrets.compare_digest(str(expected_token), str(posted_token)):
        flash('Phiên gửi lời nhắn không hợp lệ. Em tải lại trang rồi thử lại nhé.', 'warning')
        return redirect(url_for('index') + '#lien-he')

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    subject = request.form.get('subject', '').strip()
    message = request.form.get('message', '').strip()
    contact_values = {
        'name': name,
        'email': email,
        'subject': subject,
        'message': message,
    }

    allowed_subjects = {
        'Góp ý về website',
        'Báo lỗi',
        'Hỏi về tính năng',
        'Khác',
    }
    error = None
    if not name or not email or not subject or not message:
        error = 'Vui lòng điền đầy đủ các trường bắt buộc.'
    elif len(name) > 120:
        error = 'Họ và tên không được vượt quá 120 ký tự.'
    elif len(email) > 254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        error = 'Vui lòng nhập địa chỉ email hợp lệ.'
    elif subject not in allowed_subjects:
        error = 'Vui lòng chọn một chủ đề hợp lệ.'
    elif len(message) > 2000:
        error = 'Nội dung câu hỏi không được vượt quá 2000 ký tự.'

    if error:
        flash(error, 'warning')
        return render_template(
            'index.html',
            contact_csrf_token=_contact_csrf_token(),
            contact_values=contact_values,
            contact_cooldown_remaining=_contact_cooldown_remaining(),
        ), 400

    cooldown_remaining = _contact_cooldown_remaining()
    if cooldown_remaining:
        flash(f'Em có thể gửi lời nhắn tiếp theo sau {cooldown_remaining} giây nữa nhé.', 'warning')
        return render_template(
            'index.html',
            contact_csrf_token=_contact_csrf_token(),
            contact_values=contact_values,
            contact_cooldown_remaining=cooldown_remaining,
        ), 429

    db = get_db()
    db.execute(
        'INSERT INTO contact_messages(name, email, subject, message) VALUES(?, ?, ?, ?)',
        (name, email, subject, message),
    )
    db.commit()
    session.pop('contact_csrf', None)
    session['contact_last_sent'] = time.time()
    flash('Đã gửi lời nhắn thành công.', 'success')
    return redirect(url_for('index') + '#lien-he')


@app.route('/manus-routes.json')
def route_manifest():
    return send_from_directory(os.path.dirname(__file__), 'manus-routes.json', mimetype='application/json')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip(); email = request.form.get('email', '').strip(); password = request.form.get('password', '')
        if len(username) < 3 or len(password) < 6 or '@' not in email:
            flash('Tên đăng nhập từ 3 ký tự, email hợp lệ và mật khẩu ít nhất 6 ký tự.', 'warning')
        else:
            try:
                db = get_db(); cur = db.execute('INSERT INTO users(username,email,password_hash) VALUES(?,?,?)', (username, email, generate_password_hash(password)))
                db.execute('INSERT INTO profiles(user_id,character_name) VALUES(?,?)', (cur.lastrowid, username.title()))
                db.commit(); flash('Tạo tài khoản thành công. Em đăng nhập nhé!', 'success'); return redirect(url_for('login'))
            except sqlite3.IntegrityError: flash('Tên đăng nhập hoặc email đã tồn tại.', 'warning')
    return render_template('auth/register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = get_db().execute('SELECT * FROM users WHERE username=? OR email=?', (request.form.get('identity','').strip(), request.form.get('identity','').strip())).fetchone()
        if user and check_password_hash(user['password_hash'], request.form.get('password', '')):
            session.clear(); session['user_id'] = user['id']; return redirect(url_for('dashboard'))
        flash('Thông tin đăng nhập chưa đúng.', 'warning')
    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('index'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = find_by_id(session['user_id'])
    if user is None:
        session.clear()
        flash('Không tìm thấy tài khoản. Em hãy đăng nhập lại nhé.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        posted_token = request.form.get('csrf_token', '')
        expected_token = session.get('change_password_csrf', '')
        if not expected_token or not secrets.compare_digest(str(expected_token), str(posted_token)):
            flash('Phiên đổi mật khẩu không hợp lệ. Em tải lại trang rồi thử lại nhé.', 'warning')
            return redirect(url_for('change_password'))

        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not check_password_hash(user['password_hash'], current_password):
            flash('Mật khẩu hiện tại không đúng.', 'warning')
        elif len(new_password) < 12:
            flash('Mật khẩu mới cần có ít nhất 12 ký tự.', 'warning')
        elif new_password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'warning')
        elif not update_password_hash(session['user_id'], generate_password_hash(new_password)):
            flash('Không thể cập nhật mật khẩu. Em thử lại nhé.', 'warning')
        else:
            session.clear()
            flash('Đổi mật khẩu thành công. Em đăng nhập lại nhé.', 'success')
            return redirect(url_for('login'))

    return render_template(
        'auth/change_password.html',
        csrf_token=_change_password_csrf_token(),
    )


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user(); db = get_db(); exams = db.execute('SELECT * FROM exams WHERE user_id=? ORDER BY exam_date LIMIT 4', (user['id'],)).fetchall()
    plans = db.execute('SELECT sp.*, e.subject FROM study_plans sp JOIN exams e ON e.id=sp.exam_id WHERE e.user_id=? ORDER BY sp.study_date, sp.id LIMIT 8', (user['id'],)).fetchall()
    stats = {'done': db.execute('SELECT COUNT(*) FROM study_plans sp JOIN exams e ON e.id=sp.exam_id WHERE e.user_id=? AND completed=1', (user['id'],)).fetchone()[0], 'total': db.execute('SELECT COUNT(*) FROM study_plans sp JOIN exams e ON e.id=sp.exam_id WHERE e.user_id=?', (user['id'],)).fetchone()[0], 'quiz': db.execute('SELECT COUNT(*) FROM quiz_attempts WHERE user_id=?', (user['id'],)).fetchone()[0]}
    return render_template('dashboard.html', exams=exams, plans=plans, stats=stats)


@app.route('/pomodoro')
@login_required
def pomodoro():
    active_session = session.get('pomodoro_active')
    active_row = None
    if isinstance(active_session, dict) and active_session.get('user_id') == session['user_id']:
        active_row = get_db().execute(
            'SELECT id, duration_minutes, completed_at FROM pomodoro_sessions '
            'WHERE id = ? AND user_id = ? AND completed = 2',
            (active_session.get('session_id'), session['user_id']),
        ).fetchone()
    if active_row is None:
        active_row = get_db().execute(
            'SELECT id, duration_minutes, completed_at FROM pomodoro_sessions '
            'WHERE user_id = ? AND completed = 2 ORDER BY id DESC LIMIT 1',
            (session['user_id'],),
        ).fetchone()
        if active_row is None:
            session.pop('pomodoro_active', None)
            active_session = None
        else:
            started_at = datetime.strptime(active_row['completed_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()
            active_session = {
                'user_id': session['user_id'],
                'session_id': active_row['id'],
                'started_at': started_at,
                'duration_seconds': int(active_row['duration_minutes']) * 60,
            }
            session['pomodoro_active'] = active_session

    timer_active = active_session is not None
    duration_seconds = int(active_session['duration_seconds']) if timer_active else 25 * 60
    remaining_seconds = duration_seconds
    can_complete = False
    if timer_active:
        elapsed_seconds = max(0, int(datetime.now(timezone.utc).timestamp() - active_session['started_at']))
        remaining_seconds = max(0, duration_seconds - elapsed_seconds)
        can_complete = remaining_seconds == 0

    rows = get_db().execute(
        'SELECT duration_minutes, completed, completed_at FROM pomodoro_sessions '
        'WHERE user_id = ? AND completed IN (0, 1) ORDER BY completed_at DESC, id DESC LIMIT 50',
        (session['user_id'],),
    ).fetchall()
    history = []
    for row in rows:
        recorded_at = datetime.strptime(row['completed_at'], '%Y-%m-%d %H:%M:%S')
        recorded_at = recorded_at.replace(tzinfo=timezone.utc).astimezone()
        total_minutes = int(row['duration_minutes'])
        duration = f'{total_minutes // 60:02d}:{total_minutes % 60:02d}:00'
        history.append({
            'entry': (
                f'{recorded_at.day}/{recorded_at.month}/{recorded_at.year}-'
                f'{recorded_at.hour}:{recorded_at.minute:02d}-'
                f'{duration}-'
                f'{"hoàn thành" if row["completed"] else "dừng"}'
            ),
        })
    return render_template(
        'pomodoro.html',
        history=history,
        csrf_token=_pomodoro_csrf_token(),
        timer_active=timer_active,
        duration_seconds=duration_seconds,
        remaining_seconds=remaining_seconds,
        can_complete=can_complete,
    )


@app.post('/pomodoro/start')
@login_required
def pomodoro_start():
    if not _valid_pomodoro_csrf():
        flash('Phiên Pomodoro không hợp lệ. Em tải lại trang rồi thử lại nhé.', 'warning')
        return redirect(url_for('pomodoro'))

    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    active_row = db.execute(
        'SELECT id FROM pomodoro_sessions WHERE user_id = ? AND completed = 2 LIMIT 1',
        (session['user_id'],),
    ).fetchone()
    if active_row:
        db.rollback()
        flash('Em đang có một phiên Pomodoro. Hãy hoàn thành hoặc dừng phiên đó trước nhé.', 'warning')
        return redirect(url_for('pomodoro'))

    try:
        duration_seconds = int(request.form.get('duration_seconds', ''))
    except (TypeError, ValueError):
        db.rollback()
        flash('Thời lượng Pomodoro không hợp lệ.', 'warning')
        return redirect(url_for('pomodoro'))
    if not 1 <= duration_seconds <= 359999:
        db.rollback()
        flash('Thời lượng Pomodoro không hợp lệ.', 'warning')
        return redirect(url_for('pomodoro'))

    duration_minutes = (duration_seconds + 59) // 60
    cursor = db.execute(
        'INSERT INTO pomodoro_sessions(user_id, duration_minutes, completed, exp_earned) '
        'VALUES(?, ?, 2, 0)',
        (session['user_id'], duration_minutes),
    )
    db.commit()
    session['pomodoro_active'] = {
        'user_id': session['user_id'],
        'session_id': cursor.lastrowid,
        'started_at': datetime.now(timezone.utc).timestamp(),
        'duration_seconds': duration_seconds,
    }
    return redirect(url_for('pomodoro'))


@app.post('/pomodoro/complete')
@login_required
def pomodoro_complete():
    if not _valid_pomodoro_csrf():
        flash('Phiên Pomodoro không hợp lệ. Em tải lại trang rồi thử lại nhé.', 'warning')
        return redirect(url_for('pomodoro'))

    active_session = session.get('pomodoro_active')
    if not isinstance(active_session, dict) or active_session.get('user_id') != session['user_id']:
        flash('Không tìm thấy phiên Pomodoro đang chạy.', 'warning')
        return redirect(url_for('pomodoro'))
    elapsed_seconds = max(0, int(datetime.now(timezone.utc).timestamp() - active_session['started_at']))
    duration_seconds = int(active_session['duration_seconds'])
    if elapsed_seconds < duration_seconds:
        flash('Phiên tập trung chưa hoàn tất.', 'warning')
        return redirect(url_for('pomodoro'))

    db = get_db()
    cursor = db.execute(
        'UPDATE pomodoro_sessions SET completed = 1, exp_earned = 10, completed_at = CURRENT_TIMESTAMP '
        'WHERE id = ? AND user_id = ? AND completed = 2',
        (active_session.get('session_id'), session['user_id']),
    )
    if cursor.rowcount != 1:
        session.pop('pomodoro_active', None)
        flash('Phiên Pomodoro này đã được ghi nhận hoặc không còn hợp lệ.', 'warning')
        return redirect(url_for('pomodoro'))
    db.commit()
    session.pop('pomodoro_active', None)
    add_exp(session['user_id'], 10)
    flash('Hoàn thành phiên Pomodoro! Em nhận được 10 EXP.', 'success')
    return redirect(url_for('pomodoro'))


@app.post('/pomodoro/stop')
@login_required
def pomodoro_stop():
    if not _valid_pomodoro_csrf():
        flash('Phiên Pomodoro không hợp lệ. Em tải lại trang rồi thử lại nhé.', 'warning')
        return redirect(url_for('pomodoro'))

    active_session = session.get('pomodoro_active')
    if not isinstance(active_session, dict) or active_session.get('user_id') != session['user_id']:
        flash('Không tìm thấy phiên Pomodoro đang chạy.', 'warning')
        return redirect(url_for('pomodoro'))

    elapsed_seconds = max(0, int(datetime.now(timezone.utc).timestamp() - active_session['started_at']))
    duration_seconds = int(active_session['duration_seconds'])
    minutes = (duration_seconds + 59) // 60
    exp_earned = (minutes * 2) // 5 if elapsed_seconds * 3 >= duration_seconds * 2 else 0
    db = get_db()
    cursor = db.execute(
        'UPDATE pomodoro_sessions SET duration_minutes = ?, completed = 0, exp_earned = ?, '
        'completed_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ? AND completed = 2',
        (minutes, exp_earned, active_session.get('session_id'), session['user_id']),
    )
    if cursor.rowcount != 1:
        session.pop('pomodoro_active', None)
        flash('Phiên Pomodoro này đã được ghi nhận hoặc không còn hợp lệ.', 'warning')
        return redirect(url_for('pomodoro'))
    db.commit()
    session.pop('pomodoro_active', None)
    if exp_earned:
        add_exp(session['user_id'], exp_earned)
        flash(f'Đã lưu phiên tập trung. Em nhận được {exp_earned} EXP.', 'success')
    else:
        flash('Đã lưu phiên dừng. Em chưa đạt 2/3 thời lượng nên chưa nhận EXP.', 'info')
    return redirect(url_for('pomodoro'))


@app.route('/admin')
@admin_required
def admin():
    db = get_db(); stats = {'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 'questions': db.execute('SELECT COUNT(*) FROM questions').fetchone()[0], 'attempts': db.execute('SELECT COUNT(*) FROM quiz_attempts').fetchone()[0], 'plans': db.execute('SELECT COUNT(*) FROM study_plans').fetchone()[0]}; users = db.execute('SELECT id,username,email,role,created_at FROM users ORDER BY id DESC LIMIT 10').fetchall(); return render_template('admin.html', stats=stats, users=users)


@app.route('/admin/contact-messages')
@admin_required
def admin_contact_messages():
    messages = get_db().execute(
        'SELECT id, name, email, subject, message, created_at '
        'FROM contact_messages ORDER BY id DESC'
    ).fetchall()
    return render_template('admin/contact_messages.html', messages=messages)


@app.errorhandler(404)
def not_found(error): return render_template('base.html', content_title='Không tìm thấy trang'), 404


if __name__ == '__main__':
    init_db(); app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)), debug=False)
