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
    
    # --- LA REQUÊTE CIBLÉE ---
    # Pour obtenir la liste "O4 Significant Detection Candidates" (les ~254 events) :
    # 1. public: True -> Visible sans authentification
    # 2. category: "Production" -> Pas de tests
    # 3. label: "GCN_PRELIM_SENT" -> Preuve qu'une alerte "Significative" a été envoyée
    # 4. created > 2023-05-24 -> Début du run O4
    
    # Note: On encode explicitement la requête pour éviter les erreurs d'URL
    query_string = 'public: True category: "Production" label: "GCN_PRELIM_SENT" created > "2023-05-24"'
    
    params = {
        'query': query_string,
        'count': 10,         # On commence par les 10 plus récents pour tester
        'order': '-created'
    }
    
    print(f"Connexion à GraceDB avec filtre : [{query_string}]")
    
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        
        # DEBUG : Si ça échoue, on veut savoir pourquoi
        if response.status_code != 200:
            print(f"ERREUR API ({response.status_code}) : {response.text}")
            # Tentative de fallback sur une requête plus simple si la première échoue
            print("Tentative de requête simplifiée...")
            params['query'] = 'public: True category: "Production" created > "2023-05-24"'
            response = requests.get(GRACEDB_URL, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # GraceDB renvoie parfois 'superevents' ou directement la liste dans 'results' selon la version de l'API visée
            events = data.get('superevents', data.get('results', []))
            
            # Filtrage manuel ultime pour être sûr de ne pas avoir de Rétractation
            valid_events = []
            for evt in events:
                labels = evt.get('labels', [])
                if 'RETRACTION' not in labels:
                    valid_events.append(evt)
            
            print(f"Succès : {len(valid_events)} événements significatifs récupérés (sur {len(events)} bruts).")
            return valid_events
        else:
            print(f"Échec total API : {response.text}")
            return []
            
    except Exception as e:
        print(f"Exception critique lors du fetch : {e}")
        return []

def vulgarize_event(event):
    evt_id = event['superevent_id']
    
    # On ignore les événements déjà traités pour économiser les tokens OpenAI, 
    # mais ici on veut regénérer la DB donc on traite tout ce qui est passé.
    
    labels = event.get('labels', [])
    far = event.get('far', 'Non spécifié')
    
    print(f">>> Vulgarisation de {evt_id}...")

    prompt = f"""
    Tu es un expert en astrophysique pour le grand public.
    Sujet : Onde gravitationnelle confirmée (ID: {evt_id}).
    Labels: {labels}
    FAR (Fausse Alarme): {far}
    
    Tâche : Crée une fiche technique claire et captivante.
    1. Titre : Type d'événement + Date. Ex: "Fusion de Trous Noirs (12 Mai 2023)".
    2. Type : BBH (Trous Noirs), BNS (Étoiles à Neutrons), ou NSBH (Mixte).
    3. Résumé : 40 mots max. L'essentiel : c'est quoi ? C'est loin ? C'est violent ?
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
        print("ATTENTION: Liste vide retournée par GraceDB. Vérifiez les logs ci-dessus.")
        return

    new_entries = []
    
    for event in events:
        evt_id = event['superevent_id']
        
        # Pour le développement, on traite même si ça existe déjà pour mettre à jour le format
        if evt_id not in existing_ids or True: 
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
                # On ajoute à existing_ids pour éviter doublon dans la boucle
                existing_ids.add(evt_id)
    
    if new_entries:
        # On remplace la base ou on l'étend. Ici on recrée une base propre avec les 10 derniers.
        # Pour la prod, il faudra changer la logique pour "append".
        
        # Tri par date décroissante
        new_entries.sort(key=lambda x: x['date'], reverse=True)
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(new_entries, f, indent=2)
        print(f"Base de données générée avec succès : {len(new_entries)} événements.")
    else:
        print("Aucun événement traité.")

if __name__ == "__main__":
    main()
