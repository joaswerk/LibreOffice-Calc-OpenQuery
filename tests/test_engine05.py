# -*- coding: utf-8 -*-
"""0.2.6: Tabellen verbinden (Join) und anfügen (Append)."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import engine as E

LINKS = lambda: E.Tabelle(["Jahr", "Monat", "Menge"], [[2025, 1, 10], [2025, 2, 20], [2026, 1, 30], [2026, 3, 40]])
RECHTS = lambda: E.Tabelle(["J", "M", "Preis"], [[2025, 1, 1.5], [2026, 1, 2.5], [2027, 1, 9.0], [2025, 2, 1.7]])


def lauf(tab, *schritte):
    return E.fuehre_aus(tab, list(schritte))


class Join(unittest.TestCase):
    def setUp(self):
        E.AUFLOESER["fn"] = lambda n: {"R": RECHTS(), "L2": LINKS()}[n]

    def tearDown(self):
        E.AUFLOESER["fn"] = None

    def schritt(self, join, **kw):
        d = {"op": "tabellen_verbinden", "abfrage": "R", "join": join,
             "schluessel": [{"links": "Jahr", "rechts": "J"}, {"links": "Monat", "rechts": "M"}]}
        d.update(kw)
        return d

    def test_links_mehrspaltig(self):
        r = lauf(LINKS(), self.schritt("links"))
        self.assertEqual(r.spalten, ["Jahr", "Monat", "Menge", "Preis"])
        self.assertEqual([z[3] for z in r.zeilen], [1.5, 1.7, 2.5, None])

    def test_innen(self):
        r = lauf(LINKS(), self.schritt("innen"))
        self.assertEqual([z[:3] for z in r.zeilen], [[2025, 1, 10], [2025, 2, 20], [2026, 1, 30]])

    def test_voll_schluessel_aus_rechter_seite(self):
        r = lauf(LINKS(), self.schritt("voll"))
        self.assertEqual(len(r.zeilen), 5)
        self.assertEqual(r.zeilen[-1], [2027, 1, None, 9.0])

    def test_rechts(self):
        r = lauf(LINKS(), self.schritt("rechts"))
        self.assertEqual([z[3] for z in r.zeilen], [1.5, 2.5, 9.0, 1.7])
        self.assertEqual(r.zeilen[2], [2027, 1, None, 9.0])

    def test_anti_links(self):
        r = lauf(LINKS(), self.schritt("anti_links"))
        self.assertEqual(r.spalten, ["Jahr", "Monat", "Menge"])
        self.assertEqual(r.zeilen, [[2026, 3, 40]])

    def test_anti_rechts(self):
        r = lauf(LINKS(), self.schritt("anti_rechts"))
        self.assertEqual(r.spalten, ["J", "M", "Preis"])
        self.assertEqual(r.zeilen, [[2027, 1, 9.0]])

    def test_kreuz(self):
        r = lauf(E.Tabelle(["a"], [[1], [2]]), {"op": "tabellen_verbinden", "abfrage": "R", "join": "kreuz",
                                                  "spalten_rechts": ["Preis"]})
        self.assertEqual(len(r.zeilen), 8)
        self.assertEqual(r.spalten, ["a", "Preis"])

    def test_praefix_und_spaltenauswahl(self):
        r = lauf(LINKS(), self.schritt("links", spalten_rechts=["Preis"], praefix="R."))
        self.assertEqual(r.spalten, ["Jahr", "Monat", "Menge", "R.Preis"])

    def test_namenskonflikt(self):
        t = E.Tabelle(["J", "Preis"], [[2025, 1]])
        r = lauf(t, {"op": "tabellen_verbinden", "abfrage": "R", "join": "links",
                     "schluessel": [{"links": "J", "rechts": "J"}]})
        self.assertEqual(r.spalten, ["J", "Preis", "M", "Preis.1"])

    def test_ohne_schluessel_fehler(self):
        with self.assertRaises(E.StepError):
            lauf(LINKS(), {"op": "tabellen_verbinden", "abfrage": "R", "join": "links", "schluessel": []})

    def test_unbekannte_spalte_fehler(self):
        with self.assertRaises(E.StepError):
            lauf(LINKS(), self.schritt("links", schluessel=[{"links": "gibtsnicht", "rechts": "J"}]))

    def test_umbenennen_folgt_in_schluessel(self):
        st = self.schritt("links")
        E.ersetze_spaltenname_im_schritt(st, "Jahr", "Year")
        self.assertEqual(st["schluessel"][0]["links"], "Year")
        self.assertEqual(st["schluessel"][0]["rechts"], "J")

    def test_beschreibung(self):
        self.assertIn("Jahr = J", E.beschreibe(self.schritt("links")))


class Anfuegen(unittest.TestCase):
    def setUp(self):
        E.AUFLOESER["fn"] = lambda n: {"B": E.Tabelle(["menge", "Extra"], [[5, "x"]]),
                                       "C": E.Tabelle(["A", "B"], [[1, 2]])}[n]

    def tearDown(self):
        E.AUFLOESER["fn"] = None

    def test_nach_namen(self):
        t = E.Tabelle(["Menge", "Ort"], [[1, "a"]])
        r = lauf(t, {"op": "tabellen_anfuegen", "abfragen": ["B"], "ausrichtung": "name"})
        self.assertEqual(r.spalten, ["Menge", "Ort", "Extra"])
        self.assertEqual(r.zeilen, [[1, "a", None], [5, None, "x"]])

    def test_nach_position(self):
        t = E.Tabelle(["x", "y"], [[1, 2]])
        r = lauf(t, {"op": "tabellen_anfuegen", "abfragen": ["C"], "ausrichtung": "position"})
        self.assertEqual(r.spalten, ["x", "y"])
        self.assertEqual(r.zeilen, [[1, 2], [1, 2]])

    def test_position_mit_mehr_spalten(self):
        t = E.Tabelle(["x"], [[1]])
        r = lauf(t, {"op": "tabellen_anfuegen", "abfragen": ["C"], "ausrichtung": "position"})
        self.assertEqual(r.spalten, ["x", "B"])
        self.assertEqual(r.zeilen, [[1, None], [1, 2]])

    def test_herkunft(self):
        t = E.Tabelle(["Menge"], [[1]])
        r = lauf(t, {"op": "tabellen_anfuegen", "abfragen": ["B", "C"], "herkunft": "Quelle",
                     "herkunft_eigen": "Basis"})
        self.assertEqual(r.spalten[-1], "Quelle")
        self.assertEqual([z[-1] for z in r.zeilen], ["Basis", "B", "C"])

    def test_mehrere_tabellen_und_gross_klein(self):
        t = E.Tabelle(["MENGE"], [[1]])
        r = lauf(t, {"op": "tabellen_anfuegen", "abfragen": ["B"]})
        self.assertEqual(r.spalten, ["MENGE", "Extra"])
        self.assertEqual(r.zeilen[1][0], 5)

    def test_ohne_tabelle_fehler(self):
        with self.assertRaises(E.StepError):
            lauf(E.Tabelle(["a"], [[1]]), {"op": "tabellen_anfuegen", "abfragen": []})

    def test_ohne_aufloeser(self):
        E.AUFLOESER["fn"] = None
        with self.assertRaises(E.StepError):
            lauf(E.Tabelle(["a"], [[1]]), {"op": "tabellen_anfuegen", "abfragen": ["B"]})


class Qualitaet(unittest.TestCase):
    def test_zahlenspalte_mit_ausreisser(self):
        self.assertEqual(E.spalten_qualitaet(["1", "2,5", "n/a", "", "4"]), (0, 1))

    def test_echte_textspalte(self):
        self.assertEqual(E.spalten_qualitaet(["a", "b", "c"]), (0, 0))

    def test_datumsspalte(self):
        self.assertEqual(E.spalten_qualitaet(["01.10.2026", "x", "02.10.2026"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
