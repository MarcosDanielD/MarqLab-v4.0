@echo off
title Criar Atalho na Area de Trabalho - Marq Lab
color 0B
echo ==============================================================
echo           CRIAR ATALHO DO MARQ LAB NA AREA DE TRABALHO
echo ==============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\criar_atalho.ps1"

echo.
echo ==============================================================
echo Pronto! O atalho 'Marq Lab' foi criado na Area de Trabalho.
echo Agora basta dar dois cliques no icone para abrir o sistema!
echo ==============================================================
echo.
pause
