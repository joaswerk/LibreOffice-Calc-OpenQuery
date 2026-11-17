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
    os.environ["ABFRAGE_AUTOCLOSE"] = "8"
    os.environ["ABFRAGE_AUTOOK"] = "5"
    a = E.Abfrage("Zähler Strom", {"art": "blatt", "blatt": "Auszug"}, [])
    def tun():
        time.sleep(2.5)
        os.system("DISPLAY=:99 import -window root %s/s_ziel.png" % S)
    th = threading.Thread(target=tun, daemon=True); th.start()
    r = AE.ZielDialog(ctx, doc, a, frame.getContainerWindow()).zeigen()
    th.join(); print("ERG", r); doc.close(True)
sys.exit(main())
