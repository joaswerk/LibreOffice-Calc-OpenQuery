import sys, os, unittest, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import engine as E


def par(werte):
    def fn(name):
        if name not in werte:
            raise E.FormelFehler("Parameter '%s': keine benannte Zelle dieses Namens" % name)
        return werte[name]
    E.PARAMETER["fn"] = fn


class V060Parameter(unittest.TestCase):
    def setUp(self):
        self.t = E.Tabelle(["Name", "Menge", "Datum"],
                           [["a", 1, dt.date(2026, 1, 5)], ["b", 5, dt.date(2026, 3, 1)], ["c", 9, dt.date(2026, 6, 1)]])

    def tearDown(self):
        E.PARAMETER["fn"] = None

    def test_filter_zahl(self):
        par({"Min": 5})
        r = E.wende_schritt(self.t, {"op": "filtern", "spalte": "Menge", "bedingung": "groesser_gleich", "wert": "{Min}"})
        self.assertEqual([z[0] for z in r.zeilen], ["b", "c"])

    def test_filter_text(self):
        par({"Wer": "b"})
        r = E.wende_schritt(self.t, {"op": "filtern", "spalte": "Name", "bedingung": "gleich", "wert": "{Wer}"})
        self.assertEqual(len(r.zeilen), 1)

    def test_filter_datum(self):
        par({"Start": dt.date(2026, 3, 1)})
        r = E.wende_schritt(self.t, {"op": "filtern", "spalte": "Datum", "bedingung": "groesser_gleich", "wert": "{Start}"})
        self.assertEqual([z[0] for z in r.zeilen], ["b", "c"])

    def test_formel_zahl_text_datum(self):
        par({"Faktor": 2.5, "Praefix": "x-", "Start": dt.date(2026, 3, 1)})
        r = E.wende_schritt(self.t, {"op": "benutzerdefinierte_spalte", "neu": "F", "formel": "[Menge] * {Faktor}"})
        self.assertEqual([z[3] for z in r.zeilen], [2.5, 12.5, 22.5])
        r = E.wende_schritt(self.t, {"op": "benutzerdefinierte_spalte", "neu": "P", "formel": "{Praefix} & [Name]"})
        self.assertEqual(r.zeilen[0][3], "x-a")
        r = E.wende_schritt(self.t, {"op": "benutzerdefinierte_spalte", "neu": "T", "formel": "[Datum] - {Start}"})
        self.assertEqual([z[3] for z in r.zeilen], [-55, 0, 92])

    def test_fehlender_parameter(self):
        par({})
        with self.assertRaises(E.StepError) as cm:
            E.wende_schritt(self.t, {"op": "filtern", "spalte": "Menge", "bedingung": "gleich", "wert": "{Fehlt}"})
        self.assertIn("Fehlt", cm.exception.meldung)
        with self.assertRaises(E.StepError) as cm:
            E.wende_schritt(self.t, {"op": "benutzerdefinierte_spalte", "neu": "F", "formel": "[Menge] * {Fehlt2}"})
        self.assertIn("Fehlt2", cm.exception.meldung)

    def test_ohne_geschweifte_klammern_unveraendert(self):
        s = {"op": "filtern", "spalte": "Menge", "bedingung": "gleich", "wert": "5"}
        self.assertIs(E.loese_parameter(s), s)

    def test_bedingte_spalte(self):
        par({"Grenze": 5, "Text": "gross"})
        s = {"op": "bedingte_spalte", "neu": "K", "klauseln": [
            {"verknuepfung": "und", "bedingungen": [{"spalte": "Menge", "bedingung": "groesser_gleich", "wert_art": "text", "wert": "{Grenze}"}],
             "dann_art": "text", "dann": "{Text}"}], "sonst_art": "text", "sonst": "klein"}
        r = E.wende_schritt(self.t, s)
        self.assertEqual([z[3] for z in r.zeilen], ["klein", "gross", "gross"])


class V060Hand(unittest.TestCase):
    def tearDown(self):
        E.SNAPSHOT["fn"] = None

    def test_hand_behalten(self):
        neu = E.Tabelle(["Id", "Wert"], [["1", 10], ["2", 20], ["4", 40]])
        alt = E.Tabelle(["Id", "Wert", "Notiz"], [["1", 9, "erledigt"], ["2", 19, None], ["3", 30, "weg"]])
        E.SNAPSHOT["fn"] = lambda: alt
        E.HINWEISE[:] = []
        r = E.wende_schritt(neu, {"op": "hand_behalten", "schluessel": ["Id"], "handspalten": "Notiz"})
        self.assertEqual(r.spalten, ["Id", "Wert", "Notiz"])
        self.assertEqual([z[2] for z in r.zeilen], ["erledigt", None, None])
        self.assertEqual([z[1] for z in r.zeilen], [10, 20, 40])      # Quellwerte bleiben maßgeblich
        self.assertTrue(any("1 Eintrag" in h for h in E.HINWEISE), E.HINWEISE)

    def test_erster_lauf_ohne_stand(self):
        neu = E.Tabelle(["Id", "Wert"], [["1", 10]])
        E.SNAPSHOT["fn"] = lambda: None
        r = E.wende_schritt(neu, {"op": "hand_behalten", "schluessel": ["Id"], "handspalten": "Notiz\nStatus"})
        self.assertEqual(r.spalten, ["Id", "Wert", "Notiz", "Status"])
        self.assertEqual(r.zeilen[0][2:], [None, None])

    def test_mehrere_schluessel_und_spalten(self):
        neu = E.Tabelle(["Z", "M", "Wert"], [["a", "1", 1], ["a", "2", 2]])
        alt = E.Tabelle(["Z", "M", "N1", "N2"], [["a", "2", "x", "y"]])
        E.SNAPSHOT["fn"] = lambda: alt
        r = E.wende_schritt(neu, {"op": "hand_behalten", "schluessel": ["Z", "M"], "handspalten": "N1\nN2"})
        self.assertEqual(r.zeilen, [["a", "1", 1, None, None], ["a", "2", 2, "x", "y"]])

    def test_schluessel_fehlt_im_stand(self):
        neu = E.Tabelle(["Id", "Wert"], [["1", 10]])
        E.SNAPSHOT["fn"] = lambda: E.Tabelle(["Andere", "Notiz"], [["1", "x"]])
        with self.assertRaises(E.StepError):
            E.wende_schritt(neu, {"op": "hand_behalten", "schluessel": ["Id"], "handspalten": "Notiz"})

    def test_pflichtfelder(self):
        neu = E.Tabelle(["Id"], [["1"]])
        with self.assertRaises(E.StepError):
            E.wende_schritt(neu, {"op": "hand_behalten", "schluessel": ["Id"], "handspalten": ""})

    def test_spaltenumbenennung_zieht_schluessel_nach(self):
        schritte = [{"op": "hand_behalten", "schluessel": ["Id"], "handspalten": "Notiz"}]
        n = E.folge_schritte_anpassen(schritte, 0, "Id", "Nr")
        self.assertEqual(schritte[0]["schluessel"], ["Nr"], n)

unittest.main()
