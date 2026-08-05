# Rapport Détaillé Dashboard Frontend

Source analysée : `meteo_saas/frontend/dashboard.html`

Rapport basé sur une lecture complète de `meteo_saas/frontend/dashboard.html`.

## Partie 1 — Structure Générale

### 1. Nombre exact de lignes

- `4543` lignes

### 2. Variables CSS dans `:root`

- `ABSENT`
- Nombre de variables CSS `:root` : `0`

### 3. Polices utilisées

- Google Fonts chargées :

```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
```

- Polices réellement utilisées dans le CSS / styles inline :
- `'IBM Plex Sans', sans-serif`
- `'IBM Plex Mono', monospace`

### 4. Bibliothèques externes chargées

```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/apexcharts@3.49.0/dist/apexcharts.min.js"></script>
```

- `Leaflet 1.9.4` via `unpkg`
- `ApexCharts 3.49.0` via `jsdelivr`
- `Google Fonts CSS2` pour `IBM Plex Sans` et `IBM Plex Mono`

## Partie 2 — Header

### HTML exact du header

```html
<header>
    <div class="title"><svg style="width:22px;height:22px;display:inline-block;vertical-align:middle;margin-right:6px" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="hSunG" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#FFB81C"/><stop offset="100%" style="stop-color:#FF8C00"/></linearGradient></defs><circle cx="50" cy="40" r="28" fill="url(#hSunG)"/><g stroke="#FFB81C" stroke-width="3" stroke-linecap="round"><line x1="50" y1="5" x2="50" y2="15"/><line x1="50" y1="65" x2="50" y2="75"/><line x1="85" y1="40" x2="75" y2="40"/><line x1="25" y1="40" x2="15" y2="40"/><line x1="72" y1="18" x2="65" y2="11"/><line x1="35" y1="69" x2="28" y2="76"/></g><path d="M 25 65 Q 20 65 20 72 Q 20 80 28 82 L 72 82 Q 80 80 80 72 Q 80 65 75 65" fill="#ecf0f1" opacity="0.9"/></svg>Mah Météo</div>
    <div class="controls">
        <div class="company-badge" id="company-name">---</div>
        <button class="refresh-btn" onclick="refreshData(true)">Actualiser</button>
        <button class="refresh-btn" onclick="openAdmin()" style="background:linear-gradient(135deg,#c53030,#e53e3e);color:#fff;font-size:11px;padding:6px 14px">🔒 Admin</button>
        <button class="logout-btn" onclick="logout()">Déconnexion</button>
    </div>
</header>
```

### Éléments présents

- Logo SVG inline + texte `Mah Météo`
- Badge société
- Bouton `Actualiser`
- Bouton `🔒 Admin`
- Bouton `Déconnexion`

### Classes CSS utilisées

- `title`
- `controls`
- `company-badge`
- `refresh-btn`
- `logout-btn`

### IDs utilisés

- `company-name`

### Texte exact des boutons

- `Actualiser`
- `🔒 Admin`
- `Déconnexion`

## Partie 3 — Barre KPI

### HTML exact de la barre KPI

```html
<div class="kpi-bar">
    <div class="kpi-item">
        <div class="kpi-val" id="kpi-temp">--</div>
        <div class="kpi-meta">Temp. max<br><span style="font-size:9px;font-weight:400;text-transform:none;letter-spacing:0">sites GEODIS</span></div>
    </div>
    <div class="kpi-item">
        <div class="kpi-val" id="kpi-wind">--</div>
        <div class="kpi-meta">Vent max<br><span style="font-size:9px;font-weight:400;text-transform:none;letter-spacing:0">sites GEODIS</span></div>
    </div>
    <div class="kpi-item">
        <div class="kpi-val" id="kpi-rain">--</div>
        <div class="kpi-meta">Précip.<br><span style="font-size:9px;font-weight:400;text-transform:none;letter-spacing:0">sites GEODIS</span></div>
    </div>
    <div class="kpi-item" id="kpi-alerts-box">
        <div class="kpi-val" id="kpi-alerts">0</div>
        <div class="kpi-meta">Alertes</div>
    </div>
</div>
```

### Indicateurs présents

- `Temp. max`
- `Vent max`
- `Précip.`
- `Alertes`

### IDs des valeurs

- `kpi-temp`
- `kpi-wind`
- `kpi-rain`
- `kpi-alerts`

### Classe CSS du conteneur

- `kpi-bar`

## Partie 4 — Navigation Onglets

### HTML exact de la barre d’onglets

```html
<div class="tabs">
    <button class="tab-btn active" onclick="switchTab(0)">Vue générale</button>
    <button class="tab-btn" onclick="switchTab(1)">Prévisions</button>
    <button class="tab-btn" onclick="switchTab(2)">Trafic & Alertes</button>
    <button class="tab-btn" onclick="switchTab(3)">Tournées</button>
    <button class="tab-btn" onclick="switchTab(4)">Mon Compte</button>
</div>
```

### Noms exacts des onglets

- `Vue générale`
- `Prévisions`
- `Trafic & Alertes`
- `Tournées`
- `Mon Compte`

### Fonction JavaScript appelée au clic

- `switchTab(0)`
- `switchTab(1)`
- `switchTab(2)`
- `switchTab(3)`
- `switchTab(4)`

### Classe actif vs inactif

- Actif : `tab-btn active`
- Inactif : `tab-btn`

### ID du conteneur de navigation

- `ABSENT`
- Classe du conteneur : `tabs`

### Note utile

- Il existe un panneau admin `switchTab(5)` mais il n’est pas dans cette barre d’onglets. Il est ouvert par le bouton header `openAdmin()`.

## Partie 5 — Onglet Vue Générale

### 5.1 Carte Leaflet

#### ID du conteneur

- `map`

#### HTML exact

```html
<div style="position:relative">
    <div id="map"></div>
    <!-- FIX C5: Bouton pause/reprise autoZoom -->
    <button id="btn-autozoom" onclick="toggleAutoZoom()" style="position:absolute;top:10px;right:10px;z-index:1000;background:#fff;border:1px solid #cbd5e0;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:13px;box-shadow:0 1px 4px rgba(0,0,0,0.1)" title="Pause / Reprise du zoom automatique">⏸️ Pause</button>
</div>
```

#### Hauteurs définies

- CSS global `#map` :

```css
#map {
    height: 420px;
    border-radius: 4px;
    border: 1px solid #dce1e8;
}
```

- CSS vue générale :

```css
.overview-split #map {
    height: 100%;
    min-height: 520px;
    border-radius: 8px;
    border: 1px solid #dce1e8;
}
```

- Mobile :
- `260px` à `max-width: 768px`
- `220px` à `max-width: 480px`

#### Options d’initialisation

- Signature : `function updateMapTab(meteo, previsions)`
- Initialisation exacte :

```js
if (!map) {
    const center = meteo.length > 0 ? [meteo[0].lat, meteo[0].lon] : [49.4, 2.75];
    map = L.map('map').setView(center, 10);
    L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap'
    }).addTo(map);
}
```

#### Types de marqueurs utilisés

- Zones `site` : emoji `🚚`
- Zones `voisin` : emoji `📍`
- Incidents trafic : `⚠️`, `💥`, `🚗`, `🚧`, `⛔`, `🚛`
- Type Leaflet : `L.divIcon` avec classe `custom-icon`

### 5.2 Tableau Sites GEODIS

#### Titre exact

- `Sites GEODIS`

#### HTML exact

```html
<div class="table-container">
    <div class="table-title">Sites GEODIS</div>
    <table id="sites-table">
        <thead>
            <th>Zone</th>
            <th>Ciel</th>
            <th>Temp.</th>
            <th>Vent</th>
            <th>Dir.</th>
            <th>Pluie</th>
            <th>UV</th>
            <th title="Indice de pollution de l'air (AQI européen)">Pollution (AQI) 🌫️</th>
            <th>Risques</th>
        </thead>
        <tbody></tbody>
    </table>
</div>
```

#### Colonnes exactes

- `Zone`
- `Ciel`
- `Temp.`
- `Vent`
- `Dir.`
- `Pluie`
- `UV`
- `Pollution (AQI) 🌫️`
- `Risques`

#### ID / classe

- Table : `sites-table`
- Conteneur : `table-container`
- Titre : `table-title`

#### Fonction qui le remplit

- `function updateMeteoTab(meteo)`

### 5.3 Zones voisines

#### Titre exact

- `Zones voisines`

#### HTML exact

```html
<div class="voisins-section">
    <div class="voisins-header" onclick="toggleVoisins()">
        <div class="voisins-header-left">
            <span style="font-size:15px">📍</span>
            <span class="voisins-header-title">Zones voisines</span>
            <span class="voisins-count" id="voisins-count">0 villes</span>
            <span class="voisins-alert-info" id="voisins-alert-info"></span>
        </div>
        <span class="voisins-toggle" id="voisins-chevron">▲ Replier</span>
    </div>
    <div id="voisins-grid" class="voisins-grid"></div>
    <div class="voisins-last-update" id="voisins-last-update"></div>
</div>
```

#### Format d’affichage

- `cards`
- Conteneur grille : `voisins-grid`
- Carte unitaire : `voisin-card`

#### Classes CSS des cards

- `voisin-card`
- `voisin-card alerte`
- `voisin-badge`
- `voisin-badge alert`
- `voisin-risk`
- `voisin-risk ok`
- `voisin-risk warn`
- `voisin-risk high`

#### Fonction qui le remplit

- `function updateMeteoTab(meteo)`

### 5.4 Bannière AQI / Pollution

#### Présence

- `OUI`

#### ID / classe

- ID dynamique : `pollution-banner`
- Pas de HTML statique dans le DOM initial
- Créée en JavaScript dans `updateMeteoTab(meteo)`

#### Condition exacte d’affichage

- Seulement pour les zones `site`
- Seuil d’apparition : `aqi >= 40`
- Condition finale :

```js
if (allAffected.length > 0) {
    pollutionBanner.innerHTML = bannerContent;
    pollutionBanner.style.display = 'block';
} else {
    pollutionBanner.style.display = 'none';
}
```

#### Calcul exact

```js
const sitesModerate = meteo.filter(z => z.type === 'site' && z.aqi != null && z.aqi >= 40 && z.aqi < 60);
const sitesBad = meteo.filter(z => z.type === 'site' && z.aqi != null && z.aqi >= 60 && z.aqi < 80);
const sitesVeryBad = meteo.filter(z => z.type === 'site' && z.aqi != null && z.aqi >= 80);
const allAffected = [...sitesVeryBad, ...sitesBad, ...sitesModerate];
```

#### Bloc exact de génération

```js
let pollutionBanner = document.getElementById('pollution-banner');
if (!pollutionBanner) {
    pollutionBanner = document.createElement('div');
    pollutionBanner.id = 'pollution-banner';
    pollutionBanner.style.cssText = 'padding:12px 16px;font-size:12px;border-radius:6px;margin-bottom:12px;display:none;';
    const tableWrap = document.querySelector('.table-container');
    if (tableWrap) tableWrap.parentNode.insertBefore(pollutionBanner, tableWrap);
}

if (allAffected.length > 0) {
    let bannerContent = '';
```

#### HTML injecté exact pour les 3 cas

```js
bannerContent += `<div style="background:#7b341e;color:#fff;padding:8px 12px;border-radius:4px;margin-bottom:6px;"><strong>⛔ Très mauvais (80+):</strong> ${names}</div>`;
bannerContent += `<div style="background:#e53e3e;color:#fff;padding:8px 12px;border-radius:4px;margin-bottom:6px;"><strong>🔴 Mauvais (60-79):</strong> ${names}</div>`;
bannerContent += `<div style="background:#dd6b20;color:#fff;padding:8px 12px;border-radius:4px;"><strong>🟠 Modéré (40-59):</strong> ${names}</div>`;
```

## Partie 6 — Onglet Prévisions

### Structure

- Conteneur principal :

```html
<div class="tab-content">
    <div class="forecast-grid" id="forecast-grid"></div>
</div>
```

### Structure de grille

- Desktop : `grid-template-columns: repeat(5, 1fr);`
- `max-width: 900px` : `repeat(3, 1fr)`
- `max-width: 768px` : `repeat(2, minmax(0, 1fr))`
- `max-width: 600px` : `repeat(2, 1fr)`
- `max-width: 480px` : `1fr`

### Classes / IDs

- `forecast-grid`
- `prevision-zone`
- `zone-header`
- `zone-icon`
- `zone-name`
- `forecast-card`
- `forecast-day`
- `day-name`
- `day-icon`
- `day-temps`
- `day-rain`
- `day-uv`
- `day-risk`

### Fonction qui remplit

- `function updatePrevisionTab(previsions)`

### Badge risque : classes exactes

- `day-risk`
- `risk-ok`
- `risk-pluie`
- `risk-vent`
- `risk-verglas`
- `risk-uv`

## Partie 7 — Onglet Trafic & Alertes

### KPIs trafic : labels et IDs

- `Incidents actifs` → `kpi-incidents`
- `Retard max` → `kpi-delay`
- `Heure MAJ` → `kpi-trafic-time`

### HTML exact des KPIs trafic

```html
<div class="kpi-grid" style="margin-bottom:16px;">
    <div class="kpi-box">
        <div class="kpi-label">Incidents actifs</div>
        <div class="kpi-value" id="kpi-incidents">0</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">Retard max</div>
        <div class="kpi-value" id="kpi-delay">--</div>
        <div class="kpi-unit">min</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">Heure MAJ</div>
        <div class="kpi-value" id="kpi-trafic-time">--</div>
    </div>
</div>
```

### Tableau incidents : structure exacte

```html
<div class="table-container" style="margin-bottom:16px;">
    <div class="table-title">Incidents trafic</div>
    <table id="trafic-table">
        <thead>
            <th>Route</th>
            <th>Description</th>
            <th>Sévérité</th>
            <th>Retard</th>
        </thead>
        <tbody></tbody>
    </table>
</div>
```

### Alerte combinée visuelle

- `OUI`

#### HTML présent dans le DOM

```html
<div id="alerte-combinee" style="display:none;margin-bottom:16px;"></div>
```

#### HTML injecté si présente

```html
<div style="padding:12px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px;margin-bottom:16px;">
    <div style="font-weight:600;color:#856404;font-size:13px;">Alerte combinée météo + trafic</div>
    <div style="color:#856404;font-size:12px;margin-top:6px;">${_esc(alerte_combinee.message)}</div>
</div>
```

### Historique alertes

- `ABSENT` dans l’onglet `Trafic & Alertes`
- Il n’y a pas de tableau ou liste visuelle d’historique d’alertes dans cet onglet
- Les graphes d’alertes sont dans `Mon Compte`

## Partie 8 — Onglet Tournées

### Champs du formulaire : labels exacts + IDs

- `Prénom` → `t-prenom`
- `Nom` → `t-nom`
- `Date` → `t-date`
- `Heure départ` → `t-heure`
- `Destinations` → `t-search-ville`
- `Notes` → `t-notes`

### HTML exact du formulaire

```html
<form id="form-tournee" autocomplete="off">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
        <div class="form-group" style="margin-bottom:0">
            <label>Prénom</label>
            <input type="text" id="t-prenom" required placeholder="Jean">
        </div>
        <div class="form-group" style="margin-bottom:0">
            <label>Nom</label>
            <input type="text" id="t-nom" required placeholder="Dupont">
        </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
        <div class="form-group" style="margin-bottom:0">
            <label>Date</label>
            <input type="date" id="t-date" required>
        </div>
        <div class="form-group" style="margin-bottom:0">
            <label>Heure départ</label>
            <input type="time" id="t-heure" required>
        </div>
    </div>
    <div class="form-group">
        <label>Destinations</label>
        <div class="t-autocomplete-wrap">
            <input type="text" id="t-search-ville" placeholder="Rechercher une ville..." autocomplete="off">
            <div id="t-suggestions"></div>
        </div>
        <ul id="t-selected-destinations"></ul>
    </div>
    <div class="form-group">
        <label>Notes</label>
        <textarea id="t-notes" rows="2" placeholder="Remarques éventuelles..." style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-family:'IBM Plex Sans',sans-serif;font-size:14px;resize:vertical;"></textarea>
    </div>
    <button type="submit" class="login-btn" style="background:#2c3e50;">Enregistrer la tournée</button>
</form>
```

### Bouton d’ajout

- Texte exact : `Enregistrer la tournée`
- Pas de `onclick` inline
- Soumis par l’écouteur :

```js
document.getElementById('form-tournee').addEventListener('submit', function (e) {
```

### Format d’affichage d’une tournée créée

- Format principal : `tableau`
- Table : `tournees-table`
- La cellule `Villes & Météo` contient une grille de mini-cards `.t-villes-grid` avec des cards `.t-ville-tag`
- Une ligne d’alerte additionnelle peut être injectée avec `.t-alerte-row` et `.t-alerte-banner`

### Colonnes exactes de `tournees-table`

- `Date`
- `Heure`
- `Chauffeur`
- `Risque`
- `Villes & Météo`
- `Notes`
- `Actions`

### Score de risque : affichage exact

- Cellule HTML injectée :

```html
<td style="text-align:center"><span class="' + scoreClass + '">' + scoreEmoji + ' ' + scoreLabel + '</span></td>
```

- Classes exactes
- `t-risk-ok`
- `t-risk-warn`
- `t-risk-danger`

### Classes des badges / états météo tournée

- `t-ville-tag`
- `t-ville-ok`
- `t-ville-warn`
- `t-ville-danger`

## Partie 9 — Onglet Mon Compte

### Sections présentes

- `Mon compte`
- `Mes zones`
- `Statistiques alertes`
- `Filtre actif`
- `Panneau détail zone`
- `Pollution (AQI) — évolution sur 7 jours`

### IDs des conteneurs ApexCharts

- `chart-zones`
- `chart-types`
- `chart-temp24`
- `chart-pluievent`
- `chart-uv`
- `chart-heatmap`
- `chart-pollution-weekly`

### Note

- Il n’y a pas `4` conteneurs ApexCharts. Il y en a `7`.

### Titres exacts des graphiques

- `📊 Alertes par zone (top 10) — cliquez pour filtrer`
- `🥧 Répartition par type — cliquez pour filtrer`
- `🌡️ Température — Dernières 48h`
- `🌧️ Pluie & Vent — 7 jours`
- `☀️ Indice UV — 7 jours`
- `🗺️ Niveau de risque par zone`
- `🌫️ Pollution (AQI) — évolution sur 7 jours`

### Barres de quota : labels et IDs

- `Sites` → `acc-sites-text`, `acc-sites-bar`
- `Villes voisines` → `acc-voisins-text`, `acc-voisins-bar`
- `Modifications restantes` → `acc-changes-text`, `acc-changes-bar`

## Partie 10 — JavaScript Global

### Fonctions demandées

- `refreshData()` ou équivalent : `OUI`

```js
async function refreshData(forceServerRefresh = false) {
```

- `showDashboard()` ou équivalent : `OUI`

```js
function showDashboard() {
```

- `switchPanel()` ou `switchTab()` : `OUI`

```js
function switchTab(index) {
```

- `updateKPI()` ou équivalent : `ABSENT`
- La mise à jour KPI est faite dans `updateMeteoTab(meteo)` et `updateTraficTab(trafic)`

- `showNotif()` ou `showToast()` : `OUI`

```js
function showNotif(message) {
```

- `loopZoom()` ou `autoZoom()` : `OUI` pour `autoZoom`, `ABSENT` pour `loopZoom`

```js
function autoZoom() {
```

- `_get_bulletin_window_label()` côté frontend : `ABSENT`

### Fonctions commençant par `_`

```js
function _readJsonCache(key, fallback) {
function _writeJsonCache(key, value) {
function _esc(str) {
function _normalizeZoneKey(str) {
function _sleep(ms) {
function _getToutesVillesConnues() {
function _levenshtein(a, b) {
function _trouverSuggestionsProches(saisie, max) {
function _filtrerSuggestions(query) {
function _storageKey() {
function _load() {
function _save(data) {
function _esc(str) {
function _addDestination(ville) {
function _removeDestination(index) {
function _renderSelectedDestinations() {
function _showSuggestions(items) {
function _hideSuggestions() {
function _renderTournees() {
function _updateStats() {
function _resetForm() {
async function _applyFilter(kind, value) {
function _clearFilter() {
function _aqiLevel(v) {
function _renderPollutionWeekly(pollution) {
function _renderRapportCharts(alertes, charts) {
function _showZoneDetail(zoneName, score) {
```

## Partie 11 — Gestion Email / Alertes Frontend

### Logique email côté frontend

- `ABSENT` pour l’envoi d’emails
- Aucune logique SMTP, Brevo, `test-email`, `cleanup-tests` ou composition email n’est présente côté frontend
- Le frontend gère seulement :
- champ d’inscription `reg-email`
- affichage de l’email du compte `acc-email`
- affichage email des utilisateurs en attente admin

### Bandeau AQI : condition exacte

- Voir Partie 5.4
- Condition métier : au moins un site GEODIS avec `aqi >= 40`

### Comment les alertes actives sont comptées

- Logique exacte :

```js
const isOk = !zone.risques || zone.risques.includes("RAS") || zone.risques.includes("✅");
if (!isOk) alertCount++;
```

- Donc une zone compte comme alerte active si `zone.risques` existe et ne contient ni `RAS` ni `✅`

### `localStorage` : clés utilisées

#### Clés explicites

- `mah_meteo_last_good_v1`
- `mah_trafic_last_good_v1`
- `token`
- `client_id`
- `company_name`
- `tournees_<client_id|default>`

#### Copies exactes des accès `localStorage`

```js
const raw = localStorage.getItem(key);
```

```js
localStorage.setItem(key, JSON.stringify(value));
```

```js
localStorage.setItem("token", TOKEN);
localStorage.setItem("client_id", CLIENT_ID);
localStorage.setItem("company_name", COMPANY_NAME);
```

```js
localStorage.removeItem("token");
localStorage.removeItem("client_id");
localStorage.removeItem("company_name");
```

```js
if (localStorage.getItem("token")) {
    const storedToken = localStorage.getItem("token");
```

```js
CLIENT_ID = parseInt(localStorage.getItem("client_id"));
COMPANY_NAME = localStorage.getItem("company_name");
```

```js
return JSON.parse(localStorage.getItem(_storageKey())) || [];
```

```js
localStorage.setItem(_storageKey(), JSON.stringify(data));
```

## Partie 12 — Responsive Actuel

### Meta viewport

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

### Classes `mobile-only` / `desktop-only`

- `ABSENT`

### Media queries présentes

- `OUI`

#### Media query 1

```css
@media (max-width: 768px) {
    body {
        font-size: 13px;
    }

    #login-screen {
        align-items: flex-start;
        padding: 16px;
    }

    .login-box {
        padding: 28px 18px;
        max-width: 100%;
    }

    .kpi-bar {
        flex-wrap: wrap;
    }

    .kpi-bar .kpi-item {
        flex: 1 1 50%;
        padding: 8px 10px;
        border-right: none;
        border-bottom: 1px solid #edf2f7;
    }

    .kpi-bar .kpi-item:nth-child(2n) {
        border-right: none;
    }

    .kpi-bar .kpi-item:nth-last-child(-n + 2) {
        border-bottom: none;
    }

    .overview-split {
        grid-template-columns: 1fr;
    }

    .main-content {
        overflow: visible;
    }

    .tabs {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        padding: 8px 8px 0;
        gap: 6px;
        scrollbar-width: none;
    }

    .tabs::-webkit-scrollbar {
        display: none;
    }

    .tab-btn {
        flex: 0 0 auto;
        white-space: nowrap;
        padding: 10px 12px;
        font-size: 12px;
        border-radius: 8px 8px 0 0;
    }

    .tab-content {
        padding: 14px 12px 18px;
    }

    .overview-split #map {
        height: 260px;
        min-height: 260px;
    }

    .kpi-grid {
        grid-template-columns: 1fr;
    }

    .voisins-grid {
        grid-template-columns: 1fr;
    }

    .table-container {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }

    table {
        min-width: 680px;
    }

    th,
    td {
        padding: 8px 10px;
    }

    .account-grid {
        gap: 12px;
    }

    .table-title {
        padding: 10px 12px;
        font-size: 12px;
    }

    .zone-search-box,
    .t-autocomplete-wrap {
        margin-bottom: 12px;
    }

    .zone-row,
    #t-selected-destinations li {
        padding: 8px 10px;
    }

    .zone-row {
        align-items: flex-start;
        gap: 8px;
    }

    .zone-row button {
        font-size: 18px;
    }

    .voisins-section {
        border-radius: 6px;
    }

    .voisins-header {
        padding: 9px 12px;
        align-items: flex-start;
    }

    .voisins-header-left {
        flex-wrap: wrap;
    }

    .voisin-card {
        padding: 8px;
    }

    .voisin-data {
        gap: 4px;
    }

    .forecast-card {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }

    .forecast-day {
        padding: 12px 6px;
    }

    .day-name {
        margin-bottom: 6px;
    }

    .day-temps,
    .day-rain,
    .day-uv {
        font-size: 10px;
    }

    .day-risk {
        margin-top: 6px;
    }

    #zone-add-bar > div,
    #filter-banner,
    #admin-content > div:first-child,
    #admin-gate > div,
    .table-container > div[style*="padding:20px"],
    .account-panel > div[style*="grid-template-columns:1fr 1fr"],
    .tab-content div[style*="grid-template-columns:1fr 1fr"] {
        display: block !important;
    }

    #zone-add-bar > div > div:last-child,
    .account-panel > div[style*="grid-template-columns:1fr 1fr"],
    .tab-content div[style*="grid-template-columns:1fr 1fr"] {
        grid-template-columns: 1fr !important;
    }

    .tab-content div[style*="grid-template-columns:repeat(3,1fr)"] {
        grid-template-columns: 1fr !important;
    }

    .tab-content div[style*="grid-template-columns:1fr 1fr 1fr"] {
        grid-template-columns: 1fr !important;
    }

    .tab-content div[style*="grid-template-columns:repeat(2,1fr)"] {
        grid-template-columns: 1fr !important;
    }

    #admin-kpis {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 10px;
    }

    #connections-table {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }

    #chart-zones,
    #chart-types,
    #chart-temp24,
    #chart-pluievent,
    #chart-uv,
    #chart-heatmap,
    #chart-pollution-weekly {
        min-height: 240px !important;
    }

    #btn-autozoom {
        padding: 4px 8px !important;
        font-size: 12px !important;
        top: 8px !important;
        right: 8px !important;
    }

    .risk-badge {
        max-width: 120px;
    }
}
```

#### Media query 2

```css
@media (max-width: 480px) {
    .kpi-bar .kpi-item {
        flex: 1 1 100%;
        border-right: none;
    }

    .kpi-bar .kpi-item:nth-last-child(-n + 2) {
        border-bottom: 1px solid #edf2f7;
    }

    .kpi-bar .kpi-item:last-child {
        border-bottom: none;
    }

    .voisins-grid {
        grid-template-columns: 1fr;
    }

    .overview-split #map,
    #map {
        height: 220px;
        min-height: 220px;
    }

    .tab-btn {
        padding: 9px 10px;
        font-size: 11px;
    }

    .tab-content {
        padding: 12px 10px 16px;
    }

    .login-box h1 {
        font-size: 20px;
    }

    .login-box {
        padding: 24px 14px;
    }

    .table-title {
        padding: 9px 10px;
    }

    .table-container {
        border-radius: 6px;
    }

    .forecast-card {
        grid-template-columns: 1fr !important;
    }

    .forecast-day {
        border-right: none;
        border-bottom: 1px solid #e2e8f0;
    }

    .forecast-day:last-child {
        border-bottom: none;
    }

    .kpi-box {
        padding: 14px 14px;
    }

    .account-panel {
        padding: 16px;
    }

    .zone-list {
        max-height: 240px;
    }

    .zone-row .zone-type {
        margin-top: 2px;
    }
}
```

#### Media query 3

```css
@media (max-width: 768px) {
    .account-grid { grid-template-columns: 1fr; }
}
```

#### Media query 4

```css
@media (max-width: 600px) {
    .forecast-card {
        grid-template-columns: repeat(2, 1fr) !important;
    }
}
```

#### Media query 5

```css
@media (min-width: 601px) and (max-width: 900px) {
    .forecast-card {
        grid-template-columns: repeat(3, 1fr) !important;
    }
}
```

## Partie 13 — Palette Couleurs Réelle

### Note

- Extraction unique des hex du fichier : `4543` lignes parcourues
- `#10005` repéré par extraction n’est pas une couleur, c’est l’entité HTML `&#10005;` du bouton supprimer

### Fond principal

- `#eef1f5`
- `#fff`
- `#f7fafc`
- `#edf2f7`
- `#f0fff4`
- `#fff5f5`
- `#fffaf0`
- `#fffff0`
- `#fff3cd`
- `#ebf8ff`
- `#ebf4ff`
- `#edf7f1`
- `#eef4fb`
- `#faf5ff`
- `#fdf0ee`
- `#fdf6ec`
- `#d9f2e3`
- `#fdecc8`
- `#f8d4d4`
- `#ead5d0`
- `#e6fffa`
- `#f0f0f0`
- `#fef2f2`
- `#fefcbf`
- `#feebc8`

### Header / navbar / shell

- `#2c3e50`
- `#ecf0f1`
- `#e0e0e0`
- `#1a252f`
- `#FFB81C`
- `#FF8C00`

### Accents bleu

- `#3498db`
- `#3182ce`
- `#2c5282`
- `#2b6cb0`
- `#bee3f8`
- `#ebf8ff`
- `#ebf4ff`

### Accents vert

- `#38a169`
- `#27ae60`
- `#2f855a`
- `#276749`
- `#22543d`
- `#68d391`
- `#c6f6d5`
- `#d9f2e3`

### Accents rouge

- `#e53e3e`
- `#c53030`
- `#c0392b`
- `#b91c1c`
- `#9b2c2c`
- `#7b341e`
- `#fed7d7`
- `#fecaca`
- `#feb2b2`
- `#f8d4d4`

### Accents orange / jaune

- `#dd6b20`
- `#d69e2e`
- `#e67e22`
- `#ed8936`
- `#c05621`
- `#b7791f`
- `#b8660a`
- `#744210`
- `#856404`
- `#ecc94b`
- `#ffc107`

### Accents violet

- `#6b46c1`
- `#805ad5`
- `#e9d8fd`
- `#faf5ff`

### Texte

- `#2d3748`
- `#4a5568`
- `#718096`
- `#a0aec0`
- `#1a202c`

### Bordures

- `#dce1e8`
- `#e2e8f0`
- `#cbd5e0`
- `#edf2f7`
- `#ddd`
- `#e4e2dc`
- `#ccc`

### Badges / puces / chips

- `#38a169`
- `#27ae60`
- `#2b6cb0`
- `#2c5282`
- `#c53030`
- `#dd6b20`
- `#d69e2e`
- `#744210`
- `#276749`
- `#9b2c2c`
- `#7b341e`
- `#e53e3e`
- `#fed7d7`
- `#c6f6d5`
- `#fefcbf`
- `#d9f2e3`
- `#fdecc8`
- `#f8d4d4`
- `#ead5d0`

### Liste unique complète des hex réellement trouvés

- `#1a202c`
- `#1a252f`
- `#1a4a7a`
- `#1a6b3a`
- `#1c4f82`
- `#22543d`
- `#276749`
- `#27ae60`
- `#2b6cb0`
- `#2c3e50`
- `#2c5282`
- `#2d3748`
- `#2f855a`
- `#3182ce`
- `#3498db`
- `#38a169`
- `#4a5568`
- `#68d391`
- `#6b46c1`
- `#718096`
- `#744210`
- `#7b341e`
- `#805ad5`
- `#856404`
- `#9b2c2c`
- `#a0aec0`
- `#b7791f`
- `#b8660a`
- `#b91c1c`
- `#bee3f8`
- `#c0392b`
- `#c05621`
- `#c53030`
- `#c6f6d5`
- `#cbd5e0`
- `#ccc`
- `#d69e2e`
- `#d9f2e3`
- `#dce1e8`
- `#dd6b20`
- `#ddd`
- `#e0e0e0`
- `#e2e8f0`
- `#e4e2dc`
- `#e53e3e`
- `#e67e22`
- `#e6fffa`
- `#e9d8fd`
- `#ead5d0`
- `#ebf4ff`
- `#ebf8ff`
- `#ecc94b`
- `#ecf0f1`
- `#ed8936`
- `#edf2f7`
- `#edf7f1`
- `#eef1f5`
- `#eef4fb`
- `#f0f0f0`
- `#f0fff4`
- `#f7fafc`
- `#f8d4d4`
- `#faf5ff`
- `#fdecc8`
- `#fdf0ee`
- `#fdf6ec`
- `#feb2b2`
- `#fecaca`
- `#fed7d7`
- `#feebc8`
- `#fef2f2`
- `#fefcbf`
- `#FF8C00`
- `#FFB81C`
- `#ffc107`
- `#fff`
- `#fff3cd`
- `#fff5f5`
- `#fffaf0`
- `#fffff0`

## Rapport Final

| ÉLÉMENT | PRÉSENT | DÉTAIL |
|---|---|---|
| Meta viewport | OUI | `<meta name="viewport" content="width=device-width, initial-scale=1.0">` |
| Variables CSS `:root` | NON | `0 variable` |
| KPI bar | OUI | `4 KPIs` |
| Carte Leaflet | OUI | `id="map"` |
| Tableau sites GEODIS | OUI | `9 colonnes` |
| Cards zones voisines | OUI | `grille de .voisin-card` |
| Bannière AQI | OUI | `seuil AQI >= 40 sur sites` |
| Onglet Prévisions | OUI | `grille 5 colonnes desktop, 3/2/1 responsive` |
| Onglet Trafic | OUI | `4 colonnes incidents` |
| Onglet Tournées | OUI | `6 champs principaux + tableau tournées` |
| Onglet Mon Compte | OUI | `7 conteneurs ApexCharts, 3 sections majeures` |
| ApexCharts | OUI | `7 charts` |
| Media queries mobile | OUI | `480px, 600px, 768px, 601-900px` |
| `localStorage` | OUI | `mah_meteo_last_good_v1, mah_trafic_last_good_v1, token, client_id, company_name, tournees_<id>` |
| `showNotif()` | OUI | fonction présente |
| `refreshData()` | OUI | fonction présente |
| `switchPanel/Tab()` | OUI | `switchTab(index)` |
| `loopZoom/autoZoom()` | OUI | `autoZoom()` présent, `loopZoom` absent |
| Bandeau superviseur | NON | `ABSENT` |

## Points utiles pour un autre agent

1. Il n’y a pas de variables CSS `:root`, donc toute refonte devra partir de couleurs en dur.
2. La bannière AQI n’est pas statique : elle est injectée dynamiquement par `updateMeteoTab(meteo)`.
3. Le dashboard visible a 5 onglets, mais le JavaScript gère aussi un panneau admin `index === 5`.
4. Les graphes Mon Compte ne sont pas 4 mais 7.
5. La logique “alertes actives” côté KPI repose uniquement sur `zone.risques` et la présence ou non de `RAS` / `✅`.
6. Il n’existe aucune logique d’envoi email côté frontend ; toute logique mail reste backend.

## Addendum — Avant / Après (Mails & Notifications)

### Portée

- Ce bloc documente les évolutions récentes liées aux notifications (et leur articulation avec la chaîne email backend).

### Avant / Après

| Sujet | Avant | Après |
|---|---|---|
| Bannière d'installation | Message orienté téléphone uniquement | Message généralisé : "Installer Mah Météo pour recevoir les alertes même application fermée" |
| Branding PWA | Nom pouvant inclure un contexte client | Nom d'application généralisé côté manifest (`Mah Météo`) |
| État du bouton push | Retours utilisateur parfois contradictoires | Rafraîchissement d'état renforcé après activation et parcours d'erreur clarifié |
| Erreurs de souscription | Messages non homogènes selon tentative auto / manuelle | Affichage d'erreurs plus explicite sur action utilisateur |
| Ressources iOS | 404 possible sur `apple-touch-icon-120x120.png` | URL servie, compatible Safari iOS |

### Note d'architecture

- Le frontend ne déclenche pas d'envoi email direct.
- Le frontend gère uniquement la souscription push (`/api/push/subscribe`) et l'UX d'activation.
- Les envois email et push effectifs restent pilotés par le backend selon les règles d'alerte.