# -*- coding: utf-8 -*-
"""Nachstellung: bis zum Ende löschen, danach in die Tabelle klicken ("row index is invalid")."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe

def klick(d, x, y, taste=1, n=1):
    d.screen().root.warp_pointer(x, y); d.sync(); time.sleep(0.3)
    for _ in range(n):
        xtest.fake_input(d, X.ButtonPress, taste); d.sync(); time.sleep(0.04)
        xtest.fake_input(d, X.ButtonRelease, taste); d.sync(); time.sleep(0.08)

def main():
    import faulthandler; faulthandler.dump_traceback_later(170, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx); T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "40"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:6])))
    meld = []; res = {}
    ed.meld = lambda t, *a, **k: meld.append(t)
    def tun():
        time.sleep(3)
        d = display.Display(":99")
        orig = AE.meldung; AE.meldung = lambda *a, **k: 2
        try:
            ed.lstS.waehle(1); time.sleep(0.5)
            ed.loeschen_bis_ende(); time.sleep(2)
        finally:
            AE.meldung = orig
        g = ed.d.ctrl("grid"); dp = ed.d.dlg.getPosSize(); gp = g.getPosSize()
        res["zeilen"] = len(ed.angezeigt.zeilen) if ed.angezeigt else None
        res["gridzeilen"] = g.getModel().GridDataModel.RowCount
        for (cx, cy, n) in ((120, 40, 1), (250, 60, 1), (250, 80, 2), (400, 100, 1), (60, 100, 1), (400, 14, 1), (400, 14, 2), (150, 300, 1)):
            klick(d, dp.X + gp.X + cx, dp.Y + gp.Y + cy, 1, n); time.sleep(0.8)
        res["lebt"] = True
    th = threading.Thread(target=tun, daemon=True); th.start(); ed.run(); th.join()
    try: doc.close(True)
    except Exception: pass
    print("RES", res, "MELD", meld)
    pruefe("Keine Meldung nach Klicks", not meld, str(meld))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
