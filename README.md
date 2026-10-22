# Tracker d'offres : contrôleur de gestion à Bordeaux

Toutes les heures, GitHub Actions cherche les offres de contrôleur de gestion autour de Bordeaux,
les note selon les critères de recherche, puis publie le résultat sur une page GitHub Pages.

## Critères (`tracker/criteres.json`)

| Critère | Effet |
|---|---|
| Bordeaux Sud (Bègles, Talence, Pessac…) | +15 |
| Reste de Bordeaux Métropole | +8 |
| Salaire ≥ 40 k€ | +20 (≥ 38 k€ : +8) |
| Télétravail mentionné | +15 |
| 3 à 7 ans d'expérience demandés | +10 |
| Avantages (tickets resto, mutuelle, RTT…) | jusqu'à +10 |
| Part variable | +3 |

**Red flags → offre « Écartée »** : poste en comptabilité, poste junior / stage / alternance /
débutant accepté, salaire maximum sous 38 k€, pas de télétravail.

Note ≥ 75 et aucun red flag → **À postuler** ; sinon → **À étudier**.

## Suivre ses candidatures (`data/suivi.csv`)

Sur github.com, ouvre `data/suivi.csv`, clique sur le crayon et ajoute une ligne par offre
(l'`id` est affiché sur chaque carte de la page) :

```
id;statut;notes
ft-123ABCD;Postulé;Envoyé le 22/10, relancer le 05/11
az-4567890;Entretien;RH le 30/10 à 14h
```

La page se met à jour quelques minutes après l'enregistrement.

## Mise en route

1. **Clés API** (gratuites) :
   - France Travail : créer un compte sur [francetravail.io](https://francetravail.io),
     créer une application et l'abonner à l'API **« Offres d'emploi v2 »**.
     On obtient un *client id* et un *client secret*.
   - Adzuna (optionnel, couvre Indeed, HelloWork, sites carrières…) :
     [developer.adzuna.com](https://developer.adzuna.com), on obtient un *app id* et une *app key*.
2. **Secrets GitHub** : dans le dépôt, Settings → Secrets and variables → Actions →
   New repository secret : `FT_CLIENT_ID`, `FT_CLIENT_SECRET`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.
3. **Page** : Settings → Pages → Source « Deploy from a branch », branche `main`, dossier `/docs`.
4. **Premier lancement** : onglet Actions → « Tracker offres » → Run workflow.

## En local

```bash
python3 -m unittest discover tracker/tests
python3 tracker/run.py --fixture tracker/tests/exemple.json   # sans clés, offres de test
```
