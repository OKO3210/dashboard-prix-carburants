"""
Prépare l'historique 2026 des prix pour la page 2.

À lancer une fois, depuis la racine du projet :
    python scripts/prepare_historique.py

Étapes :
1. télécharger l'archive annuelle officielle (un ZIP) ;
2. lire le fichier XML qu'elle contient, station par station ;
3. écrire toutes les déclarations de prix dans data/historique_2026.parquet.

Pourquoi Parquet plutôt que CSV ? Le fichier est compressé (≈ 21 Mo pour
4 millions de lignes) et on peut n'en lire qu'un carburant sans tout charger.
"""

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests


YEAR = 2026
URL = f"https://donnees.roulez-eco.fr/opendata/annee/{YEAR}"
OUTPUT_PATH = Path(f"data/historique_{YEAR}.parquet")

# On écrit le fichier par paquets de 100 000 lignes
# pour ne pas garder 4 millions de lignes en mémoire.
BATCH_SIZE = 100_000

# Schéma = liste des colonnes et de leur type dans le fichier Parquet.
SCHEMA = pa.schema([
    ("id", pa.string()),
    ("cp", pa.string()),
    ("adresse", pa.string()),
    ("ville", pa.string()),
    ("prix_nom", pa.string()),
    ("prix_valeur", pa.float64()),
    ("prix_maj", pa.timestamp("ns")),
])


def local_tag(tag):
    """Retire l'éventuel namespace XML : '{http://...}pdv' -> 'pdv'."""
    return tag.split("}")[-1]


def flush_buffer(buffer, writer):
    """
    Écrit un paquet de lignes dans le fichier Parquet.
    Le writer (l'objet qui écrit le fichier) est créé au premier paquet.
    """

    if not buffer:
        return writer

    df = pd.DataFrame(buffer)

    for column in ["id", "cp", "adresse", "ville", "prix_nom"]:
        df[column] = df[column].astype("string")

    df["prix_valeur"] = pd.to_numeric(df["prix_valeur"], errors="coerce")
    df["prix_maj"] = pd.to_datetime(df["prix_maj"], errors="coerce")

    table = pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False)

    if writer is None:
        writer = pq.ParquetWriter(OUTPUT_PATH, SCHEMA, compression="snappy")

    writer.write_table(table)
    return writer


def main():

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # On repart d'un fichier vide à chaque exécution.
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()

    # --------------------------------------------------------
    # 1. Téléchargement et ouverture du ZIP
    # --------------------------------------------------------

    print(f"Téléchargement de l'historique {YEAR}...")
    response = requests.get(URL, timeout=300)
    response.raise_for_status()
    print("Archive téléchargée.")

    # BytesIO : le ZIP est lu directement en mémoire, sans l'enregistrer sur le disque.
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    xml_files = [name for name in archive.namelist() if name.lower().endswith(".xml")]

    if not xml_files:
        raise RuntimeError("Aucun fichier XML trouvé dans l'archive.")

    # --------------------------------------------------------
    # 2. Lecture du XML
    # --------------------------------------------------------

    # Structure d'une station dans le XML :
    # <pdv id="1000001" cp="01000" ...>
    #     <adresse>596 AVENUE DE TREVOUX</adresse>
    #     <ville>SAINT-DENIS-LÈS-BOURG</ville>
    #     <prix nom="Gazole" maj="2026-01-02T00:39:00" valeur="1.638"/>
    #     <prix nom="Gazole" maj="2026-01-03T00:40:00" valeur="1.649"/>
    #     ...
    # </pdv>

    buffer = []
    writer = None
    total_rows = 0

    for xml_name in xml_files:
        print(f"Lecture de {xml_name}")

        with archive.open(xml_name) as xml_file:

            # iterparse lit le XML au fil de l'eau (événement "end" = fin d'une balise)
            # au lieu de charger tout le fichier en mémoire d'un coup.
            for _, element in ET.iterparse(xml_file, events=("end",)):

                if local_tag(element.tag) != "pdv":
                    continue

                station_id = element.attrib.get("id")
                postal_code = element.attrib.get("cp")
                address = None
                city = None
                prices = []

                for child in element:
                    tag = local_tag(child.tag)

                    if tag == "adresse":
                        address = child.text
                    elif tag == "ville":
                        city = child.text
                    elif tag == "prix":
                        prices.append({
                            "prix_nom": child.attrib.get("nom"),
                            "prix_valeur": child.attrib.get("valeur"),
                            "prix_maj": child.attrib.get("maj"),
                        })

                # Une ligne par déclaration de prix.
                for price in prices:
                    buffer.append({
                        "id": station_id,
                        "cp": postal_code,
                        "adresse": address,
                        "ville": city,
                        **price,   # ajoute prix_nom, prix_valeur et prix_maj
                    })
                    total_rows += 1

                # Libère la mémoire occupée par cette station.
                element.clear()

                # --------------------------------------------
                # 3. Écriture par paquets
                # --------------------------------------------

                if len(buffer) >= BATCH_SIZE:
                    writer = flush_buffer(buffer, writer)
                    buffer.clear()
                    print(f"{total_rows:,} lignes traitées...")

    # Dernier paquet incomplet
    writer = flush_buffer(buffer, writer)

    if writer is not None:
        writer.close()

    print()
    print("Terminé.")
    print(f"{total_rows:,} observations enregistrées.")
    print(f"Fichier : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
