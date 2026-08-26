# Présentation du projet

Deux versions du même document. La première pour comprendre et faire comprendre,
la seconde pour ceux qui vont mettre les mains dedans.

---

# Version simple

## C'est quoi

Un tableau de bord public qui met deux courbes côte à côte : combien de personnes
cherchent une destination, et combien de personnes y volent réellement.

## Ça fait quoi

Il mesure le temps qui sépare les deux, **pays par pays**.

Les statistiques officielles de trafic passagers sortent une fois par an, avec
près d'un an de retard. Les recherches Google sur « vol New York », elles, sont
visibles tout de suite. Le tableau de bord répond donc à une question simple :
combien de mois avant le départ les gens commencent-ils à chercher ?

Et la réponse n'est pas la même selon le pays d'où l'on cherche.

## Le résultat principal

Sur Paris-New York, le marché français cherche en janvier pour voler en août,
soit sept mois d'avance. Le marché américain cherche en juin pour voler en août,
soit deux mois. Même route, même avion, deux calendriers complètement différents.

À l'autre bout du spectre, Paris-Ajaccio : la recherche et le vol tombent le même
mois. C'est un marché de dernière minute, il ne s'anticipe pas.

## Pourquoi

Parce qu'un budget publicitaire doit être dépensé quand les gens cherchent, pas
quand ils voyagent. Une campagne lancée au début du mois du départ arrive trop
tard : la décision d'achat est prise depuis longtemps, souvent chez un
concurrent. Et un calendrier budgétaire unique appliqué à tous les marchés se
trompe forcément sur une partie d'entre eux.

Aujourd'hui, cette question se règle à l'intuition ou à l'habitude. Ici elle se
règle avec un chiffre, recalculé tout seul.

## Pour qui

- **Celui qui achète de la publicité pour du voyage** : compagnie aérienne,
  agence, comparateur, office de tourisme. C'est le lecteur principal, et la
  question du calendrier budgétaire est la sienne.
- **Celui qui planifie** : marketing, revenue management, qui cherche des repères
  de saisonnalité par destination et par marché.
- **Le curieux** : tout est public, vérifiable et reproductible.

## Comment on s'en sert

On ouvre la page calendrier. Chaque ligne est un couple destination et marché.
La bande du haut montre la saison de trafic réelle, la bande du bas la même
saison reculée de l'avance mesurée : c'est la période où le budget doit être
engagé. On remonte son calendrier de campagne du nombre de mois indiqué.

## Ce que ça ne fait pas

Ce n'est pas une prévision : le tableau de bord mesure un décalage passé, il
n'annonce pas le trafic de l'an prochain.

Ce n'est pas une analyse de compagnie aérienne : les chiffres portent sur une
paire d'aéroports, toutes compagnies confondues. C'est une demande de marché, pas
une part de marché.

Il n'y a ni prix, ni nombre de sièges offerts, ni budget publicitaire. Donc rien
à dire sur la rentabilité d'une campagne.

Et les recherches ne sont pas des volumes : Google Trends fournit un indice
relatif ramené de 0 à 100. On compare des formes de courbes, jamais des niveaux
entre deux pays.

## Deux résultats que le tableau de bord refuse de donner

Paris-Francfort ressort en « mesure peu fiable ». Son amplitude saisonnière est
de 1,2, autrement dit cette route n'a quasiment pas de saison. Une route
d'affaires n'a pas de fenêtre à pousser, et le dire vaut mieux que d'inventer un
chiffre net.

Rome depuis l'Italie affiche neuf mois d'avance, ce qui n'a pas de sens comme
anticipation. La lecture honnête est qu'il s'agit de deux saisons différentes :
les Italiens cherchent Paris à l'automne, alors que le trafic de la route culmine
en août. Le tableau de bord l'affiche avec cette réserve.

---

# Version technique

## Chaîne complète

```
API Eurostat            Google Trends
avia_par_fr             export manuel daté
      |                        |
      +----------+-------------+
                 |
          ingest.py            cache du brut, profils saisonniers,
                 |             trois mesures, 10 contrôles
                 |
        data/out/*.csv         5 tables versionnées
                 |
        build_site.py          HTML et SVG calculés en Python
                 |
           docs/               3 pages, GitHub Pages
```

Rafraîchissement par GitHub Actions le 5 de chaque mois, plus déclenchement
manuel. Un contrôle en erreur fait sortir le script en code non nul, donc le job
échoue. L'échec est le signal.

## Modèle de données

**Grain** : le trafic est au grain route et mois, la recherche au grain route,
marché et mois. C'est l'asymétrie structurante du projet : **le trafic est commun
à la route, seule la recherche se ventile par marché.**

Séparer les marchés par le sens du vol ne fonctionne pas. `PAS_CRD` est
bidirectionnel, vérifié sur Paris-New York en juin 2024 où 93 386 arrivées plus
82 224 départs font exactement les 175 610 du total. Et un aller-retour compte
dans les deux sens, donc au pas mensuel les deux flux sont quasi symétriques.

| Table | Contenu |
|---|---|
| `trafic_mensuel.csv` | route, mois, passagers |
| `recherche_mensuelle.csv` | route, marché, mois, indice |
| `profils_saisonniers.csv` | route, marché, fenêtre, série, mois de 1 à 12, indice |
| `calibration.csv` | les trois mesures, la concentration, l'amplitude, le drapeau de fiabilité |
| `adoption_marches.csv` | marché, mois, indice d'adoption des assistants |
| `qualite.csv` | contrôle, statut, détail, date |

## Traitements

**Profil saisonnier.** Moyenne de chacun des douze mois sur la fenêtre, ramenée à
une moyenne de 1. Élimine la tendance, le bruit d'une année isolée et la reprise
post-pandémie.

**Écart des pics.** Distance circulaire entre le mois du maximum de recherche et
celui du maximum de trafic.

**Centre de gravité.** Moyenne circulaire pondérée par le seul excédent au-dessus
de la moyenne annuelle. Pondérer par le profil brut ne marche pas : chaque mois
pèse environ 1, la composante constante écrase le signal et la concentration ne
discrimine plus rien. Vérifié : sur le profil brut toutes les valeurs tombaient
entre 0,005 et 0,12, sur l'excédent elles s'étalent de 0,25 à 0,86.

**Drapeau de fiabilité.** Une ligne est fiable si les deux concentrations
dépassent 0,45 et si les deux mesures ne divergent pas de plus de deux mois.
Sept couples sur neuf sont fiables sur 2015-2019, quatre sur neuf sur 2022-2024
qui compte trois ans au lieu de cinq.

**Corrélation croisée.** Conservée pour transparence, cherchée de 0 à 6 mois, et
publiée avec la mention de son échec sur les profils bimodaux.

## Les dix contrôles

Sources lues, origine des données de recherche, exports présents, routes du
référentiel présentes, unicité route et mois, bornes de l'indice, continuité des
séries sur les fenêtres, exclusion effective de 2020 et 2021, fraîcheur du trafic
comparée au rythme annuel de publication, points de calibration suffisants.

Statuts `ok`, `alerte`, `erreur`. Seul `erreur` fait échouer le script. Un
contrôle spécifique détecte un jeu synthétique en entrée et déclenche un bandeau
rouge sur les trois pages du site.

## Choix techniques et leurs raisons

**Aucune dépendance.** Un traitement qui doit tourner seul chaque mois pendant
des années ne doit pas pouvoir casser sur une montée de version. Effet de bord
utile : le job d'intégration continue n'a rien à installer.

**Une seule échelle verticale pour tous les graphes.** Les profils saisonniers
sont dessinés sur une échelle commune aux deux courbes et identique d'une carte à
l'autre, avec un filet tous les 25 % autour de la moyenne annuelle. Normaliser
chaque courbe sur son propre minimum et son propre maximum, ce qui était le
premier choix, donnait la même ampleur visuelle à un profil d'amplitude 1,2 et à
un profil d'amplitude 3,1 : le graphe contredisait alors le drapeau de fiabilité
affiché à côté de lui.

**Résultat et diagnostic séparés.** La page par marché ne porte que ce qui répond
à la question « quand pousser » : les deux pics et l'écart entre eux. Les mesures
qui servent à juger la fiabilité, écart des centres de gravité, concentration,
amplitude, corrélation croisée, sont en page qualité. Chaque intitulé chiffré
porte son unité sous le libellé et sa définition dans une infobulle.

**Le brut est immuable.** Les réponses de l'API sont mises en cache et
versionnées avec leur date. Toute erreur découverte plus tard se recalcule sur
les mêmes entrées.

**Sortie dans `docs/`.** GitHub Pages ne sert que la racine ou ce dossier.

**Trends en export manuel.** L'API officielle est en alpha sur candidature depuis
juillet 2025. Les bibliothèques non officielles cassent et violent les conditions
d'utilisation, ce qui serait un mauvais calcul pour un dépôt public.

**Piège Trends.** L'indice est normalisé sur la période demandée. Deux exports de
périodes différentes ne se recollent pas, il faut toujours réexporter depuis
2015.

**Pas de dbt, pas d'Airflow, pas de Great Expectations.** Cinq tables et un
traitement mensuel. Ces outils deviennent justifiés vers plusieurs dizaines de
sources, des dépendances entre modèles, ou plusieurs personnes qui écrivent dans
le même entrepôt.

## Limites techniques connues

**Ambiguïté circulaire.** Sur un cycle annuel, une avance de N mois et un retard
de 12 moins N sont indiscernables. La lecture en avance s'impose parce qu'on
réserve avant de voler, mais un écart de huit mois ou plus signale plutôt deux
saisons différentes.

**Le mois est le plancher.** Un décalage réel de six semaines ressort à un ou
deux mois, pas mieux.

**Le pic est un maximum.** Il est calculé sur une moyenne de trois à cinq ans,
donc plus stable qu'une année isolée, mais il reste un point et non une
distribution. C'est pourquoi le centre de gravité l'accompagne.

**Sémantique du comptage.** `PAS_CRD` exclut le transit direct et vaut la somme
des deux sens. Vérifié une fois, à revérifier si Eurostat change la définition.

## Arborescence

```
ingest.py                   API Eurostat, calculs, contrôles
build_site.py               génération du site
README.md                   question, résultats, sources, méthode, mode d'emploi
PRESENTATION.md             ce document
dashboard/maquette.md       spécification de la version Looker Studio
data/README.md              conventions de fichiers, liens Trends pré-remplis
data/ref/                   routes, marchés, termes
data/raw/                   brut daté, jamais modifié
data/out/                   cinq tables
docs/                       le site
```

## Lancer

```bash
python ingest.py
python build_site.py
```
