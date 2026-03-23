# Configuration UptimeRobot

## Pourquoi ?
Render.com endort le service gratuit après 15 min d'inactivité.
UptimeRobot ping l'app toutes les 5 min pour la garder éveillée.

## Étapes
1. Créer un compte gratuit sur https://uptimerobot.com
2. Cliquer "Add New Monitor"
3. Remplir :
   - Monitor Type : HTTP(s)
   - Friendly Name : Mah-Meteo
   - URL : https://ton-app.onrender.com/
   - Monitoring Interval : Every 5 minutes
4. Cliquer "Create Monitor"

## Résultat
- Service toujours éveillé
- Zéro délai de démarrage pour les clients
