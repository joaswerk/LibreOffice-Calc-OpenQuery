# -*- coding: utf-8 -*-
"""0.8.0: Navigator für eine Datei: Blätter, Tabellen, benannte Bereiche; Vorschau; Lesen; Fehler."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
from Xlib import X, display
from Xlib.ext import xtest
AE, E = T.AE, T.E
pruefe = T.pruefe
S = os.environ.get("SCRATCH", "/tmp")

def pv(n, v):
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue"); p.Name = n; p.Value = v; return p

def klick(d, x, y):
    d.screen().root.warp_pointer(x, y); d.sync(); time.sleep(0.3)
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.05)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync(); time.sleep(0.2)

def main():
    import faulthandler; faulthandler.dump_traceback_later(200, exit=True)
    import uno
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    sh = doc.getSheets()
    sh.getByIndex(0).Name = "Daten"
    sh.insertNewByName("Zwei", 1)
    d0, d1 = sh.getByName("Daten"), sh.getByName("Zwei")
    for r, z in enumerate([["Nr", "Name"], [1, "a"], [2, "b"], [3, "c"], [4, "d"]]):
        for c, v in enumerate(z):
            (d0.getCellByPosition(c, r).setString(v) if isinstance(v, str) else d0.getCellByPosition(c, r).setValue(v))
    for r, z in enumerate([["Kopf1", "Kopf2", "Kopf3"], [10, 20, 30], [11, 21, 31]]):
        for c, v in enumerate(z):
            (d1.getCellByPosition(c + 1, r + 1).setString(v) if isinstance(v, str) else d1.getCellByPosition(c + 1, r + 1).setValue(v))
    dbs = doc.DatabaseRanges
    ra = d1.getCellRangeByPosition(1, 1, 3, 3).getRangeAddress()
    dbs.addNewByName("tbl_x", ra)
    nr = doc.NamedRanges
    nr.addNewByName("Zahlen", "$Daten.$A$1:$B$3", uno.createUnoStruct("com.sun.star.table.CellAddress"), 0)
    ods, xlsx, csv = S + "/nav.ods", S + "/nav.xlsx", S + "/nav.csv"
    doc.storeToURL(uno.systemPathToFileUrl(ods), (pv("FilterName", "calc8"),))
    doc.storeToURL(uno.systemPathToFileUrl(xlsx), (pv("FilterName", "Calc MS Excel 2007 XML"),))
    doc.close(True)
    open(csv, "w", encoding="utf-8").write("a;b;c\n1;2;3\n4;5;6\n")

    inh = AE.datei_inhalt(ctx, ods)
    typen = [(e["typ"], e["name"]) for e in inh]
    print("ODS", [e["text"] for e in inh])
    pruefe("ODS: Blätter, Tabelle und benannter Bereich angeboten",
           ("blatt", "Daten") in typen and ("blatt", "Zwei") in typen and ("tabelle", "tbl_x") in typen and ("name", "Zahlen") in typen, str(typen))
    inx = AE.datei_inhalt(ctx, xlsx)
    print("XLSX", [e["text"] for e in inx])
    pruefe("XLSX: Blätter und benannter Bereich angeboten", ("blatt", "Zwei") in [(e["typ"], e["name"]) for e in inx] and ("name", "Zahlen") in [(e["typ"], e["name"]) for e in inx], str([(e["typ"], e["name"]) for e in inx]))
    inc = AE.datei_inhalt(ctx, csv)
    pruefe("CSV: ein Eintrag mit 3 Zeilen × 3 Spalten", len(inc) == 1 and inc[0]["zeilen"] == 3 and inc[0]["spalten"] == 3, str(inc))

    t = AE.lies_quelle(ctx, None, {"art": "datei", "pfad": ods, "tabelle": "tbl_x"})
    pruefe("Tabelle lesen: 3 Zeilen × 3 Spalten, erste Zeile = Kopf", len(t.zeilen) == 3 and len(t.spalten) == 3 and t.zeilen[0][0] == "Kopf1", str(t.zeilen))
    t = AE.lies_quelle(ctx, None, {"art": "datei", "pfad": ods, "bereichsname": "Zahlen"})
    pruefe("Benannter Bereich lesen: 3 × 2", len(t.zeilen) == 3 and len(t.spalten) == 2, str(t.zeilen))
    t = AE.lies_quelle(ctx, None, {"art": "datei", "pfad": ods, "blatt": "Zwei"})
    pruefe("Blatt lesen (Zwei)", t.zeilen and any("Kopf1" == v for z in t.zeilen for v in z), str(t.zeilen[:2]))
    t = AE.lies_quelle(ctx, None, {"art": "datei", "pfad": ods})
    pruefe("Ohne Angabe: erstes Blatt", any("Name" == v for z in t.zeilen for v in z), str(t.zeilen[:2]))
    t = AE.lies_quelle(ctx, None, {"art": "datei", "pfad": xlsx, "blatt": "Daten"})
    pruefe("XLSX lesen", len(t.zeilen) == 5, str(len(t.zeilen)))
    t = AE.lies_quelle(ctx, None, {"art": "datei", "pfad": ods, "blatt": "Daten", "bereich": "A1:B2"})
    pruefe("Bereich in Dateiblatt", len(t.zeilen) == 2, str(t.zeilen))
    for k, v, wort in (("blatt", "Gibtsnicht", "Tabellenblatt"), ("tabelle", "tbl_weg", "Tabelle"), ("bereichsname", "Weg", "Bereich")):
        try:
            AE.lies_quelle(ctx, None, {"art": "datei", "pfad": ods, k: v}); ok = False; msg = ""
        except E.FormelFehler as ex:
            ok = wort in str(ex) and v in str(ex); msg = str(ex)
        pruefe("Fehlendes %s -> klare Meldung" % k, ok, msg)
    pruefe("Beschreibung nennt Tabelle", "tbl_x" in AE.beschreibe_quelle({"art": "datei", "pfad": ods, "tabelle": "tbl_x"}))

    # Dialog
    res = {}
    dlgobj = AE.QuellenDialog(ctx, None, {"art": "datei", "pfad": ods, "tabelle": "tbl_x"}, None, {}, None)
    os.environ["ABFRAGE_AUTOCLOSE"] = "40"
    def tun():
        time.sleep(3)
        dd = dlgobj.d
        try:
            lw = dd.ctrl("dateiwahl")
            res["sel"] = lw.getModel().SelectedItems[0]
            res["texte"] = list(lw.getModel().StringItemList)
            res["vorschau1"] = dd.ctrl("vorschau").getModel().Text
            i_n = next(k for k, t_ in enumerate(res["texte"]) if t_.startswith("Benannter"))
            lw.selectItemPos(i_n, True); time.sleep(0.8)
            res["vorschau2"] = dd.ctrl("vorschau").getModel().Text
            os.system("DISPLAY=:99 import -window root %s/s_nav.png" % S)
            xd = display.Display(":99")
            ps, bp = dd.dlg.getPosSize(), dd.ctrl("ok").getPosSize()
            klick(xd, ps.X + bp.X + bp.Width // 2, ps.Y + bp.Y + bp.Height // 2)
        except Exception:
            import traceback; traceback.print_exc()
    th = threading.Thread(target=tun, daemon=True); th.start()
    q = dlgobj.zeigen(); th.join()
    print("DLG", res, q)
    pruefe("Dialog: gespeicherte Tabelle ist vorgewählt", res.get("texte") and res["texte"][res["sel"]].startswith("Tabelle: tbl_x"), str(res.get("texte")))
    pruefe("Dialog: Vorschau zeigt Kopfzeile der Tabelle", "Kopf1" in res.get("vorschau1", ""), res.get("vorschau1", ""))
    pruefe("Dialog: Vorschau wechselt mit der Auswahl", "Nr" in res.get("vorschau2", "") and "Kopf1" not in res.get("vorschau2", ""), res.get("vorschau2", ""))
    pruefe("Dialog: OK liefert benannten Bereich", q and q.get("bereichsname") == "Zahlen" and not q.get("tabelle") and q.get("pfad") == ods, str(q))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
