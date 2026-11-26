@echo off
chcp 65001 >nul
title Suivi Budgétaire
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo  Python n'est pas installe sur ce PC.
    echo  Installez-le depuis https://www.python.org/downloads/
    echo  En cochant "Add Python to PATH" pendant l'installation,
    echo  puis relancez ce fichier.
    echo.
    pause
    exit /b 1
)

if not exist .venv (
    echo Premiere lancement : installation en cours...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo.
echo  Suivi Budgetaire demarre sur http://127.0.0.1:8000
echo  Fermez cette fenetre pour arreter l'application.
echo.
start "" "http://127.0.0.1:8000"
python app.py
