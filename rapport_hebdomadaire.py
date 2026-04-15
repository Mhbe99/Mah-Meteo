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
_receivers_raw = os.getenv("RECEIVER_EMAILS", "")
RECEIVER_EMAILS = [e.strip() for e in _receivers_raw.split(",") if e.strip()]
# TEST: forcer les destinataires pour validation
RECEIVER_EMAILS = ["mahame.toure@geodis.com", "mahmeteo@gmail.com"]
RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")

# Paths
EXPORT_PATH = "exports"
RAPPORT_FILE = os.path.join(EXPORT_PATH, "rapport_hebdomadaire.xlsx")

# --- Sites pour prévisions (mêmes sites que le dashboard) ---
SITES = {
    "Le Meux 🏣": {"lat": 49.378829, "lon": 2.750393},
    "Clairoix 🏣": {"lat": 49.4194, "lon": 2.8328},
}

def charger_historique():
    """Charger l'historique des alertes depuis l'API Render."""
    try:
        # Obtenir un token service
        r = requests.get(f"{RENDER_URL}/api/service/token", timeout=15)
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token") or data.get("token", "")

        # Récupérer les alertes de tous les clients
        rc = requests.get(f"{RENDER_URL}/api/service/clients",
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
        rc.raise_for_status()
        clients = rc.json().get("clients", [])

        alertes = []
        for client in clients:
            cid = client.get("id") or client.get("client_id")
            if not cid:
                continue
            # Token par client
            rt = requests.get(f"{RENDER_URL}/api/service/token?client_id={cid}", timeout=10)
            if rt.status_code != 200:
                continue
            td = rt.json()
            token_c = td.get("access_token") or td.get("token", "")
            ra = requests.get(f"{RENDER_URL}/api/alertes/{cid}?limit=500",
                              headers={"Authorization": f"Bearer {token_c}"}, timeout=15)
            if ra.status_code == 200:
                for a in ra.json():
                    # Harmoniser les champs pour la compatibilité avec filtrer_semaine
                    ts = a.get("timestamp") or a.get("created_at") or ""
                    alertes.append({
                        "timestamp": ts,
                        "date": ts[:10] if ts else "",
                        "heure": ts[11:16] if len(ts) > 15 else "",
                        "jour_semaine": datetime.datetime.fromisoformat(ts).strftime("%A") if ts else "",
                        "zone": a.get("zone_name", ""),
                        "risques": a.get("message", ""),
                        "temp": "",
                        "wind": "",
                        "rain": "",
                    })
        print(f"✅ {len(alertes)} alertes chargées depuis l'API")
        return alertes
    except Exception as e:
        print(f"❌ Erreur chargement alertes API: {e}")
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
    # TEST: retourne toutes les alertes pour valider l'envoi email
    return alertes

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
    
    # --- KPI cards ---
    kpi_html = f"""
    <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
        <div style="flex:1;min-width:120px;background:#ebf8ff;border-left:4px solid #3182ce;border-radius:4px;padding:12px 16px;">
            <div style="font-size:22px;font-weight:700;color:#2b6cb0;">{stats['total_alertes']}</div>
            <div style="font-size:12px;color:#4a5568;margin-top:2px;">Alertes totales</div>
        </div>
        <div style="flex:1;min-width:120px;background:#fff5f5;border-left:4px solid #e53e3e;border-radius:4px;padding:12px 16px;">
            <div style="font-size:22px;font-weight:700;color:#c53030;">{len(stats['zones'])}</div>
            <div style="font-size:12px;color:#4a5568;margin-top:2px;">Zones affectées</div>
        </div>
        <div style="flex:1;min-width:120px;background:#fffaf0;border-left:4px solid #d69e2e;border-radius:4px;padding:12px 16px;">
            <div style="font-size:22px;font-weight:700;color:#b7791f;">{len(stats['risques'])}</div>
            <div style="font-size:12px;color:#4a5568;margin-top:2px;">Types de risques</div>
        </div>
    </div>
    """

    # --- Tableau risques ---
    risques_rows = ""
    for risque, count in sorted(stats['risques'].items(), key=lambda x: x[1], reverse=True):
        risques_rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{risque}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;font-weight:600;color:#e53e3e;">{count}</td>
        </tr>"""

    # --- Tableau zones ---
    zones_rows = ""
    for zone, count in sorted(stats['zones'].items(), key=lambda x: x[1], reverse=True):
        zones_rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{zone}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;font-weight:600;color:#3182ce;">{count}</td>
        </tr>"""

    # --- Tableau prévisions ---
    prev_rows = ""
    if previsions:
        for site, jours in previsions.items():
            for j in jours:
                risk_color = "#e53e3e" if "❄️" in j['risk'] or "💨" in j['risk'] or "🌧️" in j['risk'] else "#38a169"
                prev_rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{site}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{j['jour']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{j['tmin']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{j['tmax']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{j['pluie']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;font-weight:600;color:{risk_color};">{j['risk']}</td>
        </tr>"""

    from datetime import datetime as _dt
    now_str = _dt.now().strftime('%d/%m/%Y %H:%M')

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:620px;margin:32px auto;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">

  <!-- Header -->
  <div style="background:#2c3e50;padding:20px 24px;">
    <div style="font-size:11px;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Mah Météo</div>
    <h1 style="margin:0;font-size:18px;color:#fff;font-weight:600;">📊 Rapport Hebdomadaire des Risques Météo</h1>
    <p style="margin:6px 0 0 0;font-size:13px;color:#90cdf4;">Semaine du {semaine_debut} au {semaine_fin}</p>
  </div>

  <!-- Body -->
  <div style="padding:24px;">

    <!-- KPIs -->
    {kpi_html}

    <!-- Risques par type -->
    <h3 style="margin:20px 0 10px 0;font-size:14px;color:#2d3748;border-bottom:2px solid #f0f4f8;padding-bottom:6px;">⚠️ Risques par type</h3>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:4px;overflow:hidden;">
      <thead>
        <tr style="background:#f7fafc;">
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Type de risque</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Occurrences</th>
        </tr>
      </thead>
      <tbody>{risques_rows if risques_rows else '<tr><td colspan="2" style="padding:10px 12px;font-size:13px;color:#a0aec0;">Aucun risque détecté</td></tr>'}</tbody>
    </table>

    <!-- Zones -->
    <h3 style="margin:20px 0 10px 0;font-size:14px;color:#2d3748;border-bottom:2px solid #f0f4f8;padding-bottom:6px;">🗺️ Zones les plus affectées</h3>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:4px;overflow:hidden;">
      <thead>
        <tr style="background:#f7fafc;">
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Zone</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Alertes</th>
        </tr>
      </thead>
      <tbody>{zones_rows if zones_rows else '<tr><td colspan="2" style="padding:10px 12px;font-size:13px;color:#a0aec0;">Aucune zone affectée</td></tr>'}</tbody>
    </table>

    <!-- Prévisions -->
    <h3 style="margin:20px 0 10px 0;font-size:14px;color:#2d3748;border-bottom:2px solid #f0f4f8;padding-bottom:6px;">🔮 Prévisions 5 jours</h3>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:4px;overflow:hidden;">
      <thead>
        <tr style="background:#f7fafc;">
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Site</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Jour</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Tmin</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Tmax</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Pluie</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Risques</th>
        </tr>
      </thead>
      <tbody>{prev_rows if prev_rows else '<tr><td colspan="6" style="padding:10px 12px;font-size:13px;color:#a0aec0;">Aucune prévision disponible</td></tr>'}</tbody>
    </table>

    <p style="margin-top:20px;font-size:12px;color:#a0aec0;">📎 Rapport Excel détaillé en pièce jointe.</p>
  </div>

  <!-- Footer -->
  <div style="padding:14px 24px;background:#f7fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#a0aec0;">
    Envoyé automatiquement par Mah Météo — {now_str}<br>Ne pas répondre à cet email.
  </div>

</div>
</body>
</html>"""
    
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
