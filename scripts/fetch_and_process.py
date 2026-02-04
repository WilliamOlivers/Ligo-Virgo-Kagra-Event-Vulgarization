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
    # On cherche les événements confirmés (category: Production)
    params = {'query': 'category: Production', 'count': 5, 'order': '-created'}
    
    print(f"Connexion à {GRACEDB_URL}...")
    try:
        response = requests.get(GRACEDB_URL, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('superevents', data.get('results', []))
        else:
            print(f"Erreur API: {response.text}")
            return []
    except Exception as e:
        print(f"Erreur Fetch: {e}")
        return []

def get_event_details(event_self_url):
    """
    Va chercher les détails spécifiques (probabilités) qui ne sont pas toujours
    dans la liste principale.
    """
    try:
        response = requests.get(event_self_url, headers={'User-Agent': 'GrokipediaGW/1.0'})
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {}

def vulgarize_event(event):
    evt_id = event['superevent_id']
    
    # 1. Récupération des détails pour avoir les probabilités (BBH, BNS, etc.)
    # L'API GraceDB met souvent ces infos dans un champ 'labels' ou il faut parser les fichiers logs.
    # Pour simplifier ici, nous allons donner le maximum de contexte brut à OpenAI.
    
    labels = event.get('labels', [])
    far = event.get('far', 'Inconnu')
    instruments = event.get('instruments', 'Inconnu')
    
    # Tentative d'extraire des infos implicites des labels (ex: ADVNO = pas d'événement astrophysique)
    context_str = f"ID: {evt_id}, Labels: {labels}, FAR: {far}, Instruments: {instruments}"
    
    print(f"--- Analyse scientifique de {evt_id} ---")

    # LE PROMPT "SCIENTIFIC DECODER"
    prompt = f"""
    Tu es un astrophysicien spécialisé dans l'analyse des ondes gravitationnelles.
    Ta mission : Décoder les métadonnées brutes de GraceDB pour créer une fiche technique claire et pédagogique.
    
    Données brutes :
    {context_str}

    CONSIGNES STRICTES DE RÉDACTION :
    1.  **Titre** : Pas de clickbait. Utilise le format : "Type d'événement probable (Date)". 
        - Exemple si BBH : "Coalescence de Trous Noirs (14 Août 2023)"
        - Exemple si BNS : "Fusion d'Étoiles à Neutrons (14 Août 2023)"
        - Si incertain ou "Terrestrial" : "Signal Non Classifié / Bruit probable"
    
    2.  **Type de Source (Décodage)** : Analyse les labels/ID.
        - Si tu vois 'BBH' ou labels similaires -> Explique que ce sont deux trous noirs.
        - Si tu vois 'BNS' -> Explique étoiles à neutrons.
        - Si 'MassGap' -> Explique l'objet mystère.
        - Si le FAR est élevé (ex: 1 fois par mois) -> Précise que c'est probablement du bruit.
        
    3.  **La Distance/Temps** : 
        - Décode l'ID (SYYMMDD) pour donner la date exacte en toutes lettres en Français.
        - Explique que le signal a voyagé depuis une galaxie lointaine (si astrophysique).
    
    4.  **Résumé Technique** : 
        - Utilise un ton encyclopédique (neutre, précis).
        - Explique ce que les instruments (H1, L1, V1) ont ressenti (une vibration de l'espace-temps inférieure à la taille d'un atome).
        - Évite les analogies enfantines ("c'est comme une vague"). Préfère "une perturbation de la métrique de l'espace-temps".

    Réponds UNIQUEMENT via ce JSON :
    {{
        "title": "Titre Scientifique",
        "event_type": "BBH / BNS / NSBH / Terrestrial",
        "date_readable": "14 Octobre 2023",
        "description": "Paragraphe explicatif de 50 mots max, style encyclopédie.",
        "scientific_score": (note de 1 à 10 basée sur la rareté. BBH=5, BNS=9, Terrestrial=1)
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2 # Température basse pour être factuel
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
        
        if evt_id not in existing_ids:
            # On ignore les événements marqués "Retracted" dans les labels si on veut être puriste
            # mais on laisse l'IA juger pour l'instant.
            
            vulgarized = vulgarize_event(event)
            
            if vulgarized:
                new_entry = {
                    "id": evt_id,
                    "date": event['created'],
                    "title": vulgarized.get('title'),
                    "type": vulgarized.get('event_type'), # Nouveau champ
                    "readable_date": vulgarized.get('date_readable'), # Nouveau champ
                    "summary": vulgarized.get('description'),
                    "score": vulgarized.get('scientific_score', 1),
                    "url": event['links']['self']
                }
                new_entries.append(new_entry)
    
    if new_entries:
        updated_data = new_entries + existing_data
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(updated_data, f, indent=2)
        print(f"Ajout de {len(new_entries)} fiches techniques.")
    else:
        print("Base de données à jour.")

if __name__ == "__main__":
    main()
