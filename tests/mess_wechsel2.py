import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
ctx = T.verbinden()
desk, doc = T.neues_calc(ctx)
T.fuelle_auszug(doc)
frame = doc.getCurrentController().getFrame()
os.environ["ABFRAGE_AUTOCLOSE"] = "0"
st = [{"op":"erste_zeile_als_kopf"},{"op":"typen_erkennen"}]
ed = AE.Editor(ctx, frame, doc, E.Abfrage("A", {"art":"datei","pfad":"/tmp/gross.csv","trenner":"auto"}, list(st)))
ed.run(ohne_dialog=True)
ed._neue_in_liste(E.Abfrage("B", {"art":"datei","pfad":"/tmp/gross.csv","trenner":"auto"}, list(st) + [{"op":"gruppieren","spalten":["Objekt"],"aggregationen":[{"fn":"summe","spalte":"Verbrauch"}]}]), False)
import cProfile, pstats
for i in range(2):
    t = time.time(); ed._wechsle_zu(0); t1 = time.time() - t
    t = time.time(); ed._wechsle_zu(1); t2 = time.time() - t
    print("wechsel A(10000 Zeilen, nur Kopf+Typen) %.2f s / B(+Gruppieren) %.2f s" % (t1, t2))
pr = cProfile.Profile(); pr.enable(); ed._wechsle_zu(0); pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(16)
doc.close(True)
