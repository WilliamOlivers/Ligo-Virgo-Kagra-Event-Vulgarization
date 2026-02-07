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
    
    # --- LE FILTRE MAGIQUE "SIGNIFICANT O4" ---
    # 1. category: "Production" -> Uniquement les vraies données
    # 2. label: "GCN_PRELIM_SENT" -> Uniquement celles qui ont déclenché une alerte publique
    # 3. -label: "RETRACTION" -> On exclut celles qui ont été annulées ensuite
    query = 'category: "Production" label: "GCN_PRELIM_SENT" -label: "RETRACTION"'
    
    params = {
        'query': query,
        'count': 10,        # On prend les 10 dernières significatives
        'order': '-created' # Les plus récentes d'abord
    }
    
    print(f"Recherche des événements significatifs O4 sur GraceDB...")
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            events = data.get('superevents', data.get('results', []))
            print(f"Trouvé : {len(events)} candidats significatifs.")
            return events
        else:
            print(f"Erreur API ({response.status_code}): {response.text}")
            return []
    except Exception as e:
        print(f"Erreur Fetch: {e}")
        return []

def vulgarize_event(event):
    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    far = event.get('far', 'Inconnu')
    instruments = event.get('instruments', 'Inconnu')
    
    # On prépare le contexte pour l'IA
    context_str = f"ID: {evt_id}, Labels: {labels}, FAR: {far}, Instruments: {instruments}"
    
    print(f"--- Analyse scientifique de {evt_id} ---")

    prompt = f"""
    Tu es un astrophysicien expert. Analyse cette détection d'onde gravitationnelle CONFIRMÉE et SIGNIFICATIVE (O4).
    
    Données brutes : {context_str}

    Tâche :
    1.  **Titre** : Format "Type d'événement (Date)". Ex: "Fusion de Trous Noirs (12 Mai 2023)".
    2.  **Type** : Déduis-le des labels (BBH=Trous noirs, BNS=Étoiles à neutrons, NSBH=Mixte). Si incertain, mets "Événement Cosmique".
    3.  **Date** : Convertis l'ID (S230512...) ou la date de création en format lisible français (ex: "12 Mai 2023").
    4.  **Résumé** : Un paragraphe dense et précis (style encyclopédie). Explique la nature de la fusion et pourquoi c'est un événement majeur (significatif). Mentionne la distance si déductible ou parle de "l'Univers lointain".
    5.  **Score** : Donne une note de "Rareté" sur 10. (BBH standard = 6, BNS = 9, Fusion proche = 10).

    Réponds UNIQUEMENT via ce JSON :
    {{
        "title": "...",
        "event_type": "BBH / BNS / NSBH",
        "date_readable": "...",
        "description": "...",
        "scientific_score": 0
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erreur OpenAI: {e}")
        return None

def main():
    existing_data = load_existing_data()
    existing_ids = {entry['id'] for entry in existing_data if 'id' in entry}
    
    raw_events = fetch_gracedb_events()
    new_entries = []

    for event in raw_events:
        evt_id = event['superevent_id']
        
        # On traite si c'est nouveau
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
        # On garde les plus récents en haut
        updated_data = new_entries + existing_data
        # Optionnel : On peut limiter la taille totale du fichier si on veut
        # updated_data = updated_data[:50] 
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"Ajout de {len(new_entries)} événements majeurs.")
    else:
        print("Aucun nouvel événement significatif trouvé.")

if __name__ == "__main__":
    main()
