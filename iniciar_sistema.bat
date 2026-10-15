@echo off
title Marq Lab - Prospeccao Ativa B2B
color 0B
echo ==============================================================
echo                 MARQ LAB - PROSPECCAO ATIVA B2B
echo         Robo de Captacao e Venda de Landing Pages (R$ 1.000)
echo ==============================================================
echo.

:: 1. Verifica se o Python esta instalado e no PATH
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    color 0C
    echo [ERRO] O Python nao foi detectado no seu computador!
    echo.
    echo Para executar o Marq Lab, por favor instale o Python:
    echo   1. Baixe o instalador em: https://www.python.org/downloads/
    echo   2. IMPORTANTE: Durante a instalacao, marque a opcao:
    echo      [X] "Add Python to PATH"
    echo   3. Apos instalar, execute este arquivo novamente.
    echo.
    pause
    exit /b 1
)

:: 2. Verifica atualizacoes de codigo no GitHub
where git >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Sincronizando codigo com o GitHub...
    git pull origin main --quiet
)

:: 3. Verifica se o ambiente virtual existe
if not exist ".venv" (
    echo [INFO] Primeiro uso detectado neste computador!
    echo [INFO] Configurando ambiente local... Aguarde alguns instantes...
    echo.
    python -m venv .venv
    call .\.venv\Scripts\activate.bat
    echo [INFO] Instalando bibliotecas necessarias...
    pip install -r requirements.txt --quiet
    echo [INFO] Instalando navegador Chromium para o robo de prospeccao...
    python -m playwright install chromium
    echo.
    echo [OK] Ambiente configurado com sucesso!
    echo.
) else (
    call .\.venv\Scripts\activate.bat
)

echo.
echo ==============================================================
echo [OK] Servidor iniciando em Modo Aplicativo...
echo.
echo   * URL Local: http://127.0.0.1:5000
echo   * A janela do aplicativo sera aberta automaticamente.
echo   * Para encerrar o sistema, basta fechar esta janela.
echo ==============================================================
echo.

python wsgi.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [AVISO] O processo foi encerrado.
    pause
)
