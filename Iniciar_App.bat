@echo off
title Real Estate Scraper & AI Extractor
cd /d "%~dp0"

echo ===================================================
echo   Iniciando Real Estate AI Extractor...
echo ===================================================

if exist ".venv\Scripts\python.exe" (
    echo [OK] Ambiente virtual detectado (.venv)
    ".venv\Scripts\python.exe" run.py
) else (
    echo [AVISO] .venv nao encontrado. Usando Python do sistema...
    python run.py
)

pause
