"""Smoke test cho phần Admin 2.
Chạy: python test_backend.py
Script dùng database tạm, không làm thay đổi database.db thật.
"""
import os
import tempfile
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

        print('ALL BACKEND TESTS PASSED')
        print('- SQLite schema: OK')
        print('- User/Profile/EXP: OK')
        print('- Planner model: OK')
        print('- Quiz model: OK')
        print('- Library model: OK')
    finally:
        database.DATABASE = old_database
        temp_dir.cleanup()


if __name__ == '__main__':
    main()
