import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
S = os.environ.get("SCRATCH", "/tmp")
def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "22"
    AE.speichere_abfrage(doc, E.Abfrage("Eins", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:5])))
    def tun():
        try:
            time.sleep(3.5)
            sh = lambda n: os.system("DISPLAY=:99 import -window root %s/s_%s.png" % (S, n))
            sh("a")
            ed.neue_abfrage(); time.sleep(2); sh("neu"); ed._wechsle_zu(0); time.sleep(1.5); ed.spalte_markieren("Objekt"); time.sleep(1.5); sh("markiert"); print("ST", ed._scroll, [(n, ed.d.modell(n).VScroll, ed.d.ctrl(n).getPosSize().Height, len(l.items), ed._zeilen_geometrie(ed.d.ctrl(n))) for n, l in (("lstAbfragen", ed.lstA), ("lstSchritte", ed.lstS))], ed.ZEILE_DU, flush=True)
            ed._wechsle_zu(0); time.sleep(2); sh("zurueck")
            ed.d.ctrl("chkGitter").getModel().State = 1; ed._gitter_geaendert(); time.sleep(1.5); sh("gitter")
            ed.d.ctrl("chkGitter").getModel().State = 0; ed._gitter_geaendert(); time.sleep(1.5); sh("band")
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(); doc.close(True)
sys.exit(main())
