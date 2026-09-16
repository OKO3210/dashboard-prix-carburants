"""
PAGE 3 — SIMULATEUR (niveau ACTION)

Question : où faire son plein au meilleur prix ?
L'utilisateur donne une ville ou un code postal, un carburant, une quantité
et un rayon. La page cherche toutes les stations dans ce rayon (à vol d'oiseau)
et recommande la moins chère.
"""

import requests
import streamlit as st

from utils.data import COMMUNES_API_URL, FUELS, MAX_PRICE_AGE_DAYS, load_daily_data
from utils.logic import haversine_distance, normalize_text, station_address
from utils.ui import show_data_sources


# ============================================================
# CONFIGURATION ET TITRE
# ============================================================

st.set_page_config(page_title="Simulateur de plein", layout="wide")

st.title("Où faire son plein au meilleur prix ?")
st.caption("Recherche la station la moins chère autour d'une ville ou d'un code postal.")


# ============================================================
# GÉOCODAGE : TROUVER LES COMMUNES CORRESPONDANTES
# ============================================================

@st.cache_data(ttl=7 * 24 * 60 * 60, show_spinner=False)
def find_communes(zone):
    """
    Renvoie la liste des communes correspondant à un code postal ou à un nom,
    avec leur centre GPS (API Découpage administratif).

    Il peut y en avoir plusieurs :
    - un code postal couvre parfois plusieurs communes ;
    - un nom comme "Saint-Denis" existe dans plusieurs départements.
    """

    zone = str(zone).strip()

    params = {"fields": "nom,code,codeDepartement,centre,population", "format": "json"}

    if zone.isdigit():
        params["codePostal"] = zone.zfill(5)
    else:
        params["nom"] = zone
        params["boost"] = "population"   # les communes les plus peuplées d'abord
        params["limit"] = 10

    response = requests.get(COMMUNES_API_URL, params=params, timeout=30)
    response.raise_for_status()

    communes = []

    for commune in response.json():
        coordinates = (commune.get("centre") or {}).get("coordinates")

        if not coordinates:
            continue

        communes.append({
            "name": commune.get("nom"),
            "code": commune.get("code"),
            "department": commune.get("codeDepartement"),
            "population": commune.get("population") or 0,
            # Attention : en GeoJSON l'ordre est [longitude, latitude]
            # (l'inverse de la colonne geom du dataset carburant).
            "longitude": coordinates[0],
            "latitude": coordinates[1],
        })

    # Recherche par nom : si des communes portent exactement ce nom,
    # on ne garde qu'elles (sinon on garde les résultats approchants).
    if not zone.isdigit():
        exact_matches = [c for c in communes if normalize_text(c["name"]) == normalize_text(zone)]
        if exact_matches:
            communes = exact_matches

    # La commune la plus peuplée en premier.
    communes.sort(key=lambda commune: commune["population"], reverse=True)

    return communes


# ============================================================
# FORMULAIRE
# ============================================================

# st.form : la page ne se recalcule qu'au clic sur le bouton,
# pas à chaque caractère tapé.
with st.form("simulator"):

    col1, col2, col3 = st.columns(3)

    with col1:
        zone = st.text_input("Ville ou code postal", placeholder="Ex : Beauvais ou 60000")

    with col2:
        fuel = st.selectbox("Carburant", FUELS, index=3)

    with col3:
        liters = st.number_input(
            "Quantité souhaitée (litres)",
            min_value=1.0, max_value=150.0, value=45.0, step=1.0, format="%.0f",
        )

    radius = st.slider("Rayon de recherche", min_value=5, max_value=30, value=10, step=5, format="%d km")

    submitted = st.form_submit_button("Trouver la station la moins chère", type="primary")


# ============================================================
# MÉMORISATION DE LA RECHERCHE
# ============================================================

# Le bouton ne vaut True que pendant UN rechargement.
# On mémorise donc la recherche, sinon choisir une commune dans la liste
# ci-dessous (qui relance la page) ferait disparaître les résultats.
if submitted:
    st.session_state.search = {"zone": zone, "fuel": fuel, "liters": liters, "radius": radius}

if "search" not in st.session_state:
    show_data_sources(["quotidien", "geo"])
    st.stop()   # rien n'a encore été recherché

search = st.session_state.search
zone, fuel, liters, radius = search["zone"], search["fuel"], search["liters"], search["radius"]

if not zone.strip():
    st.warning("Indique une ville ou un code postal.")
    st.stop()


# ============================================================
# GÉOCODAGE
# ============================================================

with st.spinner("Recherche de la zone..."):
    communes = find_communes(zone)

if not communes:
    st.error("Impossible d'identifier cette ville ou ce code postal.")
    st.stop()

if len(communes) > 1:
    # Plusieurs communes possibles : l'utilisateur choisit.
    # La liste contient les positions 0, 1, 2... et affiche "Nom (département)".
    selected_index = st.selectbox(
        "Plusieurs communes correspondent, laquelle ?",
        range(len(communes)),
        format_func=lambda index: f"{communes[index]['name']} ({communes[index]['department']})",
    )
    location = communes[selected_index]
else:
    location = communes[0]


# ============================================================
# DISTANCE DE CHAQUE STATION
# ============================================================

df = load_daily_data(fuel)

# Une distance n'est calculable qu'avec des coordonnées GPS.
stations = df.dropna(subset=["latitude", "longitude", "prix_valeur"]).copy()

if stations.empty:
    st.warning(f"Aucune station avec coordonnées GPS pour le {fuel}.")
    st.stop()

# apply(..., axis=1) : la fonction est appliquée à chaque ligne (chaque station).
stations["distance_km"] = stations.apply(
    lambda row: haversine_distance(
        location["latitude"], location["longitude"], row["latitude"], row["longitude"]
    ),
    axis=1,
)

nearby = stations[stations["distance_km"] <= radius].copy()


# ============================================================
# CAS : AUCUNE STATION DANS LE RAYON
# ============================================================

if nearby.empty:
    closest = stations.sort_values("distance_km").iloc[0]

    st.warning(
        f"Aucune station proposant du {fuel} dans un rayon de {radius} km "
        f"autour de {location['name']}."
    )
    st.info(f"La station disponible la plus proche est située à environ {closest['distance_km']:.1f} km.")
    st.stop()


# ============================================================
# MEILLEURE STATION
# ============================================================

# Tri : la moins chère d'abord, puis la plus proche en cas d'égalité.
nearby = nearby.sort_values(["prix_valeur", "distance_km"])

best_station = nearby.iloc[0]
best_price = best_station["prix_valeur"]
best_distance = best_station["distance_km"]
best_cost = best_price * liters

# Économie = plein au prix moyen du rayon - plein dans la meilleure station
average_price = nearby["prix_valeur"].mean()
saving = average_price * liters - best_cost

station_count = nearby["id"].nunique()


# ============================================================
# RÉSULTAT
# ============================================================

st.divider()

st.subheader(f"Meilleure option autour de {location['name']}")
st.caption(f"{station_count} station{'s' if station_count > 1 else ''} proposant du {fuel} dans un rayon de {radius} km.")
st.write(f"**{station_address(best_station)}**")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Prix", f"{best_price:.3f} €/L", border=True)
    st.caption(f"À {best_distance:.1f} km à vol d'oiseau")

with col2:
    st.metric(f"Coût pour {liters:.0f} L", f"{best_cost:.2f} €", border=True)

with col3:
    st.metric("Économie estimée", f"{saving:.2f} €", border=True)
    st.caption(f"Par rapport au prix moyen du rayon : {average_price:.3f} €/L")


# ============================================================
# TOP 5
# ============================================================

st.subheader("Les 5 stations les moins chères")

ranking = nearby.head(5).copy()

ranking["Rang"] = range(1, len(ranking) + 1)
ranking["Station"] = ranking.apply(station_address, axis=1)
ranking["Distance"] = ranking["distance_km"]
ranking["Prix"] = ranking["prix_valeur"]
ranking["Coût du plein"] = ranking["prix_valeur"] * liters
# Ce que coûte le plein EN PLUS par rapport à la station n°1 (0.00 € = même prix).
ranking["Surcoût vs n°1"] = ranking["Coût du plein"] - best_cost

st.dataframe(
    ranking[["Rang", "Station", "Distance", "Prix", "Coût du plein", "Surcoût vs n°1"]],
    hide_index=True,
    width="stretch",
    # column_config : format d'affichage de chaque colonne (les données restent des nombres)
    column_config={
        "Rang": st.column_config.NumberColumn("Rang", format="%d", width="small"),
        "Distance": st.column_config.NumberColumn("Distance", format="%.1f km"),
        "Prix": st.column_config.NumberColumn("Prix", format="%.3f €/L"),
        "Coût du plein": st.column_config.NumberColumn("Coût du plein", format="%.2f €"),
        "Surcoût vs n°1": st.column_config.NumberColumn("Surcoût vs n°1", format="+%.2f €"),
    },
)

st.caption(
    "Des stations voisines affichent souvent exactement le même prix : "
    "à prix égal, la plus proche est classée devant. "
    "Les distances sont calculées à vol d'oiseau entre le centre de la commune recherchée "
    f"et chaque station. Seuls les prix mis à jour depuis moins de {MAX_PRICE_AGE_DAYS} jours sont utilisés."
)


# ============================================================
# SOURCES
# ============================================================

show_data_sources(["quotidien", "geo"])
