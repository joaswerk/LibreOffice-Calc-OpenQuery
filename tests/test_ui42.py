# -*- coding: utf-8 -*-
"""0.9.2: Rechtsklick öffnet Menüs (Einstellung), Dialoge erscheinen am letzten Klick, vollständig auf dem Bildschirm."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe

def klick(d, x, y, taste=1):
    d.screen().root.warp_pointer(x, y); d.sync(); time.sleep(0.3)
    xtest.fake_input(d, X.ButtonPress, taste); d.sync(); time.sleep(0.05)
    xtest.fake_input(d, X.ButtonRelease, taste); d.sync(); time.sleep(0.2)

def taste(d, code):
    xtest.fake_input(d, X.KeyPress, code); d.sync(); xtest.fake_input(d, X.KeyRelease, code); d.sync()

def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "40"
    AE.schreibe_einstellung("rechtsklick", True)
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    res = {}
    def dialog_test(name):
        dd = AE.Dlg(ctx, "Test", 120, 80)
        dd.add("FixedText", "a", 5, 5, 100, 10, Label="x")
        def zeige():
            threading.Timer(1.5, lambda: dd.dlg.endExecute()).start()
            dd.zeigen(ed.d.peer())
        ed._spaeter(zeige)
        time.sleep(2.5)
        res[name] = getattr(dd, "letzte_pos", None)
    def tun():
        for _ in range(40):
            if AE._KLICK.get("fenster"):
                break
            time.sleep(0.5)
        time.sleep(3)
        d = display.Display(":99")
        wa = AE.toolkit(ctx).getWorkArea()
        res["wa"] = (wa.X, wa.Y, wa.Width, wa.Height)
        dp_x = _origin = AE._KLICK.get("fenster")
        res["fenster"] = dp_x
        ls = ed.d.ctrl("lstSchritte").getPosSize()
        zeile = lambda k: dp_x[1] + AE.KOPFZEILE_PX + ls.Y + 7 + 18 * k
        xl = dp_x[0] + ls.X + 30
        # 1. Rechtsklick öffnet das Schrittmenü
        klick(d, xl, zeile(1), 3)
        time.sleep(2)
        res["pm_rechts"] = getattr(ed, "_pm", None) is not None
        taste(d, 9); time.sleep(1)          # Escape schließt das Menü
        # 2. Dialog nahe am letzten Klick (links oben im Editor)
        ed._pm = None
        klick(d, dp_x[0] + 150, dp_x[1] + 200)
        time.sleep(0.5)
        res["klick1"] = AE._KLICK.get("pos")
        dialog_test("dlg1")
        # 3. Klick ganz rechts unten: Dialog muss auf dem Bildschirm bleiben
        klick(d, wa.Width - 5, wa.Height - 5)
        time.sleep(0.5)
        res["klick2"] = AE._KLICK.get("pos")
        dialog_test("dlg2")
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join()
    doc.close(True)
    AE.schreibe_einstellung("rechtsklick", None)
    pruefe("Rechtsklick öffnet in der Schrittliste ein Menü", res.get("pm_rechts") is True, str(res))
    pruefe("Klick im Editor wird gemerkt", res.get("klick1") is not None, str(res))
    wa = res.get("wa", (0, 0, 0, 0))
    d1, d2 = res.get("dlg1"), res.get("dlg2")
    pruefe("Dialog erscheint nahe am Klick", bool(d1) and abs(d1[0] - (res["klick1"][0] - 30)) < 5, str(res))
    pruefe("Dialog am Rand bleibt vollständig sichtbar", bool(d2) and d2[0] + d2[2] <= wa[0] + wa[2] and d2[1] + d2[3] <= wa[1] + wa[3], str(res))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print('\n%d Prüfungen, %d Fehler' % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0

sys.exit(main())
