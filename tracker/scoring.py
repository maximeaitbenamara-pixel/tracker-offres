"""Note chaque offre selon les critères de Job.docx (voir criteres.json).

Une offre normalisée est un dict avec au moins :
  titre, entreprise, lieu, description, contrat,
  salaire_texte, salaire_min, salaire_max (annuels, en euros, ou None),
  experience_texte, experience_annees (ou None), experience_debutant (bool)
"""
import re
import unicodedata

VERDICT_POSTULER = "À postuler"
VERDICT_ETUDIER = "À étudier"
VERDICT_ECARTE = "Écarté"


def normaliser(texte):
    """Minuscules, apostrophes droites, espaces simples (les accents sont gardés)."""
    texte = unicodedata.normalize("NFC", texte or "")
    texte = texte.replace("’", "'").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", texte.lower())


def contient(texte, mots):
    """Renvoie les mots-clés trouvés dans le texte (mots entiers)."""
    trouves = []
    for mot in mots:
        motif = r"(?<![\w])" + re.escape(mot.strip().lower()) + r"(?![\w])"
        if re.search(motif, texte):
            trouves.append(mot.strip())
    return trouves


# ---------------------------------------------------------------------------
# Salaire
# ---------------------------------------------------------------------------
MOTS_SALAIRE = ("salaire", "rémunération", "remuneration", "package", "brut", "k€",
                "€/an", "euros", "€ par an", "fixe", "annuel", "mensuel")

_MONTANT = re.compile(
    r"(?P<val>\d{1,3}(?:[ .]\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<k>k)?\s*(?P<eur>€|euros?|eur\b)?",
    re.IGNORECASE,
)


def _montants(phrase):
    """Extrait les montants annuels plausibles (20 k€ - 120 k€) d'une phrase."""
    mensuel = re.search(r"mensuel|par mois|/ ?mois", phrase)
    mois = re.search(r"sur (\d{2})(?:[.,]0+)? mois", phrase)
    nb_mois = int(mois.group(1)) if mois else 12
    valeurs = []
    for m in _MONTANT.finditer(phrase):
        if not (m.group("k") or m.group("eur")):
            continue
        brut = m.group("val").replace(" ", "")
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", brut):
            brut = brut.replace(".", "")
        try:
            v = float(brut.replace(",", "."))
        except ValueError:
            continue
        if m.group("k"):
            v *= 1000
        if mensuel and 1500 <= v <= 9000:
            v *= nb_mois
        if 20000 <= v <= 120000:
            valeurs.append(v)
    return valeurs


def extraire_salaire(texte):
    """(min, max) annuels trouvés dans les phrases qui parlent de salaire."""
    texte = normaliser(texte)
    # « 38-42 k€ » / « 38 à 42k » : le k s'applique aux deux bornes
    texte = re.sub(r"(\d+)\s*(-|à)\s*(\d+)\s*k", r"\1k \2 \3k", texte)
    valeurs = []
    for phrase in re.split(r"[\n.;!?]\s|\s-\s|\|", texte):
        if any(mot in phrase for mot in MOTS_SALAIRE):
            valeurs += _montants(phrase)
    if not valeurs:
        return None, None
    return min(valeurs), max(valeurs)


# ---------------------------------------------------------------------------
# Expérience
# ---------------------------------------------------------------------------
def extraire_experience(texte):
    """Nombre d'années d'expérience demandé (le minimum s'il y a une fourchette)."""
    texte = normaliser(texte)
    motifs = [
        r"(\d{1,2})\s*(?:à|-|/)\s*\d{1,2}\s*ans?\s*(?:minimum\s*)?d'exp",
        r"(\d{1,2})\s*ans?\s*(?:minimum\s*)?(?:d'|de |en )?exp",
        r"exp[ée]rience\s*(?:significative\s*|réussie\s*|minimum\s*|similaire\s*)?(?:de|d'au moins|minimum)\s*(\d{1,2})\s*ans",
        r"(\d{1,2})\s*an\(s\)",
    ]
    for motif in motifs:
        m = re.search(motif, texte)
        if m:
            return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Note finale
# ---------------------------------------------------------------------------
def noter(offre, criteres):
    titre = normaliser(offre.get("titre"))
    lieu = normaliser(offre.get("lieu"))
    tout = " ".join(normaliser(offre.get(k)) for k in
                    ("titre", "description", "salaire_texte", "experience_texte", "avantages_texte"))

    score = 50
    plus, moins, drapeaux = [], [], []

    # --- Intitulé : hors cible / stage / junior / comptabilité = red flags -
    if not any(m in titre for m in criteres["intitule_cible"]):
        drapeaux.append("Intitulé hors contrôle de gestion")
    exclus = contient(titre, criteres["exclusions_intitule"])
    if exclus:
        drapeaux.append("Poste junior / stage / alternance (" + ", ".join(exclus) + ")")
    contrat = normaliser(offre.get("contrat"))
    if any(c in contrat for c in ("stage", "alternance", "apprentissage")):
        drapeaux.append("Contrat " + offre.get("contrat"))
    compta = contient(titre, criteres["metiers_comptables"])
    if compta and "contrôl" not in titre and "control" not in titre:
        drapeaux.append("Poste en comptabilité (" + ", ".join(compta) + ")")

    # --- Localisation : idéalement Bordeaux Sud ---------------------------
    loc = criteres["localisation"]
    if contient(lieu, loc["bordeaux_sud"]):
        score += 15
        plus.append("Bordeaux Sud")
    elif contient(lieu, loc["bordeaux_metropole"]):
        score += 8
        plus.append("Bordeaux Métropole")
    else:
        moins.append("Hors métropole bordelaise")

    # --- Salaire : 38 k€ minimum, 40 k€ souhaité --------------------------
    smin, smax = offre.get("salaire_min"), offre.get("salaire_max")
    if smin is None and smax is None:
        smin, smax = extraire_salaire(" | ".join(
            str(offre.get(k) or "") for k in ("salaire_texte", "description")))
    s_cfg = criteres["salaire"]
    if smax is not None and smax < s_cfg["minimum_annuel"]:
        drapeaux.append("Salaire sous 38 k€ (max %d k€)" % (smax / 1000))
    elif smin is not None and smin >= s_cfg["souhaite_annuel"]:
        score += 20
        plus.append("Salaire ≥ 40 k€")
    elif smax is not None and smax >= s_cfg["souhaite_annuel"]:
        score += 12
        plus.append("Fourchette jusqu'à %d k€" % (smax / 1000))
    elif smin is not None and smin >= s_cfg["minimum_annuel"]:
        score += 8
        plus.append("Salaire ≥ 38 k€")
    elif smin is not None:
        score -= 10
        moins.append("Salaire en bas de fourchette (%d k€)" % (smin / 1000))
    else:
        moins.append("Salaire non précisé")

    # --- Télétravail -------------------------------------------------------
    if contient(tout, criteres["teletravail_non"]):
        drapeaux.append("Pas de télétravail")
    elif contient(tout, criteres["teletravail_oui"]):
        score += 15
        plus.append("Télétravail mentionné")
    else:
        moins.append("Télétravail non mentionné")

    # --- Expérience : 4-5 ans ----------------------------------------------
    annees = offre.get("experience_annees")
    if annees is None:
        annees = extraire_experience(" ".join((offre.get("experience_texte") or "",
                                               offre.get("description") or "")))
    e_cfg = criteres["experience"]
    if offre.get("experience_debutant"):
        drapeaux.append("Débutant accepté (poste junior)")
    elif annees is not None and annees < 2:
        drapeaux.append("Poste junior (%d an demandé)" % annees)
    elif annees is not None and e_cfg["annees_min_ideal"] <= annees <= e_cfg["annees_max_ideal"]:
        score += 10
        plus.append("Expérience demandée : %d ans" % annees)
    elif annees is not None and annees > e_cfg["annees_max_ideal"]:
        score -= 5
        moins.append("Profil plus senior (%d ans)" % annees)
    elif annees is not None:
        moins.append("Expérience demandée : %d ans" % annees)

    # --- Avantages et variable ----------------------------------------------
    avantages = contient(tout, criteres["avantages"])
    if avantages:
        score += min(10, 4 * len(avantages))
        plus.append("Avantages : " + ", ".join(avantages[:4]))
    if contient(tout, criteres["variable"]):
        score += 3
        plus.append("Part variable")

    score = max(0, min(100, score))
    if drapeaux:
        verdict = VERDICT_ECARTE
    elif score >= criteres["seuils"]["a_postuler"]:
        verdict = VERDICT_POSTULER
    else:
        verdict = VERDICT_ETUDIER

    return {
        "score": score,
        "verdict": verdict,
        "plus": plus,
        "moins": moins,
        "drapeaux": drapeaux,
        "salaire_min": smin,
        "salaire_max": smax,
    }
