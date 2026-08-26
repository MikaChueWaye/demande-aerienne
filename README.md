# Quand la demande de voyage se cherche-t-elle ?

Le trafic passagers d'une route aérienne est publié une fois par an, avec près
d'un an de retard. L'intérêt de recherche sur la même destination, lui, est
visible tout de suite. Ce projet mesure le temps qui sépare les deux, **marché par
marché**, pour savoir quand engager un budget d'acquisition.

Tableau de bord : `<lien GitHub Pages à coller ici>`

## Ce que les données disent

Écart entre le pic de recherche et le pic de trafic, mesuré sur le profil
saisonnier moyen de 2015 à 2019. Seules les lignes jugées fiables figurent ici,
le tableau complet est dans le tableau de bord.

| Route | Marché | Pic de recherche | Pic de trafic | Avance |
|---|---|---|---|---|
| Paris CDG vers New York JFK | FR | janvier | août | **7 mois** |
| Paris CDG vers New York JFK | US | juin | août | **2 mois** |
| Paris CDG vers Rome | FR | février | août | 6 mois |
| Paris CDG vers São Paulo | BR | mai | juillet | 2 mois |
| Paris CDG vers São Paulo | FR | juillet | juillet | aucune |
| Paris Orly vers Ajaccio | FR | août | août | aucune |

Les deux premières lignes portent tout le projet : **sur la même route, le marché
français cherche sept mois avant le vol, le marché américain deux mois**. Un
calendrier budgétaire unique se trompe forcément sur l'un des deux.

Deux cas que le tableau de bord refuse de trancher, et le dit. Paris-Francfort a
une amplitude saisonnière de 1,2 : cette route n'a pas de saison, donc pas de
fenêtre à pousser. Rome depuis l'Italie affiche neuf mois, ce qui se lit plus
honnêtement comme deux saisons distinctes que comme une longue anticipation.

## Sources

- **Trafic** : Eurostat, série `avia_par_fr`, passagers transportés par paire
  d'aéroports, mensuel, récupéré par API. Publication annuelle, environ dix mois
  de retard. Réutilisation autorisée avec mention de la source.
- **Recherche et adoption des assistants** : Google Trends, export manuel daté.
  L'API officielle est en alpha fermée depuis juillet 2025 et les bibliothèques
  non officielles violent les conditions d'utilisation, donc cette étape reste
  manuelle et documentée comme telle.

Les réponses brutes de l'API et les exports sont versionnés dans `data/raw` avec
leur date : le calcul se refait à l'identique.

## Méthode

Le profil saisonnier moyen d'une série est la moyenne de chacun des douze mois
sur la fenêtre, ramenée à une moyenne de 1. Passer par ce profil élimine d'un
coup la tendance, le bruit d'une année isolée et la reprise post-pandémie.

Trois mesures, chacune avec un rôle :

1. **L'écart des pics**, indicateur de tête, lisible sans statistiques.
2. **L'écart des centres de gravité**, calculé en moyenne circulaire sur le seul
   excédent au-dessus de la moyenne annuelle. Il prend toute la masse de la
   saison et pas seulement son sommet. Quand les deux mesures se rejoignent, le
   résultat tient ; quand elles divergent, la ligne est marquée peu fiable.
3. **La corrélation croisée**, conservée bien qu'elle échoue ici. Sur des profils
   bimodaux, une vague de réservation hivernale plus un pic de dernière minute,
   aucune corrélation glissante ne résume la relation. Elle est publiée avec ce
   défaut plutôt que retirée.

Fenêtres de calibration : 2015-2019 et 2022-2024. **2020 et 2021 sont exclus** :
la pandémie détruit toute corrélation et n'apprend rien sur un délai
d'anticipation normal.

## Limites

Les sept limites sont écrites en clair sur la page « Qualité et limites » du
tableau de bord. Les deux principales : sur un cycle annuel, une avance de N mois
et un retard de 12 moins N mois sont indiscernables, et l'indice Trends est
relatif, donc deux marchés se comparent en forme mais jamais en niveau.

## Contrôles qualité

Dix contrôles à chaque ingestion, publiés tels quels dans le tableau de bord :
sources lues, routes présentes, unicité, continuité, bornes de l'indice,
fraîcheur au regard du rythme annuel de publication, points de calibration
suffisants. Un contrôle en erreur fait échouer le script, donc la planification
mensuelle. Un contrôle signale la présence d'un jeu synthétique en entrée et
déclenche un bandeau rouge sur les trois pages : impossible de publier une
maquette par inadvertance.

## Faire tourner

Python 3.9 ou plus, aucune dépendance.

```bash
python ingest.py            # API Eurostat plus exports Trends, calculs, contrôles
python build_site.py        # génère docs/, trois pages
python ingest.py --refresh  # force le rechargement depuis l'API
```

`python ingest.py --demo-trends` fabrique des courbes de recherche synthétiques
dérivées du vrai trafic et avancées de trois mois : si la calibration ressort
autre chose que trois, le calcul est cassé. C'est un test à réponse connue
déguisé en jeu d'exemple.

## Mise à jour

`.github/workflows/refresh.yml` relance l'ingestion et la construction le 5 de
chaque mois. Le trafic ne bouge qu'une fois par an, ce passage mensuel sert à le
capter dès sa sortie et à reconstruire le site quand de nouveaux exports Trends
ont été déposés.

Ajouter un export Trends : voir `data/README.md`, qui contient un lien
pré-rempli par terme et par marché.

## Structure

```
ingest.py                   API Eurostat, calculs, contrôles
build_site.py               génération du site
PRESENTATION.md             le projet expliqué, version simple et version technique
data/ref/                   routes, marchés, termes suivis
data/raw/                   brut daté : JSON Eurostat, exports Trends
data/out/                   cinq tables lues par le site
docs/                       le site publié par GitHub Pages
dashboard/maquette.md       spécification de la version Looker Studio
```

## Pourquoi sans aucune dépendance

Un traitement qui doit tourner seul chaque mois pendant des années ne doit pas
pouvoir casser sur une montée de version de bibliothèque. Tout tient dans la
bibliothèque standard, et le job d'intégration continue n'a rien à installer.

Le site suit le même principe : le HTML et le SVG sont calculés à la génération,
les définitions de colonnes passent par l'attribut `title`. Les pages sont donc
complètes sans JavaScript, et une capture d'écran montre exactement ce que montre
le navigateur.

## Remerciements

Merci à Julien Leclerc pour ses précisions sur les pratiques de l'acquisition
payante dans le transport aérien. C'est à lui que ce projet doit d'être modélisé
par marché et non par route, qui en est la décision de conception la plus
structurante : le trafic reste commun à la liaison, seule la recherche se
ventile, et c'est de là que vient tout le reste.

Mika Chue Waye · mika.chuewaye@gmail.com · mikachuewaye.com
