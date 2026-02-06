import os

# Google API Configuration
GOOGLE_API_KEY = "gen-lang-client-0550006478"

# Flask Configuration
SECRET_KEY = "lexistream-secret-key-2026-change-in-production"

# Default: use SQLite (simple, file-based)
DEFAULT_SQLITE_URI = "sqlite:///lexistream.db"

# Optional: switch to MySQL by setting environment variables
#   LEXISTREAM_USE_MYSQL=1
#   LEXISTREAM_MYSQL_URI=mysql+pymysql://lexi_user:lexi_password@localhost/lexistream
USE_MYSQL = os.getenv("LEXISTREAM_USE_MYSQL", "0") == "1"

if USE_MYSQL:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "LEXISTREAM_MYSQL_URI",
        "mysql+pymysql://lexi_user:lexi_password@localhost/lexistream"
    )
else:
    SQLALCHEMY_DATABASE_URI = DEFAULT_SQLITE_URI

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Application Settings
UPLOAD_FOLDER = "uploads"
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'flac'}
