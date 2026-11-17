# -*- coding: utf-8 -*-
"""0.7.8: wenige Spalten -> letzte Spalte füllt den Rest (Screenshot zur Sichtprüfung)."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
S = os.environ.get("SCRATCH", "/tmp")
def main():
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx); T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "20"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:6])))
    def tun():
        try:
            time.sleep(3)
            ed.abfrage.schritte.append({"op": "spalten_behalten", "spalten": ["Objekt", "Gebäude"]})
            ed.liste_neu(len(ed.abfrage.schritte)); ed.zeige(); time.sleep(2.5)
            os.system("DISPLAY=:99 import -window root %s/s_fuell.png" % S)
            gm = ed.d.ctrl("grid").getModel()
            x = ed.d.model.getByName("deckTabelleR"); cols = sum(c.ColumnWidth for c in gm.ColumnModel.getColumns())
            T.pruefe("Letzte Spalte füllt die Breite, keine freie Fläche (Abdeckung ausgeblendet)", x.PositionX <= 0 and cols >= gm.Width - 6, "%s / %s / %s" % (x.PositionX, cols, gm.Width))
            print("COLS", [(c.ColumnWidth, c.Flexibility) for c in gm.ColumnModel.getColumns()], gm.Width, flush=True)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start(); ed.run(); th.join(); doc.close(True)
    fe = [e for e in T.ergebnisse if not e[1]]
    print('%d Prüfungen, %d Fehler' % (len(T.ergebnisse), len(fe)))
    return 1 if fe else 0
sys.exit(main())
