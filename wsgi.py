"""
Production WSGI Entrypoint for Marq Lab.
Run with Gunicorn (Linux VPS) or Waitress/Python (Windows Local).

Example Gunicorn command:
    gunicorn --workers 1 --threads 8 --timeout 300 --bind 127.0.0.1:5000 wsgi:application
"""

import os
import sys

# Ensure app directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import banco_dados
from app import app as application

# Ensure database tables and WAL journal mode are initialized on startup
banco_dados.init_db()

if __name__ == "__main__":
    print("Iniciando Marq Lab em http://127.0.0.1:5000 ...")
    application.run(host="0.0.0.0", port=5000, debug=False)
