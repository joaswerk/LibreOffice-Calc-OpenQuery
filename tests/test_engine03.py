# -*- coding: utf-8 -*-
"""Tests für 0.2.1: Ausfüllen (unten/oben) und die neue bedingte Spalte."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import engine as E  # noqa: E402


def T(spalten, zeilen):
    return E.Tabelle(spalten, zeilen)


def lauf(tab, *schritte):
    return E.fuehre_aus(tab, list(schritte))


class Ausfuellen(unittest.TestCase):
    def test_unten_mit_mehreren_leeren_nacheinander(self):
        t = T(["a"], [["x"], [None], [""], ["  "], ["y"], [None]])
        r = lauf(t, {"op": "fuellen_unten", "spalten": ["a"]})
        self.assertEqual([z[0] for z in r.zeilen], ["x", "x", "x", "x", "y", "y"])

    def test_unten_fuehrende_leere_bleiben_leer(self):
        t = T(["a"], [[None], [""], ["x"], [None]])
        r = lauf(t, {"op": "fuellen_unten", "spalten": ["a"]})
        self.assertEqual([z[0] for z in r.zeilen], [None, "", "x", "x"])

    def test_oben_mit_mehreren_leeren_nacheinander(self):
        t = T(["a"], [[None], [""], ["x"], [None], ["y"], [None]])
        r = lauf(t, {"op": "fuellen_oben", "spalten": ["a"]})
        self.assertEqual([z[0] for z in r.zeilen], ["x", "x", "x", "y", "y", None])

    def test_oben_abschliessende_leere_bleiben_leer(self):
        t = T(["a"], [["x"], [None], [None]])
        r = lauf(t, {"op": "fuellen_oben", "spalten": ["a"]})
        self.assertEqual([z[0] for z in r.zeilen], ["x", None, None])

    def test_zahlen_und_nullen(self):
        t = T(["a"], [[5], [None], [0], [None], [2.5], [None]])
        r = lauf(t, {"op": "fuellen_unten", "spalten": ["a"]})
        self.assertEqual([z[0] for z in r.zeilen], [5, 5, 0, 0, 2.5, 2.5])     # 0 ist ein gültiger Wert
        r = lauf(t, {"op": "fuellen_oben", "spalten": ["a"]})
        self.assertEqual([z[0] for z in r.zeilen], [5, 0, 0, 2.5, 2.5, None])

    def test_nur_gewaehlte_spalte_und_original_unveraendert(self):
        t = T(["a", "b"], [["x", 1], [None, None], ["y", None]])
        r = lauf(t, {"op": "fuellen_unten", "spalten": ["a"]})
        self.assertEqual([z[1] for z in r.zeilen], [1, None, None])
        self.assertIsNone(t.zeilen[1][0])

    def test_json_und_gruppe(self):
        for op in ("fuellen_unten", "fuellen_oben"):
            self.assertEqual(E.OPS[op]["gruppe"], "Spalten")
        a = E.Abfrage("x", {"art": "blatt"}, [{"op": "fuellen_oben", "spalten": ["a"]}])
        b = E.Abfrage.from_json(a.to_json())
        self.assertEqual(b.schritte, [{"op": "fuellen_oben", "spalten": ["a"]}])


DATEN = lambda: T(["Name", "Menge", "Budget", "Art"], [
    ["A", 10, 5, "x"], ["B", 3, 5, "y"], ["C", 5, 5, ""], ["D", None, 5, "x"], ["E", 8, 20, "z"]])


def klausel(bed, dann, dann_art="text", verk="und"):
    return {"verknuepfung": verk, "bedingungen": bed, "dann_art": dann_art, "dann": dann}


def b(spalte, bedingung, wert="", art="text"):
    return {"spalte": spalte, "bedingung": bedingung, "wert_art": art, "wert": wert}


class Bedingt(unittest.TestCase):
    def test_kette_wenn_sonst_wenn_sonst(self):
        r = lauf(DATEN(), {"op": "bedingte_spalte", "neu": "Stufe", "klauseln": [
            klausel([b("Menge", "groesser", "8")], "hoch"),
            klausel([b("Menge", "groesser", "4")], "mittel")], "sonst_art": "text", "sonst": "niedrig"})
        self.assertEqual([z[-1] for z in r.zeilen], ["hoch", "niedrig", "mittel", "niedrig", "mittel"])

    def test_wert_aus_spalte_ist_zellwert_nicht_name(self):
        r = lauf(DATEN(), {"op": "bedingte_spalte", "neu": "Ueber", "klauseln": [
            klausel([b("Menge", "groesser", "Budget", "spalte")], "ja")], "sonst_art": "text", "sonst": "nein"})
        self.assertEqual([z[-1] for z in r.zeilen], ["ja", "nein", "nein", "nein", "nein"])

    def test_ausgabe_spalte_und_formel(self):
        r = lauf(DATEN(), {"op": "bedingte_spalte", "neu": "X", "klauseln": [
            klausel([b("Art", "gleich", "x")], "Name", "spalte"),
            klausel([b("Art", "gleich", "y")], "[Menge] * 2", "formel")],
            "sonst_art": "formel", "sonst": "[Budget] + 1"})
        self.assertEqual([z[-1] for z in r.zeilen], ["A", 6, 6, "D", 21])

    def test_und_und_oder(self):
        k_und = klausel([b("Art", "gleich", "x"), b("Menge", "groesser", "5")], "tr", verk="und")
        r = lauf(DATEN(), {"op": "bedingte_spalte", "neu": "U", "klauseln": [k_und], "sonst_art": "text", "sonst": "fa"})
        self.assertEqual([z[-1] for z in r.zeilen], ["tr", "fa", "fa", "fa", "fa"])
        k_oder = klausel([b("Art", "gleich", "x"), b("Menge", "groesser", "7")], "tr", verk="oder")
        r = lauf(DATEN(), {"op": "bedingte_spalte", "neu": "O", "klauseln": [k_oder], "sonst_art": "text", "sonst": "fa"})
        self.assertEqual([z[-1] for z in r.zeilen], ["tr", "fa", "fa", "tr", "tr"])

    def test_operator_ohne_wert(self):
        r = lauf(DATEN(), {"op": "bedingte_spalte", "neu": "L", "klauseln": [
            klausel([b("Art", "leer")], "leer")], "sonst_art": "text", "sonst": "voll"})
        self.assertEqual([z[-1] for z in r.zeilen], ["voll", "voll", "leer", "voll", "voll"])

    def test_vergleich_mit_formelwert(self):
        r = lauf(DATEN(), {"op": "bedingte_spalte", "neu": "F", "klauseln": [
            klausel([b("Menge", "groesser_gleich", "[Budget] * 2", "formel")], "viel")],
            "sonst_art": "text", "sonst": "wenig"})
        self.assertEqual([z[-1] for z in r.zeilen], ["viel", "wenig", "wenig", "wenig", "wenig"])

    def test_altes_format_laeuft_weiter(self):
        alt = {"op": "bedingte_spalte", "neu": "Alt", "spalte": "Art", "bedingung": "gleich", "wert": "x",
               "dann": "JA", "sonst": "NEIN", "ort": "de"}
        r = lauf(DATEN(), alt)
        self.assertEqual([z[-1] for z in r.zeilen], ["JA", "NEIN", "NEIN", "JA", "NEIN"])
        self.assertIn("Bedingte Spalte", E.beschreibe(alt))

    def test_fehler_sind_verstaendlich(self):
        with self.assertRaises(E.StepError) as c:
            lauf(DATEN(), {"op": "bedingte_spalte", "neu": "F", "klauseln": [
                klausel([b("Menge", "groesser", "[GibtsNicht]", "formel")], "x")]})
        self.assertIn("GibtsNicht", c.exception.meldung)
        with self.assertRaises(E.StepError):
            lauf(DATEN(), {"op": "bedingte_spalte", "neu": "F", "klauseln": []})
        with self.assertRaises(E.StepError):
            lauf(DATEN(), {"op": "bedingte_spalte", "neu": "F", "klauseln": [klausel([b("", "gleich", "x")], "x")]})

    def test_json_roundtrip(self):
        s = {"op": "bedingte_spalte", "neu": "K", "klauseln": [klausel([b("Art", "gleich", "x")], "ja")],
             "sonst_art": "text", "sonst": "nein", "ort": "de"}
        a = E.Abfrage("q", {"art": "blatt"}, [s])
        b2 = E.Abfrage.from_json(json.dumps(json.loads(a.to_json())))
        self.assertEqual(b2.schritte[0], s)
        self.assertTrue(E.beschreibe(s))


class WerteErsetzen(unittest.TestCase):
    def test_teiltext_in_zahlen_bleibt_zahl(self):
        t = T(["a"], [[1234], [1234.5], ["x1"], [None]])
        r = lauf(t, {"op": "ersetzen", "spalte": "a", "suchen": "1", "ersetzen_durch": "7", "ganze_zelle": False})
        self.assertEqual([z[0] for z in r.zeilen], [7234, 7234.5, "x7", None])
        self.assertIsInstance(r.zeilen[0][0], (int, float))

    def test_teiltext_in_zahlen_wird_text_wenn_keine_zahl(self):
        t = T(["a"], [[1234], [5]])
        r = lauf(t, {"op": "ersetzen", "spalte": "a", "suchen": "1", "ersetzen_durch": "x", "ganze_zelle": False})
        self.assertEqual([z[0] for z in r.zeilen], ["x234", 5])

    def test_ganze_zelle_standard_im_dialog_aber_alt_ohne_schluessel_unveraendert(self):
        f = [x for x in E.OPS["ersetzen"]["felder"] if x["name"] == "ganze_zelle"][0]
        self.assertTrue(f["standard"])
        t = T(["a"], [["Altstadt"]])
        r = lauf(t, {"op": "ersetzen", "spalte": "a", "suchen": "Alt", "ersetzen_durch": "Neu"})   # altes Format
        self.assertEqual(r.zeilen[0][0], "Neustadt")

    def test_ganze_zelle_zahl(self):
        t = T(["a"], [[5], [50]])
        r = lauf(t, {"op": "ersetzen", "spalte": "a", "suchen": "5", "ersetzen_durch": "9", "ganze_zelle": True})
        self.assertEqual([z[0] for z in r.zeilen], ["9", 50])


class Typen(unittest.TestCase):
    def test_waehrung_tausenderpunkt_zwei_stellen(self):
        t = T(["a"], [["1234,567"], ["€ 12,5"], ["0,005"], [None]])
        r = lauf(t, {"op": "typ_aendern", "spalten": ["a"], "typ": "waehrung"})
        self.assertEqual([E.als_text(z[0]) for z in r.zeilen], ["1.234,57", "12,50", "0,01", ""])
        self.assertIsInstance(r.zeilen[0][0], E.Waehrung)
        self.assertEqual(r.zeilen[0][0], 1234.57)

    def test_prozent(self):
        t = T(["a"], [["12,5 %"], ["0,125"], ["1234%"]])
        r = lauf(t, {"op": "typ_aendern", "spalten": ["a"], "typ": "prozent"})
        self.assertEqual([E.als_text(z[0]) for z in r.zeilen], ["12,50 %", "12,50 %", "1.234,00 %"])
        self.assertIsInstance(r.zeilen[0][0], E.Prozent)

    def test_typ_bleibt_bei_sortieren_und_filtern(self):
        t = T(["a", "b"], [["3,1", "x"], ["1,2", "y"], ["2,3", "z"]])
        r = lauf(t, {"op": "typ_aendern", "spalten": ["a"], "typ": "waehrung"},
                 {"op": "sortieren", "spalte1": "a", "richtung1": "auf"},
                 {"op": "filtern", "spalte": "b", "bedingung": "ungleich", "wert": "z", "aktion": "behalten"})
        self.assertTrue(all(isinstance(z[0], E.Waehrung) for z in r.zeilen))
        self.assertEqual([float(z[0]) for z in r.zeilen], [1.2, 3.1])

    def test_dezimal_ist_keine_waehrung(self):
        r = lauf(T(["a"], [["1234,567"]]), {"op": "typ_aendern", "spalten": ["a"], "typ": "dezimal"})
        self.assertNotIsInstance(r.zeilen[0][0], E.Waehrung)
        self.assertEqual(r.zeilen[0][0], 1234.567)

    def test_standard_bei_fehler_ist_fehlerwert_wert(self):
        f = [x for x in E.OPS["typ_aendern"]["felder"] if x["name"] == "bei_fehler"][0]
        self.assertEqual(f["standard"], "fehler")
        r = lauf(T(["a"], [["abc"], ["5"]]), {"op": "typ_aendern", "spalten": ["a"], "typ": "ganzzahl",
                                               "bei_fehler": "fehler"})
        self.assertTrue(E.ist_fehler(r.zeilen[0][0]))
        self.assertEqual(str(r.zeilen[0][0]), "#WERT!")
        self.assertEqual(r.zeilen[1][0], 5)

    def test_rechnen_mit_waehrung(self):
        t = lauf(T(["a"], [["10,5"]]), {"op": "typ_aendern", "spalten": ["a"], "typ": "waehrung"},
                 {"op": "benutzerdefinierte_spalte", "neu": "b", "formel": "[a] * 2"})
        self.assertEqual(t.zeilen[0][1], 21.0)

    def test_typliste_vollstaendig(self):
        self.assertEqual([k for k, _ in E.TYPEN], ["text", "ganzzahl", "dezimal", "waehrung", "prozent",
                                                   "datum", "datumzeit", "zeit", "bool"])


if __name__ == "__main__":
    unittest.main()
