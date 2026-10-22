"""Récupère les offres depuis les API officielles et les met au même format.

- France Travail (API « Offres d'emploi v2 ») : variables FT_CLIENT_ID / FT_CLIENT_SECRET
- Adzuna (agrège Indeed, HelloWork, sites carrières...) : ADZUNA_APP_ID / ADZUNA_APP_KEY

Une source sans clés est ignorée : le tracker tourne avec l'une, l'autre ou les deux.
"""
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

TIMEOUT = 30


def _get_json(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as rep:
        if rep.status == 204:
            return {}
        return json.loads(rep.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# France Travail
# ---------------------------------------------------------------------------
FT_TOKEN_URL = ("https://entreprise.francetravail.fr/connexion/oauth2/access_token"
                "?realm=%2Fpartenaire")
FT_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def _ft_token(client_id, secret):
    corps = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": secret,
        "scope": "api_offresdemploiv2 o2dsoffre",
    }).encode()
    rep = _get_json(FT_TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, corps)
    return rep["access_token"]


def _ft_salaire(sal):
    texte = " ".join(v for v in (sal.get("libelle"), sal.get("commentaire"),
                                 sal.get("complement1"), sal.get("complement2")) if v)
    return texte


def _ft_normaliser(o):
    lieu = o.get("lieuTravail") or {}
    exp_code = o.get("experienceExige")  # D = débutant accepté, S = souhaitée, E = exigée
    exp_lib = o.get("experienceLibelle") or ""
    m = re.search(r"(\d+)\s*an", exp_lib.lower())
    annees = int(m.group(1)) if m else None
    if m is None:
        m = re.search(r"(\d+)\s*mois", exp_lib.lower())
        annees = int(m.group(1)) // 12 if m else None
    url = (o.get("origineOffre") or {}).get("urlOrigine") or \
        "https://candidat.francetravail.fr/offres/recherche/detail/" + o["id"]
    return {
        "id": "ft-" + o["id"],
        "source": "France Travail",
        "titre": o.get("intitule", ""),
        "entreprise": (o.get("entreprise") or {}).get("nom") or "Non communiqué",
        "lieu": lieu.get("libelle", ""),
        "description": o.get("description", ""),
        "url": url,
        "date": (o.get("dateCreation") or "")[:10],
        "contrat": o.get("typeContratLibelle") or o.get("typeContrat") or "",
        "salaire_texte": _ft_salaire(o.get("salaire") or {}),
        "salaire_min": None,
        "salaire_max": None,
        "experience_texte": exp_lib,
        "experience_annees": annees,
        "experience_debutant": exp_code == "D",
        "avantages_texte": " ".join(
            (o.get("salaire") or {}).get(k) or "" for k in ("complement1", "complement2")),
    }


def france_travail(recherche):
    client_id, secret = os.environ.get("FT_CLIENT_ID"), os.environ.get("FT_CLIENT_SECRET")
    if not (client_id and secret):
        print("France Travail : pas de clés, source ignorée", file=sys.stderr)
        return []
    token = _ft_token(client_id, secret)
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    offres = {}
    for mot in recherche["mots_cles"]:
        # L'API renvoie 150 offres max par appel et 1 150 au total : on parcourt les pages
        for debut in range(0, 1150, 150):
            params = urllib.parse.urlencode({
                "motsCles": mot,
                "commune": recherche["commune_insee"],
                "distance": recherche["rayon_km"],
                "range": "%d-%d" % (debut, min(debut + 149, 1149)),
                "sort": 1,
            })
            resultats = _get_json(FT_SEARCH_URL + "?" + params, headers).get("resultats", [])
            for o in resultats:
                offres[o["id"]] = _ft_normaliser(o)
            if len(resultats) < 150:
                break
    print("France Travail : %d offres" % len(offres), file=sys.stderr)
    return list(offres.values())


# ---------------------------------------------------------------------------
# Adzuna
# ---------------------------------------------------------------------------
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/%d"


def _az_normaliser(o):
    predit = bool(o.get("salary_is_predicted") and str(o["salary_is_predicted"]) != "0")
    return {
        "id": "az-" + str(o["id"]),
        "source": "Adzuna",
        "titre": re.sub(r"<[^>]+>", "", o.get("title", "")),
        "entreprise": (o.get("company") or {}).get("display_name") or "Non communiqué",
        "lieu": (o.get("location") or {}).get("display_name", ""),
        "description": re.sub(r"<[^>]+>", "", o.get("description", "")),
        "url": o.get("redirect_url", ""),
        "date": (o.get("created") or "")[:10],
        "contrat": " ".join(v for v in (o.get("contract_type"), o.get("contract_time")) if v),
        "salaire_texte": "",
        # Adzuna estime parfois le salaire : on ne garde que les salaires affichés
        "salaire_min": None if predit else o.get("salary_min"),
        "salaire_max": None if predit else o.get("salary_max"),
        "experience_texte": "",
        "experience_annees": None,
        "experience_debutant": False,
        "avantages_texte": "",
    }


def adzuna(recherche):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("Adzuna : pas de clés, source ignorée", file=sys.stderr)
        return []
    # Quota gratuit limité : Adzuna est interrogé toutes les 3 h (et à chaque lancement manuel)
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and datetime.datetime.now().hour % 3:
        print("Adzuna : pas cette heure-ci (quota)", file=sys.stderr)
        return []
    offres = {}
    for expression in recherche["adzuna_expressions"]:
        offres.update(_adzuna_expression(app_id, app_key, expression, recherche))
    print("Adzuna : %d offres" % len(offres), file=sys.stderr)
    return list(offres.values())


def _adzuna_expression(app_id, app_key, expression, recherche):
    offres = {}
    for page in (1, 2):
        params = urllib.parse.urlencode({
            "app_id": app_id,
            "app_key": app_key,
            "what_phrase": expression,
            "where": recherche["ville"],
            "distance": recherche["rayon_km"],
            "results_per_page": 50,
            "max_days_old": 14,
            "sort_by": "date",
            "content-type": "application/json",
        })
        rep = _get_json(ADZUNA_URL % page + "?" + params, {"Accept": "application/json"})
        resultats = rep.get("results", [])
        for o in resultats:
            offres[str(o["id"])] = _az_normaliser(o)
        if len(resultats) < 50:
            break
    return offres


SOURCES = [france_travail, adzuna]
