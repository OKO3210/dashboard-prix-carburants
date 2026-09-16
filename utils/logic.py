"""
Calculs et petites fonctions utilitaires.

Aucun affichage ici : ces fonctions prennent des données
et renvoient un résultat, ce qui les rend faciles à tester et à expliquer.
"""

import math
import unicodedata

import pandas as pd


# ============================================================
# ADRESSE D'UNE STATION
# ============================================================

def station_address(row):
    """
    Transforme une ligne du dataset en adresse lisible.

    Le dataset ne donne pas la marque des stations :
    l'adresse est donc la meilleure façon de les identifier.

    Exemple : "596 AVENUE DE TREVOUX — 01000 — SAINT-DENIS-LÈS-BOURG"
    """

    values = [row.get("adresse", ""), row.get("cp", ""), row.get("ville", "")]

    # On ignore les morceaux vides ou manquants.
    parts = [str(value) for value in values if pd.notna(value) and str(value).strip()]

    return " — ".join(parts)


# ============================================================
# KPIs DE LA PAGE 1
# ============================================================

def calculate_kpis(df):
    """
    Calcule les 3 indicateurs de la page 1 sur un groupe de stations :
    prix moyen, station la moins chère, station la plus chère.

    Renvoie None s'il n'y a aucune donnée exploitable.
    """

    if df.empty or df["prix_valeur"].dropna().empty:
        return None

    # idxmin / idxmax donnent l'index (le numéro de ligne) du prix min / max,
    # ce qui permet de récupérer TOUTE la ligne, donc l'adresse de la station.
    min_station = df.loc[df["prix_valeur"].idxmin()]
    max_station = df.loc[df["prix_valeur"].idxmax()]

    return {
        "mean_price": df["prix_valeur"].mean(),
        "min_price": min_station["prix_valeur"],
        "max_price": max_station["prix_valeur"],
        "min_station": min_station,
        "max_station": max_station,
    }


# ============================================================
# NORMALISATION D'UN TEXTE
# ============================================================

def normalize_text(value):
    """
    Met un texte sous une forme comparable :
    majuscules, sans accents, sans espaces en trop.

    Exemple : "Saint-Denis-lès-Bourg" -> "SAINT-DENIS-LES-BOURG"

    Utilisé par le simulateur pour reconnaître le nom exact d'une commune,
    quelle que soit la façon dont l'utilisateur l'a tapé.
    """

    if value is None:
        return ""

    # NFKD sépare chaque lettre de son accent ("è" -> "e" + "`")...
    value = unicodedata.normalize("NFKD", str(value))

    # ... puis on supprime les accents.
    value = "".join(character for character in value if not unicodedata.combining(character))

    # split() puis join() remplace les espaces multiples par un seul.
    return " ".join(value.upper().split())


# ============================================================
# DISTANCE À VOL D'OISEAU (HAVERSINE)
# ============================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Distance en kilomètres entre deux points GPS, à vol d'oiseau.

    La Terre est ronde : on ne peut pas utiliser Pythagore directement
    sur des latitudes et longitudes. La formule de Haversine calcule
    la longueur de l'arc de cercle entre les deux points.

    Renvoie None si une coordonnée manque.
    """

    if any(pd.isna(value) for value in [lat1, lon1, lat2, lon2]):
        return None

    earth_radius_km = 6371.0088   # rayon moyen de la Terre

    # Les fonctions trigonométriques travaillent en radians, pas en degrés.
    lat1, lon1, lat2, lon2 = (math.radians(float(value)) for value in [lat1, lon1, lat2, lon2])

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )

    # c = angle entre les deux points, vu depuis le centre de la Terre
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_km * c
