# -*- coding: utf-8 -*-
"""0.10.0: Dialoge nach Klick auf Kopfzeilen-Knöpfe erscheinen mausnah; Fenster im Calc-Fenster; Start anpassbar."""
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
    xtest.fake_input(d, X.ButtonRelease, taste); d.sync(); time.sleep(0.1)


def main():
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "20"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    res = {}
    orig = AE.Dlg.zeigen
    pos = []

    def zeigen(self, parent=None, anteil=None):
        if anteil is None:
            self.nach_peer_ = None
            def zu():
                time.sleep(2.5)
                try:
                    ps = self.dlg.getPosSize()
                    pos.append((ps.X, ps.Y, ps.Width, ps.Height))
                    self.schliessen(0)
                except Exception as e:
                    pos.append(str(e))
            threading.Thread(target=zu, daemon=True).start()
        return orig(self, parent, anteil)
    AE.Dlg.zeigen = zeigen

    def tun():
        time.sleep(9)
        d = display.Display(":99")
        dp = ed.d.dlg.getPosSize()
        res["fenster"] = (dp.X, dp.Y, dp.Width, dp.Height)
        res["rahmen"] = ed.d.rahmen and (ed.d.rahmen.X, ed.d.rahmen.Y, ed.d.rahmen.Width, ed.d.rahmen.Height)
        ed.leiste_reiter(0); time.sleep(1.5)
        for kid in ("param", "a_neu"):
            ctl = ed.d.ctrl("tbi_" + kid).getPosSize()
            x, y = dp.X + ctl.X + ctl.Width // 2, dp.Y + ctl.Y + ctl.Height // 2
            res["klick_" + kid] = (x, y)
            klick(d, x, y)
            time.sleep(4)
        # Schritt-Knopf unter der Liste
        ctl = ed.d.ctrl("btnAendern").getPosSize()
        x, y = dp.X + ctl.X + ctl.Width // 2, dp.Y + ctl.Y + ctl.Height // 2
        res["klick_aendern"] = (x, y)
        klick(d, x, y)
        time.sleep(4)
        res["pos"] = list(pos)
        res["start"] = [e[0] if e else "|" for e in AE.start_eintraege()]
        res["tabs"] = [t for t, _ in AE.LEISTE]
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join()
    AE.Dlg.zeigen = orig
    doc.close(True)
    print(res)
    pruefe("Tabs: ohne Abfrage/Schritte, mit Extras", res["tabs"] == ["Start", "Transformieren", "Spalte hinzufügen", "Kombinieren", "Ansicht", "Extras"], str(res["tabs"]))
    pruefe("Start enthält Neue Abfrage, Parameter und Schritt-Menü", all(k in res["start"] for k in ("a_neu", "param", "s_hin", "a_menu", "s_menu")), str(res["start"]))
    for k, (cx, cy) in (("param", res["klick_param"]), ("a_neu", res["klick_a_neu"]), ("aendern", res["klick_aendern"])):
        i = {"param": 0, "a_neu": 1, "aendern": 2}[k]
        p = res["pos"][i] if len(res["pos"]) > i else None
        ok = isinstance(p, tuple) and (p[0] <= cx <= p[0] + p[2] or abs(p[0] - (cx - 30)) < 120) and (p[1] <= cy <= p[1] + p[3] or abs(p[1] - (cy - 20)) < 120)
        pruefe("Dialog nach Klick auf %s erscheint mausnah" % k, ok, "klick %s dialog %s" % ((cx, cy), p))
    fw = res["fenster"]; rr = res["rahmen"]
    pruefe("Editor nicht größer als das Calc-Fenster", rr is None or (fw[2] <= rr[2] and fw[3] <= rr[3]), "%s %s" % (fw, rr))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print('\n%d Prüfungen, %d Fehler' % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0

sys.exit(main())
