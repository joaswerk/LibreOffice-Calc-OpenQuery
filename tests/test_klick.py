# -*- coding: utf-8 -*-
"""Echter X11-Mausklick in die Schrittliste: wird die Tabelle neu aufgebaut?"""
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
    AE.schreibe_einstellung("rechtsklick", False)       # dieser Test prüft das Verhalten mit ausgeschaltetem Rechtsklick
    def tun():
        time.sleep(9)
        d = display.Display(":99")
        res["vorher"] = ed.d.ctrl("lblInfo").getModel().Label
        dp = ed.d.dlg.getPosSize()
        ls = ed.d.ctrl("lstSchritte").getPosSize()
        dp = ed.d.dlg.getPosSize()
        fx, fy = (dp.X, dp.Y - 40) if dp.X else (AE._KLICK.get("fenster") or (0, 0))
        zeile = lambda k: fy + 40 + ls.Y + 7 + 18 * k          # Mitte der Listenzeile k (Pixel, Raster ohne Kopfzeile)
        xl, xr = fx + ls.X + 30, fx + ls.X + ls.Width - 20
        res["geo"] = (dp.X, dp.Y, ls.X, ls.Y, ls.Width, ls.Height, ed.lstS.items[:3])
        klick(d, xl, zeile(1))       # Schritt 02 (links in der Liste)
        time.sleep(2)
        res["nach_links"] = ed.d.ctrl("lblInfo").getModel().Label
        klick(d, xl, zeile(3))      # Schritt 04: Einfachklick wählt nur, öffnet kein Menü
        time.sleep(2.5)
        res["nach_rechts"] = ed.d.ctrl("lblInfo").getModel().Label
        res["pm_links"] = getattr(ed, "_pm", None) is not None
        klick(d, xl, zeile(1), 3)   # echter Rechtsklick: wird ignoriert (seit 0.7.0)
        time.sleep(2.5)
        res["pm"] = getattr(ed, "_pm", None) is not None
        os.system("DISPLAY=:99 import -window root /tmp/claude-0/-home-claude/ea0bcda6-313b-5a47-b1ad-65d9b38f4ccc/scratchpad/k2.png")
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join()
    doc.close(True)
    AE.schreibe_einstellung("rechtsklick", None)
    pruefe('Echter Klick auf Schritt 02 baut die Tabelle neu auf', res.get('nach_links', '').startswith('Schritt 2'), str(res))
    pruefe('Einfachklick in der Liste öffnet kein Menü', res.get('pm_links') is False, str(res))
    pruefe('Rechtsklick in der Liste ist bei ausgeschalteter Einstellung ohne Wirkung', res.get('pm') is False and res.get('nach_rechts', '').startswith('Schritt 4'), str(res))
    pruefe('Schritt 04 per Klick gewählt', res.get('nach_rechts', '').startswith('Schritt 4'), str(res))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print('\n%d Prüfungen, %d Fehler' % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0

sys.exit(main())
