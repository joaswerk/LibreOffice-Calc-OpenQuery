# -*- coding: utf-8 -*-
"""0.2.5: Umbenennen -> Folgeschritte anpassen."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import engine as E


def tab():
    return E.Tabelle(["a", "b"], [[1, 2], [3, 4]])


class Umbenennen(unittest.TestCase):
    def folge(self):
        return [
            {"op": "benutzerdefinierte_spalte", "neu": "c", "formel": "[a] + [b]"},
            {"op": "sortieren", "spalte1": "a", "richtung1": "ab"},
            {"op": "bedingte_spalte", "neu": "d", "klauseln": [{"verknuepfung": "und", "bedingungen": [
                {"spalte": "a", "bedingung": "gleich", "wert_art": "spalte", "wert": "b"}],
                "dann_art": "formel", "dann": "[a]*2"}], "sonst_art": "spalte", "sonst": "a"},
            {"op": "gruppieren", "spalten": ["a"], "aggregationen": [{"fn": "summe", "spalte": "b"}]},
        ]

    def test_bestehender_schritt_geaendert(self):
        # a war schon in x umbenannt, jetzt heißt es y
        schritte = [{"op": "spalte_umbenennen", "spalte": "a", "neu": "y"}]
        folge = self.folge()
        for s in folge:
            E.ersetze_spaltenname_im_schritt(s, "a", "x")      # Ausgangslage: Folgeschritte nutzen "x"
        schritte += folge
        tab_nach = E.fuehre_aus(tab(), schritte[:1])
        n = E.folge_schritte_anpassen(schritte, 1, "x", "y", tab_nach)
        self.assertEqual(n, 4)
        self.assertEqual(schritte[1]["formel"], "[y] + [b]")
        self.assertEqual(schritte[2]["spalte1"], "y")
        kl = schritte[3]["klauseln"][0]
        self.assertEqual(kl["bedingungen"][0]["spalte"], "y")
        self.assertEqual(kl["dann"], "[y]*2")
        self.assertEqual(schritte[3]["sonst"], "y")
        self.assertEqual(schritte[4]["spalten"], ["y"])
        E.fuehre_aus(tab(), schritte)

    def test_neuer_schritt_vorne(self):
        schritte = self.folge()
        neu = {"op": "spalte_umbenennen", "spalte": "a", "neu": "menge"}
        schritte.insert(0, neu)
        vor = tab()
        nach = E.fuehre_aus(vor, [neu])
        E.folge_schritte_anpassen(schritte, 1, "a", "menge", nach)
        E.fuehre_aus(tab(), schritte)         # läuft ohne Fehler durch
        self.assertEqual(schritte[1]["formel"], "[menge] + [b]")

    def test_stopp_bei_neuer_spalte_gleichen_namens(self):
        schritte = [
            {"op": "spalte_umbenennen", "spalte": "a", "neu": "menge"},
            {"op": "benutzerdefinierte_spalte", "neu": "a", "formel": "[b] * 10"},     # neue Spalte "a"
            {"op": "sortieren", "spalte1": "a", "richtung1": "auf"},                   # meint die neue Spalte
        ]
        nach = E.fuehre_aus(tab(), schritte[:1])
        E.folge_schritte_anpassen(schritte, 1, "a", "menge", nach)
        self.assertEqual(schritte[2]["spalte1"], "a")

    def test_stopp_wenn_spalte_entfernt(self):
        schritte = [
            {"op": "spalte_umbenennen", "spalte": "a", "neu": "menge"},
            {"op": "spalten_entfernen", "spalten": ["menge"]},
            {"op": "benutzerdefinierte_spalte", "neu": "q", "formel": "[b]"},
        ]
        nach = E.fuehre_aus(tab(), schritte[:1])
        E.folge_schritte_anpassen(schritte, 1, "a", "menge", nach)
        E.fuehre_aus(tab(), schritte)

    def test_mehrfach_umbenennen_text(self):
        s = {"op": "spalten_umbenennen", "umbenennungen": "a = x\nb = y"}
        self.assertEqual(E.umbenennungen_von(s), [("a", "x"), ("b", "y")])
        s2 = {"op": "spalten_umbenennen", "umbenennungen": "a = x\nb = y"}
        E.ersetze_spaltenname_im_schritt(s2, "a", "q")
        self.assertEqual(s2["umbenennungen"], "q = x\nb = y")

    def test_einzelnes_umbenennen_paar(self):
        self.assertEqual(E.umbenennungen_von({"op": "spalte_umbenennen", "spalte": "a", "neu": "z"}), [("a", "z")])

    def test_inaktiver_schritt_wird_trotzdem_angepasst(self):
        schritte = [{"op": "spalte_umbenennen", "spalte": "a", "neu": "m"},
                    {"op": "sortieren", "spalte1": "a", "richtung1": "auf", "aktiv": False}]
        nach = E.fuehre_aus(tab(), schritte[:1])
        E.folge_schritte_anpassen(schritte, 1, "a", "m", nach)
        self.assertEqual(schritte[1]["spalte1"], "m")


if __name__ == "__main__":
    unittest.main()
