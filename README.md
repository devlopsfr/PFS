# Suivi Budgétaire

Application web de suivi budgétaire multi-clients pour vos projets en régie :
budget en jours (UO), taux journalier, consommation mensuelle, soldes et
alertes de dépassement. Conçue pour être auto-hébergée sur votre serveur avec
Docker.

## Fonctionnalités

- Multi-clients (THALES, etc.) et multi-projets
- Budget en jours (UO) et taux journalier €/j → montants en € calculés
- Consommation mensuelle par projet (jours), soldes et alertes de dépassement
- Tableau de bord : KPI globaux, graphique mensuel, suivi par client, projets en alerte
- **Import de vos fichiers Excel existants** (feuilles de type « Project Financial Sheet »)
- Interface en français, responsive (Bootstrap 5)

## Utilisation sur votre PC (sans Docker)

### Lancement simple (Python requis)

- **Windows** : double-cliquez sur `Lancer-Windows.bat`
- **macOS / Linux** : `./lancer-mac-linux.sh`

Au premier lancement, l'environnement Python est créé et les dépendances
installées automatiquement, puis le navigateur s'ouvre sur
`http://127.0.0.1:8000`. Les données sont stockées dans `data/budget.db`
à côté de l'application.

Si Python n'est pas installé : https://www.python.org/downloads/
(cochez « Add Python to PATH » sur Windows).

### Exécutable autonome (optionnel)

Pour générer un vrai exécutable unique (`.exe` sur Windows) ne nécessitant
plus Python ni installation :

- **Windows** : double-cliquez sur `build-exe-Windows.bat`
- **macOS / Linux** : `./build-exe-unix.sh`

L'exécutable est produit dans `dist/` — copiez-le où vous voulez et
double-cliquez dessus.

## Démarrage rapide (Docker, pour un serveur)

```bash
docker compose up -d --build
```

L'application est disponible sur `http://localhost:8000` (le port n'écoute que
sur 127.0.0.1 : placez un reverse proxy Nginx/Caddy/Traefik devant pour y
accéder depuis l'extérieur, avec HTTPS).

## Démarrage sans Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py          # http://127.0.0.1:8000
```

## Import de vos données

1. Page **Import Excel** → déposez votre fichier `.xlsx` (ex. `THALES - Project Financial Sheet.xlsx`)
2. Le nom du client est déduit du nom du fichier, ou saisissez-le manuellement
3. Renseignez le taux journalier par défaut (utilisé pour les feuilles sans taux explicite)
4. Vérifiez les projets importés et ajustez taux/budgets si besoin — tout est éditable

Les doublons entre feuilles d'un même fichier sont fusionnés ; un ré-import du
même fichier ne crée pas de doublons (mise à jour des valeurs existantes).

## Sécurité

- **Authentification HTTP Basic** optionnelle : définissez `ADMIN_USER` et
  `ADMIN_PASSWORD` (via un fichier `.env` à côté du `docker-compose.yml`)
- Changez `SECRET_KEY` en production
- L'application est prévue pour tourner derrière un reverse proxy avec HTTPS
  (Let's Encrypt via Certbot ou Caddy)
- Données dans SQLite (`data/budget.db`) : pensez à sauvegarder ce fichier
  (ex. cron quotidien avec `sqlite3 data/budget.db ".backup ..."`)

## Structure

```
app.py           Application Flask (routes, import, auth optionnelle)
models.py        Modèles : Client, Project, Entry (SQLAlchemy / SQLite)
importer.py      Lecteur des feuilles Excel existantes
templates/       Interface Jinja2
static/          Styles
```
