@echo off
setlocal
cd /d "%~dp0"
title Marq Lab - Prospeccao Ativa B2B
color 0B

echo ==============================================================
echo                 MARQ LAB - PROSPECCAO ATIVA B2B
echo         Robo de Captacao e Venda de Landing Pages (R$ 1.000)
echo ==============================================================
echo.

:: 1. Sincroniza atualizacoes de codigo com o GitHub se o Git estiver disponivel
where git >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Sincronizando codigo com o GitHub...
    git pull origin main --quiet
)

:: 2. Valida ou configura o ambiente virtual (.venv)
set "VENV_PY=.\.venv\Scripts\python.exe"
set "VALID_ENV=0"

if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import flask, playwright" >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "VALID_ENV=1"
    )
)

if "%VALID_ENV%"=="0" (
    echo [INFO] Configurando ou reparando ambiente local... Aguarde...
    echo.

    :: Detecta o executavel Python no sistema
    set "SYS_PY="
    py -3 -c "import sys" >nul 2>nul && set "SYS_PY=py -3"
    if not defined SYS_PY (
        python -c "import sys" >nul 2>nul && set "SYS_PY=python"
    )
    if not defined SYS_PY (
        if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "SYS_PY=%LocalAppData%\Programs\Python\Python314\python.exe"
        if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "SYS_PY=%LocalAppData%\Programs\Python\Python313\python.exe"
        if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "SYS_PY=%LocalAppData%\Programs\Python\Python312\python.exe"
        if exist "C:\Program Files\Python314\python.exe" set "SYS_PY=C:\Program Files\Python314\python.exe"
        if exist "C:\Program Files\Python313\python.exe" set "SYS_PY=C:\Program Files\Python313\python.exe"
        if exist "C:\Program Files\Python312\python.exe" set "SYS_PY=C:\Program Files\Python312\python.exe"
    )

    if not defined SYS_PY (
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

    if not exist ".venv" (
        %SYS_PY% -m venv .venv
    )
    echo [INFO] Instalando dependencias necessarias...
    "%VENV_PY%" -m pip install -r requirements.txt --quiet
    echo [INFO] Instalando navegador Chromium para prospeccao automatizada...
    "%VENV_PY%" -m playwright install chromium
    echo.
    echo [OK] Ambiente configurado com sucesso!
    echo.
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

"%VENV_PY%" wsgi.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [AVISO] O processo foi encerrado com codigo %ERRORLEVEL%.
    pause
)
