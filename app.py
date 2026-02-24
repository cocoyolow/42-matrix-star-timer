#!/usr/bin/env python3
from flask import Flask, jsonify
from flask_cors import CORS
import requests
from dateutil import parser
from datetime import datetime, timezone
import threading
import time

# Try to import plyer for system notifications
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("Warning: plyer not installed. System notifications will be disabled.")
    print("Install with: pip install plyer")

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
UID = "u-s4t2ud-8df2267f1a2843df41e6a72698bec9824e854233bc049e93a09f92d0240a5e1b"
SECRET = "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"

# --- VARIABLES GLOBALES ---
monitored_user = None
timer_thread = None
timer_thread_running = False
timer_lock = threading.Lock()
notified_events = set()      # Pour ne pas spammer les notifs d'éval
last_star_time = None        # Pour ne pas spammer la notif d'étoile


def get_access_token():
    url = "https://api.intra.42.fr/oauth/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": UID,
        "client_secret": SECRET
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        print(f"Erreur Token: {e}")
        return None


def send_notification(title, message):
    """Envoie une notif système si plyer est installé."""
    print(f"NOTIFICATION: {title} - {message}")  # Log console
    if PLYER_AVAILABLE:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name='42 Matrix Timer',
                timeout=10
            )
        except Exception as e:
            print(f"Erreur plyer: {e}")


def check_timer_loop():
    """Thread qui vérifie les évals ET le timer de 42 min en arrière-plan."""
    global timer_thread_running, monitored_user, notified_events, last_star_time
    
    print("Démarrage du monitoring...")
    
    while timer_thread_running:
        try:
            # 1. Récupération sécurisée du user
            with timer_lock:
                current_user = monitored_user
            
            if not current_user:
                time.sleep(60)
                continue
            
            # 2. Token
            token = get_access_token()
            if not token:
                time.sleep(60)
                continue
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # === PARTIE A : CHECK DES ÉVALUATIONS ===
            try:
                url_evals = f"https://api.intra.42.fr/v2/users/{current_user}/scale_teams/as_corrector"
                resp_eval = requests.get(url_evals, headers=headers)
                
                if resp_eval.status_code == 200:
                    scale_teams = resp_eval.json()
                    now = datetime.now(timezone.utc)
                    
                    for event in scale_teams:
                        if event.get('begin_at'):
                            begin_time = parser.isoparse(event['begin_at'])
                            time_diff = (begin_time - now).total_seconds()
                            event_id = f"{event.get('id')}_{event.get('begin_at')}"
                            
                            # Si c'est dans moins de 5 min (300s) et pas encore notifié
                            if 0 <= time_diff <= 300 and event_id not in notified_events:
                                team_name = event.get('team', {}).get('name', 'Inconnue')
                                m_left = int(time_diff / 60)
                                send_notification(
                                    "⚠️ Évaluation imminente !",
                                    f"Correction {team_name} dans {m_left} min !"
                                )
                                notified_events.add(event_id)
            except Exception as e:
                print(f"Erreur check évals: {e}")

            # === PARTIE B : CHECK TIMER ÉTOILE (42 MIN) ===
            try:
                # On ne prend que la dernière session
                url_loc = f"https://api.intra.42.fr/v2/users/{current_user}/locations?page[size]=1"
                resp_loc = requests.get(url_loc, headers=headers)
                
                if resp_loc.status_code == 200 and resp_loc.json():
                    last_session = resp_loc.json()[0]
                    end_at_str = last_session.get('end_at')
                    
                    # Si end_at existe, c'est que l'utilisateur est déconnecté
                    if end_at_str:
                        end_time = parser.isoparse(end_at_str)
                        now = datetime.now(timezone.utc)
                        diff_seconds = (now - end_time).total_seconds()
                        
                        # 42 minutes = 2520 secondes
                        if diff_seconds >= 2520:
                            # Si on n'a pas encore notifié pour CETTE session précise
                            if last_star_time != end_at_str:
                                send_notification(
                                    "⭐ Étoile Disponible !",
                                    "Les 42 minutes sont passées. Tu peux reprendre une place !"
                                )
                                last_star_time = end_at_str
                        else:
                            # Juste pour info dans la console
                            reste = int((2520 - diff_seconds) / 60)
                            # print(f"DEBUG: Reste {reste} min avant étoile.")
                            
            except Exception as e:
                print(f"Erreur check étoile: {e}")

        except Exception as e:
            print(f"Erreur générale boucle: {e}")
        
        # Pause de 60 secondes entre chaque vérification
        time.sleep(60)


@app.route('/logtime/<login>')
def get_logtime(login):
    global monitored_user, timer_thread, timer_thread_running
    
    # Gestion du thread de monitoring
    if not timer_thread_running:
        with timer_lock:
            monitored_user = login
        timer_thread_running = True
        timer_thread = threading.Thread(target=check_timer_loop, daemon=True)
        timer_thread.start()
        print(f"Thread lancé pour {login}")
    elif monitored_user != login:
        with timer_lock:
            monitored_user = login
        print(f"User changé pour {login}")
    
    print(f"Récupération logtime pour {login}...")
    token = get_access_token()
    if not token:
        return jsonify({"error": "Failed to get token"}), 500

    headers = {"Authorization": f"Bearer {token}"}
    all_locations = []
    page = 1

    # Récupération de l'historique (limité ici pour aller plus vite, ou boucle complète)
    while True:
        url = f"https://api.intra.42.fr/v2/users/{login}/locations?page[size]=100&page[number]={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        all_locations.extend(data)
        if len(data) < 100:
            break
        page += 1

    # Calcul stats par poste
    pc_stats = {}
    for loc in all_locations:
        host = loc['host']
        if not loc['begin_at']: continue
        
        start = parser.isoparse(loc['begin_at'])
        if loc['end_at']:
            end = parser.isoparse(loc['end_at'])
        else:
            end = datetime.now(timezone.utc)

        duration = (end - start).total_seconds()
        
        if host in pc_stats:
            pc_stats[host] += duration
        else:
            pc_stats[host] = duration

    # Formatage
    formatted_data = {}
    for host, seconds in pc_stats.items():
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0 or minutes > 0:
            formatted_data[host] = f"{hours}h{minutes}"

    return jsonify(formatted_data)


if __name__ == '__main__':
    print("Serveur lancé sur http://0.0.0.0:5000")
    app.run(port=5000, host='0.0.0.0', debug=True)