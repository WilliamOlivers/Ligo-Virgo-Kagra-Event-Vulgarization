import requests
import json
import os
from openai import OpenAI
from datetime import datetime

# Configuration
GRACEDB_URL = "https://gracedb.ligo.org/api/superevents/"
DATA_FILE = "data/events.json"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def load_existing_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def fetch_gracedb_events():
    headers = {'User-Agent': 'GrokipediaGW/1.0 (Educational)'}
    
    # --- LA REQUÊTE EXACTE DU SITE "O4 SIGNIFICANT" ---
    # Nous demandons à l'API de faire le tri pour nous.
    # label="GCN_PRELIM_SENT" : Signifie que c'est une détection confirmée publique.
    # created > 2023-05-24 : Date de début du run O4.
    
    query = 'category: "Production" label: "GCN_PRELIM_SENT" created > "2023-05-24"'
    
    params = {
        'query': query,
        'count': 20,         # On récupère les 20 plus récents de cette liste d'élite
        'order': '-created'  # Du plus récent au plus ancien
    }
    
    print(f"Interrogation de GraceDB avec filtre : {query}")
    
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            events = data.get('superevents', data.get('results', []))
            print(f"GraceDB a renvoyé {len(events)} événements significatifs.")
            return events
        else:
            print(f"Erreur API ({response.status_code}): {response.text}")
            return []
    except Exception as e:
        print(f"Erreur de connexion: {e}")
        return []

def vulgarize_event(event):
    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    
    # Vérification ultime anti-rétractation (au cas où l'API en laisserait passer un)
    if 'RETRACTION' in labels:
        print(f"Skipping {evt_id} (Rétracté)")
        return None

    print(f">>> Vulgarisation de {evt_id}...")

    prompt = f"""
    Tu es un expert astrophysicien. Voici une onde gravitationnelle CONFIRMÉE du run O4 (ID: {evt_id}).
    Labels: {labels}
    
    Tâche : Crée une fiche technique vulgarisée.
    1. Titre: "Type (Date)". Ex: "Fusion de Trous Noirs (14 Août 2023)".
    2. Type: BBH (Trous noirs), BNS (Étoiles neutrons), NSBH (Mixte). Déduis-le.
    3. Résumé: 40-50 mots. Explique la violence de l'événement et sa distance (lointain/proche).
    4. Score: Note d'importance scientifique /10. (BBH=6, BNS=9, Exceptionnel=10).

    JSON attendu :
    {{
        "title": "...",
        "event_type": "BBH",
        "date_readable": "...",
        "description": "...",
        "scientific_score": 6
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erreur OpenAI: {e}")
        return None

def main():
    existing_data = load_existing_data()
    existing_ids = {entry['id'] for entry in existing_data if 'id' in entry}
    
    events = fetch_gracedb_events()
    new_entries = []

    for event in events:
        evt_id = event['superevent_id']
        
        if evt_id not in existing_ids:
            vulgarized = vulgarize_event(event)
            if vulgarized:
                new_entry = {
                    "id": evt_id,
                    "date": event['created'],
                    "title": vulgarized.get('title'),
                    "type": vulgarized.get('event_type'),
                    "readable_date": vulgarized.get('date_readable'),
                    "summary": vulgarized.get('description'),
                    "score": vulgarized.get('scientific_score', 5),
                    "url": event['links']['self']
                }
                new_entries.append(new_entry)
    
    if new_entries:
        # Fusion et tri
        updated_data = new_entries + existing_data
        updated_data.sort(key=lambda x: x['date'], reverse=True)
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"Base de données mise à jour avec {len(new_entries)} événements majeurs.")
    else:
        print("Base déjà à jour.")

if __name__ == "__main__":
    main()
