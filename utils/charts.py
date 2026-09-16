"""
Création des graphiques Plotly.

Chaque fonction reçoit des données déjà chargées et renvoie une figure :
l'affichage (st.plotly_chart) reste dans les pages.
"""

import plotly.express as px
import plotly.graph_objects as go

from utils.logic import station_address


# ============================================================
# RÉGLAGES VISUELS COMMUNS
# ============================================================

# Échelle de couleurs des cartes : jaune (pas cher) -> rouge (cher).
# Une seule teinte qui s'intensifie se lit plus facilement qu'un arc-en-ciel.
COLOR_SCALE = "YlOrRd"

# Couleurs du graphique de la page 2 (reprises des KPIs et de la barre de prix).
LINE_COLOR = "#2563eb"      # bleu : évolution du prix
MIN_COLOR = "#16a34a"       # vert : minimum
MAX_COLOR = "#dc2626"       # rouge : maximum
CURRENT_COLOR = "#f59e0b"   # orange : prix actuel
AVERAGE_COLOR = "#6b7280"   # gris : moyenne de la période

# Stations sur la carte des communes.
STATION_COLOR = "#1f2937"
SELECTED_STATION_COLOR = "#2563eb"


def add_price_labels(stats):
    """
    Ajoute des colonnes texte "2.155 €/L" pour les infobulles.
    Plotly affiche alors directement le texte, unité comprise.
    """

    for column in ["prix_moyen", "prix_min", "prix_max"]:
        stats[f"{column}_label"] = stats[column].map(lambda value: f"{value:.3f} €/L")

    return stats


def aggregate_prices(df, group_columns):
    """
    Regroupe les stations par zone (département ou commune)
    et calcule prix moyen, min, max et nombre de stations.
    """

    return (
        df.dropna(subset=group_columns + ["prix_valeur"])
        .groupby(group_columns, as_index=False)
        .agg(
            prix_moyen=("prix_valeur", "mean"),
            prix_min=("prix_valeur", "min"),
            prix_max=("prix_valeur", "max"),
            nb_stations=("id", "nunique"),
        )
    )


# Infobulle commune aux deux cartes.
# customdata[0] est réservé au code de la zone (utilisé pour le clic),
# les valeurs affichées commencent donc à customdata[1].
ZONE_HOVER_TEMPLATE = (
    "<b>%{hovertext}</b><br><br>"
    "Prix moyen : %{customdata[1]}<br>"
    "Prix minimum : %{customdata[2]}<br>"
    "Prix maximum : %{customdata[3]}<br>"
    "Stations : %{customdata[4]}"
    "<extra></extra>"   # supprime le petit encadré avec le nom de la trace
)


def style_map(fig):
    """
    Mise en page commune aux deux cartes :
    pas de marges, pas de jauge de couleur, clic activé.
    """

    fig.update_traces(
        hovertemplate=ZONE_HOVER_TEMPLATE,
        marker_line_width=0.6,                          # fin contour entre les zones
        marker_line_color="rgba(255, 255, 255, 0.7)",
        selector={"type": "choroplethmap"},             # seulement les zones, pas les points
    )

    fig.update_layout(
        height=650,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_showscale=False,      # la couleur suffit, pas de jauge verticale
        clickmode="event+select",       # un clic sélectionne la zone
        hoverlabel={"font_size": 13},
    )

    return fig


# ============================================================
# CARTE DES DÉPARTEMENTS
# ============================================================

def create_department_map(df, geojson, map_style="carto-positron"):
    """
    Carte de France : chaque département est coloré selon le prix moyen.
    """

    department_stats = add_price_labels(aggregate_prices(df, ["dep_code", "dep_name"]))

    fig = px.choropleth_map(
        department_stats,
        geojson=geojson,
        # Jointure : la colonne dep_code ("01", "2A"...) est comparée
        # à la propriété "code" de chaque forme du GeoJSON.
        locations="dep_code",
        featureidkey="properties.code",
        color="prix_moyen",
        hover_name="dep_name",
        custom_data=["dep_code", "prix_moyen_label", "prix_min_label", "prix_max_label", "nb_stations"],
        color_continuous_scale=COLOR_SCALE,
        map_style=map_style,
        center={"lat": 46.6, "lon": 2.4},   # centre de la France métropolitaine
        zoom=4.4,
        opacity=0.8,
    )

    return style_map(fig)


# ============================================================
# CARTE DES COMMUNES
# ============================================================

def create_commune_map(df, geojson, selected_commune_code=None, map_style="carto-positron"):
    """
    Carte d'un département : chaque commune est colorée selon le prix moyen,
    et chaque station est un point par-dessus.

    Les stations de la commune sélectionnée sont en bleu et plus grosses.
    """

    commune_stats = add_price_labels(aggregate_prices(df, ["com_arm_code", "com_arm_name"]))

    # --------------------------------------------------------
    # Centre de la carte = position moyenne des stations
    # --------------------------------------------------------

    stations = df.dropna(subset=["latitude", "longitude", "prix_valeur"]).copy()

    if stations.empty:
        center = {"lat": 46.6, "lon": 2.4}
    else:
        center = {"lat": stations["latitude"].mean(), "lon": stations["longitude"].mean()}

    # --------------------------------------------------------
    # Zones colorées
    # --------------------------------------------------------

    fig = px.choropleth_map(
        commune_stats,
        geojson=geojson,
        locations="com_arm_code",
        featureidkey="properties.code",
        color="prix_moyen",
        hover_name="com_arm_name",
        custom_data=["com_arm_code", "prix_moyen_label", "prix_min_label", "prix_max_label", "nb_stations"],
        color_continuous_scale=COLOR_SCALE,
        map_style=map_style,
        center=center,
        zoom=7.5,
        opacity=0.8,
    )

    # --------------------------------------------------------
    # Points : une station = un point
    # --------------------------------------------------------

    stations["adresse_label"] = stations.apply(station_address, axis=1)
    stations["prix_label"] = stations["prix_valeur"].map(lambda value: f"{value:.3f} €/L")

    is_selected = stations["com_arm_code"].astype(str) == str(selected_commune_code)

    fig.add_trace(
        go.Scattermap(
            lat=stations["latitude"],
            lon=stations["longitude"],
            mode="markers",
            name="Stations",
            marker={
                "size": is_selected.map({True: 12, False: 7}),
                "color": is_selected.map({True: SELECTED_STATION_COLOR, False: STATION_COLOR}),
            },
            # com_arm_code en premier : cliquer sur une station sélectionne sa commune.
            customdata=stations[["com_arm_code", "adresse_label", "prix_label"]],
            hovertemplate="<b>%{customdata[1]}</b><br>Prix : %{customdata[2]}<extra></extra>",
            showlegend=False,
        )
    )

    return style_map(fig)


# ============================================================
# ÉVOLUTION DU PRIX D'UNE STATION (PAGE 2)
# ============================================================

def create_station_history_chart(history, current_date, current_price, period_average):
    """
    Courbe en escalier du prix d'une station sur la période,
    avec le minimum, le maximum, le prix actuel et la moyenne.

    Les repères reprennent exactement les 3 KPIs de la page :
    le graphique et les chiffres racontent la même histoire.
    """

    fig = go.Figure()

    # --------------------------------------------------------
    # Courbe principale en escalier
    # --------------------------------------------------------

    # line_shape="hv" : horizontal puis vertical.
    # Un prix reste identique jusqu'à la déclaration suivante,
    # puis change d'un coup : il ne "glisse" pas de 1.80 à 1.90.
    fig.add_trace(
        go.Scatter(
            x=history["prix_maj"],
            y=history["prix_valeur"],
            mode="lines",
            name="Prix déclaré",
            line={"shape": "hv", "color": LINE_COLOR, "width": 2},
            hovertemplate="%{x|%d/%m/%Y %H:%M}<br>%{y:.3f} €/L<extra></extra>",
        )
    )

    # --------------------------------------------------------
    # Moyenne de la période (KPI 2) : ligne pointillée
    # --------------------------------------------------------

    fig.add_hline(
        y=period_average,
        line_dash="dot",
        line_color=AVERAGE_COLOR,
        annotation_text=f"Moyenne {period_average:.3f} €/L",
        annotation_position="top left",
        annotation_font_color=AVERAGE_COLOR,
    )

    # --------------------------------------------------------
    # Repères : minimum, maximum, prix actuel
    # --------------------------------------------------------

    min_row = history.loc[history["prix_valeur"].idxmin()]
    max_row = history.loc[history["prix_valeur"].idxmax()]

    markers = [
        # (nom, date, prix, couleur, symbole, afficher le texte ?)
        ("Minimum", min_row["prix_maj"], min_row["prix_valeur"], MIN_COLOR, "circle", True),
        ("Maximum", max_row["prix_maj"], max_row["prix_valeur"], MAX_COLOR, "circle", True),
        # Pas de texte pour le prix actuel : il est souvent aussi le min ou le max,
        # et les deux textes se superposeraient. La légende et le KPI suffisent.
        ("Prix actuel", current_date, current_price, CURRENT_COLOR, "diamond", False),
    ]

    for name, date, price, color, symbol, show_text in markers:
        fig.add_trace(
            go.Scatter(
                x=[date],
                y=[price],
                mode="markers+text" if show_text else "markers",
                name=name,
                marker={"size": 12, "color": color, "symbol": symbol,
                        "line": {"width": 2, "color": "white"}},
                text=[f"{name} {price:.3f} €"],
                # Texte sous le minimum, au-dessus du maximum
                textposition="bottom center" if name == "Minimum" else "top center",
                textfont={"color": color, "size": 12},
                hovertemplate=f"{name}<br>%{{x|%d/%m/%Y}}<br>%{{y:.3f}} €/L<extra></extra>",
            )
        )

    # --------------------------------------------------------
    # Mise en page
    # --------------------------------------------------------

    # Marge verticale pour que les textes min / max ne soient pas coupés.
    price_range = max_row["prix_valeur"] - min_row["prix_valeur"]
    padding = max(price_range * 0.25, 0.02)

    fig.update_layout(
        height=520,
        hovermode="closest",
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        # Légende horizontale au-dessus du graphique
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        xaxis={"title": None, "showgrid": False},
        yaxis={
            "title": "Prix (€/L)",
            "tickformat": ".2f",
            "range": [min_row["prix_valeur"] - padding, max_row["prix_valeur"] + padding],
        },
    )

    return fig
