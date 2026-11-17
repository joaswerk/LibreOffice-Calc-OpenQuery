import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
ctx = T.verbinden()
desk, doc = T.neues_calc(ctx)
frame = doc.getCurrentController().getFrame()
os.environ["ABFRAGE_AUTOCLOSE"] = "0"
ed = AE.Editor(ctx, frame, doc, E.Abfrage("A", {"art":"datei","pfad":"/tmp/klein.csv","trenner":"auto"}, [{"op":"erste_zeile_als_kopf"}]))
ed.run(ohne_dialog=True)
def zeig(t):
    ed.d.bei_groesse(0,0)
    gm = ed.d.modell("grid")
    cols = [c.ColumnWidth for c in gm.ColumnModel.getColumns()]
    print(t, "Grid", gm.Width, "Spalten", cols, "Summe", sum(cols), "extra", ed._letzte_extra)
zeig("start")
ed._neue_in_liste(E.Abfrage("B", {"art":"datei","pfad":"/tmp/gross.csv","trenner":"auto"}, [{"op":"erste_zeile_als_kopf"}]), False)
zeig("B gross")
ed._wechsle_zu(0)
zeig("zurueck klein")
doc.close(True)
