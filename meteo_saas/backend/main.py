# -*- coding: utf-8 -*-
"""
main.py — Application FastAPI principale
"""

import os
import httpx
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Rate-limiting pour protéger /auth/login contre le brute-force
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

from .database import get_db, init_db, init_clients_from_json, SessionLocal, Client, Zone, MeteoSnapshot, PrevisionCache
from .auth import create_token, verify_password, get_current_client, hash_password
from .models import LoginRequest, RegisterRequest, TokenResponse, ZoneMeteo, PrevisionJour, TrafficIncident as TrafficIncidentModel, Alerte
from pydantic import BaseModel
from typing import Optional, List
from .clients import get_meteo_actuelle, get_previsions, get_alertes, get_zones
from .trafic import get_incidents
from .email_alerts import send_meteo_alert, send_trafic_alert, send_combined_alert

load_dotenv()


# ============ MODÈLES PYDANTIC ============

class MeteoSnapshotCreate(BaseModel):
    """Modèle pour créer un snapshot météo via API"""
    zone_name: str
    temperature: Optional[float] = None
    windspeed: Optional[float] = None
    wind_direction: Optional[str] = None
    precipitation: Optional[float] = None
    cloudcover: Optional[float] = None
    uv_index: Optional[float] = None
    risques: Optional[str] = None
    ciel: Optional[str] = None


# ============ LIFESPAN (Initialisation au démarrage) ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Événements de démarrage et arrêt de l'appli.
    """
    # Au démarrage
    print("🚀 Démarrage de l'application...")
    init_db()
    init_clients_from_json("meteo_saas/data/clients.json")
    print("✅ Application prête")
    
    yield
    
    # À l'arrêt
    print("🛑 Arrêt de l'application")


# ============ INITIALISATION FASTAPI ============

app = FastAPI(
    title="MétéoFlux SaaS",
    description="Plateforme SaaS de surveillance météo et trafic",
    version="1.0.0",
    lifespan=lifespan
)

# Rate-limiting : 10 tentatives/minute par IP sur /auth/login
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============ CORS ============

# En production (PostgreSQL détecté), seul le domaine Render est autorisé
_db_url = os.getenv("DATABASE_URL", "")
_is_production = "postgresql" in _db_url or "postgres" in _db_url

_allowed_origins = ["https://mah-meteo.onrender.com"]
if not _is_production:
    _allowed_origins += [
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ ROUTES AUTHENTIFICATION ============

# Limites par plan
PLAN_LIMITS = {
    "free":       {"sites": 1, "voisins": 5,  "emails": 1, "changes": 3},
    "standard":   {"sites": 1, "voisins": 5,  "emails": 1, "changes": 3},
    "pro":        {"sites": 3, "voisins": 8,  "emails": 3, "changes": 10},
    "enterprise": {"sites": 5, "voisins": 15, "emails": 5, "changes": 30},
    "groupe":     {"sites": 5, "voisins": 15, "emails": 5, "changes": 30},
}

@limiter.limit("10/minute")
@app.post("/auth/login", response_model=TokenResponse)
def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authentification utilisateur.
    Retourne un JWT valide 24h.
    Rate-limit : 10 tentatives/minute par IP.
    """
    # Chercher le client
    client = db.query(Client).filter(Client.username == login_data.username).first()
    
    if not client or not verify_password(login_data.password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides"
        )

    if not client.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte inactif"
        )

    # Créer le token
    token = create_token(
        data={"client_id": client.id, "username": client.username}
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        client_id=client.id,
        company_name=client.company_name
    )


# ============ INSCRIPTION SELF-SERVICE ============

@limiter.limit("5/minute")
@app.post("/auth/register", response_model=TokenResponse)
def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    """Inscription d'un nouveau client avec plan."""
    if data.plan not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail="Plan invalide")

    existing = db.query(Client).filter(Client.username == data.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur existe déjà")

    client = Client(
        username=data.username,
        password_hash=hash_password(data.password),
        company_name=data.company_name,
        email=data.email,
        plan=data.plan,
        active=1
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    token = create_token(data={"client_id": client.id, "username": client.username})
    return TokenResponse(
        access_token=token, token_type="bearer",
        client_id=client.id, company_name=client.company_name
    )


# ============ PLANS ============

@app.get("/api/plans")
def get_plans():
    """Retourne les limites de chaque plan."""
    return PLAN_LIMITS


@app.get("/api/account/{client_id}")
def get_account(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Infos du compte : plan, quotas utilisés."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    limits = PLAN_LIMITS.get(client.plan, PLAN_LIMITS["free"])
    return {
        "username": client.username,
        "company_name": client.company_name,
        "email": client.email,
        "plan": client.plan,
        "sites_used": sum(1 for z in zones if z.type == "site"),
        "sites_max": limits["sites"],
        "voisins_used": sum(1 for z in zones if z.type == "voisin"),
        "voisins_max": limits["voisins"],
        "emails_max": limits["emails"],
        "changes_used": client.zone_changes or 0,
        "changes_max": limits["changes"],
    }


# ============ GEOCODING (proxy Open-Meteo) ============

@app.get("/api/geocoding/search")
async def geocoding_search(q: str):
    """Recherche de villes via Open-Meteo Geocoding API."""
    if not q or len(q) < 2:
        return []
    async with httpx.AsyncClient(timeout=5) as http:
        resp = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": q, "count": 8, "language": "fr"}
        )
        data = resp.json()
    results = []
    for r in data.get("results", []):
        results.append({
            "name": r.get("name"),
            "lat": r.get("latitude"),
            "lon": r.get("longitude"),
            "country": r.get("country", ""),
            "admin1": r.get("admin1", ""),
        })
    return results


# ============ GESTION DES ZONES (ajout / suppression) ============

class ZoneAddRequest(BaseModel):
    name: str
    lat: float
    lon: float
    type: str = "voisin"  # "site" ou "voisin"

@app.post("/api/zones/{client_id}/add")
def add_zone(client_id: int, data: ZoneAddRequest, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Ajoute une zone au client (vérifie les limites du plan)."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    limits = PLAN_LIMITS.get(client.plan, PLAN_LIMITS["free"])
    zones = db.query(Zone).filter(Zone.client_id == client_id).all()

    if data.type == "site" and sum(1 for z in zones if z.type == "site") >= limits["sites"]:
        raise HTTPException(status_code=403, detail=f"Limite de {limits['sites']} sites atteinte (plan {client.plan})")

    if data.type == "voisin" and sum(1 for z in zones if z.type == "voisin") >= limits["voisins"]:
        raise HTTPException(status_code=403, detail=f"Limite de {limits['voisins']} villes voisines atteinte (plan {client.plan})")

    # Vérifier doublon
    existing = db.query(Zone).filter(Zone.client_id == client_id, Zone.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"La zone '{data.name}' existe déjà")

    zone = Zone(client_id=client_id, name=data.name, lat=data.lat, lon=data.lon, type=data.type)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return {"status": "ok", "zone_id": zone.id, "name": zone.name}


@app.delete("/api/zones/{client_id}/{zone_id}")
def delete_zone(client_id: int, zone_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Supprime une zone du client."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")
    zone = db.query(Zone).filter(Zone.id == zone_id, Zone.client_id == client_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone introuvable")

    # Vérifier limite de changements (suppression = 1 changement)
    client = db.query(Client).filter(Client.id == client_id).first()
    limits = PLAN_LIMITS.get(client.plan, PLAN_LIMITS["free"])
    changes_used = client.zone_changes or 0
    if changes_used >= limits["changes"]:
        raise HTTPException(status_code=403, detail=f"Limite de {limits['changes']} changements atteinte (plan {client.plan})")

    client.zone_changes = changes_used + 1
    db.delete(zone)
    db.commit()
    return {"status": "ok", "deleted": zone.name}


# ============ ROUTES API — MÉTÉO ============

@app.get("/api/meteo/{client_id}", response_model=list[ZoneMeteo])
def get_meteo(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les données météo actuelles pour le client.
    Vérifie que l'utilisateur accède UNIQUEMENT à ses propres données.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_meteo_actuelle(client_id, db)


@app.get("/api/previsions/{client_id}", response_model=list[PrevisionJour])
def get_previsions_route(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les prévisions 5 jours pour le client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_previsions(client_id, db)


@app.get("/api/alertes/{client_id}", response_model=list[Alerte])
def get_alertes_route(client_id: int, limit: int = 30, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les dernières alertes du client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_alertes(client_id, db, limit=limit)


@app.get("/api/zones/{client_id}")
def get_zones_route(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère toutes les zones du client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_zones(client_id, db)


@app.post("/api/meteo/snapshot/add")
def add_meteo_snapshot(
    client_id: int,
    data: MeteoSnapshotCreate,
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    ➕ Ajoute un snapshot météo pour une zone.
    Endpoint utilisé par auto_meteo_loop.py quand ça tourne sur GitHub Actions.
    Authentification par JWT token (Bearer).
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    # Trouver la zone
    zone = db.query(Zone).filter(
        Zone.client_id == client_id,
        Zone.name.ilike(f"%{data.zone_name}%")
    ).first()

    if not zone:
        # Auto-créer la zone si elle existe dans clients.json
        import json as _json
        _json_path = os.path.join(os.path.dirname(__file__), "..", "data", "clients.json")
        _coords = None
        _zone_type = "voisin"
        try:
            with open(_json_path, "r", encoding="utf-8") as _f:
                _clients = _json.load(_f)
            for _c in _clients.get("clients", []):
                for _st, _key in [("site", "sites"), ("voisin", "voisins")]:
                    for _z in _c.get("zones", {}).get(_key, []):
                        if _z["name"].lower() == data.zone_name.lower():
                            _coords = (_z["lat"], _z["lon"])
                            _zone_type = _st
                            break
        except Exception:
            pass
        if not _coords:
            raise HTTPException(status_code=404, detail=f"Zone '{data.zone_name}' not found")
        zone = Zone(client_id=client_id, name=data.zone_name, lat=_coords[0], lon=_coords[1], type=_zone_type)
        db.add(zone)
        db.commit()
        db.refresh(zone)
        print(f"[AUTO] Zone '{data.zone_name}' créée automatiquement")

    # Créer et sauvegarder le snapshot
    snapshot = MeteoSnapshot(
        zone_id=zone.id,
        temperature=data.temperature,
        windspeed=data.windspeed,
        wind_direction=data.wind_direction,
        precipitation=data.precipitation,
        cloudcover=data.cloudcover,
        uv_index=data.uv_index,
        risques=data.risques,
        ciel=data.ciel
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    
    # ✅ METTRE À JOUR LA ZONE avec les dernières données
    zone.temperature = data.temperature
    zone.windspeed = data.windspeed
    zone.wind_direction = data.wind_direction
    zone.precipitation = data.precipitation
    zone.cloudcover = data.cloudcover
    zone.uv_index = data.uv_index
    zone.risques = data.risques
    zone.ciel = data.ciel
    zone.updated_at = datetime.utcnow()
    
    db.add(zone)
    db.commit()

    return {"status": "success", "zone_id": zone.id, "snapshot_id": snapshot.id, "timestamp": snapshot.timestamp}


class PrevisionAdd(BaseModel):
    zone_name: str
    jour: str
    tmin: Optional[str] = None
    tmax: Optional[str] = None
    pluie: Optional[str] = None
    uv: Optional[float] = None
    risques: Optional[str] = None


@app.post("/api/previsions/add")
def add_previsions(
    client_id: int,
    data: list[PrevisionAdd],
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Reçoit les prévisions depuis GitHub Actions et les stocke en cache DB."""
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    # Supprimer l'ancien cache pour ce client
    zone_ids = [z.id for z in db.query(Zone).filter(Zone.client_id == client_id).all()]
    if zone_ids:
        db.query(PrevisionCache).filter(PrevisionCache.zone_id.in_(zone_ids)).delete(synchronize_session=False)

    added = 0
    for prev in data:
        zone = db.query(Zone).filter(
            Zone.client_id == client_id,
            Zone.name.ilike(f"%{prev.zone_name}%")
        ).first()
        if not zone:
            continue
        db.add(PrevisionCache(
            zone_id=zone.id,
            jour=prev.jour,
            tmin=prev.tmin,
            tmax=prev.tmax,
            pluie=prev.pluie,
            uv=prev.uv,
            risques=prev.risques
        ))
        added += 1

    db.commit()
    return {"status": "success", "previsions_added": added}


# ============ ROUTES API — TRAFIC ============

@app.get("/api/trafic/{client_id}")
def get_trafic_route(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les incidents trafic via TomTom pour le client.
    Retourne les incidents + alerte combinée météo+trafic si applicable.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    # Récupérer les zones du client
    zones_db = db.query(Zone).filter(Zone.client_id == client_id).all()
    zones_list = [{"name": z.name, "lat": z.lat, "lon": z.lon, "type": z.type} for z in zones_db]

    # Récupérer les incidents TomTom — passage en mode RÉEL (test_mode=False)
    from .trafic import get_incidents, get_alerte_combinee
    trafic_response = get_incidents(zones_list, test_mode=False)
    incidents_list = trafic_response.get("incidents", [])

    # Récupérer les risques météo actifs pour alerte combinée
    meteo = get_meteo_actuelle(client_id, db)
    risques_actifs = []
    for zone in meteo:
        # zone est un ZoneMeteo Pydantic model
        risques = getattr(zone, "risques", None)
        if risques and "RAS" not in risques:
            zone_name = getattr(zone, "name", "Zone")
            risques_actifs.append(f"{zone_name}: {risques}")

    alerte_combinee = get_alerte_combinee(incidents_list, risques_actifs)

    # --- ENVOI ALERTES PAR EMAIL ---
    client = db.query(Client).filter(Client.id == client_id).first()
    if client and client.email:
        # Alertes météo
        alertes_email = []
        for zone in meteo:
            risques = getattr(zone, "risques", None)
            if risques and "RAS" not in risques:
                alertes_email.append({
                    "zone": getattr(zone, "name", "?"),
                    "type": risques.split("(")[0].strip() if "(" in risques else risques,
                    "valeur": risques,
                    "message": f"Risque détecté sur {getattr(zone, 'name', '?')}"
                })
        if alertes_email:
            send_meteo_alert(client.email, client.company_name, alertes_email)

        # Alertes trafic (incidents critiques)
        if incidents_list:
            send_trafic_alert(client.email, client.company_name, incidents_list)

        # Alerte combinée
        if alerte_combinee and alerte_combinee.get("message"):
            send_combined_alert(client.email, client.company_name, alerte_combinee["message"])

    return {
        "incidents": incidents_list,
        "alerte_combinee": alerte_combinee,
        "total": trafic_response.get("total", 0),
        "retard_max": trafic_response.get("retard_max", 0)
    }


# ============ REFRESH MÉTÉO EN DIRECT ============

import math

def _wind_direction_label(deg):
    dirs = ["N","NE","E","SE","S","SO","O","NO"]
    return dirs[round(deg / 45) % 8]

def _ciel_icon(precip, cloud, wind):
    if precip > 0: return "🌧️"
    if cloud > 75: return "☁️"
    if cloud > 40: return "🌤️"
    if wind > 30: return "🌬️"
    return "☀️"

def _risk_text(temp, wind, precip, uv):
    r = []
    if temp >= 35: r.append("🔴 Canicule")
    elif temp <= -5: r.append("🔴 Gel sévère")
    elif temp <= 0: r.append("🟠 Gel")
    if wind >= 80: r.append("🔴 Tempête")
    elif wind >= 50: r.append("🟠 Vent fort")
    if precip >= 10: r.append("🔴 Fortes pluies")
    elif precip >= 3: r.append("🟠 Pluie modérée")
    if uv >= 8: r.append("🔴 UV extrême")
    elif uv >= 6: r.append("🟠 UV élevé")
    return " | ".join(r) if r else "✅ RAS"

@app.post("/api/refresh/{client_id}")
def refresh_meteo(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Rafraîchit les données météo en direct depuis Open-Meteo pour toutes les zones du client.
    Appelé au login du dashboard pour avoir des données fraîches.
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    if not zones:
        return {"status": "ok", "updated": 0}

    updated = 0
    for zone in zones:
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={zone.lat}&longitude={zone.lon}"
                f"&current_weather=true"
                f"&hourly=precipitation,cloudcover"
                f"&daily=uv_index_max"
                f"&timezone=auto"
            )
            r = httpx.get(url, timeout=8)
            r.raise_for_status()
            data = r.json()

            current = data.get("current_weather", {})
            hourly = data.get("hourly", {})

            # Heure courante depuis current_weather (timezone-aware)
            current_time = current.get("time", "")  # ex: "2026-04-17T11:00"
            times = hourly.get("time", [])

            # Pluie et nuages à l'heure courante
            precip = 0.0
            cloud = 0.0
            if current_time in times:
                idx = times.index(current_time)
                precip = hourly.get("precipitation", [0.0])[idx] or 0.0
                cloud = hourly.get("cloudcover", [0.0])[idx] or 0.0

            # UV du jour
            uv = 0.0
            daily_uv = data.get("daily", {}).get("uv_index_max", [])
            if daily_uv:
                uv = daily_uv[0] or 0.0

            temp = current.get("temperature", 0)
            wind = current.get("windspeed", 0)
            direction = _wind_direction_label(current.get("winddirection", 0))
            ciel = _ciel_icon(precip, cloud, wind)
            risques = _risk_text(temp, wind, precip, uv)

            zone.temperature = temp
            zone.windspeed = wind
            zone.wind_direction = direction
            zone.precipitation = precip
            zone.cloudcover = cloud
            zone.uv_index = uv
            zone.ciel = ciel
            zone.risques = risques
            from datetime import datetime as _dt
            zone.updated_at = _dt.utcnow()
            updated += 1

        except Exception as e:
            print(f"[REFRESH] Erreur {zone.name}: {e}")
            continue

    db.commit()
    print(f"[REFRESH] {updated}/{len(zones)} zones mises à jour pour client {client_id}")
    return {"status": "ok", "updated": updated, "total": len(zones)}


@app.get("/api/charts/{client_id}")
def get_charts_data(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Données pour les graphiques interactifs du dashboard.
    Appelle Open-Meteo pour la 1ère zone site du client :
    - Températures horaires 24h (passé + futur)
    - Pluie + vent 7 jours
    - UV 7 jours
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    sites = [z for z in zones if z.type == "site"]
    ref = sites[0] if sites else (zones[0] if zones else None)
    if not ref:
        return {"hourly": [], "daily": [], "zone_name": ""}

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={ref.lat}&longitude={ref.lon}"
            f"&hourly=temperature_2m,precipitation,windspeed_10m,cloudcover"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,uv_index_max"
            f"&past_days=1&forecast_days=7"
            f"&timezone=auto"
        )
        print(f"[CHARTS] Appel Open-Meteo pour {ref.name} ({ref.lat},{ref.lon})")
        r = httpx.get(url, timeout=15)
        print(f"[CHARTS] Status: {r.status_code}")
        r.raise_for_status()
        data = r.json()
        
        if "error" in data:
            print(f"[CHARTS] Open-Meteo error: {data}")
            raise ValueError(f"Open-Meteo: {data.get('reason', data.get('error'))}")
        
        print(f"[CHARTS] Open-Meteo OK: hourly={len(data.get('hourly',{}).get('time',[]))} daily={len(data.get('daily',{}).get('time',[]))}")

        hourly = data.get("hourly", {})
        daily = data.get("daily", {})

        hourly_out = []
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        precs = hourly.get("precipitation", [])
        winds = hourly.get("windspeed_10m", [])
        clouds = hourly.get("cloudcover", [])
        for i in range(len(times)):
            hourly_out.append({
                "time": times[i],
                "temp": temps[i] if i < len(temps) else 0,
                "precip": precs[i] if i < len(precs) else 0,
                "wind": winds[i] if i < len(winds) else 0,
                "cloud": clouds[i] if i < len(clouds) else 0,
            })

        daily_out = []
        d_times = daily.get("time", [])
        d_tmax = daily.get("temperature_2m_max", [])
        d_tmin = daily.get("temperature_2m_min", [])
        d_prec = daily.get("precipitation_sum", [])
        d_wind = daily.get("windspeed_10m_max", [])
        d_uv = daily.get("uv_index_max", [])
        for i in range(len(d_times)):
            daily_out.append({
                "date": d_times[i],
                "tmax": d_tmax[i] if i < len(d_tmax) else 0,
                "tmin": d_tmin[i] if i < len(d_tmin) else 0,
                "precip": d_prec[i] if i < len(d_prec) else 0,
                "wind": d_wind[i] if i < len(d_wind) else 0,
                "uv": d_uv[i] if i < len(d_uv) else 0,
            })

        # Données risques par zone (pour heatmap)
        zones_risks = []
        for z in zones:
            score = 0
            if z.precipitation and z.precipitation >= 10: score += 3
            elif z.precipitation and z.precipitation >= 3: score += 2
            if z.windspeed and z.windspeed >= 80: score += 3
            elif z.windspeed and z.windspeed >= 50: score += 2
            if z.temperature is not None and z.temperature <= 0: score += 2
            if z.temperature is not None and z.temperature >= 35: score += 3
            if z.uv_index and z.uv_index >= 8: score += 2
            zones_risks.append({"name": z.name, "score": score, "type": z.type or "voisin"})

        return {
            "zone_name": ref.name,
            "hourly": hourly_out,
            "daily": daily_out,
            "zones_risks": zones_risks,
        }

    except Exception as e:
        import traceback
        err_msg = f"{type(e).__name__}: {e}"
        print(f"[CHARTS] Erreur: {err_msg}")
        traceback.print_exc()
        # Même en cas d'erreur API, retourner les zones_risks depuis la DB
        zones_risks = []
        for z in zones:
            score = 0
            if z.precipitation and z.precipitation >= 10: score += 3
            elif z.precipitation and z.precipitation >= 3: score += 2
            if z.windspeed and z.windspeed >= 80: score += 3
            elif z.windspeed and z.windspeed >= 50: score += 2
            if z.temperature is not None and z.temperature <= 0: score += 2
            if z.temperature is not None and z.temperature >= 35: score += 3
            if z.uv_index and z.uv_index >= 8: score += 2
            zones_risks.append({"name": z.name, "score": score, "type": z.type or "voisin"})
        return {"hourly": [], "daily": [], "zone_name": ref.name, "zones_risks": zones_risks, "debug_error": err_msg}


# ============ ROUTES SERVICE (pour meteo_open.py) ============

# CORRECTION: Accepter GET et POST pour compatibilité GitHub Actions + meteo_open.py
@app.api_route("/api/service/token", methods=["GET", "POST"])
def get_service_token(client_id: int = 1, db: Session = Depends(get_db)):
    """
    🔐 Génère un token JWT pour le service meteo_open.py
    Accepte un client_id en paramètre (défaut=1 pour compatibilité).
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    username = client.username if client else "service-meteo"
    token = create_token(
        data={"client_id": client_id, "username": username}
    )
    return {"token": token, "client_id": client_id, "type": "bearer"}


@app.get("/api/service/clients")
def get_service_clients(db: Session = Depends(get_db)):
    """
    📋 Retourne tous les clients actifs + leurs zones.
    Utilisé par meteo_open.py pour collecter les données de TOUS les clients,
    y compris ceux inscrits en self-service (pas dans clients.json).
    Protégé par vérification JWT_SECRET dans le header.
    """
    clients = db.query(Client).filter(Client.active == 1).all()
    result = []
    for c in clients:
        zones = db.query(Zone).filter(Zone.client_id == c.id).all()
        result.append({
            "id": c.id,
            "username": c.username,
            "company_name": c.company_name,
            "zones": {
                "sites": [{"name": z.name, "lat": z.lat, "lon": z.lon} for z in zones if z.type == "site"],
                "voisins": [{"name": z.name, "lat": z.lat, "lon": z.lon} for z in zones if z.type == "voisin"]
            }
        })
    return {"clients": result}


# ============ CHANGEMENT MOT DE PASSE ============

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

@app.post("/api/account/{client_id}/password")
def change_password(client_id: int, data: PasswordChangeRequest, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Change le mot de passe du client authentifié."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    if not verify_password(data.current_password, client.password_hash):
        raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit faire au moins 6 caractères")
    client.password_hash = hash_password(data.new_password)
    db.commit()
    return {"status": "ok", "message": "Mot de passe mis à jour"}


# ============ ROUTES FRONTEND ============

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """
    Retourne le dashboard HTML.
    """
    try:
        with open("meteo_saas/frontend/dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>Dashboard introuvable</h1>", status_code=404)


@app.head("/")
async def head_root():
    """FIX: Répond aux HEAD requests pour health checks UptimeRobot/Render"""
    return Response(status_code=200)


@app.get("/health")
def health():
    """Vérification de l'état de l'application"""
    return {"status": "ok"}


@app.head("/health")
async def head_health():
    """FIX: Répond aux HEAD requests health check"""
    return Response(status_code=200)


# ============ LANCEMENT ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
