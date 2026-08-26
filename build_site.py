#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genere le site statique a partir des CSV de data/out.

Trois pages de HTML et de SVG calcules ici, sans dependance ni requete
externe. Les pages sont completes et justes sans script : ce qui se lit a
l'ecran se lit aussi a l'impression et sur une capture.

  docs/index.html    calendrier : quand pousser, par marche et par destination
  marches.html  les courbes, recherche contre trafic, par marche
  qualite.html  controles, limites, fiabilite de l'instrument

  python build_site.py
"""

import csv
import io
import math
import os
from collections import defaultdict
from datetime import date

RACINE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(RACINE, "data", "out")
SITE = os.path.join(RACINE, "docs")

TERRA, CREAM, INK, INK_SOFT = "#9A543E", "#F4EDE7", "#222124", "#6E625C"
MOIS = ["jan", "fév", "mar", "avr", "mai", "juin",
        "juil", "août", "sep", "oct", "nov", "déc"]
FENETRE_REF = "2022-2024"
FENETRE_REF_PROFIL = "2015-2019"   # fenêtre propre, sans 2020-2021
SEUIL_HAUTE = 1.10      # au-dessus de 110 % de la moyenne : haute saison
SEUIL_EPAULE = 0.95


def lire(nom):
    chemin = os.path.join(OUT, nom)
    if not os.path.exists(chemin):
        return []
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# Definition de chaque colonne chiffree, affichee au survol de son intitule.
# Le tableau porte des nombres dont l'unite n'est pas devinable : elle est
# ecrite sous l'intitule, et la definition complete tient dans l'infobulle.
DEFS = {
    "pic_recherche": "Mois le plus haut du profil saisonnier de recherche, "
                     "sur la fenêtre indiquée.",
    "pic_trafic": "Mois le plus haut du profil saisonnier de trafic de la route. "
                  "Le trafic est commun à la route, il ne se ventile pas par marché.",
    "ecart_pics": "Nombre de mois entre le pic de recherche et le pic de trafic. "
                  "C'est l'indicateur de tête : l'avance avec laquelle la demande "
                  "se cherche, donc le recul à appliquer au budget.",
    "ecart_cg": "Distance en mois entre les deux centres de gravité de saison, "
                "calculés sur le seul excédent au-dessus de la moyenne annuelle. "
                "Sert de contrôle à l'écart des pics : les deux doivent concorder.",
    "concentration": "Part de la saison ramassée autour d'un seul moment de "
                     "l'année. 0 : étalée sur les douze mois. 1 : concentrée sur "
                     "un seul mois. En dessous de 0,45, un pic ne résume plus la saison.",
    "amplitude": "Mois le plus fort divisé par le mois le plus faible. 1,2 est un "
                 "profil quasi plat, 2,4 un profil très saisonnier.",
    "correlation": "Corrélation entre les deux séries mensuelles brutes, au meilleur "
                   "décalage de 0 à 6 mois. Elle échoue sur les profils bimodaux et "
                   "reste publiée avec son défaut.",
    "fiable": "Oui quand les deux concentrations dépassent 0,45 et que l'écart des "
              "pics et l'écart des centres ne divergent pas de plus de deux mois.",
}

SURVOL = ("Les intitulés soulignés en pointillé donnent leur définition au survol.")


def dfn(libelle, cle, unite=None):
    """Intitule de colonne : definition au survol, unite sous le libelle."""
    u = '<span class="unite">%s</span>' % unite if unite else ""
    return ('<span class="def" title="%s">%s</span>%s'
            % (esc(DEFS[cle]), libelle, u))


def num_fr(v, dec=None):
    """
    Separateur decimal francais, tiret quand la valeur manque.

    dec impose le nombre de decimales : sans lui, une colonne melange 0,4 et
    0,768 et les chiffres ne s'alignent plus verticalement.
    """
    t = "" if v is None else str(v).strip()
    if not t:
        return "–"
    if dec is not None:
        try:
            t = "{:.{}f}".format(float(t), dec)
        except ValueError:
            pass
    return t.replace(".", ",")


# --------------------------------------------------------------------------- #
# Calculs
# --------------------------------------------------------------------------- #
def profil_saisonnier(trafic, route, debut="2022-01", fin="2024-12"):
    """Indice moyen par mois calendaire, 1.0 = moyenne de l'annee."""
    par_mois = defaultdict(list)
    for r in trafic:
        if r["route"] != route or not (debut <= r["mois"] <= fin):
            continue
        par_mois[int(r["mois"][5:7])].append(float(r["passagers"]))
    if not par_mois:
        return {}
    moyennes = {m: sum(v) / len(v) for m, v in par_mois.items()}
    total = sum(moyennes.values()) / len(moyennes)
    return {m: v / total for m, v in moyennes.items()} if total else {}


def niveau(indice):
    if indice >= SEUIL_HAUTE:
        return "haute"
    if indice >= SEUIL_EPAULE:
        return "epaule"
    return "basse"


def decale(mois_num, d):
    """Mois calendaire recule de d mois, avec bouclage sur l'annee."""
    return (mois_num - 1 - d) % 12 + 1


def serie_par(rows, cles, mois_key="mois", val_key="indice"):
    out = defaultdict(dict)
    for r in rows:
        out[tuple(r[k] for k in cles)][r[mois_key]] = float(r[val_key])
    return out


# --------------------------------------------------------------------------- #
# SVG
# --------------------------------------------------------------------------- #
def bornes_communes(profils, fenetre):
    """
    Minimum et maximum sur tous les profils affiches, arrondis au vingtieme.
    Une echelle unique est la condition pour que les graphes soient comparables
    entre eux : sans elle, un profil plat est dessine avec la meme ampleur
    qu'un profil tres saisonnier, ce qui contredit la mesure publiee a cote.
    """
    vals = [x for cle, prof in profils.items()
            if cle[2] == fenetre for x in prof.values()]
    if not vals:
        return (0.6, 1.6)
    return (math.floor(min(vals) * 20) / 20.0, math.ceil(max(vals) * 20) / 20.0)


def svg_profil(pr, pt, bornes, largeur=340, hauteur=196):
    """
    Les deux profils saisonniers sur douze mois.

    L'echelle verticale est commune aux deux courbes et identique d'une carte a
    l'autre : un profil plat a donc l'air plat. Le filet pointille est la
    moyenne annuelle de la serie, un filet clair par tranche de 25 % au-dessus et en
    dessous : c'est ce repere qui donne son sens a l'axe vertical. Le pic de
    chaque courbe est marque, et c'est l'ecart entre ces deux marques que mesure
    l'indicateur de tete.
    """
    lo, hi = bornes
    ml, mr, mt, mb = 46, 12, 16, 30
    w, h = largeur - ml - mr, hauteur - mt - mb
    ecart = (hi - lo) or 1.0

    def y_de(v):
        return mt + h - (v - lo) / ecart * h

    def x_de(m):
        return ml + w * (m - 1) / 11.0

    # Un filet tous les 25 % de la moyenne, sur toute la hauteur de l'echelle
    # commune. Les filets hauts restent utiles la ou aucune courbe ne monte :
    # ils disent au lecteur que la place existe et que cette courbe ne l'occupe
    # pas, au lieu de laisser une bande vide qui passe pour un defaut.
    reperes = ""
    k = int(math.ceil((lo - 1.0) / 0.25))
    while 1.0 + k * 0.25 <= hi + 1e-9:
        val = 1.0 + k * 0.25
        k += 1
        if val < lo - 1e-9:
            continue
        y = y_de(val)
        moyenne = abs(val - 1.0) < 1e-9
        style = ('stroke-width="1" stroke-dasharray="3 3" opacity="0.6"' if moyenne
                 else 'stroke-width="0.7" opacity="0.24"')
        lib = "moyenne" if moyenne else "%+d %%" % int(round((val - 1.0) * 100))
        reperes += ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" %s/>'
                    % (ml, y, ml + w, y, INK_SOFT, style))
        reperes += ('<text x="%d" y="%.1f" font-size="9.5" fill="%s" '
                    'text-anchor="end">%s</text>' % (ml - 7, y + 3.4, INK_SOFT, lib))

    # axe des mois : un repere pour les douze, une etiquette un mois sur deux
    axes = ""
    for m in range(1, 13):
        x = x_de(m)
        axes += ('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
                 'stroke-width="0.8" opacity="0.4"/>' % (x, mt + h, x, mt + h + 3, INK_SOFT))
        if m % 2:
            axes += ('<text x="%.1f" y="%d" font-size="9.5" fill="%s" '
                     'text-anchor="middle">%s</text>'
                     % (x, mt + h + 17, INK_SOFT, MOIS[m - 1]))

    def trace(profil, couleur, epaisseur, marque, au_dessus):
        if not profil:
            return ""
        coords = [(x_de(m), y_de(profil[m])) for m in range(1, 13)]
        ligne = ('<polyline fill="none" stroke="%s" stroke-width="%s" '
                 'stroke-linejoin="round" points="%s"/>'
                 % (couleur, epaisseur, " ".join("%.1f,%.1f" % c for c in coords)))
        pic = max(profil, key=profil.get)
        px, py = coords[pic - 1]
        # l'etiquette est bornee pour ne pas sortir du cadre quand le pic tombe
        # en janvier ou en decembre, et l'une va au-dessus, l'autre en dessous,
        # sinon elles se superposent quand les deux pics coincident.
        tx = min(max(px, ml + 26), largeur - mr - 26)
        ty = py - 8 if au_dessus else py + 15
        return ligne + ('<circle cx="%.1f" cy="%.1f" r="3.4" fill="%s"/>'
                        '<text x="%.1f" y="%.1f" font-size="10" font-weight="700" '
                        'fill="%s" text-anchor="middle">%s</text>'
                        % (px, py, couleur, tx, ty, couleur, marque))

    return ('<svg viewBox="0 0 %d %d" class="graphe" role="img" '
            'aria-label="profils saisonniers de la recherche et du trafic">'
            '%s%s%s%s</svg>'
            % (largeur, hauteur, reperes, axes,
               trace(pt, INK, 1.6, "trafic", False),
               trace(pr, TERRA, 2.0, "recherche", True)))


def svg_courbes(serie_a, serie_b, mois, titre_a, titre_b, largeur=340, hauteur=150,
                bornes=None):
    """
    Deux series dans le temps.

    Avec bornes, l'echelle verticale est fixe et affichee : c'est le cas de
    l'indice Trends, qui va de 0 a 100 par construction. Sans bornes, chaque
    serie est ramenee a son propre minimum et son propre maximum et seule la
    forme se compare.
    """
    ml, mr, mt, mb = (34, 12, 12, 24) if bornes else (10, 10, 12, 24)
    w, h = largeur - ml - mr, hauteur - mt - mb

    def norm(s):
        vals = [s.get(m) for m in mois]
        connus = [v for v in vals if v is not None]
        if not connus:
            return []
        lo, hi = bornes if bornes else (min(connus), max(connus))
        ecart = (hi - lo) or 1.0
        return [None if v is None else (v - lo) / ecart for v in vals]

    a, b = norm(serie_a), norm(serie_b)
    if not a and not b:
        return '<p class="vide">Pas de donnée sur cette fenêtre.</p>'

    def chemin(vals, couleur, epaisseur):
        pts, seg = [], []
        for i, v in enumerate(vals):
            if v is None:
                if len(seg) > 1:
                    pts.append(seg)
                seg = []
                continue
            x = ml + (w * i / max(1, len(mois) - 1))
            y = mt + h - v * h
            seg.append("%.1f,%.1f" % (x, y))
        if len(seg) > 1:
            pts.append(seg)
        return "".join(
            '<polyline fill="none" stroke="%s" stroke-width="%s" '
            'stroke-linejoin="round" points="%s"/>' % (couleur, epaisseur, " ".join(s))
            for s in pts)

    # echelle verticale, seulement quand elle a un sens affichable
    reperes = ""
    if bornes:
        lo, hi = bornes
        for val in (hi, (lo + hi) / 2.0, lo):
            y = mt + h - (val - lo) / ((hi - lo) or 1.0) * h
            reperes += ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                        'stroke-width="0.7" opacity="0.24"/>' % (ml, y, ml + w, y, INK_SOFT))
            reperes += ('<text x="%d" y="%.1f" font-size="9.5" fill="%s" '
                        'text-anchor="end">%s</text>'
                        % (ml - 7, y + 3.4, INK_SOFT, ("%g" % val)))

    # reperes d'annee : un filet par annee, une etiquette une annee sur deux,
    # sinon les libelles se touchent quand la carte tient dans une colonne
    annees = 0
    for i, m in enumerate(mois):
        if m.endswith("-01"):
            x = ml + (w * i / max(1, len(mois) - 1))
            reperes += ('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
                        'stroke-width="0.5" opacity="0.3"/>' % (x, mt, x, mt + h, INK_SOFT))
            if annees %2 == 0:
                reperes += ('<text x="%.1f" y="%d" font-size="9.5" fill="%s" '
                            'text-anchor="middle">%s</text>'
                            % (x, hauteur - 7, INK_SOFT, m[:4]))
            annees += 1

    return (
        '<svg viewBox="0 0 %d %d" class="graphe" role="img" aria-label="%s et %s">'
        '%s%s%s</svg>'
        % (largeur, hauteur, esc(titre_a), esc(titre_b), reperes,
           chemin(b, INK, 1.4), chemin(a, TERRA, 1.8)))


# --------------------------------------------------------------------------- #
# Gabarit
# --------------------------------------------------------------------------- #
CSS = """
@font-face{font-family:Aileron;src:url("fonts/Aileron-Regular.otf") format("opentype");font-weight:400;font-display:swap}
@font-face{font-family:Aileron;src:url("fonts/Aileron-Bold.otf") format("opentype");font-weight:700;font-display:swap}

:root{
  --terra:%s;--cream:%s;--ink:%s;--soft:%s;
  --terra-fonce:#7E4231;--terra-clair:#D8B3A3;--terra-pale:#EFE0D7;
  --action:#3F6B62;--action-clair:#B4CBC4;
  --blanc:#FFFDFC;--filet:#E4D6CC;
  --page:1120px;
}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-text-size-adjust:100%%}
body{
  background:var(--cream);color:var(--ink);
  font:400 15.5px/1.6 Aileron,"Segoe UI",system-ui,sans-serif;
  padding-bottom:72px;
}

/* ---------- en-tete ---------- */
header{background:var(--terra);color:#fff;padding:40px 32px 34px}
.dedans{max-width:var(--page);margin:0 auto}
header .oeil{font-size:11.5px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;opacity:.72}
header h1{font-size:33px;line-height:1.14;font-weight:700;letter-spacing:-.015em;margin:10px 0 12px;max-width:26ch}
header p{font-size:15.5px;line-height:1.6;opacity:.93;max-width:66ch}

/* ---------- navigation ---------- */
nav{background:var(--terra-fonce);position:sticky;top:0;z-index:5}
nav .dedans{display:flex;gap:2px;padding:0 32px}
nav a{color:#fff;padding:14px 18px 12px;text-decoration:none;font-size:14.5px;opacity:.7;border-bottom:3px solid transparent}
nav a:hover{opacity:1;background:rgba(255,255,255,.07)}
nav a.on{opacity:1;border-bottom-color:#fff;font-weight:700}

main{max-width:var(--page);margin:0 auto;padding:38px 32px 0}

/* ---------- titres et texte ---------- */
h2{font-size:13px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--terra);
   margin:52px 0 4px;padding-bottom:9px;border-bottom:2px solid var(--terra)}
h2:first-child{margin-top:0}
h3{font-size:15px;font-weight:700;letter-spacing:-.005em}
p.intro{max-width:76ch;margin:16px 0 20px;color:#3B3739}
p.intro b{color:var(--ink)}
p.intro a{color:var(--terra);text-decoration:none;border-bottom:1px solid var(--terra-clair)}
p.intro a:hover{border-bottom-color:var(--terra)}

/* ---------- bandeau de resultat ---------- */
.hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:22px 0 4px}
.tuile{background:var(--blanc);border:1px solid var(--filet);border-radius:3px;padding:18px 20px 16px}
.tuile .n{font-size:42px;line-height:1;font-weight:700;letter-spacing:-.03em;color:var(--terra)}
.tuile .n small{font-size:17px;font-weight:700;letter-spacing:0;margin-left:3px}
.tuile .q{font-size:13.5px;line-height:1.45;color:var(--soft);margin-top:9px}
.tuile .q b{color:var(--ink);font-weight:700}
.tuile.act .n{color:var(--action)}
.phrase{background:var(--blanc);border-left:4px solid var(--terra);border-radius:0 3px 3px 0;
        padding:16px 20px;margin:16px 0 0;font-size:16.5px;line-height:1.5;max-width:82ch}

/* ---------- tableaux ---------- */
.cadre{overflow-x:auto;border:1px solid var(--filet);border-radius:3px;background:var(--blanc);margin-top:18px}
table{border-collapse:collapse;width:100%%;font-size:13px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--filet)}
th{background:#F7F0EA;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
   color:var(--soft);line-height:1.3;vertical-align:bottom}
th.court{width:66px}
th.chiffre{text-align:right}
.cadre.serre{max-width:740px}
th .unite{display:block;margin-top:2px;font-size:9.5px;font-weight:400;letter-spacing:0;
          text-transform:none;color:#9C8B82}
.def{border-bottom:1px dotted var(--terra-clair);cursor:help}
p.intro .def,li .def{border-bottom-color:var(--terra)}
.survol{display:block;margin-top:6px;font-size:12.5px;color:var(--soft)}
td.num{white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:#FBF6F2}
td.num{text-align:right;font-variant-numeric:tabular-nums}
td b{font-weight:700}

/* ---------- calendrier ---------- */
.cal{border-collapse:separate;border-spacing:2px;font-size:11.5px}
.cal th,.cal td{border:0;padding:0;text-align:center}
.cal th.mois{font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
             color:var(--soft);background:none;padding-bottom:5px}
.cal td.lib{width:230px;text-align:left;padding:6px 14px 6px 2px;font-size:13.5px;
            white-space:nowrap;background:none}
.cal td.sub{width:152px;text-align:left;padding:0 14px 0 0;font-size:11.5px;line-height:1.25;
            color:var(--soft);white-space:nowrap;background:none;
            border-right:1px solid var(--filet)}
.cal td.sub b{color:var(--ink);font-weight:700}
.cal td.c{width:5.4%%}
.cal tr.espace td{height:7px;background:none}
.cal td.lib .m{color:var(--terra);font-weight:700}
.cal td.lib .d{display:block;font-size:11.5px;color:var(--soft);font-weight:400;margin-top:1px}
.cal td.c{height:23px;border-radius:2px}
.haute{background:var(--terra)}
.epaule{background:var(--terra-clair)}
.basse{background:#EDE3DB}
.pousse{background:var(--action)}
.pousse-e{background:var(--action-clair)}
.leg{display:flex;gap:18px;flex-wrap:wrap;font-size:12.5px;color:var(--soft);margin:18px 0 10px}
.leg span{display:inline-flex;align-items:center;gap:7px}
.leg i{width:14px;height:14px;border-radius:2px;display:inline-block}

/* ---------- cartes ---------- */
.cartes{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-top:18px}
.carte{background:var(--blanc);border:1px solid var(--filet);border-radius:3px;padding:15px 17px 9px}
.carte .meta{font-size:12.5px;color:var(--soft);margin:3px 0 10px;line-height:1.45}
.carte .meta b{color:var(--ink)}
.carte .meta .lr,.carte .meta .lt{font-weight:700}
.carte .meta .lr{color:var(--terra)}
.carte .meta .lt{color:var(--ink)}
.carte .meta .lr::before,.carte .meta .lt::before{content:"";display:inline-block;
          width:8px;height:8px;border-radius:1px;margin-right:5px}
.carte .meta .lr::before{background:var(--terra)}
.carte .meta .lt::before{background:var(--ink)}
.graphe{width:100%%;height:auto;display:block}
.vide{font-size:12.5px;color:var(--soft);padding:26px 0}
.drapeau{color:#8A6A1C;font-weight:700}
.pastille{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
          padding:2px 7px;border-radius:2px}
.ok{color:#2E6B45}.alerte{color:#8A6A1C}.erreur{color:#A33}
td .ok{background:#E6F0E9}td .alerte{background:#F6EBD4}td .erreur{background:#F6DEDE}

/* ---------- divers ---------- */
.bandeau{background:#8A2F2F;color:#fff;font-size:14.5px;font-weight:700}
.bandeau .dedans{padding:13px 32px}
ul.lim{margin:14px 0 0;list-style:none}
ul.lim li{position:relative;padding-left:20px;margin-bottom:11px;max-width:84ch}
ul.lim li::before{content:"";position:absolute;left:0;top:9px;width:8px;height:2px;background:var(--terra)}
footer{max-width:var(--page);margin:56px auto 0;padding:22px 32px 0;border-top:1px solid var(--filet);
       font-size:12.5px;line-height:1.65;color:var(--soft)}

@media print{
  nav{display:none}
  body{background:#fff;padding:0}
  header{padding:22px 0}
  .carte,.cadre,.tuile{break-inside:avoid}
}
@media (max-width:620px){
  header h1{font-size:26px}
  header,nav .dedans,main,footer,.bandeau .dedans{padding-left:18px;padding-right:18px}
  .tuile .n{font-size:34px}
}
""" % (TERRA, CREAM, INK, INK_SOFT)

SOUS_TITRE = ("Le trafic passagers est publié une fois par an, avec près d'un an de "
              "retard. La recherche est visible tout de suite. Ce tableau de bord "
              "mesure le temps qui les sépare, marché par marché, pour savoir quand "
              "engager un budget d'acquisition.")

PAGES = [("index.html", "Calendrier"), ("marches.html", "Par marché"),
         ("qualite.html", "Qualité et limites")]


def page(fichier, titre, corps, bandeau, maj, phrase_cle):
    nav = "".join('<a href="%s"%s>%s</a>' % (f, ' class="on"' if f == fichier else "", t)
                  for f, t in PAGES)
    alerte = ('<div class="bandeau"><div class="dedans">%s</div></div>' % esc(bandeau)
              if bandeau else "")
    favicon = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
               "<rect width='16' height='16' fill='%239A543E'/>"
               "<path d='M2 11 L6 5 L9 9 L14 3' stroke='%23F4EDE7' stroke-width='1.7' fill='none'/></svg>")
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="description" content="%s">'
        '<link rel="icon" href="%s">'
        '<title>%s</title><style>%s</style></head><body>'
        '<header><div class="dedans">'
        '<div class="oeil">Données ouvertes · Eurostat et Google Trends</div>'
        '<h1>Quand la demande de voyage se cherche-t-elle&nbsp;?</h1>'
        '<p>%s</p></div></header>'
        '<nav><div class="dedans">%s</div></nav>%s'
        '<main>%s</main>'
        '<footer><b>Sources.</b> Eurostat, série avia_par_fr, passagers transportés, mesure '
        'bidirectionnelle, publication annuelle. Google Trends, indice relatif normalisé de 0 à 100 '
        'sur la période demandée, export manuel daté.<br>'
        '<b>Remerciements.</b> Julien Leclerc, pour ses précisions sur les pratiques de '
        'l\'acquisition payante dans le transport aérien.<br>'
        'Données brutes, code et méthode dans le dépôt du projet. '
        'Dernière génération&nbsp;: %s.</footer></body></html>'
        % (esc(phrase_cle), favicon, esc(titre), CSS, esc(SOUS_TITRE), nav, alerte, corps, maj))


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def contraste_marches(calib_idx):
    """
    Cherche la route ou deux marches divergent le plus dans leur avance, parmi
    les mesures jugees fiables. C'est le resultat le plus parlant du projet :
    une meme route, deux marches, deux calendriers budgetaires.
    """
    par_route = defaultdict(list)
    for (route, marche, fen), r in calib_idx.items():
        if fen == FENETRE_REF_PROFIL and r["fiable"] == "oui":
            par_route[route].append((int(r["ecart_pics"]), marche, r))
    meilleur = None
    for route, lignes in par_route.items():
        if len(lignes) < 2:
            continue
        lignes.sort()
        ecart = lignes[-1][0] - lignes[0][0]
        if meilleur is None or ecart > meilleur[0]:
            meilleur = (ecart, route, lignes[0], lignes[-1])
    return meilleur


def bloc_resultat(routes_lib, calib_idx):
    """Trois tuiles et une phrase, calculees et non ecrites a la main."""
    total = len([1 for (_, _, f) in calib_idx if f == FENETRE_REF_PROFIL])
    fiables = len([1 for (k, r) in calib_idx.items()
                   if k[2] == FENETRE_REF_PROFIL and r["fiable"] == "oui"])
    c = contraste_marches(calib_idx)
    if not c:
        return "", ""
    _, route, bas, haut = c
    lib = routes_lib.get(route, route)
    phrase = ("Sur %s, le marché %s cherche %d mois avant le vol, le marché %s %d mois."
              % (lib, haut[1], haut[0], bas[1], bas[0]))
    html = (
        '<div class="hero">'
        '<div class="tuile"><div class="n">%d<small> mois</small></div>'
        '<div class="q">d\'avance du marché <b>%s</b><br>sur %s</div></div>'
        '<div class="tuile act"><div class="n">%d<small> mois</small></div>'
        '<div class="q">d\'avance du marché <b>%s</b><br>sur la même route</div></div>'
        '<div class="tuile"><div class="n">%d</div>'
        '<div class="q">couples route et marché suivis,<br>dont <b>%d mesures fiables</b></div></div>'
        '</div>'
        '<p class="phrase">%s</p>'
        % (haut[0], haut[1], esc(lib), bas[0], bas[1], total, fiables, esc(phrase)))
    return html, phrase


def texte_pousse(d, fiable):
    """
    Libelle de la seconde ligne de chaque paire : ce qu'elle montre et de
    combien elle recule la premiere. Sans lui, les deux lignes ne se
    distinguent que par la couleur et par la phrase d'introduction.
    """
    if d == 0:
        t = "<b>à pousser</b>, même période"
    elif d == 1:
        t = "<b>à pousser</b>, 1 mois plus tôt"
    else:
        t = "<b>à pousser</b>, %d mois plus tôt" % d
    if not fiable:
        return t + ",<br>mesure peu fiable"
    if d >= 8:
        return t + ",<br>ou deux saisons distinctes"
    return t


def page_calendrier(routes_lib, trafic, calib_idx, marches, resultat):
    corps = [resultat, '<h2>Quand pousser le budget</h2>',
             '<p class="intro">Chaque destination occupe deux lignes. La première est '
             'la saison de trafic réelle. La seconde est la même saison reculée du '
             'décalage mesuré entre la recherche et le trafic : la période où la demande '
             'se cherche, donc celle où le budget doit être engagé.</p>',
             '<div class="leg">'
             '<span><i class="haute"></i> haute saison de trafic</span>'
             '<span><i class="epaule"></i> moyenne saison</span>'
             '<span><i class="basse"></i> basse saison</span>'
             '<span><i class="pousse"></i> à pousser</span>'
             '<span><i class="pousse-e"></i> à préparer</span></div>',
             '<div class="cadre" style="border:0;background:none"><table class="cal"><tr><th></th><th></th>'
             + "".join('<th class="mois">%s</th>' % m for m in MOIS) + '</tr>']

    for m in marches:
        cle = (m["route"], m["marche"], FENETRE_REF_PROFIL)
        info = calib_idx.get(cle)
        prof = profil_saisonnier(trafic, m["route"])
        if not prof:
            continue
        d = int(info["ecart_pics"] or 0) if info else 0
        fiable = (info["fiable"] == "oui") if info else False
        lib = "%s &nbsp;<b>%s</b>" % (esc(routes_lib.get(m["route"], m["route"])), esc(m["marche"]))
        corps.append('<tr><td class="lib" rowspan="2">%s</td>'
                     '<td class="sub">saison de <b>trafic</b> réelle</td>' % lib)
        corps.append("".join('<td class="c %s"></td>' % niveau(prof.get(i + 1, 0)) for i in range(12)))
        corps.append('</tr><tr><td class="sub">%s</td>' % texte_pousse(d, fiable))
        cells = []
        for i in range(12):
            src = prof.get(decale(i + 1, -d), 0)
            n = niveau(src)
            cells.append('<td class="c %s"></td>' % ("pousse" if n == "haute" else
                                                     "pousse-e" if n == "epaule" else "basse"))
        corps.append("".join(cells) + '</tr><tr class="espace"><td colspan="14"></td></tr>')
    corps.append('</table></div>')

    corps.append('<h2>Comment lire</h2>'
                 '<p class="intro">L\'avance affichée est l\'écart entre le pic de '
                 'recherche et le pic de trafic, mesuré sur le profil saisonnier moyen '
                 'de <b>2015 à 2019</b>, la fenêtre propre : cinq années complètes, sans '
                 '2020 ni 2021 que la pandémie rend inexploitables. La saison de trafic '
                 'dessinée dans la grille est calculée sur <b>2022 à 2024</b>, parce que '
                 'c\'est celle d\'aujourd\'hui, un mois étant dit en haute saison quand '
                 'il dépasse de 10 % la moyenne annuelle, en moyenne saison entre 95 et 110 % '
                 'de cette moyenne, ce que le métier appelle l\'épaule.</p>'
                 '<p class="intro">Les lignes marquées peu fiables ont un profil trop plat '
                 'ou trop irrégulier pour qu\'un pic les résume. Elles restent affichées '
                 'plutôt que retirées : un marché sans saison marquée n\'a pas de fenêtre '
                 'à pousser.</p>')
    return "\n".join(corps)


def page_marches(routes_lib, profils, calib_idx, marches, bornes):
    corps = ['<h2>Profils saisonniers, fenêtre 2015-2019</h2>',
             '<p class="intro">Les douze valeurs mensuelles moyennes de chaque série, '
             'ramenées à une moyenne de 1. <b>L\'échelle verticale est la même sur les '
             'deux courbes et sur toutes les cartes</b>, donc un profil qui a l\'air plat '
             'l\'est. Le filet pointillé marque la moyenne annuelle de la série, un filet '
             'clair par tranche de 25 %, au-dessus comme en dessous. Le point marque le pic de chaque '
             'courbe, et l\'écart entre ces deux points est l\'avance mesurée. Passer par '
             'le profil moyen élimine la tendance, le bruit d\'une année isolée et la '
             'reprise post-pandémie.</p>', '<div class="cartes">']
    for m in marches:
        info = calib_idx.get((m["route"], m["marche"], FENETRE_REF_PROFIL))
        pr = profils.get((m["route"], m["marche"], FENETRE_REF_PROFIL, "recherche"))
        pt = profils.get((m["route"], m["marche"], FENETRE_REF_PROFIL, "trafic"))
        if not pr or not pt:
            continue
        if info:
            av = int(info["ecart_pics"])
            meta = ('<span class="lr">recherche</span> en %s, '
                    '<span class="lt">trafic</span> en %s, <b>%s</b>'
                    % (MOIS[int(info["pic_recherche"]) - 1], MOIS[int(info["pic_trafic"]) - 1],
                       "aucune&nbsp;avance" if av == 0
                       else "%d&nbsp;mois&nbsp;d\'avance" % av))
            if info["fiable"] != "oui":
                meta += ' <span class="drapeau">mesure&nbsp;peu&nbsp;fiable</span>'
        else:
            meta = "terme : %s" % m["terme"]
        corps.append('<div class="carte"><h3>%s &nbsp;<span style="color:%s">%s</span></h3>'
                     '<div class="meta">%s</div>%s</div>'
                     % (esc(routes_lib.get(m["route"], m["route"])), TERRA, esc(m["marche"]),
                        meta, svg_profil(pr, pt, bornes)))
    corps.append('</div>')

    corps.append('<h2>Toutes les avances mesurées</h2>'
                 '<p class="intro">Lecture d\'une ligne : dans ce marché, la recherche '
                 'culmine au mois indiqué, le trafic de la route au sien, et l\'écart '
                 'entre les deux est l\'avance en mois. Les quatre mesures de contrôle '
                 'qui servent à juger la fiabilité sont en page '
                 '<a href="qualite.html">Qualité et limites</a>.'
                 '<span class="survol">%s</span></p>' % SURVOL)
    corps.append('<div class="cadre serre"><table><tr><th>Route</th><th>Marché</th>'
                 '<th>Fenêtre</th><th class="court">%s</th><th class="court">%s</th>'
                 '<th class="court chiffre">%s</th><th class="court">%s</th></tr>'
                 % (dfn("Pic<br>recherche", "pic_recherche"),
                    dfn("Pic<br>trafic", "pic_trafic"),
                    dfn("Écart<br>des pics", "ecart_pics", "mois"),
                    dfn("Mesure<br>fiable", "fiable", "oui / non")))
    for (route, marche, fen), r in sorted(calib_idx.items()):
        corps.append('<tr><td title="%s"><b>%s</b></td><td>%s</td><td>%s</td>'
                     '<td>%s</td><td>%s</td><td class="num"><b>%s</b></td>'
                     '<td class="%s">%s</td></tr>'
                     % (esc(route), esc(routes_lib.get(route, route)), esc(marche), esc(fen),
                        MOIS[int(r["pic_recherche"]) - 1], MOIS[int(r["pic_trafic"]) - 1],
                        num_fr(r["ecart_pics"]),
                        "ok" if r["fiable"] == "oui" else "alerte", r["fiable"]))
    corps.append('</table></div>')
    return "\n".join(corps)


def page_qualite(qualite, adoption, trafic, routes_lib, calib_idx):
    corps = ['<h2>Contrôles automatiques</h2>',
             '<p class="intro">Exécutés à chaque ingestion. Un contrôle en erreur fait '
             'échouer le traitement, donc la planification mensuelle.</p>',
             '<div class="cadre"><table><tr><th>Contrôle</th><th>Statut</th><th>Détail</th><th>Vérifié le</th></tr>']
    for q in qualite:
        corps.append('<tr><td>%s</td><td class="%s">%s</td><td>%s</td><td>%s</td></tr>'
                     % (esc(q["controle"]), q["statut"], esc(q["statut"]),
                        esc(q["detail"]), esc(q["verifie_le"])))
    corps.append('</table></div>')

    corps.append('<h2>Diagnostic de fiabilité</h2>')
    corps.append('<p class="intro">L\'écart des pics est l\'indicateur publié. '
                 'L\'écart des centres de gravité sert de contrôle : il prend toute la '
                 'masse de la saison et pas seulement son sommet. Quand les deux '
                 'concordent, la mesure tient. Quand ils divergent de plus de deux mois, '
                 'ou quand la saison est trop étalée pour qu\'un pic la résume, la ligne '
                 'est marquée peu fiable et elle reste affichée.'
                 '<span class="survol">%s</span></p>' % SURVOL)
    corps.append('<div class="cadre"><table><tr><th>Route</th><th>Marché</th><th>Fenêtre</th>'
                 '<th class="court chiffre">%s</th><th class="court chiffre">%s</th>'
                 '<th class="court chiffre">%s</th><th class="court chiffre">%s</th>'
                 '<th class="court chiffre">%s</th><th class="court chiffre">%s</th>'
                 '<th class="court">%s</th></tr>'
                 % (dfn("Écart<br>des pics", "ecart_pics", "mois"),
                    dfn("Écart des<br>centres", "ecart_cg", "mois"),
                    dfn("Concentration<br>recherche", "concentration", "0 à 1"),
                    dfn("Concentration<br>trafic", "concentration", "0 à 1"),
                    dfn("Amplitude<br>recherche", "amplitude", "max / min"),
                    dfn("Corrélation<br>croisée", "correlation", "-1 à 1"),
                    dfn("Mesure<br>fiable", "fiable", "oui / non")))
    for (route, marche, fen), r in sorted(calib_idx.items()):
        corps.append('<tr><td title="%s"><b>%s</b></td><td>%s</td><td>%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="%s">%s</td></tr>'
                     % (esc(route), esc(routes_lib.get(route, route)), esc(marche), esc(fen),
                        num_fr(r["ecart_pics"]), num_fr(r["ecart_cg"], 1),
                        num_fr(r["concentration_recherche"], 2),
                        num_fr(r["concentration_trafic"], 2),
                        num_fr(r["amplitude_recherche"], 2),
                        num_fr(r["correlation_croisee"], 2),
                        "ok" if r["fiable"] == "oui" else "alerte", r["fiable"]))
    corps.append('</table></div>')

    if adoption:
        mois = sorted({r["mois"] for r in adoption})
        par_marche = serie_par(adoption, ["marche"])
        corps.append('<h2>Où l\'instrument se dégrade le plus vite</h2>')
        corps.append('<p class="intro">Cette mesure repose sur ce que les gens tapent '
                     'dans Google. À mesure que la recherche de voyage se déplace vers '
                     'les assistants, elle mesure une part qui rétrécit. L\'indice '
                     'ci-dessous est un proxy '
                     '<b>faible</b> : chercher un assistant mesure l\'intérêt pour '
                     'l\'outil, pas son usage pour préparer un voyage. Il sert à comparer '
                     'des marchés entre eux, pas à quantifier une perte. Chaque '
                     'courbe est graduée de 0 à 100, le maximum de la série valant '
                     '100 : deux marchés ne se comparent donc pas en niveau.</p>')
        corps.append('<div class="cartes">')
        for (marche,), s in sorted(par_marche.items()):
            corps.append('<div class="carte"><h3>%s</h3><div class="meta">'
                         'intérêt de recherche pour les assistants</div>%s</div>'
                         % (esc(marche), svg_courbes(s, {}, mois, "adoption", "",
                                                     bornes=(0, 100))))
        corps.append('</div>')

    corps.append('<h2>Ce que cette donnée ne permet pas de dire</h2><ul class="lim">')
    for lim in [
        "Le trafic par route est publié une fois par an, avec environ dix mois de retard. "
        "Il sert à calibrer un décalage, pas à suivre l'actualité. Le pilotage repose "
        "sur la recherche, qui est à jour.",
        "L'indice de recherche est relatif et normalisé sur la période demandée. Deux "
        "marchés ne se comparent pas en niveau, seulement en forme.",
        "Corrélation n'est pas causalité. Recherche et trafic partagent une saisonnalité "
        "qui suffit à produire une corrélation forte sans lien causal, d'où la double mesure.",
        "Le mois est la granularité plancher. Un décalage réel de six semaines ressort à "
        "un ou deux mois.",
        "Le trafic est bidirectionnel et toutes compagnies confondues. Un aller-retour "
        "compte dans les deux sens, donc le sens du vol ne permet pas de séparer les "
        "marchés : le trafic reste commun à la route, seule la recherche se ventile.",
        "2020 et 2021 sont exclus des calibrations. Ces deux années sont atypiques et ne "
        "renseignent pas sur un délai d'anticipation normal.",
        "Aucune donnée de prix, de capacité offerte ni de dépense publicitaire. Ce tableau "
        "de bord ne dit donc rien de la rentabilité d'une campagne.",
        "Une avance de N mois et un retard de 12 moins N mois sont indiscernables sur un "
        "cycle annuel : la donnée seule ne tranche pas. La lecture en avance s'impose "
        "parce qu'on réserve avant de voler, mais un écart de huit mois ou plus signale "
        "plutôt deux saisons différentes qu'une longue anticipation. C'est le cas du "
        "marché italien, qui cherche Paris à l'automne quand le trafic culmine en août.",
        "Quand le profil est plat ou bimodal, le pic ne résume plus la saison et les deux "
        "mesures divergent. Ces lignes sont marquées peu fiables plutôt que retirées : "
        "la route affaires Paris-Francfort, dont l'amplitude saisonnière est de 1,2, "
        "en est l'exemple. Un marché sans saison n'a pas de fenêtre à pousser.",
    ]:
        corps.append("<li>%s</li>" % lim)
    corps.append('</ul>')
    return "\n".join(corps)


# --------------------------------------------------------------------------- #
def main():
    trafic = lire("trafic_mensuel.csv")
    recherche_rows = lire("recherche_mensuelle.csv")
    calib = lire("calibration.csv")
    adoption = lire("adoption_marches.csv")
    qualite = lire("qualite.csv")
    profils = defaultdict(dict)
    for r in lire("profils_saisonniers.csv"):
        profils[(r["route"], r["marche"], r["fenetre"], r["serie"])][int(r["mois"])] = float(r["indice"])
    if not trafic:
        raise SystemExit("data/out est vide, lancer ingest.py d'abord")

    routes_lib = {r["route"]: r["libelle"] for r in trafic}
    recherche = serie_par(recherche_rows, ["route", "marche"])
    calib_idx = {(r["route"], r["marche"], r["fenetre"]): r for r in calib}
    marches = []
    vus = set()
    for r in calib:
        cle = (r["route"], r["marche"])
        if cle not in vus:
            vus.add(cle)
            marches.append({"route": r["route"], "marche": r["marche"], "terme": r["terme"]})

    synth = [q for q in qualite if q["controle"] == "Origine de la recherche"
             and q["statut"] != "ok"]
    bandeau = ("Données de recherche SYNTHÉTIQUES : ce site est une maquette, "
               "les courbes ne sont pas réelles.") if synth else ""

    bornes = bornes_communes(profils, FENETRE_REF_PROFIL)
    maj = date.today().isoformat()
    resultat, phrase = bloc_resultat(routes_lib, calib_idx)
    if not phrase:
        phrase = SOUS_TITRE
    sous = ("Le trafic passagers paraît avec près d'un an de retard, la recherche est "
            "visible tout de suite. Ce tableau de bord mesure le temps qui les sépare, "
            "par marché, pour savoir quand engager un budget d'acquisition.")

    if not os.path.isdir(SITE):
        os.makedirs(SITE)
    # les polices de la charte voyagent avec le site, aucune requete externe
    polices = os.path.join(SITE, "fonts")
    if not os.path.isdir(polices):
        os.makedirs(polices)
    for nom in ("Aileron-Regular.otf", "Aileron-Bold.otf"):
        src = os.path.join(RACINE, "assets", "fonts", nom)
        dst = os.path.join(polices, nom)
        if os.path.exists(src) and not os.path.exists(dst):
            with open(src, "rb") as f, open(dst, "wb") as g:
                g.write(f.read())
    pages = {
        "index.html": ("Calendrier", page_calendrier(routes_lib, trafic, calib_idx, marches, resultat)),
        "marches.html": ("Par marché", page_marches(routes_lib, profils, calib_idx, marches, bornes)),
        "qualite.html": ("Qualité et limites", page_qualite(qualite, adoption, trafic, routes_lib, calib_idx)),
    }
    for fichier, (titre, corps) in pages.items():
        html = page(fichier, "Demande aérienne, " + titre, corps, bandeau, maj, phrase)
        with io.open(os.path.join(SITE, fichier), "w", encoding="utf-8") as f:
            f.write(html)
        print("  docs/%-14s %6d octets" % (fichier, len(html)))
    if bandeau:
        print("  bandeau d'avertissement actif : donnees de recherche synthetiques")


if __name__ == "__main__":
    main()
