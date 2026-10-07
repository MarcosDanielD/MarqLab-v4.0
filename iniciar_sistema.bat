@echo off
title Marq Lab - Lead Generation & Vendas
color 0B
echo ==============================================================
echo                 MARQ LAB - PROSPECCAO ATIVA B2B
echo         Robo de Captacao e Venda de Landing Pages (R$ 1.000)
echo ==============================================================
echo.

:: Verifica se a pasta do ambiente virtual existe
if not exist ".venv" (
    echo [INFO] Primeiro uso detectado! Criando ambiente virtual Python...
    python -m venv .venv
    call .\.venv\Scripts\activate.bat
    echo [INFO] Instalando dependencias necessarias...
    pip install -r requirements.txt
) else (
    call .\.venv\Scripts\activate.bat
)

echo.
echo [1/2] Servidor Web iniciando na porta 5000...
echo.
echo   * Acesso Local:          http://127.0.0.1:5000
echo   * Acesso na Rede Local:  Use o IP deste computador:5000
echo.

echo [2/2] Abrindo painel no navegador padrao...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:5000

echo.
echo ==============================================================
echo Marq Lab em execucao! Para encerrar, feche esta janela.
echo ==============================================================
echo.
python app.py
pause
