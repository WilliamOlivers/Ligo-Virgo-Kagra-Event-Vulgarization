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
    
    # STRATÉGIE "FETCH WIDE" : On demande simplement tout ce qui est "Production"
    # On augmente le count à 50 pour être sûr d'attraper les rares événements significatifs
    # parmi le bruit.
    params = {
        'query': 'category: Production', 
        'count': 50,
        'order': '-created'
    }
    
    print(f"Connexion à GraceDB (Récupération large)...")
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Gestion de la structure de réponse variable (results vs superevents)
            events = data.get('superevents', data.get('results', []))
            print(f"Brut : {len(events)} événements 'Production' récupérés.")
            return events
        else:
            print(f"Erreur API ({response.status_code}): {response.text}")
            return []
    except Exception as e:
        print(f"Erreur Fetch: {e}")
        return []

def is_significant_O4(event):
    """
    Filtre local pour déterminer si l'événement vaut le coup.
    Critères : O4, Alertée envoyée, Pas de rétractation.
    """
    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    
    # 1. Vérifier si c'est O4 (L'ID commence par S23 ou S24...)
    # O4 a commencé en mai 2023.
    if not (evt_id.startswith('S23') or evt_id.startswith('S24') or evt_id.startswith('S25')):
        # print(f"Ignoré {evt_id}: Pas O4")
        return False

    # 2. Vérifier si une alerte publique a été envoyée
    if 'GCN_PRELIM_SENT' not in labels and 'GCN_NO_SKYMAP_SENT' not in labels:
        # print(f"Ignoré {evt_id}: Pas d'alerte publique (Low Significance)")
        return False

    # 3. Vérifier s'il a été rétracté (Fausse alarme annulée)
    if 'RETRACTION' in labels:
        print(f"Ignoré {evt_id}: RÉTRACTÉ (Fausse alarme)")
        return False

    return True

def vulgarize_event(event):
    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    far = event.get('far', 'Inconnu')
    
    print(f">>> Traitement IA de l'événement significatif : {evt_id}")

    prompt = f"""
    Tu es un astrophysicien expert.
    Données brutes : ID: {evt_id}, Labels: {labels}, FAR: {far}
    
    Tâche : Crée une fiche technique pour cette onde gravitationnelle CONFIRMÉE.
    1. Titre: "Type (Date)". Ex: "Fusion Trous Noirs (12 Mai 2023)".
    2. Type: BBH (Trous Noirs), BNS (Étoiles Neutrons), ou NSBH.
    3. Résumé: 40-50 mots, dense, scientifique, encyclopédique.
    4. Score: Rareté/Importance sur 10. (BBH=6, BNS=9).

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
    
    raw_events = fetch_gracedb_events()
    significant_events = []

    # ÉTAPE DE FILTRAGE LOCAL
    for event in raw_events:
        if is_significant_O4(event):
            significant_events.append(event)
    
    print(f"Après filtrage : {len(significant_events)} événements significatifs à traiter/vérifier.")

    new_entries = []
    for event in significant_events:
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
        updated_data = new_entries + existing_data
        # On trie par date décroissante pour être sûr
        updated_data.sort(key=lambda x: x['date'], reverse=True)
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"SUCCÈS : {len(new_entries)} ajoutés à la base.")
    else:
        print("Rien de nouveau à ajouter.")

if __name__ == "__main__":
    main()
