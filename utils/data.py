"""
Chargement des données.

Toutes les fonctions qui vont chercher des données (API, fichiers)
sont regroupées ici. Elles sont décorées par @st.cache_data :
Streamlit garde le résultat en mémoire et ne relance pas le
téléchargement à chaque clic de l'utilisateur.
"""

import io
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

# Export CSV de l'API officielle (flux quotidien des prix).
# L'API permet de ne télécharger que les colonnes et le carburant voulus,
# au lieu du fichier complet d'environ 80 Mo.
DAILY_EXPORT_URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/"
    "datasets/prix-carburants-quotidien/exports/csv"
)

# Contours des départements (Etalab, précision 100 m).
# L'API geo.api.gouv.fr/departements ne fournit PAS de contours :
# elle ne renvoie qu'une liste {nom, code}, sans géométrie.
DEPARTMENTS_GEOJSON_URL = (
    "https://etalab-datasets.geo.data.gouv.fr/"
    "contours-administratifs/2025/geojson/departements-100m.geojson"
)

# API Découpage administratif : contours et centres des communes.
COMMUNES_API_URL = "https://geo.api.gouv.fr/communes"

# Fichier d'historique créé par scripts/prepare_historique.py
HISTORY_PATH = Path("data/historique_2026.parquet")

# Un prix déclaré il y a plus de 7 jours est considéré comme périmé :
# le flux garde le dernier prix connu, parfois vieux de plusieurs mois.
MAX_PRICE_AGE_DAYS = 7

# Les carburants ont des prix très différents : on n'en mélange jamais
# plusieurs dans un même calcul, l'utilisateur en choisit toujours un.
FUELS = ["Gazole", "SP95", "SP98", "E10", "E85", "GPLc"]

# Colonnes demandées à l'API (noms techniques du dataset).
DAILY_FIELDS = [
    "id",            # identifiant unique de la station
    "cp",            # code postal
    "adresse",
    "ville",         # nom de ville saisi par la station (orthographe variable)
    "geom",          # coordonnées GPS "latitude, longitude"
    "prix_maj",      # date de la dernière mise à jour du prix
    "prix_valeur",   # prix en €/L
    "prix_nom",      # nom du carburant
    "com_arm_code",  # code INSEE commune (ou arrondissement à Paris/Lyon/Marseille)
    "com_arm_name",  # nom officiel de la commune / de l'arrondissement
    "dep_code",      # code département, ex : "01", "2A"
    "dep_name",
    "reg_code",
    "reg_name",
]


# ============================================================
# DONNÉES QUOTIDIENNES
# ============================================================

@st.cache_data(ttl=6 * 60 * 60, show_spinner="Chargement des prix...")
def load_daily_data(fuel):
    """
    Télécharge les prix du jour pour UN carburant.

    Renvoie un DataFrame avec une ligne par station, et deux colonnes
    ajoutées : latitude et longitude.
    Le cache dure 6 heures (ttl) : les données ne changent qu'une fois par jour.
    """

    if fuel not in FUELS:
        raise ValueError(f"Carburant inconnu : {fuel}")

    # --------------------------------------------------------
    # Requête à l'API
    # --------------------------------------------------------

    params = {
        # "select" : seulement les colonnes utiles
        "select": ",".join(DAILY_FIELDS),
        # "where" : seulement le carburant choisi et les prix renseignés
        "where": f"prix_valeur IS NOT NULL AND prix_nom='{fuel}'",
        "use_labels": "false",   # noms techniques des colonnes
        "delimiter": ";",
    }

    response = requests.get(DAILY_EXPORT_URL, params=params, timeout=180)
    response.raise_for_status()   # erreur claire si l'API répond mal

    # dtype=str : on lit tout en texte pour ne pas perdre les zéros
    # au début des codes (ex : "01" deviendrait 1).
    df = pd.read_csv(io.BytesIO(response.content), sep=";", dtype=str)

    # Certains exports ajoutent un caractère invisible (BOM)
    # devant le premier nom de colonne.
    df.columns = df.columns.str.replace("﻿", "", regex=False)

    required_columns = {"id", "cp", "adresse", "ville", "prix_maj", "prix_valeur", "prix_nom"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans le dataset : {missing_columns}")

    # --------------------------------------------------------
    # Nettoyage des colonnes texte
    # --------------------------------------------------------

    text_columns = [
        "id", "cp", "adresse", "ville", "prix_nom",
        "com_arm_code", "com_arm_name", "dep_code", "dep_name",
        "reg_code", "reg_name",
    ]

    for column in text_columns:
        if column in df.columns:
            # Espaces en trop retirés, texte vide remplacé par une vraie valeur manquante
            df[column] = df[column].astype("string").str.strip().replace("", pd.NA)

    # Codes sur 5 caractères : "1000" -> "01000"
    df["cp"] = df["cp"].apply(lambda value: str(value).zfill(5) if pd.notna(value) else value)

    if "com_arm_code" in df.columns:
        df["com_arm_code"] = df["com_arm_code"].apply(
            lambda value: str(value).zfill(5) if pd.notna(value) else value
        )

    # --------------------------------------------------------
    # Conversion des types
    # --------------------------------------------------------

    # Prix : texte -> nombre (la virgule éventuelle devient un point)
    df["prix_valeur"] = pd.to_numeric(
        df["prix_valeur"].str.replace(",", ".", regex=False),
        errors="coerce",   # une valeur illisible devient NaN au lieu de planter
    )

    # Date : texte -> date (en UTC, comme dans le fichier)
    df["prix_maj"] = pd.to_datetime(df["prix_maj"], errors="coerce", utc=True)

    # --------------------------------------------------------
    # Coordonnées GPS
    # --------------------------------------------------------

    # geom vaut par exemple "46.201, 5.198" : latitude PUIS longitude.
    # (Vérifié sur les données : la 1re valeur va de 41 à 51 = latitudes françaises.)
    if "geom" in df.columns:
        coordinates = df["geom"].astype(str).str.extract(
            r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)"
        )
        df["latitude"] = pd.to_numeric(coordinates[0], errors="coerce")
        df["longitude"] = pd.to_numeric(coordinates[1], errors="coerce")
    else:
        df["latitude"] = pd.NA
        df["longitude"] = pd.NA

    # Sans identifiant ou sans prix, une ligne est inutilisable.
    df = df.dropna(subset=["id", "prix_valeur"])

    # --------------------------------------------------------
    # Suppression des prix périmés
    # --------------------------------------------------------

    # Référence = la mise à jour la plus récente du fichier
    # (et non l'heure actuelle) : on reste cohérent avec J-1.
    most_recent_update = df["prix_maj"].max()
    oldest_allowed_update = most_recent_update - pd.Timedelta(days=MAX_PRICE_AGE_DAYS)

    df = df[df["prix_maj"] >= oldest_allowed_update]

    # --------------------------------------------------------
    # Une ligne par station
    # --------------------------------------------------------

    # Une station apparaît sur plusieurs lignes identiques
    # (une par carburant "en rupture"). Comme la requête ne contient
    # qu'un seul carburant, dédoublonner sur "id" suffit.
    # On trie par date pour garder la ligne la plus récente.
    df = (
        df.sort_values("prix_maj", na_position="first")
        .drop_duplicates(subset=["id"], keep="last")
        .reset_index(drop=True)
    )

    # Si le nom officiel de commune manque, on prend le nom saisi par la station.
    if "com_arm_name" in df.columns:
        df["com_arm_name"] = df["com_arm_name"].fillna(df["ville"])

    return df


# ============================================================
# CONTOURS DES COMMUNES
# ============================================================

@st.cache_data(ttl=7 * 24 * 60 * 60, show_spinner=False)
def load_communes_geojson(department_code):
    """
    Récupère les contours des communes d'un département (GeoJSON).

    Deux appels sont nécessaires :
    - les communes classiques (ex : Beauvais = 60057) ;
    - les arrondissements de Paris, Lyon, Marseille (ex : Paris 8e = 75108),
      car le dataset carburant utilise ces codes dans com_arm_code.
    Les frontières ne changent pas : cache d'une semaine.
    """

    features = []

    for commune_type in ["commune-actuelle", "arrondissement-municipal"]:
        params = {
            "codeDepartement": department_code,
            "type": commune_type,
            "fields": "code,nom",
            "format": "geojson",
            "geometry": "contour",
        }

        response = requests.get(COMMUNES_API_URL, params=params, timeout=120)
        response.raise_for_status()

        # Un GeoJSON est une "FeatureCollection" : une liste de formes (features).
        features.extend(response.json().get("features", []))

    return {"type": "FeatureCollection", "features": features}


# ============================================================
# CONTOURS DES DÉPARTEMENTS
# ============================================================

@st.cache_data(ttl=7 * 24 * 60 * 60, show_spinner=False)
def load_departments_geojson():
    """
    Récupère les contours des départements français (GeoJSON Etalab).

    Chaque département a les propriétés {"code": "01", "nom": "Ain", ...}
    -> jointure avec dep_code grâce à featureidkey="properties.code".
    """

    response = requests.get(DEPARTMENTS_GEOJSON_URL, timeout=120)
    response.raise_for_status()

    geojson = response.json()

    # Sécurité : sans "features", Plotly afficherait une carte vide
    # sans aucun message d'erreur (c'était le bug de départ).
    if "features" not in geojson:
        raise ValueError("Le fichier des départements ne contient aucun contour.")

    return geojson


# ============================================================
# HISTORIQUE 2026
# ============================================================

@st.cache_data(show_spinner="Chargement de l'historique...")
def load_history(path, fuel):
    """
    Charge l'historique 2026 depuis le fichier Parquet.

    Le fichier contient tous les carburants (plus de 4 millions de lignes) ;
    le filtre Parquet ne lit que les lignes du carburant demandé.
    """

    history_path = Path(path)

    if not history_path.exists():
        raise FileNotFoundError(f"Fichier historique introuvable : {path}")

    df = pd.read_parquet(history_path, filters=[("prix_nom", "==", fuel)])

    df["id"] = df["id"].astype(str)
    df["prix_maj"] = pd.to_datetime(df["prix_maj"], errors="coerce")
    df["prix_valeur"] = pd.to_numeric(df["prix_valeur"], errors="coerce")

    return df.dropna(subset=["prix_maj", "prix_valeur"])
