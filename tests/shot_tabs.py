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
    st = list(T.SCHRITTE[:3]) + [{"op": "spalten_behalten", "spalten": ["Objekt", "Zähler"]}]
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, st))
    def tun():
        try:
            time.sleep(4)
            orig = ed._spaltenmodell
            g = ed.d.ctrl("grid")
            print("spalten", ed._grid_namen, [(c.ColumnWidth, c.Flexibility, c.MaxWidth) for c in g.getModel().ColumnModel.getColumns()], g.getPosSize().Width, flush=True)
            for k in range(7):
                ed.leiste_reiter(k); time.sleep(.8)
                if k == 0:
                    os.system("DISPLAY=:99 import -window root %s/voll_0a.png" % S); time.sleep(2)
                if k == 2:
                    os.system("DISPLAY=:99 import -window root %s/voll_a.png" % S)
                    ed.leiste_reiter(2); time.sleep(.8)
                    os.system("DISPLAY=:99 import -window root %s/voll_b.png" % S)
                os.system("DISPLAY=:99 import -window root %s/voll%d.png" % (S, k))
            ps = g.getPosSize(); g.setPosSize(0,0,ps.Width-2,0,4); time.sleep(.3); g.setPosSize(0,0,ps.Width,0,4); time.sleep(1)
            os.system("DISPLAY=:99 import -window root %s/s2sp_b.png" % S)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(); doc.close(True)
sys.exit(main())
