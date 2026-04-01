import time
import os
import datetime

SCRIPT_PATH = "meteo_open.py"
RAPPORT_PATH = "rapport_hebdomadaire.py"

def run_script():
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Lancement de la mise à jour météo...")
    exit_code = os.system(f"python {SCRIPT_PATH}")
    if exit_code == 0:
        print("✅ Mise à jour terminée avec succès.")
    else:
        print("❌ Erreur pendant l'exécution du script météo.")

def run_rapport_hebdo():
    """Lancer le rapport hebdomadaire le lundi"""
    print(f"\n📊 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Lancement du RAPPORT HEBDOMADAIRE...")
    exit_code = os.system(f"python {RAPPORT_PATH}")
    if exit_code == 0:
        print("✅ Rapport hebdomadaire terminé avec succès.")
    else:
        print("❌ Erreur pendant l'exécution du rapport.")

if __name__ == "__main__":
    # ⛔ ARRÊT AUTOMATIQUE — Tout tourne sur GitHub Actions / Render depuis le 1er avril 2026
    DATE_ARRET = datetime.datetime(2026, 4, 1)
    if datetime.datetime.now() >= DATE_ARRET:
        print("⛔ ARRÊT: Depuis le 1er avril 2026, la boucle locale est désactivée.")
        print("   → Tout tourne désormais via GitHub Actions (meteo-cron.yml) toutes les 22 min.")
        print("   → Render héberge l'API et le dashboard.")
        exit(0)

    rapport_envoye_semaine = None  # Flag pour éviter dupliquant le rapport

    while True:
        now = datetime.datetime.now()
        
        # Lancer le rapport chaque lundi à 08:00
        semaine_courante = now.isocalendar()[1]
        if now.weekday() == 0 and now.hour == 8 and rapport_envoye_semaine != semaine_courante:
            run_rapport_hebdo()
            rapport_envoye_semaine = semaine_courante
        
        # Lancer la mise à jour météo toutes les 22 minutes
        run_script()
        print("[INFO] Attente 22 minutes avant la prochaine execution...\n")
        time.sleep(1320)  # 1320 secondes = 22 minutes
