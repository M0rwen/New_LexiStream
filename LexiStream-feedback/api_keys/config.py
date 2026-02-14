import os
from dotenv import load_dotenv
load_dotenv()

# Google API Configuration
GOOGLE_API_KEY = "gen-lang-client-0550006478"

# Flask Configuration
SECRET_KEY = "lexistream-secret-key-2026-change-in-production"

# Database: MySQL only. Set in .env or environment:
#   LEXISTREAM_MYSQL_URI=mysql+pymysql://user:password@host/database
SQLALCHEMY_DATABASE_URI = os.getenv(
    "LEXISTREAM_MYSQL_URI",
    "mysql+pymysql://lexi_user:lexi_password@localhost/lexistream"
)

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Cohere (for AI feedback on recordings). Set COHERE_API_KEY in .env or environment.
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

# Application Settings
UPLOAD_FOLDER = "uploads"
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'flac', 'webm'}
