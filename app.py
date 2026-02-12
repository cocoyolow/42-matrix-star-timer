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

# Identifiants Intra
UID = "ENTER_YOUR_UID_HERE"
SECRET = "ENTER_YOUR_SECRET_HERE"

# Global variables for timer monitoring
monitored_user = None
timer_thread = None
timer_thread_running = False


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
    """Send a system notification if plyer is available."""
    if PLYER_AVAILABLE:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name='42 Matrix Timer',
                timeout=10
            )
            print(f"Notification sent: {title} - {message}")
        except Exception as e:
            print(f"Error sending notification: {e}")
    else:
        print(f"Notification (plyer not available): {title} - {message}")


def check_timer_loop():
    """Background thread that monitors upcoming scale_teams (evaluations)."""
    global timer_thread_running, monitored_user
    
    notified_events = set()  # Track which events we've already notified about
    
    print(f"Starting timer monitoring for user: {monitored_user}")
    
    while timer_thread_running:
        try:
            if not monitored_user:
                time.sleep(60)
                continue
            
            token = get_access_token()
            if not token:
                print("Failed to get token for timer check")
                time.sleep(60)
                continue
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # Fetch upcoming scale_teams (evaluations) for the user
            url = f"https://api.intra.42.fr/v2/users/{monitored_user}/scale_teams/as_corrector"
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"Failed to fetch scale_teams: {response.status_code}")
                time.sleep(60)
                continue
            
            scale_teams = response.json()
            now = datetime.now(timezone.utc)
            
            for event in scale_teams:
                # Only check upcoming events (not past ones)
                if event.get('begin_at'):
                    begin_time = parser.isoparse(event['begin_at'])
                    time_diff = (begin_time - now).total_seconds()
                    
                    # Create a unique identifier for this event
                    event_id = f"{event.get('id')}_{event.get('begin_at')}"
                    
                    # Check if the event is imminent (within 5 minutes) and not already notified
                    if 0 <= time_diff <= 300 and event_id not in notified_events:
                        # Extract relevant information
                        team_name = event.get('team', {}).get('name', 'Unknown team')
                        minutes_left = int(time_diff / 60)
                        
                        send_notification(
                            title="42 Evaluation Starting Soon!",
                            message=f"Evaluation for {team_name} starts in {minutes_left} minute(s)!"
                        )
                        notified_events.add(event_id)
                        print(f"Notified about evaluation: {team_name} in {minutes_left} minutes")
            
            # Clean up old event IDs from notified_events (events more than 1 hour old)
            notified_events = {eid for eid in notified_events 
                             if not any(eid.startswith(str(e.get('id'))) 
                                      for e in scale_teams 
                                      if e.get('begin_at') and 
                                      (now - parser.isoparse(e['begin_at'])).total_seconds() > 3600)}
            
        except Exception as e:
            print(f"Error in timer check loop: {e}")
        
        # Check every 60 seconds
        time.sleep(60)
    
    print("Timer monitoring stopped")


@app.route('/logtime/<login>')
def get_logtime(login):
    global monitored_user, timer_thread, timer_thread_running
    
    # Start the timer monitoring thread if not already running
    if not timer_thread_running:
        monitored_user = login
        timer_thread_running = True
        timer_thread = threading.Thread(target=check_timer_loop, daemon=True)
        timer_thread.start()
        print(f"Started timer monitoring thread for user: {login}")
    elif monitored_user != login:
        # Update monitored user if it changed
        monitored_user = login
        print(f"Updated monitored user to: {login}")
    
    print(f"Calcul du logtime pour {login}...")
    token = get_access_token()
    if not token:
        return jsonify({"error": "Failed to get token"}), 500

    headers = {"Authorization": f"Bearer {token}"}
    all_locations = []
    page = 1

    # Récupération de TOUTES les pages
    while True:
        url = f"https://api.intra.42.fr/v2/users/{login}/locations?page[size]=100&page[number]={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        all_locations.extend(data)
        print(f"Page {page} récupérée ({len(data)} sessions)")
        if len(data) < 100:
            break
        page += 1

    # --- CALCUL DU TEMPS PAR POSTE ---
    pc_stats = {}

    for loc in all_locations:
        host = loc['host']
        start = parser.isoparse(loc['begin_at'])

        # Gestion session active (pas de end_at)
        if loc['end_at']:
            end = parser.isoparse(loc['end_at'])
        else:
            end = datetime.now(timezone.utc)
            # On peut ajouter un indicateur visuel pour le poste actuel si tu veux
            # host = host

        duration = (end - start).total_seconds()

        # On additionne le temps pour ce poste
        if host in pc_stats:
            pc_stats[host] += duration
        else:
            pc_stats[host] = duration

    # Formatage en texte lisible (ex: "10h30")
    formatted_data = {}
    for host, seconds in pc_stats.items():
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)

        # On ne garde que si > 0
        if hours > 0 or minutes > 0:
            formatted_data[host] = f"{hours}h{minutes}"

    print(f"Envoi des stats pour {len(formatted_data)} postes.")
    return jsonify(formatted_data)


if __name__ == '__main__':
    print("Serveur lancé sur http://0.0.0.0:5000")
    app.run(port=5000, host='0.0.0.0', debug=True)
