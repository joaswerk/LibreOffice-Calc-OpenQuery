# -*- coding: utf-8 -*-
"""Abbildungen für das Handbuch: Dialoge und Editor im Xvfb aufnehmen, auf das Neue gegenüber der Basis zuschneiden."""
import os, sys, threading, time, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from PIL import Image, ImageChops
AE, E = T.AE, T.E
S = os.environ.get("SCRATCH", "/tmp")
OUT = S + "/hb"
os.makedirs(OUT, exist_ok=True)

def grab(pfad):
    subprocess.run("DISPLAY=:99 import -window root %s" % pfad, shell=True)
    return Image.open(pfad).convert("RGB")

def dialog_box():
    """Oberstes sichtbares Fenster, das nicht das Hauptfenster ist (= der offene Dialog): (l, o, r, u) oder None."""
    from Xlib import display as xd, X as XX
    d = xd.Display(":99")
    root = d.screen().root
    sw, sh = d.screen().width_in_pixels, d.screen().height_in_pixels
    best = None
    for w in root.query_tree().children:
        try:
            a, g = w.get_attributes(), w.get_geometry()
        except Exception:
            continue
        if a.map_state != XX.IsViewable or g.width < 200 or g.height < 80:
            continue
        if g.width * g.height > 0.9 * sw * sh:
            continue
        best = (g.x, g.y, g.x + g.width, g.y + g.height)
    d.close()
    return best


def zuschneiden(basis, neu, name, rand=4):
    """basis wird nicht gebraucht (None erlaubt)."""
    bb = dialog_box()
    if not bb:
        neu.save("%s/%s.png" % (OUT, name)); return
    l, o, r, u = bb
    neu.crop((max(l - rand, 0), max(o - rand, 0), min(r + rand, neu.width), min(u + rand, neu.height))).save("%s/%s.png" % (OUT, name))


def modal(name, faktor, warte=2.5, schliessen=4):
    """faktor() öffnet einen modalen Dialog im Hauptthread; ein Thread nimmt auf."""
    time.sleep(1.2)
    basis = grab(OUT + "/_basis.png")
    os.environ["ABFRAGE_AUTOCLOSE"] = str(schliessen)
    def tun():
        time.sleep(warte)
        try:
            zuschneiden(basis, grab(OUT + "/_neu.png"), name)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    try:
        faktor()
    except Exception:
        import traceback; traceback.print_exc()
    th.join()

def main():
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    AE.setze_aufloeser(ctx, doc)
    time.sleep(1)
    tab = E.Tabelle(["Text", "Menge"], [["ab-cd", 5]])
    for name, op, start in (("s085_extrahieren", "text_extrahieren", {"art": "vor_trenner", "trenner": "-"}),
                            ("s085_extrahieren_ziffern", "text_extrahieren", {"art": "nur_ziffern"}),
                            ("s085_rechnen", "rechnen", {"spalten": ["Menge"], "rechenart": "multiplizieren", "operand": "1,19"}),
                            ("s085_filter_gerade", "filtern", {"spalte": "Menge", "bedingung": "gerade"})):
        os.environ["ABFRAGE_AUTOOK"] = "5"
        modal(name, lambda: AE.SchrittDialog(ctx, op, tab, None, start, None).zeigen(), warte=2.5)
    doc.close(True)
    return 0
sys.exit(main())
