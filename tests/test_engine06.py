import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import engine as E

class V027(unittest.TestCase):
    def test_fehler_beibehalten(self):
        t = E.Tabelle(["a", "b"], [["1", E.FehlerWert("#WERT!")], ["2", "3"]])
        r = E.wende_schritt(t, {"op": "fehler_zeilen_behalten"})
        self.assertEqual(len(r.zeilen), 1)
    def test_menue_reihenfolge(self):
        ops = [o for o, _ in E.ops_der_gruppe("Zeilen")]
        self.assertEqual(ops.index("fehler_zeilen_behalten"), ops.index("fehler_zeilen_entfernen") + 1)
        self.assertEqual(ops.index("kopf_als_erste_zeile"), ops.index("erste_zeile_als_kopf") + 1)
    def test_filter_standard(self):
        f = [x for x in E.OPS["filtern"]["felder"] if x["name"] == "bedingung"][0]
        self.assertEqual(f["standard"], "enthaelt")
    def test_keine_felder(self):
        for op in ("erste_zeile_als_kopf", "kopf_als_erste_zeile", "zeilen_umkehren", "spaltenreihenfolge_umkehren"):
            self.assertFalse(E.OPS[op]["felder"], op)
unittest.main()
