# -*- coding: utf-8 -*-
"""0.6.1: Reiterfarbe nur für die eigene Abfrage, Diagnose beim Löschen, Menü-Verzögerung (_nach_menue)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def main():
    import faulthandler; faulthandler.dump_traceback_later(120, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld14.log")
    diag = os.path.join(os.path.expanduser("~"), "OpenQuery-Diagnose.txt")
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        sh = doc.getSheets()
        sh.insertNewByName("Roh", 1)
        b = sh.getByName("Roh")
        for r, z in enumerate([["A", "B"], [1, 2], [3, 4]]):
            for c, v in enumerate(z):
                (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)
        # Reiterfarbe: fremd gesetzte Farbe bleibt, eigene wird zurückgenommen
        x = E.Abfrage("TX", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt", "reiter": False})
        AE.aktualisiere_abfrage(ctx, doc, x)
        sh.getByName("TX").TabColor = 0x1F4E79          # von Hand gesetzt, zufällig gleich einer Palettenfarbe
        AE.aktualisiere_abfrage(ctx, doc, x)
        pruefe("Von Hand gesetzte Reiterfarbe bleibt (Reiter-Häkchen aus)", sh.getByName("TX").TabColor == 0x1F4E79, hex(sh.getByName("TX").TabColor))
        y = E.Abfrage("TY", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt", "reiter": True, "farbe": "gruen"})
        AE.aktualisiere_abfrage(ctx, doc, y)
        pruefe("Reiterfarbe gesetzt, Abfrage merkt sie sich", sh.getByName("TY").TabColor == 0x375623 and y.ziel.get("reiter_farbe") == 0x375623)
        y.ziel["reiter"] = False
        AE.aktualisiere_abfrage(ctx, doc, y)
        pruefe("Häkchen aus: eigene Farbe wird zurückgenommen", sh.getByName("TY").TabColor == -1)
        pruefe("Fremdes Blatt TX unberührt", sh.getByName("TX").TabColor == 0x1F4E79)

        # Diagnose beim Löschen + Menübefehl verzögert
        open(diag, "w").close()
        AE.speichere_abfrage(doc, x)
        ed = AE.Editor(ctx, frame, doc, E.Abfrage.from_json(x.to_json()))
        ed.run(ohne_dialog=True)
        orig = AE.meldung
        AE.meldung = lambda *a, **k: 2
        try:
            ed.abfrage_loeschen()
        finally:
            AE.meldung = orig
        for _ in range(40):                           # Löschen läuft erst nach dem Ereignis
            time.sleep(0.1)
            if "Abfrage löschen: fertig" in open(diag, encoding="utf-8").read():
                break
        text = open(diag, encoding="utf-8").read()
        pruefe("Diagnose: Löschen protokolliert", "Abfrage löschen: bestätigt" in text and "Abfrage löschen: fertig" in text, text[-200:])
        laeuft = []
        ed._nach_menue("Test", lambda: laeuft.append(1))
        for _ in range(30):
            if laeuft:
                break
            time.sleep(0.1)
        pruefe("Menübefehl läuft nach dem Ereignis", laeuft == [1])
        text = open(diag, encoding="utf-8").read()
        pruefe("Diagnose: Menübefehl protokolliert", "Befehl fertig: Test" in text)
    finally:
        try:
            os.remove(diag)
        except Exception:
            pass
        doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
