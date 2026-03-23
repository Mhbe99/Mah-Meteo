# -*- coding: utf-8 -*-
"""
main.py — Application FastAPI principale
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .database import get_db, init_db, init_clients_from_json, SessionLocal, Client, Zone
from .auth import create_token, verify_password, get_current_client
from .models import LoginRequest, TokenResponse, ZoneMeteo, PrevisionJour, TrafficIncident as TrafficIncidentModel, Alerte
from .clients import get_meteo_actuelle, get_previsions, get_alertes, get_zones
from .trafic import get_incidents

load_dotenv()


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
    allow_origins=["http://localhost", "http://localhost:8000", "http://127.0.0.1:8000"],
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


@app.get("/health")
def health():
    """Vérification de l'état de l'application"""
    return {"status": "ok"}


# ============ LANCEMENT ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
