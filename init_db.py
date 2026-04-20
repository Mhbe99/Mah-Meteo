#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
init_db.py — Initialise la base de données et ajoute le client par défaut
"""

from meteo_saas.backend.database import Base, engine, SessionLocal, Client, Zone

# DROP toutes les tables et recréer
print("[1] DROP des anciennes tables...")
Base.metadata.drop_all(bind=engine)
print("[✅] Anciennes tables supprimées")

print("[2] Création des tables...")
Base.metadata.create_all(bind=engine)
print("[✅] Tables créées")

# Initialiser la BD avec un client par défaut
db = SessionLocal()

# Vérifier que GEODIS-LEMEUX existe
existing_client = db.query(Client).filter(Client.username == "service-meteo").first()

if existing_client:
    print(f"[✅] Client GEODIS-LEMEUX existe déjà (id={existing_client.id})")
else:
    print("[2] Création du client GEODIS-LEMEUX...")
    client = Client(
        username="service-meteo",
        password_hash="hashed_dummy_password",  # Dummy
        company_name="GEODIS-LEMEUX",
        email="mahmeteo@gmail.com",
        plan="pro",
        active=1
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    print(f"[✅] Client créé avec id={client.id}")

# Vérifier les zones
zones_count = db.query(Zone).count()
print(f"[ℹ️] Zones existantes : {zones_count}")

db.close()
print("[✅] DB initialisée et prête!")
