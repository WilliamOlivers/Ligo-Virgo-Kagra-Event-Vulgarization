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

def get_voevent_text(evt_id, voevents_url):
    """
    Récupère le contenu XML de la dernière alerte VOEvent pour extraire la distance.
    """
    try:
        # 1. Récupérer la liste des fichiers VOEvent
        r = requests.get(voevents_url, headers={'User-Agent': 'GrokipediaGW/1.0'})
        if r.status_code != 200: return ""
        
        voevents = r.json().get('voevents', [])
        if not voevents: return ""
        
        # 2. Prendre le plus récent (trié par 'sort_order' ou le dernier de la liste)
        # Les alertes s'appellent souvent 'Initial', 'Update', etc. On prend la dernière.
        latest_voevent = voevents[-1] 
        file_url = latest_voevent['links']['file']
        
        # 3. Télécharger le contenu XML
        xml_r = requests.get(file_url, headers={'User-Agent': 'GrokipediaGW/1.0'})
        if xml_r.status_code == 200:
            return xml_r.text[:5000] # On tronque pour ne pas saturer le prompt (la distance est au début)
    except Exception as e:
        print(f"Erreur VOEvent pour {evt_id}: {e}")
    return ""

def fetch_gracedb_events():
    headers = {'User-Agent': 'GrokipediaGW/1.0', 'Accept': 'application/json'}
    query = 'category: Production label: GCN_PRELIM_SENT'
    params = {'query': query, 'count': 15, 'order': '-created'}
    
    print(f"Connexion à GraceDB...")
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            events = data.get('superevents', data.get('results', []))
            
            valid_events = []
            for evt in events:
                labels = evt.get('labels', [])
                created = evt.get('created', '')
                if 'RETRACTION' in labels: continue
                if created < "2023-05-24": continue 
                valid_events.append(evt)
            return valid_events
        return []
    except Exception as e:
        print(f"Erreur Fetch: {e}")
        return []

def vulgarize_event(event):
    evt_id = event['superevent_id']
    labels = event.get('labels', [])
    
    # --- NO STRESS ---
    # On va chercher le fichier XML technique pour que l'IA puisse lire la distance exacte
    voevents_url = event['links']['voevents']
    xml_context = get_voevent_text(evt_id, voevents_url)
    
    print(f">>> Vulgarisation de {evt_id} (Recherche distance)...")

    prompt = f"""
    Tu es un expert en astrophysique.
    
    CONTEXTE :
    Onde gravitationnelle ID : "{evt_id}".
    Labels : {labels}
    
    EXTRAIT FICHIER TECHNIQUE (XML VOEvent) :
    \"\"\"{xml_context}\"\"\"

    TUTORIEL DATE :
    ID Format [Prefix][YYMMDD][Suffix]. 
    S230518h -> 230518 -> 18 Mai 2023.

    TACHE (JSON) :
    1. "title" : "Type (Date Décodée)". Ex: "Fusion de Trous Noirs (14 Mai 2023)".
    2. "event_type" : BBH, BNS, NSBH (déduit des labels ou du XML).
    3. "date_readable" : La date décodée.
    4. "description" : Résumé 40 mots max.
    5. "distance" : Cherche la valeur "Distance" dans le XML (souvent en Mpc).
       - Si tu la trouves, convertis-la approximativement en Milliards ou Millions d'années-lumière (1 Mpc = 3.26 Millions AL).
       - Affiche le résultat sous forme de texte court. Ex: "1.2 Milliards d'AL" ou "400 Millions d'AL".
       - Si introuvable, mets "Inconnue".

    Réponds UNIQUEMENT via ce JSON :
    {{
        "title": "...",
        "event_type": "...",
        "date_readable": "...",
        "description": "...",
        "distance": "..."
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
                    "display_date": vulgarized.get('date_readable'),
                    "title": vulgarized.get('title'),
                    "type": vulgarized.get('event_type'),
                    "summary": vulgarized.get('description'),
                    "distance": vulgarized.get('distance', 'Inconnue'), # Nouveau champ
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
        print(f"Succès : {len(new_entries)} ajouts.")
    else:
        print("Aucun nouvel événement.")

if __name__ == "__main__":
    main()
