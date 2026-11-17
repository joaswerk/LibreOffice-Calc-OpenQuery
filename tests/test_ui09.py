# -*- coding: utf-8 -*-
"""Tests für 0.4.1: Neue Abfrage im Menü, Sprung ins Ausgabeblatt, Blattauswahl in der Quelle, Platzhalter, Raster-Wechsel."""
import os, sys, time, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def schreibe(doc, name, rows):
    sh = doc.getSheets()
    if not sh.hasByName(name):
        sh.insertNewByName(name, sh.getCount())
    b = sh.getByName(name)
    for r, z in enumerate(rows):
        for c, v in enumerate(z):
            cell = b.getCellByPosition(c, r)
            cell.setString(v) if isinstance(v, str) else cell.setValue(v)


def main():
    import faulthandler
    faulthandler.dump_traceback_later(90, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld09.log")
    os.environ["ABFRAGE_AUTOOK"] = "2"
    ctx = T.verbinden()
    desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        schreibe(doc, "Roh", [["Menge", "Preis"], [1, 2], [3, 4]])
        schreibe(doc, "Eins", [["x"]])
        sh = doc.getSheets()

        # Menü
        pruefe("Abfragenmenü beginnt mit „Neue Abfrage“", AE.Editor.ABFRAGE_BEFEHLE[0] == ("Neue Abfrage", "neu"),
               str(AE.Editor.ABFRAGE_BEFEHLE[0]))

        # Blattauswahl in der Quelle
        q = AE.QuellenDialog(ctx, doc, None, None, {"Eins": "Eins"}, "Roh")
        namen, texte, vor = q._blaetter()
        pruefe("Quelle: eigenes Ausgabeblatt wird nicht angeboten", "Roh" not in namen, str(namen))
        pruefe("Quelle: Ausgabeblatt anderer Abfrage ist markiert", any("Ausgabe von" in t for t in texte), str(texte))
        pruefe("Quelle: Vorauswahl ist nie ein Ausgabeblatt", vor >= 0 and namen[vor] not in ("Eins", "Roh"), str(namen[vor] if vor >= 0 else vor))
        q2 = AE.QuellenDialog(ctx, doc, {"art": "blatt", "blatt": "Eins"}, None, {"Eins": "Eins"}, None)
        n2, t2, v2 = q2._blaetter()
        pruefe("Quelle: gespeicherte Wahl bleibt erhalten", v2 >= 0 and n2[v2] == "Eins", str((n2, v2)))

        # Laden springt ins Ausgabeblatt; Platzhalter bei leerer Abfrage
        ed = AE.Editor(ctx, frame, doc, E.Abfrage("Neu1", {}, []))
        ed.run(ohne_dialog=True)
        pruefe("Leere Abfrage: Hinweis statt Raster", ed._leer is True, str(ed._leer))
        ed.abfrage.quelle = {"art": "blatt", "blatt": "Roh"}
        ed.quelle_laden(); ed.liste_neu(); ed.zeige()
        pruefe("Nach Quellwahl: Raster sichtbar", ed._leer is False)
        a0 = ed.d.alias["grid"]
        ed.zeige()
        pruefe("Raster wechselt bei jedem Aufbau", ed.d.alias["grid"] != a0, "%s -> %s" % (a0, ed.d.alias["grid"]))
        gm = ed.d.modell("grid")
        pruefe("Geparktes Raster liegt außerhalb", ed.d.modell("gridA" if ed.d.alias["grid"] == "gridB" else "gridB").PositionX < -1000)
        doc.getCurrentController().setActiveSheet(sh.getByName("Roh"))
        r = ed.laden(schliessen=False)
        ed._zum_ausgabeblatt()
        akt = doc.getCurrentController().getActiveSheet().Name
        pruefe("Schließen und Laden springt ins Ausgabeblatt", akt == "Neu1", akt)
    finally:
        doc.close(True)
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
