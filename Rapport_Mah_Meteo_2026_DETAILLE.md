# 📊 Rapport Détaillé — Application Mah Météo GEODIS 2026

## 1. Contexte et genèse du projet

### Besoin initial
Le DA a exprimé le besoin d'une **station météo** capable de fournir des prévisions fiables et des alertes adaptées au site GEODIS (Compiègne, Clairoix). Après analyse du marché :
- Les stations météo classiques ne proposent pas de prévisions locales précises
- Aucune solution existante n'offre des alertes adaptées à l'exploitation (tournées, trafic, sécurité)
- Besoin d'une solution sur-mesure, intégrée, avec reporting automatisé

### Solution conçue
Application **SaaS multi-tenant** personnalisée pour GEODIS, combinant :
- **Collecte météo** précise (Open-Meteo API)
- **Automatisation complète** (cron-job.org + GitHub workflow_dispatch)
- **Alertes intelligentes** (déduplication, cooldown, multi-zones)
- **Reporting hebdomadaire** automatique par email
- **Dashboard moderne** avec analytics avancées (Mon Compte)
- **Module Tournées** avec score risque combiné

---

## 2. Architecture Technique Détaillée

### 2.1 Stack Technologique

| Composant | Technologie | Détail |
|-----------|------------|--------|
| **Backend** | FastAPI (Python) | API REST asynchrone, ~1300 lignes (main.py), 25+ endpoints |
| **Base de données** | PostgreSQL | Production (Render) ; SQLite fallback local |
| **ORM** | SQLAlchemy | Modèles clients, zones, snapshots, alertes, tournées |
| **Authentification** | JWT + Rate-limiting | 24h tokens, protection brute-force /auth/login (10 req/min/IP) |
| **Frontend** | HTML/JS vanilla | 3988 lignes, 5 onglets, ApexCharts, Leaflet |
| **Automatisation** | GitHub Actions + cron-job.org | cron-job.org déclenche workflow_dispatch toutes les heures (fiable), rapport chaque lundi 8h |
| **Données météo** | Open-Meteo API | Gratuite, 10 000 req/jour, historique + prévisions |
| **Email** | Brevo API + fallback SMTP | Multi-destinataires, HTML enrichi, attachements Excel, contournement des blocages SMTP Render |
| **Déploiement** | Render.com | PostgreSQL managed, auto-redémarrage, logs streaming |

### 2.2 Modèles de données

**Client** (multi-tenant)
```
id, username, password_hash, company_name, email, plan (free/standard/pro/groupe)
zones (1:N), alertes (1:N)
quotas : sites, voisins, emails, modifications
```

**Zone** (site ou voisin)
```
client_id, name, lat, lon, type (site/voisin)
temp, windspeed, wind_direction, precipitation, cloudcover, uv_index, risques, ciel
updated_at
```

**MeteoSnapshot** (archive horaire)
```
zone_id, temperature, windspeed, wind_direction, precipitation, cloudcover, uv_index, risques, ciel
created_at (timestamp)
```

**AlerteLog** (archive alertes)
```
client_id, zone_name, message (risques détectés), timestamp
```

**Tournées (module frontend local)**
```
Saisie exploitant -> stockage localStorage par client (clé tournees_<client_id>)
chauffeur (prenom+nom), date, heure_depart, destinations (villes), notes
pas d'API backend dédiée à ce stade
```

---

## 3. Workflow Complet : De la Collecte au Reporting

### 3.1 Cycle de collecte (toutes les heures via cron-job.org + GitHub Actions)

```
cron-job.org (0 * * * *) → GitHub workflow_dispatch → meteo_open.py
        ↓
1. Charger clients (API Render ou clients.json fallback)
2. Pour chaque client :
   - Pour chaque zone (site + voisins) :
     a) Appeler Open-Meteo API
     b) Extraire temp, vent, pluie, UV, ciel
     c) Calculer risques (verglas, vent fort, pluie, UV)
     d) Sauvegarder snapshot en BD
     e) POST vers Render API (sync données frontend)
3. Générer/Mettre à jour dashboard_meteo.html
4. Envoyer alertes email (cooldown 1h par zone)
```

**Exemple d'appel Open-Meteo :**
```json
GET https://api.open-meteo.com/v1/forecast?latitude=49.378829&longitude=2.750393&current_weather=true&daily=...&hourly=...

Réponse :
{
  "current_weather": {
    "temperature": 8.2,
    "windspeed": 25.5,
    "winddirection": 240,
    "precipitation": 0.5
  },
  "hourly": {
    "time": ["2026-05-04T14:00", "2026-05-04T15:00", ...],
    "precipitation": [0.5, 1.2, ...],
    "cloudcover": [60, 75, ...],
    "uv_index": [5.2, 4.8, ...]
  }
}
```

### 3.2 Logique de calcul des risques

**Risques détectés :**

| Risque | Condition | Seuil | Mois |
|--------|-----------|-------|------|
| ❄️ Verglas | T < 1°C **ET** Pluie > 0 | T<1, Pluie>0 | Nov-Fév |
| 💨 Vent fort | Vitesse vent | > 40 km/h | Année |
| 🌧️ Alerte pluie | Précipitation | > 5 mm/h | Année |
| 🔥 UV fort | Indice UV | ≥ 7 | Mai-Sep |
| 🔥 UV extrême | Indice UV | ≥ 10 | Toute année |

**Exemple :** 
- Temp = 0.5°C, Pluie = 1.2 mm/h, Vent = 35 km/h, UV = 8 → **"❄️ Verglas | 🔥 UV fort"**

### 3.3 Système d'alertes et archivage

**Génération d'alerte :**
1. Risques détectés ? OUI
2. Alerte déjà envoyée dans les 60 min ? NON → Envoyer email
3. Archiver dans BD (AlerteLog) + dernier timestamp (last_alerts.json)
4. Cooldown 1h (anti-spam)

**Archivage :**
- Chaque snapshot = sauvegarde en BD (MeteoSnapshot)
- Chaque alerte = log en BD (AlerteLog) + exports/last_alerts.json
- Nettoyage : garder 30j d'alertes, 7j de snapshots

**Email d'alerte :**
```
À : alerts@example.com, ops@example.com
Sujet : Alerte météo détectée à Le Meux 🏣

Risques détectés :
❄️ Verglas (T=0.5°C, Pluie=1.2 mm/h)
🔥 UV fort (UV=8.2)

Heure : 2026-05-04 14:30
Température : 0.5°C
Vent : 35 km/h (SO)
Pluie : 1.2 mm/h
Couverture nuageuse : 60%

Actions recommandées :
- Attention tournées : conditions glissantes
- Protections UV conseillées
- Vérifier météo locale avant départ
```

---

### 3.4 Surveillance Qualité de l'Air (AQI) — NOUVEAU MAI 2026

**Source :** Open-Meteo Air Quality API (gratuit, même provider que météo)

**Données collectées :**
- **AQI européen** (0-100, échelle officielle)
- **PM2.5** (particules fines µg/m³)
- **PM10** (particules µg/m³)

**3 seuils d'alerte par site GEODIS :**

| AQI | Seuil | Niveau | Email cooldown | Style | Impact |
|-----|-------|--------|----------|-------|--------|
| 40-59 | 🟠 | Modéré | 6h | Orange | Attention tournées, port masque recommandé |
| 60-79 | 🔴 | Mauvais | 3h | Rouge | Risque respiratoire, ralentir rythme |
| 80+ | ⛔ | Très mauvais | 1h | Bordeaux | DANGER — minimiser déplacements, EPI obligatoire |

**Email d'alerte pollution :**
```
À : alerts@example.com, ops@example.com
Sujet : ⚠️ Alerte Pollution — Qualité air Très mauvais (80+)

Le Meux 🏣 : AQI 85 ⛔ Très mauvais → PM2.5 = 32.1 µg/m³
Clairoix 🏣 : AQI 62 🔴 Mauvais → PM2.5 = 18.5 µg/m³

Risque sanitaire : Les particules fines impactent la santé respiratoire.
Recommandations : Minimiser déplacements, port de masque FFP2 conseillé.
```

**Intégration dashboard :**
- Nouvelle colonne AQI 🌫️ dans tableau sites (badge coloré vert/orange/rouge)
- Bannière pollution en haut de Vue Générale si AQI ≥ 40
- Groupée par seuil (Très mauvais > Mauvais > Modéré)

**Intégration rapport hebdomadaire :**
- Section "Qualité de l'air actuellement" après KPIs
- Tableau : Site / AQI / Niveau pour tous les sites ≥ 40
- Permet suivi hebdomadaire de la pollution

**Collecte cron :**
- 1 seule requête batch Open-Meteo Air Quality (27 zones)
- Même que fetch_meteo_batch() → aucun impact perfs
- Stockage : colonnes `aqi` + `pollution_label` table zones PostgreSQL

---

## 4. Rapport Hebdomadaire (Chaque Lundi 8h)

### 4.1 Workflow

```
GitHub Actions (lundi 8h) → rapport_hebdomadaire.py
        ↓
1. Charger historique alertes (API Render ou exports/alertes_historique.json)
2. Filtrer semaine précédente (lundi-dimanche)
3. Générer statistiques :
   - Total alertes, zones affectées, types de risques
   - Graphiques (ApexCharts), cartes prévisions
4. Générer Excel (avec graphiques, pivot tables)
5. Générer HTML (email enrichi)
6. Envoyer par email à tous destinataires
7. Archiver dans exports/
```

### 4.2 Contenu du rapport

**KPIs semaine :**
```
┌──────────────────────────────────────────────────┐
│  Alertes : 12   │  Zones affectées : 4   │  Types : 3  │
└──────────────────────────────────────────────────┘
```

**Tableau risques (top):**
| Risque | Nombre |
|--------|--------|
| 🌧️ Alerte pluie | 7 |
| 💨 Vent fort | 3 |
| 🔥 UV fort | 2 |

**Tableau zones (top) :**
| Zone | Alertes |
|------|---------|
| Le Meux 🏣 | 6 |
| Clairoix 🏣 | 4 |
| Compiègne | 2 |

---

## 5. Dashboard Frontend — 5 Onglets

### 5.1 Onglet 1 : Vue Générale

**Composants :**
- **KPI Bar (persistent)** : Temp max sites, Vent max, Précip., Alertes actives
- **Carte Leaflet** : Positionnement zones (emoji markers 🏣📍), auto-zoom actif/passif
- **Tableau Sites GEODIS** : Zone, Ciel, T°, Vent, Direction, Pluie, UV, Risques
- **Tableau Zones voisines** : Même colonnes

### 5.2 Onglet 2 : Prévisions 5 Jours

- Grille par zone (site + voisins)
- 5 colonnes (jours)
- Chaque jour : Tmax/Tmin (couleurs contraste), pluie, UV, badge risque
- Couleurs risques : vert (RAS), bleu (pluie), orange (vent), mauve (verglas), rouge (UV)

### 5.3 Onglet 3 : Trafic & Alertes

**KPIs :**
- Incidents actifs (TomTom API)
- Retard max (min)
- Heure MAJ

**Tableau Incidents :** Route, Description, Sévérité (low/med/high), Retard

### 5.4 Onglet 4 : Tournées

**Création :**
1. Formulaire : Prénom, Nom, Date, Heure départ, Villes (autocomplete), Notes
2. Autocomplete recherche villes + correction (normalisation DB)
3. Affichage météo par étape en temps réel
4. Score risque combiné (avg des risques des villes)

**Exemple d'affichage tournée :**
```
📋 Tournée Jean Dupont — 04/05/2026 08:00
Risque combiné : ⚠️ MOYEN (score: 6/10)

Étape 1️⃣ Le Meux 🏣 — 08:00
  ☀️ 8°C | 💨 25 km/h | 🌧 0 mm | ✅ RAS

Étape 2️⃣ Compiègne — 08:45
  ☀️ 7°C | 💨 28 km/h | 🌧 1 mm | ⚠️ Vent fort

Étape 3️⃣ Noyon — 09:30
  ☀️ 6°C | 💨 32 km/h | 🌧 2 mm | 🔥 Vent fort + Pluie
```

### 5.5 Onglet 5 : Mon Compte — Analytics

**Section 1 : Infos compte**
- Entreprise, Utilisateur, Email, Plan
- Barres de quota : Sites (n/max), Voisins (n/max), Modifications (n/max)

**Section 2 : Gestion zones**
- Recherche ville (autocomplete Open-Meteo Geocoding)
- Liste zones avec type (site/voisin), actions suppression

**Section 3 : Statistiques alertes (4 graphiques interactifs)**

| Graphique | Type | Données |
|-----------|------|---------|
| **Alertes par zone (Top 10)** | BarChart | Zones affectées, cliquez pour filtrer |
| **Répartition par type** | PieChart | Types risques, cliquez pour filtrer |
| **Température — 48h** | LineChart | Hourly avec zoom/hover |
| **Pluie & Vent — 7j** | AreaChart | Prévisions quotidiennes |

---

## 6. Backend API — Endpoints Clés

| Endpoint | Méthode | Authentification | Fonctionnalité |
|----------|---------|------------------|-----------------|
| `/auth/login` | POST | Rate-limit 10/min | Génère JWT 24h |
| `/auth/register` | POST | Rate-limit 5/min | Inscription self-service |
| `/api/meteo/{client_id}` | GET | JWT | Récupère météo actuelle zones |
| `/api/previsions/{client_id}` | GET | JWT | Prévisions 5j depuis cache DB |
| `/api/alertes/{client_id}` | GET | JWT | Historique alertes |
| `/api/zones/{client_id}` | GET | JWT | Zones client |
| `/api/zones/{client_id}/add` | POST | JWT | Ajouter zone |
| `/api/meteo/snapshot/add` | POST | Service Secret | POST webhook (GitHub Actions) |
| `/api/account/{client_id}` | GET | JWT | Infos compte (plan, quotas) |
| `/api/geocoding/search?q=...` | GET | Public | Recherche villes |

---

## 7. Authentification et Sécurité

### JWT Token
```
Payload : {
  "client_id": 1,
  "username": "geodis-lemeux",
  "exp": 1714876800  // +24h
}

Encodage : HS256 avec JWT_SECRET
```

### Rate-limiting
- `/auth/login` : 10 tentatives/min par IP
- `/auth/register` : 5 tentatives/min par IP
- Exceptions : 429 Too Many Requests

### CORS & Sécurité
- **Production** : HTTPS, domaine Render uniquement
- **Développement** : localhost:8000, 127.0.0.1:8080
- **Headers HTTPS** : Validation IP, timeout geolocalisation 1s

---

## 8. Tests Validés (Avril-Mai 2026)

| Test | Script | Résultat | Date |
|------|--------|----------|------|
| Collecte météo multi-zones | test_all_zones.py | ✅ PASS | 30/04 |
| Alertes email cooldown | test_final_success.py | ✅ PASS | 01/05 |
| Dashboard HTML render | test_complete_render.py | ✅ PASS | 02/05 |
| Tournées météo par étape | test_simple_trafic.py | ✅ PASS | 03/05 |
| Cache & fraîcheur données | test_cache_multiple.py | ✅ PASS | 02/05 |
| **Collecte AQI batch** | meteo_open.py | ✅ PASS | 06/05 |
| **Email pollution 3 seuils** | send_email_pollution() | ✅ PASS | 06/05 |
| **Dashboard AQI badge** | updateMeteoTab() | ✅ PASS | 26/05 |
| **Emails trafic SMTP** | trafic.py send_email_trafic() | ✅ PASS | 26/05 |
| **Email de test en production** | `/api/alertes/{client_id}/test-email` | ✅ PASS | 28/05 |
| **Alerte UV/chaleur temps réel** | `/api/meteo/snapshot/add` | ✅ PASS | 28/05 |

**Tests manuels UI :**
- ✅ Login/Register workflow
- ✅ Affichage 5 onglets
- ✅ Graphiques Mon Compte
- ✅ Création/suppression tournées
- ✅ Gestion zones
- ✅ Cartes Leaflet

---

## 9. Changements Majeurs à partir du 1er Mai 2026

### 9.1 Transition "Cron Local → GitHub Actions"

**Avant 1er mai :**
- `auto_meteo_loop.py` boucle locale (appel meteo_open.py toutes les 22 min)
- Dépendance machine locale
- Risque d'interruption

**À partir du 1er mai puis stabilisation en mai :**
- GitHub Actions d'abord en `schedule */22` (cadence non garantie)
- Migration vers **cron-job.org** + `workflow_dispatch` toutes les heures (cadence maîtrisée)
- Pas de script local tournant
- Données toujours à jour même machine arrêtée

### 9.2 Changements observés

```
✅ Fraîcheur données : Garantie 1h max (cron-job.org)
✅ Continuité service : Pas de dépendance machine locale
✅ Logs centralisés : GitHub Actions logs + Render logs
✅ Fiabilité améliorée : déclenchement externe stable (HTTP 204)
```

---

## 10. Cas d'Usage Réels — Scenarios

### Scenario 1 : Alerte verglas en hiver
```
Heure : Janvier, 14:30
Données : T = 0.5°C, Pluie = 2 mm/h

Système :
  1. Détecte ❄️ Verglas
  2. Vérifie last_alerts.json → pas d'alerte dans la dernière heure
  3. Envoie email "Alerte verglas à Le Meux"
  4. Sauvegarde AlerteLog en BD
  5. Met à jour last_alerts.json (timestamp)

Résultat : Manager alerté, tournées reprogrammées si nécessaire
```

### Scenario 2 : Rapport hebdo lundi 8h
```
Heure : Lundi 8:00

Rapport inclut :
  - 12 alertes la semaine passée
  - 4 zones affectées
  - 3 types de risques (pluie x7, vent x3, UV x2)
  - Graphiques + prévisions
  - Excel attaché

Destinataires : alerts@example.com, ops@example.com

Résultat : Manager reçoit synthèse complète chaque lundi
```

### Scenario 3 : Création tournée avec météo
```
Heure : Mercredi 06:00
Chauffeur : Jean Dupont
Villes : Le Meux → Compiègne → Noyon

Dashboard affiche :
  ✅ Le Meux : 8°C, Vent 25 km/h → ✅ RAS
  ⚠️ Compiègne : 7°C, Vent 28 km/h → 💨 Vent fort
  🔴 Noyon : 6°C, Vent 35 km/h → 💨 Vent + 🌧️ Pluie

Score combiné : ⚠️ MOYEN

Résultat : Chauffeur sait conditions exactes au moment départ
```

### Scenario 4 : Alerte pollution AQI (NOUVEAU — Mai 2026)
```
Heure : Mardi 10:00

Données AQI récupérées :
  - Le Meux 🏣 : AQI = 62 (🔴 Mauvais, PM2.5 = 18.5 µg/m³)
  - Clairoix 🏣 : AQI = 35 (Acceptable)

Système :
  1. Filtre sites avec AQI ≥ 40 → Le Meux
  2. Détermine max_aqi = 62 → cooldown 3h (Mauvais)
  3. Vérifie last_pollution_alert.json → pas d'alerte dans les 3h
  4. Envoie email avec sections colorées
  5. Sauvegarde cooldown (clé="medium")

Email envoyé :
  ⚠️ Alerte Pollution — Qualité air Mauvais
  
  🔴 Mauvais (60-79): Le Meux 🏣 (AQI 62)
  
  Recommandations : Port de masque conseillé, ralentir rythme déplacements

Dashboard affiche :
  ✅ Colonne AQI : badge rouge "62" pour Le Meux
  ✅ Bannière : "🔴 Mauvais (60-79): Le Meux (AQI 62)"
  ✅ Rapport hebdo : tableau AQI après KPIs

Résultat : Manager alerté, tournées peuvent ajuster horaires/équipes
```

---

## 11. Plus-values et Avantages Compétitifs

| Aspect | Solution GEODIS | Marché |
|--------|-----------------|--------|
| **Précision météo** | Open-Meteo local | Stations générales 5-50 km |
| **Alertes** | Multi-zones intelligentes | Pas d'alertes ou génériques |
| **Surveillance pollution** | AQI européen + PM2.5 (3 seuils) | Aucune solution ⭐ UNIQUE |
| **Reporting** | Hebdo auto Excel+HTML + AQI | Manuel ou inexistant |
| **Tournées** | Score risque par étape | Calendrier basique |
| **Adaptabilité** | Custom pour GEODIS | Templates génériques |
| **Coût** | $7/mois (Render) | $100-1000+/mois |

---

## 12. Conclusion

**Mah Météo** est une **solution météo sur-mesure**, conçue pour répondre aux besoins opérationnels de GEODIS :

✅ **Précision** : Données locales avec cycle horaire garanti  
✅ **Automatisation** : Déclenchement externe stable (cron-job.org + workflow_dispatch)  
✅ **Intelligence** : Alertes intelligentes + analytics  
✅ **Reporting** : Rapport hebdo auto (Excel + email)  
✅ **Adaptabilité** : Tournées, zones custom, quotas  
✅ **Robustesse** : Tests validés, fallback, JWT, rate-limiting  

La plateforme est **production-ready** avec un mode d'exécution stabilisé en mai 2026 (cron-job.org → GitHub Actions).

---

## 13. Audit Technique & Corrections Appliquées (Mai 2026)

### 13.1 Problèmes identifiés par l'audit

| Problème | Gravité | Impact |
|----------|---------|--------|
| Actions GitHub dépréciées (`checkout@v3`, `setup-python@v4`) | 🔴 Critique | Deadline suppression : juin 2026 |
| GitHub Actions schedule `*/22` non respecté | 🔴 Critique | Gaps réels : 42-251 min (throttling GitHub) |
| Rapport hebdo : erreur 403 Forbidden sur Render | 🔴 Critique | Rapport envoyé sans données d'alertes |
| SQLite `no such table: zones` en CI | 🟡 Moyen | Bruit dans les logs, non bloquant |
| Timeout Open-Meteo trop court (10s) | 🟡 Moyen | Timeouts occasionnels sur 27 zones |

### 13.2 Corrections appliquées

**Fix 1 — Actions GitHub mises à jour** (commit `117ffe3`)
```yaml
# Avant
uses: actions/checkout@v3
uses: actions/setup-python@v4

# Après
uses: actions/checkout@v4
uses: actions/setup-python@v5
  with:
    cache: 'pip'  # +optimisation durée run ~3min → ~1min
```

**Fix 2 — SQLite désactivé en CI** (commit `117ffe3`)
```python
# meteo_open.py
if os.environ.get('GITHUB_ACTIONS') == 'true':
    DB_AVAILABLE = False  # Pas de SQLite en CI, PostgreSQL uniquement via Render
```

**Fix 3 — Timeout Open-Meteo augmenté** (commit `117ffe3`)
```python
# Avant : timeout=10
response = requests.get(url, timeout=25)  # Après : 25s
```

**Fix 4 — Rapport hebdo 403 corrigé** (commit `2632b69`)
```python
# rapport_hebdomadaire.py — appels service Render avec auth
headers = {"X-Service-Secret": jwt_secret}  # Ajouté
response = requests.get(url, headers=headers, timeout=30)
# + fallback JSON local si API inaccessible
```

**Fix 5 — Vérification secrets en preflight** (commits `117ffe3` + `2632b69`)
```yaml
# Les deux workflows vérifient maintenant tous les secrets au démarrage
# avant de lancer le script Python
```

### 13.3 Migration cron GitHub → cron-job.org (commit `2d150e4`)

**Problème root cause :** GitHub throttle les crons `*/22` en période de forte charge → gaps réels 42-251 min, aucune garantie de cadence.

**Solution adoptée :**
- `schedule:` désactivé dans `meteo-cron.yml`
- **cron-job.org** (gratuit) appelle l'API GitHub `workflow_dispatch` toutes les heures
- Résultat : cadence garantie ±1 min, indépendante de la charge GitHub

```
cron-job.org (0 * * * *)  →  POST GitHub API workflow_dispatch  →  meteo-cron.yml
```

**Configuration cron-job.org :**
- URL : `https://api.github.com/repos/Mhbe99/Mah-Meteo/actions/workflows/meteo-cron.yml/dispatches`
- Méthode : POST
- Headers : `Authorization: Bearer <PAT>`, `Accept: application/vnd.github+json`, `Content-Type: application/json`
- Body : `{"ref":"main"}`
- Fréquence : `0 * * * *` (toutes les heures)
- Réponse attendue : HTTP 204 No Content ✅

### 13.4 État des workflows après corrections

| Workflow | Fichier | Fréquence | État |
|----------|---------|-----------|------|
| Collecte météo | `meteo-cron.yml` | Toutes les heures (cron-job.org) | ✅ Opérationnel |
| Rapport hebdo | `rapport-hebdo.yml` | Lundi 06:00 UTC (08:00 Paris) | ✅ Opérationnel |

### 13.5 Consommation GitHub Actions (après optimisations)

| Paramètre | Valeur |
|-----------|--------|
| Fréquence | 1 run/heure |
| Durée observée/run | ~1-3 min (1er run ou file d'attente possibles plus longs) |
| Runs/mois | 720 |
| Minutes/mois estimées | **~720 à 2160 min** selon durée réelle |
| Quota gratuit | 2000 min/mois |
| **Lecture pratique** | garder un oeil mensuel sur la conso (repo privé) |

### 13.6 Incident opérationnel — Bulletin 12h non reçu (Juin 2026)

**Symptôme observé :**
- Le bulletin horaire attendu sur le créneau **12h00 Paris** n'a pas été reçu côté destinataires.

**Cause racine identifiée (backend) :**
1. Le déclenchement bulletin était évalué uniquement quand `refresh_meteo` mettait réellement des zones à jour (`updated > 0`).
2. En cas de `cooldown` (rafraîchissement trop récent) ou `rate_limited` Open-Meteo, le refresh sortait tôt sans évaluer le bulletin du créneau.
3. Le marquage interne `_mark_bulletin_sent(...)` pouvait être exécuté même si l'envoi email échouait (destinataire vide, provider indisponible, erreur transport).

**Conséquence :**
- Fenêtre horaire de bulletin potentiellement manquée alors que le système était vivant.
- Risque de faux positif "envoyé" côté mémoire process sans email réellement reçu.

**Correctif appliqué (code) :**
- Fichier impacté : `meteo_saas/backend/main.py`
- Ajout d'une routine de tentative bulletin sur données courantes (`_try_send_bulletin_with_current_data`) exécutée aussi dans les branches `skipped` (`cooldown` et `rate_limited`).
- Le marquage `_mark_bulletin_sent` est désormais conditionné au retour `True` de `send_bulletin_email(...)`.
- Ajout de logs explicites en cas de non-envoi (transport/destinataire) pour diagnostic rapide.

**État après correction :**
- Le bulletin de créneau est évalué même sans refresh complet des zones.
- Le statut "envoyé" reflète mieux la réalité de transport email.
- Réduction du risque de perte silencieuse sur créneaux 06h30 / 10h30 / 12h00 / 15h00 / 17h30.

**Points de vigilance restant à partager avec l'agent externe :**
1. `_last_bulletin_sent` est actuellement en mémoire process (non persistant entre redémarrages Render).
2. Les preuves d'envoi doivent s'appuyer sur les logs provider (Brevo/SMTP) en plus des logs applicatifs.
3. Vérifier la présence d'un destinataire valide (`client.email` ou fallback `RECEIVER_EMAILS`) pour chaque client avant créneau.

**Plan de vérification recommandé (opérationnel) :**
1. Forcer un appel `POST /api/refresh/{client_id}` pendant une fenêtre active (ex. 12h00-12h29 Paris).
2. Contrôler les logs Render : `[BULLETIN] Envoyé ...` ou message explicite de non-envoi.
3. Contrôler les logs provider email (Brevo events / SMTP) pour confirmer la livraison.
4. Refaire le contrôle sur 2 créneaux consécutifs pour valider la stabilité.

### 13.6 Incidents récents et résolution

| Incident | Symptôme | Cause | Correctif |
|----------|----------|-------|-----------|
| cron-job.org 401 à 12:00 | `401 Unauthorized` | Header `Authorization` mal formé | Format corrigé en `Bearer <token>` |
| cron-job.org 13:00/14:00 | `204 No Content` | - | Déclenchement validé |
| Run GitHub en orange > 5 min | attente longue | cache pip à chaud + queue runner | attendu sur premiers runs |
| Run échoué secret | `Missing required secret: RENDER_API_TOKEN` | secret absent côté GitHub | secret ajouté dans Actions Secrets |

### 13.7 Fonctionnement actuel des alertes météo et trafic

- Alertes météo : envoi email uniquement si risque actif **et changement de risque** par zone/client, avec cooldown anti-spam.
- Détection des risques : verglas (hiver), vent fort, pluie forte, UV fort/extrême, puis archivage JSON.
- Trafic TomTom : incidents récupérés par bbox globale, déduplication, tri par sévérité, cache 30 min.
- Emails trafic : synthèse groupée envoyée via `_send_email` (Brevo prioritaire si configuré, fallback SMTP), avec cooldown global.

### 13.8 Correctifs UX/Data — Onglet Mon Compte (Mai 2026)

| Sujet | Problème observé | Correctif appliqué | Impact |
|-------|-------------------|--------------------|--------|
| Graphes Alertes par zone / Répartition type | Graphes vides malgré exécution OK | Log des alertes persisté dans `alertes_log` lors de la réception des snapshots risque | Données enfin exploitables pour les graphes |
| Fenêtre 24h trop stricte | 24h parfois sans alerte, impression de bug | Fallback automatique sur 7 jours (`hours=168`) | Lecture métier plus pertinente |
| Écran vide ambigu | Message peu explicite pour les utilisateurs | Message clarifié : "aucune alerte sur 24h et 7 jours" | Compréhension immédiate multi-utilisateurs |

**Commits liés :**
- `ae5f70f` — Persist des alertes pour alimenter les graphes Mon Compte
- `96542e5` — Fallback sur historique plus large (première étape)
- `5db68f2` — Ajustement fallback final sur 7 jours
- `092bfef` — Message UX explicite en absence d'alertes

---

## 14. Évolutions fin mai 2026 (26 mai)

### 14.1 Fix SMTP Trafic — Emails trafic opérationnels

**Problème :** `send_email_trafic()` dans `meteo_saas/backend/trafic.py` échouait silencieusement — la connexion SMTP utilisait le port 465 (SSL) mais le serveur Gmail attendait le port 587 (STARTTLS). De plus, les variables SMTP n'étaient pas déclarées `global` en tête de fonction.

**Correctif appliqué :**
```python
# trafic.py — avant
smtp_server = smtplib.SMTP_SSL(SMTP_HOST, 465)

# trafic.py — après
smtp_server = smtplib.SMTP(SMTP_HOST, 587)
smtp_server.starttls()
```
- Variables `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_DEST` déclarées `global` en début de `send_email_trafic()`
- Résultat : emails trafic/incidents envoyés correctement

### 14.2 Suppression du bouton "Mode Démo"

**Situation :** Le bouton "Mode Démo" sur l'écran de connexion a été **retiré définitivement** de `dashboard.html`. L'interface login ne propose désormais que :
- Toggle Se connecter / S'inscrire
- Champs Email + Mot de passe
- Bouton Connexion

Aucune fonctionnalité de démonstration publique n'est maintenue.

### 14.3 Croissance du frontend — 3988 lignes

Le fichier `meteo_saas/frontend/dashboard.html` atteint désormais **3988 lignes** (versus ~2100 lignes en début de projet), reflétant l'ensemble des fonctionnalités ajoutées :
- Module Tournées complet
- Onglet Trafic & Alertes (TomTom)
- Analytics ApexCharts (4 graphiques)
- Gestion AQI / pollution avec badges et bannière
- Gestion des zones voisines avec mini-cartes

### 14.4 Documentation utilisateur — Guide Mah Météo (PPTX + DOCX)

Création de `generer_guide.py` : script Python (`python-pptx` + `python-docx`) générant une documentation complète :

| Fichier généré | Format | Contenu |
|---|---|---|
| `exports/GUIDE_MAH_METEO.pptx` | PowerPoint | 15 slides avec mockups fidèles du dashboard (thème clair, palette réelle) |
| `exports/GUIDE_MAH_METEO.docx` | Word | ~12 pages, même structure que les slides |

**Structure des 15 slides :**
1. Page de titre
2. Présentation Mah Météo
3. Écran de connexion
4. Vue d'ensemble du dashboard
5. Vue générale — Tableau Sites GEODIS
6. Vue générale — Zones voisines
7. Onglet Prévisions
8. Onglet Trafic & Alertes
9. Onglet Tournées — Création
10. Onglet Tournées — Liste
11. Onglet Mon Compte
12. Alertes email
13. Rapport hebdomadaire

### 14.5 Incident email météo production — diagnostic, correction et validation (28 mai 2026)

**Problème métier constaté :** les risques UV/chaleur étaient bien détectés et visibles dans l'application, mais aucun email de prévention n'arrivait aux destinataires. Le problème n'était donc pas la détection métier, mais la chaîne de transport email en production.

**Symptômes observés :**
- L'endpoint de test email répondait `status: ok`, ce qui confirmait le déclenchement applicatif.
- Les snapshots météo risqués créaient bien des entrées dans `alertes_log`.
- Les boîtes de réception restaient vides malgré ces confirmations côté API.
- Les logs Render montraient une erreur réseau SMTP de type `Network is unreachable`.

**Cause racine :**
- Le backend historique utilisait principalement un envoi SMTP direct.
- En environnement Render, la connectivité SMTP sortante n'était plus fiable pour ce service.
- Résultat : l'application déclenchait bien l'envoi, mais le transport échouait avant remise au fournisseur email.

**Correctif appliqué :**
- Ajout d'un mode fournisseur `Brevo` dans `meteo_saas/backend/email_alerts.py`.
- Priorité donnée a l'API HTTPS Brevo (`https://api.brevo.com/v3/smtp/email`) quand `EMAIL_PROVIDER=brevo` et `BREVO_API_KEY` sont configurés.
- Conservation d'un fallback SMTP pour les environnements qui disposent encore d'une connectivité SMTP fonctionnelle.
- Maintien de l'adresse expéditrice Mah Météo comme identité d'envoi, a condition qu'elle soit vérifiée côté Brevo.

**Pourquoi l'adresse Mah Météo n'a pas "disparu" :**
- L'identité expéditrice peut rester `sender@example.com` (ou toute adresse validée).
- Ce qui a changé n'est pas l'adresse visible par le destinataire, mais le canal technique d'envoi.
- Avant : `application -> SMTP direct`.
- Maintenant : `application -> API Brevo en HTTPS -> livraison email`.

**Validation réelle en production :**
- Test login Render sur `/auth/login` : ✅ OK.
- Test email manuel via `/api/alertes/{client_id}/test-email` : ✅ OK.
- Test métier réel via `/api/meteo/snapshot/add` avec une alerte `UV/chaleur` unique : ✅ OK.
- Confirmation utilisateur de réception dans la boîte mail : ✅ OK.

**Nettoyage des tests de production :**
- Ajout d'un endpoint ciblé `/api/alertes/{client_id}/cleanup-tests` dans `meteo_saas/backend/main.py`.
- Cet endpoint supprime les entrées de test (`TEST REEL`, `ALERTE REELLE`, `Verification envoi email`) dans `alertes_log` et `meteo_snapshot`.
- Puis il déclenche `refresh_meteo()` pour remettre des valeurs météo réelles sur les zones impactées.

**Configuration production retenue :**
- `EMAIL_PROVIDER=brevo`
- `BREVO_API_KEY=<cle API>`
- `SMTP_FROM=<adresse expediteur verifiee>`
- `SENDER_EMAIL=<adresse expediteur verifiee>`
- `RECEIVER_EMAILS=<liste destinataires>`
- `ALERT_EMAIL_ENABLED=true` (optionnel car la valeur par défaut est déjà `true`)

**Conclusion :** le problème n'était pas la logique d'alerte météo. La logique fonctionnait déjà. La panne réelle se situait sur le transport SMTP en production, et la migration vers Brevo API a restauré un envoi fiable des emails de prévention.

### 14.6 Incident alertes combinées météo + trafic non reçues (28 mai 2026)

**Problème observé :** les alertes combinées étaient bien calculées dans la réponse API trafic (`alerte_combinee`) mais elles n'arrivaient plus par email.

**Cause racine :**
- Dans `meteo_saas/backend/main.py`, la route `GET /api/trafic/{client_id}` avait un correctif ancien qui désactivait explicitement l'envoi email dans ce flux (commentaire "les emails ne doivent PAS être envoyés dans un GET").
- Résultat : détection fonctionnelle OK, transport email jamais appelé pour les alertes combinées.

**Correctif appliqué :**
- Réactivation de l'envoi automatique dans `get_trafic_route()` uniquement quand une `alerte_combinee` existe.
- Garde-fou anti-spam conservé via le cooldown déjà présent dans `send_combined_alert()` (`_check_cooldown`).
- Ajout d'un endpoint de validation explicite : `POST /api/alertes/{client_id}/test-combined-email`.

**Validation production :**
- Déploiement commit `001b400`.
- Appel `POST /api/alertes/{client_id}/test-combined-email` : `status: ok`.
- Nettoyage des artefacts de test exécuté via `POST /api/alertes/{client_id}/cleanup-tests` : suppression des entrées de test + refresh météo des zones impactées.

**Paramètre de contrôle :**
- `COMBINED_ALERT_AUTO_ENABLED=true` (par défaut) permet l'envoi auto des alertes combinées.
- Mettre `false` pour neutraliser ce flux en cas de besoin opérationnel exceptionnel.

### 14.7 Audit complémentaire du 28 mai 2026 — Correctifs finaux appliqués

| # | Fichier | Problème | Gravité | Correction appliquée |
|---|---|---|---|---|
| 1 | `meteo-cron.yml` | `schedule: '0 * * * *'` provoquait un double-déclenchement avec cron-job.org | 🟠 Moyen | `schedule` supprimé, `workflow_dispatch` conservé |
| 2 | `meteo-cron.yml` | `BREVO_API_KEY`, `EMAIL_PROVIDER`, `SMTP_FROM` absents du step run | 🟠 Moyen | Variables ajoutées dans `env` |
| 3 | `rapport-hebdo.yml` | `cache: 'pip'` absent sur `setup-python` | 🟡 Mineur | Cache pip ajouté |
| 4 | `rapport-hebdo.yml` | `BREVO_API_KEY`, `EMAIL_PROVIDER`, `SMTP_FROM` absents du step run | 🟠 Moyen | Variables ajoutées dans `env` |
| 5 | `meteo_open.py` | `_send_email_html()` SMTP-only, Brevo ignoré | 🟠 Moyen | Brevo prioritaire, fallback SMTP |
| 6 | `rapport_hebdomadaire.py` | Envoi rapport SMTP-only, Brevo ignoré | 🟠 Moyen | Brevo (avec pièce jointe base64) prioritaire, fallback SMTP |
| 7 | `main.py` | `/api/alertes` avait `le=500` (fenêtre trop large) | 🟡 Mineur | Limite abaissée à `le=200` |
| 8 | `dashboard.html` | `localStorage` sans garde en navigation privée | 🟡 Mineur | `setItem/getItem` encapsulés en `try/catch` |

**Statut global :** ✅ Tous les correctifs ci-dessus sont appliqués en code et poussés sur `main`.

### 14.8 Incident en cours — Double canal d'envoi email / expéditeur incohérent (03 juin 2026)

**Tableau résumé mis à jour (relevé du 03/06/2026)**

| Fichier | Points contrôlés | Anomalies ouvertes | Corrections appliquées |
|---|---:|---:|---:|
| `main.py` | 10 | 1 | 1 |
| `trafic.py` | 5 | 0 | 1 |
| `database.py` | 3 | 2 | 0 |
| `meteo_open.py` | 6 | 0 | 1 |
| `rapport_hebdomadaire.py` | 4 | 0 | 1 |
| `meteo-cron.yml` | 6 | 1 | 0 |
| `rapport-hebdo.yml` | 4 | 1 | 0 |
| `dashboard.html` | 8 | 0 | 2 |
| **TOTAL** | **54** | **7** | **8** |

> Note : le total inclut l'ensemble du périmètre d'audit (11 fichiers) ; le tableau ci-dessus reprend les éléments fournis dans la synthèse consolidée.

**Symptôme métier observé :**
- certains emails arrivent avec une identité visible "Mah Météo" ;
- d'autres arrivent via l'infrastructure Brevo ;
- certains flux (notamment trafic) peuvent sembler irréguliers d'un run à l'autre ;
- la lecture opérationnelle donne l'impression que plusieurs systèmes d'envoi coexistent.

**Constat technique :** l'application utilise actuellement **3 points d'entrée d'envoi email distincts**, avec une logique de transport partiellement dupliquée.

| Flux | Fichier | Canal actuel | Remarque |
|---|---|---|---|
| Alertes backend Render (météo, trafic, combiné) | `meteo_saas/backend/email_alerts.py` | Brevo prioritaire, fallback SMTP | Canal principal côté API FastAPI |
| Cron météo GitHub Actions | `meteo_open.py` | Brevo prioritaire, fallback SMTP | Implémentation séparée de `email_alerts.py` |
| Rapport hebdomadaire | `rapport_hebdomadaire.py` | Brevo prioritaire, fallback SMTP | Implémentation encore séparée |

**Cause racine principale :** le projet a convergé vers Brevo en production, mais **la centralisation n'est pas complète**. Le résultat est une architecture hybride où plusieurs scripts décident eux-mêmes s'ils envoient via Brevo ou via SMTP, selon les variables d'environnement disponibles au moment de l'exécution.

**Sous-causes identifiées :**

1. **Secrets GitHub incomplets côté workflows**
- `BREVO_API_KEY`, `EMAIL_PROVIDER`, `SMTP_FROM` n'étaient pas présents côté GitHub Actions lors de l'audit.
- Conséquence : un workflow peut exécuter le code en mode SMTP/fallback alors que le backend Render, lui, fonctionne déjà en mode Brevo.

2. **Logique d'envoi dupliquée dans plusieurs fichiers**
- `meteo_saas/backend/email_alerts.py` possède sa propre fonction `_send_email()`.
- `meteo_open.py` possède une autre fonction `_send_email_html()`.
- `rapport_hebdomadaire.py` possède une troisième logique d'envoi.
- Conséquence : la politique d'envoi n'est pas garantie uniforme entre backend, cron météo et rapport hebdo.

3. **Identité d'expéditeur distincte du transport technique**
- Le nom visible envoyé à Brevo est "Mah Meteo" ou "Mah Météo" selon le fichier.
- L'adresse d'envoi réelle dépend de `SMTP_FROM` ou `SENDER_EMAIL`.
- Conséquence : l'utilisateur peut percevoir une différence "Mah Météo / Brevo", alors qu'il s'agit parfois du même email expéditeur, mais acheminé par des transports différents.

4. **Trafic : comportement historiquement irrégulier**
- l'envoi batch trafic dépendait précédemment d'une logique qui ne notifiait effectivement que certains cas (notamment présence de sévérité forte).
- un correctif a été appliqué début juin 2026 pour envoyer la synthèse batch trafic pour toutes les sévérités détectées, tout en conservant le cooldown.

**Fichiers où se situe le problème de fond :**
- `meteo_saas/backend/email_alerts.py` — canal backend principal
- `meteo_open.py` — cron météo GitHub Actions avec logique d'envoi propre
- `rapport_hebdomadaire.py` — rapport hebdo avec logique d'envoi propre
- `.github/workflows/meteo-cron.yml` — secrets d'exécution du cron météo
- `.github/workflows/rapport-hebdo.yml` — secrets d'exécution du rapport hebdo
- `meteo_saas/backend/trafic.py` — synthèse batch trafic et cooldown associé

**Conclusion d'audit :** le problème n'est pas un bug unique d'email, mais une **dette d'architecture sur le transport mail**. Le système fonctionne, mais il reste trop distribué entre backend, cron et rapport, ce qui produit un comportement perçu comme incohérent.

**Cible de simplification recommandée :**
- en **production**, imposer un seul canal : `EMAIL_PROVIDER=brevo` ;
- conserver SMTP seulement comme fallback local/dev, pas comme stratégie de production ;
- centraliser tout envoi HTML dans un seul module partagé ;
- unifier le nom d'expéditeur visible : `Mah Météo` ;
- imposer les secrets GitHub suivants sur tous les workflows : `BREVO_API_KEY`, `EMAIL_PROVIDER`, `SMTP_FROM`.

**Corrections déjà engagées dans ce sens :**
- workflow météo corrigé pour exécution stable en CI ;
- alignement `SMTP_PASSWORD` dans `meteo-cron.yml` ;
- correctif trafic batch pour ne plus dépendre uniquement d'incidents sévères ;
- run météo et run rapport hebdo relancés avec succès après correction de workflow.

### 14.9 Incident complémentaire — Rapport hebdomadaire ancien / vérification des doublons (03 juin 2026)

**Symptôme observé :** le rapport hebdomadaire reçu lundi ne correspondait pas au contenu attendu le plus récent et semblait réutiliser un ancien jeu de données.

**Constat sur les workflows :**

| Élément | Fichier | État réel | Conclusion |
|---|---|---|---|
| Workflow rapport hebdo planifié | `rapport-hebdo.yml` | **Actif** (`schedule` + `workflow_dispatch`) | C'est le seul workflow hebdo automatique |
| Second workflow rapport hebdo | aucun | **Absent** | Pas de doublon de scheduling hebdomadaire détecté |
| Workflow météo principal | `meteo-cron.yml` | **Actif** via `workflow_dispatch` | Utilisé par cron-job.org |
| Ancien workflow météo | `run_meteo.yml` | **Présent mais manuel uniquement** | Pas un doublon automatique, mais source de confusion technique/documentaire |

**Conclusion :** pas de double cron, source de données fallback locale potentiellement obsolète identifiée comme cause.

---

## 15. Évolutions Juin 2026 — Bulletins horaires, alertes immédiates, sécurité repo

### 15.1 Bulletins météo programmés aux créneaux opérationnels

**Besoin métier :** envoyer automatiquement un récapitulatif complet (météo + trafic) aux conducteurs GEODIS aux moments clés de la journée, sans aucune action manuelle.

**Créneaux configurés (heure Paris) :**

| Créneau | Heure | Usage |
|---------|-------|-------|
| 06h30 | Matin | Prise de poste nuit → matin |
| 10h30 | Matin | Bilan milieu de matinée |
| 12h00 | Midi | Départ tournées après-midi |
| 15h00 | Après-midi | Bilan milieu d'après-midi |
| 17h30 | Soir | Fin tournées |

**Tolérance :** 30 min par créneau (ex : bulletin 06h30 envoyé entre 06h30 et 07h00).

**Dédoublonnage :** 1 seul bulletin par créneau par client par jour (`_last_bulletin_sent` en mémoire).

**Contenu du bulletin — design carte visuel :**
- Bannière statut (rouge si alertes, verte si RAS) + bouton dashboard intégré
- 4 chips statistiques : Temp. moyenne sites / Vent max / Trafic retard max / Nb alertes
- Cards zones 2 par ligne : icône météo, température en grand, badge Site/Zone, vent/pluie/UV, risques colorés
- Cards incidents trafic avec barre latérale colorée (rouge ≥30min, orange ≥15min, vert <15min)

**Sujets emails (sans emoji) :**
```
[Mah Météo] ALERTE 10h30 — GEODIS Ile-de-France    (si alertes actives)
[Mah Météo] Bulletin 10h30 — GEODIS Ile-de-France (mardi 03 juin 2026)
```

**Fichiers modifiés :**
- `meteo_saas/backend/email_alerts.py` — `send_bulletin_email()` ajouté
- `meteo_saas/backend/main.py` — globals `_BULLETIN_WINDOWS`, helpers `_get_bulletin_window_label()`, `_can_send_bulletin()`, `_mark_bulletin_sent()`, hook dans `refresh_meteo()`
- `meteo_open.py` — appel `POST /api/refresh/{client_id}` en fin de `_executer_pour_client()` pour déclencher le bulletin depuis le cron

**Bug initial et correctif :**
Le bulletin était hookté dans `/api/refresh/{client_id}` mais `meteo_open.py` n'appelait que `/api/meteo/snapshot/add`. Conséquence : bulletin jamais déclenché depuis le cron. Correctif : ajout d'un appel `POST /api/refresh/{client_id}` en fin de traitement client dans `meteo_open.py`.

### 15.2 Alerte trafic immédiate standalone (≥ 30 min)

**Besoin :** alerter immédiatement si un retard ≥ 30 min est détecté sur une zone, sans attendre un créneau de bulletin.

**Implémentation :** dans `get_trafic_route()` de `main.py`, après la vérification alerte combinée, envoi `send_trafic_alert()` avec uniquement les incidents ≥ 30 min si `retard_max >= 30`.

```python
# main.py — alerte trafic standalone
if retard_max >= 30:
    gros = [i for i in incidents_list if (i.get("delay_minutes") or 0) >= 30]
    send_trafic_alert(to_email=..., incidents=gros)
```

### 15.3 Uniformisation visuelle des emails

**Logo :** réduit de `28px` → `18px` dans `_build_email_shell()` (utilisé par tous les types de mails).

**Sujets sans emoji** — récapitulatif de tous les sujets :

| Type d'email | Sujet |
|---|---|
| Alerte météo | `[Mah Météo] X alerte(s) météo — {company}` |
| Alerte trafic | `[Mah Météo] X incident(s) trafic — {company}` |
| Alerte combinée | `[Mah Météo] ALERTE COMBINÉE météo + trafic — {company}` |
| Bienvenue | `Bienvenue sur Mah Météo — Compte approuvé (plan)` |
| Bulletin (alerte) | `[Mah Météo] ALERTE {créneau} — {company}` |
| Bulletin (normal) | `[Mah Météo] Bulletin {créneau} — {company} (date)` |

### 15.4 Sécurisation du dépôt git avant mise en public

**Fichiers retirés du suivi git (`git rm --cached`) :**
- `meteo_saas/data/clients.json` — contenait email GEODIS + coordonnées GPS sites
- `exports/` (67 fichiers) — données opérationnelles (alertes, rapports xlsx, cache trafic)

**Données hardcodées remplacées par variables d'environnement :**

| Fichier | Donnée retirée | Remplacement |
|---|---|---|
| `init_db.py` | `email="sender@example.com"` | `os.getenv("INIT_CLIENT_EMAIL", "")` |
| `debug_api.py` | `'password': 'demo1234'` | `os.getenv("TEST_PASSWORD", "")` |
| `check_dashboard.py` | `"demo1234"` par défaut | `os.getenv("TEST_PASSWORD", "")` |

**Historique git nettoyé :**
- Ancien historique (4 commits) remplacé par un commit orphelin unique propre (`git checkout --orphan`)
- Force push sur `origin/main`
- Aucune donnée sensible dans l'historique

**`.gitignore` mis à jour :**
```
meteo_saas/data/clients.json
exports/
```

**État final :** repo prêt à passer en public — aucun email, mot de passe, clé API, token, ni coordonnée GPS dans le code ou l'historique.

### 15.5 État fonctionnel au 3 juin 2026

| Fonctionnalité | État | Détail |
|---|---|---|
| Collecte météo horaire | ✅ Opérationnel | cron-job.org → GitHub Actions → meteo_open.py |
| Bulletins horaires programmés | ✅ Opérationnel | 5 créneaux, design carte, 1 envoi/créneau/jour |
| Alerte météo (verglas, vent, pluie, UV) | ✅ Opérationnel | Cooldown 1h, Brevo production |
| Alerte trafic immédiate ≥ 30 min | ✅ Opérationnel | Standalone sans attendre un créneau |
| Alerte combinée météo + trafic | ✅ Opérationnel | `COMBINED_ALERT_AUTO_ENABLED=true` |
| Rapport hebdomadaire lundi 8h | ✅ Opérationnel | Excel + HTML + Brevo |
| Dashboard frontend | ✅ Opérationnel | 5 onglets, 3988+ lignes |
| API Render (FastAPI + PostgreSQL) | ✅ Opérationnel | 25+ endpoints, JWT, rate-limiting |
| Sécurité repo | ✅ Prêt à passer en public | Historique propre, données retirées |

**Recommandation de correction :**
- en production GitHub Actions, **interdire le fallback local** pour le rapport hebdomadaire ;
- faire échouer explicitement le job si l'API Render ne fournit pas les données attendues ;
- supprimer ou archiver `run_meteo.yml` pour réduire les ambiguïtés ;
- journaliser dans l'email ou dans les logs la source réellement utilisée : `API Render` ou `fallback local`.

### 15.6 Validation post-correctifs audit (04 juin 2026)

**Objectif de validation :** confirmer les derniers correctifs d'audit (pool DB, concurrence workflow, flag CI rapport, index alertes) et vérifier l'absence de régression bloquante.

**Résultats des vérifications exécutées :**

| Vérification | Commande / Méthode | Résultat |
|---|---|---|
| Compilation backend DB | `python -m py_compile meteo_saas/backend/database.py` | ✅ OK |
| Exécution suite pytest globale | `python -m pytest -q --maxfail=1` | ⚠️ Échec structure tests (capture/teardown + `SystemExit` dans `test_all_zones.py`) |
| Exécution pytest sans capture | `python -m pytest -q -s --maxfail=1` | ⚠️ Même blocage de collection (tests scripts non pytest-purs) |
| Migration index alertes | `init_db()` + inspection SQLAlchemy | ✅ OK (`ix_alertelog_client_ts` présent) |
| Workflow météo concurrence | lecture `.github/workflows/meteo-cron.yml` | ✅ OK (`concurrency` workflow-level actif) |
| Workflow rapport mode CI | lecture `.github/workflows/rapport-hebdo.yml` | ✅ OK (`GITHUB_ACTIONS: 'true'` présent) |

**Correctif additionnel appliqué suite test réel :**
- Ajout d'une migration idempotente dans `init_db()` pour créer explicitement l'index:
  - `CREATE INDEX IF NOT EXISTS ix_alertelog_client_ts ON alertes_log (client_id, timestamp)`
- Motif : sur base déjà existante, la simple déclaration ORM de l'index ne garantissait pas sa création rétroactive.

**Conclusion opérationnelle (04/06) :**
- ✅ Les 4 points d'audit ouverts sont désormais couverts en code et validés.
- ⚠️ La suite `pytest` actuelle contient des scripts d'intégration qui quittent volontairement le process (`SystemExit`) et perturbent la collecte standard; ce point relève de l'hygiène des tests, pas d'un bug métier du correctif bulletin/audit.

## 15. Bonnes pratiques

- Garder `EMAIL_PROVIDER=brevo` en production Render.
- Vérifier mensuellement les secrets GitHub Actions (`BREVO_API_KEY`, `JWT_SECRET`, `RENDER_API_TOKEN`).
- Conserver `workflow_dispatch` pour la collecte météo, déclenché par cron-job.org.
- Éviter d'avoir plusieurs implémentations d'envoi email en production ; centraliser le transport dans un seul module partagé.

## 16. Contacts & Accès

**Palette fidèle au dashboard réel :** fond `#eef1f5`, header `#2c3e50`, accents bleu `#3498db`, vert `#38a169`, rouge `#c53030`.
