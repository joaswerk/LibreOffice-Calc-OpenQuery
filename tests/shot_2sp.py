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
            os.system("DISPLAY=:99 import -window root %s/s2sp.png" % S)
            ps = g.getPosSize(); g.setPosSize(0,0,ps.Width-2,0,4); time.sleep(.3); g.setPosSize(0,0,ps.Width,0,4); time.sleep(1)
            os.system("DISPLAY=:99 import -window root %s/s2sp_b.png" % S)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(); doc.close(True)
sys.exit(main())
