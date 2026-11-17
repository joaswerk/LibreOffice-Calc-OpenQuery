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
    os.environ["ABFRAGE_AUTOCLOSE"] = "14"
    schritte = list(T.SCHRITTE[:4]) + [{"op": "zeilen_umkehren"}] * 30
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, schritte))
    def tun():
        try:
            time.sleep(4)
            m = ed.d.modell
            ls = m("lstSchritte"); yf = m("linieUnten").PositionY
            print("VOLL", ls.PositionY + ls.Height, m("btnHinzu").PositionY, m("btnDupl").PositionY + m("btnDupl").Height, yf, ed._scroll.get("lstSchritte"), flush=True)
            os.system("DISPLAY=:99 import -window root %s/s_voll.png" % S)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(); doc.close(True)
sys.exit(main())
