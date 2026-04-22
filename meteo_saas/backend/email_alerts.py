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

    if not _check_cooldown(f"{company_name}:combined"):
        print(f"[EMAIL] Cooldown actif — alerte combinée non envoyée")
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
            <div style="font-size:32px;margin-bottom:8px;">🌤️</div>
            <h1 style="margin:0 0 8px 0;font-size:24px;font-weight:700;">Bienvenue dans Mah Météo</h1>
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
                    <li style="margin-bottom:6px;">Prévisions météo sur 7 jours</li>
                    <li style="margin-bottom:6px;">Alertes en temps réel</li>
                    <li style="margin-bottom:6px;">Suivi du trafic</li>
                    <li style="margin-bottom:6px;">Gestion des tournées</li>
                    <li>Statistiques et rapports</li>
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
    
    subject = f"✅ Bienvenue sur Mah Météo — Compte approuvé ({plan_label})"
    return _send_email(to_email, subject, html)
