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
    headers = {
        'User-Agent': 'GrokipediaGW/1.0 (Educational)',
        'Accept': 'application/json'
    }
    
    # --- CORRECTION DE LA REQUÊTE ---
    # On a retiré "public: True" qui causait l'erreur 400.
    # On garde les critères stricts pour les événements significatifs O4.
    # Note : Les guillemets autour des valeurs sont importants pour l'API.
    
    query = 'category: "Production" label: "GCN_PRELIM_SENT" created > "2023-05-24"'
    
    params = {
        'query': query,
        'count': 15,         # On prend les 15 derniers pour être sûr
        'order': '-created'
    }
    
    print(f"Connexion à GraceDB avec filtre : [{query}]")
    
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # L'API publique renvoie généralement une clé 'superevents'
            events = data.get('superevents', data.get('results', []))
            
            # Filtrage de sécurité : on retire les rétractations
            valid_events = []
            for evt in events:
                labels = evt.get('labels', [])
                # Si 'RETRACTION' est dans les labels, c'est une fausse alarme
                if 'RETRACTION' not in labels:
                    valid_events.append(evt)
            
            print(f"Succès : {len(valid_events)} événements significatifs récupérés.")
            return valid_events
        else:
            print(f"ERREUR API ({response.status_code}) : {response.text}")
            return []
            
    except Exception as e:
        print(f"Exception lors du fetch : {e}")
        return []

def vulgarize_event(event):
    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    far = event.get('far', 'Non spécifié')
    
    print(f">>> Vulgarisation de {evt_id}...")

    prompt = f"""
    Tu es un expert en astrophysique.
    Sujet : Onde gravitationnelle confirmée (ID: {evt_id}).
    Labels: {labels}
    FAR: {far}
    
    Tâche : Crée une fiche technique vulgarisée style Wikipédia.
    1. Titre : "Type (Date)". Ex: "Fusion de Trous Noirs (12 Mai 2023)".
    2. Type : BBH (Trous Noirs), BNS (Étoiles à Neutrons), NSBH (Mixte).
    3. Résumé : 40 mots max. L'essentiel, le plus factuel possible.
    4. Score : Importance scientifique /10 (BBH=6, BNS=9, Exceptionnel=10).

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
    # On charge l'existant pour éviter les doublons, 
    # mais pour ce test, on peut vouloir tout rafraîchir.
    existing_data = load_existing_data()
    existing_ids = {entry['id'] for entry in existing_data if 'id' in entry}
    
    events = fetch_gracedb_events()
    
    if not events:
        print("Aucun événement trouvé. Vérifiez la requête.")
        return

    new_entries = []
    
    for event in events:
        evt_id = event['superevent_id']
        
        # Condition pour traiter seulement les nouveaux (ou tout le monde si on vide le JSON avant)
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
                existing_ids.add(evt_id)
    
    if new_entries:
        # On ajoute les nouveaux en tête de liste
        updated_data = new_entries + existing_data
        # Tri par date décroissante pour être propre
        updated_data.sort(key=lambda x: x['date'], reverse=True)
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"Base de données mise à jour : {len(new_entries)} nouveaux événements ajoutés.")
    else:
        print("Base déjà à jour, rien de nouveau.")

if __name__ == "__main__":
    main()
