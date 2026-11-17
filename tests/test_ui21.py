# -*- coding: utf-8 -*-
"""Handeinträge: Verhalten, wenn die Ausgabetabelle im Blatt verschoben wird (Prüfung, kein Bestehen-Test)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E

def werte(sh, adr):
    r = sh.getCellRangeByName(adr)
    return [list(z) for z in r.getDataArray()]

def neu(doc):
    sh = doc.getSheets()
    sh.insertNewByName("Roh", 1); b = sh.getByName("Roh")
    for r, z in enumerate([["Name", "Wert"], ["a", 1], ["b", 2], ["c", 3]]):
        for c, v in enumerate(z):
            (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)

SCHR = [{"op": "erste_zeile_als_kopf"}, {"op": "hand_behalten", "schluessel": ["Name"], "handspalten": "Notiz"}]

def szenario(ctx, art):
    desk, doc = T.neues_calc(ctx)
    try:
        neu(doc)
        sheets = doc.getSheets()
        if art == "zelle":
            sheets.insertNewByName("Ziel", 2)
            ziel = {"art": "zelle", "blatt": "Ziel", "zelle": "B2"}
        else:
            ziel = {"art": "blatt"}
        q = E.Abfrage("Q", {"art": "blatt", "blatt": "Roh"}, [dict(s) for s in SCHR], ziel)
        AE.aktualisiere_abfrage(ctx, doc, q)
        AE.speichere_abfrage(doc, q)
        sh = sheets.getByName("Ziel" if art == "zelle" else "Q")
        a0 = doc.DatabaseRanges.getByName(q.ziel["bereich"]).getDataArea() if q.ziel.get("bereich") else None
        print("[%s] erster Lauf, Bereich: %s" % (art, (a0.StartColumn, a0.StartRow, a0.EndColumn, a0.EndRow) if a0 else None))
        # Handeinträge tippen (Spalte Notiz = letzte Spalte)
        sp = a0.EndColumn
        sh.getCellByPosition(sp, a0.StartRow + 1).setString("N-a")
        sh.getCellByPosition(sp, a0.StartRow + 3).setString("N-c")
        # Tabelle verschieben nach F10
        ad = doc.DatabaseRanges.getByName(q.ziel["bereich"]).getDataArea()
        sh.moveRange(sh.getCellRangeByName("F10").getCellAddress(), ad)
        # an der alten Stelle trägt der Nutzer eigene Daten ein
        sh.getCellRangeByName("B2").setString("MEINE DATEN")
        sh.getCellRangeByName("A1").setString("MEIN TITEL")
        a1 = doc.DatabaseRanges.getByName(q.ziel["bereich"]).getDataArea()
        print("[%s] nach Verschieben Bereich: %s" % (art, (a1.StartColumn, a1.StartRow, a1.EndColumn, a1.EndRow)))
        # Quelle ändert sich, dann aktualisieren
        sheets.getByName("Roh").getCellRangeByName("A5").setString("d"); sheets.getByName("Roh").getCellRangeByName("B5").setValue(4)
        q2 = E.Abfrage.from_json(AE.gespeicherte_abfragen(doc)["Q"])
        try:
            AE.aktualisiere_abfrage(ctx, doc, q2)
            fehler = None
        except Exception as e:
            fehler = "%s: %s" % (type(e).__name__, e)
        print("[%s] Aktualisieren -> Fehler: %s" % (art, fehler))
        sh = sheets.getByName("Ziel" if art == "zelle" else "Q")
        cur = sh.createCursor(); cur.gotoEndOfUsedArea(False)
        print("[%s] belegt bis: %s" % (art, cur.getRangeAddress().EndRow))
        for z in range(0, 16):
            zeile = [sh.getCellByPosition(c, z).getString() for c in range(0, 10)]
            if any(zeile):
                print("   Z%02d %s" % (z + 1, zeile))
        if q2.ziel.get("bereich") and doc.DatabaseRanges.hasByName(q2.ziel["bereich"]):
            a2 = doc.DatabaseRanges.getByName(q2.ziel["bereich"]).getDataArea()
            print("[%s] Bereich danach: %s (Blatt %d)" % (art, (a2.StartColumn, a2.StartRow, a2.EndColumn, a2.EndRow), a2.Sheet))
    finally:
        try: doc.close(True)
        except Exception: pass

def main():
    import faulthandler; faulthandler.dump_traceback_later(150, exit=True)
    ctx = T.verbinden()
    for art in ("zelle", "blatt"):
        szenario(ctx, art)
    return 0
sys.exit(main())
