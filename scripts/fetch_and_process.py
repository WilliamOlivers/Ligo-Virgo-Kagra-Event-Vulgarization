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
    
    # Requête simple et robuste
    query = 'category: Production label: GCN_PRELIM_SENT'
    
    params = {
        'query': query,
        'count': 15,
        'order': '-created'
    }
    
    print(f"Connexion à GraceDB...")
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            events = data.get('superevents', data.get('results', []))
            
            # Filtrage basique (O4 + Pas de Rétractation)
            valid_events = []
            for evt in events:
                labels = evt.get('labels', [])
                created = evt.get('created', '')
                
                if 'RETRACTION' in labels: continue
                if created < "2023-05-24": continue # Début O4
                
                valid_events.append(evt)
            
            return valid_events
        return []
    except Exception as e:
        print(f"Erreur Fetch: {e}")
        return []

def vulgarize_event(event):
    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    far = event.get('far', 'Non spécifié')
    
    print(f">>> Vulgarisation de {evt_id}...")

    # --- LE TUTORIEL INTÉGRÉ AU PROMPT ---
    prompt = f"""
    Tu es un expert en astrophysique et communication scientifique.
    
    CONTEXTE :
    Tu dois analyser une onde gravitationnelle identifiée par l'ID : "{evt_id}".
    Labels associés : {labels}
    FAR (Fausse Alarme) : {far}

    TUTORIEL POUR DÉCODER LA DATE (IMPORTANT) :
    Les IDs GraceDB contiennent la date cachée. Format : [Prefix][YYMMDD][Suffix].
    1. Ignore le préfixe (S, GW, MS...).
    2. Prends les 6 premiers chiffres : ce sont YYMMDD.
    3. Si YY est entre 00 et 79, l'année est 20YY. (Ex: 23 = 2023).
    4. Convertis MM en nom de mois français.
    
    EXEMPLES :
    - ID "S190425z" -> 190425 -> 25 Avril 2019.
    - ID "GW170817" -> 170817 -> 17 Août 2017.
    - ID "S230518h" -> 230518 -> 18 Mai 2023.

    TACHE À RÉALISER (JSON) :
    1. "title" : Crée un titre au format "Type d'événement (Date Décodée)". Ex: "Fusion de Trous Noirs (14 Mai 2023)".
    2. "event_type" : Déduis le type (BBH, BNS, NSBH) d'après les labels ou la nature probable.
    3. "date_readable" : La date que tu as décodée (ex: "14 Mai 2023").
    4. "description" : Résumé de 40 mots max. Scientifique, précis, impactant.
    5. "scientific_score" : Note d'importance /10 (BBH=6, BNS=9, Exceptionnel=10).

    Réponds UNIQUEMENT via ce JSON :
    {{
        "title": "...",
        "event_type": "...",
        "date_readable": "...",
        "description": "...",
        "scientific_score": 0
    }}
    """

    try:
        response = client.chat.completions.create(
            # CORRECTION : Utilisation du vrai modèle existant
            model="gpt-4o-mini", 
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            # gpt-4o-mini SUPPORTE la température basse, ce qui aide à suivre le tuto date
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
                    "date": event['created'], # Date de tri (technique)
                    "display_date": vulgarized.get('date_readable'), # Date IA (Humaine)
                    "title": vulgarized.get('title'),
                    "type": vulgarized.get('event_type'),
                    "summary": vulgarized.get('description'),
                    "score": vulgarized.get('scientific_score', 5),
                    "url": event['links']['self']
                }
                new_entries.append(new_entry)
                existing_ids.add(evt_id)
    
    if new_entries:
        updated_data = new_entries + existing_data
        updated_data.sort(key=lambda x: x['date'], reverse=True)
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"Mise à jour réussie : {len(new_entries)} événements ajoutés.")
    else:
        print("Aucun nouvel événement.")

if __name__ == "__main__":
    main()
