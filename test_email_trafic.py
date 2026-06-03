# -*- coding: utf-8 -*-
"""
test_email_trafic.py — Envoie un email de test trafic avec des incidents RÉELS
depuis le cache TomTom ou des données fictives réalistes.

Usage:
    python test_email_trafic.py                  # données réelles depuis cache
    python test_email_trafic.py --fake           # données fictives
    python test_email_trafic.py --render         # tire les données depuis l'API Render
"""
import os
import sys
import json
import smtplib
import datetime
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

# ── Incidents fictifs réalistes (région Compiègne/Oise) ──────────────────────
FAKE_INCIDENTS = [
    {
        "route": "A1 — Compiègne Sud → Ressons-sur-Matz",
        "description": "Accident impliquant 2 véhicules",
        "severity": "high",
        "delay_minutes": 25,
        "icon": "[CRASH]",
        "lat": 49.38, "lon": 2.75,
        "zone_source": "Le Meux 🏣"
    },
    {
        "route": "N31 — Clermont → Breteuil",
        "description": "Bouchon suite à accident",
        "severity": "high",
        "delay_minutes": 18,
        "icon": "[TRAFFIC]",
        "lat": 49.37, "lon": 2.42,
        "zone_source": "Clermont 🏣"
    },
    {
        "route": "D200 — Verberie → Pont-Sainte-Maxence",
        "description": "Travaux — voie droite neutralisée",
        "severity": "med",
        "delay_minutes": 10,
        "icon": "[WORK]",
        "lat": 49.31, "lon": 2.73,
        "zone_source": "Verberie"
    },
    {
        "route": "D1017 — Margny-lès-Compiègne → Clairoix",
        "description": "Route fermée — câbles tombés",
        "severity": "high",
        "delay_minutes": 0,
        "icon": "[CLOSED]",
        "lat": 49.43, "lon": 2.82,
        "zone_source": "Clairoix 🏣"
    },
]

# ── Charger depuis le cache local ─────────────────────────────────────────────
def load_from_cache():
    cache_file = "exports/trafic_cache.json"
    if not os.path.exists(cache_file):
        print("[CACHE] Fichier cache introuvable")
        return None
    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    incidents = data.get("incidents", [])
    ts = data.get("timestamp", 0)
    age_min = ((__import__("time").time() - ts) / 60) if ts else 999
    print(f"[CACHE] {len(incidents)} incidents dans le cache (age: {age_min:.0f} min)")
    return incidents

# ── Charger depuis l'API Render ───────────────────────────────────────────────
def load_from_render():
    render_url = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
    jwt_secret = os.getenv("JWT_SECRET", "")
    try:
        # Récupérer token
        r = requests.get(f"{render_url}/api/service/token",
                         params={"client_id": 1},
                         headers={"X-Service-Secret": jwt_secret},
                         timeout=10)
        token = r.json().get("token") or r.json().get("access_token")
        # Appel trafic
        r2 = requests.get(f"{render_url}/api/trafic/1",
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=30)
        data = r2.json()
        incidents = data.get("incidents", [])
        print(f"[RENDER] {len(incidents)} incidents reçus depuis l'API")
        return incidents
    except Exception as e:
        print(f"[RENDER] Erreur: {e}")
        return None

# ── Envoyer l'email (copie de send_email_trafic_batch sans cooldown) ──────────
def send_test_email(incidents: list, label: str = "TEST"):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("GMAIL_PASSWORD")
    receivers_str = os.getenv("RECEIVER_EMAILS", "")
    receivers = [r.strip() for r in receivers_str.split(",") if r.strip()]

    if not sender or not password:
        print("❌ SENDER_EMAIL ou GMAIL_PASSWORD manquant dans .env")
        return
    if not receivers:
        print("❌ RECEIVER_EMAILS vide dans .env")
        return

    # Tous les incidents inclus (HIGH, MED, LOW/bouchons) — impactent les tournées GEODIS
    incidents_notif = incidents
    print(f"\n📊 Résumé:")
    print(f"   Total incidents       : {len(incidents)}")
    high = sum(1 for i in incidents if i.get("severity") == "high")
    med  = sum(1 for i in incidents if i.get("severity") == "med")
    low  = sum(1 for i in incidents if i.get("severity") == "low")
    print(f"   🔴 HIGH (graves)       : {high}")
    print(f"   🟠 MED  (significatifs): {med}")
    print(f"   🟡 LOW  (bouchons)     : {low}")

    if not incidents_notif:
        print("\n✅ Aucun incident — pas d'email envoyé")
        return

    # Construire email (identique à send_email_trafic_batch)
    from collections import defaultdict
    now_str = datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')
    groups = defaultdict(list)
    type_labels = {
        "[CRASH]":   ("Accidents",      "#e53e3e", "🚗"),
        "[TRAFFIC]": ("Congestion",     "#dd6b20", "🚦"),
        "[WORK]":    ("Travaux",        "#3182ce", "🚧"),
        "[CLOSED]":  ("Routes fermées", "#6b21a8", "⛔"),
        "[HAZARD]":  ("Dangers",        "#b45309", "⚠️"),
        "[OTHER]":   ("Autres",         "#718096", "📌"),
    }
    for inc in incidents_notif:
        groups[inc.get("icon", "[OTHER]")].append(inc)

    total = len(incidents_notif)
    high_count = sum(1 for i in incidents_notif if i["severity"] == "high")
    retard_max = max((i["delay_minutes"] for i in incidents_notif), default=0)
    sev_dot = {"high": "🔴", "med": "🟠", "low": "🟡"}

    sections_html = ""
    for icon_key, (lbl, color, emoji) in type_labels.items():
        inc_list = groups.get(icon_key)
        if not inc_list:
            continue
        cards = ""
        for inc in inc_list:
            dot = sev_dot.get(inc["severity"], "⚪")
            delay_txt = f"+{inc['delay_minutes']} min" if inc["delay_minutes"] > 0 else "—"
            cards += f"""
            <div style="padding:12px 16px;border-bottom:1px solid #edf2f7;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <div style="font-size:13px;font-weight:600;color:#1a202c;">{inc['route']}</div>
                  <div style="font-size:12px;color:#4a5568;margin-top:3px;">{inc['description']}</div>
                </div>
                <div style="text-align:right;white-space:nowrap;margin-left:12px;">
                  <div style="font-size:13px;font-weight:700;color:#e53e3e;">{delay_txt}</div>
                  <div style="font-size:11px;color:#718096;">{dot} {inc.get('zone_source','')}</div>
                </div>
              </div>
            </div>"""
        sections_html += f"""
        <div style="margin-bottom:16px;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
          <div style="background:{color};padding:8px 16px;color:#fff;font-size:13px;font-weight:600;">
            {emoji} {lbl} ({len(inc_list)})
          </div>
          {cards}
        </div>"""

    subject = f"[{label}] Trafic — {high_count} incident(s) sévère(s) / {total} au total"

    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:600px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
  <div style="background:#c53030;padding:8px 20px;font-size:11px;color:#fff;font-weight:600;letter-spacing:1px;">
    ⚠️ EMAIL DE TEST — Ne pas tenir compte pour les opérations
  </div>
  <div style="background:#2c3e50;padding:18px 20px;">
    <div style="font-size:10px;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">Mah Météo — Surveillance trafic</div>
    <div style="font-size:16px;color:#fff;font-weight:600;margin-top:4px;">Point trafic du {now_str}</div>
  </div>
  <div style="padding:16px 20px 8px 20px;display:flex;gap:8px;border-bottom:1px solid #edf2f7;">
    <div style="flex:1;text-align:center;padding:10px 0;">
      <div style="font-size:24px;font-weight:700;color:#2d3748;">{total}</div>
      <div style="font-size:10px;color:#718096;text-transform:uppercase;">incidents HIGH/MED</div>
    </div>
    <div style="flex:1;text-align:center;padding:10px 0;border-left:1px solid #edf2f7;border-right:1px solid #edf2f7;">
      <div style="font-size:24px;font-weight:700;color:#e53e3e;">{high_count}</div>
      <div style="font-size:10px;color:#718096;text-transform:uppercase;">sévères</div>
    </div>
    <div style="flex:1;text-align:center;padding:10px 0;">
      <div style="font-size:24px;font-weight:700;color:#dd6b20;">+{retard_max}<span style="font-size:12px;"> min</span></div>
      <div style="font-size:10px;color:#718096;text-transform:uppercase;">retard max</div>
    </div>
  </div>
  <div style="padding:16px 20px;">{sections_html}</div>
  <div style="padding:12px 20px;background:#f7fafc;border-top:1px solid #edf2f7;font-size:10px;color:#a0aec0;">
    Mah Météo — {now_str} · Email de test · Ne pas répondre
  </div>
</div>
</body>
</html>"""

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = ", ".join(receivers)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())

        print(f"\n✅ Email de test envoyé → {receivers}")
        print(f"   Objet: {subject}")

    except smtplib.SMTPAuthenticationError:
        print("❌ Auth Gmail échouée — vérifier SENDER_EMAIL et GMAIL_PASSWORD")
    except Exception as e:
        print(f"❌ Erreur envoi: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    use_fake   = "--fake"   in sys.argv
    use_render = "--render" in sys.argv

    if use_fake:
        print("Mode: incidents fictifs réalistes (région Compiègne/Oise)")
        incidents = FAKE_INCIDENTS
        label = "TEST FICTIF"
    elif use_render:
        print("Mode: données réelles depuis API Render")
        incidents = load_from_render()
        if incidents is None:
            print("Fallback → cache local")
            incidents = load_from_cache() or FAKE_INCIDENTS
        label = "TEST RENDER"
    else:
        print("Mode: cache local (défaut)")
        incidents = load_from_cache()
        if not incidents:
            print("Cache vide → utilisation des données fictives")
            incidents = FAKE_INCIDENTS
            label = "TEST FICTIF"
        else:
            label = "TEST CACHE"

    send_test_email(incidents, label)
