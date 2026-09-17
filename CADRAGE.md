# Document de cadrage : Dashboard prix des carburants

## Message clé

Le prix d'un même carburant varie fortement d'une station à l'autre : comparer avant de faire son plein permet d'économiser plusieurs euros à chaque passage.

Exemple au 15/09/2026 : le E10 va de 1,952 à 2,739 €/L en France, et autour de Montreuil la station la moins chère fait gagner 8,64 € sur un plein de 45 L.

## Audience cible

Les automobilistes particuliers qui veulent payer leur carburant moins cher.

Ce ne sont pas des experts de la donnée : ils doivent comprendre chaque écran en quelques secondes et savoir quoi faire ensuite (où aller, quand remplir).

## KPIs retenus

Un KPI est **actionable** s'il aide à prendre une décision. Il est **vanity** s'il est flatteur ou impressionnant mais ne change rien au comportement.

| Page | KPI | Type | Justification |
| :--- | :--- | :--- | :--- |
| 1. Vue globale | Prix moyen (+ écart vs France) | Actionable | Situe une zone par rapport au reste du pays : l'utilisateur sait si sa zone est chère. |
| 1. Vue globale | Station la moins chère | Actionable | Donne un prix et une adresse précise où aller. |
| 1. Vue globale | Station la plus chère | Actionable | Montre l'écart maximal et la station à éviter. |
| 2. Station | Prix actuel (+ évolution vs M-1) | Actionable | Indique si le prix monte ou baisse : faire le plein maintenant ou attendre. |
| 2. Station | Moyenne sur la période | Actionable | Dit si le prix actuel est au-dessus ou en dessous de l'habitude de la station. |
| 2. Station | Amplitude sur la période | Actionable | Mesure l'instabilité du prix : plus elle est forte, plus il vaut la peine de surveiller. |
| 3. Simulateur | Prix de la station recommandée (+ distance) | Actionable | Répond directement à la question : où aller et à quelle distance. |
| 3. Simulateur | Coût du plein | Actionable | Traduit le prix au litre en montant réel à payer. |
| 3. Simulateur | Économie estimée | Actionable | Chiffre le gain par rapport au prix moyen du secteur : c'est la raison de se déplacer. |

**Indicateur écarté : le nombre de stations.** C'est un indicateur vanity : un gros chiffre impressionne mais ne guide aucune décision. Il reste affiché en petit, comme simple contexte, pas comme KPI.

## Structure prévue

Le dashboard suit trois niveaux : **macro** (où est-ce moins cher ?), **micro** (comment évolue une station ?), **action** (où faire mon plein ?).

| Page | Filtres | Zone KPIs | Zone détail |
| :--- | :--- | :--- | :--- |
| 1. Où le carburant est-il le moins cher ? | Barre latérale : carburant, département. Clic sur la carte : département puis commune. | 3 KPIs en haut, puis une barre min / moyenne / max | Carte colorée par prix moyen : départements, puis communes avec les stations |
| 2. Comment le prix d'une station évolue-t-il ? | Barre latérale : carburant, département, commune, station, période | 3 KPIs en haut | Courbe en escalier du prix avec minimum, maximum, prix actuel et moyenne |
| 3. Où faire son plein au meilleur prix ? | Formulaire : ville ou code postal, carburant, litres, rayon | 3 KPIs sous la station recommandée | Tableau des 5 stations les moins chères avec le surcoût par rapport à la première |

Règles communes : un seul carburant à la fois (les prix ne sont jamais mélangés), prix de plus de 7 jours exclus, sources officielles indiquées en bas de chaque page.
