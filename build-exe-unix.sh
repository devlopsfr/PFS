#!/usr/bin/env bash
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 n'est pas installé."
    exit 1
fi

if [ ! -d .venv-build ]; then
    python3 -m venv .venv-build
fi
source .venv-build/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt pyinstaller

echo "Construction de l'exécutable (peut prendre quelques minutes)..."
pyinstaller --clean --noconfirm --onefile --name SuiviBudgetaire \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --collect-submodules flask \
    app.py

if [ -f dist/SuiviBudgetaire ]; then
    echo ""
    echo " Terminé : dist/SuiviBudgetaire"
    echo " Rendez-le exécutable (chmod +x) puis lancez-le ;"
    echo " l'application s'ouvre dans votre navigateur."
else
    echo "La construction a échoué."
fi
