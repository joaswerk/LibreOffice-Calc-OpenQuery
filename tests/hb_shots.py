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
    import uno
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx); T.fuelle_auszug(doc)
    _s = doc.getSheets().getByIndex(0)
    for _c in (7, 8, 9):
        _s.getCellByPosition(_c, 4).setString(''); _s.getCellByPosition(_c, 4).NumberFormat = 0
    time.sleep(1)
    frame = doc.getCurrentController().getFrame()
    par = None
    ordner = S + "/dateien"
    ods = S + "/nav.ods"
    raw = E.Tabelle  # noqa
    # Zweite Tabelle für Verbinden/Anfügen
    sh = doc.getSheets()
    sh.insertNewByName("Gebaeude", 1)
    g = sh.getByName("Gebaeude")
    for r, z in enumerate([["Gebäude", "Baujahr", "Fläche m²"], ["Haus 1", 1965, 4200], ["Haus 2", 1998, 3100]]):
        for c, v in enumerate(z):
            (g.getCellByPosition(c, r).setString(v) if isinstance(v, str) else g.getCellByPosition(c, r).setValue(v))
    # Parameter
    AE.speichere_oq_parameter(doc, "p_ordner", {"typ": "text", "wert": ordner, "beschreibung": "Ordner mit den Exportdateien"})
    AE.speichere_oq_parameter(doc, "p_von", {"typ": "datum", "wert": "01.10.2026", "beschreibung": "Beginn des Auswertungszeitraums"})
    AE.speichere_oq_parameter(doc, "p_standorte", {"typ": "liste", "wert": "Schule A;Schule B", "beschreibung": "Standorte für den Filter"})
    st = list(T.SCHRITTE)
    AE.speichere_abfrage(doc, E.Abfrage("Gebaeude", {"art": "blatt", "blatt": "Gebaeude"}, [{"op": "erste_zeile_als_kopf"}]))
    AE.speichere_abfrage(doc, E.Abfrage("Verbrauch", {"art": "blatt", "blatt": "Auszug"}, st))
    ed = AE.Editor(ctx, frame, doc, E.Abfrage("Verbrauch", {"art": "blatt", "blatt": "Auszug"}, st))
    os.environ["ABFRAGE_AUTOCLOSE"] = "60"
    res = {}
    def tun():
        try:
            time.sleep(4)
            ed._wechsle_zu(0) if False else None
            ed.spalte_markieren("Kosten je kWh"); time.sleep(1.5)
            ed.liste_neu(10); time.sleep(1.5)
            grab(OUT + "/_editor_voll.png").crop((170, 100, 1530, 900)).save(OUT + "/editor.png")
            res["editor"] = True
            # Dialoge außerhalb des Editors: im Hauptthread nicht möglich -> hier Thread-Aufrufe über _spaeter
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    ed.run(); th.join()
    print("Editor-Screenshot", res)
    # ---- Phase 2: einzelne Dialoge
    E.AUFLOESER["fn"] = None
    AE.setze_aufloeser(ctx, doc)
    raw = AE.lies_quelle(ctx, doc, {"art": "blatt", "blatt": "Auszug"})
    tab = lambda k: E.fuehre_aus(raw, st[:k])
    SD = lambda op, k, schritt=None, vor=None: (lambda: AE.SchrittDialog(ctx, op, tab(k), schritt, vor, None).zeigen())
    ab = E.Abfrage("Verbrauch", {"art": "blatt", "blatt": "Auszug"}, st)
    modal("quelle_blatt", lambda: AE.QuellenDialog(ctx, doc, {"art": "blatt", "blatt": "Auszug"}, None, {}, None).zeigen())
    modal("quelle_datei", lambda: AE.QuellenDialog(ctx, doc, {"art": "datei", "pfad": ods, "tabelle": "tbl_x"}, None, {}, None).zeigen())
    modal("quelle_ordner", lambda: AE.QuellenDialog(ctx, doc, {"art": "ordner", "pfad": ordner, "muster": "*.csv", "spalten": ["name", "groesse", "geaendert"]}, None, {}, None).zeigen())
    modal("quelle_abfrage", lambda: AE.QuellenDialog(ctx, doc, {"art": "abfrage", "name": "Gebaeude"}, None, {"Gebaeude": "Gebaeude"}, None).zeigen())
    modal("ziel", lambda: AE.ZielDialog(ctx, doc, ab, None).zeigen())
    modal("schritt_filter", SD("filtern", 3, {"op": "filtern", "spalte": "Objekt", "bedingung": "beginnt_mit", "wert": "Summe", "aktion": "entfernen"}))
    modal("schritt_formel", SD("benutzerdefinierte_spalte", 7, {"op": "benutzerdefinierte_spalte", "neu": "Kosten je kWh", "formel": "RUNDEN([Kosten] / [Verbrauch kWh]; 3)"}))
    modal("schritt_bedingt", SD("bedingte_spalte", 7, {"op": "bedingte_spalte", "neu": "Stufe", "klauseln": [{"bedingungen": [{"spalte": "Verbrauch kWh", "bedingung": "groesser", "wert": "1500", "wert_art": "text"}], "verknuepfung": "und", "dann_art": "text", "dann": "hoch"}], "sonst_art": "text", "sonst": "normal"}))
    modal("schritt_typ", SD("typ_aendern", 6, {"op": "typ_aendern", "spalten": ["Verbrauch kWh", "Kosten"], "typ": "dezimal"}))
    modal("schritt_sortieren", SD("sortieren", 9, {"op": "sortieren", "spalte1": "Objekt", "richtung1": "ab", "spalte2": "Datum", "richtung2": "auf"}))
    modal("schritt_gruppieren", SD("gruppieren", 9, {"op": "gruppieren", "spalten": ["Objekt"], "aggregationen": [{"spalte": "Verbrauch kWh", "fn": "summe"}, {"spalte": "Kosten", "fn": "summe"}, {"fn": "anzahl"}]}))
    modal("schritt_ersetzen", SD("ersetzen", 7, {"op": "ersetzen", "spalten": ["Zähler"], "suchen": "Strom", "ersetzen_durch": "Elektro", "ganze_zelle": True}))
    modal("schritt_extrahieren", SD("text_extrahieren", 7, {"op": "text_extrahieren", "spalte": "Objekt", "art": "nach_trenner", "trenner": " ", "neu": "Kurzname"}))
    modal("schritt_teilen", SD("spalte_teilen", 7, {"op": "spalte_teilen", "spalte": "Objekt", "modus": "trenner", "trenner": " "}))
    modal("schritt_pivot", SD("pivotieren", 9, {"op": "pivotieren", "spalte": "Zähler", "werte": "Verbrauch kWh", "fn": "summe"}))
    modal("schritt_hand", SD("hand_behalten", 9, {"op": "hand_behalten", "schluessel": ["Objekt", "Datum"], "handspalten": "Bemerkung\nPrüfer", "auto_neu": True}))
    modal("schritt_verbinden", lambda: AE.VerbindenDialog(ctx, "tabellen_verbinden", tab(9), {"op": "tabellen_verbinden", "abfrage": "Gebaeude", "join": "links"}, None, None).zeigen())
    modal("schritt_anfuegen", lambda: AE.AnfuegenDialog(ctx, "tabellen_anfuegen", tab(9), {"op": "tabellen_anfuegen", "abfragen": ["Gebaeude"], "ausrichtung": "name"}, None, None).zeigen())
    modal("parameter", lambda: AE.ParameterDialog(ctx, doc).zeigen())
    modal("parameter_neu", lambda: AE.parameter_bearbeiten(ctx, doc, None, "p_von"))
    modal("eigenschaften", lambda: AE.EigenschaftenDialog(ctx, ab, lambda *a: None, None).zeigen())
    # ---- Ergebnis im Blatt als intelligente Tabelle
    ab2 = E.Abfrage("Verbrauch", {"art": "blatt", "blatt": "Auszug"}, st, {"art": "blatt", "tabelle": True, "farbe": "blau"})
    AE.speichere_abfrage(doc, ab2)
    AE.aktualisiere_abfrage(ctx, doc, ab2)
    doc.getCurrentController().setActiveSheet(doc.getSheets().getByName("Verbrauch"))
    time.sleep(1.5)
    grab(OUT + "/_blatt_voll.png").crop((0, 105, 1100, 300)).save(OUT + "/ergebnis_blatt.png")
    doc.close(True)
sys.exit(main())
