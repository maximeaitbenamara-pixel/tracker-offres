"""Point d'entrée : récupère les offres, les note, met à jour data/ et docs/.

    python3 tracker/run.py                       # vraies API (clés en variables d'environnement)
    python3 tracker/run.py --fixture exemple.json  # offres de test, sans API
"""
import argparse
import csv
import datetime
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, ICI)

import scoring  # noqa: E402
import sources  # noqa: E402

FICHIER_OFFRES = os.path.join(RACINE, "data", "offres.json")
FICHIER_SUIVI = os.path.join(RACINE, "data", "suivi.csv")
FICHIER_PAGE = os.path.join(RACINE, "docs", "offres.json")
JOURS_CONSERVATION = 45


def charger_json(chemin, defaut):
    if not os.path.exists(chemin):
        return defaut
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def ecrire_json(chemin, donnees):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=1)
        f.write("\n")


def charger_suivi():
    """data/suivi.csv : id;statut;notes — à éditer à la main (ou sur github.com)."""
    if not os.path.exists(FICHIER_SUIVI):
        return {}
    with open(FICHIER_SUIVI, encoding="utf-8") as f:
        return {l["id"].strip(): l for l in csv.DictReader(f, delimiter=";") if l.get("id")}


def recuperer(criteres, fixture):
    if fixture:
        return charger_json(fixture, [])
    offres = []
    for source in sources.SOURCES:
        try:
            offres += source(criteres["recherche"])
        except Exception as e:  # une source en panne ne bloque pas les autres
            print("%s : erreur %s" % (source.__name__, e), file=sys.stderr)
    return offres


def doublon(offre):
    """Clé pour repérer la même offre publiée sur plusieurs sources."""
    return (scoring.normaliser(offre["titre"]).strip(), scoring.normaliser(offre["entreprise"]).strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", help="fichier JSON d'offres de test")
    args = parser.parse_args()

    criteres = charger_json(os.path.join(ICI, "criteres.json"), None)
    aujourd_hui = datetime.date.today().isoformat()
    limite = (datetime.date.today() - datetime.timedelta(days=JOURS_CONSERVATION)).isoformat()

    base = charger_json(FICHIER_OFFRES, {})
    nouvelles = 0
    for offre in recuperer(criteres, args.fixture):
        ancienne = base.get(offre["id"])
        offre["premiere_vue"] = ancienne["premiere_vue"] if ancienne else aujourd_hui
        offre["derniere_vue"] = aujourd_hui
        nouvelles += ancienne is None
        base[offre["id"]] = offre

    # On oublie les offres disparues depuis longtemps
    base = {k: o for k, o in base.items() if o["derniere_vue"] >= limite}
    ecrire_json(FICHIER_OFFRES, base)

    # Page : notes + suivi, sans doublons inter-sources
    suivi = charger_suivi()
    vues, page = set(), []
    for o in sorted(base.values(), key=lambda o: o["derniere_vue"], reverse=True):
        cle = doublon(o)
        if cle in vues:
            continue
        vues.add(cle)
        note = scoring.noter(o, criteres)
        s = suivi.get(o["id"], {})
        page.append({
            "id": o["id"], "source": o["source"], "titre": o["titre"],
            "entreprise": o["entreprise"], "lieu": o["lieu"], "url": o["url"],
            "date": o["date"], "contrat": o["contrat"],
            "premiere_vue": o["premiere_vue"], "active": o["derniere_vue"] == aujourd_hui,
            "statut": (s.get("statut") or "").strip(), "notes": (s.get("notes") or "").strip(),
            **note,
        })
    ordre = [scoring.VERDICT_POSTULER, scoring.VERDICT_ETUDIER, scoring.VERDICT_ECARTE]
    page.sort(key=lambda o: (ordre.index(o["verdict"]), -o["score"], o["titre"]))

    # La date ne bouge que si les offres changent : pas de commit toutes les 15 min pour rien
    precedent = charger_json(FICHIER_PAGE, {})
    if precedent.get("offres") != page:
        ecrire_json(FICHIER_PAGE, {
            "mise_a_jour": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "offres": page,
        })
    compte = {}
    for o in page:
        compte[o["verdict"]] = compte.get(o["verdict"], 0) + 1
    print("%d offres (%d nouvelles) : %s" % (len(page), nouvelles, compte))


if __name__ == "__main__":
    main()
