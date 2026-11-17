# -*- coding: utf-8 -*-
"""0.7.4: Schlüsselprüfung, Tabelle folgt dem Bereich, Konflikte, neue Handspalten."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe

def roh(doc, zeilen, name="Roh"):
    sheets = doc.getSheets()
    if not sheets.hasByName(name):
        sheets.insertNewByName(name, sheets.getCount())
    b = sheets.getByName(name)
    b.clearContents(1023)
    for r, z in enumerate(zeilen):
        for c, v in enumerate(z):
            (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)
    return b

BASIS = [["Name", "Wert"], ["a", 1], ["b", 2], ["c", 3]]
SCHR = lambda **kw: [{"op": "erste_zeile_als_kopf"}, dict({"op": "hand_behalten", "schluessel": ["Name"], "handspalten": "Notiz"}, **kw)]

def lauf(ctx, doc, q):
    try:
        AE.aktualisiere_abfrage(ctx, doc, q); AE.speichere_abfrage(doc, q); return None
    except Exception as e:
        return "%s: %s" % (type(e).__name__, e)

def holen(doc, q):
    return E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)[q.name])

def bereich(doc, q):
    a = doc.DatabaseRanges.getByName(q.ziel["bereich"]).getDataArea()
    return (a.Sheet, a.StartColumn, a.StartRow, a.EndColumn, a.EndRow)

def zeile(sh, r, c0=0, c1=8):
    return [sh.getCellByPosition(c, r).getString() for c in range(c0, c1)]

def test_schluessel(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, [["Name", "Wert"], ["a", 1], ["a", 2], ["c", 3]])
        q = E.Abfrage("S", {"art": "blatt", "blatt": "Roh"}, SCHR(), {"art": "blatt"})
        f = lauf(ctx, doc, q)
        pruefe("Doppelter Schlüssel in der Ausgabe bricht ab", f is not None and "nicht eindeutig" in f and "Zeilen 1, 2" in f, str(f))
        roh(doc, BASIS)
        q = E.Abfrage("S2", {"art": "blatt", "blatt": "Roh"}, SCHR(), {"art": "blatt"})
        pruefe("Eindeutig: läuft", lauf(ctx, doc, q) is None)
        sh = doc.getSheets().getByName("S2")
        # Nutzer macht den Schlüssel im Blatt doppelt -> Stand im Blatt nicht eindeutig
        sh.getCellRangeByName("A3").setString("a")
        roh(doc, [["Name", "Wert"], ["a", 1], ["b", 2], ["c", 3], ["d", 4]])
        f = lauf(ctx, doc, holen(doc, q))
        pruefe("Doppelter Schlüssel im Blatt-Stand bricht ab", f is not None and "im letzten Stand" in f, str(f))
        # mehrere Schlüsselspalten machen es eindeutig
        roh(doc, [["Name", "Teil", "Wert"], ["a", "x", 1], ["a", "y", 2], ["c", "x", 3]])
        q = E.Abfrage("S3", {"art": "blatt", "blatt": "Roh"}, SCHR(schluessel=["Name", "Teil"]), {"art": "blatt"})
        pruefe("Zwei Schlüsselspalten: eindeutig", lauf(ctx, doc, q) is None)
    finally:
        doc.close(True)

def test_folgen(ctx):
    for art in ("blatt", "zelle"):
        desk, doc = T.neues_calc(ctx)
        try:
            roh(doc, BASIS)
            sheets = doc.getSheets()
            ziel = {"art": "blatt"}
            if art == "zelle":
                sheets.insertNewByName("Ziel", 2); ziel = {"art": "zelle", "blatt": "Ziel", "zelle": "B2"}
            q = E.Abfrage("Q", {"art": "blatt", "blatt": "Roh"}, SCHR(), ziel)
            pruefe("[%s] erster Lauf" % art, lauf(ctx, doc, q) is None)
            q = holen(doc, q)
            sh = sheets.getByName("Ziel" if art == "zelle" else "Q")
            b = bereich(doc, q)
            sh.getCellByPosition(b[3], b[2] + 1).setString("N-a")
            sh.getCellByPosition(b[3], b[2] + 3).setString("N-c")
            sh.moveRange(sh.getCellRangeByName("F10").getCellAddress(), doc.DatabaseRanges.getByName(q.ziel["bereich"]).getDataArea())
            sh.getCellRangeByName("A1").setString("MEIN TITEL")
            sh.getCellRangeByName("B2").setString("MEINE DATEN")
            roh(doc, BASIS + [["d", 4]])
            pruefe("[%s] Aktualisieren nach Verschieben" % art, lauf(ctx, doc, holen(doc, q)) is None)
            q2 = holen(doc, q)
            pruefe("[%s] Ziel auf Zelle F10 umgestellt" % art, q2.ziel.get("art") == "zelle" and q2.ziel.get("zelle") == "F10"
                   and q2.ziel.get("blatt") == sh.Name, str(q2.ziel))
            pruefe("[%s] Daten wachsen an neuer Stelle" % art, zeile(sh, 13, 5, 8)[:3] == ["d", "4", ""], str(zeile(sh, 13, 5, 8)))
            pruefe("[%s] Handeinträge mitgenommen" % art, zeile(sh, 10, 5, 8)[2] == "N-a" and zeile(sh, 12, 5, 8)[2] == "N-c", str([zeile(sh, r, 5, 8) for r in range(9, 14)]))
            pruefe("[%s] Fremde Daten an alter Stelle unberührt" % art, sh.getCellRangeByName("A1").getString() == "MEIN TITEL" and sh.getCellRangeByName("B2").getString() == "MEINE DATEN")
            pruefe("[%s] Blatt-Rechtsklick findet die Abfrage über den Bereich" % art, AE.abfrage_fuer_blatt(doc, sh.Name) == "Q")
        finally:
            doc.close(True)

def test_konflikte(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, BASIS)
        sheets = doc.getSheets(); sheets.insertNewByName("Ziel", 2); z = sheets.getByName("Ziel")
        q = E.Abfrage("Q", {"art": "blatt", "blatt": "Roh"}, SCHR(), {"art": "zelle", "blatt": "Ziel", "zelle": "A1"})
        lauf(ctx, doc, q)
        z.getCellRangeByName("A6").setString("FREMD")          # direkt unter der Tabelle (4 Zeilen + Kopf = A1:C4)
        roh(doc, BASIS + [["d", 4], ["e", 5], ["f", 6]])
        f = lauf(ctx, doc, holen(doc, q))
        pruefe("Wachsen: Fremddaten darunter wandern mit (0.8.8), kein Abbruch", f is None, str(f))
        pruefe("Fremde Daten behalten den Abstand (A6 -> A9)", z.getCellRangeByName("A9").getString() == "FREMD" and z.getCellRangeByName("A6").getString() == "e", z.getCellRangeByName("A9").getString())
        # zwei Tabellen dürfen sich nicht berühren
        z.getCellRangeByName("A9").setString("")
        roh(doc, BASIS, "Roh2")
        q2 = E.Abfrage("Q2", {"art": "blatt", "blatt": "Roh2"}, SCHR(), {"art": "zelle", "blatt": "Ziel", "zelle": "A5"})
        f = lauf(ctx, doc, q2)
        pruefe("Zwei Tabellen berühren sich: Abbruch", f is not None and "berühren" in f, str(f))
        q2 = E.Abfrage("Q2", {"art": "blatt", "blatt": "Roh2"}, SCHR(), {"art": "zelle", "blatt": "Ziel", "zelle": "A12"})
        pruefe("Mit Abstand: ok", lauf(ctx, doc, q2) is None)
    finally:
        doc.close(True)

def test_neue_spalten(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, BASIS)
        sheets = doc.getSheets()
        q = E.Abfrage("N", {"art": "blatt", "blatt": "Roh"}, SCHR(), {"art": "blatt"})
        lauf(ctx, doc, q)
        q = holen(doc, q); sh = sheets.getByName("N")
        pruefe("Bekannte Spalten gemerkt", q.ziel.get("spalten") == ["Name", "Wert", "Notiz"], str(q.ziel.get("spalten")))
        # innerhalb: Spalte vor Notiz einfügen (leere Überschrift) und noch eine mit Namen "Wert" (doppelt)
        sh.getColumns().insertByIndex(2, 2)
        sh.getCellRangeByName("C2").setString("hand-c"); sh.getCellRangeByName("D2").setString("hand-d")
        sh.getCellRangeByName("D1").setString("Wert")
        pruefe("Bereich wuchs mit", bereich(doc, q)[3] == 4, str(bereich(doc, q)))
        pruefe("Lauf", lauf(ctx, doc, q) is None)
        q = holen(doc, q)
        kopf = zeile(sh, 0, 0, 6)
        pruefe("Leere Überschrift -> Spalte3, doppelte -> Wert (2)", sorted(kopf[:5]) == sorted(["Name", "Wert", "Spalte3", "Wert (2)", "Notiz"]), str(kopf))
        pruefe("Handspalten im Schritt ergänzt", q.schritte[1]["handspalten"].splitlines() == ["Notiz", "Spalte3", "Wert (2)"], str(q.schritte[1]))
        z1 = dict(zip(zeile(sh, 0, 0, 5), zeile(sh, 1, 0, 5)))
        pruefe("Eingaben blieben erhalten (je Spalte)", z1.get("Spalte3") == "hand-c" and z1.get("Wert (2)") == "hand-d", str(z1))
        # Ohne Häkchen: Spalte rechts außerhalb wird nicht übernommen
        sh.getCellRangeByName("G1").setString("Rechts"); sh.getCellRangeByName("G2").setString("r1")
        lauf(ctx, doc, holen(doc, q))
        pruefe("Ohne Häkchen: rechte Spalte wird nicht übernommen", bereich(doc, q)[3] < 6 and sh.getCellRangeByName("G1").getString() == "Rechts", str(bereich(doc, q)))
        # mit Häkchen
        sh.getCellRangeByName("F1").setString("Rechts"); sh.getCellRangeByName("F2").setString("r1")
        sh.getCellRangeByName("G1").setString(""); sh.getCellRangeByName("G2").setString("")
        q = holen(doc, q); q.schritte[1]["auto_neu"] = True; AE.speichere_abfrage(doc, q)
        # eine andere Tabelle direkt rechts daneben (mit Lücke), die nicht angefasst werden darf
        sh.getCellRangeByName("K1").setString("Fremd"); sh.getCellRangeByName("K2").setString("x")
        f = lauf(ctx, doc, holen(doc, q))
        pruefe("Mit Häkchen: Lauf", f is None, str(f))
        kopf = zeile(sh, 0, 0, 12)
        pruefe("Mit Häkchen: Spalte 'Rechts' übernommen", "Rechts" in kopf and zeile(sh, 1, 0, 12)[kopf.index("Rechts")] == "r1", str(kopf))
        pruefe("Fremde Spalte K (nicht angrenzend) unberührt", sh.getCellRangeByName("K1").getString() == "Fremd")
    finally:
        doc.close(True)

def test_menue(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, BASIS)
        q = E.Abfrage("M", {"art": "blatt", "blatt": "Roh"}, SCHR(), {"art": "blatt"})
        lauf(ctx, doc, q)
        sh = doc.getSheets().getByName("M")
        # Spalte direkt rechts von der Tabelle (außerhalb) + Spalte innen
        sh.getCellRangeByName("D1").setString("Extern"); sh.getCellRangeByName("D2").setString("e1")
        meld = []
        orig = AE.meldung; AE.meldung = lambda c, p, t, *a, **k: meld.append(t) or 1
        try:
            doc.getCurrentController().select(sh.getCellRangeByName("A2"))
            frame = doc.getCurrentController().getFrame()
            AE.befehl_spalten_uebernehmen(ctx, frame, doc)
            pruefe("Menü: ohne Häkchen nichts Neues", meld and "Keine neuen" in meld[-1], str(meld))
            q = holen(doc, q); q.schritte[1]["auto_neu"] = True; AE.speichere_abfrage(doc, q)
            AE.befehl_spalten_uebernehmen(ctx, frame, doc)
        finally:
            AE.meldung = orig
        q = holen(doc, q)
        pruefe("Menü: Spalte übernommen + Meldung", "Extern" in meld[-1] and "Extern" in q.schritte[1]["handspalten"], str(meld))
        pruefe("Menü: Bereich erweitert (sortiert mit)", bereich(doc, q)[3] == 3 and bereich(doc, q)[1] == 0, str(bereich(doc, q)))
    finally:
        doc.close(True)

def test_zu_breiter_bereich(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, BASIS)
        q = E.Abfrage("W", {"art": "blatt", "blatt": "Roh"}, SCHR(), {"art": "blatt"})
        lauf(ctx, doc, q); q = holen(doc, q)
        sh = doc.getSheets().getByName("W")
        db = doc.DatabaseRanges.getByName(q.ziel["bereich"]); a = db.getDataArea(); a.EndColumn = 400; db.setDataArea(a)
        pruefe("Lauf bei zu breitem Bereich", lauf(ctx, doc, q) is None)
        q = holen(doc, q)
        pruefe("Keine SpalteN-Flut", q.schritte[1]["handspalten"].strip() == "Notiz", q.schritte[1]["handspalten"][:80])
        pruefe("Bereich wieder schmal", bereich(doc, q)[3] == 2, str(bereich(doc, q)))
    finally:
        doc.close(True)

def test_formelspalten(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, BASIS)
        q = E.Abfrage("F", {"art": "blatt", "blatt": "Roh"}, SCHR(handspalten="Notiz\nKalk"), {"art": "zelle", "blatt": "Ziel", "zelle": "B2"})
        doc.getSheets().insertNewByName("Ziel", 2)
        lauf(ctx, doc, q); q = holen(doc, q)
        sh = doc.getSheets().getByName("Ziel")
        # Kopf B2:E2 -> Name, Wert, Notiz, Kalk; Daten ab Zeile 3
        kopf = zeile(sh, 1, 1, 5)
        pruefe("Spalten da", kopf[:4] == ["Name", "Wert", "Notiz", "Kalk"], str(kopf))
        for r in (2, 3, 4):
            sh.getCellByPosition(4, r).setFormula("=C%d*2" % (r + 1))
        sh.getCellRangeByName("D3").setString("keine Formel")
        # neue Quellzeile -> neue Zeile bekommt die Formel, Verschieben passt Bezüge an
        roh(doc, BASIS + [["d", 4]])
        q = holen(doc, q)
        pruefe("Lauf 1", lauf(ctx, doc, q) is None)
        q = holen(doc, q)
        pruefe("Formelspalte erkannt", "Kalk" in (q.schritte[1].get("formeln") or {}), str(q.schritte[1]))
        pruefe("Notiz-Spalte ist keine Formelspalte", "Notiz" not in (q.schritte[1].get("formeln") or {}))
        werte = [sh.getCellByPosition(4, r).getFormula() for r in (2, 3, 4, 5)]
        pruefe("Formel in allen 4 Zeilen (inkl. neuer)", werte == ["=C3*2", "=C4*2", "=C5*2", "=C6*2"], str(werte))
        pruefe("Wert berechnet", sh.getCellByPosition(4, 5).getValue() == 8.0, str(sh.getCellByPosition(4, 5).getValue()))
        # Tabelle verschieben: Formeln mit
        db = doc.DatabaseRanges.getByName(q.ziel["bereich"])
        sh.moveRange(sh.getCellRangeByName("H10").getCellAddress(), db.getDataArea())
        roh(doc, BASIS + [["d", 4], ["e", 5]])
        pruefe("Lauf nach Verschieben", lauf(ctx, doc, holen(doc, q)) is None)
        f2 = [sh.getCellRangeByName("K%d" % r).getFormula() for r in (11, 12, 13, 14, 15)]
        pruefe("Formeln an neuer Stelle angepasst", f2 == ["=I11*2", "=I12*2", "=I13*2", "=I14*2", "=I15*2"], str(f2))
        # gemischt: eine Zelle überschreiben -> keine Formelspalte mehr
        sh.getCellRangeByName("K12").setValue(99)
        lauf(ctx, doc, holen(doc, q))
        q = holen(doc, q)
        pruefe("Gemischte Spalte ist keine Formelspalte mehr", "Kalk" not in (q.schritte[1].get("formeln") or {}), str(q.schritte[1].get("formeln")))
    finally:
        doc.close(True)

def test_baender(ctx):
    desk, doc = T.neues_calc(ctx)
    try:
        roh(doc, BASIS + [["d", 4], ["e", 5], ["f", 6]])
        q = E.Abfrage("B", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "zelle", "blatt": "Roh2", "zelle": "A1"})
        doc.getSheets().insertNewByName("Roh2", 2)
        lauf(ctx, doc, q)
        sh = doc.getSheets().getByName("Roh2")
        n1 = len(sh.getPropertyValue("ConditionalFormats").getConditionalFormats())
        roh(doc, BASIS)
        lauf(ctx, doc, holen(doc, q))
        n2 = len(sh.getPropertyValue("ConditionalFormats").getConditionalFormats())
        pruefe("Bedingte Formate sammeln sich nicht an", n2 <= n1 and n2 == 1, "%s -> %s" % (n1, n2))
    finally:
        doc.close(True)

def main():
    import faulthandler; faulthandler.dump_traceback_later(170, exit=True)
    ctx = T.verbinden()
    for t in (test_schluessel, test_folgen, test_konflikte, test_neue_spalten, test_menue, test_zu_breiter_bereich, test_formelspalten, test_baender):
        try:
            t(ctx)
        except Exception as e:
            import traceback; traceback.print_exc()
            pruefe(t.__name__ + " ohne Ausnahme", False, str(e))
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0
sys.exit(main())
