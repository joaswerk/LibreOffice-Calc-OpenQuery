# -*- coding: utf-8 -*-
"""Tests für die Schritte aus Version 0.2."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import engine as E  # noqa: E402


def T(spalten, zeilen):
    return E.Tabelle(spalten, zeilen)


def lauf(tab, *schritte):
    return E.fuehre_aus(tab, list(schritte))


VERBRAUCH = lambda: T(["Objekt", "Zähler", "Menge", "Kosten"], [
    ["A", "Strom", 10, 2.5], ["A", "Gas", 5, 1.0], ["B", "Strom", 20, 5.0],
    ["A", "Strom", 30, 7.5], ["B", "Gas", None, None], [None, "Gas", 1, 0.5]])


class Gruppieren(unittest.TestCase):
    def test_summe_anzahl_mittel_minmax(self):
        r = lauf(VERBRAUCH(), {"op": "gruppieren", "spalten": ["Objekt"], "aggregationen": [
            {"fn": "summe", "spalte": "Menge"}, {"fn": "anzahl"}, {"fn": "mittelwert", "spalte": "Kosten"},
            {"fn": "min", "spalte": "Menge", "name": "Kleinste"}, {"fn": "max", "spalte": "Menge"}]})
        self.assertEqual(r.spalten, ["Objekt", "Summe von Menge", "Anzahl", "Mittelwert von Kosten",
                                     "Kleinste", "Maximum von Menge"])
        self.assertEqual(r.zeilen[0], ["A", 45, 3, 3.6666666666666665, 5, 30])       # Reihenfolge: A, B, leer
        self.assertEqual(r.zeilen[1], ["B", 20, 2, 5.0, 20, 20])
        self.assertEqual(r.zeilen[2][0], None)
        self.assertEqual(r.zeilen[2][1:3], [1, 1])

    def test_zwei_gruppenspalten(self):
        r = lauf(VERBRAUCH(), {"op": "gruppieren", "spalten": ["Objekt", "Zähler"],
                               "aggregationen": [{"fn": "summe", "spalte": "Menge"}]})
        self.assertEqual([z[:2] for z in r.zeilen], [["A", "Strom"], ["A", "Gas"], ["B", "Strom"], ["B", "Gas"], [None, "Gas"]])
        self.assertEqual(r.zeilen[0][2], 40)

    def test_ganze_tabelle(self):
        r = lauf(VERBRAUCH(), {"op": "gruppieren", "aggregationen": [{"fn": "summe", "spalte": "Menge"}, {"fn": "anzahl"}]})
        self.assertEqual(r.zeilen, [[66, 6]])
        leer = lauf(T(["a"], []), {"op": "gruppieren", "aggregationen": [{"fn": "summe", "spalte": "a"}, {"fn": "anzahl"}]})
        self.assertEqual(leer.zeilen, [[0, 0]])

    def test_textzahlen_werden_gerechnet(self):
        t = T(["g", "w"], [["x", "1.234,5"], ["x", "0,5"]])
        r = lauf(t, {"op": "gruppieren", "spalten": ["g"], "aggregationen": [{"fn": "summe", "spalte": "w"}]})
        self.assertEqual(r.zeilen[0][1], 1235.0)

    def test_fehlermeldungen(self):
        t = T(["g", "w"], [["x", "abc"]])
        with self.assertRaises(E.StepError) as cm:
            lauf(t, {"op": "gruppieren", "spalten": ["g"], "aggregationen": [{"fn": "summe", "spalte": "w"}]})
        self.assertIn("keine Zahl", str(cm.exception))
        for s in [{"op": "gruppieren"},
                  {"op": "gruppieren", "spalten": ["g"], "aggregationen": [{"fn": "summe"}]},
                  {"op": "gruppieren", "spalten": ["g"], "aggregationen": [{"fn": "anzahl", "name": "g"}]}]:
            with self.assertRaises(E.StepError):
                lauf(t, s)

    def test_erster_letzter_verketten_anzahl_werte(self):
        r = lauf(VERBRAUCH(), {"op": "gruppieren", "spalten": ["Objekt"], "aggregationen": [
            {"fn": "erster", "spalte": "Zähler"}, {"fn": "letzter", "spalte": "Zähler"},
            {"fn": "verketten", "spalte": "Zähler"}, {"fn": "anzahl_werte", "spalte": "Menge"}]})
        self.assertEqual(r.zeilen[0][1:], ["Strom", "Strom", "Strom, Gas, Strom", 3])
        self.assertEqual(r.zeilen[1][4], 1)           # B: eine gefüllte Menge von zwei

    def test_median_eindeutig_trenner(self):
        t = T(["Name", "Farbe", "Zahl"], [["Maya", "blau", 1], ["Maya", "grün", 4], ["Maya", "blau", 10],
                                         ["Paul", "lila", 2], ["Paul", "pink", 3], ["Müller", None, None]])
        r = lauf(t, {"op": "gruppieren", "spalten": ["Name"], "trenner": " / ", "aggregationen": [
            {"fn": "verketten", "spalte": "Farbe", "name": "Farben"},
            {"fn": "anzahl_eindeutig", "spalte": "Farbe", "name": "Verschiedene"},
            {"fn": "median", "spalte": "Zahl", "name": "Median"}]})
        self.assertEqual(r.zeilen[0], ["Maya", "blau / grün / blau", 2, 4])          # Median 1,4,10 = 4
        self.assertEqual(r.zeilen[1], ["Paul", "lila / pink", 2, 2.5])               # gerade Anzahl: Mittel
        self.assertEqual(r.zeilen[2], ["Müller", None, 0, None])                     # leer bleibt leer
        r2 = lauf(t, {"op": "gruppieren", "spalten": ["Name"], "aggregationen": [{"fn": "verketten", "spalte": "Farbe"}]})
        self.assertEqual(r2.zeilen[1][1], "lila, pink")                              # alter Schritt ohne Trenner: Komma
        self.assertEqual(r2.spalten[1], "Alle Werte verketten von Farbe")
        r3 = lauf(T(["g", "w"], [["a", 2], ["a", 4]]), {"op": "gruppieren", "spalten": ["g"], "aggregationen": [
            {"fn": "median", "spalte": "w"}]})
        self.assertEqual(r3.zeilen[0][1], 3)                                         # ganzzahliges Ergebnis bleibt Ganzzahl

    def test_verketten_doppelte_weglassen(self):
        t = T(["Name", "Farbe"], [["Maya", "blau"], ["Maya", "grün"], ["Maya", "blau"], ["Paul", None], ["Paul", "pink"]])
        r = lauf(t, {"op": "gruppieren", "spalten": ["Name"], "trenner": " | ", "doppelte_weglassen": True,
                     "aggregationen": [{"fn": "verketten", "spalte": "Farbe", "name": "F"}]})
        self.assertEqual(r.zeilen[0][1], "blau | grün")
        self.assertEqual(r.zeilen[1][1], "pink")
        r2 = lauf(t, {"op": "gruppieren", "spalten": ["Name"], "aggregationen": [{"fn": "verketten", "spalte": "Farbe", "name": "F"}]})
        self.assertEqual(r2.zeilen[0][1], "blau, grün, blau")                       # ohne Option unverändert

    def test_fehlerwert_wird_gemeldet(self):
        t = T(["g", "w"], [["x", E.FehlerWert("#DIV/0!")]])
        with self.assertRaises(E.StepError) as cm:
            lauf(t, {"op": "gruppieren", "spalten": ["g"], "aggregationen": [{"fn": "summe", "spalte": "w"}]})
        self.assertIn("Fehler", str(cm.exception))


class Drehen(unittest.TestCase):
    MONATE = lambda self: T(["Objekt", "Jan", "Feb", "Mär"], [["A", 1, 2, None], ["B", 4, None, 6]])

    def test_entpivotieren(self):
        r = lauf(self.MONATE(), {"op": "entpivotieren", "spalten": ["Jan", "Feb", "Mär"]})
        self.assertEqual(r.spalten, ["Objekt", "Attribut", "Wert"])
        self.assertEqual(r.zeilen, [["A", "Jan", 1], ["A", "Feb", 2], ["B", "Jan", 4], ["B", "Mär", 6]])

    def test_entpivotieren_andere_und_leere_behalten(self):
        r = lauf(self.MONATE(), {"op": "entpivotieren", "spalten": ["Objekt"], "modus": "andere",
                                 "attribut_name": "Monat", "wert_name": "kWh", "leere_weg": False})
        self.assertEqual(r.spalten, ["Objekt", "Monat", "kWh"])
        self.assertEqual(len(r.zeilen), 6)

    def test_entpivotieren_fehler(self):
        with self.assertRaises(E.StepError):
            lauf(self.MONATE(), {"op": "entpivotieren", "modus": "andere", "spalten": ["Jan", "Feb", "Mär", "Objekt"]})
        with self.assertRaises(E.StepError):
            lauf(self.MONATE(), {"op": "entpivotieren", "spalten": ["Jan"], "attribut_name": "Objekt"})

    def test_alle_spalten_entpivotieren_ist_erlaubt(self):
        r = lauf(self.MONATE(), {"op": "entpivotieren", "spalten": ["Objekt", "Jan", "Feb", "Mär"]})
        self.assertEqual(r.spalten, ["Attribut", "Wert"])

    def test_pivotieren_roundtrip(self):
        lang = lauf(self.MONATE(), {"op": "entpivotieren", "spalten": ["Jan", "Feb", "Mär"]})
        breit = lauf(lang, {"op": "pivotieren", "spalte": "Attribut", "werte": "Wert"})
        self.assertEqual(breit.spalten, ["Objekt", "Jan", "Feb", "Mär"])
        self.assertEqual(breit.zeilen, [["A", 1, 2, None], ["B", 4, None, 6]])

    def test_pivotieren_summiert_duplikate_und_text(self):
        t = T(["o", "m", "w"], [["A", "x", 1], ["A", "x", 2], ["A", "y", 5], ["B", "x", 7]])
        r = lauf(t, {"op": "pivotieren", "spalte": "m", "werte": "w"})
        self.assertEqual(r.zeilen, [["A", 3, 5], ["B", 7, None]])
        t = T(["o", "m", "w"], [["A", "x", "hallo"], ["A", "x", "welt"]])
        r = lauf(t, {"op": "pivotieren", "spalte": "m", "werte": "w"})
        self.assertEqual(r.zeilen, [["A", "hallo"]])                          # automatisch: erster Wert
        r = lauf(t, {"op": "pivotieren", "spalte": "m", "werte": "w", "fn": "verketten"})
        self.assertEqual(r.zeilen, [["A", "hallo, welt"]])

    def test_pivotieren_leer_und_konflikt(self):
        t = T(["o", "m", "w"], [["A", None, 1]])
        self.assertEqual(lauf(t, {"op": "pivotieren", "spalte": "m", "werte": "w"}).spalten, ["o", "(leer)"])
        t = T(["o", "m", "w"], [["A", "o", 1]])
        with self.assertRaises(E.StepError):
            lauf(t, {"op": "pivotieren", "spalte": "m", "werte": "w"})
        with self.assertRaises(E.StepError):
            lauf(t, {"op": "pivotieren", "spalte": "m", "werte": "m"})

    def test_transponieren(self):
        t = T(["a", "b"], [[1, 2], [3, 4]])
        r = lauf(t, {"op": "transponieren"})
        self.assertEqual(r.spalten, ["Spalte1", "Spalte2", "Spalte3"])
        self.assertEqual(r.zeilen, [["a", 1, 3], ["b", 2, 4]])
        r = lauf(t, {"op": "transponieren", "mit_kopf": False})
        self.assertEqual(r.zeilen, [[1, 3], [2, 4]])
        self.assertEqual(r.spalten, ["Spalte1", "Spalte2"])
        r2 = lauf(t, {"op": "transponieren"}, {"op": "erste_zeile_als_kopf"}, {"op": "transponieren", "mit_kopf": False})
        self.assertEqual(r2.zeilen, [["b", 2, 4]] and [[ "b"], [2], [4]])
        self.assertEqual(lauf(T(["a"], []), {"op": "transponieren", "mit_kopf": False}).spalten, [])


class Zeilen(unittest.TestCase):
    def t(self):
        return T(["n"], [[i] for i in range(1, 11)])

    def col(self, r):
        return [z[0] for z in r.zeilen]

    def test_letzte_behalten(self):
        self.assertEqual(self.col(lauf(self.t(), {"op": "zeilen_behalten_unten", "anzahl": 3})), [8, 9, 10])
        self.assertEqual(self.col(lauf(self.t(), {"op": "zeilen_behalten_unten", "anzahl": 0})), [])
        self.assertEqual(len(lauf(self.t(), {"op": "zeilen_behalten_unten", "anzahl": 99}).zeilen), 10)

    def test_bereich(self):
        self.assertEqual(self.col(lauf(self.t(), {"op": "zeilen_bereich", "von": 3, "bis": 5})), [3, 4, 5])
        self.assertEqual(self.col(lauf(self.t(), {"op": "zeilen_bereich", "aktion": "entfernen", "von": 2, "bis": 9})), [1, 10])
        for s in [{"von": 0, "bis": 3}, {"von": 5, "bis": 2}]:
            with self.assertRaises(E.StepError):
                lauf(self.t(), dict(s, op="zeilen_bereich"))

    def test_jede_nte(self):
        self.assertEqual(self.col(lauf(self.t(), {"op": "jede_nte_zeile", "n": 3})), [1, 4, 7, 10])
        self.assertEqual(self.col(lauf(self.t(), {"op": "jede_nte_zeile", "n": 2, "start": 2})), [2, 4, 6, 8, 10])
        self.assertEqual(self.col(lauf(self.t(), {"op": "jede_nte_zeile", "n": 5, "aktion": "entfernen"})), [2, 3, 4, 5, 7, 8, 9, 10])
        with self.assertRaises(E.StepError):
            lauf(self.t(), {"op": "jede_nte_zeile", "n": 0})

    def test_umkehren(self):
        self.assertEqual(self.col(lauf(self.t(), {"op": "zeilen_umkehren"}))[:3], [10, 9, 8])


class Spalten(unittest.TestCase):
    def t(self):
        return T(["a", "b", "c"], [[1, 2, 3]])

    def test_mehrfach_umbenennen(self):
        r = lauf(self.t(), {"op": "spalten_umbenennen", "umbenennungen": "a = Alpha\nb=Beta\n\nc = c"})
        self.assertEqual(r.spalten, ["Alpha", "Beta", "c"])

    def test_tauschen_ist_erlaubt(self):
        r = lauf(self.t(), {"op": "spalten_umbenennen", "umbenennungen": "a = b\nb = a"})
        self.assertEqual(r.spalten, ["b", "a", "c"])

    def test_umbenennen_fehler(self):
        for text in ["a = b", "x = y", "a Alpha", "a = "]:
            with self.assertRaises(E.StepError, msg=text):
                lauf(self.t(), {"op": "spalten_umbenennen", "umbenennungen": text})

    def test_beschreibung_zaehlt_aenderungen(self):
        b = E.beschreibe({"op": "spalten_umbenennen", "umbenennungen": "a = Alpha\nb = b\nc = Gamma"})
        self.assertIn("2 Spalte", b)

    def test_umkehren_und_sortieren(self):
        r = lauf(self.t(), {"op": "spaltenreihenfolge_umkehren"})
        self.assertEqual((r.spalten, r.zeilen), (["c", "b", "a"], [[3, 2, 1]]))
        t = T(["Zebra", "apfel", "Bär"], [[1, 2, 3]])
        r = lauf(t, {"op": "spalten_sortieren"})
        self.assertEqual((r.spalten, r.zeilen), (["apfel", "Bär", "Zebra"], [[2, 3, 1]]))
        r = lauf(t, {"op": "spalten_sortieren", "richtung": "ab"})
        self.assertEqual(r.spalten, ["Zebra", "Bär", "apfel"])


class Fehler(unittest.TestCase):
    def tab(self):
        return T(["w", "x"], [["1", "a"], ["zwei", "b"], ["3", "c"]])

    def test_fehlerwert_einsetzen_und_ersetzen(self):
        r = lauf(self.tab(), {"op": "typ_aendern", "spalten": ["w"], "typ": "ganzzahl", "bei_fehler": "fehler"})
        self.assertTrue(E.ist_fehler(r.zeilen[1][0]))
        self.assertEqual([z[0] for z in r.zeilen if not E.ist_fehler(z[0])], [1, 3])
        r2 = E.fuehre_aus(self.tab(), [{"op": "typ_aendern", "spalten": ["w"], "typ": "ganzzahl", "bei_fehler": "fehler"},
                                       {"op": "fehler_ersetzen", "wert": "0"}])
        self.assertEqual(r2.zeilen[1][0], "0")
        r3 = E.fuehre_aus(self.tab(), [{"op": "typ_aendern", "spalten": ["w"], "typ": "ganzzahl", "bei_fehler": "fehler"},
                                       {"op": "fehler_ersetzen", "spalten": ["w"], "wert": ""}])
        self.assertIsNone(r3.zeilen[1][0])

    def test_zeilen_mit_fehlern_entfernen(self):
        r = E.fuehre_aus(self.tab(), [{"op": "typ_aendern", "spalten": ["w"], "typ": "ganzzahl", "bei_fehler": "fehler"},
                                      {"op": "fehler_zeilen_entfernen"}])
        self.assertEqual([z[1] for z in r.zeilen], ["a", "c"])
        r = E.fuehre_aus(self.tab(), [{"op": "typ_aendern", "spalten": ["w"], "typ": "ganzzahl", "bei_fehler": "fehler"},
                                      {"op": "fehler_zeilen_entfernen", "spalten": ["x"]}])
        self.assertEqual(len(r.zeilen), 3)

    def test_formelspalte_fehlerwert(self):
        r = lauf(T(["a"], [[1], [0]]), {"op": "benutzerdefinierte_spalte", "neu": "q", "formel": "10 / [a]",
                                        "bei_fehler": "fehler"})
        self.assertEqual(r.zeilen[0][1], 10)
        self.assertTrue(E.ist_fehler(r.zeilen[1][1]))

    def test_fehlerwert_ist_text_fuer_filter_und_sortieren(self):
        f = E.FehlerWert("#DIV/0!")
        self.assertEqual(E.als_text(f), "#DIV/0!")
        r = lauf(T(["a"], [[f], ["x"]]), {"op": "filtern", "spalte": "a", "bedingung": "beginnt_mit", "wert": "#"})
        self.assertEqual(len(r.zeilen), 1)
        lauf(T(["a"], [[f], ["x"], [3]]), {"op": "sortieren", "spalte1": "a"})


class TextOps(unittest.TestCase):
    def t(self):
        return T(["s"], [["Haus 12-B"], ["Villa 7-C"], [None], ["ohne"]])

    def one(self, **kw):
        r = lauf(self.t(), dict(op="text_extrahieren", spalte="s", **kw))
        return [z[0] for z in r.zeilen]

    def test_trenner(self):
        self.assertEqual(self.one(art="vor_trenner", trenner="-"), ["Haus 12", "Villa 7", None, None])
        self.assertEqual(self.one(art="nach_trenner", trenner="-"), ["B", "C", None, None])
        self.assertEqual(self.one(art="vor_trenner", trenner=" "), ["Haus", "Villa", None, None])
        self.assertEqual(self.one(art="zwischen_trennern", trenner=" ", trenner2="-"), ["12", "7", None, None])
        t = T(["s"], [["a-b-c"]])
        self.assertEqual(lauf(t, dict(op="text_extrahieren", spalte="s", art="vor_trenner", trenner="-",
                                      vorkommen="letztes")).zeilen[0][0], "a-b")
        self.assertEqual(lauf(t, dict(op="text_extrahieren", spalte="s", art="nach_trenner", trenner="-",
                                      vorkommen="letztes")).zeilen[0][0], "c")

    def test_positionen_und_ziffern(self):
        self.assertEqual(self.one(art="erste_zeichen", anzahl=4), ["Haus", "Vill", None, "ohne"])
        self.assertEqual(self.one(art="letzte_zeichen", anzahl=3), ["2-B", "7-C", None, "hne"])
        self.assertEqual(self.one(art="ab_position", start=6, anzahl=2), ["12", " 7", None, None])
        self.assertEqual(self.one(art="laenge"), [9, 9, None, 4])
        self.assertEqual(self.one(art="nur_ziffern"), ["12", "7", None, None])
        self.assertEqual(self.one(art="ohne_ziffern"), ["Haus -B", "Villa -C", None, "ohne"])

    def test_neue_spalte_und_fehler(self):
        r = lauf(self.t(), dict(op="text_extrahieren", spalte="s", art="vor_trenner", trenner=" ", neu="Typ"))
        self.assertEqual(r.spalten, ["s", "Typ"])
        self.assertEqual(r.zeilen[0], ["Haus 12-B", "Haus"])
        with self.assertRaises(E.StepError):
            lauf(self.t(), dict(op="text_extrahieren", spalte="s", art="vor_trenner", trenner=""))
        with self.assertRaises(E.StepError):
            lauf(self.t(), dict(op="text_extrahieren", spalte="s", art="zwischen_trennern", trenner=" ", trenner2=""))


class Teilen(unittest.TestCase):
    def teile(self, texte, **kw):
        r = lauf(T(["s"], [[x] for x in texte]), dict(op="spalte_teilen", spalte="s", **kw))
        return r.spalten, r.zeilen

    def test_trenner_wie_vorher(self):
        sp, z = self.teile(["a b c", "d e"], trenner=" ")
        self.assertEqual(sp, ["s.1", "s.2", "s.3"])
        self.assertEqual(z, [["a", "b", "c"], ["d", "e", None]])
        sp, z = self.teile(["a b c"], trenner=" ", max_teile=2)
        self.assertEqual(z, [["a", "b c"]])

    def test_position(self):
        sp, z = self.teile(["ABCDEFGH"], modus="position", positionen="4;7")
        self.assertEqual(z, [["ABC", "DEF", "GH"]])
        sp, z = self.teile(["AB"], modus="position", positionen="4")
        self.assertEqual(z, [["AB"]])

    def test_anzahl(self):
        sp, z = self.teile(["ABCDEFG"], modus="anzahl", anzahl_zeichen=3)
        self.assertEqual(z, [["ABC", "DEF", "G"]])

    def test_ziffer_buchstabe_und_klein_gross(self):
        sp, z = self.teile(["Haus12B", "X9"], modus="ziffer_buchstabe")
        self.assertEqual(z, [["Haus", "12", "B"], ["X", "9", None]])
        sp, z = self.teile(["MeinHausNummer"], modus="klein_gross")
        self.assertEqual(z, [["Mein", "Haus", "Nummer"]])

    def test_fehler(self):
        for kw in [dict(modus="trenner", trenner=""), dict(modus="position", positionen=""),
                   dict(modus="position", positionen="a;b"), dict(modus="anzahl", anzahl_zeichen=0)]:
            with self.assertRaises(E.StepError, msg=str(kw)):
                self.teile(["abc"], **kw)


class Sonstiges(unittest.TestCase):
    def test_schritt_ausschalten(self):
        t = T(["a"], [[1], [2], [3]])
        r = lauf(t, {"op": "zeilen_entfernen_oben", "anzahl": 1, "aktiv": False}, {"op": "zeilen_umkehren"})
        self.assertEqual([z[0] for z in r.zeilen], [3, 2, 1])

    def test_abfrage_json_mit_ziel_und_auto(self):
        a = E.Abfrage("X", {"art": "blatt"}, [], {"art": "zelle", "blatt": "B", "zelle": "C3", "letzter": "C3:D9"}, True)
        b = E.Abfrage.from_json(a.to_json())
        self.assertEqual((b.ziel["zelle"], b.ziel["letzter"], b.auto), ("C3", "C3:D9", True))
        alt = E.Abfrage.from_json('{"format": "abfrage-editor", "version": 1, "name": "Alt", "quelle": {}, "schritte": []}')
        self.assertEqual((alt.ziel, alt.auto), ({"art": "blatt"}, False))

    def test_alle_ops_haben_beschreibung_und_pflichtfeldpruefung(self):
        for op, d in E.OPS.items():
            self.assertTrue(E.beschreibe({"op": op}), op)
        with self.assertRaises(E.StepError):
            lauf(T(["a"], [[1]]), {"op": "spalten_umbenennen", "umbenennungen": ""})

    def test_bestandsabfrage_laeuft_unveraendert(self):
        s = [{"op": "zeilen_entfernen_oben", "anzahl": 1},
             {"op": "spalte_teilen", "spalte": "x", "trenner": "-"}]
        r = lauf(T(["x"], [["kopf"], ["a-b"]]), *s)
        self.assertEqual(r.zeilen, [["a", "b"]])

    def test_grosse_tabelle_gruppieren_pivot(self):
        zeilen = [["O%d" % (i % 200), "M%d" % (i % 12), float(i % 7)] for i in range(30000)]
        import time
        t0 = time.time()
        g = lauf(T(["o", "m", "w"], zeilen), {"op": "gruppieren", "spalten": ["o", "m"], "aggregationen": [{"fn": "summe", "spalte": "w"}]},
                 {"op": "pivotieren", "spalte": "m", "werte": "Summe von w"})
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(len(g.spalten), 13)


if __name__ == "__main__":
    unittest.main(verbosity=1)
