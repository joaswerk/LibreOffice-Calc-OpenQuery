# -*- coding: utf-8 -*-
"""0.7.6: Umbenennen-Schritt nach oben verschieben zieht Namen in den Schritten dazwischen nach."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def main():
    import faulthandler; faulthandler.dump_traceback_later(170, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    b = doc.getSheets().getByIndex(0); b.Name = "Roh"
    for r, z in enumerate([["Name", "Wert"], ["a", 1], ["b", 2]]):
        for c, v in enumerate(z):
            (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)
    s = [{"op": "erste_zeile_als_kopf"},
         {"op": "hand_behalten", "schluessel": ["Name"], "handspalten": "Notiz"},
         {"op": "spalte_umbenennen", "spalte": "Name", "neu": "Kennung"}]
    q = E.Abfrage("U", {"art": "blatt", "blatt": "Roh"}, s, {"art": "blatt"})
    frame = doc.getCurrentController().getFrame()
    ed = AE.Editor(ctx, frame, doc, q)
    orig = AE.meldung; AE.meldung = lambda *a, **k: 1
    try:
        ed.run(ohne_dialog=True)
        ed.lstS.waehle(3)
        ed.verschiebe(-1)
        st = ed.abfrage.schritte
        pruefe("Reihenfolge: Umbenennen steht jetzt vor Manuelle Spalten", st[1]["op"] == "spalte_umbenennen" and st[2]["op"] == "hand_behalten", str([x["op"] for x in st]))
        pruefe("Schlüssel zieht auf neuen Namen nach", st[2]["schluessel"] == ["Kennung"], str(st[2]))
        ed.lstS.waehle(2)
        ed.verschiebe(1)
        st = ed.abfrage.schritte
        pruefe("Zurückschieben: alter Name wieder da", st[1]["op"] == "hand_behalten" and st[1]["schluessel"] == ["Name"], str(st[1]))
    finally:
        AE.meldung = orig
    doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
