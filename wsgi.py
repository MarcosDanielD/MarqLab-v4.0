"""
Production WSGI Entrypoint for Marq Lab.
Run with Gunicorn (Linux VPS) or Waitress (Windows Server).

Example Gunicorn command:
    gunicorn --workers 1 --threads 8 --timeout 300 --bind 127.0.0.1:5000 wsgi:application
"""

import database
from app import app as application

# Ensure database tables and WAL journal mode are initialized on startup
database.init_db()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)
