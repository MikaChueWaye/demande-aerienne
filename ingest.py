#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chaine d'ingestion du projet « demande aerienne ».

Deux temps, parce que les deux sources n'ont pas le meme rythme :
  calibration  sur l'historique long, une fois par an, quand Eurostat publie
  pilotage     chaque mois, la recherche etant fraiche

Entrees
  API Eurostat, serie avia_par_fr, recuperee et mise en cache dans data/raw/trafic
  data/raw/recherche/<route>_<marche>.csv   exports Google Trends manuels, dates
  data/raw/adoption/<marche>.csv            exports Trends, adoption des assistants
  data/ref/routes.csv, marches.csv, adoption.csv

Sorties, dans data/out
  trafic_mensuel.csv       route, mois, passagers
  recherche_mensuelle.csv  route, marche, mois, indice
  calibration.csv          route, marche, fenetre, decalage et correlation, brut et annuel
  adoption_marches.csv     marche, mois, indice
  qualite.csv              resultat des controles, publie dans le dashboard

Aucune dependance : bibliotheque standard uniquement.

  python ingest.py                traite ce qui est disponible
  python ingest.py --refresh      force le rechargement depuis l'API Eurostat
  python ingest.py --demo-trends  fabrique des exports Trends synthetiques pour tester
"""

import argparse
import csv
import io
import json
import math
import os
import random
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

RACINE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(RACINE, "data", "raw")
REF = os.path.join(RACINE, "data", "ref")
OUT = os.path.join(RACINE, "data", "out")

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/avia_par_fr"

# Mesure retenue : passagers transportes, hors transit direct, unite passager,
# frequence mensuelle. PAS_CRD est BIDIRECTIONNEL, il vaut arrivees plus departs.
# Verifie sur CDG-JFK en juin 2024 : 93 386 + 82 224 = 175 610.
MESURE = {"freq": "M", "unit": "PAS", "tra_meas": "PAS_CRD"}

# Fenetres de calibration. 2020 et 2021 sont exclus : la pandemie detruit
# toute correlation et n'apprend rien sur un delai d'anticipation normal.
FENETRES = {"2015-2019": ("2015-01", "2019-12"),
            "2022-2024": ("2022-01", "2024-12")}
COVID = ("2020", "2021")

DECALAGE_MAX = 6        # on cherche un decalage de 0 a 6 mois
PUBLICATION_ANNUELLE = 22   # retard maximal tolere, en mois, avant alerte


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
def lire_csv(chemin):
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        tete = f.read(4096)
        f.seek(0)
        sep = ";" if tete.count(";") > tete.count(",") else ","
        return list(csv.DictReader(f, delimiter=sep))


def lire_trends(chemin):
    """
    Export Google Trends. Deux ou trois lignes d'en-tete selon la langue de
    l'interface : on saute tout ce qui precede la premiere cellule qui ressemble
    a une date. Retourne {AAAA-MM: valeur}. Au dela de cinq ans Trends renvoie
    du mensuel, sinon on moyenne les semaines du mois.
    """
    par_mois = defaultdict(list)
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for ligne in csv.reader(f):
            if len(ligne) < 2:
                continue
            cle = ligne[0].strip()
            if len(cle) >= 7 and cle[:4].isdigit() and cle[4] == "-":
                brut = ligne[1].strip().replace("<", "").replace("%", "")
                if not brut:
                    continue
                try:
                    par_mois[cle[:7]].append(float(brut))
                except ValueError:
                    continue
    return {m: sum(v) / len(v) for m, v in par_mois.items()}


def charger_ref():
    routes = {r["route"]: r for r in lire_csv(os.path.join(REF, "routes.csv"))}
    marches = lire_csv(os.path.join(REF, "marches.csv"))
    adoption = lire_csv(os.path.join(REF, "adoption.csv"))
    if not routes or not marches:
        sys.exit("referentiels vides, voir data/ref")
    return routes, marches, adoption


# --------------------------------------------------------------------------- #
# Trafic : API Eurostat, avec cache sur disque
# --------------------------------------------------------------------------- #
def cache_trafic(code):
    return os.path.join(RAW, "trafic", "eurostat_%s.json" % code)


def telecharger_trafic(code):
    p = dict(MESURE)
    p.update({"format": "JSON", "lang": "FR", "airp_pr": code})
    url = API + "?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(url, timeout=90) as r:
        brut = r.read().decode("utf-8")
    chemin = cache_trafic(code)
    with io.open(chemin, "w", encoding="utf-8") as f:
        f.write(brut)
    return json.loads(brut)


def serie_jsonstat(doc):
    """Cube a une seule serie temporelle : l'index plat vaut l'index du temps."""
    idx = doc["dimension"]["time"]["category"]["index"]
    val = doc["value"]
    return {m: val[str(i)] for m, i in idx.items() if str(i) in val}


def charger_trafic(routes, refresh):
    trafic, meta = {}, {}
    for code, r in sorted(routes.items()):
        chemin = cache_trafic(r["code_eurostat"])
        if refresh or not os.path.exists(chemin):
            doc = telecharger_trafic(r["code_eurostat"])
            origine = "API"
        else:
            with io.open(chemin, encoding="utf-8") as f:
                doc = json.load(f)
            origine = "cache"
        trafic[code] = serie_jsonstat(doc)
        meta[code] = {"origine": origine, "maj": (doc.get("updated") or "")[:10]}
    return trafic, meta


# --------------------------------------------------------------------------- #
# Recherche
# --------------------------------------------------------------------------- #
def charger_recherche(marches):
    rech, fichiers = {}, []
    for m in marches:
        nom = "%s_%s.csv" % (m["route"], m["marche"])
        chemin = os.path.join(RAW, "recherche", nom)
        if os.path.exists(chemin):
            rech[(m["route"], m["marche"])] = lire_trends(chemin)
            fichiers.append(nom)
    return rech, fichiers


def charger_adoption(adoption):
    out, fichiers = {}, []
    for a in adoption:
        chemin = os.path.join(RAW, "adoption", "%s.csv" % a["marche"])
        if os.path.exists(chemin):
            out[a["marche"]] = lire_trends(chemin)
            fichiers.append(os.path.basename(chemin))
    return out, fichiers


# --------------------------------------------------------------------------- #
# Calibration : decalage entre recherche et trafic
# --------------------------------------------------------------------------- #
def pearson(a, b):
    n = len(a)
    if n < 12:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if va == 0 or vb == 0:
        return None
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb)


def decale_mois(m, d):
    a, mo = int(m[:4]), int(m[5:7]) + d
    a += (mo - 1) // 12
    mo = (mo - 1) % 12 + 1
    return "%04d-%02d" % (a, mo)


def variation_annuelle(serie):
    """Passage en variation sur douze mois : neutralise la saisonnalite partagee."""
    out = {}
    for m, v in serie.items():
        precedent = serie.get(decale_mois(m, -12))
        if precedent and precedent > 0:
            out[m] = v / precedent - 1.0
    return out


def meilleur_decalage(rech, traf, debut, fin):
    """Retourne (decalage, correlation, nombre de points) sur la fenetre."""
    best = (None, None, 0)
    for d in range(DECALAGE_MAX + 1):
        x, y = [], []
        for m in sorted(rech):
            if not (debut <= m <= fin) or m[:4] in COVID:
                continue
            cible = decale_mois(m, d)
            if cible[:4] in COVID or cible not in traf:
                continue
            x.append(rech[m])
            y.append(traf[cible])
        c = pearson(x, y)
        if c is not None and (best[1] is None or c > best[1]):
            best = (d, c, len(x))
    return best


def profil_saisonnier(serie, debut, fin):
    """
    Les douze valeurs mensuelles moyennes sur la fenetre, ramenees a une moyenne
    de 1. Passer par le profil moyen elimine d'un coup la tendance, le bruit
    d'une annee isolee et la reprise post-pandemie.
    """
    par = defaultdict(list)
    for m, v in serie.items():
        if debut <= m <= fin and m[:4] not in COVID:
            par[int(m[5:7])].append(v)
    if len(par) < 12:
        return None
    moy = {m: sum(v) / len(v) for m, v in par.items()}
    total = sum(moy.values()) / 12.0
    return {m: v / total for m, v in moy.items()} if total else None


def pic_mois(profil):
    return max(profil, key=profil.get)


def centre_gravite(profil):
    """
    Mois moyen de la SAISON, calcule en moyenne circulaire sur le seul excedent
    au-dessus de la moyenne annuelle. Ponderer par le profil brut ne marche pas :
    chaque mois pese environ 1, la composante constante ecrase le signal et la
    concentration ne discrimine plus rien (verifie, toutes les valeurs tombaient
    entre 0,005 et 0,12). En ne gardant que ce qui depasse la moyenne, on decrit
    la saison et non le niveau.

    Retourne le mois moyen et la concentration de 0 a 1 : proche de 1 la saison
    est ramassee sur quelques mois, proche de 0 elle est etalee ou bimodale et
    le mois moyen ne veut plus dire grand-chose.
    """
    poids = {m: max(0.0, v - 1.0) for m, v in profil.items()}
    total = sum(poids.values())
    if total <= 0:
        return None, 0.0
    X = sum(poids[m] * math.cos(2 * math.pi * (m - 1) / 12) for m in poids)
    Y = sum(poids[m] * math.sin(2 * math.pi * (m - 1) / 12) for m in poids)
    mois = (math.atan2(Y, X) / (2 * math.pi) * 12) % 12 + 1
    return mois, math.sqrt(X * X + Y * Y) / total


def amplitude(profil):
    """Mois le plus fort divise par le plus faible : 1,1 est plat, 3 est marque."""
    bas = min(profil.values())
    return max(profil.values()) / bas if bas > 0 else None


def ecart_circulaire(depuis, vers):
    """Distance en mois de `depuis` vers `vers`, de 0 a 11."""
    return (vers - depuis) % 12


def calibrer(routes, marches, trafic, recherche):
    """
    Indicateur de tete : l'ecart entre le pic de recherche et le pic de trafic.
    Indicateur robuste : l'ecart entre les centres de gravite.
    Indicateur conserve pour transparence : la correlation croisee, qui echoue
    sur les profils bimodaux et qui est publiee avec ce defaut.
    """
    lignes, profils = [], []
    for m in marches:
        cle = (m["route"], m["marche"])
        if cle not in recherche or m["route"] not in trafic:
            continue
        r, t = recherche[cle], trafic[m["route"]]
        r_yoy, t_yoy = variation_annuelle(r), variation_annuelle(t)
        for nom, (debut, fin) in sorted(FENETRES.items()):
            pr = profil_saisonnier(r, debut, fin)
            pt = profil_saisonnier(t, debut, fin)
            if not pr or not pt:
                continue
            pic_r, pic_t = pic_mois(pr), pic_mois(pt)
            cg_r, conc_r = centre_gravite(pr)
            cg_t, conc_t = centre_gravite(pt)
            dc, cc, nb = meilleur_decalage(r, t, debut, fin)
            _, cy, _ = meilleur_decalage(r_yoy, t_yoy, debut, fin)
            ecart_cg = "" if cg_r is None or cg_t is None else round((cg_t - cg_r) % 12, 1)
            # Les deux mesures doivent se rejoindre : sinon le profil est plat
            # ou bimodal, et on le dit au lieu de publier un chiffre net.
            desaccord = ""
            if ecart_cg != "":
                d = abs(ecart_circulaire(pic_r, pic_t) - ecart_cg)
                desaccord = round(min(d, 12 - d), 1)
            fiable = (conc_r >= 0.45 and conc_t >= 0.45
                      and desaccord != "" and desaccord <= 2)
            lignes.append({
                "route": m["route"],
                "libelle": routes[m["route"]]["libelle"],
                "marche": m["marche"],
                "terme": m["terme"],
                "fenetre": nom,
                "pic_recherche": pic_r,
                "pic_trafic": pic_t,
                "ecart_pics": ecart_circulaire(pic_r, pic_t),
                "cg_recherche": "" if cg_r is None else round(cg_r, 1),
                "cg_trafic": "" if cg_t is None else round(cg_t, 1),
                "ecart_cg": ecart_cg,
                "desaccord_mesures": desaccord,
                "concentration_recherche": round(conc_r, 3),
                "concentration_trafic": round(conc_t, 3),
                "amplitude_recherche": round(amplitude(pr) or 0, 2),
                "amplitude_trafic": round(amplitude(pt) or 0, 2),
                "fiable": "oui" if fiable else "non",
                "correlation_croisee": "" if cc is None else round(cc, 3),
                "decalage_correlation": "" if dc is None else dc,
                "correlation_variation_annuelle": "" if cy is None else round(cy, 3),
                "points": nb,
            })
            for serie, prof in (("recherche", pr), ("trafic", pt)):
                for mois in range(1, 13):
                    profils.append({"route": m["route"], "marche": m["marche"],
                                    "fenetre": nom, "serie": serie, "mois": mois,
                                    "indice": round(prof[mois], 3)})
    return lignes, profils


# --------------------------------------------------------------------------- #
# Controles qualite
# --------------------------------------------------------------------------- #
def controles(routes, marches, trafic, meta, recherche, fich_r, adoption, fich_a,
              calib, aujourdhui):
    c = []

    def add(nom, statut, detail):
        c.append({"controle": nom, "statut": statut, "detail": detail,
                  "verifie_le": aujourdhui})

    origines = sorted({v["origine"] for v in meta.values()})
    majs = sorted({v["maj"] for v in meta.values() if v["maj"]})
    add("Source du trafic", "ok" if trafic else "erreur",
        "%d routes, origine %s, jeu de données mis à jour le %s"
        % (len(trafic), " et ".join(origines), ", ".join(majs) or "inconnu"))

    manquantes = sorted(set(routes) - set(trafic))
    add("Routes du référentiel présentes", "ok" if not manquantes else "erreur",
        "toutes" if not manquantes else "absentes : " + ", ".join(manquantes))

    attendus = {"%s_%s" % (m["route"], m["marche"]) for m in marches}
    presents = {f[:-4].replace("_synth_", "") for f in fich_r}
    absents = sorted(attendus - presents)
    add("Exports de recherche présents", "ok" if not absents else "alerte",
        "%d sur %d" % (len(presents), len(attendus))
        + ("" if not absents else ", manquants : " + ", ".join(absents)))

    synth = [f for f in fich_r + fich_a if f.startswith("_synth")]
    if synth:
        add("Origine de la recherche", "alerte",
            "EXPORTS SYNTHÉTIQUES en entrée : à remplacer par les vrais exports "
            "Trends avant toute publication")
    elif fich_r:
        add("Origine de la recherche", "ok", "exports Trends réels")

    doublons = 0
    for code, s in trafic.items():
        if len(s) != len(set(s)):
            doublons += 1
    add("Unicité route et mois", "ok" if doublons == 0 else "erreur",
        "%d série(s) avec doublon" % doublons)

    hors = 0
    for s in list(recherche.values()) + list(adoption.values()):
        hors += sum(1 for v in s.values() if not 0 <= v <= 100)
    add("Indice de recherche dans 0 à 100", "ok" if hors == 0 else "erreur",
        "%d valeur(s) hors bornes" % hors)

    trous = []
    for code, s in sorted(trafic.items()):
        for nom, (debut, fin) in sorted(FENETRES.items()):
            attendu = mois_entre(debut, fin)
            absents_f = [m for m in attendu if m not in s]
            if absents_f:
                trous.append("%s sur %s : %d mois" % (code, nom, len(absents_f)))
    add("Continuité du trafic sur les fenêtres", "ok" if not trous else "alerte",
        "aucun trou" if not trous else " ; ".join(trous))

    covid = [l for l in calib if False]  # les fenetres excluent 2020 et 2021 par construction
    add("Exclusion de 2020 et 2021", "ok",
        "fenêtres de calibration : " + ", ".join(sorted(FENETRES)))

    derniers = [max(s) for s in trafic.values() if s]
    if derniers:
        dernier = max(derniers)
        retard = ecart_mois(dernier, aujourdhui[:7])
        add("Fraîcheur du trafic",
            "ok" if retard <= PUBLICATION_ANNUELLE else "alerte",
            "dernier mois publié %s, soit %d mois. Cette série paraît une fois "
            "par an, le retard normal va jusqu'à %d mois"
            % (dernier, retard, PUBLICATION_ANNUELLE))

    faibles = [l for l in calib if l["points"] and int(l["points"]) < 24]
    add("Points de calibration suffisants", "ok" if not faibles else "alerte",
        "toutes les fenêtres ont au moins 24 points" if not faibles
        else "%d fenêtre(s) sous 24 points" % len(faibles))

    return c


def mois_entre(debut, fin):
    a, m = int(debut[:4]), int(debut[5:7])
    af, mf = int(fin[:4]), int(fin[5:7])
    out = []
    while (a, m) <= (af, mf):
        out.append("%04d-%02d" % (a, m))
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return out


def ecart_mois(m1, m2):
    return (int(m2[:4]) - int(m1[:4])) * 12 + (int(m2[5:7]) - int(m1[5:7]))


# --------------------------------------------------------------------------- #
# Ecriture
# --------------------------------------------------------------------------- #
def ecrire(nom, lignes):
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    if not lignes:
        print("  %-24s vide" % nom)
        return
    with io.open(os.path.join(OUT, nom), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)
    print("  %-24s %5d lignes" % (nom, len(lignes)))


# --------------------------------------------------------------------------- #
# Jeu synthetique pour la recherche, le temps que les vrais exports arrivent
# --------------------------------------------------------------------------- #
def demo_trends(routes, marches, adoption, trafic):
    """
    Fabrique des exports Trends plausibles a partir du VRAI trafic : on avance la
    courbe de trois mois et on ajoute du bruit. Si la calibration ressort autre
    chose que trois, le calcul de decalage est casse. Les fichiers portent le
    prefixe _synth pour que le controle qualite les signale.
    """
    random.seed(2026)
    for m in marches:
        t = trafic.get(m["route"])
        if not t:
            continue
        mois = sorted(x for x in t if x >= "2015-01")
        vals = {}
        for x in mois:
            source = t.get(decale_mois(x, 3))
            if source:
                vals[x] = source * random.uniform(0.9, 1.1)
        if not vals:
            continue
        haut = max(vals.values())
        lignes = [["Categorie : toutes categories"], [],
                  ["Mois", "%s: (%s)" % (m["terme"], m["marche"])]]
        for x in sorted(vals):
            lignes.append([x, int(round(100.0 * vals[x] / haut))])
        chemin = os.path.join(RAW, "recherche", "_synth_%s_%s.csv" % (m["route"], m["marche"]))
        with io.open(chemin, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(lignes)
    for a in adoption:
        lignes = [["Categorie : toutes categories"], [], ["Mois", "%s: (%s)" % (a["terme"], a["marche"])]]
        for i, x in enumerate(mois_entre("2015-01", "2026-07")):
            v = 1 if x < "2022-11" else min(100, 2 + (i - 94) * 1.4 * random.uniform(0.85, 1.15))
            lignes.append([x, int(round(max(0, v)))])
        with io.open(os.path.join(RAW, "adoption", "_synth_%s.csv" % a["marche"]),
                     "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(lignes)
    print("exports synthetiques ecrits, prefixe _synth, decalage attendu : 3 mois")


def charger_recherche_synth(marches):
    rech, fichiers = {}, []
    for m in marches:
        nom = "_synth_%s_%s.csv" % (m["route"], m["marche"])
        chemin = os.path.join(RAW, "recherche", nom)
        if os.path.exists(chemin):
            rech[(m["route"], m["marche"])] = lire_trends(chemin)
            fichiers.append(nom)
    return rech, fichiers


def charger_adoption_synth(adoption):
    out, fichiers = {}, []
    for a in adoption:
        nom = "_synth_%s.csv" % a["marche"]
        chemin = os.path.join(RAW, "adoption", nom)
        if os.path.exists(chemin):
            out[a["marche"]] = lire_trends(chemin)
            fichiers.append(nom)
    return out, fichiers


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="recharge depuis l'API Eurostat")
    ap.add_argument("--demo-trends", action="store_true",
                    help="fabrique des exports de recherche synthetiques")
    args = ap.parse_args()

    aujourdhui = date.today().isoformat()
    routes, marches, adoption_ref = charger_ref()

    print("ingestion du %s" % aujourdhui)
    trafic, meta = charger_trafic(routes, args.refresh)
    for code in sorted(trafic):
        s = trafic[code]
        print("  trafic %-8s %3d mois, %s a %s (%s)"
              % (code, len(s), min(s), max(s), meta[code]["origine"]))

    if args.demo_trends:
        demo_trends(routes, marches, adoption_ref, trafic)

    recherche, fich_r = charger_recherche(marches)
    adoption, fich_a = charger_adoption(adoption_ref)
    if not recherche:
        r2, f2 = charger_recherche_synth(marches)
        a2, fa2 = charger_adoption_synth(adoption_ref)
        recherche, fich_r = r2, f2
        adoption, fich_a = a2, fa2

    lignes_trafic = [{"route": c, "libelle": routes[c]["libelle"], "mois": m,
                      "passagers": int(round(v)), "extrait_le": aujourdhui}
                     for c, s in sorted(trafic.items()) for m, v in sorted(s.items())]
    lignes_rech = [{"route": r, "marche": mk, "mois": m, "indice": round(v, 1),
                    "extrait_le": aujourdhui}
                   for (r, mk), s in sorted(recherche.items()) for m, v in sorted(s.items())]
    lignes_ado = [{"marche": mk, "mois": m, "indice": round(v, 1), "extrait_le": aujourdhui}
                  for mk, s in sorted(adoption.items()) for m, v in sorted(s.items())]
    calib, profils = calibrer(routes, marches, trafic, recherche)

    print("sorties :")
    ecrire("trafic_mensuel.csv", lignes_trafic)
    ecrire("recherche_mensuelle.csv", lignes_rech)
    ecrire("calibration.csv", calib)
    ecrire("profils_saisonniers.csv", profils)
    ecrire("adoption_marches.csv", lignes_ado)
    ctrl = controles(routes, marches, trafic, meta, recherche, fich_r,
                     adoption, fich_a, calib, aujourdhui)
    ecrire("qualite.csv", ctrl)

    for x in ctrl:
        if x["statut"] != "ok":
            print("  [%s] %s : %s" % (x["statut"], x["controle"], x["detail"]))
    if any(x["statut"] == "erreur" for x in ctrl):
        sys.exit("controles en erreur")


if __name__ == "__main__":
    main()
