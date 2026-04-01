# -*- coding: utf-8 -*-
"""
main.py — Application FastAPI principale
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .database import get_db, init_db, init_clients_from_json, SessionLocal, Client, Zone, MeteoSnapshot, PrevisionCache
from .auth import create_token, verify_password, get_current_client
from .models import LoginRequest, TokenResponse, ZoneMeteo, PrevisionJour, TrafficIncident as TrafficIncidentModel, Alerte
from pydantic import BaseModel
from typing import Optional
from .clients import get_meteo_actuelle, get_previsions, get_alertes, get_zones
from .trafic import get_incidents

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

# ============ CORS ============

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "https://mah-meteo.onrender.com",  # Allow Render production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ ROUTES AUTHENTIFICATION ============

@app.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authentification utilisateur.
    Retourne un JWT valide 24h.
    """
    # Chercher le client
    client = db.query(Client).filter(Client.username == request.username).first()
    
    if not client or not verify_password(request.password, client.password_hash):
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

    return {
        "incidents": incidents_list,
        "alerte_combinee": alerte_combinee,
        "total": trafic_response.get("total", 0),
        "retard_max": trafic_response.get("retard_max", 0)
    }


# ============ ROUTES SERVICE (pour meteo_open.py) ============

# CORRECTION: Accepter GET et POST pour compatibilité GitHub Actions + meteo_open.py
@app.api_route("/api/service/token", methods=["GET", "POST"])
def get_service_token():
    """
    🔐 Génère un token JWT pour le service meteo_open.py
    Accepte GET et POST pour compatibilité avec GitHub Actions et meteo_open.py
    
    GET  : curl https://mah-meteo.onrender.com/api/service/token
    POST : curl -X POST https://mah-meteo.onrender.com/api/service/token
    """
    # Créer un token avec client_id=1 (GEODIS) pour le service
    token = create_token(
        data={"client_id": 1, "username": "service-meteo"}
    )
    return {"token": token, "client_id": 1, "type": "bearer"}


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
