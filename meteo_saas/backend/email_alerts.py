# -*- coding: utf-8 -*-
"""
email_alerts.py — Envoi d'alertes par email (météo, trafic, alerte combinée)
Utilise SMTP configurable via variables d'environnement.
"""

import os
import json
import smtplib
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()


# ============ CONFIG SMTP ============

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "") or os.getenv("SENDER_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "") or os.getenv("GMAIL_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or os.getenv("SENDER_EMAIL", "")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS", "")
ALERT_ENABLED = os.getenv("ALERT_EMAIL_ENABLED", "true").lower() == "true"
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()

# Cooldown anti-spam : 1 email par clé (zone+type) par heure
_COOLDOWN_SECONDS = 3600
_last_sent = {}  # clé = "zone:type" → datetime du dernier envoi

def _check_cooldown(key: str) -> bool:
    """Retourne True si on peut envoyer, False si cooldown actif."""
    last = _last_sent.get(key)
    if last and (datetime.now() - last).total_seconds() < _COOLDOWN_SECONDS:
        return False
    _last_sent[key] = datetime.now()
    return True


def _normalize_recipients(to_emails):
    """Normalise la liste des destinataires pour tous les appels email."""
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    return [email.strip() for email in (to_emails or []) if email and email.strip()]


def _build_smtp_message(subject: str, html_content: str, to_emails: list, from_name: str, sender_email: str, attachments=None):
    """Construit le MIME SMTP local en gardant le même rendu HTML."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{sender_email}>"
    msg["To"] = ", ".join(to_emails)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(alt)

    for attachment in attachments or []:
        part = MIMEApplication(attachment["content"], Name=attachment["name"])
        part["Content-Disposition"] = f'attachment; filename="{attachment["name"]}"'
        msg.attach(part)

    return msg


def _envoyer_email(subject: str, html_content: str, to_emails: list, from_name: str = "Mah Météo", attachments=None) -> bool:
    """
    Fonction centrale unique d'envoi email.
    Brevo uniquement si EMAIL_PROVIDER=brevo.
    SMTP reste un fallback local si aucun provider n'est imposé.
    """
    import base64

    if not ALERT_ENABLED:
        print(f"[EMAIL] Désactivé — sujet: {subject}")
        return False

    recipients = _normalize_recipients(to_emails)
    if not recipients:
        print(f"[EMAIL] Aucun destinataire — sujet: {subject}")
        return False

    provider = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    brevo_key = os.getenv("BREVO_API_KEY", "").strip()
    sender_email = (os.getenv("SMTP_FROM") or os.getenv("SENDER_EMAIL") or os.getenv("SMTP_USER") or "").strip()

    # En production on force Brevo: pas de bascule silencieuse vers SMTP.
    if provider == "brevo":
        if not brevo_key:
            print("[EMAIL] Brevo demandé mais BREVO_API_KEY est absente")
            return False
        if not sender_email:
            print("[EMAIL] Brevo demandé mais SMTP_FROM/SENDER_EMAIL est absent")
            return False

        try:
            payload = {
                "sender": {"name": from_name, "email": sender_email},
                "to": [{"email": email} for email in recipients],
                "subject": subject,
                "htmlContent": html_content,
            }
            if attachments:
                payload["attachment"] = [
                    {
                        "name": attachment["name"],
                        "content": base64.b64encode(attachment["content"]).decode("utf-8"),
                    }
                    for attachment in attachments
                ]

            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": brevo_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
                timeout=15,
            )
            if resp.status_code in (200, 201, 202):
                print(f"[EMAIL] Brevo OK : {subject[:50]}")
                return True

            print(f"[EMAIL] Brevo erreur {resp.status_code} : {resp.text[:200]}")
            return False
        except Exception as exc:
            print(f"[EMAIL] Brevo exception : {exc}")
            return False

    # En local/dev, SMTP reste disponible si aucun provider n'est imposé.
    smtp_host = os.getenv("SMTP_HOST", SMTP_HOST)
    smtp_port = int(os.getenv("SMTP_PORT", str(SMTP_PORT)))
    smtp_user = (os.getenv("SMTP_USER") or sender_email).strip()
    smtp_password = (
        os.getenv("SMTP_PASSWORD")
        or os.getenv("SMTP_PASS")
        or os.getenv("GMAIL_PASSWORD", "")
    ).strip()

    if not smtp_user or not smtp_password:
        print(f"[EMAIL] SMTP fallback non configuré — sujet: {subject}")
        return False

    try:
        msg = _build_smtp_message(subject, html_content, recipients, from_name, smtp_user, attachments=attachments)
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, recipients, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, recipients, msg.as_string())
        print(f"[EMAIL] SMTP fallback OK : {subject[:50]}")
        return True
    except smtplib.SMTPAuthenticationError as exc:
        print(f"[EMAIL] SMTP auth erreur : {exc}")
        return False
    except Exception as exc:
        print(f"[EMAIL] SMTP fallback erreur : {exc}")
        return False


def _send_email(to_emails, subject: str, html_body: str):
    """Compatibilité interne: tout passe désormais par _envoyer_email."""
    return _envoyer_email(subject, html_body, to_emails)


def _get_all_recipients(to_email: str):
    """Combine le destinataire spécifique + RECEIVER_EMAILS du .env."""
    recipients = set()
    if to_email:
        recipients.add(to_email.strip())
    if RECEIVER_EMAILS:
        for e in RECEIVER_EMAILS.split(","):
            e = e.strip()
            if e:
                recipients.add(e)
    return list(recipients)


# ============ TEMPLATES EMAIL ============

def _build_email_shell(title: str, subtitle: str, content_html: str, accent: str = "#2c3e50"):
        now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        import base64
        logo_b64 = ""
        try:
            import os as os_module
            logo_path = os_module.path.join(os_module.path.dirname(__file__), "../../exports/LOGO_MAH_METEO_SITE.png")
            if os_module.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_b64 = base64.b64encode(f.read()).decode()
        except:
            pass

        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:18px;vertical-align:middle;" alt="Mah Météo">' if logo_b64 else 'Mah Météo'
        
        return f"""<!DOCTYPE html>
<html><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head>
<body style=\"margin:0;padding:0;background:#eef1f5;font-family:'Segoe UI',Arial,sans-serif;\">
    <div style=\"max-width:680px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;\">
        <div style=\"background:{accent};padding:16px 20px;\">
            <div style=\"font-size:11px;color:#cbd5e0;text-transform:uppercase;letter-spacing:1px;\">{logo_html}</div>
            <div style=\"font-size:18px;color:#fff;font-weight:700;margin-top:4px;\">{title}</div>
            <div style=\"font-size:12px;color:#e2e8f0;margin-top:2px;\">{subtitle}</div>
        </div>
        <div style=\"padding:18px 20px;color:#2d3748;font-size:13px;line-height:1.55;\">{content_html}</div>
        <div style=\"padding:12px 20px;background:#f7fafc;border-top:1px solid #e2e8f0;color:#718096;font-size:11px;\">
            Mah Météo GEODIS · Généré automatiquement · {now_str}
        </div>
    </div>
</body></html>"""


def _html_alerte_combinee(alerte: dict, meteo_data: dict | None = None, trafic_data: dict | None = None) -> str:
        """Template simple pour l'alerte combinée afin d'éviter les emails trop denses."""
        meteo_data = meteo_data or {}
        trafic_data = trafic_data or {}
        zone = alerte.get("route") or trafic_data.get("route") or "Zone inconnue"
        retard = int(alerte.get("delay_minutes") or trafic_data.get("delay_minutes") or 0)
        risques_meteo = alerte.get("risques_meteo") or meteo_data.get("risques_meteo") or alerte.get("message") or ""

        if retard >= 30 or "verglas" in risques_meteo.lower():
                couleur = "#c53030"
                niveau = "ÉLEVÉ"
                emoji_niveau = "🔴"
        elif retard >= 10 or risques_meteo:
                couleur = "#dd6b20"
                niveau = "MODÉRÉ"
                emoji_niveau = "🟠"
        else:
                couleur = "#38a169"
                niveau = "FAIBLE"
                emoji_niveau = "🟢"

        return f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:0">
    <div style="background:{couleur};padding:16px 20px;border-radius:8px 8px 0 0">
        <p style="margin:0;color:white;font-size:18px;font-weight:bold">{emoji_niveau} Alerte combinée — {niveau}</p>
        <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px">Météo + Trafic simultanés</p>
    </div>

    <div style="background:#f8f9fa;border:1px solid #e2e8f0;border-top:none;padding:16px 20px">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;padding:10px 14px;background:white;border-radius:6px;border-left:4px solid {couleur}">
            <span style="font-size:20px">🚗</span>
            <div>
                <p style="margin:0;font-weight:bold;font-size:13px;color:#2d3748">{zone}</p>
                <p style="margin:2px 0 0;font-size:12px;color:#718096">Retard estimé : <strong>+{retard} min</strong></p>
            </div>
        </div>

        <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:white;border-radius:6px;border-left:4px solid #3498db">
            <span style="font-size:20px">🌤️</span>
            <div>
                <p style="margin:0;font-weight:bold;font-size:13px;color:#2d3748">Conditions météo actives</p>
                <p style="margin:2px 0 0;font-size:12px;color:#718096">{risques_meteo if risques_meteo else 'Conditions dégradées'}</p>
            </div>
        </div>
    </div>

    <div style="background:{couleur};opacity:0.08;border:1px solid #e2e8f0;border-top:none;padding:10px 20px;border-radius:0 0 8px 8px">
        <p style="margin:0;font-size:12px;color:#4a5568;text-align:center">{"⚠️ Prévoir un itinéraire alternatif" if retard >= 30 else "ℹ️ Adapter l'heure de départ si possible"}</p>
    </div>

    <p style="text-align:center;font-size:11px;color:#a0aec0;margin-top:12px">Mah Météo · <a href="{os.getenv('RENDER_URL', '#')}" style="color:#3498db">Voir le dashboard</a></p>
</div>
"""


# ============ ALERTES MÉTÉO ============

def send_meteo_alert(to_email: str, company_name: str, alertes: list):
    """
    Envoie un email d'alerte météo.
    alertes = [{"zone": "Beauvais", "type": "Vent", "valeur": "55 km/h", "message": "..."}]
    """
    if not alertes:
        return

    # Filtrer par cooldown (1 email/heure/zone)
    alertes_filtered = []
    for a in alertes:
        key = f"{a.get('zone','?')}:meteo:{a.get('type','')}"
        if _check_cooldown(key):
            alertes_filtered.append(a)
    if not alertes_filtered:
        print(f"[EMAIL] Cooldown actif — aucune alerte météo envoyée")
        return
    alertes = alertes_filtered

    rows = ""
    for a in alertes:
        color = "#e53e3e" if "fort" in a.get("type", "").lower() else "#d69e2e"
        rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{a['zone']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{a['type']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;font-weight:600;color:{color};">{a['valeur']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{a['message']}</td>
        </tr>
        """

    content = f"""
    <p style="color:#718096;font-size:13px;margin:0 0 16px 0;">{len(alertes)} alerte(s) détectée(s) sur vos zones.</p>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:4px;">
      <thead>
        <tr style="background:#f7fafc;">
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Zone</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Type</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Valeur</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Message</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """
    html = _build_email_shell(
        title="Alerte météo",
        subtitle=f"{company_name} — surveillance active",
        content_html=content,
        accent="#2c3e50",
    )

    subject = f"[Mah Météo] {len(alertes)} alerte(s) météo — {company_name}"
    _send_email(_get_all_recipients(to_email), subject, html)


# ============ ALERTES TRAFIC ============

def send_trafic_alert(to_email: str, company_name: str, incidents: list):
    """
    Envoie un email d'alerte trafic.
    incidents = [{"route": "A1", "description": "...", "severity": "high", "delay_minutes": 25}]
    """
    if not incidents:
        return

    # Filtrer : envoyer uniquement les incidents sévères (high ou delay > 15 min)
    critical = [i for i in incidents if i.get("severity") == "high" or (i.get("delay_minutes") or 0) > 15]
    if not critical:
        return

    # Filtrer par cooldown (1 email/heure/route)
    critical_filtered = []
    for inc in critical:
        key = f"{inc.get('route','?')}:trafic:{inc.get('severity','')}"
        if _check_cooldown(key):
            critical_filtered.append(inc)
    if not critical_filtered:
        print(f"[EMAIL] Cooldown actif — aucune alerte trafic envoyée")
        return
    critical = critical_filtered

    rows = ""
    for inc in critical:
        sev = inc.get("severity", "low")
        color = "#e53e3e" if sev == "high" else "#d69e2e" if sev == "med" else "#718096"
        delay = f"+{inc['delay_minutes']} min" if inc.get("delay_minutes") else "—"
        rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{inc['route']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{inc['description']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;font-weight:600;color:{color};">{sev.upper()}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">{delay}</td>
        </tr>
        """

    content = f"""
    <p style="color:#718096;font-size:13px;margin:0 0 16px 0;">{len(critical)} incident(s) critique(s) détecté(s).</p>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:4px;">
      <thead>
        <tr style="background:#f7fafc;">
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Route</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Description</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Sévérité</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#4a5568;">Retard</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """
    html = _build_email_shell(
        title="Alerte trafic",
        subtitle=f"{company_name} — incidents critiques",
        content_html=content,
        accent="#2c3e50",
    )

    subject = f"[Mah Météo] {len(critical)} incident(s) trafic — {company_name}"
    _send_email(_get_all_recipients(to_email), subject, html)


# ============ ALERTE COMBINÉE MÉTÉO + TRAFIC ============

def send_combined_alert(to_email: str, company_name: str, message: str):
    """
    Envoie l'alerte combinée météo + trafic par email.
    """
    if not message:
        return

    if not _check_cooldown(f"{company_name}:combined"):
        print(f"[EMAIL] Cooldown actif — alerte combinée non envoyée")
        return

    # On accepte encore une chaîne legacy, mais on normalise vers un dict pour le nouveau template.
    if isinstance(message, dict):
        alerte = dict(message)
    else:
        alerte = {
            "route": company_name,
            "delay_minutes": 0,
            "risques_meteo": str(message),
            "message": str(message),
        }

    html = _html_alerte_combinee(alerte)

    subject = f"[Mah Météo] ALERTE COMBINÉE météo + trafic — {company_name}"
    _envoyer_email(subject, html, _get_all_recipients(to_email))


def send_pollution_alert(to_email: str, company_name: str, zones_alertes: list, state_file: str = "exports/last_pollution_alert.json") -> bool:
    """
    Envoie une alerte pollution (AQI >= 40) avec cooldown différencié:
    - 40-59: 6h
    - 60-79: 3h
    - 80+: 1h
    """
    if not zones_alertes:
        return False

    # Grouper par seuil
    zones_moderate = [z for z in zones_alertes if 40 <= (z.get("aqi") or 0) < 60]
    zones_bad = [z for z in zones_alertes if 60 <= (z.get("aqi") or 0) < 80]
    zones_very_bad = [z for z in zones_alertes if (z.get("aqi") or 0) >= 80]

    max_aqi = max([z.get("aqi", 0) for z in zones_alertes], default=0)
    if max_aqi >= 80:
        cooldown_seconds = 1 * 3600
        cooldown_key = "high"
        max_level = "Très mauvais"
    elif max_aqi >= 60:
        cooldown_seconds = 3 * 3600
        cooldown_key = "medium"
        max_level = "Mauvais"
    else:
        cooldown_seconds = 6 * 3600
        cooldown_key = "low"
        max_level = "Modéré"

    state = {}
    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
    except Exception:
        state = {}

    last = state.get(cooldown_key)
    if last:
        try:
            delta = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
            if delta < cooldown_seconds:
                print(f"[EMAIL] Cooldown pollution {cooldown_key} actif ({int(delta)}s/{cooldown_seconds}s)")
                return False
        except Exception:
            pass

    def render_section(zones: list, title: str, bg_color: str, border_color: str) -> str:
        if not zones:
            return ""
        rows = ""
        for z in zones:
            pm25_txt = f"{z.get('pm25', 0):.1f} µg/m³" if z.get("pm25") else "—"
            rows += f"""<tr style="border-bottom:1px solid #e2e8f0;">
              <td style="padding:10px 14px;color:#1a202c;font-weight:600;">{z.get('zone', 'Inconnu')}</td>
              <td style="padding:10px 14px;text-align:center;font-size:18px;font-weight:700;color:{border_color};">{round(z.get('aqi', 0))}</td>
              <td style="padding:10px 14px;text-align:center;color:{border_color};font-weight:600;">{z.get('label', 'Inconnu')}</td>
              <td style="padding:10px 14px;text-align:center;color:#4a5568;font-size:12px;">{pm25_txt}</td>
            </tr>"""

        return f"""<div style="margin:12px 0;border-left:4px solid {border_color};background:{bg_color};padding:12px;border-radius:4px;">
          <div style="font-weight:700;color:{border_color};margin-bottom:8px;font-size:13px;">{title}</div>
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
              <tr style="background:#f7fafc;">
                <th style="padding:8px 14px;text-align:left;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">Site</th>
                <th style="padding:8px 14px;text-align:center;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">AQI</th>
                <th style="padding:8px 14px;text-align:center;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">Niveau</th>
                <th style="padding:8px 14px;text-align:center;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">PM2.5</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    sections_html = ""
    if zones_very_bad:
        sections_html += render_section(zones_very_bad, "Très mauvais (AQI 80+)", "#fef2f2", "#7b341e")
    if zones_bad:
        sections_html += render_section(zones_bad, "Mauvais (AQI 60-79)", "#fef2f2", "#e53e3e")
    if zones_moderate:
        sections_html += render_section(zones_moderate, "Modéré (AQI 40-59)", "#fffbeb", "#dd6b20")

    content = f"""
    <p style=\"margin-top:0;\">La qualité de l'air dépasse le seuil d'alerte sur <strong>{len(zones_alertes)} site(s)</strong>.</p>
    {sections_html}
    <div style=\"background:#f7fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 14px;margin-top:14px;font-size:11px;color:#718096;line-height:1.5;\">
      <strong>Échelle AQI européen:</strong><br>
      0-20 Bon · 20-40 Acceptable · <strong>40-60 Modéré</strong> · <strong>60-80 Mauvais</strong> · <strong style=\"color:#7b341e;\">80-100 Très mauvais</strong> · >100 Extrême
    </div>
    """
    html = _build_email_shell(
        title="Alerte pollution",
        subtitle=f"{company_name} — surveillance qualité air",
        content_html=content,
        accent="#744210",
    )
    subject = f"[Mah Météo] Alerte pollution — {max_level} — {company_name}"

    sent = _envoyer_email(subject, html, _get_all_recipients(to_email), from_name="Mah Météo")
    if sent:
        try:
            state[cooldown_key] = datetime.now().isoformat()
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EMAIL] Alerte pollution envoyée mais sauvegarde cooldown impossible: {e}")
    return sent


def _build_trial_block(trial_expires_at):
    """Génère le bloc essai PRO gratuit 7j (sauf si trial_expires_at est None)."""
    if not trial_expires_at:
        return ""  # Pas d'essai
    
    expiry_date = trial_expires_at.strftime('%d/%m/%Y')
    return f"""<div style="background:linear-gradient(135deg,#3498db,#2980b9);border-radius:8px;padding:20px;margin-bottom:24px;color:#fff;border:2px solid #2980b9;">
                <h3 style="margin:0 0 12px 0;font-size:16px;font-weight:700;">Essai PRO GRATUIT - 7 jours</h3>
                <div style="background:rgba(0,0,0,0.2);border-radius:6px;padding:12px;margin-bottom:12px;border-left:4px solid #f39c12;">
                    <p style="margin:0;font-size:13px;line-height:1.5;">
                        <strong>Débloquez TOUTES les fonctionnalités PRO gratuitement !</strong><br>
                        Accès complet jusqu'au <strong>{expiry_date}</strong>.
                    </p>
                </div>
                <ul style="margin:0;padding-left:20px;font-size:12px;line-height:1.6;">
                    <li><strong>5 sites</strong> GEODIS (au lieu de 1)</li>
                    <li><strong>15 zones voisines</strong> (au lieu de 3)</li>
                    <li><strong>5 alertes/mois</strong> par email (au lieu de 0)</li>
                    <li><strong>30 modifications/mois</strong> (au lieu de 2)</li>
                    <li>Cartes avancées, rapports, tournées complètes</li>
                </ul>
                <div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(0,0,0,0.2);">
                    <p style="margin:0;font-size:12px;">
                        Après l'essai : Vous reviendrez au plan FREE. Pour conserver PRO, passez à un abonnement payant avant le {expiry_date}.
                    </p>
                </div>
            </div>"""


# ============ EMAIL DE BIENVENUE (APPROBATION) ============

def send_welcome_email(to_email: str, username: str, temp_password: str, company_name: str, plan: str, limits: dict, trial_expires_at=None):
    """
    Envoie un email de bienvenue après approbation de l'inscription.
    
    Inclut :
    - Identifiant (username)
    - Mot de passe temporaire
    - Quotas de démarrage (FREE = très limité)
    - Offre essai PRO 7j gratuit
    - Guide d'utilisation
    - Lien de connexion
    """
    
    # Traduction du plan
    plan_labels = {
        'standard': 'Standard',
        'pro': 'Pro',
        'groupe': 'Groupe',
        'enterprise': 'Groupe',
        'free': 'Standard',
        'gratuit': 'Standard'
    }
    plan_label = plan_labels.get(plan, plan.capitalize())
    
    # Couleur du plan
    plan_color = {
        'standard': '#27ae60',
        'pro': '#3498db',
        'groupe': '#e67e22',
        'enterprise': '#e67e22',
        'free': '#27ae60',
        'gratuit': '#27ae60'
    }.get(plan, '#2c3e50')
    
    limits_html = f"""
    <table style="width:100%;border-collapse:collapse;margin-top:12px;">
        <tr style="background:#f7fafc;">
            <td style="padding:10px 12px;border:1px solid #e2e8f0;font-weight:600;color:#2d3748;">Ressource</td>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;font-weight:600;color:#2d3748;text-align:center;">Limite</td>
        </tr>
        <tr>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;color:#4a5568;">Sites GEODIS</td>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;text-align:center;font-weight:600;color:#27ae60;">{limits.get('sites', 0)}</td>
        </tr>
        <tr>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;color:#4a5568;">Zones voisines</td>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;text-align:center;font-weight:600;color:#27ae60;">{limits.get('voisins', 0)}</td>
        </tr>
        <tr>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;color:#4a5568;">Modifications/mois</td>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;text-align:center;font-weight:600;color:#27ae60;">{limits.get('changes', 0)}</td>
        </tr>
        <tr>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;color:#4a5568;">Alertes par email/mois</td>
            <td style="padding:10px 12px;border:1px solid #e2e8f0;text-align:center;font-weight:600;color:#27ae60;">{limits.get('emails', 0)}</td>
        </tr>
    </table>
    """
    
    html = f"""
    <div style="max-width:650px;margin:0 auto;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;background:#fff;">
        <!-- En-tête avec logo -->
        <div style="background:linear-gradient(135deg,{plan_color},rgba(0,0,0,0.05));padding:30px 24px;color:#fff;text-align:center;">
            <div style="font-size:24px;margin-bottom:8px;">M</div>
            <h1 style="margin:0 0 8px 0;font-size:24px;font-weight:700;">Bienvenue</h1>
            <p style="margin:0;font-size:14px;opacity:0.9;">{company_name}</p>
        </div>
        
        <!-- Contenu principal -->
        <div style="padding:30px 24px;">
            <h2 style="color:#2d3748;font-size:18px;margin:0 0 8px 0;">Compte approuvé !</h2>
            <p style="color:#718096;font-size:14px;margin:0 0 24px 0;">Voici vos identifiants et le récapitulatif de votre abonnement.</p>
            
            <!-- Bloc identifiants -->
            <div style="background:#f0f9ff;border:2px solid #bee3f8;border-radius:8px;padding:16px;margin-bottom:24px;">
                <h3 style="margin:0 0 12px 0;color:#2b6cb0;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Vos identifiants</h3>
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:11px;color:#718096;font-weight:600;margin-bottom:4px;">Identifiant</label>
                    <div style="background:#fff;border:1px solid #cbd5e0;border-radius:4px;padding:10px 12px;font-family:monospace;font-size:14px;color:#2d3748;font-weight:600;word-break:break-all;">{username}</div>
                </div>
                <div>
                    <label style="display:block;font-size:11px;color:#718096;font-weight:600;margin-bottom:4px;">Mot de passe temporaire</label>
                    <div style="background:#fff;border:1px solid #cbd5e0;border-radius:4px;padding:10px 12px;font-family:monospace;font-size:14px;color:#2d3748;font-weight:600;word-break:break-all;">{temp_password}</div>
                </div>
                <p style="color:#c53030;font-size:12px;margin:12px 0 0 0;font-weight:600;">IMPORTANT : Ce mot de passe est temporaire. Vous devrez le changer lors de votre première connexion.</p>
            </div>
            
            <!-- Bloc plan -->
            <div style="background:linear-gradient(135deg,rgba(0,0,0,0.02),rgba(0,0,0,0.04));border-left:4px solid {plan_color};border-radius:8px;padding:16px;margin-bottom:24px;">
                <h3 style="margin:0 0 12px 0;color:#2d3748;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Votre plan</h3>
                <div style="font-size:18px;font-weight:700;color:{plan_color};margin-bottom:12px;">{plan_label}</div>
                <p style="color:#718096;font-size:13px;margin:0;">Voici vos quotas de démarrage :</p>
                {limits_html}
            </div>
            
            <!-- Bloc essai PRO gratuit 7j -->
            {_build_trial_block(trial_expires_at)}
            
            <!-- Bloc guide -->
            <div style="background:#fffaf0;border:1px solid #feebc8;border-radius:8px;padding:16px;margin-bottom:24px;">
                <h3 style="margin:0 0 12px 0;color:#c05621;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Guide de démarrage</h3>
                <ol style="margin:0;padding-left:20px;color:#4a5568;font-size:13px;line-height:1.7;">
                    <li style="margin-bottom:8px;"><strong>Connectez-vous</strong> avec vos identifiants ci-dessus</li>
                    <li style="margin-bottom:8px;"><strong>Changez votre mot de passe</strong> lors de la première connexion</li>
                    <li style="margin-bottom:8px;"><strong>Allez à "Mon Compte"</strong> et ajoutez vos zones de suivi</li>
                    <li style="margin-bottom:8px;"><strong>Consultez vos prévisions</strong> et recevez des alertes météo</li>
                    <li><strong>Créez des tournées</strong> pour planifier vos trajets</li>
                </ol>
            </div>
            
            <!-- Bloc fonctionnalités -->
            <div style="background:#f0fff4;border:1px solid #c6f6d5;border-radius:8px;padding:16px;margin-bottom:24px;">
                <h3 style="margin:0 0 12px 0;color:#276749;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Fonctionnalités</h3>
                <ul style="margin:0;padding-left:20px;color:#4a5568;font-size:13px;line-height:1.7;list-style:none;">
                    <li style="margin-bottom:6px;">Carte interactive avec vos zones</li>
                    <li style="margin-bottom:6px;">Prévisions météo</li>
                    <li style="margin-bottom:6px;">Alertes en temps réel</li>
                    <li style="margin-bottom:6px;">Suivi du trafic</li>
                    <li style="margin-bottom:6px;">Gestion des tournées</li>
                    <li>Rapports personnalisés</li>
                </ul>
            </div>
            
            <!-- Bouton de connexion -->
            <div style="text-align:center;margin-bottom:24px;">
                <a href="https://mah-meteo.onrender.com" style="display:inline-block;background:{plan_color};color:#fff;padding:12px 32px;border-radius:20px;text-decoration:none;font-weight:600;font-size:14px;box-shadow:0 2px 8px rgba(0,0,0,0.15);">
                    Se connecter maintenant →
                </a>
            </div>
            
            <!-- Support -->
            <div style="background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;text-align:center;">
                <p style="margin:0;color:#718096;font-size:12px;">Besoin d'aide ? Répondez à cet email avec vos questions.</p>
            </div>
        </div>
        
        <!-- Pied de page -->
        <div style="padding:12px 24px;background:#f7fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#a0aec0;text-align:center;">
            Mah Météo — Supervision météo & trafic pour vos trajets<br>
            Envoyé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        </div>
    </div>
    """
    
    subject = f"Bienvenue sur Mah Météo — Compte approuvé ({plan_label})"
    return _send_email(to_email, subject, html)


# ============ BULLETIN HORAIRE PROGRAMMÉ ============

def send_bulletin_email(to_email: str, company_name: str, zones: list, incidents: list = None, creneau: str = "") -> bool:
    """
    Envoie un bulletin météo visuel (cards) à une tranche horaire programmée.
    zones : liste d'objets Zone (SQLAlchemy) ou dicts avec name/temperature/windspeed/precipitation/uv_index/risques/ciel/type
    incidents : liste d'incidents trafic [{route, description, severity, delay_minutes}]
    creneau : label ex: "06h30"
    """
    incidents = incidents or []
    now_str = datetime.now().strftime("%A %d %B %Y")
    heure_str = datetime.now().strftime("%H:%M")

    def _get(obj, attr, default=None):
        val = (getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr))
        return val if val is not None else default

    # Détecter les alertes actives
    alertes_actives = []
    for z in zones:
        risques = _get(z, "risques", "") or ""
        if risques and "RAS" not in risques and "✅" not in risques:
            alertes_actives.append(((_get(z, "name") or "Zone"), risques))

    gros_retards = [i for i in incidents if (i.get("delay_minutes") or 0) >= 30]
    nb_alertes = len(alertes_actives) + len(gros_retards)
    retard_max = max((i.get("delay_minutes") or 0 for i in incidents), default=0)

    if alertes_actives or gros_retards:
        accent = "#c53030"
        status_bg = "#fff5f5"
        status_border = "#feb2b2"
        status_txt = "#c53030"
        status_icon = "⚠️"
        status_label = f"{nb_alertes} ALERTE{'S' if nb_alertes > 1 else ''} EN COURS"
    else:
        accent = "#276749"
        status_bg = "#f0fff4"
        status_border = "#9ae6b4"
        status_txt = "#276749"
        status_icon = "✅"
        status_label = "TOUTES LES ZONES OK"

    render_url = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")

    # ──────────────────────────────────────────────────────────
    # Banniere statut
    # ──────────────────────────────────────────────────────────
    banniere = f"""
    <div style="background:{status_bg};border:1px solid {status_border};border-radius:8px;padding:12px 16px;margin-bottom:20px;display:flex;align-items:center;">
        <span style="font-size:22px;margin-right:10px;">{status_icon}</span>
        <div style="flex:1;">
            <div style="font-size:13px;font-weight:700;color:{status_txt};">{status_label}</div>
            <div style="font-size:11px;color:#718096;margin-top:2px;">Bulletin du {now_str} · Créneau {creneau if creneau else heure_str}</div>
        </div>
        <a href="{render_url}" style="font-size:11px;background:{accent};color:#fff;padding:5px 12px;border-radius:12px;text-decoration:none;font-weight:600;white-space:nowrap;">Dashboard →</a>
    </div>"""

    # ──────────────────────────────────────────────────────────
    # Chips de stats rapides
    # ──────────────────────────────────────────────────────────
    # Calcul temp moyenne sites
    sites = [z for z in zones if (_get(z, "type") or "voisin") == "site"]
    temps = [_get(z, "temperature") for z in sites]
    temps = [t for t in temps if isinstance(t, (int, float))]
    temp_moy_str = f"{sum(temps)/len(temps):.1f}°C" if temps else "—"

    winds = [_get(z, "windspeed") for z in zones]
    winds = [w for w in winds if isinstance(w, (int, float))]
    wind_max_str = f"{max(winds):.0f} km/h" if winds else "—"

    retard_str = f"+{retard_max} min" if retard_max > 0 else "Fluide"
    retard_chip_bg = "#fff5f5" if retard_max >= 30 else "#fffbeb" if retard_max >= 15 else "#f0fff4"
    retard_chip_col = "#c53030" if retard_max >= 30 else "#c05621" if retard_max >= 15 else "#276749"

    def chip(icon, label, value, bg, col):
        return f"""
        <td style="padding:0 4px;">
          <div style="background:{bg};border-radius:8px;padding:10px 12px;text-align:center;min-width:80px;">
            <div style="font-size:18px;margin-bottom:4px;">{icon}</div>
            <div style="font-size:15px;font-weight:700;color:{col};">{value}</div>
            <div style="font-size:10px;color:#718096;margin-top:2px;text-transform:uppercase;letter-spacing:.5px;">{label}</div>
          </div>
        </td>"""

    chips_html = f"""
    <table style="width:100%;border-collapse:separate;border-spacing:0;margin-bottom:20px;">
      <tr>
        {chip("🌡️", "Temp. moy.", temp_moy_str, "#ebf8ff", "#2b6cb0")}
        {chip("💨", "Vent max", wind_max_str, "#faf5ff", "#553c9a")}
        {chip("🚗", "Trafic", retard_str, retard_chip_bg, retard_chip_col)}
        {chip("🚨", "Alertes", str(nb_alertes) if nb_alertes > 0 else "Aucune", "#fff5f5" if nb_alertes > 0 else "#f0fff4", "#c53030" if nb_alertes > 0 else "#276749")}
      </tr>
    </table>"""

    # ──────────────────────────────────────────────────────────
    # Cards zones (2 par ligne)
    # ──────────────────────────────────────────────────────────
    def zone_card(z):
        name = _get(z, "name") or "Zone"
        z_type = _get(z, "type") or "voisin"
        temp = _get(z, "temperature")
        wind = _get(z, "windspeed")
        wind_dir = _get(z, "wind_direction") or ""
        precip = _get(z, "precipitation")
        uv = _get(z, "uv_index")
        risques = _get(z, "risques") or "✅ RAS"
        ciel_ico = _get(z, "ciel") or "☀️"

        has_alert = "RAS" not in str(risques) and "✅" not in str(risques)
        card_border = "#feb2b2" if has_alert else "#e2e8f0"
        card_top_bg = "#fff5f5" if has_alert else "#f7fafc"
        risques_col = "#c53030" if has_alert else "#276749"
        badge_txt = "🏭 Site" if z_type == "site" else "📍 Zone"
        badge_bg = "#ebf8ff" if z_type == "site" else "#f0fff4"
        badge_col = "#2b6cb0" if z_type == "site" else "#276749"

        temp_str = f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "—"
        wind_str = f"{wind:.0f} km/h" if isinstance(wind, (int, float)) else "—"
        precip_str = f"{precip:.1f} mm" if isinstance(precip, (int, float)) else "—"
        uv_str = f"UV {uv:.0f}" if isinstance(uv, (int, float)) else "UV —"

        # Couleur température
        if isinstance(temp, (int, float)):
            t_col = "#c53030" if temp >= 35 else "#c05621" if temp >= 28 else "#2b6cb0" if temp <= 0 else "#2d3748"
        else:
            t_col = "#2d3748"

        # Couleur vent
        w_col = "#c53030" if isinstance(wind, (int, float)) and wind >= 80 else "#c05621" if isinstance(wind, (int, float)) and wind >= 50 else "#4a5568"

        return f"""
        <div style="border:1px solid {card_border};border-radius:8px;overflow:hidden;margin-bottom:10px;">
          <div style="background:{card_top_bg};padding:8px 12px;display:flex;align-items:center;border-bottom:1px solid {card_border};">
            <span style="font-size:22px;margin-right:8px;">{ciel_ico}</span>
            <div style="flex:1;">
              <div style="font-size:13px;font-weight:700;color:#2d3748;">{name}</div>
              <span style="font-size:10px;font-weight:600;color:{badge_col};background:{badge_bg};padding:1px 7px;border-radius:10px;">{badge_txt}</span>
            </div>
            <span style="font-size:22px;font-weight:800;color:{t_col};">{temp_str}</span>
          </div>
          <div style="padding:8px 12px;background:#fff;">
            <table style="width:100%;border-collapse:collapse;">
              <tr>
                <td style="padding:3px 6px 3px 0;font-size:11px;color:#718096;width:33%;">💨 Vent</td>
                <td style="padding:3px 0;font-size:12px;font-weight:600;color:{w_col};width:33%;">{wind_str} {wind_dir}</td>
                <td style="padding:3px 0;font-size:11px;color:#718096;text-align:right;">🌧 {precip_str} · {uv_str}</td>
              </tr>
              <tr>
                <td colspan="3" style="padding-top:6px;border-top:1px dashed #e2e8f0;font-size:11px;font-weight:600;color:{risques_col};">{risques}</td>
              </tr>
            </table>
          </div>
        </div>"""

    # Grouper zones par paires (sites en premier)
    sites_zones = [z for z in zones if (_get(z, "type") or "voisin") == "site"]
    voisins_zones = [z for z in zones if (_get(z, "type") or "voisin") != "site"]
    ordered = sites_zones + voisins_zones

    cards_rows = ""
    for i in range(0, len(ordered), 2):
        left = zone_card(ordered[i])
        right = zone_card(ordered[i + 1]) if i + 1 < len(ordered) else ""
        cards_rows += f"""
        <table style="width:100%;border-collapse:separate;border-spacing:8px 0;margin-bottom:0;">
          <tr>
            <td style="width:50%;vertical-align:top;padding:0;">{left}</td>
            <td style="width:50%;vertical-align:top;padding:0;">{right}</td>
          </tr>
        </table>"""

    zone_label = f"""
    <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#4a5568;margin-bottom:10px;padding-bottom:6px;border-bottom:2px solid #e2e8f0;">
        🌤 Conditions météo — {len(zones)} zone{'s' if len(zones) > 1 else ''}
    </div>"""

    # ──────────────────────────────────────────────────────────
    # Section trafic : cards incidents
    # ──────────────────────────────────────────────────────────
    if incidents:
        inc_cards = ""
        for i in sorted(incidents, key=lambda x: -(x.get("delay_minutes") or 0)):
            delay = i.get("delay_minutes") or 0
            if delay >= 30:
                sev_bg, sev_col, sev_dot = "#fff5f5", "#c53030", "🔴"
            elif delay >= 15:
                sev_bg, sev_col, sev_dot = "#fffbeb", "#c05621", "🟠"
            else:
                sev_bg, sev_col, sev_dot = "#f7fafc", "#718096", "🟢"
            inc_cards += f"""
            <div style="border:1px solid #e2e8f0;border-left:4px solid {sev_col};border-radius:6px;padding:9px 12px;margin-bottom:8px;background:{sev_bg};display:flex;align-items:center;">
                <span style="font-size:16px;margin-right:8px;">{sev_dot}</span>
                <div style="flex:1;">
                    <div style="font-size:12px;font-weight:700;color:#2d3748;">{i.get('route','—')}</div>
                    <div style="font-size:11px;color:#718096;margin-top:1px;">{str(i.get('description','—'))[:70]}</div>
                </div>
                <div style="text-align:right;min-width:52px;">
                    <div style="font-size:13px;font-weight:800;color:{sev_col};">+{delay}</div>
                    <div style="font-size:10px;color:#718096;">min</div>
                </div>
            </div>"""
        trafic_section = f"""
        <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#4a5568;margin:18px 0 10px 0;padding-bottom:6px;border-bottom:2px solid #e2e8f0;">
            🚗 Trafic en temps réel — {len(incidents)} incident{'s' if len(incidents) > 1 else ''}
        </div>
        {inc_cards}"""
    else:
        trafic_section = """
        <div style="background:#f0fff4;border:1px solid #9ae6b4;border-radius:6px;padding:10px 14px;margin-top:16px;font-size:12px;color:#276749;font-weight:600;">
            🚗 Trafic fluide — Aucun incident signalé sur vos zones
        </div>"""

    content = f"""
    {banniere}
    {chips_html}
    {zone_label}
    {cards_rows}
    {trafic_section}
    """

    html = _build_email_shell(
        title=f"Bulletin météo GEODIS",
        subtitle=f"{company_name} · Créneau {creneau if creneau else heure_str} · {now_str}",
        content_html=content,
        accent=accent,
    )

    if alertes_actives:
        subject = f"[Mah Météo] ALERTE {creneau} — {company_name}"
    else:
        subject = f"[Mah Météo] Bulletin {creneau} — {company_name} ({now_str})"

    return _envoyer_email(subject, html, _get_all_recipients(to_email), from_name="Mah Météo")
