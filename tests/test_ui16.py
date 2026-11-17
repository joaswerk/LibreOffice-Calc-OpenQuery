# -*- coding: utf-8 -*-
"""0.7.0: Absturz-Nachstellung (neue Abfrage sofort löschen, bis zum Ende löschen) bei sichtbarem Editor,
echte Doppelklicks, Rechtsklicks werden ignoriert."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe


def klick(d, x, y, taste=1, n=1):
    d.screen().root.warp_pointer(x, y); d.sync(); time.sleep(0.3)
    for _ in range(n):
        xtest.fake_input(d, X.ButtonPress, taste); d.sync(); time.sleep(0.04)
        xtest.fake_input(d, X.ButtonRelease, taste); d.sync(); time.sleep(0.08)


def main():
    import faulthandler; faulthandler.dump_traceback_later(170, exit=True)
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    T.fuelle_auszug(doc)
    frame = doc.getCurrentController().getFrame()
    os.environ["ABFRAGE_AUTOCLOSE"] = "40"
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("B", {"art": "blatt", "blatt": "Auszug"}, list(T.SCHRITTE[:4])))
    res = {}

    def tun():
        time.sleep(6)
        d = display.Display(":99")
        orig = AE.meldung
        AE.meldung = lambda *a, **k: 2
        orig_ld = AE.loesch_dialog
        AE.loesch_dialog = lambda *a, **k: {"abh": True, "par": True, "blatt": False}
        try:
            for i in range(5):                     # neue Abfrage und sofort wieder löschen
                ed.neue_abfrage()
                ed.abfrage_loeschen()
            time.sleep(1.5)
            res["n_nach_loeschen"] = len(ed.arbeit)
            ed.lstS.waehle(2)
            time.sleep(0.5)
            ed.loeschen_bis_ende()
            time.sleep(1.5)
            res["schritte_nach_ende"] = len(ed.abfrage.schritte)
            for i in range(30):                    # viele Rückrufe: Listener müssen leben
                ed._spaeter(lambda: None)
            time.sleep(1)
        finally:
            AE.meldung = orig
            AE.loesch_dialog = orig_ld
        AE.schreibe_einstellung("rechtsklick", False)
        dp = ed.d.dlg.getPosSize()
        fx, fy = (dp.X, dp.Y - 40) if dp.X else (AE._KLICK.get("fenster") or (0, 0))
        ls = ed.d.ctrl("lstSchritte").getPosSize()
        zeile = lambda k: fy + 40 + ls.Y + 7 + 18 * k
        xl = fx + ls.X + 30
        ed._pm = None
        klick(d, xl, zeile(1), 3)                  # Rechtsklick: nichts
        time.sleep(1.5)
        res["pm_rechts"] = getattr(ed, "_pm", None) is not None
        klick(d, xl, zeile(1), 1)                  # Einfachklick: wählt nur
        time.sleep(1.5)
        res["pm_einfach"] = getattr(ed, "_pm", None) is not None
        res["lebt"] = True
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join()
    try:
        doc.close(True)
    except Exception:
        pass
    pruefe("5x neue Abfrage + sofort löschen ohne Absturz", res.get("n_nach_loeschen") == 1, str(res))
    pruefe("Bis zum Ende löschen ohne Absturz", res.get("schritte_nach_ende") == 1, str(res))
    AE.schreibe_einstellung("rechtsklick", None)
    pruefe("Rechtsklick öffnet kein Menü", res.get("pm_rechts") is False, str(res))
    pruefe("Einfachklick öffnet kein Menü", res.get("pm_einfach") is False, str(res))
    pruefe("Editor läuft nach allem weiter", res.get("lebt") is True, str(res))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
