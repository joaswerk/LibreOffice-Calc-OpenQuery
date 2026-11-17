# -*- coding: utf-8 -*-
import datetime as dt
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import engine as E  # noqa: E402

AUSZUG = """Liegenschaftsbericht;;;;;
Stand: 27.10.2026;;;;;
;;;;;
Objekt;Gebäude;Zähler;Datum;Verbrauch kWh;Kosten
Schule A;Haus 1;Strom;01.10.2026 08:30;1.234,50;356,12 €
;;Gas;02.10.2026 09:00;980,00;88,40 €
;;Wasser;03.10.2026 10:15;12,5;4,30 €
Zwischensumme;;;;2.227,00;448,82 €
;;;;;
Schule B;Haus 2;Strom;01.10.2026 08:30;2.000,00;500,00 €
;;Gas;04.10.2026 07:45;1.500,00;120,00 €
Summe gesamt;;;;5.727,00;1.068,82 €
"""


def roh():
    return E.tabelle_aus_text(AUSZUG)


BASIS = [
    {"op": "zeilen_entfernen_oben", "anzahl": 3},
    {"op": "erste_zeile_als_kopf"},
    {"op": "fuellen_unten", "spalten": ["Objekt", "Gebäude"]},
    {"op": "filtern", "spalte": "Objekt", "bedingung": "beginnt_mit", "wert": "Summe", "aktion": "entfernen"},
    {"op": "filtern", "spalte": "Objekt", "bedingung": "beginnt_mit", "wert": "Zwischensumme", "aktion": "entfernen"},
    {"op": "leere_zeilen_entfernen"},
]


class Grundlagen(unittest.TestCase):
    def test_csv_trenner(self):
        t = roh()
        self.assertEqual(len(t.spalten), 6)
        self.assertEqual(t.zeilen[3][0], "Objekt")

    def test_basisbereinigung(self):
        t = E.fuehre_aus(roh(), BASIS)
        self.assertEqual(t.spalten, ["Objekt", "Gebäude", "Zähler", "Datum", "Verbrauch kWh", "Kosten"])
        self.assertEqual(len(t.zeilen), 5)
        self.assertEqual([z[0] for z in t.zeilen], ["Schule A"] * 3 + ["Schule B"] * 2)
        self.assertEqual([z[1] for z in t.zeilen][:3], ["Haus 1"] * 3)

    def test_typen_de(self):
        s = BASIS + [
            {"op": "typ_aendern", "spalten": ["Datum"], "typ": "datumzeit"},
            {"op": "typ_aendern", "spalten": ["Verbrauch kWh", "Kosten"], "typ": "dezimal"},
        ]
        t = E.fuehre_aus(roh(), s)
        self.assertEqual(t.zeilen[0][3], dt.datetime(2026, 10, 1, 8, 30))
        self.assertEqual(t.zeilen[0][4], 1234.5)
        self.assertEqual(t.zeilen[0][5], 356.12)     # Währungssymbol wird erkannt
        self.assertEqual(t.zeilen[2][4], 12.5)

    def test_zahl_nicht_falsch_gelesen(self):
        # '12.5' im deutschen Format darf NICHT 125 werden
        with self.assertRaises(E.FormelFehler):
            E.parse_zahl("12.5", "de")
        self.assertEqual(E.parse_zahl("12.500", "de"), 12500)
        self.assertEqual(E.parse_zahl("1,234.56", "en"), 1234.56)
        self.assertEqual(E.parse_zahl("(1.000,00)", "de"), -1000)
        self.assertEqual(E.parse_zahl("5%", "de"), 0.05)

    def test_typfehler_meldung(self):
        s = BASIS + [{"op": "typ_aendern", "spalten": ["Zähler"], "typ": "ganzzahl"}]
        with self.assertRaises(E.StepError) as cm:
            E.fuehre_aus(roh(), s)
        self.assertEqual(cm.exception.index, len(BASIS))
        self.assertIn("Zeile 1", str(cm.exception))

    def test_typfehler_leer(self):
        s = BASIS + [{"op": "typ_aendern", "spalten": ["Zähler"], "typ": "ganzzahl", "bei_fehler": "leer"}]
        t = E.fuehre_aus(roh(), s)
        self.assertTrue(all(z[2] is None for z in t.zeilen))

    def test_sortieren_mehrstufig(self):
        s = BASIS + [
            {"op": "typ_aendern", "spalten": ["Verbrauch kWh"], "typ": "dezimal"},
            {"op": "sortieren", "spalte1": "Objekt", "richtung1": "ab",
             "spalte2": "Verbrauch kWh", "richtung2": "auf"},
        ]
        t = E.fuehre_aus(roh(), s)
        self.assertEqual([z[0] for z in t.zeilen], ["Schule B"] * 2 + ["Schule A"] * 3)
        self.assertEqual([z[4] for z in t.zeilen], [1500.0, 2000.0, 12.5, 980.0, 1234.5])

    def test_filter_zahl_und_text(self):
        s = BASIS + [
            {"op": "typ_aendern", "spalten": ["Verbrauch kWh"], "typ": "dezimal"},
            {"op": "filtern", "spalte": "Verbrauch kWh", "bedingung": "groesser", "wert": "1.000,00"},
        ]
        t = E.fuehre_aus(roh(), s)
        self.assertEqual(len(t.zeilen), 3)
        t2 = E.fuehre_aus(roh(), BASIS + [{"op": "filtern", "spalte": "Zähler",
                                            "bedingung": "in_liste", "wert": "strom; wasser"}])
        self.assertEqual(len(t2.zeilen), 3)

    def test_spalten_ops(self):
        s = BASIS + [
            {"op": "spalte_umbenennen", "spalte": "Verbrauch kWh", "neu": "kWh"},
            {"op": "spalten_verschieben", "spalten": ["Datum"], "position": "anfang"},
            {"op": "spalten_zusammenfuehren", "spalten": ["Objekt", "Gebäude"], "trenner": " / ",
             "neu": "Ort"},
            {"op": "spalte_teilen", "spalte": "Datum", "trenner": " "},
        ]
        t = E.fuehre_aus(roh(), s)
        self.assertEqual(t.spalten, ["Datum.1", "Datum.2", "Ort", "Zähler", "kWh", "Kosten"])
        self.assertEqual(t.zeilen[0][2], "Schule A / Haus 1")
        self.assertEqual(t.zeilen[0][0], "01.10.2026")

    def test_duplikate_und_ersetzen(self):
        s = BASIS + [
            {"op": "ersetzen", "spalte": "Kosten", "suchen": " €", "ersetzen_durch": ""},
            {"op": "duplikate_entfernen", "spalten": ["Objekt"]},
        ]
        t = E.fuehre_aus(roh(), s)
        self.assertEqual(len(t.zeilen), 2)
        self.assertEqual(t.zeilen[0][5], "356,12")

    def test_typen_erkennen(self):
        s = BASIS + [{"op": "ersetzen", "spalte": "Kosten", "suchen": " €", "ersetzen_durch": ""},
                     {"op": "typen_erkennen"}]
        t = E.fuehre_aus(roh(), s)
        self.assertIsInstance(t.zeilen[0][3], dt.datetime)
        self.assertEqual(t.zeilen[0][4], 1234.5)
        self.assertEqual(t.zeilen[0][5], 356.12)
        self.assertEqual(t.zeilen[0][0], "Schule A")   # Text bleibt Text

    def test_fuehrende_nullen_bleiben_text(self):
        self.assertIsNone(E.erkenne_typ(["007", "012", "100"]))
        self.assertEqual(E.erkenne_typ(["7", "12", "1.000"]), "ganzzahl")

    def test_filtern_werte(self):
        r = E.fuehre_aus(roh(), BASIS + [{"op": "filtern_werte", "spalte": "Zähler", "werte": ["Strom", "Gas"]}])
        self.assertEqual(len(r.zeilen), 4)
        r = E.fuehre_aus(roh(), BASIS + [{"op": "filtern_werte", "spalte": "Zähler",
                                           "werte": ["Strom"], "aktion": "entfernen"}])
        self.assertEqual(len(r.zeilen), 3)
        t = E.fuehre_aus(roh(), BASIS)
        self.assertEqual(E.eindeutige_werte(t, "Zähler"), ["Gas", "Strom", "Wasser"])
        with self.assertRaises(E.StepError):
            E.fuehre_aus(roh(), BASIS + [{"op": "filtern_werte", "spalte": "Zähler", "werte": []}])
        self.assertIn("Strom", E.beschreibe({"op": "filtern_werte", "spalte": "Zähler", "werte": ["Strom"]}))

    def test_wende_schritt(self):
        t = E.wende_schritt(E.Tabelle(["a"], [[1]]), {"op": "spalte_umbenennen", "spalte": "a", "neu": "b"})
        self.assertEqual(t.spalten, ["b"])


class Formeln(unittest.TestCase):
    def tab(self):
        return E.Tabelle(["Menge", "Preis", "Vorname", "Nachname", "Datum"],
                         [[3, 2.5, "Anna", "Müller", dt.date(2026, 10, 27)],
                          [4, 10, "Bo", "Ng", dt.date(2026, 1, 5)],
                          [None, None, "Cy", None, None]])

    def ev(self, f, zeile=0):
        t = self.tab()
        return E.werte_formel(f, t, t.zeilen[zeile])

    def test_arith(self):
        self.assertEqual(self.ev("[Menge] * [Preis]"), 7.5)
        self.assertEqual(self.ev("= ([Menge] + 2) * 2"), 10)
        self.assertEqual(self.ev("2 ^ 3 ^ 2"), 64)           # (2^3)^2 wie in Calc: links-assoz
        self.assertEqual(self.ev("-[Menge] + 10"), 7)
        self.assertEqual(self.ev("50%"), 0.5)
        self.assertEqual(self.ev("1,5 * 2"), 3)

    def test_text(self):
        self.assertEqual(self.ev('[Vorname] & " " & [Nachname]'), "Anna Müller")
        self.assertEqual(self.ev('LINKS([Nachname]; 2)'), "Mü")
        self.assertEqual(self.ev('rechts([Nachname]; 3)'), "ler")
        self.assertEqual(self.ev('TEIL([Nachname]; 2; 3)'), "üll")
        self.assertEqual(self.ev('GROSS([Vorname])'), "ANNA")
        self.assertEqual(self.ev('LAENGE([Nachname])'), 6)
        self.assertEqual(self.ev('LÄNGE([Nachname])'), 6)
        self.assertEqual(self.ev('WECHSELN([Nachname]; "ü"; "ue")'), "Mueller")
        self.assertEqual(self.ev('FINDEN("l"; [Nachname])'), 3)

    def test_wenn(self):
        self.assertEqual(self.ev('WENN([Menge] > 3; "viel"; "wenig")'), "wenig")
        self.assertEqual(self.ev('WENN([Menge] > 3; "viel"; "wenig")', 1), "viel")
        self.assertEqual(self.ev('WENN(UND([Menge] > 1; [Preis] < 5); 1; 0)'), 1)
        self.assertEqual(self.ev('WENNFEHLER([Menge] / 0; -1)'), -1)
        self.assertEqual(self.ev('WENN(ISTLEER([Menge]); "leer"; "da")', 2), "leer")

    def test_datum(self):
        self.assertEqual(self.ev('JAHR([Datum])'), 2026)
        self.assertEqual(self.ev('TEXT([Datum]; "TT.MM.JJJJ")'), "27.10.2026")
        self.assertEqual(self.ev('TEXT([Datum]; "JJJJ-MM")'), "2026-10")
        self.assertEqual(self.ev('DATUM(2026; 14; 1)'), dt.date(2027, 2, 1))
        self.assertEqual(self.ev('[Datum] + 5'), dt.date(2026, 11, 1))
        self.assertEqual(self.ev('[Datum] - DATUM(2026; 10; 1)'), 26)

    def test_text_zahlformat(self):
        self.assertEqual(self.ev('TEXT(1234,5; "#.##0,00")'), "1.234,50")
        self.assertEqual(self.ev('TEXT(5; "000")'), "005")
        self.assertEqual(self.ev('TEXT(0,256; "0,0%")'), "25,6%")

    def test_runden(self):
        self.assertEqual(self.ev("RUNDEN(2,5; 0)"), 3)
        self.assertEqual(self.ev("RUNDEN(-2,5; 0)"), -3)
        self.assertEqual(self.ev("RUNDEN(1,005; 2)"), 1.01)
        self.assertEqual(self.ev("ABRUNDEN(1,999; 2)"), 1.99)

    def test_fehler(self):
        for f in ["[Gibtsnicht] + 1", "FOO(1)", "Menge + 1", "1 +", "LINKS()", '"offen', "(1"]:
            with self.assertRaises(E.FormelFehler, msg=f):
                self.ev(f)
        with self.assertRaises(E.FormelFehler):
            self.ev("1 / 0")

    def test_leere_zellen(self):
        self.assertEqual(self.ev("[Menge] + 1", 2), 1)
        self.assertEqual(self.ev('[Nachname] & "!"', 2), "!")

    def test_formelspalte_im_schritt(self):
        t = E.fuehre_aus(self.tab(), [
            {"op": "benutzerdefinierte_spalte", "neu": "Summe", "formel": "[Menge]*[Preis]"}])
        self.assertEqual([z[5] for z in t.zeilen], [7.5, 40, 0])
        with self.assertRaises(E.StepError):
            E.fuehre_aus(self.tab(), [{"op": "benutzerdefinierte_spalte", "neu": "X", "formel": "[Nix]"}])
        t = E.fuehre_aus(self.tab(), [{"op": "benutzerdefinierte_spalte", "neu": "X",
                                       "formel": "10 / [Menge]", "bei_fehler": "leer"}])
        self.assertIsNone(t.zeilen[2][5])


class Sonstiges(unittest.TestCase):
    def test_json_roundtrip(self):
        a = E.Abfrage("Test", {"art": "datei", "pfad": "x.csv"}, BASIS)
        b = E.Abfrage.from_json(a.to_json())
        self.assertEqual(b.schritte, BASIS)
        self.assertEqual(b.quelle["pfad"], "x.csv")
        with self.assertRaises(ValueError):
            E.Abfrage.from_json('{"foo": 1}')

    def test_beschreibung_aller_ops(self):
        for op, d in E.OPS.items():
            step = {"op": op}
            for f in d["felder"]:
                if "standard" in f:
                    step[f["name"]] = f["standard"]
            self.assertTrue(E.beschreibe(step), op)

    def test_fuellen_oben_und_kopf(self):
        t = E.Tabelle(["a", "b"], [[None, 1], ["x", 2], [None, 3]])
        r = E.fuehre_aus(t, [{"op": "fuellen_oben", "spalten": ["a"]}])
        self.assertEqual([z[0] for z in r.zeilen], ["x", "x", None])
        r = E.fuehre_aus(t, [{"op": "kopf_als_erste_zeile"}, {"op": "erste_zeile_als_kopf"}])
        self.assertEqual(r.spalten, ["a", "b"])

    def test_doppelte_ueberschriften(self):
        t = E.Tabelle(["x", "y", "z"], [["Name", "Name", None], [1, 2, 3]])
        r = E.fuehre_aus(t, [{"op": "erste_zeile_als_kopf"}])
        self.assertEqual(r.spalten, ["Name", "Name.1", "Spalte3"])

    def test_pflichtfeld(self):
        with self.assertRaises(E.StepError):
            E.fuehre_aus(roh(), [{"op": "spalten_entfernen", "spalten": []}])

    def test_eingabe_nicht_veraendert(self):
        r = roh()
        vorher = [list(z) for z in r.zeilen]
        E.fuehre_aus(r, BASIS)
        self.assertEqual(r.zeilen, vorher)

    def test_tausende_zeilen_tempo(self):
        zeilen = []
        for i in range(20000):
            zeilen.append(["Obj%d" % (i % 50) if i % 3 == 0 else None,
                           "%d.%02d.2026 %02d:%02d" % (1 + i % 28, 1 + i % 12, i % 24, i % 60),
                           "%s,%02d" % ("{:,}".format(i).replace(",", "."), i % 100)])
        t = E.Tabelle(["O", "D", "W"], zeilen)
        t0 = time.time()
        r = E.fuehre_aus(t, [
            {"op": "fuellen_unten", "spalten": ["O"]},
            {"op": "typ_aendern", "spalten": ["D"], "typ": "datumzeit"},
            {"op": "typ_aendern", "spalten": ["W"], "typ": "dezimal"},
            {"op": "benutzerdefinierte_spalte", "neu": "X", "formel": "WENN([W] > 100; [O] & \"!\"; \"\")"},
            {"op": "sortieren", "spalte1": "W", "richtung1": "ab"},
        ])
        dauer = time.time() - t0
        self.assertEqual(len(r.zeilen), 20000)
        self.assertLess(dauer, 10, "zu langsam: %.1fs" % dauer)
        print("\n20000 Zeilen in %.2fs" % dauer)


if __name__ == "__main__":
    unittest.main(verbosity=1)
