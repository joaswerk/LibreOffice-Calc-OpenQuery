# -*- coding: utf-8 -*-
"""Echtes Mausziehen (XTest): Teiler und Spaltenbreite."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe
SCRATCH = os.environ.get("SCRATCH", "/tmp")

def ziehe(d, x0, y0, x1, y1, schritte=12):
    xtest.fake_input(d, X.MotionNotify, 0, x=x0, y=y0); d.sync(); time.sleep(0.3)
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.2)
    for i in range(1, schritte + 1):
        xtest.fake_input(d, X.MotionNotify, 0, x=x0 + (x1 - x0) * i // schritte, y=y0 + (y1 - y0) * i // schritte)
        d.sync(); time.sleep(0.05)
    time.sleep(0.2)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync(); time.sleep(0.5)

def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "25"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    res = {}
    def tun():
        try:
            time.sleep(3)
            d = display.Display(":99")
            dp = ed.d.dlg.getPosSize()
            res["dlg"] = (dp.X, dp.Y, dp.Width, dp.Height)
            sp = ed.d.ctrl("sp1l").getPosSize()
            res["sp1"] = (sp.X, sp.Y, sp.Width, sp.Height)
            g = ed.d.ctrl("grid").getPosSize()
            res["grid"] = (g.X, g.Y, g.Width, g.Height)
            res["breite_a0"] = ed.breite_a
            ziehe(d, dp.X + sp.X + 1, dp.Y + sp.Y + 60, dp.X + sp.X + 41, dp.Y + sp.Y + 60)
            res["breite_a1"] = ed.breite_a
            pass
            # Spaltenrand: zweite Spalte (erste Datenspalte) rechter Rand
            cm = ed.d.ctrl("grid").getModel().ColumnModel
            cols = cm.getColumns()
            res["w0"] = [c.ColumnWidth for c in cols[:3]]
            gp = ed.d.ctrl("grid").getPosSize()
            # Pixel je Dialogeinheit
            f = gp.Width / max(ed.d.modell("grid").Width, 1)
            res["f"] = f
            rand = int((cols[0].ColumnWidth + cols[1].ColumnWidth) * f)
            res["rand"] = rand
            ziehe(d, dp.X + gp.X + rand, dp.Y + gp.Y + 5, dp.X + gp.X + rand + 40, dp.Y + gp.Y + 5)
            cols = ed.d.ctrl("grid").getModel().ColumnModel.getColumns()
            res["w1"] = [c.ColumnWidth for c in cols[:3]]
            os.system("DISPLAY=:99 import -window root %s/zieh.png" % SCRATCH)
        except Exception as e:
            import traceback; res["fehler"] = traceback.format_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join()
    doc.close(True)
    print(res)
    return 0
sys.exit(main())
