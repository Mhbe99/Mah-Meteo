# 🚀 MétéoFlux SaaS — Guide Démarrage

## Installation

### 1. Installer les dépendances

```bash
pip install -r requirements_saas.txt
```

### 2. Configurer .env

Le fichier `.env` contient des variables pour la SaaS:

```env
SECRET_KEY=your-super-secret-key-change-this-in-production
TOMTOM_API_KEY=  # Optionnel — laisser vide pour désactiver trafic
```

⚠️ **Important** : Changer `SECRET_KEY` en production (min 64 caractères aléatoires)

### 3. Lancer l'application

```bash
cd meteo_saas/backend
uvicorn main:app --reload --port 8000
```

L'app démarre sur http://localhost:8000

## 🔐 Authentification

### Données de test

```
Utilisateur : geodis-lemeux
Mot de passe : demo1234
```

(Ces données viennent de `data/clients.json`)

### Flux de connexion

1. Utilisateur remplit login/password
2. POST `/auth/login` retourne JWT
3. JWT stocké dans `localStorage`
4. Routes API nécessitent le JWT en header : `Authorization: Bearer <token>`
5. Expiration : 24h

## 📊 Routes API

### Authentification
- **POST /auth/login** — Obtenir un token JWT

### Météo
- **GET /api/meteo/{client_id}** — Données actuelles
- **GET /api/previsions/{client_id}** — Prévisions 5 jours
- **GET /api/zones/{client_id}** — Liste les zones du client

### Alertes
- **GET /api/alertes/{client_id}** — Historique alertes

### Trafic
- **GET /api/trafic/{client_id}** — Incidents trafic (TomTom)

### Santé
- **GET /health** — Vérifier que l'app tourne

### Frontend
- **GET /** — Retourne le dashboard HTML

## 🗄️ Base de données

SQLite : `meteo_saas.db` (créée automatiquement au démarrage)

Tables :
- `clients` — Comptes utilisateurs
- `zones` — Zones météo (sites + voisins)
- `meteo_snapshot` — Historique données météo
- `alertes_log` — Journal des alertes
- `trafic_incidents` — Historique incidents trafic

## 🌍 Variables d'environnement

```env
# Email (existant)
GMAIL_PASSWORD=...
SENDER_EMAIL=...
RECEIVER_EMAILS=...

# SaaS JWT
SECRET_KEY=your-secret-key

# Trafic (optionnel)
TOMTOM_API_KEY=  # Laisser vide = fonction désactivée
```

## 📝 Notes sur les données

### Pollution (AQI)
- AQI = indice de pollution de l'air (Air Quality Index), sur une echelle 0-100
- Dans l'interface, la colonne "Pollution (AQI)" correspond a ce niveau de pollution
- Les emails d'alerte pollution sont actuellement envoyes pour les sites GEODIS (pas les voisins)

### Méteo
- Récupère en temps réel desde Open-Meteo (gratuit)
- Snapshots sauvegardés en base
- Prévisions 5 jours

### Alertes
- Archivées depuis `exports/alertes_historique.json` (système legacy)
- Sauvegardées aussi en base `alertes_log`

### Trafic
- Données depuis API TomTom Traffic
- Nécessite une clé API (gratuit tier disponible)
- Si TOMTOM_API_KEY vide → données indisponibles (pas d'erreur)

## 🔧 Développement

### CORS

Actuellement activé pour `http://localhost:8000` (développement).

À changer en prod :
```python
allow_origins=["https://mondomaine.fr"]
```

### Logs

Tous les logs print() vont dans le terminal uvicorn.

### Structure

```
meteo_saas/
├── backend/
│   ├── main.py         # Routes FastAPI
│   ├── auth.py         # JWT + auth
│   ├── database.py     # Modèles SQLAlchemy
│   ├── models.py       # Schémas Pydantic
│   ├── clients.py      # Logique métier
│   └── trafic.py       # API TomTom
├── frontend/
│   └── dashboard.html  # Interface unique
├── data/
│   └── clients.json    # Données clients
└── meteo_saas.db       # Base SQLite (générée)
```

## 🐛 Troubleshooting

### "CORS error"
→ Vérifier que `allow_origins` contient le domaine du front

### "Token invalide"
→ Vérifier que JWT dans localStorage n'a pas expiré (24h)
→ Re-login si expiré

### "Aucun incident trafic"
→ TOMTOM_API_KEY n'est pas configurée → normal (pas d'erreur)

### "Port 8000 déjà utilisé"
→ Utiliser un autre port : `uvicorn main:app --port 8001`

## 🚀 Déploiement

Pour la production :

1. **Générer une vraie SECRET_KEY** (64 chars)
2. **Obtenir une clé TomTom API** pour le trafic
3. **Passer de SQLite à PostgreSQL** (recommandé)
4. **Utiliser HTTPS**
5. **Héberger sur** : Render, Railway, Heroku, DigitalOcean, etc.

---

**Questions ?** Consulter les docstrings des fonctions Python ou la section "Routes API" ci-dessus.
