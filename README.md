# Dashboard — Prix des carburants en France

Dashboard Streamlit construit sur les données officielles des prix des carburants.
Projet du module **Dashboards & Data Visualisation** (Bachelor Data & IA).

Le dashboard suit trois niveaux de lecture :

| Page | Niveau | Question |
| --- | --- | --- |
| `app.py` | Macro | Où le carburant est-il le moins cher ? |
| `pages/2_Analyse_station.py` | Micro | Comment le prix d'une station évolue-t-il ? |
| `pages/3_Simulateur.py` | Action | Où faire son plein au meilleur prix ? |

## Fonctionnalités

- **Vue globale** : carte de France par département, puis par commune (avec les stations) ;
  un clic sur la carte recalcule les KPIs (prix moyen, station la moins chère, la plus chère).
- **Analyse d'une station** : courbe en escalier du prix sur 2026, tendance sur un mois,
  moyenne et amplitude sur la période choisie.
- **Simulateur** : à partir d'une ville ou d'un code postal, recherche des stations dans un rayon
  (distance à vol d'oiseau, formule de Haversine) et calcul du coût du plein et de l'économie.

## Installation

```bash
python -m venv env
# Windows
env\Scripts\activate
# macOS / Linux
source env/bin/activate

pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

**Avant le premier lancement**, générer l'historique utilisé par la page 2
(téléchargement de l'archive officielle 2026 puis conversion en Parquet, quelques minutes) :

```bash
python scripts/prepare_historique.py
```

Le fichier `data/historique_2026.parquet` n'est pas versionné : il se recrée avec ce script,
et le relancer met l'historique à jour (l'archive de l'année en cours grossit chaque jour).
Les pages 1 et 3 fonctionnent sans lui : elles interrogent directement l'API du flux quotidien.

## Structure

```
├── app.py                      Page 1 — vue globale
├── pages/
│   ├── 2_Analyse_station.py    Page 2 — analyse temporelle d'une station
│   └── 3_Simulateur.py         Page 3 — simulateur de plein
├── utils/
│   ├── data.py                 Chargement des données (API, Parquet) + cache
│   ├── logic.py                Calculs (KPIs, Haversine, normalisation)
│   ├── charts.py               Graphiques Plotly
│   └── ui.py                   Éléments d'interface (barre de prix, sources)
├── scripts/
│   └── prepare_historique.py   Création de l'historique 2026 en Parquet
└── data/
    └── historique_2026.parquet  (généré, non versionné)
```

## Choix techniques

- **Chargement ciblé** : l'API ne renvoie que les colonnes utiles et le carburant choisi,
  mis en cache 6 h avec `@st.cache_data`.
- **Un carburant à la fois** : les prix du E85 et du SP98 n'ont rien à voir, ils ne sont jamais moyennés ensemble.
- **Prix périmés exclus** : un prix non mis à jour depuis plus de 7 jours est ignoré
  (le flux conserve parfois des prix vieux de plusieurs mois).
- **Communes** : `com_arm_code` est utilisé car il distingue les arrondissements de Paris, Lyon et Marseille.
- **Distances à vol d'oiseau** : pas d'API routière, pour rester simple et sans clé d'API.

## Sources des données

- [Prix des carburants en France – flux quotidien](https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-quotidien-1) — ministère de l'Économie
- [Archive annuelle 2026](https://donnees.roulez-eco.fr/opendata/annee/2026) — même source, toutes les déclarations de l'année
- [Contours administratifs](https://www.data.gouv.fr/datasets/contours-administratifs) — Etalab
- [API Découpage administratif](https://geo.api.gouv.fr/decoupage-administratif/communes) — geo.api.gouv.fr
