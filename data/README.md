# Conventions des fichiers de donnees

## Trafic, rien a faire

Recupere automatiquement par `ingest.py` depuis l'API Eurostat, serie `avia_par_fr`, mesure `PAS_CRD` (passagers transportes, **bidirectionnel**), unite passager, mensuel. La reponse brute est mise en cache dans `raw/trafic/eurostat_<code>.json` et versionnee : le brut ne se modifie jamais, il se recalcule. `--refresh` force le rechargement.

Cette serie parait **une fois par an** avec environ dix mois de retard. Elle sert a calibrer le decalage, pas a suivre l'actualite.

## Recherche, 14 exports a faire a la main

L'API Trends officielle est en alpha fermee, les bibliotheques non officielles cassent et violent les conditions d'utilisation. Cette etape reste donc manuelle et assumee.

**Procedure** : ouvrir le lien, verifier que la courbe n'est pas vide, bouton de telechargement en haut a droite du graphique, puis renommer le fichier et le deposer dans le bon dossier.

**Deux regles a ne jamais enfreindre.** Toujours exporter la periode complete depuis 2015, jamais seulement les derniers mois : l'indice est normalise sur la periode demandee, deux exports de periodes differentes ne se recollent pas. Et ne jamais changer un terme une fois la serie commencee.

### Demande, dans `raw/recherche/`

| Fichier a creer  | Terme            | Marche | Lien                                                                                                         |
| ---------------- | ---------------- | ------ | ------------------------------------------------------------------------------------------------------------ |
| `CDG-JFK_FR.csv` | vol new york     | FR     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=FR&q=vol+new+york&hl=fr)     |
| `CDG-JFK_US.csv` | flights to paris | US     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=US&q=flights+to+paris&hl=fr) |
| `CDG-GRU_FR.csv` | vol sao paulo    | FR     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=FR&q=vol+sao+paulo&hl=fr)    |
| `CDG-GRU_BR.csv` | voos para paris  | BR     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=BR&q=voos+para+paris&hl=fr)  |
| `CDG-FCO_FR.csv` | vol rome         | FR     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=FR&q=vol+rome&hl=fr)         |
| `CDG-FCO_IT.csv` | voli parigi      | IT     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=IT&q=voli+parigi&hl=fr)      |
| `CDG-FRA_FR.csv` | vol francfort    | FR     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=FR&q=vol+francfort&hl=fr)    |
| `CDG-FRA_DE.csv` | fluge nach paris | DE     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=DE&q=fluge+nach+paris&hl=fr) |
| `ORY-AJA_FR.csv` | vol ajaccio      | FR     | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=FR&q=vol+ajaccio&hl=fr)      |

### Adoption des assistants, dans `raw/adoption/`

Sert a mesurer ou l'instrument Trends se degrade le plus vite. Proxy faible et etiquete comme tel : chercher un assistant mesure l'interet pour l'outil, pas son usage pour preparer un voyage.

| Fichier a creer | Terme | Marche | Lien |
|---|---|---|---|
| `FR.csv` | chatgpt | FR | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=FR&q=chatgpt&hl=fr) |
| `US.csv` | chatgpt | US | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=US&q=chatgpt&hl=fr) |
| `BR.csv` | chatgpt | BR | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=BR&q=chatgpt&hl=fr) |
| `IT.csv` | chatgpt | IT | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=IT&q=chatgpt&hl=fr) |
| `DE.csv` | chatgpt | DE | [ouvrir](https://trends.google.fr/trends/explore?date=2015-01-01+2026-08-25&geo=DE&q=chatgpt&hl=fr) |

## Quand les vrais exports sont en place

Supprimer les fichiers prefixes `_synth_` dans `raw/recherche/` et `raw/adoption/`. Tant qu'ils sont la, le controle qualite « Origine de la recherche » passe en alerte et le signale dans le dashboard.

## Sorties, dans `out/`

Generees, a ne pas modifier a la main. Versionnees parce que le site les lit.
