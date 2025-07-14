from datetime import datetime
from typing import List, Optional, Dict
from collections import Counter

# Example artist-to-era mapping
ARTIST_ERA_MAP = {
    "Michael Jackson": ["1980s", "1990s", "2000s"],
    "Prince": ["1980s", "1990s"],
    "Hall and Oates": ["1980s"],
    "Taylor Swift": ["2010s", "2020s"],
    "Sabrina Carpenter": ["2020s"],
    "Chappell Roan": ["2020s"],
    "Adele": ["2010s", "2020s"],
    "Doja Cat": ["2020s"],
    "Britney Spears": ["2000s"],
    "Backstreet Boys": ["1990s", "2000s"],
    "Usher": ["1990s", "2000s", "2010s"],
    "Maxwell": ["1990s", "2000s"],
    "John Legend": ["2000s", "2010s"],
    "Drake": ["2010s", "2020s"],
    "Snoop Dogg": ["1990s", "2000s", "2010s"],
    "Pharrell": ["2000s", "2010s", "2020s"],
    "Marshmello": ["2010s", "2020s"],
    "Dr. Dre": ["1990s", "2000s"],
    "Ice Cube": ["1990s", "2000s"],
    "Eminem": ["2000s", "2010s"]
}

# Dummy track DB (replace this later with Last.fm search results)
TRACK_DB = [
    {"artist": "Michael Jackson", "track": "Billie Jean", "genre": "pop", "era": "1980s"},
    {"artist": "Prince", "track": "Kiss", "genre": "funk/pop", "era": "1980s"},
    {"artist": "Taylor Swift", "track": "Cruel Summer", "genre": "pop", "era": "2020s"},
    {"artist": "Sabrina Carpenter", "track": "Espresso", "genre": "pop", "era": "2020s"},
    {"artist": "Chappell Roan", "track": "Red Wine Supernova", "genre": "pop", "era": "2020s"},
    {"artist": "Adele", "track": "Hello", "genre": "soul/pop", "era": "2010s"},
    {"artist": "Doja Cat", "track": "Woman", "genre": "pop/rap", "era": "2020s"},
    {"artist": "Backstreet Boys", "track": "I Want It That Way", "genre": "pop", "era": "1990s"},
    {"artist": "Britney Spears", "track": "Toxic", "genre": "pop", "era": "2000s"},
    {"artist": "Hall and Oates", "track": "Maneater", "genre": "pop/rock", "era": "1980s"}
]

def infer_dominant_eras_from_artists(seed_artists: List[str]) -> Dict[str, float]:
    era_count = Counter()
    for artist in seed_artists:
        for era in ARTIST_ERA_MAP.get(artist, []):
            era_count[era] += 1
    if not era_count:
        return {}
    max_count = max(era_count.values())
    return {era: count / max_count for era, count in era_count.items() if count >= 1}

def get_recommendations(seed_artists: List[str], genre: str, birth_year: Optional[int] = None) -> List[Dict]:
    era_weights = infer_dominant_eras_from_artists(seed_artists)
    if not era_weights and birth_year:
        age = datetime.now().year - birth_year
        if age < 30:
            era_weights = {"2020s": 1.0, "2010s": 0.8}
        elif 30 <= age <= 45:
            era_weights = {"2000s": 1.0, "1990s": 0.8}
        else:
            era_weights = {"1980s": 1.0, "1990s": 0.6}
    total = sum(era_weights.values()) if era_weights else 1
    normalized_weights = {era: weight / total for era, weight in era_weights.items()}
    recommendations = []
    for track in TRACK_DB:
        genre_match = 1.0 if genre.lower() in track["genre"].lower() else 0.5
        era_weight = normalized_weights.get(track["era"], 0.1)
        artist_bonus = 1.2 if track["artist"] in seed_artists else 1.0
        score = genre_match * era_weight * artist_bonus
        recommendations.append({
            "artist": track["artist"],
            "track": track["track"],
            "score": round(score, 3)
        })
    return sorted(recommendations, key=lambda x: x["score"], reverse=True)[:10]
