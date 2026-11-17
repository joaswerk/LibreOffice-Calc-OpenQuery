import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "12"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:5])))
    def tun():
        try:
            time.sleep(4)
            print("scroll", ed._scroll, flush=True)
            for n in ("lstSchritte", "lstAbfragen", "gridDetail"):
                m = ed.d.modell(n); ps = ed.d.ctrl(n).getPosSize()
                print("VS", n, m.VScroll, m.HScroll, ps.Height, flush=True)
            try:
                ed._scroll_fuer("lstAbfragen", False)
            except Exception:
                import traceback; traceback.print_exc()
            for n in ("lstSchritte", "lstAbfragen"):
                g = ed.d.ctrl(n); ps = g.getPosSize()
                m=ed.d.modell(n); print("modell", m.PositionY, m.Height, "geo", ed._geo, "n", len(ed.lstS.items), len(ed.lstA.items), ed.ZEILE_DU, flush=True); print(n, (ps.X, ps.Y, ps.Width, ps.Height), "items", len(ed.lstS.items), "geo", ed._zeilen_geometrie(g), "pxdu", ed._px_je_du(n), "zh", ed._zeilenhoehe(), flush=True)
                print([ (y, g.getRowAtPoint(3, y)) for y in range(0, 60, 3)], flush=True)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(); doc.close(True)
sys.exit(main())
