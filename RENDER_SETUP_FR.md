# GUIDE COMPLET : Configuration Render - Étape par Étape

## ✅ DÉJÀ FAIT
- GitHub connecté à Render ✓
- Code poussé sur GitHub ✓

---

## 🔧 ÉTAPE 1 : Créer le Service Web (L'API)

### 1️⃣ Accédez à Render
```
URL : https://dashboard.render.com
```

Vous devez voir ce tableau de bord :
```
┌─────────────────────────────────────┐
│  Dashboard          New +    Account │
├─────────────────────────────────────┤
│                                     │
│  My Services                        │
│  (Liste vide ou services existants)  │
│                                     │
└─────────────────────────────────────┘
```

### 2️⃣ Cliquez sur "New +"
Bouton en HAUT À DROITE

```
Menu déroulant :
┌──────────────────┐
│ Web Service      │ ← CLIQUEZ ICI
│ Background Job   │
│ Cron Job         │
│ Postgres         │
└──────────────────┘
```

### 3️⃣ Sélectionnez "Web Service"

Render va demander : **"Quel dépôt ?"**

```
┌─────────────────────────────────────┐
│ Connect a repository                │
├─────────────────────────────────────┤
│ Mah-Meteo                           │ ← CLIQUEZ ICI
│ (private repo)                      │
│                                     │
│ [Configure build and deploy]        │
└─────────────────────────────────────┘
```

Cliquez sur **"Mah-Meteo"** pour le sélectionner

### 4️⃣ Remplissez le formulaire (exactement comme ceci)

```
┌─────────────────────────────────────────────────────┐
│ Create a New Web Service                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Name *                                              │
│ [meteo-saas-api                             ]       │
│  └─> COPIE EXACTE : meteo-saas-api                 │
│                                                     │
│ Runtime *                                           │
│ [Python 3                                   ▼]      │
│  └─> Sélectionnez "Python 3"                       │
│                                                     │
│ Build Command *                                     │
│ [pip install -r requirements.txt           ]       │
│  └─> COPIE EXACTE                                  │
│                                                     │
│ Start Command *                                     │
│ [uvicorn meteo_saas.backend.main:app       ]       │
│  [--host 0.0.0.0 --port $PORT              ]       │
│  └─> COPIE EXACTE (2 lignes)                       │
│                                                     │
│ Plan *                                              │
│ ◉ Free  (gratuit)                                   │
│ ○ Starter                                           │
│  └─> Sélectionnez "Free"                           │
│                                                     │
│ [Create Web Service]                      [Cancel]  │
└─────────────────────────────────────────────────────┘
```

### 5️⃣ Cliquez sur "Create Web Service"

Render va DÉPLOYER (attendez 2-3 minutes)

```
Écran pendant le déploiement :
┌─────────────────────────────────────┐
│ Building... ████████░░ 75%           │
│                                     │
│ Logs :                              │
│ > Fetching code...                  │
│ > Installing dependencies...        │
│ > Building...                       │
│ > Deploying...                      │
└─────────────────────────────────────┘
```

Attendez jusqu'à voir : **"Your service is live"** avec une URL verte

```
✅ Live
meteo-saas-api.onrender.com
```

---

## 🔑 ÉTAPE 2 : Ajouter les Clés Secrètes (IMPORTANT !)

### 1️⃣ Allez dans l'onglet "Environment"

Vous devez voir :
```
┌─────────────────────────────────────┐
│ Service: meteo-saas-api             │
├─────────────────────────────────────┤
│ Settings     Logs     Environment   │ ← CLIQUEZ ICI
├─────────────────────────────────────┤
│ Environment Variables               │
│ Add Environment Variable    [Button] │
├─────────────────────────────────────┤
│ (Aucune variable pour l'instant)    │
└─────────────────────────────────────┘
```

### 2️⃣ Cliquez sur "Add Environment Variable" 5 fois

**VARIABLE 1 :**
```
Key   : TOMTOM_API_KEY
Value : [VOTRE CLÉ TOMTOM - voir .env]
[Add]
```

**VARIABLE 2 :**
```
Key   : SENDER_EMAIL
Value : [VOTRE EMAIL GMAIL - ex: votreemail@gmail.com]
[Add]
```

**VARIABLE 3 :**
```
Key   : GMAIL_PASSWORD
Value : [VOTRE MOT DE PASSE APP GMAIL]
[Add]
```

**VARIABLE 4 :**
```
Key   : RECEIVER_EMAILS
Value : [email1@example.com,email2@example.com]
[Add]
```

**VARIABLE 5 :**
```
Key   : JWT_SECRET
Value : your_jwt_secret_key_here
[Add]
```

### 3️⃣ Attendez 1 minute que le service redémarre

Render redéploie automatiquement avec les nouvelles variables.

Vous verrez : **"Your service is live"** à nouveau ✅

---

## ⏰ ÉTAPE 3 : Créer la Tâche Planifiée (Cron Job)

### 1️⃣ Retournez au tableau de bord

Cliquez sur **"New +"** en haut à droite → **"Cron Job"**

### 2️⃣ Sélectionnez le dépôt "Mah-Meteo"

Même processus qu'avant.

### 3️⃣ Remplissez le formulaire (exactement)

```
┌─────────────────────────────────────────────────────┐
│ Create a New Cron Job                               │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Name *                                              │
│ [meteo-dashboards-cron                      ]       │
│  └─> COPIE EXACTE                                  │
│                                                     │
│ Runtime *                                           │
│ [Python 3                                   ▼]      │
│                                                     │
│ Build Command *                                     │
│ [pip install -r requirements.txt           ]       │
│                                                     │
│ Start Command *                                     │
│ [python meteo_open.py                       ]       │
│                                                     │
│ Schedule *                                          │
│ [*/15 * * * *                               ]       │
│  └─> COPIE EXACTE (toutes les 15 minutes)         │
│                                                     │
│ Plan *                                              │
│ ◉ Free                                              │
│                                                     │
│ [Create Cron Job]                         [Cancel]  │
└─────────────────────────────────────────────────────┘
```

### 4️⃣ Cliquez sur "Create Cron Job"

### 5️⃣ Allez à l'onglet "Environment" du Cron Job

Ajoutez les **MÊMES 5 variables** qu'avant :
- TOMTOM_API_KEY
- SENDER_EMAIL
- GMAIL_PASSWORD
- RECEIVER_EMAILS
- JWT_SECRET

---

## ✅ VÉRIFICATION FINALE

Vous devez voir dans votre tableau de bord :

```
┌──────────────────────────────────────────────┐
│ My Services                                  │
├──────────────────────────────────────────────┤
│ ✅ meteo-saas-api      (Web Service)         │
│    meteo-saas-api.onrender.com               │
│    Live                                      │
│                                              │
│ ✅ meteo-dashboards-cron    (Cron Job)       │
│    every 15 minutes                          │
│    Next run: in 12 minutes                   │
└──────────────────────────────────────────────┘
```

---

## 🎉 BRAVO !

Votre système fonctionne maintenant 24/7 sur le cloud Render :

✅ **API accessible** : https://meteo-saas-api.onrender.com/docs
✅ **Dashboards mis à jour** : Toutes les 15 minutes automatiquement
✅ **Pas de PC allumé requis** : Tout fonctionne sur les serveurs Render

---

## 📱 BESOIN D'AIDE ?

Si vous êtes bloqué à une étape, décrivez exactement :
- Le texte/bouton que vous voyez
- Le message d'erreur (s'il y a)
- Quelle étape exactement

Exemple : "Je suis bloqué à l'étape 2, je ne vois pas le bouton 'Add Environment Variable'"
