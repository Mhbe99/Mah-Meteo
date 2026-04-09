# 🔍 AUDIT TECHNIQUE — Mah Météo SaaS • 9 Avril 2026 (V2.1)

---

## 📊 RÉSUMÉ EXÉCUTIF

**Mah Météo** est une plateforme SaaS de monitoring météorologique et trafic pour les sites logistiques GEODIS.
Depuis l'audit du 1er avril 2026, **20 commits** ont été livrés, apportant des évolutions majeures en UX, fonctionnalités et opérationnel.

| Indicateur | 1er avril | 9 avril | Évolution |
|------------|-----------|---------|-----------|
| Zones couvertes | 15 (2 sites + 13 voisins) | **27** (2 sites + 25 voisins) | +12 villes |
| Zones avec prévisions J+5 | 15 | **27** (toutes synchronisées) | ✅ Corrigé |
| Onglets dashboard | 6 (puis réduit à 4) | **4** (Vue générale, Prévisions, Trafic & Alertes, Tournées) | Consolidé |
| Système d'email | ❌ Inexistant | ✅ **3 types** (météo, trafic, combinée) + multi-destinataires | **NOUVEAU** |
| Mode Démo | ❌ Inexistant | ✅ **Complet** (données fictives, 0 appel API) | **NOUVEAU** |
| Tournées enrichies | ❌ Basique | ✅ **Météo/étape + score risque + alertes combinées** | **NOUVEAU** |
| Emojis météo | ❌ Texte brut | ✅ **Ciel, vent, prévisions** (☀️⛅🌧️⛈️🧭) | **NOUVEAU** |
| Lignes frontend | ~1800 | **~2470** | +670 lignes |
| Endpoints API | 12 | **12** (+ email backend) | Stable |
| Sync meteo_open.py ↔ clients.json | ❌ 15 vs 27 zones | ✅ **27 = 27** (synchronisées) | ✅ Corrigé |

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
Testé et validé le 9 avril — envoi confirmé vers `mahmeteo@gmail.com` ET `mahame.toure@geodis.com`.

### 7. Corrections UX

| Commit | Date | Description |
|--------|------|-------------|
| `5e6def1` | 08/04 | Heure par défaut = heure courante, risques 1 ligne (ellipsis), suppression historique alertes |

---

## 🔴 DIAGNOSTIC : PROBLÈMES CRITIQUES RESTANTS

### 1. PAS UN VRAI MULTI-TENANT

Le système reste **verrouillé sur GEODIS (client_id=1)** :

| Couche | Fichier | Problème |
|--------|---------|----------|
| Backend | `main.py` | `/api/service/token` retourne toujours `client_id: 1` |
| Script | `meteo_open.py` L30 | `CLIENT_ID = 1` en dur |
| Script | `meteo_open.py` L78 | `username: "geodis-lemeux"` en dur |
| Script | `meteo_open.py` L196-222 | Zones GEODIS en dur (duplicat de clients.json) |
| Frontend | `dashboard.html` | Placeholder : `geodis-lemeux` / `demo1234` |
| Config | `clients.json` | Mot de passe en clair : `"demo1234"` |
| Workflow | `meteo-cron.yml` | Exécute `meteo_open.py` qui ne gère que client 1 |

**Impact** : Impossible d'ajouter un 2e client sans modifier 5+ fichiers.

### 2. SÉCURITÉ

| Sévérité | Problème | Fichier |
|----------|----------|---------|
| 🔴 Critique | JWT SECRET par défaut : `"your-secret-key-change-this"` | `auth.py` L16 |
| 🔴 Critique | Mot de passe en clair dans `clients.json` | `clients.json` L3 |
| 🟠 Élevé | Aucun rate-limiting sur `/auth/login` (brute-force possible) | `main.py` |
| 🟠 Élevé | Token JWT stocké dans `localStorage` (vol via XSS) | `dashboard.html` |
| 🟡 Moyen | CORS avec `localhost` autorisé en production | `main.py` L70-77 |
| 🟡 Moyen | Pas de timeout/expiration visible côté frontend | `dashboard.html` |

### 3. BASE DE DONNÉES

| Problème | Impact |
|----------|--------|
| **SQLite** en production (conteneur éphémère Render) | DB réinitialisée à chaque redéploiement |
| Pas de contrainte unique sur `(client_id, zone_name)` | Doublons possibles |
| `AlerteLog.zone_name` = String au lieu de FK | Pas d'intégrité référentielle |
| Pas de table de suivi quota API | Impossible de monitorer la consommation |

### 4. DUPLICATION DE CODE (partiellement résolu)

Les zones sont encore définies dans **3+ endroits** :
1. `meteo_saas/data/clients.json` — source de vérité DB (27 zones)
2. `meteo_open.py` L196-222 — `SITES` et `VOISINS` dicts (✅ **synchronisé le 9 avril — 27 zones**)
3. `rapport_hebdomadaire.py` — copie dupliquée
4. Fichiers de test (10+) — hardcodés

⚠️ La synchronisation reste **manuelle** — ajouter une zone exige de modifier 2+ fichiers.

---

## 🏗️ ARCHITECTURE ACTUELLE (9 avril 2026)

```
┌────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (dashboard.html)                      │
│  ~2470 lignes · 4 onglets · KPI bar · Mode Démo · Tournées        │
│  Vue générale | Prévisions J+5 | Trafic & Alertes | Tournées      │
│  Emojis météo (cielEmoji, dirEmoji, getWeatherIcon)                │
│  Carte Leaflet interactive · Score risque tournées 🟢🟡🔴          │
└───────────────────────────┬────────────────────────────────────────┘
                            │ Bearer JWT (client_id dans le token)
┌───────────────────────────▼────────────────────────────────────────┐
│                     BACKEND FastAPI (main.py)                      │
│  12 endpoints · JWT auth · CORS whitelist                          │
│  /auth/login · /api/meteo · /api/previsions · /api/trafic          │
│  /api/alertes · /api/zones · /api/snapshot/add · /api/previsions/add│
│  /health · / (serve dashboard)                                     │
├────────────────────────────────────────────────────────────────────┤
│                   EMAIL ALERTS (email_alerts.py)                   │
│  3 types : météo · trafic · combinée                               │
│  Multi-destinataires · SMTP Gmail · Templates HTML pro             │
│  _get_all_recipients() → RECEIVER_EMAILS du .env                   │
└───────────────────────────┬────────────────────────────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │       SQLite (éphémère Render)       │
         │  clients | zones | snapshots         │
         │  previsions | alertes | trafic       │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │  GitHub Actions (meteo-cron.yml)     │
         │  Cron : */22 * * * * (toutes 22 min) │
         │  → Wake Render API                   │
         │  → python meteo_open.py              │
         │  → Fetch Open-Meteo (27 zones)       │
         │  → POST snapshots + prévisions       │
         │  → Deploy GitHub Pages               │
         └──────────────────────────────────────┘
```

---

## 📊 INVENTAIRE TECHNIQUE

### Endpoints API (12)

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/auth/login` | ❌ | Authentification JWT (24h) |
| GET | `/api/meteo/{client_id}` | ✅ | Données météo temps réel |
| GET | `/api/previsions/{client_id}` | ✅ | Prévisions J+5 |
| GET | `/api/alertes/{client_id}` | ✅ | Historique alertes (limit=30) |
| GET | `/api/zones/{client_id}` | ✅ | Liste zones + coordonnées |
| POST | `/api/meteo/snapshot/add` | ✅ | Stocker snapshot météo |
| POST | `/api/previsions/add` | ✅ | Stocker prévisions cache |
| GET | `/api/trafic/{client_id}` | ✅ | Incidents trafic TomTom |
| GET | `/` | ❌ | Servir le dashboard HTML |
| HEAD | `/` | ❌ | Health check |
| GET | `/health` | ❌ | Status check |
| HEAD | `/health` | ❌ | HEAD health check |

### Dépendances (requirements.txt)

| Package | Version | Rôle |
|---------|---------|------|
| fastapi | 0.100.1 | Framework web |
| uvicorn | 0.23.2 | Serveur ASGI |
| sqlalchemy | 2.0.23 | ORM |
| requests | 2.31.0 | Client HTTP |
| python-jose | 3.3.0 | JWT |
| python-dotenv | 1.0.0 | Variables d'env |
| openpyxl | 3.1.5 | Export Excel |
| pydantic | 1.10.12 | Validation données |
| passlib | 1.7.4 | Hachage mots de passe |
| python-multipart | 0.0.6 | Parsing formulaires |
| bcrypt | 4.0.1 | Hachage bcrypt |

### Structure des fichiers clés

| Fichier | Lignes | Rôle |
|---------|--------|------|
| `meteo_saas/frontend/dashboard.html` | ~2470 | Interface complète (HTML+CSS+JS) |
| `meteo_saas/backend/main.py` | ~420 | API FastAPI + routing |
| `meteo_saas/backend/email_alerts.py` | ~230 | Module alertes email |
| `meteo_saas/backend/auth.py` | ~95 | Auth JWT + hachage |
| `meteo_saas/backend/models.py` | ~70 | Modèles Pydantic |
| `meteo_saas/backend/database.py` | ~55 | Config SQLAlchemy |
| `meteo_saas/backend/clients.py` | ~45 | Init clients depuis JSON |
| `meteo_saas/data/clients.json` | ~190 | Config zones GEODIS |
| `meteo_open.py` | ~310 | Script collecte données |

---

## 📋 FEUILLE DE ROUTE MISE À JOUR (par priorité)

### Phase 1 — Sécurité (Priorité critique)

| # | Tâche | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 1.1 | Exiger `JWT_SECRET` via variable d'env (pas de fallback faible) | 15 min | 🔴 Critique | ⬜ À faire |
| 1.2 | Supprimer mot de passe en clair de `clients.json` | 15 min | 🔴 Critique | ⬜ À faire |
| 1.3 | Ajouter rate-limiting sur `/auth/login` (slowapi) | 30 min | 🟠 Élevé | ⬜ À faire |
| 1.4 | Retirer `localhost` des CORS en production | 10 min | 🟡 Moyen | ⬜ À faire |

### Phase 2 — Multi-tenant

| # | Tâche | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 2.1 | Supprimer `CLIENT_ID = 1` de meteo_open.py — boucle multi-client | 2h | 🔴 Critique | ⬜ À faire |
| 2.2 | Refactorer `/api/service/token` pour tous les clients | 30 min | 🔴 Critique | ⬜ À faire |
| 2.3 | Supprimer zones hardcodées de meteo_open.py → lire clients.json | 1h | 🟠 Important | ⬜ À faire |
| 2.4 | Source unique pour les zones (éliminer duplications) | 1h | 🟠 Important | ⬜ À faire |

### Phase 3 — Base de données robuste

| # | Tâche | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 3.1 | Migrer SQLite → PostgreSQL (addon Render) | 2h | 🔴 Critique | ⬜ À faire |
| 3.2 | Ajouter contrainte unique `(client_id, zone_name)` | 15 min | 🟡 Moyen | ⬜ À faire |
| 3.3 | Corriger AlerteLog : `zone_name` → `zone_id` (FK) | 30 min | 🟡 Moyen | ⬜ À faire |
| 3.4 | Ajouter table `api_usage` pour quotas | 1h | 🟡 Moyen | ⬜ À faire |

### Phase 4 — Alertes email avancées

| # | Tâche | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 4.1 | Module email créé (3 types + multi-destinataires) | — | 🟠 Important | ✅ Fait |
| 4.2 | Intégrer envoi email dans le cron GitHub Actions | 1h | 🟠 Important | ⬜ À faire |
| 4.3 | Cooldown email (1 alerte/heure/zone, pas de spam) | 30 min | 🟡 Moyen | ⬜ À faire |
| 4.4 | Configuration seuils d'alerte par client | 1h | 🟡 Moyen | ⬜ À faire |

### Phase 5 — Interface d'admin + onboarding

| # | Tâche | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 5.1 | Endpoint `/admin/clients` (CRUD) | 3h | 🟠 Important | ⬜ À faire |
| 5.2 | Page admin pour ajouter client + zones | 4h | 🟠 Important | ⬜ À faire |
| 5.3 | Auto-provisioning nouveau client | 2h | 🟡 Moyen | ⬜ À faire |

### Phase 6 — Optimisation

| # | Tâche | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 6.1 | Batch appels Open-Meteo par lat/lon | 2h | 🟡 Moyen | ⬜ À faire |
| 6.2 | Cache HTTP (Cache-Control headers) | 30 min | 🟡 Moyen | ⬜ À faire |
| 6.3 | Remplacer `print()` par `logging` | 1h | 🟡 Moyen | ⬜ À faire |

---

## 📈 MÉTRIQUES ACTUELLES (9 avril 2026)

| Métrique | Valeur | Status |
|----------|--------|--------|
| Clients actifs | 1 (GEODIS — Le Meux) | 🟡 |
| Zones couvertes | **27** (2 sites + 25 voisins) | ✅ |
| Zones avec prévisions J+5 | **27/27** (meteo_open.py synchronisé) | ✅ |
| Onglets dashboard | **4** (Vue générale, Prévisions, Trafic, Tournées) | ✅ |
| Fréquence mise à jour | 22 min (GitHub Actions) | ✅ |
| Prévisions | J+5, ~135 entrées/run (27 zones × 5 jours) | ✅ |
| Trafic TomTom | Cache 30 min | ✅ |
| Alertes email | **3 types, multi-destinataires** | ✅ **NOUVEAU** |
| Mode Démo | **Complet, 0 appel API** | ✅ **NOUVEAU** |
| Tournées | **Météo/étape + score risque** | ✅ **NOUVEAU** |
| Emojis météo | **Ciel + direction + prévisions** | ✅ **NOUVEAU** |
| Uptime Render | ~95% (free tier) | 🟡 |
| GitHub Actions runs/mois | ~1960 (plafond 2000) | ⚠️ Serré |
| Appels Open-Meteo/jour | ~1764 (27 zones × ~65 runs/jour) | ✅ Sous plafond 10 000 |
| DB | SQLite (éphémère) | 🔴 |
| Sécurité | JWT secret faible, pas de rate-limit | 🔴 |
| Commits depuis audit V2.0 | **20 commits** (1-9 avril) | 📈 |

---

## ✅ CE QUI MARCHE BIEN

1. **Architecture API REST** bien structurée (FastAPI + JWT + 12 endpoints)
2. **Séparation frontend/backend** propre (1 HTML, 6 modules Python)
3. **Cache trafic TomTom** 30 min (protection quota)
4. **Prévisions stockées en DB** (plus d'appel live depuis Render)
5. **Alertes email multi-destinataires** — 3 types, templates HTML pro
6. **GitHub Actions** automatise la collecte sans serveur dédié
7. **Dashboard professionnel** — KPI bar, carte Leaflet, 4 onglets
8. **Mode Démo** complet — présentation client sans données réelles
9. **Tournées enrichies** — météo par étape, score risque, alerte combinée
10. **27 zones** avec emojis météo (ciel, direction, prévisions)
11. **Multi-destinataires email** — testé et validé (gmail + geodis)

---

## 🔄 HISTORIQUE DES AUDITS

| Version | Date | Changements majeurs |
|---------|------|---------------------|
| V1.0 | 25 mars 2026 | Audit produit initial |
| V2.0 | 1er avril 2026 | Corrections quota + workflow + encodage |
| **V2.1** | **9 avril 2026** | **+12 zones, mode démo, tournées enrichies, email multi-dest, emojis, UI pro, sync zones prévisions** |

---

*Audit réalisé le 9 avril 2026 — Version 2.1*
*Prochain audit recommandé : 23 avril 2026*
