"""
PAGE 1 — VUE GLOBALE (niveau MACRO)

Question : où le carburant est-il le moins cher ?
- France entière : carte des départements.
- Un département : carte des communes, avec les stations.
Un clic sur la carte fait descendre d'un niveau et recalcule les KPIs.

Lancement : streamlit run app.py
"""

import streamlit as st

from utils.charts import create_commune_map, create_department_map
from utils.data import (
    FUELS,
    MAX_PRICE_AGE_DAYS,
    load_communes_geojson,
    load_daily_data,
    load_departments_geojson,
)
from utils.logic import calculate_kpis, station_address
from utils.ui import display_price_scale, get_clicked_code, get_map_style, show_data_sources


# ============================================================
# CONFIGURATION
# ============================================================

# Doit être le premier appel Streamlit de la page.
st.set_page_config(page_title="Prix des carburants", layout="wide")

# Réglages de la barre du haut des cartes Plotly.
MAP_CONFIG = {"displayModeBar": False, "scrollZoom": True}


# ============================================================
# SESSION STATE
# ============================================================

# st.session_state garde des valeurs d'un rechargement à l'autre
# (Streamlit relance tout le script à chaque interaction).
if "selected_commune" not in st.session_state:
    st.session_state.selected_commune = None   # code de la commune cliquée

if "map_scope" not in st.session_state:
    st.session_state.map_scope = None          # (carburant, département) affiché

if "map_version" not in st.session_state:
    # Numéro ajouté à la clé des cartes : l'augmenter recrée une carte
    # "neuve", donc efface l'ancien clic.
    st.session_state.map_version = 0


# ============================================================
# TITRE
# ============================================================

st.title("Où le carburant est-il le moins cher ?")

st.caption(
    "Prix issus du flux quotidien officiel des carburants en France — données J-1. "
    f"Seuls les prix mis à jour depuis moins de {MAX_PRICE_AGE_DAYS} jours sont pris en compte."
)


# ============================================================
# FILTRE 1 : CARBURANT
# ============================================================

st.sidebar.header("Filtres")

# index=3 : E10 sélectionné par défaut
fuel = st.sidebar.selectbox("Carburant", FUELS, index=3)


# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================

try:
    df = load_daily_data(fuel)
except Exception as error:
    st.error("Impossible de charger les données.")
    st.exception(error)
    st.stop()   # arrête la page ici

if df.empty:
    st.warning("Aucune donnée disponible pour ce carburant.")
    st.stop()


# ============================================================
# FILTRE 2 : DÉPARTEMENT
# ============================================================

departments = (
    df[["dep_code", "dep_name"]]
    .dropna()
    .drop_duplicates()
    .sort_values(["dep_code", "dep_name"])
)

department_labels = ["France entière"]
department_lookup = {}           # "60 — Oise" -> ("60", "Oise")
label_by_department_code = {}    # "60" -> "60 — Oise" (sert au clic sur la carte)

for _, row in departments.iterrows():
    code = str(row["dep_code"])
    name = str(row["dep_name"])
    label = f"{code} — {name}"

    department_labels.append(label)
    department_lookup[label] = (code, name)
    label_by_department_code[code] = label

# Un clic sur la carte de France a demandé un département :
# on l'applique AVANT de créer la liste déroulante
# (Streamlit interdit de modifier un widget déjà affiché).
if "pending_department" in st.session_state:
    st.session_state.department_label = st.session_state.pop("pending_department")

# Si le département mémorisé n'existe plus (ex : changement de carburant),
# retour à la France entière.
if st.session_state.get("department_label") not in department_labels:
    st.session_state.department_label = "France entière"

selected_department_label = st.sidebar.selectbox(
    "Département",
    department_labels,
    key="department_label",   # la valeur est stockée dans st.session_state.department_label
)

if selected_department_label == "France entière":
    department_code, department_name = None, None
else:
    department_code, department_name = department_lookup[selected_department_label]


# ============================================================
# RÉINITIALISATION SI LES FILTRES CHANGENT
# ============================================================

# Changer de carburant ou de département efface la commune sélectionnée.
scope_key = (fuel, department_code)

if st.session_state.map_scope != scope_key:
    st.session_state.selected_commune = None
    st.session_state.map_scope = scope_key
    st.session_state.map_version += 1


# ============================================================
# PÉRIMÈTRE DES KPIs : FRANCE, DÉPARTEMENT OU COMMUNE
# ============================================================

if department_code is None:
    base_df = df
else:
    base_df = df[df["dep_code"].astype(str) == department_code]

selected_commune_code = st.session_state.selected_commune

if selected_commune_code:
    commune_df = base_df[base_df["com_arm_code"].astype(str) == str(selected_commune_code)]

    # La commune n'existe pas dans ce département : on l'oublie.
    if commune_df.empty:
        st.session_state.selected_commune = None
        selected_commune_code = None

if selected_commune_code:
    scope_df = commune_df
    scope_name = commune_df["com_arm_name"].dropna().iloc[0]
elif department_code:
    scope_df = base_df
    scope_name = department_name
else:
    scope_df = df
    scope_name = "France entière"

is_national_view = scope_name == "France entière"


# ============================================================
# EN-TÊTE DU PÉRIMÈTRE
# ============================================================

st.subheader(f"{fuel} — {scope_name}")

station_count = scope_df["id"].nunique()
# Séparateur de milliers : 6 372 plutôt que 6,372
station_count_text = f"{station_count:,}".replace(",", " ")

st.caption(f"{station_count_text} station{'s' if station_count > 1 else ''} prises en compte.")


# ============================================================
# KPIs
# ============================================================

kpis = calculate_kpis(scope_df)

# Moyenne nationale : sert de point de comparaison pour un département / une commune.
national_average = df["prix_valeur"].mean()

if kpis is None:
    st.warning("Impossible de calculer les indicateurs.")

else:
    col1, col2, col3 = st.columns(3)

    # --- KPI 1 : prix moyen -------------------------------------------------
    with col1:
        if is_national_view:
            st.metric("Prix moyen", f"{kpis['mean_price']:.3f} €/L", border=True)
            st.caption("Moyenne des stations disponibles pour ce carburant.")
        else:
            difference_percent = (kpis["mean_price"] - national_average) / national_average * 100

            st.metric(
                "Prix moyen",
                f"{kpis['mean_price']:.3f} €/L",
                delta=f"{difference_percent:+.1f} % vs France",
                # inverse : une hausse de prix est une MAUVAISE nouvelle -> en rouge
                delta_color="inverse",
                border=True,
            )
            st.caption(f"Moyenne France : {national_average:.3f} €/L")

    # --- KPI 2 : station la moins chère -------------------------------------
    with col2:
        st.metric("Station la moins chère", f"{kpis['min_price']:.3f} €/L", border=True)
        st.caption(station_address(kpis["min_station"]))

    # --- KPI 3 : station la plus chère --------------------------------------
    with col3:
        st.metric("Station la plus chère", f"{kpis['max_price']:.3f} €/L", border=True)
        st.caption(station_address(kpis["max_station"]))

    # --- Barre minimum -> moyenne -> maximum --------------------------------
    st.markdown("#### Positionnement des prix")

    # En vue France, le marqueur "France" serait confondu avec la moyenne : on ne l'affiche pas.
    display_price_scale(
        min_price=kpis["min_price"],
        mean_price=kpis["mean_price"],
        max_price=kpis["max_price"],
        national_average=None if is_national_view else national_average,
    )


st.divider()

map_style = get_map_style()


# ============================================================
# CARTE : FRANCE ENTIÈRE -> DÉPARTEMENTS
# ============================================================

if department_code is None:

    st.subheader("Prix moyen par département")
    st.caption(
        f"Plus un département est foncé, plus le prix moyen du {fuel} y est élevé. "
        "Clique sur un département pour afficher le détail par commune."
    )

    try:
        figure = create_department_map(df, load_departments_geojson(), map_style=map_style)

        # on_select="rerun" : un clic relance la page et renvoie la sélection.
        department_event = st.plotly_chart(
            figure,
            width="stretch",
            key=f"department_map_{fuel}_{st.session_state.map_version}",
            on_select="rerun",
            selection_mode="points",
            config=MAP_CONFIG,
        )

    except Exception as error:
        st.error("Impossible d'afficher la carte nationale.")
        st.exception(error)
        department_event = None

    clicked_department = get_clicked_code(department_event)

    if clicked_department in label_by_department_code:
        # Appliqué au prochain rechargement, avant la création de la liste déroulante.
        st.session_state.pending_department = label_by_department_code[clicked_department]
        st.rerun()


# ============================================================
# CARTE : UN DÉPARTEMENT -> COMMUNES
# ============================================================

else:

    st.subheader(f"Prix moyen par commune — {department_name}")
    st.caption(
        "Plus une commune est foncée, plus le prix moyen y est élevé. "
        "Les points sont les stations. "
        "Clique sur une commune ou une station pour mettre à jour les indicateurs."
    )

    # Bandeau "commune sélectionnée" + bouton de retour
    if st.session_state.selected_commune:
        col_info, col_button = st.columns([4, 1])

        with col_info:
            st.info(f"Commune sélectionnée : **{scope_name}**")

        with col_button:
            if st.button("Revenir au département", width="stretch"):
                st.session_state.selected_commune = None
                st.session_state.map_version += 1   # efface le clic sur la carte
                st.rerun()

    try:
        figure = create_commune_map(
            base_df,
            load_communes_geojson(department_code),
            selected_commune_code=st.session_state.selected_commune,
            map_style=map_style,
        )

        commune_event = st.plotly_chart(
            figure,
            width="stretch",
            key=f"commune_map_{fuel}_{department_code}_{st.session_state.map_version}",
            on_select="rerun",
            selection_mode="points",
            config=MAP_CONFIG,
        )

    except Exception as error:
        st.error("Impossible d'afficher la carte des communes.")
        st.exception(error)
        commune_event = None

    commune_code = get_clicked_code(commune_event)

    # Mise à jour seulement si la commune cliquée est différente.
    if commune_code and commune_code != str(st.session_state.selected_commune):
        st.session_state.selected_commune = commune_code
        st.rerun()


# ============================================================
# SOURCES
# ============================================================

show_data_sources(["quotidien", "contours", "geo"])
