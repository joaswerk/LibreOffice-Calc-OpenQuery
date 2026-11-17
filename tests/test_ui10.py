# -*- coding: utf-8 -*-
"""Tests für 0.4.2: Linien, Rahmen, Buttons unter den Listen, Enter im Namensfeld, Rechtsklick ins Leere, Doppelklick Spaltentrenner."""
import os, sys, threading, time, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display, XK
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe


def main():
    import faulthandler
    faulthandler.dump_traceback_later(100, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld10.log")
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "30"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    res = {}

    def tun():
        try:
            time.sleep(7)
            d = ed.d
            m = d.modell
            # Layout
            oben, unten = m("linieOben"), m("linieUnten")
            sp = m("sp1l")
            res["linien"] = (sp.PositionY, oben.PositionY, sp.PositionY + sp.Height, unten.PositionY)
            res["rahmen"] = (m("gridA").Border, m("gridB").Border, m("gridDetail").Border)
            la, ls = m("lstAbfragen"), m("lstSchritte")
            res["knoepfe"] = (m("btnNeueAbfrage").PositionY - (la.PositionY + la.Height),
                              m("btnUndoK").PositionY - (ls.PositionY + ls.Height))
            res["info_y"] = (m("lblInfo").PositionY, m("lblSchritte").PositionY)
            # Enter im Namensfeld: nichts wird geschrieben, Editor bleibt offen
            d.ctrl("txtName").getModel().Text = "Neuer Name"
            d.ctrl("txtName").setFocus()
            time.sleep(0.5)
            dp = display.Display(":99")
            kc = dp.keysym_to_keycode(XK.XK_Return)
            xtest.fake_input(dp, X.KeyPress, kc); dp.sync(); time.sleep(0.1)
            xtest.fake_input(dp, X.KeyRelease, kc); dp.sync(); time.sleep(1.5)
            res["enter"] = (ed.abfrage.name, bool(doc.getSheets().hasByName("Neuer Name")), ed.lstA.items[ed.aktuell])
            # Rechtsklick ins Leere: kein Menü
            gerufen = []
            ed.zeige_schritt_menue = lambda x, y: gerufen.append("s")
            ed.zeige_abfragen_menue = lambda x, y: gerufen.append("a")
            ed.schritt_maus(types.SimpleNamespace(X=30, Y=ls.Height * 3, PopupTrigger=True, ClickCount=1, Buttons=2))
            ed.abfragen_maus(types.SimpleNamespace(X=30, Y=la.Height * 3, PopupTrigger=True, ClickCount=1, Buttons=2))
            time.sleep(1.5)
            res["leer_menue"] = list(gerufen)
            # Doppelklick auf den Spaltentrenner
            g = d.ctrl("grid")
            cols = g.getModel().ColumnModel.getColumns()
            f = g.getPosSize().Width / max(d.modell("grid").Width, 1)
            rand = int((cols[0].ColumnWidth + cols[1].ColumnWidth) * f)
            vor = cols[1].ColumnWidth
            ed.breiten[ed._grid_namen[0]] = 120                      # absichtlich zu breit
            cols[1].ColumnWidth = 120
            ed.grid_maus(types.SimpleNamespace(X=int((cols[0].ColumnWidth + 120) * f), Y=5, PopupTrigger=False,
                                               ClickCount=2, Buttons=1))
            time.sleep(1.5)
            nach = d.ctrl("grid").getModel().ColumnModel.getColumns()[1].ColumnWidth
            res["doppel"] = (vor, nach, ed._spdrag)
        except Exception:
            import traceback; res["fehler"] = traceback.format_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join()
    # Ergebnisse
    p = res.get("linien", (0, 1, 2, 3))
    pruefe("Teilerlinie läuft von der oberen bis zur unteren Linie", p[0] <= p[1] + 2 and abs(p[2] - p[3]) <= 1, str(res.get("linien")))
    pruefe("Tabelle und Details haben flachen Rahmen", res.get("rahmen") == (2, 2, 2), str(res.get("rahmen")))
    k = res.get("knoepfe", (99, 99))
    pruefe("Neue Abfrage / Schrittknöpfe direkt unter den Listen", 0 <= k[0] <= 4 and 0 <= k[1] <= 4, str(k))
    i = res.get("info_y", (0, 1))
    pass  # lblInfo entfällt seit 0.7.3
    e = res.get("enter", ("", True, ""))
    pruefe("Enter im Namensfeld übernimmt den Namen, schreibt nichts, schließt nicht",
           e[0] == "Neuer Name" and e[1] is False and e[2] == "Neuer Name" and "fehler" not in res, str(res.get("enter")) + res.get("fehler", ""))
    pruefe("Rechtsklick ins Leere öffnet kein Menü", res.get("leer_menue") == [], str(res.get("leer_menue")))
    dd = res.get("doppel", (0, 0, 1))
    pruefe("Doppelklick auf Spaltentrenner setzt die optimale Breite", dd[1] < 120 and dd[2] is None, str(dd))
    doc.close(True)
    fehler = [x for x in T.ergebnisse if not x[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
