#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genere le site statique a partir des CSV de data/out.

Trois pages, aucune dependance, aucun script cote client : du HTML et du SVG
calcules ici. Publiable tel quel sur GitHub Pages.

  docs/index.html    calendrier : quand pousser, par marche et par destination
  marches.html  les courbes, recherche contre trafic, par marche
  qualite.html  controles, limites, fiabilite de l'instrument

  python build_site.py
"""

import csv
import io
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
def svg_profil(pr, pt, largeur=520, hauteur=190):
    """
    Les deux profils saisonniers sur douze mois, normalises chacun sur lui-meme.
    Le pic de chaque courbe est marque : c'est l'ecart entre ces deux marques
    que mesure l'indicateur de tete.
    """
    ml, mr, mt, mb = 10, 10, 16, 26
    w, h = largeur - ml - mr, hauteur - mt - mb

    def pts(profil, couleur, epaisseur, marque, au_dessus):
        if not profil:
            return ""
        lo, hi = min(profil.values()), max(profil.values())
        ecart = (hi - lo) or 1.0
        coords = []
        for m in range(1, 13):
            x = ml + w * (m - 1) / 11.0
            y = mt + h - (profil[m] - lo) / ecart * h
            coords.append((x, y, m))
        ligne = ('<polyline fill="none" stroke="%s" stroke-width="%s" '
                 'stroke-linejoin="round" points="%s"/>'
                 % (couleur, epaisseur, " ".join("%.1f,%.1f" % (x, y) for x, y, _ in coords)))
        pic = max(profil, key=profil.get)
        px, py, _ = coords[pic - 1]
        # l'etiquette est bornee pour ne pas sortir du cadre quand le pic tombe
        # en janvier ou en decembre, et l'une va au-dessus, l'autre en dessous,
        # sinon elles se superposent quand les deux pics coincident.
        tx = min(max(px, ml + 26), largeur - mr - 26)
        ty = py - 8 if au_dessus else py + 14
        return ligne + ('<circle cx="%.1f" cy="%.1f" r="3.4" fill="%s"/>'
                        '<text x="%.1f" y="%.1f" font-size="10" font-weight="700" '
                        'fill="%s" text-anchor="middle">%s</text>'
                        % (px, py, couleur, tx, ty, couleur, marque))

    axes = ""
    for m in range(1, 13):
        x = ml + w * (m - 1) / 11.0
        axes += ('<text x="%.1f" y="%d" font-size="9" fill="%s" text-anchor="middle">%s</text>'
                 % (x, hauteur - 8, INK_SOFT, MOIS[m - 1][0]))
    return ('<svg viewBox="0 0 %d %d" class="graphe" role="img" '
            'aria-label="profils saisonniers">%s%s%s</svg>'
            % (largeur, hauteur, axes, pts(pt, INK, 1.6, "trafic", False),
               pts(pr, TERRA, 2.0, "recherche", True)))


def svg_courbes(serie_a, serie_b, mois, titre_a, titre_b, largeur=560, hauteur=170):
    """Deux series normalisees chacune sur elle-meme : on compare des formes."""
    ml, mr, mt, mb = 8, 8, 14, 22
    w, h = largeur - ml - mr, hauteur - mt - mb

    def norm(s):
        vals = [s.get(m) for m in mois]
        connus = [v for v in vals if v is not None]
        if not connus:
            return []
        lo, hi = min(connus), max(connus)
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

    # reperes d'annee
    reperes = ""
    for i, m in enumerate(mois):
        if m.endswith("-01"):
            x = ml + (w * i / max(1, len(mois) - 1))
            reperes += ('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
                        'stroke-width="0.5" opacity="0.35"/>' % (x, mt, x, mt + h, INK_SOFT))
            reperes += ('<text x="%.1f" y="%d" font-size="9" fill="%s" '
                        'text-anchor="middle">%s</text>' % (x, hauteur - 6, INK_SOFT, m[:4]))

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
th.court{width:64px}
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
.cal td.lib{width:268px;text-align:left;padding:6px 18px 6px 2px;font-size:13.5px;
            white-space:nowrap;background:none;border-right:1px solid var(--filet)}
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


def texte_avance(d, fiable):
    if d == 0:
        t = "aucune avance"
    elif d == 1:
        t = "1 mois d'avance"
    else:
        t = "%d mois d'avance" % d
    if not fiable:
        return t + ", mesure peu fiable"
    # Sur un cycle annuel, une avance de 8 mois ou plus se lit plus honnetement
    # comme deux saisons differentes que comme une longue anticipation.
    if d >= 8:
        return t + ", ou deux saisons distinctes"
    return t


def page_calendrier(routes_lib, trafic, calib_idx, marches, resultat):
    corps = [resultat, '<h2>Quand pousser le budget</h2>',
             '<p class="intro">La ligne du haut est la saison de trafic réelle. '
             'La ligne du bas est la même saison reculée du décalage mesuré entre '
             'la recherche et le trafic : c\'est la période où la demande se cherche, '
             'donc celle où le budget doit être engagé.</p>',
             '<div class="leg">'
             '<span><i class="haute"></i> haute saison de trafic</span>'
             '<span><i class="epaule"></i> moyenne saison</span>'
             '<span><i class="basse"></i> basse saison</span>'
             '<span><i class="pousse"></i> à pousser</span>'
             '<span><i class="pousse-e"></i> à préparer</span></div>',
             '<div class="cadre" style="border:0;background:none"><table class="cal"><tr><th></th>'
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
        corps.append('<tr><td class="lib" rowspan="2">%s<br><span style="color:%s;font-size:11.5px">'
                     '%s</span></td>' % (lib, INK_SOFT, texte_avance(d, fiable)))
        corps.append("".join('<td class="c %s"></td>' % niveau(prof.get(i + 1, 0)) for i in range(12)))
        corps.append('</tr><tr>')
        cells = []
        for i in range(12):
            src = prof.get(decale(i + 1, -d), 0)
            n = niveau(src)
            cells.append('<td class="c %s"></td>' % ("pousse" if n == "haute" else
                                                     "pousse-e" if n == "epaule" else "basse"))
        corps.append("".join(cells) + '</tr><tr class="espace"><td colspan="13"></td></tr>')
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


def page_marches(routes_lib, profils, calib_idx, marches):
    corps = ['<h2>Profils saisonniers, fenêtre 2015-2019</h2>',
             '<p class="intro">Les douze valeurs mensuelles moyennes de chaque série, '
             'ramenées à une moyenne de 1. Terracotta : la recherche dans le marché. '
             'Sombre : le trafic sur la route. Le point marque le pic de chaque courbe, '
             'et c\'est l\'écart entre ces deux points que mesure l\'indicateur de tête. '
             'Passer par le profil moyen élimine la tendance, le bruit d\'une année '
             'isolée et la reprise post-pandémie.</p>', '<div class="cartes">']
    for m in marches:
        info = calib_idx.get((m["route"], m["marche"], FENETRE_REF_PROFIL))
        pr = profils.get((m["route"], m["marche"], FENETRE_REF_PROFIL, "recherche"))
        pt = profils.get((m["route"], m["marche"], FENETRE_REF_PROFIL, "trafic"))
        if not pr or not pt:
            continue
        if info:
            av = int(info["ecart_pics"])
            meta = ("recherche en %s, trafic en %s, <b>%s</b>"
                    % (MOIS[int(info["pic_recherche"]) - 1], MOIS[int(info["pic_trafic"]) - 1],
                       "aucune avance" if av == 0 else "%d mois d\'avance" % av))
            if info["fiable"] != "oui":
                meta += ' <span class="drapeau">mesure peu fiable</span>'
        else:
            meta = "terme : %s" % m["terme"]
        corps.append('<div class="carte"><h3>%s &nbsp;<span style="color:%s">%s</span></h3>'
                     '<div class="meta">%s</div>%s</div>'
                     % (esc(routes_lib.get(m["route"], m["route"])), TERRA, esc(m["marche"]),
                        meta, svg_profil(pr, pt)))
    corps.append('</div>')

    corps.append('<h2>Les trois mesures, côte à côte</h2>'
                 '<p class="intro">L\'écart des pics est l\'indicateur de tête. '
                 'L\'écart des centres de gravité prend toute la masse '
                 'de la saison et pas seulement son sommet : quand les deux se rejoignent, '
                 'la mesure tient ; quand ils divergent, le profil est plat ou bimodal et '
                 'la ligne est marquée peu fiable. La corrélation croisée est conservée pour '
                 'transparence, bien qu\'elle échoue sur les profils bimodaux.</p>')
    corps.append('<div class="cadre"><table><tr><th>Route</th><th>Marché</th><th>Fenêtre</th>'
                 '<th class="court">Pic<br>recherche</th><th class="court">Pic<br>trafic</th>'
                 '<th class="court">Écart<br>des pics</th><th class="court">Écart<br>des centres</th>'
                 '<th class="court">Concentration</th><th class="court">Amplitude</th>'
                 '<th class="court">Corrélation<br>croisée</th><th class="court">Fiable</th></tr>')
    for (route, marche, fen), r in sorted(calib_idx.items()):
        corps.append('<tr><td title="%s"><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td><td class="%s">%s</td></tr>'
                     % (esc(routes_lib.get(route, route)), esc(route), esc(marche), esc(fen),
                        MOIS[int(r["pic_recherche"]) - 1], MOIS[int(r["pic_trafic"]) - 1],
                        r["ecart_pics"], r["ecart_cg"], r["concentration_recherche"],
                        r["amplitude_recherche"], r["correlation_croisee"],
                        "ok" if r["fiable"] == "oui" else "alerte", r["fiable"]))
    corps.append('</table></div>')
    return "\n".join(corps)


def page_qualite(qualite, adoption, trafic):
    corps = ['<h2>Contrôles automatiques</h2>',
             '<p class="intro">Exécutés à chaque ingestion. Un contrôle en erreur fait '
             'échouer le traitement, donc la planification mensuelle.</p>',
             '<div class="cadre"><table><tr><th>Contrôle</th><th>Statut</th><th>Détail</th><th>Vérifié le</th></tr>']
    for q in qualite:
        corps.append('<tr><td>%s</td><td class="%s">%s</td><td>%s</td><td>%s</td></tr>'
                     % (esc(q["controle"]), q["statut"], esc(q["statut"]),
                        esc(q["detail"]), esc(q["verifie_le"])))
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
                     'des marchés entre eux, pas à quantifier une perte.</p>')
        corps.append('<div class="cartes">')
        for (marche,), s in sorted(par_marche.items()):
            corps.append('<div class="carte"><h3>%s</h3><div class="meta">'
                         'intérêt de recherche pour les assistants</div>%s</div>'
                         % (esc(marche), svg_courbes(s, {}, mois, "adoption", "")))
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
        "marches.html": ("Par marché", page_marches(routes_lib, profils, calib_idx, marches)),
        "qualite.html": ("Qualité et limites", page_qualite(qualite, adoption, trafic)),
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
