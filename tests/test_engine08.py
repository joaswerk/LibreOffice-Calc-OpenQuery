import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import engine as E


class V070(unittest.TestCase):
    def setUp(self):
        self.t = E.Tabelle(["Text", "Wert"], [["a\nb", 1], ["c\nd\ne", 2], ["ohne", 3]])

    def test_extrahieren_vor_lf(self):
        r = E.wende_schritt(self.t, {"op": "text_extrahieren", "spalte": "Text", "art": "vor_trenner", "trenner": "#(lf)"})
        self.assertEqual([z[0] for z in r.zeilen], ["a", "c", None])

    def test_extrahieren_nach_lf_gross(self):
        r = E.wende_schritt(self.t, {"op": "text_extrahieren", "spalte": "Text", "art": "nach_trenner", "trenner": "#(LF)"})
        self.assertEqual([z[0] for z in r.zeilen], ["b", "d\ne", None])

    def test_zwischen_zwei_trennern(self):
        r = E.wende_schritt(self.t, {"op": "text_extrahieren", "spalte": "Text", "art": "zwischen_trennern",
                                     "trenner": "#(lf)", "trenner2": "#(lf)", "vorkommen": "erstes"})
        self.assertEqual(r.zeilen[1][0], "d")

    def test_teilen_lf(self):
        r = E.wende_schritt(self.t, {"op": "spalte_teilen", "spalte": "Text", "modus": "trenner", "trenner": "#(lf)"})
        self.assertEqual(len(r.spalten), 4)
        self.assertEqual(r.zeilen[1][0:3], ["c", "d", "e"])

    def test_ersetzen_lf(self):
        r = E.wende_schritt(self.t, {"op": "ersetzen", "spalte": "Text", "suchen": "#(lf)", "ersetzen_durch": " / ",
                                     "ganze_zelle": False})
        self.assertEqual(r.zeilen[0][0], "a / b")

    def test_zusammenfuehren_lf_tab(self):
        r = E.wende_schritt(self.t, {"op": "spalten_zusammenfuehren", "spalten": ["Text", "Wert"], "trenner": "#(tab)",
                                     "neu": "X", "quellen_behalten": False})
        self.assertEqual(r.zeilen[2][0], "ohne\t3")

    def test_normales_trennzeichen_unveraendert(self):
        r = E.wende_schritt(E.Tabelle(["A"], [["x#y"]]), {"op": "text_extrahieren", "spalte": "A", "art": "vor_trenner", "trenner": "#"})
        self.assertEqual(r.zeilen[0][0], "x")

    def test_doppelte_beibehalten(self):
        t = E.Tabelle(["A", "B"], [["x", 1], ["y", 2], ["x", 3], ["z", 4], ["y", 5]])
        r = E.wende_schritt(t, {"op": "duplikate_behalten", "spalten": ["A"]})
        self.assertEqual([z[1] for z in r.zeilen], [1, 2, 3, 5])
        r2 = E.wende_schritt(t, {"op": "duplikate_behalten", "spalten": []})
        self.assertEqual(r2.zeilen, [])


if __name__ == "__main__":
    unittest.main(verbosity=0)
