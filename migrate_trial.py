#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration script: Ajoute la colonne trial_expires_at à la table clients
"""

import os
import sys
from datetime import datetime
from sqlalchemy import text, inspect
from dotenv import load_dotenv

# Importer les configs
sys.path.insert(0, os.path.dirname(__file__))
from meteo_saas.backend.database import engine, SessionLocal, Client, Base

load_dotenv()

def migrate():
    """Ajoute la colonne trial_expires_at si elle n'existe pas."""
    
    # Vérifier si on utilise SQLite ou PostgreSQL
    db_url = os.getenv("DATABASE_URL", "sqlite:///./meteo_saas.db")
    
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            columns = [c['name'] for c in inspector.get_columns('clients')]
            
            if 'trial_expires_at' not in columns:
                print("🔄 Ajout de la colonne trial_expires_at...")
                
                if "postgresql" in db_url:
                    sql = text("ALTER TABLE clients ADD COLUMN trial_expires_at TIMESTAMP NULL")
                else:  # SQLite
                    sql = text("ALTER TABLE clients ADD COLUMN trial_expires_at TIMESTAMP")
                
                conn.execute(sql)
                conn.commit()
                print("✅ Colonne trial_expires_at ajoutée avec succès")
            else:
                print("ℹ️  Colonne trial_expires_at déjà présente")
                
    except Exception as e:
        print(f"❌ Erreur migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🗄️  Migration base de données...")
    migrate()
    print("✅ Migration terminée")
