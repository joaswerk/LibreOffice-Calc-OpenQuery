# -*- coding: utf-8 -*-
"""0.8.3: Schritt „Dateiinhalt einlesen“ (erste Datei / alle untereinander), Unterordner, Sonderzeichen in Namen."""
import os, sys, shutil, faulthandler; faulthandler.enable(); sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe
S = os.environ.get("SCRATCH", "/tmp")

def pv(n, v):
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue"); p.Name = n; p.Value = v; return p

def xlsx(ctx, desk, pfad, daten, blatt="Daten"):
    import uno
    d = desk.loadComponentFromURL("private:factory/scalc", "_blank", 0, (pv("Hidden", True),))
    sh = d.getSheets().getByIndex(0); sh.Name = blatt
    for r, z in enumerate(daten):
        for c, v in enumerate(z):
            (sh.getCellByPosition(c, r).setString(v) if isinstance(v, str) else sh.getCellByPosition(c, r).setValue(v))
    d.storeToURL(uno.systemPathToFileUrl(pfad), (pv("FilterName", "Calc MS Excel 2007 XML"),))
    d.close(True)

def fehler_von(f):
    try:
        f(); return None
    except (E.FormelFehler, E.StepError) as ex:
        return getattr(ex, "meldung", None) or str(ex.args[0] if ex.args else ex)

def main():
    import faulthandler; faulthandler.dump_traceback_later(90, exit=True)
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    AE.setze_aufloeser(ctx, doc)
    o = S + "/dateien2"
    shutil.rmtree(o, ignore_errors=True); os.makedirs(o + "/Unter Ordner/tief"); os.makedirs(o + "/.versteckt")
    n1, n2, n3 = "Export Januar äöü (1).xlsx", "Export {Feb} 100%.xlsx", "Export März #3.xlsx"
    xlsx(ctx, desk, o + "/" + n1, [[1, "a", 10], [2, "b", 20]])
    xlsx(ctx, desk, o + "/Unter Ordner/" + n2, [[3, "c", 30]])
    xlsx(ctx, desk, o + "/Unter Ordner/tief/" + n3, [[4, "d", 40], [5, "e", 50]])
    xlsx(ctx, desk, o + "/.versteckt/x.xlsx", [[9, "z", 9]])
    q = {"art": "ordner", "pfad": o, "muster": "*.xlsx", "spalten": ["name", "pfad", "ordner"]}
    t0 = AE.lies_quelle(ctx, doc, q)
    pruefe("Ordnerliste ohne Unterordner: 1 Datei", [z[0] for z in t0.zeilen] == [n1], str(t0.zeilen))
    q["unterordner"] = True
    t = AE.lies_quelle(ctx, doc, q)
    pruefe("Mit Unterordnern: 3 Dateien, versteckter Ordner ausgelassen", len(t.zeilen) == 3, str([z[0] for z in t.zeilen]))
    pruefe("Spalte Unterordner relativ, Wurzel leer", [z[2] for z in t.zeilen] == ["", "Unter Ordner", os.path.join("Unter Ordner", "tief")], str([z[2] for z in t.zeilen]))
    pruefe("Beschreibung nennt Unterordner", "Unterordner" in AE.beschreibe_quelle(q), AE.beschreibe_quelle(q))
    # alle
    st = {"op": "datei_einlesen", "pfadspalte": "Pfad", "modus": "alle", "herkunft": "Quelle.Datei", "blatt": "Daten"}
    r = E.fuehre_aus(t, [st])
    pruefe("Alle: 5 Zeilen, 4 Spalten (Herkunft + 3)", len(r.zeilen) == 5 and r.spalten[0] == "Quelle.Datei" and len(r.spalten) == 4, str(r.spalten) + str(len(r.zeilen)))
    pruefe("Alle: Dateinamen mit Leerzeichen/Umlaut/{}/%/# als Herkunft",
           [z[0] for z in r.zeilen] == [n1, n1, n2, n3, n3], str([z[0] for z in r.zeilen]))
    pruefe("Alle: Werte untereinander", [z[1] for z in r.zeilen] == [1, 2, 3, 4, 5] and r.zeilen[4][2] == "e", str(r.zeilen))
    r1 = E.fuehre_aus(t, [dict(st, modus="erste")])
    pruefe("Erste: nur die erste Datei (2 Zeilen)", len(r1.zeilen) == 2 and r1.zeilen[0][0] == n1, str(r1.zeilen))
    r2 = E.fuehre_aus(t, [{"op": "sortieren", "spalte1": "Name", "richtung1": "ab"}, dict(st, modus="erste")])
    pruefe("Erste nach Sortierung absteigend: letzte Datei im Alphabet zuerst", r2.zeilen[0][0] == n2, str(r2.zeilen[0]))
    r3 = E.fuehre_aus(t, [dict(st, herkunft="")])
    pruefe("Ohne Herkunftsspalte: 3 Spalten", len(r3.spalten) == 3 and len(r3.zeilen) == 5, str(r3.spalten))
    f = fehler_von(lambda: E.fuehre_aus(t, [dict(st, herkunft="Spalte1")]))
    pruefe("Herkunftsname schon vorhanden -> Meldung", f and "gibt es in den Daten schon" in f, str(f))
    # Fehlerfälle
    xlsx(ctx, desk, o + "/Unter Ordner/tief/Zwei Spalten.xlsx", [[1, "a"]])
    t2 = AE.lies_quelle(ctx, doc, q)
    f = fehler_von(lambda: E.fuehre_aus(t2, [st]))
    pruefe("Andere Spaltenzahl -> Abbruch mit Dateiname", f and "Zwei Spalten.xlsx" in f and "2 Spalten" in f and "Abgebrochen" in f, str(f))
    os.remove(o + "/Unter Ordner/tief/Zwei Spalten.xlsx")
    xlsx(ctx, desk, o + "/Unter Ordner/tief/Anderes Blatt.xlsx", [[1, "a", 1]], blatt="Woanders")
    t2 = AE.lies_quelle(ctx, doc, q)
    f = fehler_von(lambda: E.fuehre_aus(t2, [st]))
    pruefe("Blatt fehlt in einer Datei -> Abbruch mit Dateiname", f and "Anderes Blatt.xlsx" in f and "Daten" in f, str(f))
    os.remove(o + "/Unter Ordner/tief/Anderes Blatt.xlsx")
    f = fehler_von(lambda: E.fuehre_aus(AE.lies_quelle(ctx, doc, dict(q, spalten=["name"])), [st]))
    pruefe("Spalte Pfad fehlt -> Hinweis", f and "Pfad" in f and "ankreuzen" in f, str(f))
    f = fehler_von(lambda: E.fuehre_aus(AE.lies_quelle(ctx, doc, dict(q, muster="*.nix")), [st]))
    pruefe("Leere Dateiliste -> Meldung", f and "leer" in f, str(f))
    # CSV (ohne Überschrift), alle, Sonderzeichen
    c = S + "/csvs"
    shutil.rmtree(c, ignore_errors=True); os.makedirs(c)
    open(c + "/Bericht 1 ü.csv", "w", encoding="utf-8").write("1;a\n2;b\n")
    open(c + "/Bericht 2.csv", "w", encoding="utf-8").write("3;c\n")
    tc = AE.lies_quelle(ctx, doc, {"art": "ordner", "pfad": c, "muster": "*.csv", "spalten": ["pfad"]})
    rc = E.fuehre_aus(tc, [{"op": "datei_einlesen", "pfadspalte": "Pfad", "modus": "alle", "herkunft": "Quelle.Datei", "trenner": "auto"}])
    pruefe("CSV ohne Überschrift: 3 Zeilen, Herkunft", len(rc.zeilen) == 3 and rc.zeilen[0][0] == "Bericht 1 ü.csv" and rc.zeilen[2][1] == "3", str(rc.zeilen))
    # Dialog
    sel = E.fuehre_aus(t, [{"op": "sortieren", "spalte1": "Name", "richtung1": "auf"}])
    os.environ["ABFRAGE_AUTOOK"] = "3"
    dlg = AE.DateiLesenDialog(ctx, "datei_einlesen", sel, None, {"modus": "alle"}, None)
    res = dlg.zeigen()
    print("DLG", res)
    pruefe("Dialog: OK liefert Schritt mit Blatt und Modus alle", res and res["op"] == "datei_einlesen" and res["modus"] == "alle" and res.get("blatt") == "Daten" and res["pfadspalte"] == "Pfad", str(res))
    r4 = E.fuehre_aus(sel, [res])
    pruefe("Dialog-Schritt ausführbar: 5 Zeilen", len(r4.zeilen) == 5, str(len(r4.zeilen)))
    pruefe("Beschreibung des Schritts", "Dateien einlesen" in E.beschreibe(res), E.beschreibe(res))
    # Dialog: ohne Pfad-Spalte
    dlg = AE.DateiLesenDialog(ctx, "datei_einlesen", AE.lies_quelle(ctx, doc, dict(q, spalten=["name"])), None, {}, None)
    os.environ["ABFRAGE_MELDUNGSLOG"] = S + "/meld32.log"
    res = dlg.zeigen()
    pruefe("Dialog ohne Pfad-Spalte: kein Dialog, Hinweis auf „Pfad“", res is None and "Pfad" in open(S + "/meld32.log", encoding="utf-8").read(), str(res))
    doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
