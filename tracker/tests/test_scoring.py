"""Tests du scoring : python3 -m unittest discover tracker/tests"""
import json
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))

import scoring  # noqa: E402

with open(os.path.join(os.path.dirname(ICI), "criteres.json"), encoding="utf-8") as f:
    CRITERES = json.load(f)
with open(os.path.join(ICI, "exemple.json"), encoding="utf-8") as f:
    OFFRES = {o["id"]: o for o in json.load(f)}


class TestSalaire(unittest.TestCase):
    def test_france_travail_annuel(self):
        self.assertEqual(scoring.extraire_salaire("Annuel de 38000,00 Euros à 45000,00 Euros"),
                         (38000, 45000))

    def test_france_travail_mensuel(self):
        self.assertEqual(scoring.extraire_salaire("Mensuel de 3200,00 Euros sur 13,00 mois"),
                         (41600, 41600))

    def test_k_euros(self):
        self.assertEqual(scoring.extraire_salaire("Rémunération : 38-42 k€ fixe"), (38000, 42000))
        self.assertEqual(scoring.extraire_salaire("Salaire 38k€ - 42k€"), (38000, 42000))

    def test_espaces(self):
        self.assertEqual(scoring.extraire_salaire("Salaire de 40 000 € brut annuel"), (40000, 40000))

    def test_ignore_chiffre_affaires(self):
        self.assertEqual(scoring.extraire_salaire("Groupe de 500 M€ de chiffre d'affaires"),
                         (None, None))


class TestExperience(unittest.TestCase):
    def test_fourchette(self):
        self.assertEqual(scoring.extraire_experience("4 à 6 ans d'expérience"), 4)

    def test_minimum(self):
        self.assertEqual(scoring.extraire_experience("Expérience de 5 ans minimum"), 5)


class TestVerdicts(unittest.TestCase):
    def verdict(self, id_):
        return scoring.noter(OFFRES[id_], CRITERES)

    def test_offre_ideale(self):
        n = self.verdict("test-1")
        self.assertEqual(n["verdict"], scoring.VERDICT_POSTULER, n)

    def test_sans_infos_a_etudier(self):
        n = self.verdict("test-2")
        self.assertEqual(n["verdict"], scoring.VERDICT_ETUDIER, n)

    def test_junior_ecarte(self):
        n = self.verdict("test-3")
        self.assertEqual(n["verdict"], scoring.VERDICT_ECARTE)
        self.assertTrue(any("junior" in d.lower() for d in n["drapeaux"]))

    def test_comptable_ecarte(self):
        n = self.verdict("test-4")
        self.assertEqual(n["verdict"], scoring.VERDICT_ECARTE)
        self.assertTrue(any("comptabilité" in d for d in n["drapeaux"]))

    def test_pas_de_teletravail_ecarte(self):
        n = self.verdict("test-5")
        self.assertIn("Pas de télétravail", n["drapeaux"])


if __name__ == "__main__":
    unittest.main()
