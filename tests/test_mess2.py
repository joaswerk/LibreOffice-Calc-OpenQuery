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
    os.environ["ABFRAGE_AUTOCLOSE"] = "20"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:5])))
    def shot(n): os.system("DISPLAY=:99 import -window root -crop 320x260+840+190 %s/m_%s.png" % (S, n))
    def tun():
        try:
            time.sleep(4); shot("0")
            ed.neue_abfrage(); time.sleep(2.5); shot("1")
            ed._wechsle_zu(0); time.sleep(3); shot("2")
            for n in ("lstAbfragen", "lstSchritte"):
                ed.d.auffrischen(n)
            time.sleep(1.5); shot("3")
            print("ST", ed._scroll, [(n, ed.d.modell(n).VScroll, ed.d.modell(n).Height) for n in ("lstAbfragen", "lstSchritte")], flush=True)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(); doc.close(True)
sys.exit(main())
