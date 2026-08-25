# Version Looker Studio, phase 2

Le tableau de bord existe déjà en HTML dans `docs/`, généré par `build_site.py`.
Ce document décrit comment en faire une version miroir dans Looker Studio, sans
recalculer quoi que ce soit.

Pourquoi les deux. Le HTML est sous votre contrôle total, il se régénère seul
chaque mois et il ne dépend d'aucun compte. Looker Studio est l'outil qu'une
équipe d'acquisition utilise au quotidien, et savoir le manier se vérifie en
entretien. Les deux lisent **les mêmes CSV**, donc les chiffres ne peuvent pas
diverger.

## Brancher la source

Les fichiers de `data/out` sont versionnés sur GitHub, donc accessibles par une
URL brute stable. Dans une feuille Google Sheets, un onglet par fichier :

```
=IMPORTDATA("https://raw.githubusercontent.com/<compte>/<depot>/main/data/out/calibration.csv")
```

Puis dans Looker Studio, connecteur Google Sheets, une source par onglet.
`IMPORTDATA` se rafraîchit tout seul, donc la chaîne complète reste automatique
une fois posée.

Quatre onglets suffisent : `calibration`, `profils_saisonniers`,
`adoption_marches`, `qualite`.

## Page 1, calendrier

**Titre** : Quand pousser le budget.

Quatre indicateurs en bandeau, source `calibration` filtrée sur la fenêtre
2015-2019 et sur `fiable = oui` : nombre de couples suivis, avance médiane,
nombre de lignes fiables sur le total, dernier mois de trafic disponible.

**Tableau principal** : une ligne par couple route et marché, colonnes pic de
recherche, pic de trafic, avance en mois, fiabilité. Mise en forme
conditionnelle sur la fiabilité, pour que l'œil écarte tout de suite les lignes
peu sûres.

La grille colorée sur douze mois du site HTML n'a pas d'équivalent simple dans
Looker Studio. Deux options : la refaire avec un tableau croisé mois par mois et
une mise en forme conditionnelle, ou l'insérer en image depuis le site. La
seconde est honnête si la légende précise d'où vient l'image.

## Page 2, profils par marché

**Titre** : Où se situe la saison de recherche.

Source `profils_saisonniers`, filtre sur `fenetre = 2015-2019`. Un graphique en
courbes par couple route et marché, dimension `mois` de 1 à 12, deux métriques
distinguées par la colonne `serie`, recherche et trafic. Filtres en haut : route,
marché.

Sous les graphiques, le tableau complet de `calibration` avec les trois mesures :
écart des pics, écart des centres de gravité, corrélation croisée. Ce tableau est
le même que celui du site.

## Page 3, qualité et limites

**Tableau** de `qualite` : contrôle, statut, détail, date de vérification, avec
une couleur par statut.

**Graphiques** de `adoption_marches`, un par marché, pour le volet sur l'érosion
de l'instrument.

**Zone de texte** : les sept limites, recopiées telles quelles depuis la page
qualité du site HTML. Ne pas les adoucir au passage.

## Réglages

Palette terracotta `#9A543E`, crème `#F4EDE7`, encre `#222124`, la même que le CV
et le portfolio. Contrôle de plage de dates inutile, les données sont déjà
agrégées par fenêtre. Partage en lecture par lien.

## Ce qu'il ne faut pas ajouter

Une carte du monde avec des lignes entre aéroports : c'est joli et ça ne sert
aucune décision. Une quatrième page : la dernière page qu'on ajoute est toujours
celle qui trahit qu'on n'avait plus de question.
