"""
Éléments d'interface réutilisés par plusieurs pages :
barre de prix, lecture d'un clic sur une carte, style de carte, sources.
"""

import streamlit as st


# ============================================================
# SOURCES DES DONNÉES
# ============================================================

# Chaque source : titre, lien, et une phrase qui dit ce que c'est.
DATA_SOURCES = {
    "quotidien": (
        "Prix des carburants en France – flux quotidien",
        "https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-quotidien-1",
        "Jeu de données officiel du ministère de l'Économie. Chaque station-service "
        "a l'obligation de déclarer ses prix ; le fichier donne, pour chaque station, "
        "le dernier prix de chaque carburant, son adresse et ses coordonnées GPS. "
        "Il est récupéré via l'API de data.economie.gouv.fr.",
    ),
    "historique": (
        "Prix des carburants – archive annuelle 2026",
        "https://donnees.roulez-eco.fr/opendata/annee/2026",
        "Même source officielle, mais avec TOUTES les déclarations de prix de l'année 2026. "
        "Le fichier XML d'origine est converti en Parquet par scripts/prepare_historique.py.",
    ),
    "contours": (
        "Contours administratifs (Etalab)",
        "https://www.data.gouv.fr/datasets/contours-administratifs",
        "Formes géographiques officielles des départements, utilisées pour colorer la carte de France.",
    ),
    "geo": (
        "API Découpage administratif (geo.api.gouv.fr)",
        "https://geo.api.gouv.fr/decoupage-administratif/communes",
        "API publique de l'État : contours des communes et centre géographique "
        "d'une commune à partir de son nom ou de son code postal.",
    ),
}


def show_data_sources(source_keys):
    """
    Affiche en bas de page les sources utilisées par la page.

    Exemple : show_data_sources(["quotidien", "contours", "geo"])
    """

    st.divider()
    st.markdown("##### Sources des données")

    for key in source_keys:
        title, url, description = DATA_SOURCES[key]
        # Lien Markdown : [texte](adresse)
        st.caption(f"**[{title}]({url})** — {description}")


# ============================================================
# STYLE DE CARTE SELON LE THÈME
# ============================================================

def get_map_style():
    """
    Fond de carte clair ou sombre, selon le thème Streamlit de l'utilisateur.
    Un fond clair sur une page sombre éblouit et casse la cohérence visuelle.
    """

    if st.context.theme.type == "dark":
        return "carto-darkmatter"

    return "carto-positron"


# ============================================================
# CODE DE LA ZONE CLIQUÉE SUR UNE CARTE
# ============================================================

def get_clicked_code(event):
    """
    Renvoie le code de la zone cliquée (département ou commune),
    ou None si l'utilisateur n'a rien cliqué.

    - clic sur une zone colorée : Plotly renvoie "location" ;
    - clic sur un point station : on lit customdata[0].
    """

    try:
        points = event.selection.points
    except (AttributeError, TypeError):
        points = []

    if not points:
        return None

    point = points[0]
    code = point.get("location")

    if code is None:
        custom_data = point.get("customdata") or []
        if custom_data:
            code = custom_data[0]

    return None if code is None else str(code)


# ============================================================
# BARRE VISUELLE MINIMUM -> MOYENNE -> MAXIMUM
# ============================================================

def position_percent(value, min_price, max_price):
    """
    Position d'un prix sur la barre, en % (0 = minimum, 100 = maximum).
    Exemple : min 1.80, max 2.00, prix 1.85 -> 25 %.
    """

    price_range = max_price - min_price

    # Tous les prix identiques : on place le point au milieu.
    if price_range <= 0:
        return 50

    percent = (value - min_price) / price_range * 100

    # On reste dans la barre (utile pour la moyenne France, qui peut en sortir).
    return max(0, min(100, percent))


def display_price_scale(min_price, mean_price, max_price, national_average=None):
    """
    Barre non interactive : où se situe le prix moyen entre le minimum et le maximum ?
    Si national_average est fourni, un trait bleu "France" sert de comparaison.

    Affichée avec st.html : st.markdown relirait le texte comme du Markdown,
    et les lignes indentées de 4 espaces s'afficheraient comme du code.
    """

    mean_position = position_percent(mean_price, min_price, max_price)

    # Marqueur France : un trait sur la barre + son étiquette sur une ligne à part,
    # sous la moyenne, pour que les deux textes ne se chevauchent jamais.
    national_line = ""
    national_label = ""

    if national_average is not None:
        national_position = position_percent(national_average, min_price, max_price)

        national_line = f"""
<div style="position:absolute; left:{national_position}%; top:-5px;
            width:3px; height:35px; background:#3b82f6; transform:translateX(-50%);"></div>
"""

        national_label = f"""
<div style="position:relative; height:40px; font-size:12px; color:#3b82f6;">
  <div style="position:absolute; left:{national_position}%;
              transform:translateX(-50%); text-align:center; white-space:nowrap;">
    ▲ France<br>{national_average:.3f} €/L
  </div>
</div>
"""

    html = f"""
<div style="margin:10px 0; padding:0 15px;">

  <!-- Étiquettes minimum / maximum, au-dessus des extrémités -->
  <div style="display:flex; justify-content:space-between; font-size:13px;">
    <div><strong>Minimum</strong> · {min_price:.3f} €/L</div>
    <div><strong>Maximum</strong> · {max_price:.3f} €/L</div>
  </div>

  <!-- Barre dégradée vert -> jaune -> rouge, et ses points -->
  <div style="position:relative; height:25px; margin-top:10px;">

    <div style="position:absolute; top:9px; left:0; width:100%; height:7px; border-radius:20px;
                background:linear-gradient(90deg, #22c55e 0%, #eab308 50%, #ef4444 100%);"></div>

    <div style="position:absolute; left:0%; top:3px; width:19px; height:19px; border-radius:50%;
                background:#22c55e; border:3px solid white; box-shadow:0 0 0 1px #22c55e;
                transform:translateX(-50%);"></div>

    <div style="position:absolute; left:100%; top:3px; width:19px; height:19px; border-radius:50%;
                background:#ef4444; border:3px solid white; box-shadow:0 0 0 1px #ef4444;
                transform:translateX(-50%);"></div>

    {national_line}

    <div style="position:absolute; left:{mean_position}%; top:1px; width:23px; height:23px;
                border-radius:50%; background:#111827; border:3px solid white;
                box-shadow:0 0 0 1px #111827; transform:translateX(-50%);"></div>

  </div>

  <!-- Étiquette de la moyenne : toujours juste sous son point -->
  <div style="position:relative; height:44px; margin-top:6px; font-size:13px;">
    <div style="position:absolute; left:{mean_position}%;
                transform:translateX(-50%); text-align:center; white-space:nowrap;">
      <strong>Moyenne</strong><br>{mean_price:.3f} €/L
    </div>
  </div>

  {national_label}

</div>
"""

    st.html(html)
