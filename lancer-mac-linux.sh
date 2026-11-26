#!/usr/bin/env bash
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo ""
    echo " Python 3 n'est pas installé."
    echo " Installez-le depuis https://www.python.org/downloads/"
    echo " puis relancez ce script."
    echo ""
    read -r -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Premier lancement : installation en cours..."
    python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo ""
echo " Suivi Budgétaire démarré sur http://127.0.0.1:8000"
echo " Ctrl+C pour arrêter l'application."
echo ""
( sleep 2; xdg-open http://127.0.0.1:8000 >/dev/null 2>&1 || open http://127.0.0.1:8000 >/dev/null 2>&1 ) &
python app.py
