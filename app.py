#!/usr/bin/env python3
from flask import Flask, jsonify
from flask_cors import CORS
import requests
from dateutil import parser
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

# Identifiants Intra
UID = "ENTER_YOUR_UID_HERE"
SECRET = "ENTER_YOUR_SECRET_HERE"


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


@app.route('/logtime/<login>')
def get_logtime(login):
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
