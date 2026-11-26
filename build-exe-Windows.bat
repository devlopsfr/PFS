@echo off
chcp 65001 >nul
title Construction de l'exécutable - Suivi Budgétaire
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python n'est pas installe. Voir Lancer-Windows.bat
    pause
    exit /b 1
)

if not exist .venv-build python -m venv .venv-build
call .venv-build\Scripts\activate.bat
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt pyinstaller

echo Construction de l'executable (peut prendre quelques minutes)...
pyinstaller --clean --noconfirm --onefile --name SuiviBudgetaire ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --collect-submodules flask ^
    app.py

if exist dist\SuiviBudgetaire.exe (
    echo.
    echo  Termine : dist\SuiviBudgetaire.exe
    echo  Copiez ce fichier ou vous voulez, double-cliquez dessus,
    echo  l'application s'ouvre dans votre navigateur.
    echo  Les donnees sont enregistrees dans un dossier "data" a cote.
) else (
    echo La construction a echoue.
)
pause
