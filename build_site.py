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
:root{--terra:%s;--cream:%s;--ink:%s;--soft:%s}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--cream);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding-bottom:60px}
header{background:var(--terra);color:#fff;padding:22px 28px}
header h1{font-size:20px;font-weight:700;letter-spacing:.01em}
header p{font-size:14px;opacity:.9;margin-top:4px;max-width:70ch}
nav{background:#82442f;padding:0 28px}
nav a{display:inline-block;color:#fff;padding:11px 16px 10px;text-decoration:none;font-size:14px;opacity:.75}
nav a.on{opacity:1;box-shadow:inset 0 -3px 0 #fff}
nav a:hover{opacity:1}
main{padding:26px 28px;max-width:1180px}
h2{font-size:17px;margin:30px 0 10px}
h2:first-child{margin-top:0}
p.intro{max-width:78ch;margin-bottom:14px}
table{border-collapse:collapse;width:100%%;font-size:13.5px;background:#fff}
th,td{border:1px solid #e2d5cc;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f6efe9;font-weight:700}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.cal td,.cal th{padding:0;text-align:center;font-size:11.5px}
.cal th.mois{width:52px;font-weight:400;color:var(--soft)}
.cal td.lib{text-align:left;padding:5px 9px;font-size:13px;white-space:nowrap}
.cal td.c{height:22px}
.haute{background:var(--terra);color:#fff;font-weight:700}
.epaule{background:#d8b3a3}
.basse{background:#fff}
.pousse{background:#4f7d5e;color:#fff;font-weight:700}
.pousse-e{background:#b6cbbc}
.leg{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--soft);margin:8px 0 4px}
.leg span{display:inline-flex;align-items:center;gap:6px}
.leg i{width:13px;height:13px;display:inline-block;border:1px solid #e2d5cc}
.cartes{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}
.carte{background:#fff;border:1px solid #e2d5cc;padding:12px 14px}
.carte h3{font-size:14px;margin-bottom:2px}
.carte .meta{font-size:12px;color:var(--soft);margin-bottom:6px}
.graphe{width:100%%;height:auto;display:block}
.vide{font-size:12.5px;color:var(--soft);padding:24px 0}
.drapeau{color:#9a6b1f;font-weight:700}
.ok{color:#2e6b45}.alerte{color:#9a6b1f}.erreur{color:#a33}
.bandeau{background:#8a2f2f;color:#fff;padding:11px 28px;font-size:14px;font-weight:700}
footer{padding:20px 28px;font-size:12.5px;color:var(--soft);max-width:88ch}
ul.lim{margin:6px 0 0 18px}ul.lim li{margin-bottom:5px;max-width:84ch}
""" % (TERRA, CREAM, INK, INK_SOFT)

PAGES = [("index.html", "Calendrier"), ("marches.html", "Par marché"),
         ("qualite.html", "Qualité et limites")]


def page(fichier, titre, sous_titre, corps, bandeau, maj):
    nav = "".join('<a href="%s"%s>%s</a>' % (f, ' class="on"' if f == fichier else "", t)
                  for f, t in PAGES)
    alerte = '<div class="bandeau">%s</div>' % esc(bandeau) if bandeau else ""
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>%s</title><style>%s</style></head><body>'
        '<header><h1>Quand la demande de voyage se cherche-t-elle&nbsp;?</h1>'
        '<p>%s</p></header><nav>%s</nav>%s<main>%s</main>'
        '<footer>Sources : Eurostat, série avia_par_fr, passagers transportés, '
        'mesure bidirectionnelle. Google Trends, indice relatif normalisé de 0 à 100 '
        'sur la période demandée. Données et code : dépôt du projet. '
        'Dernière génération : %s.</footer></body></html>'
        % (esc(titre), CSS, esc(sous_titre), nav, alerte, corps, maj))


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
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


def page_calendrier(routes_lib, trafic, calib_idx, marches):
    corps = ['<h2>Quand pousser le budget</h2>',
             '<p class="intro">La ligne du haut est la saison de trafic réelle. '
             'La ligne du bas est la même saison reculée du décalage mesuré entre '
             'la recherche et le trafic : c\'est la période où la demande se cherche, '
             'donc celle où le budget doit être engagé.</p>',
             '<div class="leg">'
             '<span><i class="haute"></i> haute saison de trafic</span>'
             '<span><i class="epaule"></i> épaule</span>'
             '<span><i class="pousse"></i> à pousser</span>'
             '<span><i class="pousse-e"></i> à préparer</span></div>',
             '<table class="cal"><tr><th></th>'
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
        corps.append("".join(cells) + '</tr>')
    corps.append('</table>')

    corps.append('<h2>Comment lire</h2>'
                 '<p class="intro">L\'avance affichée est l\'écart entre le pic de '
                 'recherche et le pic de trafic, mesuré sur le profil saisonnier moyen '
                 'de <b>2015 à 2019</b>, la fenêtre propre : cinq années complètes, sans '
                 '2020 ni 2021 que la pandémie rend inexploitables. La saison de trafic '
                 'dessinée dans la grille est calculée sur <b>2022 à 2024</b>, parce que '
                 'c\'est celle d\'aujourd\'hui, un mois étant dit en haute saison quand '
                 'il dépasse de 10 % la moyenne annuelle. Autrement dit : saison actuelle, '
                 'avance calibrée sur le comportement stable d\'avant la pandémie.</p>'
                 '<p class="intro">Les lignes marquées peu fiables ont un profil trop plat '
                 'ou trop irrégulier pour qu\'un pic les résume. Elles restent affichées '
                 'plutôt que retirées : un marché sans saison marquée n\'a pas de fenêtre '
                 'à pousser, et c\'est en soi une information.</p>')
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
                 '<p class="intro">L\'écart des pics est l\'indicateur de tête, il se lit '
                 'sans statistiques. L\'écart des centres de gravité prend toute la masse '
                 'de la saison et pas seulement son sommet : quand les deux se rejoignent, '
                 'la mesure tient ; quand ils divergent, le profil est plat ou bimodal et '
                 'la ligne est marquée peu fiable. La corrélation croisée est conservée '
                 'bien qu\'elle échoue ici, parce qu\'une mesure qui ne marche pas se '
                 'publie avec son défaut plutôt qu\'elle ne se cache.</p>')
    corps.append('<table><tr><th>Route</th><th>Marché</th><th>Fenêtre</th>'
                 '<th>Pic recherche</th><th>Pic trafic</th><th>Écart des pics</th>'
                 '<th>Écart des centres</th><th>Concentration</th><th>Amplitude</th>'
                 '<th>Corrélation croisée</th><th>Fiable</th></tr>')
    for (route, marche, fen), r in sorted(calib_idx.items()):
        corps.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td><td class="%s">%s</td></tr>'
                     % (esc(routes_lib.get(route, route)), esc(marche), esc(fen),
                        MOIS[int(r["pic_recherche"]) - 1], MOIS[int(r["pic_trafic"]) - 1],
                        r["ecart_pics"], r["ecart_cg"], r["concentration_recherche"],
                        r["amplitude_recherche"], r["correlation_croisee"],
                        "ok" if r["fiable"] == "oui" else "alerte", r["fiable"]))
    corps.append('</table>')
    return "\n".join(corps)


def page_qualite(qualite, adoption, trafic):
    corps = ['<h2>Contrôles automatiques</h2>',
             '<p class="intro">Exécutés à chaque ingestion. Un contrôle en erreur fait '
             'échouer le traitement, donc la planification mensuelle : un échec est un '
             'signal, pas un silence.</p>',
             '<table><tr><th>Contrôle</th><th>Statut</th><th>Détail</th><th>Vérifié le</th></tr>']
    for q in qualite:
        corps.append('<tr><td>%s</td><td class="%s">%s</td><td>%s</td><td>%s</td></tr>'
                     % (esc(q["controle"]), q["statut"], esc(q["statut"]),
                        esc(q["detail"]), esc(q["verifie_le"])))
    corps.append('</table>')

    if adoption:
        mois = sorted({r["mois"] for r in adoption})
        par_marche = serie_par(adoption, ["marche"])
        corps.append('<h2>Où l\'instrument se dégrade le plus vite</h2>')
        corps.append('<p class="intro">Cette mesure repose sur ce que les gens tapent '
                     'dans Google. À mesure que la recherche de voyage se déplace vers '
                     'les assistants, elle mesure une part qui rétrécit, et rien dans '
                     'les données ne le signale. L\'indice ci-dessous est un proxy '
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
        "Il sert à calibrer un décalage, pas à suivre l'actualité. C'est la recherche qui "
        "est fraîche, et c'est elle qui sert au pilotage.",
        "L'indice de recherche est relatif et normalisé sur la période demandée. Deux "
        "marchés ne se comparent pas en niveau, seulement en forme.",
        "Corrélation n'est pas causalité. Recherche et trafic partagent une saisonnalité "
        "qui suffit à produire une corrélation forte sans lien causal, d'où la double mesure.",
        "Le mois est la granularité plancher. Un décalage réel de six semaines ressort à "
        "un ou deux mois, pas mieux.",
        "Le trafic est bidirectionnel et toutes compagnies confondues. Un aller-retour "
        "compte dans les deux sens, donc le sens du vol ne permet pas de séparer les "
        "marchés : le trafic reste commun à la route, seule la recherche se ventile.",
        "2020 et 2021 sont exclus des calibrations. La pandémie détruit toute corrélation "
        "et n'apprend rien sur un délai d'anticipation normal.",
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
    sous = ("Le trafic passagers paraît avec près d'un an de retard, la recherche est "
            "visible tout de suite. Ce tableau de bord mesure le temps qui les sépare, "
            "par marché, pour savoir quand engager un budget d'acquisition.")

    if not os.path.isdir(SITE):
        os.makedirs(SITE)
    pages = {
        "index.html": ("Calendrier", page_calendrier(routes_lib, trafic, calib_idx, marches)),
        "marches.html": ("Par marché", page_marches(routes_lib, profils, calib_idx, marches)),
        "qualite.html": ("Qualité et limites", page_qualite(qualite, adoption, trafic)),
    }
    for fichier, (titre, corps) in pages.items():
        html = page(fichier, "Demande aérienne, " + titre, sous, corps, bandeau, maj)
        with io.open(os.path.join(SITE, fichier), "w", encoding="utf-8") as f:
            f.write(html)
        print("  docs/%-14s %6d octets" % (fichier, len(html)))
    if bandeau:
        print("  bandeau d'avertissement actif : donnees de recherche synthetiques")


if __name__ == "__main__":
    main()
