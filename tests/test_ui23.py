# -*- coding: utf-8 -*-
"""0.7.3: leere Abfrage löschen; freier Bereich rechts der Tabelle (wenige Spalten)."""
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
            ed.neue_abfrage(); time.sleep(1.5)
            res["n1"] = len(ed.arbeit)
            ed.abfrage_loeschen(); time.sleep(2)
            res["n2"] = len(ed.arbeit)
            ed.lstA.waehle(0); time.sleep(1)
            for _ in range(3):
                ed.neue_abfrage(); time.sleep(1); ed.abfrage_loeschen(); time.sleep(1.5)
        finally:
            AE.meldung = orig
        ed.abfrage.schritte.append({"op": "spalten_behalten", "spalten": ["Objekt", "Gebäude"]})
        ed.liste_neu(len(ed.abfrage.schritte)); ed.zeige(); time.sleep(2)
        # wenige Spalten: Tabelle bleibt, rechts frei
        res["lebt"] = True
        g = ed.d.ctrl("grid"); dp = ed.d.dlg.getPosSize(); gp = g.getPosSize()
        res["deck"] = ed.d.model.getByName("deckTabelleR").PositionX
        pruefe("Abdeckung rechts ausgeblendet (letzte Spalte füllt die Breite)", res["deck"] <= 0, str(res["deck"]))
        for (cx, cy, t) in ((gp.Width-20, 40, 1), (gp.Width-20, 40, 3), (gp.Width-20, 120, 3), (gp.Width-20, 8, 3)):
            klick(d, dp.X + gp.X + cx, dp.Y + gp.Y + cy, t, 1); time.sleep(0.6)
    def verschieben():
        time.sleep(3)
        ed.abfrage.schritte[:] = [{"op": "erste_zeile_als_kopf"},
                                  {"op": "hand_behalten", "schluessel": ["Name"], "handspalten": "Notiz"},
                                  {"op": "spalte_umbenennen", "spalte": "Name", "neu": "Kennung"}]
        ed.liste_neu(3); time.sleep(1)
        ed.lstS.waehle(3); time.sleep(0.5)
        ed.verschiebe(-1); time.sleep(4)
        res["nach_oben"] = (ed.abfrage.schritte[1].get("op"), list(ed.abfrage.schritte[2].get("schluessel")))
        ed.lstS.waehle(2); time.sleep(0.5)
        ed.verschiebe(1); time.sleep(4)
        res["nach_unten"] = list(ed.abfrage.schritte[1].get("schluessel"))
    tun0 = tun
    def tun():
        tun0(); verschieben()
    th = threading.Thread(target=tun, daemon=True); th.start(); ed.run(); th.join()
    try: doc.close(True)
    except Exception: pass
    print("RES", res, "MELD", meld)
    pruefe("Keine Meldung", not meld, str(meld))
    pruefe("Umbenennen nach oben: Schlüssel im Nachbarn angepasst", res.get("nach_oben") == ("spalte_umbenennen", ["Kennung"]), str(res.get("nach_oben")))
    pruefe("Umbenennen nach unten: Schlüssel zurück", res.get("nach_unten") == ["Name"], str(res.get("nach_unten")))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
