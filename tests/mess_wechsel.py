import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
ctx = T.verbinden()
desk, doc = T.neues_calc(ctx)
T.fuelle_auszug(doc)
# größere Quelle: 3000 Zeilen
sh = doc.Sheets.getByName("Auszug")
for r in range(30, 3000):
    sh.getCellByPosition(0, r).setString("Schule %d" % (r % 40)); sh.getCellByPosition(1, r).setString("Strom"); sh.getCellByPosition(2, r).setValue(r)
frame = doc.getCurrentController().getFrame()
os.environ["ABFRAGE_AUTOCLOSE"] = "0"
ed = AE.Editor(ctx, frame, doc, E.Abfrage("A", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:3])))
ed.run(ohne_dialog=True)
ed._neue_in_liste(E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:3])), False)
import cProfile, pstats
for i in range(3):
    t = time.time(); ed._wechsle_zu(0); t1 = time.time() - t
    t = time.time(); ed._wechsle_zu(1); t2 = time.time() - t
    print("wechsel %.2f s / %.2f s" % (t1, t2))
pr = cProfile.Profile(); pr.enable(); ed._wechsle_zu(0); pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(14)
doc.close(True)
