"""Smoke test cho phần Admin 2.
Chạy: python test_backend.py
Script dùng database tạm, không làm thay đổi database.db thật.
"""
import os
import tempfile
import time
from pathlib import Path

import models.database as database


def main():
    old_database = database.DATABASE
    temp_dir = tempfile.TemporaryDirectory()
    database.DATABASE = str(Path(temp_dir.name) / 'test_database.db')

    try:
        database.init_db()

        from app import app
        from models.exam_model import add_topics, calculate_progress, create_exam
        from models.library_model import get_book, list_books
        from models.profile_model import add_exp, get_profile
        from models.quiz_model import list_subjects, random_questions, save_attempt
        from models.user_model import create_user, find_by_identity
        from werkzeug.security import generate_password_hash

        with app.app_context():
            user_id = create_user(
                'test_student',
                'test@student.local',
                generate_password_hash('password123'),
            )
            assert find_by_identity('test_student')['id'] == user_id

            profile = add_exp(user_id, 20)
            assert profile['exp'] == 20 and profile['level'] == 1

            exam_id = create_exam(user_id, 'Toán', '2099-12-20', 6, 8, 60)
            add_topics(exam_id, ['Hàm số', 'Xác suất'])
            assert calculate_progress(exam_id, user_id) == 0

            questions = random_questions('Toán', 'Hàm số', 2)
            assert len(questions) > 0
            save_attempt(user_id, 'Toán', 'Hàm số', len(questions), 1, 5.0, 30)

            books = list_books(subject='Toán')
            assert len(books) > 0 and get_book(books[0]['id']) is not None

        with app.test_client() as client:
            homepage = client.get('/')
            assert homepage.status_code == 200
            assert b'Li\xc3\xaan h\xe1\xbb\x87 v\xe1\xbb\x9bi ch\xc3\xbang t\xc3\xb4i' in homepage.data
            assert b'home-section-menu' not in homepage.data
            for footer_text in (
                'Study Quest – Smart Exam Planner',
                'Dự án Tin học lớp 12A1 Hoàng Diệu',
                'Liên hệ: 12A1 Hoàng Diệu',
                '© 2026 Study Quest. Bản quyền thuộc về nhóm thực hiện.',
            ):
                assert footer_text.encode('utf-8') in homepage.data
            with client.session_transaction() as browser_session:
                csrf_token = browser_session['contact_csrf']

            csrf_response = client.post(
                '/contact',
                data={
                    'name': 'Nguyễn An',
                    'email': 'an@example.com',
                    'subject': 'Báo lỗi',
                    'message': 'Nội dung kiểm tra',
                },
            )
            assert csrf_response.status_code == 302

            empty_response = client.post(
                '/contact',
                data={'csrf_token': csrf_token, 'name': '  ', 'email': '', 'subject': '', 'message': ''},
            )
            assert empty_response.status_code == 400

            invalid_email_response = client.post(
                '/contact',
                data={
                    'csrf_token': csrf_token,
                    'name': '<script>alert(1)</script>',
                    'email': 'not-an-email',
                    'subject': 'Báo lỗi',
                    'message': 'Nội dung kiểm tra',
                },
            )
            assert invalid_email_response.status_code == 400
            assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in invalid_email_response.data

            oversized_response = client.post(
                '/contact',
                data={
                    'csrf_token': csrf_token,
                    'name': 'Nguyễn An',
                    'email': 'an@example.com',
                    'subject': 'Góp ý về website',
                    'message': 'x' * 2001,
                },
            )
            assert oversized_response.status_code == 400

            success_response = client.post(
                '/contact',
                data={
                    'csrf_token': csrf_token,
                    'name': '  Nguyễn An  ',
                    'email': '  an@example.com  ',
                    'subject': 'Báo lỗi',
                    'message': '  Nội dung kiểm tra  ',
                },
                follow_redirects=True,
            )
            assert success_response.status_code == 200
            assert 'Đã gửi lời nhắn thành công.'.encode('utf-8') in success_response.data
            assert b'data-cooldown="15" disabled' in success_response.data

            with client.session_transaction() as browser_session:
                csrf_token = browser_session['contact_csrf']
            cooldown_response = client.post(
                '/contact',
                data={
                    'csrf_token': csrf_token,
                    'name': 'Nguyễn An',
                    'email': 'an@example.com',
                    'subject': 'Báo lỗi',
                    'message': 'Gửi lại quá sớm',
                },
            )
            assert cooldown_response.status_code == 429
            assert 'gửi lời nhắn tiếp theo sau'.encode('utf-8') in cooldown_response.data

            with client.session_transaction() as browser_session:
                browser_session['contact_last_sent'] = time.time() - 16
            next_homepage = client.get('/')
            assert next_homepage.status_code == 200
            assert b'data-cooldown="0" >G\xe1\xbb\xadi l\xe1\xbb\x9di nh\xe1\xba\xafn</button>' in next_homepage.data
            with client.session_transaction() as browser_session:
                csrf_token = browser_session['contact_csrf']
            next_success = client.post(
                '/contact',
                data={
                    'csrf_token': csrf_token,
                    'name': 'Nguyễn An',
                    'email': 'an@example.com',
                    'subject': 'Góp ý về website',
                    'message': 'Có thể gửi lại sau thời gian chờ',
                },
                follow_redirects=True,
            )
            assert next_success.status_code == 200
            assert 'Đã gửi lời nhắn thành công.'.encode('utf-8') in next_success.data

        with app.app_context():
            saved_count = database.get_db().execute(
                'SELECT COUNT(*) FROM contact_messages'
            ).fetchone()[0]
            saved_message = database.get_db().execute(
                'SELECT name, email, subject, message FROM contact_messages'
            ).fetchone()
            assert saved_count == 2
            assert tuple(saved_message) == (
                'Nguyễn An',
                'an@example.com',
                'Báo lỗi',
                'Nội dung kiểm tra',
            )

        with app.test_client() as client:
            anonymous_response = client.get('/admin/contact-messages')
            assert anonymous_response.status_code == 302

            with client.session_transaction() as browser_session:
                browser_session['user_id'] = user_id
            non_admin_response = client.get('/admin/contact-messages')
            assert non_admin_response.status_code == 302

            with app.app_context():
                database.get_db().execute(
                    'UPDATE users SET role = ? WHERE id = ?',
                    ('admin', user_id),
                )
                database.get_db().commit()
            admin_response = client.get('/admin/contact-messages')
            assert admin_response.status_code == 200
            assert 'Lời nhắn liên hệ'.encode('utf-8') in admin_response.data
            assert 'Nội dung kiểm tra'.encode('utf-8') in admin_response.data
            assert 'href="/admin/contact-messages">Lời nhắn</a>'.encode('utf-8') in admin_response.data

        print('ALL BACKEND TESTS PASSED')
        print('- SQLite schema: OK')
        print('- User/Profile/EXP: OK')
        print('- Planner model: OK')
        print('- Quiz model: OK')
        print('- Library model: OK')
        print('- Contact form validation, CSRF, and storage: OK')
        print('- Admin-only contact inbox: OK')
    finally:
        database.DATABASE = old_database
        temp_dir.cleanup()


if __name__ == '__main__':
    main()
