# 🌐 Architecture SaaS MétéoFlux

## 📋 Vue d'ensemble

L'application SaaS ajoute une **couche multi-clients** par-dessus le système météo existant (meteo_open.py, rapport_hebdomadaire.py).

- **Backend** : FastAPI avec JWT + SQLAlchemy
- **Frontend** : Single-page app HTML/JS avec Leaflet.js
- **DB** : SQLite (dev), PostgreSQL (prod)
- **Auth** : JWT 24h, JWT renouvelable

---

## 🏗️ Architecture générale

```
┌─────────────────────────────────────────────────────────────┐
│                    UTILISATEUR FINAL                          │
│              (Navigateur → dashboard.html)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
    [LOGIN]                           [DASHBOARD]
    POST /auth/login                  Onglets 1-5:
    ↓                                 - Temps réel
    JWT TOKEN                         - Carte
    (localStorage)                    - Prévisions
                                      - Trafic
                                      - Alertes
                                            │
        ┌───────────────────────────────────┴───────────────────┐
        │                                                        │
    [BACKEND FastAPI]                                      [DATABASES]
    ├── auth.py                                           ├─ meteo_saas.db
    │   ├─ create_token()             ←──────JWT───→      │   ├─ clients
    │   ├─ verify_token()                                 │   ├─ zones
    │   └─ get_current_client()                           │   ├─ meteo_snapshot
    │                                                     │   ├─ alertes_log
    ├── main.py (Routes)                                 │   └─ trafic_incidents
    │   ├─ POST /auth/login           ←────────────→    │
    │   ├─ GET /api/meteo/{id}                          │
    │   ├─ GET /api/previsions/{id}                     │
    │   ├─ GET /api/alertes/{id}                        │
    │   ├─ GET /api/trafic/{id}                         │
    │   ├─ GET /api/zones/{id}                          │
    │   └─ GET /                                        │
    │                                                    │
    ├── database.py                                      │
    │   ├─ Client model                                 │
    │   ├─ Zone model                                   │
    │   ├─ MeteoSnapshot model                          │
    │   ├─ AlerteLog model                              │
    │   ├─ TrafficIncident model                        │
    │   ├─ init_db()                                    │
    │   └─ init_clients_from_json()                     │
    │                                                    │
    ├── clients.py (Métier)                             │
    │   ├─ get_meteo_actuelle()                         │
    │   ├─ get_previsions()                             │
    │   ├─ get_alertes()                                │
    │   ├─ save_meteo_snapshot()                        │
    │   └─ get_zones()                                  │
    │                                                    │
    ├── trafic.py (API TomTom)                          │
    │   └─ get_incidents()                              │
    │                                                    │
    └── models.py (Pydantic)                            │
        ├─ LoginRequest                                 │
        ├─ TokenResponse                                │
        ├─ ZoneMeteo                                    │
        ├─ PrevisionJour                                │
        └─ TrafficIncident                              │
                                                        │
        ┌───────────────────────────────────────────────┴───┐
        │                                                   │
        └─→ [DONNÉES EXISTANTES]                           │
            ├─ exports/alertes_historique.json            │
            ├─ exports/last_alerts.json                   │
            ├─ meteo_open.py (runner)                     │
            ├─ rapport_hebdomadaire.py                    │
            └─ auto_meteo_loop.py                         │
                └─ Tourne indépendamment (15 min + lundi) │
```

---

## 🔐 Flux authentification

```
Utilisateur saisit : username + password
            ↓
     POST /auth/login
            ↓
    [auth.py → verify_password(user.password_hash)]
            ↓
        JWT Token créé (24h)
        {
            "client_id": 1,
            "username": "geodis-lemeux",
            "exp": <24h_from_now>
        }
            ↓
    JSON: { access_token, token_type, client_id, company_name }
            ↓
    localStorage.setItem("token", ...)
            ↓
    Toutes requêtes API : 
    Authorization: Bearer <token>
            ↓
    get_current_client() décrypte et retourne client_id
            ↓
    Vérifier : client_id de la route == client_id du token
    (sinon 403 Forbidden)
```

---

## 📊 Structure données

### Clients (Multi-tenant)
```python
class Client:
    id              # PK
    username        # Unique login
    password_hash   # Hash bcrypt
    company_name    # Ex: "GEODIS — Le Meux"
    email
    plan            # "free", "pro", "enterprise"
    active          # Booléen
```

### Zones (Héritées)
```python
class Zone:
    id              # PK
    client_id       # FK → Client (isolation)
    name            # "Le Meux", "Compiègne"
    lat, lon        # Coordonnées
    type            # "site" ou "voisin"
```

### Snapshots météo
```python
class MeteoSnapshot:
    id
    zone_id         # FK → Zone
    timestamp       # Horodatage
    temperature
    windspeed
    wind_direction
    precipitation
    cloudcover
    uv_index
    risques         # Ex: "❄️ Verglas | 💨 Vent fort"
    ciel            # Ex: "🌧️"
```

### Alertes
```python
class AlerteLog:
    id
    client_id       # FK → Client
    zone_name
    timestamp
    type_alerte     # "verglas", "vent_fort", "pluie", "uv"
    valeur          # Ex: "0°C"
    message
```

### Incidents trafic
```python
class TrafficIncident:
    id
    client_id       # FK → Client
    timestamp
    route           # Ex: "A1, E5"
    description
    severity        # "low", "med", "high"
    delay_minutes
    lat, lon        # Position
```

---

## 🎨 Frontend — Structure

### 1. Écran LOGIN
- Form username/password
- Appel : `POST /auth/login`
- Stocke : JWT + client_id + company_name dans localStorage
- Redirect → Dashboard

### 2. Écran DASHBOARD
Sidebar gauche (280px) :
- Logo "MétéoFlux" animé
- Badge entreprise
- Cards zones (sites seulement)
- Alertes actives (top 2)

Contenu central (5 onglets) :

**Onglet 1 : Temps réel**
- KPIs : Tmax, Vent max, Pluie, Nb alertes
- Tableau sites (zone, ciel, temp, vent, direction, pluie, UV, risques)
- Tableau voisins (même structure)

**Onglet 2 : Carte Leaflet.js**
- Points rouges = sites (rayon 7px)
- Points bleus = voisins (rayon 5px)
- Popup au clic : détails complète
- Zoom auto sur données

**Onglet 3 : Prévisions 5j**
- Grid par site
- 5 colonnes (jours)
- Tmin/Tmax, pluie, jour

**Onglet 4 : Trafic TomTom**
- KPIs : Incidents actifs, retard max, heure MAJ
- Tableau incidents : route, description, sévérité colorée, retard

**Onglet 5 : Historique alertes**
- 30 dernières
- Colonnes : date/heure, zone, type, valeur, message

---

## 🔄 Flux données

### 1. Données météo actuelles
```
Dashboard (onglet 1) 
    ↓
GET /api/meteo/{client_id} (avec JWT)
    ↓
[clients.py] get_meteo_actuelle()
    ↓
Requête DB : Zone + dernier MeteoSnapshot
    ↓
Retour : [{name, type, temp, wind, direction, ciel, risques, lat, lon, updated_at}]
```

### 2. Prévisions 5 jours
```
Dashboard (onglet 3)
    ↓
GET /api/previsions/{client_id}
    ↓
[clients.py] get_previsions()
    ↓
Pour chaque zone : appel Open-Meteo API
    ↓
Parse daily : temperature_2m_min/max, precipitation_sum, uv_index_max
    ↓
Retour : [{zone, jour, tmin, tmax, pluie, uv, risques}]
```

### 3. Alertes
```
Dashboard (sidebar + onglet 5)
    ↓
GET /api/alertes/{client_id}?limit=30
    ↓
[clients.py] get_alertes()
    ↓
Chercher dans AlerteLog (DB) 
    ↓
Si vide → lire exports/alertes_historique.json (legacy)
    ↓
Retour : [{zone_name, timestamp, type_alerte, valeur, message}]
```

### 4. Trafic
```
Dashboard (onglet 4)
    ↓
GET /api/trafic/{client_id}
    ↓
[trafic.py] get_incidents()
    ↓
Récupérer zones du client (sites uniquement)
    ↓
Calculer centre géo + bbox
    ↓
Appel API TomTom : https://api.tomtom.com/traffic/services/5/incidentDetails
    ↓
Parser : route, description, magnitude→severity, delay→minutes
    ↓
Sauvegarder en DB (historique)
    ↓
Retour : [{route, description, severity, delay_minutes, lat, lon}]
```

---

## 🚀 Démarrage application

### Dev
```bash
cd meteo_saas/backend
uvicorn main:app --reload --port 8000
```

Ouvrir http://localhost:8000 dans navigateur

### Prod
- Utiliser Gunicorn + Nginx
- PostgreSQL au lieu de SQLite
- Variables `.env` en secrets système
- HTTPS obligatoire
- CORS configuré pour domaine réel

---

## 🔗 Intégration avec système existant

L'app SaaS **n'interfère pas** avec les scripts existants :

- `meteo_open.py` → Tourne toutes les 15 min (indépendant)
  - Génère `exports/risques_meteo.xlsx`
  - Archive dans `exports/alertes_historique.json`
  - Mise à jour dashboards HTML

- `rapport_hebdomadaire.py` → Tourne lundi 08:00 (indépendant)
  - Envoie email avec Excel + prévisions
  - Génère `exports/rapport_hebdomadaire.xlsx`

- `auto_meteo_loop.py` → Orchestrateur (peut rester actif)

**La SaaS lit depuis ces données** :
- `exports/alertes_historique.json` (fallback alertes)
- Peut être liée à DB MeteoSnapshot pour historique futur

---

## ⚙️ Configuration

### `.env`
```env
# Existant (email)
GMAIL_PASSWORD=...
SENDER_EMAIL=...
RECEIVER_EMAILS=...

# SaaS JWT
SECRET_KEY=your-secret-key-64-chars-min

# TomTom Trafic (optionnel)
TOMTOM_API_KEY=  # Vide = désactivé
```

### `data/clients.json`
```json
{
  "clients": [
    {
      "username": "service-meteo",
      "password": "example-password",
      "company_name": "GEODIS",
      "email": "client@example.com",
      "plan": "pro",
      "zones": { "sites": [...], "voisins": [...] }
    }
  ]
}
```

Automatiquement chargé au démarrage via `init_clients_from_json()`.

---

## 🎯 Points clés

✅ **Isolation multi-client** : Chaque client voit seulement ses données (vérification client_id)
✅ **JWT stateless** : Pas de session stockée (scalable)
✅ **Résilience** : API externes (Open-Meteo, TomTom) gérées avec try/except
✅ **Single-page app** : Dashboard HTML autonome, localStorage, 15min refresh
✅ **Pas de dépendances CSS** : CSS natif → léger et portable
✅ **Compatible legacy** : Lit alertes_historique.json existant

---

## 📞 Support

Tous les fichiers sont commentés en français. Consulter docstrings pour détails.

Questions de structure → README.md racine
Questions API → routes main.py
Questions DB → database.py
Questions frontend → dashboard.html
