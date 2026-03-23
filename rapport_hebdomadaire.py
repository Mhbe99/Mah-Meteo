#!/usr/bin/env python3
"""
Script de rapport hebdomadaire des risques météo
Généré chaque lundi matin avec :
- Récapitulatif des alertes par jour/heure
- Graphiques et statistiques
- Envoi par email
"""

import json
import os
import datetime
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.encoders import encode_base64
import smtplib
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS").split(",")

# Paths
HISTORIQUE_FILE = os.path.join("exports", "alertes_historique.json")
EXPORT_PATH = "exports"
RAPPORT_FILE = os.path.join(EXPORT_PATH, "rapport_hebdomadaire.xlsx")

# --- Sites pour prévisions (mêmes sites que le dashboard) ---
SITES = {
    "Le Meux 🏣": {"lat": 49.378829, "lon": 2.750393},
    "Clairoix 🏣": {"lat": 49.4194, "lon": 2.8328},
}

def charger_historique():
    """Charger l'historique complet des alertes"""
    if os.path.exists(HISTORIQUE_FILE):
        try:
            with open(HISTORIQUE_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as e:
            print(f"❌ Erreur chargement historique: {e}")
    return []

def get_semaine_precedente():
    """Retourner la date de début et fin de la semaine précédente (lundi-dimanche)"""
    today = datetime.datetime.now()
    # Lundi de la semaine précédente
    jours_avant = (today.weekday() + 7) % 7
    lundi = today - datetime.timedelta(days=jours_avant + 7)
    dimanche = lundi + datetime.timedelta(days=6)
    return lundi.date(), dimanche.date()

def filtrer_semaine(alertes):
    """Filtrer les alertes de la semaine précédente"""
    lundi, dimanche = get_semaine_precedente()
    alertes_semaine = []
    
    for alerte in alertes:
        try:
            date_alerte = datetime.datetime.fromisoformat(alerte["timestamp"]).date()
            if lundi <= date_alerte <= dimanche:
                alertes_semaine.append(alerte)
        except:
            pass
    
    return alertes_semaine

def generer_statistiques(alertes_semaine):
    """Générer les statistiques des alertes"""
    stats = {
        "total_alertes": len(alertes_semaine),
        "zones": defaultdict(int),
        "risques": defaultdict(int),
        "par_jour": defaultdict(int),
        "par_heure": defaultdict(int),
        "par_zone_heure": defaultdict(lambda: defaultdict(int))
    }
    
    for alerte in alertes_semaine:
        zone = alerte.get("zone", "Inconnue")
        jour = alerte.get("jour_semaine", "?")
        heure = alerte.get("heure", "?")
        risques_str = alerte.get("risques", "")
        
        stats["zones"][zone] += 1
        stats["par_jour"][jour] += 1
        stats["par_heure"][heure] += 1
        stats["par_zone_heure"][zone][heure] += 1
        
        # Comptabiliser les risques individuels
        for risque in ["Verglas", "Vent fort", "Alerte pluie", "UV fort"]:
            if risque in risques_str:
                stats["risques"][risque] += 1
    
    return stats


def get_risk_icons(temp, wind, rain, uv):
    """Petit heuristique pour identifier les risques (copie légère)."""
    risk = []
    try:
        t = float(temp)
        r = float(rain)
        if t < 1 and r > 0 and datetime.datetime.now().month in [11, 12, 1, 2]:
            risk.append("❄️ Verglas")
    except:
        pass
    if wind is not None and float(wind) > 40:
        risk.append("💨 Vent fort")
    if rain is not None and float(rain) > 5:
        risk.append("🌧️ Alerte pluie")
    if uv is not None and float(uv) >= 8:
        risk.append("🔥 UV fort")
    return " | ".join(risk) if risk else "✅ RAS"


def fetch_previsions_5j(sites, jours=5):
    """Récupère les prévisions journalières (jours prochains) pour les sites fournis.

    Retourne dict: {site: [ {jour,tmin,tmax,pluie,uv,risk}, ... ] }
    """
    result = {site: [] for site in sites}
    for site, coord in sites.items():
        lat, lon = coord.get("lat"), coord.get("lon")
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max&timezone=auto"
        )
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            days = data.get("daily", {})
            times = days.get("time", [])
            for i in range(min(len(times), jours)):
                date = datetime.datetime.strptime(times[i], "%Y-%m-%d").strftime("%a %d/%m")
                tmin = days.get('temperature_2m_min', [None])[i]
                tmax = days.get('temperature_2m_max', [None])[i]
                pluie = days.get('precipitation_sum', [0])[i]
                uv = days.get('uv_index_max', [0])[i]
                risk = get_risk_icons(tmin if tmin is not None else 0, 0, pluie, uv)
                result[site].append({
                    "jour": date,
                    "tmin": f"{tmin}\u00b0C" if tmin is not None else "N/A",
                    "tmax": f"{tmax}\u00b0C" if tmax is not None else "N/A",
                    "pluie": f"{pluie} mm",
                    "uv": uv,
                    "risk": risk,
                })
        except Exception as e:
            print(f"⚠️ Erreur récupération prévisions pour {site}: {e}")
    return result

def envoyer_rapport_email(semaine_debut, semaine_fin, stats, rapport_file, previsions=None, dry_run=False):
    """Envoyer le rapport par email"""
    
    html_body = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; }}
            h2 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>📊 Rapport Hebdomadaire Météo - Risques Détectés</h1>
        <p><strong>Période :</strong> {semaine_debut} au {semaine_fin}</p>
        
        <h2>📈 Résumé</h2>
        <table>
            <tr><th>Métrique</th><th>Valeur</th></tr>
            <tr><td>Total alertes</td><td>{stats['total_alertes']}</td></tr>
            <tr><td>Zones affectées</td><td>{len(stats['zones'])}</td></tr>
            <tr><td>Types de risques</td><td>{len(stats['risques'])}</td></tr>
        </table>
        
        <h2>⚠️ Risques par type</h2>
        <table>
            <tr><th>Type de risque</th><th>Occurrences</th></tr>
    """
    
    for risque, count in sorted(stats['risques'].items(), key=lambda x: x[1], reverse=True):
        html_body += f"<tr><td>{risque}</td><td>{count}</td></tr>"
    
    html_body += """
        </table>
        
        <h2>🗺️ Zones les plus affectées</h2>
        <table>
            <tr><th>Zone</th><th>Alertes</th></tr>
    """
    
    for zone, count in sorted(stats['zones'].items(), key=lambda x: x[1], reverse=True):
        html_body += f"<tr><td>{zone}</td><td>{count}</td></tr>"
    
    html_body += """
        </table>
        
        <h2>🕐 Alertes par heure</h2>
        <table>
            <tr><th>Heure</th><th>Occurrences</th></tr>
    """
    
    for heure in sorted(stats['par_heure'].keys()):
        count = stats['par_heure'][heure]
        html_body += f"<tr><td>{heure}</td><td>{count}</td></tr>"
    
    html_body += """
        </table>
        
        <h2>🔮 Prévisions 5 jours (principaux sites)</h2>
        <table>
            <tr><th>Site</th><th>Jour</th><th>Tmin</th><th>Tmax</th><th>Pluie</th><th>UV</th><th>Risques</th></tr>
    """

    if previsions:
        for site, jours in previsions.items():
            for j in jours:
                html_body += f"<tr><td>{site}</td><td>{j['jour']}</td><td>{j['tmin']}</td><td>{j['tmax']}</td><td>{j['pluie']}</td><td>{j['uv']}</td><td>{j['risk']}</td></tr>"

    html_body += """
        </table>
        
        <p style="margin-top: 30px; font-size: 12px; color: #666;">
            ✅ Rapport généré automatiquement - Fichier Excel détaillé en pièce jointe
        </p>
    </body>
    </html>
    """
    
    # Créer le message
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECEIVER_EMAILS)
    msg["Subject"] = f"📊 Rapport Hebdomadaire Météo - {semaine_debut} au {semaine_fin}"
    
    # Ajouter le corps HTML
    msg.attach(MIMEText(html_body, "html"))
    
    # Ajouter le fichier Excel en pièce jointe
    if os.path.exists(rapport_file):
        try:
            with open(rapport_file, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(rapport_file)}")
                msg.attach(part)
        except Exception as e:
            print(f"⚠️ Erreur ajout pièce jointe: {e}")
    
    # Si dry_run, ne pas envoyer : sauvegarder HTML et le message MIME dans exports/
    if dry_run:
        try:
            os.makedirs(EXPORT_PATH, exist_ok=True)
            html_path = os.path.join(EXPORT_PATH, "test_email.html")
            eml_path = os.path.join(EXPORT_PATH, "test_email.eml")
            # Sauvegarder le corps HTML
            with open(html_path, "w", encoding="utf-8") as fh:
                fh.write(html_body)
            # Sauvegarder le message complet (MIME)
            with open(eml_path, "w", encoding="utf-8") as fh:
                fh.write(msg.as_string())
            print(f"✅ Dry-run : email sauvegardé dans {html_path} et {eml_path}")
            return True
        except Exception as e:
            print(f"❌ Erreur sauvegarde email dry-run: {e}")
            return False

    # Envoyer réellement
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, GMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print(f"✅ Rapport envoyé par email")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False

def generer_excel(alertes_semaine, stats):
    """Générer un fichier Excel avec le rapport détaillé"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        
        wb = Workbook()
        
        # === Onglet 1 : Résumé ===
        ws_resume = wb.active
        ws_resume.title = "Resumé"
        
        ws_resume.append(["📊 RAPPORT HEBDOMADAIRE DES RISQUES MÉTÉO"])
        ws_resume.append([])
        ws_resume.append(["Total alertes", stats['total_alertes']])
        ws_resume.append(["Zones affectées", len(stats['zones'])])
        ws_resume.append(["Types de risques", len(stats['risques'])])
        ws_resume.append([])
        
        ws_resume.append(["Type de risque", "Occurrences"])
        for risque, count in sorted(stats['risques'].items(), key=lambda x: x[1], reverse=True):
            ws_resume.append([risque, count])
        
        # === Onglet 2 : Détails par zone/heure ===
        ws_detail = wb.create_sheet("Heatmap Zone-Heure")
        ws_detail.append(["Zone", "00:00", "01:00", "02:00", "03:00", "04:00", "05:00", 
                         "06:00", "07:00", "08:00", "09:00", "10:00", "11:00", "12:00",
                         "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
                         "20:00", "21:00", "22:00", "23:00", "TOTAL"])
        
        for zone in sorted(stats['par_zone_heure'].keys()):
            row = [zone]
            total_zone = 0
            for h in range(24):
                heure = f"{h:02d}:00"
                count = stats['par_zone_heure'][zone].get(heure, 0)
                row.append(count)
                total_zone += count
            row.append(total_zone)
            ws_detail.append(row)
        
        # === Onglet 3 : Historique complet ===
        ws_historique = wb.create_sheet("Historique Complet")
        ws_historique.append(["Date", "Heure", "Zone", "Température", "Vent", "Pluie", "Risques"])
        
        for alerte in sorted(alertes_semaine, key=lambda x: x.get("timestamp", "")):
            ws_historique.append([
                alerte.get("date", ""),
                alerte.get("heure", ""),
                alerte.get("zone", ""),
                alerte.get("temp", ""),
                alerte.get("wind", ""),
                alerte.get("rain", ""),
                alerte.get("risques", "")
            ])
        
        # Ajuster largeurs
        for ws in [ws_resume, ws_detail, ws_historique]:
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                ws.column_dimensions[column_letter].width = min(max_length + 2, 50)
        
        os.makedirs(EXPORT_PATH, exist_ok=True)
        wb.save(RAPPORT_FILE)
        print(f"✅ Rapport Excel généré : {RAPPORT_FILE}")
        return True
    except Exception as e:
        print(f"❌ Erreur génération Excel: {e}")
        return False


def generer_excel_previsions(previsions):
    """Ajoute/écrit un fichier Excel séparé contenant les prévisions 5 jours."""
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Prévisions 5J"
        ws.append(["Site", "Jour", "Tmin", "Tmax", "Pluie", "UV", "Risques"])
        for site, jours in previsions.items():
            for j in jours:
                ws.append([site, j['jour'], j['tmin'], j['tmax'], j['pluie'], j['uv'], j['risk']])
        path = os.path.join(EXPORT_PATH, "previsions_5j.xlsx")
        wb.save(path)
        print(f"✅ Prévisions 5j exportées : {path}")
        return path
    except Exception as e:
        print(f"❌ Erreur export prévisions: {e}")
        return None

def main(dry_run=False, force_send=False):
    print("=" * 60)
    print("📊 RAPPORT HEBDOMADAIRE DES RISQUES MÉTÉO")
    print("=" * 60)
    
    # Charger historique
    alertes = charger_historique()
    print(f"\n📁 Historique total: {len(alertes)} alertes")
    
    # Filtrer semaine précédente
    alertes_semaine = filtrer_semaine(alertes)
    lundi, dimanche = get_semaine_precedente()
    
    print(f"📅 Semaine analysée: {lundi} au {dimanche}")
    print(f"⚠️ Alertes de la semaine: {len(alertes_semaine)}")
    
    if len(alertes_semaine) == 0:
        print("✅ Aucune alerte cette semaine!")
        if not dry_run and not force_send:
            return
    
    # Générer statistiques
    stats = generer_statistiques(alertes_semaine)
    # Récupérer prévisions 5 jours pour affichage dans le rapport
    print("\n🔎 Récupération des prévisions 5 jours...")
    previsions = fetch_previsions_5j(SITES, jours=5)
    
    # Générer Excel
    print("\n📄 Génération du rapport Excel...")
    generer_excel(alertes_semaine, stats)
    # ajouter un export séparé pour les prévisions
    previsions_file = generer_excel_previsions(previsions)
    
    # Envoyer par email
    print("\n📧 Envoi du rapport par email...")
    # joindre aussi le fichier prévisions si disponible
    envoyer_rapport_email(lundi, dimanche, stats, RAPPORT_FILE, previsions=previsions, dry_run=dry_run)
    
    print("\n" + "=" * 60)
    print("✅ Rapport hebdomadaire terminé")
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Générer rapport hebdomadaire météo")
    parser.add_argument("--dry-run", action="store_true", help="Forcer génération et sauvegarder l'email localement sans l'envoyer")
    parser.add_argument("--force-send", action="store_true", help="Forcer envoi de l'email même sans alertes")
    args = parser.parse_args()
    main(dry_run=args.dry_run, force_send=args.force_send)
