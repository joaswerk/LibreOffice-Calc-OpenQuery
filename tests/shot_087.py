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
    os.environ["ABFRAGE_AUTOCLOSE"] = "30"
    AE.speichere_oq_parameter(doc, "p_stadt", {"typ": "text", "wert": "Berlin", "beschreibung": "Standort"})
    AE.speichere_oq_parameter(doc, "p_liste", {"typ": "liste", "wert": "H1;H3", "beschreibung": ""})
    AE.speichere_abfrage(doc, E.Abfrage("Eins", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:5])))
    def tun():
        try:
            time.sleep(4)
            sh = lambda n: os.system("DISPLAY=:99 import -window root %s/s87_%s.png" % (S, n))
            sh("a")
            ed.lstA.waehle(len(ed.arbeit)); time.sleep(1); sh("param")
            print("items", ed.lstA.items, "aktuell", ed.aktuell, "pos", ed.lstA.pos(), flush=True)
            ed.lstA.waehle(0, True); time.sleep(1.5)
            ed.d.ctrl("chkGitter").getModel().State = 0
            print("spalten", ed._grid_namen[-1], [c.ColumnWidth for c in ed.d.ctrl("grid").getModel().ColumnModel.getColumns()], ed.d.ctrl("grid").getPosSize().Width, flush=True)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join(); doc.close(True)
sys.exit(main())
