# -*- coding: utf-8 -*-
"""0.8.1: Ordner-Dateiliste, {Zelle} im Dateipfad."""
import os, sys, threading, time, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe
S = os.environ.get("SCRATCH", "/tmp")

def klick(d, x, y):
    d.screen().root.warp_pointer(x, y); d.sync(); time.sleep(0.3)
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.05)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync(); time.sleep(0.2)

def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    import uno
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    ordner = S + "/dateien"
    shutil.rmtree(ordner, ignore_errors=True); os.makedirs(ordner + "/unter")
    for n, inhalt in (("b.csv", "x;y\n1;2\n"), ("a.csv", "x;y\n3;4\n5;6\n"), ("c.txt", "q"), ("~$a.xlsx", ""), ("Z.CSV", "x;y\n9;9\n")):
        open(ordner + "/" + n, "w").write(inhalt)
    # 1) Ordnerliste
    t = AE.lies_quelle(ctx, doc, {"art": "ordner", "pfad": ordner, "muster": "*.csv"})
    namen = [z[0] for z in t.zeilen]
    pruefe("Ordnerliste: Muster, ohne Unterordner/Sperrdatei, sortiert", namen == ["a.csv", "b.csv", "Z.CSV"], str(namen))
    pruefe("Ordnerliste: Standardspalten", t.spalten == ["Name", "Größe", "Geändert"], str(t.spalten))
    pruefe("Ordnerliste: Größe Zahl, Datum datetime", isinstance(t.zeilen[0][1], int) and hasattr(t.zeilen[0][2], "year"), str(t.zeilen[0]))
    t = AE.lies_quelle(ctx, doc, {"art": "ordner", "pfad": ordner, "muster": "*.csv;*.txt", "spalten": ["pfad", "name", "endung", "erstellt"]})
    pruefe("Ordnerliste: Spaltenwahl in fester Reihenfolge, zwei Muster", t.spalten == ["Name", "Endung", "Pfad", "Erstellt"] and len(t.zeilen) == 4, str(t.spalten) + str(len(t.zeilen)))
    pruefe("Ordnerliste: Pfad voll, Endung klein", t.zeilen[0][2] == ordner + "/a.csv" and t.zeilen[3][1] == "csv", str(t.zeilen[:1]) + str(t.zeilen[3]))
    for bad, wort in (("/gibts/nicht", "nicht gefunden"), ("", "kein Ordner")):
        try:
            AE.lies_quelle(ctx, doc, {"art": "ordner", "pfad": bad}); ok = False; m = ""
        except E.FormelFehler as ex:
            ok = wort in str(ex); m = str(ex)
        pruefe("Ordner '%s' -> klare Meldung" % bad, ok, m)
    # 2) {Datei} aus benannter Zelle
    sh = doc.getSheets().getByIndex(0)
    sh.getCellByPosition(0, 0).setString("b.csv")
    doc.NamedRanges.addNewByName("Datei", "$%s.$A$1" % sh.Name, uno.createUnoStruct("com.sun.star.table.CellAddress"), 0)
    q = {"art": "datei", "pfad": ordner + "/{Datei}"}
    t = AE.lies_quelle(ctx, doc, q)
    pruefe("Zellwert im Pfad: b.csv gelesen", len(t.zeilen) == 2, str(t.zeilen))
    sh.getCellByPosition(0, 0).setString("a.csv")
    t = AE.lies_quelle(ctx, doc, q)
    pruefe("Zellwert geändert: a.csv gelesen", len(t.zeilen) == 3, str(t.zeilen))
    sh.getCellByPosition(0, 0).setString("")
    try:
        AE.lies_quelle(ctx, doc, q); ok = False; m = ""
    except E.FormelFehler as ex:
        ok = "leer" in str(ex); m = str(ex)
    pruefe("Leere Zelle -> klare Meldung", ok, m)
    sh.getCellByPosition(0, 0).setString("nix.csv")
    try:
        AE.lies_quelle(ctx, doc, q); ok = False; m = ""
    except E.FormelFehler as ex:
        ok = "nicht gefunden" in str(ex) and "nix.csv" in str(ex); m = str(ex)
    pruefe("Datei fehlt -> klare Meldung mit Name", ok, m)
    sh.getCellByPosition(0, 0).setString("a.csv")
    pruefe("Beschreibung", "a.csv" not in AE.beschreibe_quelle(q) and "{Datei}" in AE.beschreibe_quelle(q), AE.beschreibe_quelle(q))

    # 2b) bis ins Blatt: Ordnerliste -> Zielblatt
    ab = E.Abfrage("Dateien", {"art": "ordner", "pfad": ordner, "muster": "*.csv", "spalten": ["name", "groesse", "geaendert"]},
                   [], {"art": "blatt", "blatt": "Dateien", "bereich": ""} if False else {"art": "blatt"})
    n = AE.aktualisiere_abfrage(ctx, doc, ab)
    shx = doc.getSheets().getByName("Dateien")
    pruefe("Ordnerliste im Blatt: Kopf und 3 Dateien", n == 3 and shx.getCellByPosition(0, 0).String == "Name" and shx.getCellByPosition(0, 1).String == "a.csv",
           "%s %s" % (n, shx.getCellByPosition(0, 1).String))
    pruefe("Ordnerliste im Blatt: Größe Zahl, Geändert ist ein Datum", shx.getCellByPosition(1, 1).Value > 0 and shx.getCellByPosition(2, 1).Value > 40000,
           "%s %s" % (shx.getCellByPosition(1, 1).Value, shx.getCellByPosition(2, 1).Value))

    # 3) Dialog Ordner
    res = {}
    dlg = AE.QuellenDialog(ctx, doc, {"art": "ordner", "pfad": ordner, "muster": "*.csv", "spalten": ["name", "erstellt"]}, None, {}, None)
    os.environ["ABFRAGE_AUTOCLOSE"] = "40"
    def tun():
        time.sleep(3)
        dd = dlg.d
        try:
            res["an"] = [n for n in ("name", "endung", "pfad", "groesse", "geaendert", "erstellt") if dd.ctrl("sp_" + n).getModel().State == 1]
            res["muster"] = dd.ctrl("muster").getText()
            dd.ctrl("sp_pfad").getModel().State = 1
            os.system("DISPLAY=:99 import -window root %s/s_ordner.png" % S)
            xd = display.Display(":99")
            ps, bp = dd.dlg.getPosSize(), dd.ctrl("ok").getPosSize()
            klick(xd, ps.X + bp.X + bp.Width // 2, ps.Y + bp.Y + bp.Height // 2)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    q2 = dlg.zeigen(); th.join()
    print("DLG", res, q2)
    pruefe("Dialog Ordner: gespeicherte Spalten/Muster vorbelegt", res.get("an") == ["name", "erstellt"] and res.get("muster") == "*.csv", str(res))
    pruefe("Dialog Ordner: OK liefert Auswahl", q2 and q2["art"] == "ordner" and q2["spalten"] == ["name", "pfad", "erstellt"] and q2["muster"] == "*.csv" and q2["pfad"] == ordner, str(q2))

    # 4) Dialog Datei mit {Datei}: Inhalt wird mit Zellwert gelesen
    res2 = {}
    dlg2 = AE.QuellenDialog(ctx, doc, {"art": "datei", "pfad": ordner + "/{Datei}"}, None, {}, None)
    def tun2():
        time.sleep(3)
        dd = dlg2.d
        try:
            res2["texte"] = list(dd.ctrl("dateiwahl").getModel().StringItemList)
            res2["vor"] = dd.ctrl("vorschau").getModel().Text
            os.system("DISPLAY=:99 import -window root %s/s_d2.png" % S)
            xd = display.Display(":99")
            ps, bp = dd.dlg.getPosSize(), dd.ctrl("ok").getPosSize()
            res2["pos"] = (ps.X, ps.Y, bp.X, bp.Y, bp.Width, bp.Height)
            for _ in range(3):
                klick(xd, ps.X + bp.X + bp.Width // 2, ps.Y + bp.Y + bp.Height // 2)
                time.sleep(1.2)
                if dlg2.ergebnis is not None: break
            os.system("DISPLAY=:99 import -window root %s/s_d3.png" % S)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun2, daemon=True); th.start()
    q3 = dlg2.zeigen(); th.join()
    print("DLG2", res2, q3)
    pruefe("Dialog Datei mit {Datei}: Vorschau der gewählten Datei", "3 | 4" in res2.get("vor", "") and q3 and q3["pfad"] == ordner + "/{Datei}", str(res2) + str(q3))
    doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
