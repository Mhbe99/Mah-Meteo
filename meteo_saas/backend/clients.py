# -*- coding: utf-8 -*-
"""
clients.py — Logique métier pour clients (météo, prévisions, alertes)
"""

import json
import os
import requests
import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from .database import Zone, MeteoSnapshot, AlerteLog, Client
from .models import ZoneMeteo, PrevisionJour, Alerte, ZoneInfo


def get_meteo_actuelle(client_id: int, db: Session) -> List[ZoneMeteo]:
    """
    Récupère les données météo actuelles pour les zones du client.
    Utilise les données du dernier snapshot OU les données de la Zone elle-même.
    """
    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    result = []

    for zone in zones:
        # Option 1: Utiliser les données de la Zone (mise à jour quand snapshot ajouté)
        zone_meteo = ZoneMeteo(
            name=zone.name,
            type=zone.type,
            temp=zone.temperature,
            wind=zone.windspeed,
            direction=zone.wind_direction,
            ciel=zone.ciel,
            risques=zone.risques,
            precipitation=zone.precipitation,
            cloudcover=zone.cloudcover,
            uv_index=zone.uv_index,
            lat=zone.lat,
            lon=zone.lon,
            updated_at=zone.updated_at
        )

        result.append(zone_meteo)

    return result


def get_previsions(client_id: int, db: Session) -> List[PrevisionJour]:
    """
    Récupère les prévisions 5 jours pour les zones du client.
    Appelle directement l'API Open-Meteo (même logique que meteo_open.py).
    """
    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    result = []

    for zone in zones:
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={zone.lat}&longitude={zone.lon}"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max"
                f"&timezone=auto"
            )
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            days = data.get("daily", {})
            times = days.get("time", [])

            for i in range(min(len(times), 5)):  # 5 jours max
                date_str = times[i]
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                jour = date_obj.strftime("%a %d/%m")

                tmin = days.get("temperature_2m_min", [None])[i]
                tmax = days.get("temperature_2m_max", [None])[i]
                pluie = days.get("precipitation_sum", [0])[i]
                uv = days.get("uv_index_max", [0])[i]

                # Déterminer les risques (simplifié)
                risques = ""
                try:
                    if tmin is not None and tmin < 1 and pluie > 0 and datetime.datetime.now().month in [11, 12, 1, 2]:
                        risques += "❄️ Verglas "
                except:
                    pass
                if pluie > 5:
                    risques += "🌧️ Pluie "
                if uv >= 8:
                    risques += "🔥 UV "
                if not risques:
                    risques = "✅ RAS"

                prevision = PrevisionJour(
                    zone=zone.name,
                    jour=jour,
                    tmin=f"{tmin}°C" if tmin is not None else "N/A",
                    tmax=f"{tmax}°C" if tmax is not None else "N/A",
                    pluie=f"{pluie} mm",
                    uv=uv,
                    risques=risques.strip()
                )
                result.append(prevision)

        except Exception as e:
            print(f"❌ Erreur récupération prévisions pour {zone.name}: {e}")

    return result


def get_alertes(client_id: int, db: Session, limit: int = 30) -> List[Alerte]:
    """
    Récupère les dernières alertes du client.
    
    Démarche :
    1. Chercher dans alertes_log (DB) en priorité
    2. Si vide, lire exports/alertes_historique.json
    """
    
    # 1. Chercher dans la DB
    alertes_db = db.query(AlerteLog).filter(
        AlerteLog.client_id == client_id
    ).order_by(AlerteLog.timestamp.desc()).limit(limit).all()

    if alertes_db:
        return [
            Alerte(
                zone_name=a.zone_name,
                timestamp=a.timestamp,
                type_alerte=a.type_alerte,
                valeur=a.valeur,
                message=a.message
            )
            for a in alertes_db
        ]

    # 2. Fallback : lire exports/alertes_historique.json
    historique_path = "exports/alertes_historique.json"
    if os.path.exists(historique_path):
        try:
            with open(historique_path, "r", encoding="utf-8") as f:
                historique = json.load(f)

            alertes_list = []
            for alert_dict in historique[-limit:]:  # Derniers limite
                # Créer une Alerte depuis le dict (structure peut varier)
                alerte = Alerte(
                    zone_name=alert_dict.get("zone", "Inconnue"),
                    timestamp=datetime.datetime.fromisoformat(alert_dict.get("timestamp", datetime.datetime.utcnow().isoformat())),
                    type_alerte="détecté",
                    valeur=alert_dict.get("risques", "N/A"),
                    message=alert_dict.get("risques", "Alerte météo")
                )
                alertes_list.append(alerte)

            return alertes_list

        except Exception as e:
            print(f"⚠️ Erreur lecture alertes_historique.json: {e}")

    return []


def save_meteo_snapshot(zone_id: int, data: dict, db: Session) -> None:
    """
    Sauvegarde un snapshot météo en base.
    
    data dict attendu : {
        temperature, windspeed, wind_direction, precipitation,
        cloudcover, uv_index, risques, ciel
    }
    """
    snapshot = MeteoSnapshot(
        zone_id=zone_id,
        timestamp=datetime.datetime.utcnow(),
        temperature=data.get("temperature"),
        windspeed=data.get("windspeed"),
        wind_direction=data.get("wind_direction"),
        precipitation=data.get("precipitation"),
        cloudcover=data.get("cloudcover"),
        uv_index=data.get("uv_index"),
        risques=data.get("risques"),
        ciel=data.get("ciel")
    )
    db.add(snapshot)
    db.commit()


def get_zones(client_id: int, db: Session) -> List[ZoneInfo]:
    """Récupère toutes les zones d'un client"""
    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    return [
        ZoneInfo(
            id=z.id,
            name=z.name,
            lat=z.lat,
            lon=z.lon,
            type=z.type
        )
        for z in zones
    ]
