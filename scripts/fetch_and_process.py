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
        return json.load(f)

def fetch_gracedb_events():
    # On récupère les 10 derniers superevents publics
    params = {'query': 'category: Production', 'count': 10, 'order': '-created'}
    response = requests.get(GRACEDB_URL, params=params)
    if response.status_code == 200:
        return response.json()['results']
    return []

def vulgarize_event(event):
    """Utilise OpenAI pour expliquer l'événement."""
    
    # Extraction des données clés (ex: probabilité qu'il y ait une étoile à neutrons)
    labels = event.get('labels', [])
    far = event.get('far', 'N/A') # False Alarm Rate
    
    prompt = f"""
    Agis comme un expert en astrophysique et vulgarisation scientifique.
    Voici les données brutes d'une détection d'onde gravitationnelle (ID: {event['superevent_id']}) :
    - Lien: {event['links']['self']}
    - Labels: {', '.join(labels)}
    - Taux de fausse alarme (FAR): {far}
    
    Tâche :
    1. Donne un titre accrocheur en Français (ex: "Collision de Trous Noirs détectée").
    2. Écris un court paragraphe (max 60 mots) en Français très simple expliquant ce qui s'est probablement passé. Utilise des analogies si nécessaire.
    3. Estime le "Niveau d'excitation" sur une échelle de 1 à 10 (10 = fusion d'étoiles à neutrons confirmée avec lumière visible).
    
    Réponds uniquement au format JSON valide :
    {{
        "title": "...",
        "summary": "...",
        "excitement_score": 0
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Modèle rapide et économique
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erreur OpenAI: {e}")
        return None

def main():
    existing_data = load_existing_data()
    existing_ids = {entry['id'] for entry in existing_data}
    
    raw_events = fetch_gracedb_events()
    new_entries = []

    print(f"Events trouvés sur GraceDB : {len(raw_events)}")

    for event in raw_events:
        evt_id = event['superevent_id']
        
        if evt_id not in existing_ids:
            print(f"Traitement du nouvel événement : {evt_id}")
            vulgarized = vulgarize_event(event)
            
            if vulgarized:
                new_entry = {
                    "id": evt_id,
                    "date": event['created'],
                    "url": event['links']['self'],
                    "title": vulgarized['title'],
                    "summary": vulgarized['summary'],
                    "score": vulgarized['excitement_score']
                }
                new_entries.append(new_entry)
    
    if new_entries:
        # Ajouter les nouveaux en haut de la liste
        updated_data = new_entries + existing_data
        # Sauvegarder
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"{len(new_entries)} nouveaux événements ajoutés.")
    else:
        print("Aucun nouvel événement à traiter.")

if __name__ == "__main__":
    main()
