# 🔍 AUDIT TECHNIQUE — Mah Météo SaaS • 13 Avril 2026 (V3.0)

---

## 📊 RÉSUMÉ EXÉCUTIF

**Mah Météo** est une plateforme SaaS de monitoring météorologique et trafic pour les sites logistiques GEODIS.
Depuis l'audit V2.1 du 9 avril 2026, **12 commits** supplémentaires ont été livrés, portant le total à **60 commits**. Le projet est désormais à **~85% opérationnel**.

| Indicateur | 9 avril (V2.1) | 13 avril (V3.0) | Évolution |
|------------|----------------|------------------|-----------|
| Base de données | SQLite (éphémère) 🔴 | **PostgreSQL** (persistent Render) | ✅ **Migré** |
| Endpoints API | 12 | **22** (14 GET, 5 POST, 1 DELETE, 2 HEAD) | +10 endpoints |
| Onglets dashboard | 4 | **5** (+ Mon Compte) | +1 onglet |
| Sécurité JWT | Secret par défaut 🔴 | **JWT_SECRET obligatoire** (sys.exit si absent) | ✅ **Sécurisé** |
| Rate-limiting | ❌ Inexistant | ✅ **slowapi** (10/min login, 5/min register) | ✅ **NOUVEAU** |
| CORS production | localhost autorisé 🟡 | **Dynamique** — prod: domaine Render uniquement | ✅ **Corrigé** |
| Multi-tenant | Verrouillé client_id=1 🔴 | **Boucle multi-clients** (API + JSON) | ✅ **Corrigé** |
| Mot de passe JSON | Valeur en clair historique 🔴 | **Supprimé** — hash bcrypt en DB uniquement | ✅ **Corrigé** |
| Inscription | ❌ Inexistant | ✅ **Self-service** (register + quotas plan) | ✅ **NOUVEAU** |
| Email anti-spam | ❌ Pas de limite | ✅ **Cooldown 1h/zone/type** | ✅ **NOUVEAU** |
| JWT frontend | Pas d'expiration visible | ✅ **Check toutes les 5 min, auto-logout** | ✅ **Corrigé** |
| Contrainte zones | Doublons possibles | ✅ **UNIQUE INDEX (client_id, name)** | ✅ **Corrigé** |
| Lignes frontend | ~2470 | **~2531** | +61 lignes |
| Lignes backend total | ~875 | **~1361** | +486 lignes |
| Zones couvertes | 27 | **27** (2 sites + 25 voisins) | Stable |

---

## ✅ CORRECTIONS APPLIQUÉES (1er avril 2026)

| Problème | Avant | Après | Status |
|----------|-------|-------|--------|
| Double workflow GitHub Actions | 2 crons = ~2680 runs/mois | 1 seul cron (22min) = ~1960 runs/mois | ✅ Corrigé |
| Boucle locale `auto_meteo_loop.py` | Tournait H24 sans pause | Arrêt automatique | ✅ Corrigé |
| Double `post_to_render()` par zone | 2 envois × 15 zones | 1 envoi × zones | ✅ Corrigé |
| Zone Formerie absente | 404 sur chaque run | Auto-création + données peuplées | ✅ Corrigé |
| Prévisions vides | Appels Open-Meteo timeout | Cache DB via GitHub Actions | ✅ Corrigé |
| Encodage emojis Windows | Crash UnicodeEncodeError | Fix UTF-8 | ✅ Corrigé |
| Sync zones manquantes | Ignorait nouvelles zones | Sync automatique au démarrage | ✅ Corrigé |

---

## 🆕 ÉVOLUTIONS LIVRÉES (1er → 9 avril 2026)

### 1. Interface professionnelle refondée

| Commit | Date | Description |
|--------|------|-------------|
| `62abb0e` | 08/04 | Refactor UI : interface professionnelle orientée métier |
| `305116d` | 08/04 | Logo SVG, marqueurs CSS, suppression emojis UI |
| `ceffa65` | 08/04 | **Suppression sidebar**, fusion 6→4 onglets, KPI bar permanente |
| `265338c` | 08/04 | Marqueurs emoji carte, icônes incidents trafic |
| `aba530e` | 08/04 | **KPI bar = sites GEODIS uniquement** (pas toutes zones) |

**Résultat** : Dashboard épuré en 4 onglets avec barre KPI persistante calculée sur les 2 sites GEODIS.

### 2. Mode Démo complet

| Commit | Date | Description |
|--------|------|-------------|
| `b9d27e7` | 08/04 | Bouton "Mode Démo" sur login + header, données fictives complètes |

**Données générées** : 10 zones météo, 8 zones prévisions (J+5), 6 incidents trafic, 6 alertes historiques.
Accessible sans authentification — aucun appel API.

### 3. Emojis météo dans toute l'interface

| Commit | Date | Description |
|--------|------|-------------|
| `23e2c01` | 08/04 | `cielEmoji()` — colonne Ciel en emojis (☀️⛅🌥️☁️🌧️⛈️🌨️🧊🌫️💨) |
| `e5d191e` | 08/04 | Emojis prévisions + direction vent + icônes météo |
| `f21df25` | 08/04 | Direction = 🧭 boussole uniquement, RAS = "—" |

### 4. Ajout de 13 nouvelles villes

| Commit | Date | Description |
|--------|------|-------------|
| `10a524c` | 08/04 | Breteuil, St Just en Chaussée, Trosly-Breuil, Crépy-en-Valois, Saint-Maximin, Nanteuil-le-Haudouin, Ressons-sur-Matz, Estrées-Saint-Denis, Guiscard, Chambly, Crèvecoeur-le-Grand, Mouy |

**Total zones** : 2 sites + 25 voisins = **27 zones** (contre 15 auparavant).

### 5. Tournées enrichies

| Commit | Date | Description |
|--------|------|-------------|
| `ac2a1c2` | 08/04 | Onglet Tournées : formulaire, tags villes, stats |
| `e705dcc` | 08/04 | Simplification intelligente des destinations |
| `04e2073` | 08/04 | **Météo par étape**, score risque 🟢🟡🔴, alertes combinées bandeau |
| `f21df25` | 08/04 | Matching robuste (strip emojis pour noms API) |

**Fonctionnalités** : Sélection de villes → météo en temps réel par étape → score risque global → alerte combinée météo+trafic.

### 6. Alertes email automatiques

| Commit | Date | Description |
|--------|------|-------------|
| `5e6def1` | 08/04 | Module `email_alerts.py` : 3 types d'email + intégration backend |
| *(non committé)* | 09/04 | **Fix multi-destinataires** — envoi à TOUS les RECEIVER_EMAILS |
| *(non committé)* | 09/04 | **Sync meteo_open.py** — ajout 12 villes manquantes dans VOISINS → 27 zones avec prévisions J+5 |

**3 types d'emails** :
- **Alerte météo** : tableau zone + type + valeur + message
- **Alerte trafic** : incidents sévères (high) ou retard > 15 min
- **Alerte combinée** : météo + trafic simultanés

**Multi-destinataires** : `_get_all_recipients()` combine `to_email` + `RECEIVER_EMAILS` du `.env`.
Testé et validé le 9 avril — envoi confirmé vers `sender@example.com` ET `client@example.com`.

### 7. Corrections UX

| Commit | Date | Description |
|--------|------|-------------|
| `5e6def1` | 08/04 | Heure par défaut = heure courante, risques 1 ligne (ellipsis), suppression historique alertes |

---

## ✅ CORRECTIONS APPLIQUÉES (9 → 13 avril 2026)

### 8. Sécurité renforcée

| Commit | Date | Description |
|--------|------|-------------|
| `942dfab` | 09/04 | **JWT_SECRET obligatoire** — `sys.exit(1)` si absent, alerte si < 32 chars |
| `942dfab` | 09/04 | **Rate-limiting** — `slowapi` : 10/min login, 5/min register |
| `32c20a3` | 10/04 | **CORS dynamique** — prod (PostgreSQL) : domaine Render uniquement, dev : localhost |
| `32c20a3` | 10/04 | **Mot de passe supprimé** de `clients.json` — hash bcrypt en DB uniquement |
| `cee8daf` | 10/04 | **Placeholders login** nettoyés — plus de valeurs sensibles visibles |

### 9. Multi-tenant complet

| Commit | Date | Description |
|--------|------|-------------|
| `05ff72d` | 09/04 | **meteo_open.py multi-clients** — boucle sur tous les clients DB + JSON |
| `32c20a3` | 10/04 | **`GET /api/service/clients`** — retourne tous clients actifs + zones depuis DB |
| `32c20a3` | 10/04 | **`/api/service/token`** accepte `?client_id=X` pour chaque client |

### 10. PostgreSQL + migrations

| Commit | Date | Description |
|--------|------|-------------|
| `2d41d94` | 09/04 | **Migration SQLite → PostgreSQL** — `psycopg2-binary`, pool connexions |
| `1a38f44` | 10/04 | Migration `zone_changes` column sur clients existants |
| `3be7acd` | 10/04 | Migration `INIT_CLIENT_PASSWORD` — mise à jour hash au démarrage |
| `cee8daf` | 10/04 | **Contrainte unique** `(client_id, name)` sur table zones |

### 11. Self-service & gestion de compte

| Commit | Date | Description |
|--------|------|-------------|
| `3edf449` | 09/04 | **Inscription self-service** — `POST /auth/register` + onglet Mon Compte |
| `3edf449` | 09/04 | **Gestion zones** — ajout/suppression + geocoding Open-Meteo |
| `1ffca1c` | 09/04 | **Quotas séparés** — sites vs voisins, limite changements zones/mois |
| `0f43280` | 09/04 | Ajustement quotas enterprise (emails 10 → 5) |
| `3be7acd` | 10/04 | **Changement mot de passe** — `POST /api/account/{client_id}/password` |

### 12. Anti-spam & expiration JWT

| Commit | Date | Description |
|--------|------|-------------|
| `cee8daf` | 10/04 | **Cooldown email** — 1 alerte/heure/zone/type (in-memory, `_COOLDOWN_SECONDS=3600`) |
| `cee8daf` | 10/04 | **JWT expiration frontend** — check toutes les 5 min, auto-logout si expiré |

---

## 🟡 POINTS D'ATTENTION RESTANTS (non bloquants)

### 1. SÉCURITÉ (risque résiduel faible)

| Sévérité | Problème | Fichier | Status |
|----------|----------|---------|--------|
| 🟡 Moyen | Token JWT stocké dans `localStorage` (XSS théorique) | `dashboard.html` | Acceptable (pas de données sensibles injectables) |

### 2. BASE DE DONNÉES (optimisations optionnelles)

| Problème | Impact | Priorité |
|----------|--------|----------|
| `AlerteLog.zone_name` = String au lieu de FK | Pas d'intégrité référentielle | 🟢 Faible |
| Pas de table de suivi quota API (`api_usage`) | Pas de monitoring consommation | 🟢 Faible |

### 3. OPTIMISATIONS (non nécessaires à ce stade)

| Problème | Impact | Priorité |
|----------|--------|----------|
| `print()` au lieu de `logging` | Pas de niveaux de log (DEBUG/INFO/ERROR) | 🟢 Faible |
| Appels Open-Meteo non batchés | ~1764/jour sur plafond 10 000, pas de risque | 🟢 Faible |
| Pas de Cache-Control headers | Render free tier n'a pas de CDN | 🟢 Faible |

---

## 🏗️ ARCHITECTURE ACTUELLE (13 avril 2026)

```
┌────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (dashboard.html)                      │
│  ~2531 lignes · 5 onglets · KPI bar · Mode Démo · Tournées        │
│  Vue générale | Prévisions J+5 | Trafic & Alertes | Tournées      │
│  Mon Compte (zones, quota, mot de passe)                           │
│  Emojis météo · Carte Leaflet · Score risque 🟢🟡🔴               │
│  JWT expiration check (5 min) · Auto-logout                        │
└───────────────────────────┬────────────────────────────────────────┘
                            │ Bearer JWT (client_id dans le token)
┌───────────────────────────▼────────────────────────────────────────┐
│                     BACKEND FastAPI (main.py)                      │
│  22 endpoints · JWT auth (11 protégés) · slowapi rate-limiting     │
│  /auth/login · /auth/register · /api/plans · /api/account          │
│  /api/meteo · /api/previsions · /api/trafic · /api/alertes         │
│  /api/zones · /api/zones/add · /api/zones/delete                   │
│  /api/geocoding/search · /api/account/password                     │
│  /api/service/token · /api/service/clients                         │
│  CORS dynamique (prod: Render only | dev: localhost)               │
├────────────────────────────────────────────────────────────────────┤
│                   EMAIL ALERTS (email_alerts.py)                   │
│  3 types : météo · trafic · combinée                               │
│  Multi-destinataires · SMTP Gmail · Templates HTML pro             │
│  Cooldown anti-spam : 1 alerte/heure/zone/type                     │
└───────────────────────────┬────────────────────────────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │    PostgreSQL (Render persistent)    │
         │  clients | zones | snapshots         │
         │  previsions | alertes | trafic       │
         │  Unique index (client_id, zone_name) │
         │  Migrations auto au démarrage        │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │  GitHub Actions (meteo-cron.yml)     │
         │  Cron : */22 * * * * (toutes 22 min) │
         │  → python meteo_open.py              │
         │  → Charge clients depuis API Render  │
         │  → Boucle multi-clients              │
         │  → Fetch Open-Meteo (27 zones)       │
         │  → POST snapshots + prévisions       │
         └──────────────────────────────────────┘
```

---

## 📊 INVENTAIRE TECHNIQUE

### Endpoints API (22)

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/auth/login` | Rate-limit 10/min | Authentification JWT (24h) |
| POST | `/auth/register` | Rate-limit 5/min | Inscription self-service |
| GET | `/api/plans` | ❌ | Plans et limites (public) |
| GET | `/api/account/{client_id}` | ✅ JWT | Infos compte + quotas |
| POST | `/api/account/{client_id}/password` | ✅ JWT | Changement mot de passe |
| GET | `/api/geocoding/search` | ❌ | Proxy geocoding Open-Meteo |
| GET | `/api/meteo/{client_id}` | ✅ JWT | Données météo temps réel |
| GET | `/api/previsions/{client_id}` | ✅ JWT | Prévisions J+5 |
| GET | `/api/alertes/{client_id}` | ✅ JWT | Historique alertes (limit=30) |
| GET | `/api/zones/{client_id}` | ✅ JWT | Liste zones + coordonnées |
| POST | `/api/zones/{client_id}/add` | ✅ JWT | Ajouter zone (vérifie quotas plan) |
| DELETE | `/api/zones/{client_id}/{zone_id}` | ✅ JWT | Supprimer zone |
| POST | `/api/meteo/snapshot/add` | ✅ JWT | Stocker snapshot météo (GitHub Actions) |
| POST | `/api/previsions/add` | ✅ JWT | Stocker prévisions cache (GitHub Actions) |
| GET | `/api/trafic/{client_id}` | ✅ JWT | Incidents trafic TomTom + alertes |
| GET | `/api/service/token` | ❌ | Token service (meteo_open.py) |
| POST | `/api/service/token` | ❌ | Token service (meteo_open.py) |
| GET | `/api/service/clients` | ❌ | Liste tous clients actifs + zones |
| GET | `/` | ❌ | Servir le dashboard HTML |
| HEAD | `/` | ❌ | Health check UptimeRobot |
| GET | `/health` | ❌ | Status check |
| HEAD | `/health` | ❌ | HEAD health check |

### Dépendances (requirements.txt — 14 packages)

| Package | Version | Rôle |
|---------|---------|------|
| fastapi | 0.100.1 | Framework web |
| uvicorn | 0.23.2 | Serveur ASGI |
| sqlalchemy | 2.0.23 | ORM |
| **psycopg2-binary** | **2.9.9** | **Driver PostgreSQL** |
| requests | 2.31.0 | Client HTTP |
| **httpx** | **0.27.0** | **Client HTTP async (geocoding)** |
| python-jose | 3.3.0 | JWT |
| python-dotenv | 1.0.0 | Variables d'env |
| openpyxl | 3.1.5 | Export Excel |
| pydantic | 1.10.12 | Validation données |
| passlib | 1.7.4 | Hachage mots de passe |
| python-multipart | 0.0.6 | Parsing formulaires |
| bcrypt | 4.0.1 | Hachage bcrypt |
| **slowapi** | **0.1.9** | **Rate-limiting** |

### Structure des fichiers clés

| Fichier | Lignes | Rôle |
|---------|--------|------|
| `meteo_saas/frontend/dashboard.html` | **~2531** | Interface complète (HTML+CSS+JS) — 5 onglets |
| `meteo_open.py` | **~778** | Script collecte multi-clients |
| `meteo_saas/backend/main.py` | **~533** | API FastAPI — 22 endpoints + rate-limiting |
| `meteo_saas/backend/database.py` | **~299** | SQLAlchemy + PostgreSQL + migrations |
| `meteo_saas/backend/email_alerts.py` | **~216** | Alertes email + cooldown anti-spam |
| `meteo_saas/backend/clients.py` | **~144** | Fonctions métier (météo, prévisions, alertes) |
| `meteo_saas/backend/auth.py` | **~85** | Auth JWT + hachage bcrypt |
| `meteo_saas/backend/models.py` | **~84** | Modèles Pydantic (8 modèles) |
| `meteo_saas/data/clients.json` | **~43** | Config zones GEODIS (sans mot de passe) |

---

## 📋 FEUILLE DE ROUTE MISE À JOUR (par priorité)

### Phase 1 — Sécurité ✅ TERMINÉE

| # | Tâche | Impact | Status |
|---|-------|--------|--------|
| 1.1 | Exiger `JWT_SECRET` via variable d'env (sys.exit si absent) | 🔴 Critique | ✅ Fait (commit `942dfab`) |
| 1.2 | Supprimer mot de passe en clair de `clients.json` | 🔴 Critique | ✅ Fait (commit `32c20a3`) |
| 1.3 | Rate-limiting `/auth/login` + `/auth/register` (slowapi) | 🟠 Élevé | ✅ Fait (commit `942dfab`) |
| 1.4 | CORS dynamique — prod: Render uniquement | 🟡 Moyen | ✅ Fait (commit `32c20a3`) |

### Phase 2 — Multi-tenant ✅ TERMINÉE

| # | Tâche | Impact | Status |
|---|-------|--------|--------|
| 2.1 | meteo_open.py boucle multi-clients (API + JSON) | 🔴 Critique | ✅ Fait (commit `05ff72d`) |
| 2.2 | `/api/service/token` accepte `?client_id=X` | 🔴 Critique | ✅ Fait (commit `32c20a3`) |
| 2.3 | Zones chargées depuis API Render (plus de hardcoding) | 🟠 Important | ✅ Fait (commit `32c20a3`) |
| 2.4 | Source unique pour les zones (DB = source de vérité) | 🟠 Important | ✅ Fait (commit `32c20a3`) |

### Phase 3 — Base de données ✅ TERMINÉE (2 optionnels restants)

| # | Tâche | Impact | Status |
|---|-------|--------|--------|
| 3.1 | PostgreSQL persistent (addon Render) | 🔴 Critique | ✅ Fait (commit `2d41d94`) |
| 3.2 | Contrainte unique `(client_id, zone_name)` | 🟡 Moyen | ✅ Fait (commit `cee8daf`) |
| 3.3 | `AlerteLog.zone_name` → FK `zone_id` | 🟢 Faible | ⬜ Optionnel |
| 3.4 | Table `api_usage` pour quotas | 🟢 Faible | ⬜ Optionnel |

### Phase 4 — Alertes email ✅ TERMINÉE (1 optionnel restant)

| # | Tâche | Impact | Status |
|---|-------|--------|--------|
| 4.1 | Module email (3 types + multi-destinataires) | 🟠 Important | ✅ Fait |
| 4.2 | Intégration email dans le cron GitHub Actions | 🟠 Important | ✅ Fait |
| 4.3 | Cooldown email (1h/zone/type, anti-spam) | 🟡 Moyen | ✅ Fait (commit `cee8daf`) |
| 4.4 | Configuration seuils d'alerte par client | 🟢 Faible | ⬜ Optionnel |

### Phase 5 — Self-service & gestion de compte ✅ TERMINÉE

| # | Tâche | Impact | Status |
|---|-------|--------|--------|
| 5.1 | Inscription self-service (`POST /auth/register`) | 🟠 Important | ✅ Fait (commit `3edf449`) |
| 5.2 | Onglet Mon Compte (zones, quotas, mot de passe) | 🟠 Important | ✅ Fait (commit `3edf449`) |
| 5.3 | Plans & quotas (free/pro/enterprise) | 🟠 Important | ✅ Fait (commit `1ffca1c`) |
| 5.4 | Changement mot de passe | 🟡 Moyen | ✅ Fait (commit `3be7acd`) |

### Phase 6 — Optimisations (toutes optionnelles)

| # | Tâche | Impact | Nécessaire ? | Status |
|---|-------|--------|-------------|--------|
| 6.1 | Batch appels Open-Meteo par lat/lon | 🟢 Faible | Non (1764/jour sur 10 000) | ⬜ Optionnel |
| 6.2 | Cache-Control HTTP headers | 🟢 Faible | Non (pas de CDN free tier) | ⬜ Optionnel |
| 6.3 | Remplacer `print()` par `logging` | 🟢 Faible | Non (print fonctionne) | ⬜ Optionnel |

---

## 📈 MÉTRIQUES ACTUELLES (13 avril 2026)

| Métrique | Valeur | Status |
|----------|--------|--------|
| Clients actifs | 1 (GEODIS — Le Meux) | 🟡 |
| Zones couvertes | **27** (2 sites + 25 voisins) | ✅ |
| Zones avec prévisions J+5 | **27/27** | ✅ |
| Onglets dashboard | **5** (Vue générale, Prévisions, Trafic, Tournées, Mon Compte) | ✅ |
| Endpoints API | **22** (11 JWT, 2 rate-limited) | ✅ |
| Fréquence mise à jour | 22 min (GitHub Actions) | ✅ |
| Prévisions | J+5, ~135 entrées/run (27 zones × 5 jours) | ✅ |
| Trafic TomTom | Cache 30 min | ✅ |
| Alertes email | **3 types, multi-dest, cooldown 1h/zone** | ✅ |
| Mode Démo | **Complet, 0 appel API** | ✅ |
| Tournées | **Météo/étape + score risque** | ✅ |
| Emojis météo | **Ciel + direction + prévisions** | ✅ |
| Inscription self-service | **register + quotas plan** | ✅ |
| DB | **PostgreSQL** (persistent Render) | ✅ |
| Sécurité | **JWT_SECRET obligatoire + rate-limit + CORS prod** | ✅ |
| Multi-tenant | **Boucle multi-clients (API + JSON)** | ✅ |
| Uptime Render | ~95% (free tier) | 🟡 |
| GitHub Actions runs/mois | ~1960 (plafond 2000) | ⚠️ Serré |
| Appels Open-Meteo/jour | ~1764 (sous plafond 10 000) | ✅ |
| Total commits | **60** | 📈 |
| Complétion projet | **~85%** | 🟢 |

---

## ✅ CE QUI MARCHE BIEN

1. **Architecture API REST** — FastAPI + JWT + 22 endpoints + rate-limiting
2. **PostgreSQL persistent** — plus de perte de données au redéploiement
3. **Sécurité renforcée** — JWT_SECRET obligatoire, bcrypt, slowapi, CORS dynamique
4. **Multi-tenant** — boucle multi-clients, inscription self-service, quotas plan
5. **5 onglets dashboard** — Vue générale, Prévisions, Trafic, Tournées, Mon Compte
6. **Alertes email anti-spam** — 3 types, multi-destinataires, cooldown 1h/zone
7. **Cache trafic TomTom** 30 min (protection quota)
8. **Prévisions stockées en DB** (plus d'appel live depuis Render)
9. **GitHub Actions** automatise la collecte sans serveur dédié
10. **Mode Démo** complet — présentation client sans données réelles
11. **Tournées enrichies** — météo par étape, score risque, alerte combinée
12. **27 zones** avec emojis météo (ciel, direction, prévisions)
13. **Gestion de compte** — changement mot de passe, ajout/suppression zones, quotas
14. **JWT expiration** — vérification frontend toutes les 5 min, auto-logout
15. **Contrainte unique** (client_id, zone_name) — plus de doublons

---

## 🔄 HISTORIQUE DES AUDITS

| Version | Date | Changements majeurs |
|---------|------|---------------------|
| V1.0 | 25 mars 2026 | Audit produit initial |
| V2.0 | 1er avril 2026 | Corrections quota + workflow + encodage |
| V2.1 | 9 avril 2026 | +12 zones, mode démo, tournées enrichies, email multi-dest, emojis, UI pro |
| **V3.0** | **13 avril 2026** | **PostgreSQL, 22 endpoints, sécurité (JWT+rate-limit+CORS), multi-tenant, self-service, cooldown email, Mon Compte** |

---

*Audit réalisé le 13 avril 2026 — Version 3.0*
*Complétion projet : ~85% — Toutes les tâches critiques sont terminées*
*Prochain audit recommandé : 27 avril 2026*
