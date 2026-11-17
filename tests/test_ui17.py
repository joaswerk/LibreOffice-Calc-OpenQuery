# -*- coding: utf-8 -*-
"""0.7.0: Knopf „Dokument speichern“, Zielzelle beim neuen Blatt, Tabellenmenü (Einträge)."""
import os, sys, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lo as T
AE, E = T.AE, T.E
pruefe = T.pruefe


def main():
    import faulthandler; faulthandler.dump_traceback_later(120, exit=True)
    os.environ["ABFRAGE_MELDUNGSLOG"] = os.path.join(os.environ.get("SCRATCH", "/tmp"), "meld17.log")
    ctx = T.verbinden(); desk, doc = T.neues_calc(ctx)
    try:
        frame = doc.getCurrentController().getFrame()
        sh = doc.getSheets()
        sh.insertNewByName("Roh", 1)
        b = sh.getByName("Roh")
        for r, z in enumerate([["Name", "Menge"], ["a", 1], ["b", 2]]):
            for c, v in enumerate(z):
                (b.getCellByPosition(c, r).setString if isinstance(v, str) else b.getCellByPosition(c, r).setValue)(v)

        # Zielzelle beim neuen Blatt
        q = E.Abfrage("Z1", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt", "zelle": "C3"})
        AE.aktualisiere_abfrage(ctx, doc, q)
        z = sh.getByName("Z1")
        pruefe("Neues Blatt: Kopf steht ab C3", z.getCellRangeByName("C3").getString() == "Name" and z.getCellRangeByName("A1").getString() == "",
               z.getCellRangeByName("C3").getString())
        pruefe("Neues Blatt: Daten ab C4", z.getCellRangeByName("C4").getString() == "a" and z.getCellRangeByName("D5").getValue() == 2)
        q2 = E.Abfrage("Z2", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt"})
        AE.aktualisiere_abfrage(ctx, doc, q2)
        pruefe("Ohne Zielzelle: A1", sh.getByName("Z2").getCellRangeByName("A1").getString() == "Name")
        q3 = E.Abfrage("Z3", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "blatt", "zelle": "ÄÄ"})
        try:
            AE.aktualisiere_abfrage(ctx, doc, q3)
            pruefe("Ungültige Zielzelle wird gemeldet", False)
        except Exception as e:
            pruefe("Ungültige Zielzelle wird gemeldet", "Zielzelle" in str(e) or "Zelle" in str(e), str(e))

        # Speichern-Knopf
        ed = AE.Editor(ctx, frame, doc, E.Abfrage("Q1", {"art": "blatt", "blatt": "Roh"}, [{"op": "erste_zeile_als_kopf"}], {"art": "keine"}))
        ed.run(ohne_dialog=True)
        meld = []
        orig = ed.meld
        ed.meld = lambda t, *a, **k: meld.append(t)
        ed.dokument_speichern()
        time.sleep(0.8)
        pruefe("Ohne Speicherort: Hinweis statt Absturz", len(meld) == 1 and "Speicherort" in meld[0], str(meld))
        url = AE.uno.systemPathToFileUrl(os.path.join(tempfile.mkdtemp(), "ds.ods"))
        doc.storeAsURL(url, ())
        ed.neuer_schritt("sortieren", {"spalte1": "Menge", "richtung1": "ab"}, True)
        meld.clear()
        ed.dokument_speichern()
        time.sleep(1.0)
        d2 = desk.loadComponentFromURL(url, "_blank", 0, (AE.PropertyValue("Hidden", 0, True, 0),))
        try:
            p2 = d2.getDocumentProperties().getUserDefinedProperties()
            ok = p2.getPropertySetInfo().hasPropertyByName("AE:Q1") and "sortieren" in str(p2.getPropertyValue("AE:Q1"))
            pruefe("Dokument speichern: Datei enthält den aktuellen Abfragestand", ok and not meld, str(meld))
        finally:
            d2.close(True)

        # Tabellenmenü: Einträge und Operationen vorhanden
        pm, ids = ed.baue_tabellenmenue()
        aktionen = [a for a in ids.values() if a[0] == "schritt"]
        pruefe("Tabellenmenü: alle Schritte gibt es", aktionen and all(a[1] in E.OPS for a in aktionen), str([a[1] for a in aktionen if a[1] not in E.OPS]))
        pruefe("Tabellenmenü: Kopieren der Vorschau", ("kopieren",) in ids.values())
        ed.kopiere_vorschau()
        tx = AE.DataFlavor()
    finally:
        try:
            doc.close(True)
        except Exception:
            pass
    fehler = [e for e in T.ergebnisse if not e[1]]
    print("\n%d Prüfungen, %d Fehler" % (len(T.ergebnisse), len(fehler)))
    return 1 if fehler else 0


sys.exit(main())
