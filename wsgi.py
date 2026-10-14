"""
Production WSGI Entrypoint for Marq Lab.
Run with Gunicorn (Linux VPS) or Waitress/Python (Windows Local Desktop App).

Example Gunicorn command:
    gunicorn --workers 1 --threads 8 --timeout 300 --bind 127.0.0.1:5000 wsgi:application
"""

import os
import sys
import time
import threading
import subprocess
import webbrowser

# Ensure app directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import banco_dados
from app import app as application

# Ensure database tables and WAL journal mode are initialized on startup
banco_dados.init_db()


def _abrir_janela_aplicativo():
    """Abre o painel em uma janela limpa e dedicada (Modo App do Chrome/Edge)."""
    time.sleep(1.2)  # Aguarda o socket do Flask subir
    url = "http://127.0.0.1:5000"

    candidatos = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]

    for navegador in candidatos:
        if os.path.exists(navegador):
            try:
                subprocess.Popen([
                    navegador,
                    f"--app={url}",
                    "--window-size=1440,920",
                    "--window-position=50,50"
                ])
                return
            except Exception:
                pass

    # Fallback para o navegador padrao
    webbrowser.open(url)


if __name__ == "__main__":
    print("==============================================================")
    print("              MARQ LAB - PROSPECCAO ATIVA B2B                 ")
    print("==============================================================")
    print("Iniciando servidor local em http://127.0.0.1:5000 ...")

    # Inicia a janela do aplicativo no Windows em modo independente
    if os.environ.get("MARQ_NO_BROWSER") != "1":
        threading.Thread(target=_abrir_janela_aplicativo, daemon=True).start()

    application.run(host="0.0.0.0", port=5000, debug=False)
