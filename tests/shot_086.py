# -*- coding: utf-8 -*-
"""Bilder 0.8.6: Parameterdialog mit Vorschlägen, Quelle Liste, Filter Werte aus Parameter."""
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


def main():
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    sh = doc.getSheets().getByIndex(0); sh.Name = "Haus"
    for r, z in enumerate([["Nr", "Name"], ["H1", "Alt"], ["H2", "Mitte"], ["H3", "Neu"]]):
        for c, v in enumerate(z):
            sh.getCellByPosition(c, r).setString(v)
    AE.speichere_abfrage(doc, E.Abfrage("Haupt", {"art": "blatt", "blatt": "Haus"}, [{"op": "erste_zeile_als_kopf"}]))
    AE.speichere_oq_parameter(doc, "p_liste", {"typ": "liste", "wert": "H1;H3", "beschreibung": ""})
    AE.setze_aufloeser(ctx, doc); AE._EDITOR_KONTEXT["doc"] = doc
    out = os.environ.get("SCRATCH", "/tmp") + "/hb"
    os.makedirs(out, exist_ok=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = "/tmp/oq_m86.log"
    def aufnehmen(name, vor=None, warte=2.5):
        def t():
            time.sleep(warte)
            try:
                if vor: vor()
                time.sleep(0.8)
                zuschneiden(None, grab(out + "/_n.png"), name)
            except Exception:
                import traceback; traceback.print_exc()
        threading.Thread(target=t, daemon=True).start()
    os.environ["ABFRAGE_AUTOCLOSE"] = "6"
    def v1():
        d = AE._LETZTER_PARAM_DLG["d"]
        d.ctrl("name").getModel().Text = "p_stadt"
        d.ctrl("vtext").getModel().Text = "Berlin;Potsdam;Cottbus"
        d.ctrl("vart").selectItemPos(1, True); time.sleep(0.8)
        d.ctrl("wertwahl").selectItemPos(1, True)
    aufnehmen("s86_param", v1)
    AE.parameter_bearbeiten(ctx, doc, None)
    arten = [a for a, _ in AE.QuellenDialog.ARTEN]
    qd = AE.QuellenDialog(ctx, doc, None, None)
    aufnehmen("s86_quelle", lambda: qd.d.ctrl("art").selectItemPos(arten.index("liste"), True))
    qd.zeigen()
    tab = E.hole_tabelle("Haupt")
    dlg = AE.SchrittDialog(ctx, "filtern_werte", tab, None, {"op": "filtern_werte", "spalte": "Nr"}, None)
    aufnehmen("s86_filter", lambda: dlg.d.ctrl("f_listenparameter").selectItemPos(1, True))
    dlg.zeigen()
    doc.close(True)
    return 0
sys.exit(main())
