# -*- coding: utf-8 -*-
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def roh(doc, zeilen, name):
    sheets = doc.getSheets()
    if not sheets.hasByName(name):
        sheets.insertNewByName(name, sheets.getCount())
    b = sheets.getByName(name); b.clearContents(1023)
    for r, z in enumerate(zeilen):
        for c, v in enumerate(z):
            (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)

def main():
    import faulthandler; faulthandler.dump_traceback_later(170, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    roh(doc, [["A", "B"], ["x", 1]], "R1"); roh(doc, [["A", "B"], ["y", 2]], "R2")
    s = [{"op": "erste_zeile_als_kopf"}]
    q1 = E.Abfrage("Q1", {"art": "blatt", "blatt": "R1"}, list(s), {"art": "blatt"})
    q2 = E.Abfrage("Q2", {"art": "blatt", "blatt": "R2"}, list(s), {"art": "blatt"})
    for q in (q1, q2):
        AE.aktualisiere_abfrage(ctx, doc, q); AE.speichere_abfrage(doc, q)
    frame = doc.getCurrentController().getFrame()
    res = {}
    for an in (False, True):
        roh(doc, [["A", "B"], ["y", 2], ["z", 3]], "R2")
        ed = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Q1"]))
        ed.alle_an = an
        orig = AE.meldung; AE.meldung = lambda *a, **k: 1
        try:
            ed.run(ohne_dialog=True)
            ed.alle_an = an
            ed.laden(schliessen=False)
        finally:
            AE.meldung = orig
        zl = doc.getSheets().getByName("Q2").getCellRangeByName("A3").getString()
        res[an] = zl
        if not an:
            pruefe("Aus: Q2 blieb unverändert", zl == "", zl)
        else:
            pruefe("An: Q2 wurde mit aktualisiert", zl == "z", zl)
            info = ed.d.ctrl("lblInfo").getModel().Label
            pruefe("Schrittbezeichnung kurz (bis Doppelpunkt)", info.startswith("Schritt ") and ":" in info and info.count(":") == 1, info)
    doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
