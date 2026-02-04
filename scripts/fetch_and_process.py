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
    # Headers pour éviter d'être bloqué comme un "bot" basique
    headers = {
        'User-Agent': 'MyGWProject/1.0 (Educational; contact@example.com)'
    }
    # On ajuste la query pour être sûr
    params = {'query': 'category: Production', 'count': 10, 'order': '-created'}
    
    print(f"Connexion à {GRACEDB_URL}...")
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # --- BLOC DE DÉBOGAGE ---
            # Si 'results' n'est pas là, on affiche les clés disponibles pour comprendre
            if isinstance(data, dict) and 'results' not in data:
                print(f"ATTENTION: Pas de clé 'results'. Clés reçues : {list(data.keys())}")
                # Parfois l'API renvoie 'superevents' au lieu de 'results'
                if 'superevents' in data:
                    return data['superevents']
            
            # Si c'est directement une liste (cas rare mais possible)
            if isinstance(data, list):
                return data
                
            return data.get('results', [])
        else:
            print(f"Erreur API: {response.text}")
            return []
            
    except Exception as e:
        print(f"Exception lors du fetch: {e}")
        return []

def vulgarize_event(event):
    """Utilise OpenAI pour expliquer l'événement."""
    
    # Sécurité si l'event est mal formé
    if not event or 'superevent_id' not in event:
        return None

    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    # Gestion sécurisée des liens
    link = event.get('links', {}).get('self', 'N/A')
    far = event.get('far', 'N/A') 
    
    print(f"Vulgarisation en cours pour {evt_id}...")

    prompt = f"""
    Agis comme un expert en astrophysique et vulgarisation.
    Voici une détection d'onde gravitationnelle (ID: {evt_id}) :
    - Labels: {', '.join(labels)}
    - FAR: {far}
    
    Tâche :
    1. Titre accrocheur en Français.
    2. Résumé (max 60 mots) en Français simple (niveau collège).
    3. Score d'excitation (1-10).
    
    Réponds uniquement au format JSON valide :
    {{
        "title": "...",
        "summary": "...",
        "excitement_score": 0
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Erreur OpenAI sur {evt_id}: {e}")
        return None

def main():
    existing_data = load_existing_data()
    # Création d'un set d'IDs existants pour éviter les doublons
    existing_ids = {entry['id'] for entry in existing_data if 'id' in entry}
    
    raw_events = fetch_gracedb_events()
    
    if not raw_events:
        print("Aucun événement récupéré. Fin du script.")
        return

    new_entries = []
    print(f"Events trouvés sur GraceDB : {len(raw_events)}")

    for event in raw_events:
        # Vérification de sécurité
        if 'superevent_id' not in event:
            continue
            
        evt_id = event['superevent_id']
        
        if evt_id not in existing_ids:
            vulgarized = vulgarize_event(event)
            
            if vulgarized:
                new_entry = {
                    "id": evt_id,
                    "date": event.get('created', datetime.now().isoformat()),
                    "url": event.get('links', {}).get('self', ''),
                    "title": vulgarized.get('title', 'Événement Inconnu'),
                    "summary": vulgarized.get('summary', 'Pas de résumé disponible'),
                    "score": vulgarized.get('excitement_score', 5)
                }
                new_entries.append(new_entry)
    
    if new_entries:
        updated_data = new_entries + existing_data
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"SUCCÈS : {len(new_entries)} nouveaux événements ajoutés.")
    else:
        print("Aucun nouvel événement à traiter.")

if __name__ == "__main__":
    main()
