# -*- coding: utf-8 -*-
"""
email_alerts.py — Envoi d'alertes par email (météo, trafic, alerte combinée)
Utilise SMTP configurable via variables d'environnement.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


# ============ CONFIG SMTP ============

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "") or os.getenv("SENDER_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "") or os.getenv("GMAIL_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or os.getenv("SENDER_EMAIL", "")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS", "")
ALERT_ENABLED = os.getenv("ALERT_EMAIL_ENABLED", "true").lower() == "true"


def _send_email(to_emails, subject: str, html_body: str):
    """Envoie un email HTML via SMTP à un ou plusieurs destinataires."""
    if not ALERT_ENABLED:
        print(f"[EMAIL] Désactivé — sujet: {subject}")
        return False

    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[EMAIL] SMTP non configuré — sujet: {subject}")
        return False

    # Accepter str ou list
    if isinstance(to_emails, str):
        to_emails = [to_emails]

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = ", ".join(to_emails)

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(msg["From"], to_emails, msg.as_string())

        print(f"[EMAIL] Envoyé à {', '.join(to_emails)} — {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL] Erreur envoi: {e}")
        return False


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

def _header_html():
    return """
    <div style="background:#2c3e50;padding:16px 24px;color:#fff;font-family:'Segoe UI',Arial,sans-serif;">
        <h2 style="margin:0;font-size:18px;">Mah Météo — Alerte</h2>
    </div>
    """


def _footer_html():
    return f"""
    <div style="padding:12px 24px;background:#f7fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#a0aec0;font-family:'Segoe UI',Arial,sans-serif;">
        Envoyé automatiquement par Mah Météo — {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
        Ne pas répondre à cet email.
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

    html = f"""
    <div style="max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;">
        {_header_html()}
        <div style="padding:20px 24px;">
            <h3 style="margin:0 0 12px 0;color:#2d3748;font-size:15px;">Alertes météo — {company_name}</h3>
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
        </div>
        {_footer_html()}
    </div>
    """

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

    html = f"""
    <div style="max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;">
        {_header_html()}
        <div style="padding:20px 24px;">
            <h3 style="margin:0 0 12px 0;color:#2d3748;font-size:15px;">Incidents trafic critiques — {company_name}</h3>
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
        </div>
        {_footer_html()}
    </div>
    """

    subject = f"[Mah Météo] {len(critical)} incident(s) trafic — {company_name}"
    _send_email(_get_all_recipients(to_email), subject, html)


# ============ ALERTE COMBINÉE MÉTÉO + TRAFIC ============

def send_combined_alert(to_email: str, company_name: str, message: str):
    """
    Envoie l'alerte combinée météo + trafic par email.
    """
    if not message:
        return

    html = f"""
    <div style="max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;">
        {_header_html()}
        <div style="padding:20px 24px;">
            <h3 style="margin:0 0 12px 0;color:#c53030;font-size:15px;">Alerte combinée météo + trafic</h3>
            <div style="background:#fff5f5;border:1px solid #feb2b2;border-radius:4px;padding:16px;font-size:14px;color:#742a2a;line-height:1.6;">
                {message}
            </div>
            <p style="color:#a0aec0;font-size:12px;margin:16px 0 0 0;">
                Cette alerte est générée automatiquement lorsque des risques météo et des incidents trafic sont détectés simultanément sur vos zones.
            </p>
        </div>
        {_footer_html()}
    </div>
    """

    subject = f"[Mah Météo] ALERTE COMBINÉE météo + trafic — {company_name}"
    _send_email(_get_all_recipients(to_email), subject, html)
