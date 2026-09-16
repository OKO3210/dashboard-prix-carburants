"""
PAGE 2 — ANALYSE D'UNE STATION (niveau MICRO)

Question : comment le prix d'une station évolue-t-il ?
Sélection en cascade : carburant -> département -> commune -> station,
puis analyse temporelle sur l'historique 2026.
"""

import pandas as pd
import streamlit as st

from utils.charts import create_station_history_chart
from utils.data import FUELS, HISTORY_PATH, load_daily_data, load_history
from utils.logic import station_address
from utils.ui import show_data_sources


# ============================================================
# CONFIGURATION ET TITRE
# ============================================================

st.set_page_config(page_title="Analyse d'une station", layout="wide")

st.title("Comment le prix d'une station évolue-t-il ?")
st.caption("Analyse temporelle des prix déclarés par une station.")


# ============================================================
# SÉLECTION EN CASCADE (SIDEBAR)
# ============================================================

# Chaque liste dépend du choix précédent :
# on ne propose que les communes du département choisi, etc.

st.sidebar.header("Sélection")

# --- Carburant ------------------------------------------------------------
fuel = st.sidebar.selectbox("Carburant", FUELS, index=3)

# Les données du jour servent à construire les listes de choix.
df = load_daily_data(fuel)

# --- Département ----------------------------------------------------------
departments = df[["dep_code", "dep_name"]].dropna().drop_duplicates().sort_values("dep_code")

# "60 — Oise" -> "60"
department_lookup = {
    f"{row['dep_code']} — {row['dep_name']}": row["dep_code"]
    for _, row in departments.iterrows()
}

department_label = st.sidebar.selectbox("Département", list(department_lookup.keys()))
department_df = df[df["dep_code"] == department_lookup[department_label]]

# --- Commune --------------------------------------------------------------
communes = (
    department_df[["com_arm_code", "com_arm_name"]]
    .dropna()
    .drop_duplicates()
    .sort_values("com_arm_name")
)

# "Beauvais" -> "60057"
commune_lookup = {str(row["com_arm_name"]): row["com_arm_code"] for _, row in communes.iterrows()}

commune_name = st.sidebar.selectbox("Commune", list(commune_lookup.keys()))
commune_df = department_df[department_df["com_arm_code"] == commune_lookup[commune_name]]

# --- Station --------------------------------------------------------------
# Sans marque dans le dataset, une station est identifiée par
# son ID + son adresse + son code postal + sa ville.
station_lookup = {
    str(row["id"]): f"{row['id']} — {station_address(row)}"
    for _, row in commune_df.iterrows()
}

station_id = st.sidebar.selectbox(
    "Station",
    list(station_lookup.keys()),
    # La liste contient les ID, mais affiche le texte complet.
    format_func=lambda value: station_lookup[value],
)

station_row = commune_df[commune_df["id"].astype(str) == station_id].iloc[0]

st.subheader(station_address(station_row))


# ============================================================
# HISTORIQUE DE LA STATION
# ============================================================

if not HISTORY_PATH.exists():
    st.warning("Le fichier historique 2026 n'existe pas encore. Lance d'abord :")
    st.code("python scripts/prepare_historique.py")
    st.stop()

history = load_history(str(HISTORY_PATH), fuel)

station_history = (
    history[history["id"] == station_id]
    .sort_values("prix_maj")
    # Deux déclarations à la même minute : on garde la dernière.
    .drop_duplicates(subset=["prix_maj"], keep="last")
)

if station_history.empty:
    st.warning("Aucune donnée historique disponible pour cette station et ce carburant.")
    st.stop()


# ============================================================
# FILTRE : PÉRIODE
# ============================================================

min_date = station_history["prix_maj"].min().date()
max_date = station_history["prix_maj"].max().date()

selected_dates = st.sidebar.date_input(
    "Période analysée",
    value=(min_date, max_date),   # un tuple = sélection d'une plage de dates
    min_value=min_date,
    max_value=max_date,
)

filtered_history = station_history

# Pendant la sélection, Streamlit renvoie une seule date :
# on attend que la plage soit complète (2 dates) pour filtrer.
if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    dates = station_history["prix_maj"].dt.date
    filtered_history = station_history[(dates >= start_date) & (dates <= end_date)]

if filtered_history.empty:
    st.warning("Aucune donnée sur cette période.")
    st.stop()


# ============================================================
# CALCUL DES KPIs
# ============================================================

# --- KPI 1 : prix actuel et tendance vs environ 1 mois avant ---------------

latest_row = filtered_history.iloc[-1]      # dernière déclaration de la période
current_price = latest_row["prix_valeur"]
current_date = latest_row["prix_maj"]

# Si la période s'arrête avant le dernier jour connu,
# le dernier prix de la période n'est plus le prix "actuel".
current_label = "Prix en fin de période" if current_date.date() < max_date else "Prix actuel"

# On compare au DERNIER prix connu à une date <= (date actuelle - 1 mois).
# On cherche dans tout l'historique, pas seulement la période :
# sinon, sur une période courte, il n'y aurait jamais de point de comparaison.
one_month_before = current_date - pd.DateOffset(months=1)
previous_candidates = station_history[station_history["prix_maj"] <= one_month_before]

previous_price = None
monthly_change_percent = None

if not previous_candidates.empty:
    previous_price = previous_candidates.iloc[-1]["prix_valeur"]

    if previous_price != 0:
        monthly_change_percent = (current_price - previous_price) / previous_price * 100

# --- KPI 2 : moyenne de la période -----------------------------------------

period_average = filtered_history["prix_valeur"].mean()
current_vs_average_percent = (current_price - period_average) / period_average * 100

# --- KPI 3 : amplitude (écart entre le plus haut et le plus bas) -----------

minimum_price = filtered_history["prix_valeur"].min()
maximum_price = filtered_history["prix_valeur"].max()
amplitude = maximum_price - minimum_price


# ============================================================
# AFFICHAGE DES KPIs
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:
    if monthly_change_percent is None:
        st.metric(current_label, f"{current_price:.3f} €/L", border=True)
        st.caption("Pas assez d'historique pour comparer à M-1.")
    else:
        st.metric(
            current_label,
            f"{current_price:.3f} €/L",
            delta=f"{monthly_change_percent:+.1f} % vs M-1",
            delta_color="inverse",   # une hausse de prix s'affiche en rouge
            border=True,
        )
        st.caption(f"Il y a environ un mois : {previous_price:.3f} €/L")

with col2:
    st.metric(
        "Moyenne sur la période",
        f"{period_average:.3f} €/L",
        delta=f"{current_vs_average_percent:+.1f} % pour le prix actuel",
        delta_color="inverse",
        border=True,
    )
    st.caption("Moyenne des prix déclarés sur la période sélectionnée.")

with col3:
    st.metric("Amplitude sur la période", f"{amplitude:.3f} €/L", border=True)
    st.caption(f"Min : {minimum_price:.3f} €/L · Max : {maximum_price:.3f} €/L")


st.divider()


# ============================================================
# GRAPHIQUE
# ============================================================

st.subheader(f"Évolution du prix du {fuel}")
st.caption(
    "Courbe en escalier : un prix reste identique jusqu'à la déclaration suivante. "
    "La ligne pointillée est la moyenne de la période."
)

figure = create_station_history_chart(filtered_history, current_date, current_price, period_average)

st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


# ============================================================
# SOURCES
# ============================================================

show_data_sources(["quotidien", "historique"])
