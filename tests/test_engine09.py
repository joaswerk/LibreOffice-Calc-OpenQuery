import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import engine as E


class V088(unittest.TestCase):
    def setUp(self):
        self.t = E.Tabelle(["A", "B"], [[1.2345, 50.0], [2.5, 25.0], [None, 10.0]])

    def test_gruppe_heisst_standardoperationen(self):
        self.assertIn("Standardoperationen", E.GRUPPEN)
        self.assertNotIn("Zahlen", E.GRUPPEN)
        self.assertEqual(E.OPS["runden"]["gruppe"], "Standardoperationen")
        self.assertEqual(E.OPS["rechnen"]["gruppe"], "Standardoperationen")

    def test_prozent_von_setzt_typ_prozent(self):
        r = E.wende_schritt(self.t, {"op": "rechnen", "spalten": ["B"], "rechenart": "prozent_von", "operand_art": "wert", "operand": "200"})
        self.assertTrue(all(isinstance(z[1], E.Prozent) for z in r.zeilen), [type(z[1]) for z in r.zeilen])
        self.assertAlmostEqual(float(r.zeilen[0][1]), 0.25)

    def test_runden_echt_und_anzeige(self):
        r = E.wende_schritt(self.t, {"op": "runden", "spalten": ["A"], "modus": "halb", "stellen": 1})
        self.assertEqual([z[0] for z in r.zeilen], [1.2, 2.5, None])
        r = E.wende_schritt(self.t, {"op": "runden", "spalten": ["A"], "modus": "halb", "stellen": 1, "nur_anzeige": True})
        self.assertAlmostEqual(float(r.zeilen[0][0]), 1.2345)
        self.assertEqual(r.zeilen[0][0].stellen, 1)
        self.assertEqual(E.als_text(r.zeilen[0][0]), "1,2")

    def test_reihenfolge_zeilen_menue(self):
        z = [op for op, _ in E.ops_der_gruppe("Zeilen")]
        self.assertEqual(z[:2], ["erste_zeile_als_kopf", "kopf_als_erste_zeile"])

    def test_typ_dezimal_mit_stellen(self):
        r = E.wende_schritt(self.t, {"op": "typ_aendern", "spalten": ["A"], "typ": "dezimal", "stellen": "2"})
        self.assertEqual(r.zeilen[0][0], 1.23)


if __name__ == "__main__":
    unittest.main()
