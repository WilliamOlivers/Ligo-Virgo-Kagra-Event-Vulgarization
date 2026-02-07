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
    
    # --- STRATÉGIE ROBUSTE ---
    # On retire les guillemets et les symboles mathématiques (>) qui cassent l'URL.
    # On demande juste : "Donne-moi ce qui est Production ET qui a envoyé une alerte".
    query = 'category: Production label: GCN_PRELIM_SENT'
    
    params = {
        'query': query,
        'count': 20,         # On prend les 20 derniers candidats sérieux
        'order': '-created'
    }
    
    print(f"Connexion à GraceDB avec filtre simplifié : [{query}]")
    
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('superevents', data.get('results', []))
            
            # --- FILTRAGE LOCAL (PYTHON) ---
            # C'est ici qu'on applique la sécurité "O4" et "Retraction"
            valid_events = []
            for evt in events:
                # 1. Filtre Rétractation (Fausse alarme)
                labels = evt.get('labels', [])
                if 'RETRACTION' in labels:
                    continue
                
                # 2. Filtre Date (Run O4 a commencé fin Mai 2023)
                # La date est au format ISO : "2023-05-29T..."
                created_date = evt.get('created', '')
                if created_date < "2023-05-24":
                    continue
                    
                valid_events.append(evt)
            
            print(f"Succès : {len(valid_events)} événements O4 significatifs validés.")
            return valid_events
        else:
            print(f"ERREUR API ({response.status_code}) : {response.text}")
            return []
            
    except Exception as e:
        print(f"Exception lors du fetch : {e}")
        return []

def vulgarize_event(event):
    evt_id = event['superevent_id']
    
    print(f">>> Vulgarisation de {evt_id}...")
    
    # Extraction sécurisée des données
    labels = event.get('labels', [])
    far = event.get('far', 'Non spécifié')
    instruments = event.get('instruments', 'N/A')

    prompt = f"""
    Tu es un expert en astrophysique.
    Sujet : Onde gravitationnelle CONFIRMÉE (ID: {evt_id}).
    Labels: {labels}
    Instruments: {instruments}
    FAR: {far}
    
    Tâche : Crée une fiche technique vulgarisée style Wikipédia/Grokipedia.
    1. Titre : "Type (Date)". Ex: "Fusion de Trous Noirs (12 Mai 2023)".
    2. Type : BBH (Trous Noirs), BNS (Étoiles à Neutrons), NSBH (Mixte). Si incertain: "Fusion Compacte".
    3. Résumé : 40-50 mots max. Factuel, précis, scientifique mais clair.
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
    existing_data = load_existing_data()
    existing_ids = {entry['id'] for entry in existing_data if 'id' in entry}
    
    events = fetch_gracedb_events()
    
    if not events:
        print("Aucun événement à traiter.")
        return

    new_entries = []
    
    for event in events:
        evt_id = event['superevent_id']
        
        # On ne traite que les nouveaux ID
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
        # Fusion : Nouveaux + Anciens
        updated_data = new_entries + existing_data
        # Tri : Du plus récent au plus vieux
        updated_data.sort(key=lambda x: x['date'], reverse=True)
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"Base de données mise à jour : {len(new_entries)} événements ajoutés.")
    else:
        print("Base déjà à jour.")

if __name__ == "__main__":
    main()
