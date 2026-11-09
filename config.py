import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')
SECRET_KEY = os.environ.get('SECRET_KEY', 'studyquest-dev-secret-change-me')
